"""
MezarBot müzik veritabanı katmanı (şema + migrasyonlar + sorgular + cache).

database.py'deki ORTAK SQLite bağlantısını (`db`) kullanır ama kendi tablolarını kendisi kurar:
    muzik_ayarlar                 → sunucu başına müzik ayarları (DJ rolü, oylama, 7/24, istek kanalı ...)
    muzik_calma_listeleri         → kullanıcıların kişisel çalma listeleri (global, sunucudan bağımsız)
    muzik_calma_listesi_parcalari → liste içindeki parçalar
    muzik_bot_durum               → bot geneli anahtar/değer (ör. yt-dlp son güncelleme kontrolü)

Kurallar (AGENTS.md):
 - Tüm sorgular parametreli (?). Dinamik kolon adları MUZIK_AYAR_KOLONLARI beyaz listesinden doğrulanır.
 - Migrasyonlar eklemeli ve idempotent: muzik_veritabanini_kur() istediğin kadar çağrılabilir.
 - _muzik_ayar_cache her yazma ile birlikte güncellenir (sıcak yolda — on_message — DB sorgusu yok).
"""
import logging
import sqlite3
import time

from database import db
from yapilandirma import SAHIP_ID
from dil import _t

logger = logging.getLogger('MezarBot.MuzikDB')

# ── Sunucu ayarları: kolon → (SQL tipi/varsayılanı, Python varsayılanı) ──
_AYAR_SEMASI = {
    'dj_rol_id':              ("INTEGER", None),        # None = DJ sistemi kapalı (herkes kontrol eder)
    'oylama_aktif':           ("INTEGER DEFAULT 0", 0),  # DJ rolü olmasa da oylamalı atla
    'oylama_orani':           ("REAL DEFAULT 0.5", 0.5),  # dinleyicilerin ne kadarı oy vermeli (0.1–1.0)
    'varsayilan_ses':         ("INTEGER DEFAULT 60", 60),   # %100 çok yüksek geliyordu (sahibin isteği)
    'son_ses':                ("INTEGER", None),        # en son ayarlanan ses (hatırlanır); None → varsayılan
    'surekli_mod':            ("INTEGER DEFAULT 0", 0),  # 7/24: boşta/yalnızken kanaldan çıkma
    'otomatik_oynatma':       ("INTEGER DEFAULT 0", 0),  # sıra bitince benzer parçalarla devam
    'bosta_zaman_asimi':      ("INTEGER DEFAULT 180", 180),  # saniye; boşta/yalnız kalınca ayrılma süresi
    'normalizasyon':          ("INTEGER DEFAULT 0", 0),  # ses normalizasyonu varsayılan açık mı
    'istek_kanal_id':         ("INTEGER", None),        # şarkı istek kanalı (mesaj = arama)
    'panel_kanal_id':         ("INTEGER", None),        # son kontrol paneli mesajının kanalı (yeniden başlatma temizliği)
    'panel_mesaj_id':         ("INTEGER", None),
}
MUZIK_AYAR_KOLONLARI = frozenset(_AYAR_SEMASI)
VARSAYILAN_AYARLAR = {k: v[1] for k, v in _AYAR_SEMASI.items()}

SES_MIN, SES_MAX = 0, 150
LISTE_LIMITI = 25          # kullanıcı başına kişisel liste sayısı
LISTE_PARCA_LIMITI = 500   # liste başına parça sayısı
LISTE_AD_UZUNLUK = 40

_muzik_ayar_cache = {}     # {sunucu_id: dict(ayarlar)} — sadece DB'de satırı olan sunucular


