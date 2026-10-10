"""
Özel ses odası veritabanı katmanı (şema + migrasyonlar + sorgular + cache).

database.py'deki ORTAK SQLite bağlantısını (`db`) kullanır, kendi tablolarını kendisi kurar:
    ozel_oda_ayarlar → sunucu başına kurulum (kategori / hub / panel) + varsayılanlar
    ozel_odalar      → açık odalar (kanal, sahip, oluşturma zamanı, kilitli/gizli bayrakları, panel mesajı)

Kurallar (AGENTS.md):
 - Tüm sorgular parametreli (?). Dinamik kolon adları beyaz listeden (OZEL_ODA_AYAR_KOLONLARI / ODA_KOLONLARI).
 - Migrasyonlar eklemeli ve idempotent: ozel_oda_veritabanini_kur() istediğin kadar çağrılabilir.
 - Cache her yazma ile birlikte güncellenir; ses olayı dinleyicisi (sıcak yol) sadece cache okur.
"""
import logging
import sqlite3
import time

from database import db

logger = logging.getLogger('MezarBot.OzelOdaDB')

# ── Sunucu ayarları: kolon → (SQL tipi/varsayılanı, Python varsayılanı) ──
_AYAR_SEMASI = {
    'aktif':            ("INTEGER DEFAULT 0", 0),  # varsayılan KAPALI; sadece yönetici /ozelodaaktif ile açar
    'kategori_id':      ("INTEGER", None),
    'hub_id':           ("INTEGER", None),        # "➕ Oda Oluştur" (katıl → oda oluştur) ses kanalı
    'panel_kanal_id':   ("INTEGER", None),        # "🎛️oda-paneli" metin kanalı
    'panel_mesaj_id':   ("INTEGER", None),
    'varsayilan_limit': ("INTEGER DEFAULT 0", 0),  # 0 = sınırsız
    'ad_sablonu':       ("TEXT DEFAULT '🔊 {kullanici} odası'", "🔊 {kullanici} odası"),
    'bos_silme_suresi': ("INTEGER DEFAULT 30", 30),  # saniye
    'kisi_basi_oda':    ("INTEGER DEFAULT 1", 1),
    'gizlemeye_izin':   ("INTEGER DEFAULT 1", 1),  # üyeler odalarını gizleyebilir mi
}
OZEL_ODA_AYAR_KOLONLARI = frozenset(_AYAR_SEMASI)
VARSAYILAN_AYARLAR = {k: v[1] for k, v in _AYAR_SEMASI.items()}
ODA_KOLONLARI = frozenset({'sahip_id', 'kilitli', 'gizli', 'panel_mesaj_id'})

_ayar_cache = {}   # {sunucu_id: dict} — sadece kurulum yapılmış sunucular
_oda_cache = {}    # {kanal_id: dict(kanal_id, sunucu_id, sahip_id, olusturma, kilitli, gizli, panel_mesaj_id)}