def muzik_veritabanini_kur():
    """Müzik tablolarını oluşturur, eksik kolonları ekler, eski ayarları taşır ve cache'i yükler. İdempotent."""
    c = db.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS muzik_ayarlar (sunucu_id INTEGER PRIMARY KEY)")
    for kolon, (tip, _) in _AYAR_SEMASI.items():
        try:
            c.execute(f"ALTER TABLE muzik_ayarlar ADD COLUMN {kolon} {tip}")
        except sqlite3.OperationalError:
            pass  # kolon zaten var
    c.execute("""CREATE TABLE IF NOT EXISTS muzik_calma_listeleri (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kullanici_id INTEGER NOT NULL,
        ad TEXT NOT NULL,
        olusturma REAL NOT NULL,
        UNIQUE (kullanici_id, ad)
    )""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_muzik_liste_ad ON muzik_calma_listeleri (ad COLLATE NOCASE)")
    c.execute("""CREATE TABLE IF NOT EXISTS muzik_calma_listesi_parcalari (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        liste_id INTEGER NOT NULL,
        sira INTEGER NOT NULL,
        sorgu TEXT NOT NULL,
        baslik TEXT,
        url TEXT,
        sure INTEGER
    )""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_muzik_liste_parca ON muzik_calma_listesi_parcalari (liste_id, sira)")
    c.execute("CREATE TABLE IF NOT EXISTS muzik_bot_durum (anahtar TEXT PRIMARY KEY, deger TEXT)")
    # Eski !oygec ayarı (sunucu_ayarlar.oygec_aktif) → muzik_ayarlar.oylama_aktif.
    # Sadece müzik satırı HİÇ olmayan sunucular için (sonraki çalıştırmalarda yeni ayarı ezmez).
    try:
        c.execute("""INSERT OR IGNORE INTO muzik_ayarlar (sunucu_id, oylama_aktif)
                     SELECT sunucu_id, 1 FROM sunucu_ayarlar WHERE oygec_aktif = 1""")
    except sqlite3.OperationalError:
        pass  # sunucu_ayarlar / oygec_aktif yok (çok eski şema) — taşınacak bir şey yok
    # Tek seferlik (2026-09-13): varsayılan ses %100 → %60; hatırlanan %100 de sıfırlanır (yeni varsayılan geçerli olur).
    if c.execute("SELECT 1 FROM muzik_bot_durum WHERE anahtar = 'varsayilan_ses_60'").fetchone() is None:
        c.execute("UPDATE muzik_ayarlar SET varsayilan_ses = 60 WHERE varsayilan_ses IS NULL OR varsayilan_ses = 100")
        c.execute("UPDATE muzik_ayarlar SET son_ses = NULL WHERE son_ses = 100")
        c.execute("INSERT INTO muzik_bot_durum (anahtar, deger) VALUES ('varsayilan_ses_60', ?)", (str(int(time.time())),))
    db.commit()
    muzik_cache_yukle()


def muzik_cache_yukle():
    global _muzik_ayar_cache
    c = db.cursor()
    c.execute("SELECT * FROM muzik_ayarlar")
    _muzik_ayar_cache = {row['sunucu_id']: dict(row) for row in c.fetchall()}
    logger.info(f"🎵 Müzik ayarları yüklendi: {len(_muzik_ayar_cache)} sunucu")


def muzik_ayar_al(sunucu_id):
    """Sunucunun müzik ayarlarını varsayılanlarla birleştirip KOPYA olarak döner (cache — DB sorgusu yok)."""
    ayar = dict(VARSAYILAN_AYARLAR)
    kayit = _muzik_ayar_cache.get(sunucu_id)
    if kayit:
        ayar.update({k: v for k, v in kayit.items() if k in MUZIK_AYAR_KOLONLARI and v is not None})
    ayar['sunucu_id'] = sunucu_id
    return ayar


def istek_kanali_mi(sunucu_id, kanal_id):
    """on_message sıcak yolu için: bu kanal sunucunun şarkı istek kanalı mı? (sadece cache)"""
    kayit = _muzik_ayar_cache.get(sunucu_id)
    return bool(kayit and kayit.get('istek_kanal_id') == kanal_id)


def muzik_ayar_guncelle(sunucu_id, **kwargs):
    """Ayar(lar)ı yazar ve cache'i günceller. Kolon adları beyaz listeden doğrulanır (aksi halde ValueError)."""
    if not kwargs:
        return
    gecersiz = [k for k in kwargs if k not in MUZIK_AYAR_KOLONLARI]
    if gecersiz:
        raise ValueError(f"muzik_ayarlar: geçersiz kolon adı: {', '.join(map(repr, gecersiz))}")
    c = db.cursor()
    c.execute("INSERT OR IGNORE INTO muzik_ayarlar (sunucu_id) VALUES (?)", (sunucu_id,))
    setler = ", ".join(f"{k} = ?" for k in kwargs)
    c.execute(f"UPDATE muzik_ayarlar SET {setler} WHERE sunucu_id = ?", (*kwargs.values(), sunucu_id))
    db.commit()
    # Cache = DB satırının birebir kopyası (SQL varsayılanları dahil) — tek indeksli SELECT, sıcak yolda değil
    c.execute("SELECT * FROM muzik_ayarlar WHERE sunucu_id = ?", (sunucu_id,))
    _muzik_ayar_cache[sunucu_id] = dict(c.fetchone())


def istek_kanallari():
    """[(sunucu_id, istek_kanal_id)] — şarkı istek kanalı ayarlı sunucular (cache)."""
    return [(sid, a['istek_kanal_id']) for sid, a in _muzik_ayar_cache.items() if a.get('istek_kanal_id')]


def panel_kayitlari():
    """Yeniden başlatma sonrası temizlik için: [(sunucu_id, kanal_id, mesaj_id, istek_kanal_id)]."""
    return [(sid, a.get('panel_kanal_id'), a.get('panel_mesaj_id'), a.get('istek_kanal_id'))
            for sid, a in _muzik_ayar_cache.items() if a.get('panel_mesaj_id')]


# ══════════════════════════════════════════════
#  KİŞİSEL ÇALMA LİSTELERİ (kullanıcı başına, global)
# ══════════════════════════════════════════════

class ListeHatasi(Exception):
    """Kullanıcıya gösterilebilir liste hatası (mesajı Türkçe)."""


def _ad_temizle(ad):
    ad = " ".join(str(ad or "").split())[:LISTE_AD_UZUNLUK]
    if not ad:
        raise ListeHatasi(_t("Liste adı boş olamaz."))
    return ad


def listeleri_al(kullanici_id):
    """[(id, ad, parca_sayisi, toplam_sure)] — ada göre sıralı."""
    c = db.cursor()
    c.execute("""SELECT l.id, l.ad, COUNT(p.id), COALESCE(SUM(p.sure), 0)
                 FROM muzik_calma_listeleri l
                 LEFT JOIN muzik_calma_listesi_parcalari p ON p.liste_id = l.id
                 WHERE l.kullanici_id = ? GROUP BY l.id ORDER BY l.ad COLLATE NOCASE""", (kullanici_id,))
    return [tuple(r) for r in c.fetchall()]


def genel_listeleri_al(haric_kullanici_id=None):
    """Kullanıcının kendi listeleri dışındaki genel listeleri döner:
    [(id, ad, parca_sayisi, toplam_sure, kullanici_id)]
    Önce dolu listeler ve bot sahibinin listeleri gelir. Ada göre tekilleştirilir."""
    c = db.cursor()
    sahip = SAHIP_ID or 0
    if haric_kullanici_id:
        c.execute("""SELECT l.id, l.ad, COUNT(p.id), COALESCE(SUM(p.sure), 0), l.kullanici_id
                     FROM muzik_calma_listeleri l
                     LEFT JOIN muzik_calma_listesi_parcalari p ON p.liste_id = l.id
                     WHERE l.kullanici_id != ?
                     GROUP BY l.id
                     HAVING COUNT(p.id) > 0 OR l.kullanici_id = ?
                     ORDER BY (COUNT(p.id) > 0) DESC, CASE WHEN l.kullanici_id = ? THEN 0 ELSE 1 END, l.ad COLLATE NOCASE""",
                  (haric_kullanici_id, sahip, sahip))
    else:
        c.execute("""SELECT l.id, l.ad, COUNT(p.id), COALESCE(SUM(p.sure), 0), l.kullanici_id
                     FROM muzik_calma_listeleri l
                     LEFT JOIN muzik_calma_listesi_parcalari p ON p.liste_id = l.id
                     GROUP BY l.id
                     HAVING COUNT(p.id) > 0 OR l.kullanici_id = ?
                     ORDER BY (COUNT(p.id) > 0) DESC, CASE WHEN l.kullanici_id = ? THEN 0 ELSE 1 END, l.ad COLLATE NOCASE""",
                  (sahip, sahip))
    gorulen = set()
    sonuc = []
    for r in c.fetchall():
        ad_key = r[1].casefold()
        if ad_key in gorulen:
            continue
        gorulen.add(ad_key)
        sonuc.append(tuple(r))
    return sonuc


def liste_bul_ayrintili(kullanici_id, ad, genel_ara=True):
    """(liste_id, sahip_id, liste_adi) ya da None döner.
    Öncelik:
    1. kullanici_id'nin kendi listesi (boş olsa bile)
    2. genel_ara=True ise: parçası olan listeler (sahip öncelikli), sonra diğerleri"""
    try:
        ad_temiz = _ad_temizle(ad)
    except ListeHatasi:
        return None
    c = db.cursor()
    if not genel_ara:
        c.execute("SELECT id, kullanici_id, ad FROM muzik_calma_listeleri WHERE kullanici_id = ? AND ad = ? COLLATE NOCASE",
                  (kullanici_id, ad_temiz))
        r = c.fetchone()
        return (r[0], r[1], r[2]) if r else None

    sahip = SAHIP_ID or 0
    c.execute("""SELECT l.id, l.kullanici_id, l.ad, COUNT(p.id) as parca_sayisi
                 FROM muzik_calma_listeleri l
                 LEFT JOIN muzik_calma_listesi_parcalari p ON p.liste_id = l.id
                 WHERE l.ad = ? COLLATE NOCASE
                 GROUP BY l.id
                 ORDER BY
                     CASE WHEN l.kullanici_id = ? THEN 0 ELSE 1 END,
                     (COUNT(p.id) > 0) DESC,
                     CASE WHEN l.kullanici_id = ? THEN 0 ELSE 1 END,
                     l.id ASC
                 LIMIT 1""", (ad_temiz, kullanici_id, sahip))
    r = c.fetchone()
    return (r[0], r[1], r[2]) if r else None


def liste_bul(kullanici_id, ad, genel_ara=True):
    """Liste id'si (büyük/küçük harf duyarsız) ya da None."""
    ayrinti = liste_bul_ayrintili(kullanici_id, ad, genel_ara=genel_ara)
    return ayrinti[0] if ayrinti else None


def liste_olustur(kullanici_id, ad):
    """Yeni liste oluşturur (varsa mevcut id'yi döner). Limit aşımında ListeHatasi."""
    ad = _ad_temizle(ad)
    mevcut = liste_bul(kullanici_id, ad, genel_ara=False)
    if mevcut:
        return mevcut
    c = db.cursor()
    c.execute("SELECT COUNT(*) FROM muzik_calma_listeleri WHERE kullanici_id = ?", (kullanici_id,))
    if c.fetchone()[0] >= LISTE_LIMITI:
        raise ListeHatasi(_t("En fazla {LISTE_LIMITI} kişisel listen olabilir.", LISTE_LIMITI=LISTE_LIMITI))
    c.execute("INSERT INTO muzik_calma_listeleri (kullanici_id, ad, olusturma) VALUES (?, ?, ?)",
              (kullanici_id, ad, time.time()))
    db.commit()
    return c.lastrowid


def liste_parcalari(liste_id):
    """[{'sorgu','baslik','url','sure'}] — sıraya göre."""
    c = db.cursor()
    c.execute("""SELECT sorgu, baslik, url, sure FROM muzik_calma_listesi_parcalari
                 WHERE liste_id = ? ORDER BY sira, id""", (liste_id,))
    return [dict(r) for r in c.fetchall()]


def listeye_parca_ekle(liste_id, parcalar, bastan_yaz=False):
    """parcalar: [{'sorgu','baslik','url','sure'}]. Limit kadarını ekler; eklenen sayıyı döner.
    bastan_yaz=True: listedeki eski parçalar silinir (kuyruğu kaydet)."""
    c = db.cursor()
    if bastan_yaz:
        c.execute("DELETE FROM muzik_calma_listesi_parcalari WHERE liste_id = ?", (liste_id,))
    c.execute("SELECT COUNT(*), COALESCE(MAX(sira), 0) FROM muzik_calma_listesi_parcalari WHERE liste_id = ?", (liste_id,))
    sayi, son_sira = c.fetchone()
    yer = max(0, LISTE_PARCA_LIMITI - sayi)
    eklenecek = list(parcalar)[:yer]
    c.executemany(
        "INSERT INTO muzik_calma_listesi_parcalari (liste_id, sira, sorgu, baslik, url, sure) VALUES (?, ?, ?, ?, ?, ?)",
        [(liste_id, son_sira + i + 1, p['sorgu'][:500], (p.get('baslik') or '')[:200] or None,
          (p.get('url') or '')[:500] or None, int(p['sure']) if p.get('sure') else None)
         for i, p in enumerate(eklenecek)])
    db.commit()
    return len(eklenecek)


def listeden_parca_cikar(liste_id, sira_no):
    """1 tabanlı sıra numarasındaki parçayı siler; silinen parçanın başlığını ya da None döner."""
    parcalar = liste_parcalari_idli(liste_id)
    if not 1 <= sira_no <= len(parcalar):
        return None
    pid, baslik = parcalar[sira_no - 1]
    c = db.cursor()
    c.execute("DELETE FROM muzik_calma_listesi_parcalari WHERE id = ? AND liste_id = ?", (pid, liste_id))
    db.commit()
    return baslik or _t("parça")


def liste_parcalari_idli(liste_id):
    c = db.cursor()
    c.execute("SELECT id, COALESCE(baslik, sorgu) FROM muzik_calma_listesi_parcalari WHERE liste_id = ? ORDER BY sira, id",
              (liste_id,))
    return [tuple(r) for r in c.fetchall()]


def liste_sil(kullanici_id, liste_id):
    """Sadece sahibinin listesini siler. Başarılıysa True."""
    c = db.cursor()
    c.execute("DELETE FROM muzik_calma_listeleri WHERE id = ? AND kullanici_id = ?", (liste_id, kullanici_id))
    if c.rowcount == 0:
        db.commit()
        return False
    c.execute("DELETE FROM muzik_calma_listesi_parcalari WHERE liste_id = ?", (liste_id,))
    db.commit()
    return True


# ══════════════════════════════════════════════
#  BOT GENELİ DURUM (anahtar/değer)
# ══════════════════════════════════════════════

def bot_durum_al(anahtar, varsayilan=None):
    c = db.cursor()
    c.execute("SELECT deger FROM muzik_bot_durum WHERE anahtar = ?", (anahtar,))
    r = c.fetchone()
    return r[0] if r else varsayilan


def bot_durum_yaz(anahtar, deger):
    c = db.cursor()
    c.execute("INSERT INTO muzik_bot_durum (anahtar, deger) VALUES (?, ?) "
              "ON CONFLICT(anahtar) DO UPDATE SET deger = excluded.deger", (anahtar, str(deger)))
    db.commit()