def ozel_oda_veritabanini_kur():
    """Tabloları oluşturur, eksik kolonları ekler ve cache'i yükler. İdempotent."""
    c = db.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS ozel_oda_ayarlar (sunucu_id INTEGER PRIMARY KEY)")
    for kolon, (tip, _) in _AYAR_SEMASI.items():
        try:
            c.execute(f"ALTER TABLE ozel_oda_ayarlar ADD COLUMN {kolon} {tip}")
        except sqlite3.OperationalError:
            pass  # kolon zaten var
    c.execute("""CREATE TABLE IF NOT EXISTS ozel_odalar (
        kanal_id INTEGER PRIMARY KEY,
        sunucu_id INTEGER NOT NULL,
        sahip_id INTEGER NOT NULL,
        olusturma REAL NOT NULL,
        kilitli INTEGER DEFAULT 0,
        gizli INTEGER DEFAULT 0,
        panel_mesaj_id INTEGER
    )""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_ozel_odalar_sahip ON ozel_odalar (sunucu_id, sahip_id)")
    db.commit()
    ozel_oda_cache_yukle()


def ozel_oda_cache_yukle():
    global _ayar_cache, _oda_cache
    c = db.cursor()
    c.execute("SELECT * FROM ozel_oda_ayarlar")
    _ayar_cache = {r['sunucu_id']: dict(r) for r in c.fetchall()}
    c.execute("SELECT * FROM ozel_odalar")
    _oda_cache = {r['kanal_id']: dict(r) for r in c.fetchall()}
    logger.info(f"🔊 Özel oda: {len(_ayar_cache)} sunucu kurulu, {len(_oda_cache)} kayıtlı oda")


# ══════════════════════════════════════════════
#  SUNUCU AYARLARI
# ══════════════════════════════════════════════

def aktif_mi(sunucu_id):
    """Özel oda sistemi bu sunucuda açık mı? (cache). Kayıt yoksa KAPALI."""
    kayit = _ayar_cache.get(sunucu_id)
    return bool(kayit and kayit.get('aktif'))


def ayar_al(sunucu_id):
    """Kayıt varsa varsayılanlarla birleşik KOPYA döner, yoksa None (cache — DB sorgusu yok).
    Not: kayıt olması sistemin AÇIK olduğu anlamına gelmez → aktif_mi()."""
    kayit = _ayar_cache.get(sunucu_id)
    if kayit is None:
        return None
    ayar = dict(VARSAYILAN_AYARLAR)
    ayar.update({k: v for k, v in kayit.items() if k in OZEL_ODA_AYAR_KOLONLARI and v is not None})
    ayar['sunucu_id'] = sunucu_id
    return ayar


def ayar_guncelle(sunucu_id, **kwargs):
    """Ayar(lar)ı yazar (satır yoksa oluşturur) ve cache'i DB satırıyla tazeler. Beyaz liste dışı kolon → ValueError."""
    gecersiz = [k for k in kwargs if k not in OZEL_ODA_AYAR_KOLONLARI]
    if gecersiz:
        raise ValueError(f"ozel_oda_ayarlar: geçersiz kolon adı: {', '.join(map(repr, gecersiz))}")
    c = db.cursor()
    c.execute("INSERT OR IGNORE INTO ozel_oda_ayarlar (sunucu_id) VALUES (?)", (sunucu_id,))
    if kwargs:
        setler = ", ".join(f"{k} = ?" for k in kwargs)
        c.execute(f"UPDATE ozel_oda_ayarlar SET {setler} WHERE sunucu_id = ?", (*kwargs.values(), sunucu_id))
    db.commit()
    c.execute("SELECT * FROM ozel_oda_ayarlar WHERE sunucu_id = ?", (sunucu_id,))
    _ayar_cache[sunucu_id] = dict(c.fetchone())


def kayitli_sunucular():
    """Ayar satırı olan sunucular (açık ya da kapatılmış ama temizliği süren)."""
    return list(_ayar_cache)


# ══════════════════════════════════════════════
#  ODALAR
# ══════════════════════════════════════════════

def oda_al(kanal_id):
    """Oda kaydının KOPYASI ya da None (cache)."""
    kayit = _oda_cache.get(kanal_id)
    return dict(kayit) if kayit else None


def oda_mi(kanal_id):
    return kanal_id in _oda_cache


def oda_ekle(sunucu_id, kanal_id, sahip_id, kilitli=0, gizli=0):
    kayit = {'kanal_id': kanal_id, 'sunucu_id': sunucu_id, 'sahip_id': sahip_id, 'olusturma': time.time(),
             'kilitli': int(kilitli), 'gizli': int(gizli), 'panel_mesaj_id': None}
    c = db.cursor()
    c.execute("INSERT OR REPLACE INTO ozel_odalar (kanal_id, sunucu_id, sahip_id, olusturma, kilitli, gizli, panel_mesaj_id) "
              "VALUES (:kanal_id, :sunucu_id, :sahip_id, :olusturma, :kilitli, :gizli, :panel_mesaj_id)", kayit)
    db.commit()
    _oda_cache[kanal_id] = kayit
    return dict(kayit)


def oda_guncelle(kanal_id, **kwargs):
    gecersiz = [k for k in kwargs if k not in ODA_KOLONLARI]
    if gecersiz:
        raise ValueError(f"ozel_odalar: geçersiz kolon adı: {', '.join(map(repr, gecersiz))}")
    if not kwargs or kanal_id not in _oda_cache:
        return
    setler = ", ".join(f"{k} = ?" for k in kwargs)
    c = db.cursor()
    c.execute(f"UPDATE ozel_odalar SET {setler} WHERE kanal_id = ?", (*kwargs.values(), kanal_id))
    db.commit()
    _oda_cache[kanal_id].update(kwargs)


def oda_sil(kanal_id):
    """Oda kaydını unutur (kanal silindi / silinecek). Kayıt varsa True."""
    if kanal_id not in _oda_cache:
        return False
    c = db.cursor()
    c.execute("DELETE FROM ozel_odalar WHERE kanal_id = ?", (kanal_id,))
    db.commit()
    _oda_cache.pop(kanal_id, None)
    return True


def sunucu_odalari(sunucu_id):
    """[dict] — sunucunun kayıtlı odaları, oluşturma sırasına göre (cache)."""
    return sorted((dict(o) for o in _oda_cache.values() if o['sunucu_id'] == sunucu_id), key=lambda o: o['olusturma'])


def sahibin_odalari(sunucu_id, sahip_id):
    return [o for o in sunucu_odalari(sunucu_id) if o['sahip_id'] == sahip_id]


def tum_odalar():
    return [dict(o) for o in _oda_cache.values()]


def sunucu_odalarini_unut(sunucu_id):
    """Bot sunucudan çıkarıldığında: o sunucunun oda kayıtlarını siler (ayar kalır)."""
    c = db.cursor()
    c.execute("DELETE FROM ozel_odalar WHERE sunucu_id = ?", (sunucu_id,))
    db.commit()
    for kid in [k for k, o in _oda_cache.items() if o['sunucu_id'] == sunucu_id]:
        _oda_cache.pop(kid, None)
