import datetime
import os
import sqlite3
import logging
# DB: bot dizinine göre mutlak yol; SAHIP_ID ve ESKI_EKONOMI_SUNUCU_ID: config.json
from yapilandirma import DB_DOSYA, SAHIP_ID, ESKI_EKONOMI_SUNUCU_ID

logger = logging.getLogger('MezarBot.DB')

# Ana bağlantı (check_same_thread=False — asyncio tek thread'de çalışır)
db = sqlite3.connect(DB_DOSYA, check_same_thread=False)
db.row_factory = sqlite3.Row
# WAL modu: okuma/yazma çakışmalarını azaltır, performansı artırır
db.execute("PRAGMA journal_mode=WAL")
db.execute("PRAGMA synchronous=NORMAL")
db.execute("PRAGMA cache_size=-64000")       # 64 MB sayfa önbelleği (disk okumalarını RAM'e taşır)
db.execute("PRAGMA mmap_size=268435456")     # 256 MB memory-mapped I/O (sıfır kopyalama bellek eşleme)
db.execute("PRAGMA temp_store=MEMORY")       # Geçici tablolar ve sıralamalar disk yerine RAM'de çalışır
db.execute("PRAGMA busy_timeout=5000")       # Eşzamanlı yazmada kilit hatası almadan 5 sn tolerans

# ══════════════════════════════════════════════
#  CACHE SİSTEMİ
# ══════════════════════════════════════════════
# Her mesajda DB sorgusu yapmak yerine bellekten oku
_sunucu_cache = {}        # {sunucu_id: dict(ayarlar)}
_vip_kisiler = set()      # VIP kullanıcı ID'leri
_vip_roller = set()       # VIP rol ID'leri
_kelime_oyunu_cache = {}  # {sunucu_id: dict(kanal_id, son_kelime, son_kullanici_id, kelime_sayisi)}
_kullanilan_kelimeler = {}  # {sunucu_id: set(kelimeler)} — kelime oyununda tekrar engeli
_afk_cache = {}           # {(sunucu_id, kullanici_id): sebep} — AFK sunucu bazlı
_sozluk_cache = set()     # TDK'dan doğrulanmış kelimeler (yerel sözlük)


def cache_yukle():
    """Tüm cache'leri DB'den yükler. Bot başlangıcında ve ayar değişikliğinde çağrılır."""
    global _sunucu_cache, _vip_kisiler, _vip_roller, _kelime_oyunu_cache, _afk_cache, _sozluk_cache, _kullanilan_kelimeler
    c = db.cursor()

    # Sunucu ayarları
    c.execute("SELECT * FROM sunucu_ayarlar")
    _sunucu_cache = {}
    for row in c.fetchall():
        _sunucu_cache[row['sunucu_id']] = dict(row)

    # VIP kişiler
    c.execute("SELECT kullanici_id FROM vip_kisiler")
    _vip_kisiler = {row[0] for row in c.fetchall()}

    # VIP roller
    c.execute("SELECT rol_id FROM vip_roller")
    _vip_roller = {row[0] for row in c.fetchall()}

    # Kelime oyunu
    _kelime_oyunu_cache = {}
    try:
        c.execute("SELECT * FROM kelime_oyunu")
        for row in c.fetchall():
            _kelime_oyunu_cache[row['sunucu_id']] = dict(row)
    except Exception as e:
        logger.debug(f"Kelime oyunu yuklenemedi (tablo henuz yok olabilir): {e}")

    # AFK durumları (sunucu bazlı)
    _afk_cache = {}
    try:
        c.execute("SELECT sunucu_id, kullanici_id, sebep FROM afk_durumlari")
        _afk_cache = {(row[0], row[1]): row[2] for row in c.fetchall()}
    except Exception as e:
        logger.debug(f"AFK durumlari yuklenemedi (tablo henuz yok olabilir): {e}")

    _kullanilan_kelimeler = {}
    _sozluk_cache = set()
    logger.info(f"✅ Cache yüklendi: {len(_sunucu_cache)} sunucu, {len(_vip_kisiler)} VIP kişi, {len(_vip_roller)} VIP rol, {len(_afk_cache)} AFK")


def sunucu_ayar_al(sunucu_id):
    """Cache'den sunucu ayarlarını döner. DB sorgusu yapmaz."""
    return _sunucu_cache.get(sunucu_id)


# ── Dinamik SQL'de kullanılabilecek kolon adları (beyaz liste) ──
# Kolon adları f-string ile SQL'e girdiği için SADECE bu kümelerdeki adlara izin verilir.
# Yeni bir sunucu ayarı eklerken: veritabanini_kur() migrasyonuna + buraya ekle.
SUNUCU_AYAR_KOLONLARI = frozenset({
    'hosgeldin_kanal_id', 'hosgeldin_mesaj', 'otorol_id', 'otomod_aktif',
    'itiraf_kanal_id', 'log_kanal_id', 'uyari_kanal_id', 'oyun_kanal_id',
    'kelimeoyunu_kanal_id', 'oygec_aktif',
    'yama_notlari_kanal_id', 'xp_aktif',
    'gorusuruz_kanal_id', 'gorusuruz_mesaj',
    'dil',
})
KELIME_OYUNU_KOLONLARI = frozenset({'kanal_id', 'son_kelime', 'son_kullanici_id', 'kelime_sayisi'})


def sunucu_dil_al(sunucu_id):
    """Cache'den sunucunun dilini döner ('tr' veya 'en')."""
    ayar = sunucu_ayar_al(sunucu_id) or {}
    return ayar.get('dil') or 'tr'


def sunucu_dil_ayarla(sunucu_id, dil):
    """Sunucunun dil ayarını günceller ('tr' veya 'en')."""
    dil_kod = 'en' if str(dil).lower().startswith('en') else 'tr'
    sunucu_ayar_guncelle(sunucu_id, dil=dil_kod)
    return dil_kod


def _kolonlari_dogrula(kwargs, izinli, tablo):
    """kwargs anahtarlarını beyaz listeye göre doğrular; bilinmeyen kolon adında ValueError fırlatır."""
    gecersiz = [k for k in kwargs if k not in izinli]
    if gecersiz:
        raise ValueError(f"{tablo}: geçersiz kolon adı: {', '.join(map(repr, gecersiz))}")


def sunucu_ayar_guncelle(sunucu_id, **kwargs):
    """Sunucu ayarını DB'ye yazar ve cache'i günceller. Kolon adları beyaz listeden doğrulanır."""
    if not kwargs:
        return
    _kolonlari_dogrula(kwargs, SUNUCU_AYAR_KOLONLARI, "sunucu_ayarlar")
    c = db.cursor()
    c.execute("SELECT sunucu_id FROM sunucu_ayarlar WHERE sunucu_id = ?", (sunucu_id,))
    if c.fetchone():
        setler = ", ".join(f"{k} = ?" for k in kwargs)
        c.execute(f"UPDATE sunucu_ayarlar SET {setler} WHERE sunucu_id = ?", (*kwargs.values(), sunucu_id))
    else:
        kolonlar = "sunucu_id, " + ", ".join(kwargs.keys())
        placeholders = "?, " + ", ".join("?" for _ in kwargs)
        c.execute(f"INSERT INTO sunucu_ayarlar ({kolonlar}) VALUES ({placeholders})", (sunucu_id, *kwargs.values()))
    db.commit()
    # Cache güncelle
    if sunucu_id not in _sunucu_cache:
        _sunucu_cache[sunucu_id] = {'sunucu_id': sunucu_id}
    _sunucu_cache[sunucu_id].update(kwargs)


def kelime_oyunu_al(sunucu_id):
    """Cache'den kelime oyunu verisini döner."""
    return _kelime_oyunu_cache.get(sunucu_id)


def kelime_oyunu_guncelle(sunucu_id, **kwargs):
    """Kelime oyunu verisini DB'ye yazar ve cache'i günceller. Kolon adları beyaz listeden doğrulanır."""
    if not kwargs:
        return
    _kolonlari_dogrula(kwargs, KELIME_OYUNU_KOLONLARI, "kelime_oyunu")
    c = db.cursor()
    if 'kanal_id' in kwargs and sunucu_id not in _kelime_oyunu_cache:
        # Yeni kayıt
        c.execute("REPLACE INTO kelime_oyunu (sunucu_id, kanal_id, son_kelime, son_kullanici_id, kelime_sayisi) VALUES (?, ?, ?, ?, ?)",
                  (sunucu_id, kwargs.get('kanal_id'), kwargs.get('son_kelime', ''), kwargs.get('son_kullanici_id', 0), kwargs.get('kelime_sayisi', 0)))
        db.commit()
        _kelime_oyunu_cache[sunucu_id] = {
            'sunucu_id': sunucu_id,
            'kanal_id': kwargs.get('kanal_id'),
            'son_kelime': kwargs.get('son_kelime', ''),
            'son_kullanici_id': kwargs.get('son_kullanici_id', 0),
            'kelime_sayisi': kwargs.get('kelime_sayisi', 0),
        }
    else:
        setler = ", ".join(f"{k} = ?" for k in kwargs)
        c.execute(f"UPDATE kelime_oyunu SET {setler} WHERE sunucu_id = ?", (*kwargs.values(), sunucu_id))
        db.commit()
        if sunucu_id in _kelime_oyunu_cache:
            _kelime_oyunu_cache[sunucu_id].update(kwargs)


def kelime_oyunu_sayac_artir(sunucu_id):
    """Kelime sayacını atomik olarak artırır ve cache'i günceller. Yeni değeri döner."""
    c = db.cursor()
    c.execute("UPDATE kelime_oyunu SET kelime_sayisi = COALESCE(kelime_sayisi, 0) + 1 WHERE sunucu_id = ?", (sunucu_id,))
    db.commit()
    if sunucu_id in _kelime_oyunu_cache:
        yeni_sayi = _kelime_oyunu_cache[sunucu_id].get('kelime_sayisi', 0) + 1
        _kelime_oyunu_cache[sunucu_id]['kelime_sayisi'] = yeni_sayi
        return yeni_sayi
    # Cache'de yoksa DB'den oku
    c.execute("SELECT kelime_sayisi FROM kelime_oyunu WHERE sunucu_id = ?", (sunucu_id,))
    row = c.fetchone()
    return row[0] if row else 0


# ══════════════════════════════════════════════
#  KULLANILAN KELİMELER (TEKRAR ENGELİ)
# ══════════════════════════════════════════════

def kullanilan_kelime_kontrol(sunucu_id, kelime):
    """Kelime daha önce kullanılmış mı? Cache'den kontrol eder."""
    return kelime.lower() in _kullanilan_kelimeler.get(sunucu_id, set())


def kullanilan_kelime_ekle(sunucu_id, kelime):
    """Kullanılan kelimeyi DB'ye ve cache'e ekler."""
    kelime = kelime.lower()
    try:
        c = db.cursor()
        c.execute("INSERT OR IGNORE INTO kullanilan_kelimeler (sunucu_id, kelime) VALUES (?, ?)", (sunucu_id, kelime))
        db.commit()
        _kullanilan_kelimeler.setdefault(sunucu_id, set()).add(kelime)
    except Exception as e:
        logger.warning(f"Kullanilan kelime eklenemedi: {e}")


def kullanilan_kelimeler_sifirla(sunucu_id):
    """Sunucunun kullanılan kelimeler listesini temizler (oyun sıfırlanınca)."""
    try:
        c = db.cursor()
        c.execute("DELETE FROM kullanilan_kelimeler WHERE sunucu_id = ?", (sunucu_id,))
        db.commit()
        _kullanilan_kelimeler.pop(sunucu_id, None)
    except Exception as e:
        logger.warning(f"Kullanilan kelimeler sifirlanamadi: {e}")


def kullanilan_kelime_sayisi(sunucu_id):
    """Sunucuda kaç kelime kullanıldığını döner."""
    return len(_kullanilan_kelimeler.get(sunucu_id, set()))


# ══════════════════════════════════════════════
#  AFK CACHE FONKSİYONLARI
# ══════════════════════════════════════════════

def afk_al(sunucu_id, kullanici_id):
    """Cache'den kullanıcının BU sunucudaki AFK sebebini döner. DB sorgusu yapmaz."""
    return _afk_cache.get((sunucu_id, kullanici_id))


def afk_ayarla(sunucu_id, kullanici_id, sebep):
    """AFK durumunu (sunucu bazlı) DB'ye yazar ve cache'i günceller."""
    c = db.cursor()
    c.execute("REPLACE INTO afk_durumlari (sunucu_id, kullanici_id, sebep) VALUES (?, ?, ?)",
              (sunucu_id, kullanici_id, sebep))
    db.commit()
    _afk_cache[(sunucu_id, kullanici_id)] = sebep


def afk_kaldir(sunucu_id, kullanici_id):
    """AFK durumunu (sunucu bazlı) DB'den siler ve cache'i günceller."""
    c = db.cursor()
    c.execute("DELETE FROM afk_durumlari WHERE sunucu_id = ? AND kullanici_id = ?", (sunucu_id, kullanici_id))
    db.commit()
    _afk_cache.pop((sunucu_id, kullanici_id), None)


# ══════════════════════════════════════════════
#  YEREL SÖZLÜK FONKSİYONLARI
# ══════════════════════════════════════════════

def sozluk_kontrol(kelime):
    """Kelimenin yerel sözlükte olup olmadığını kontrol eder. DB sorgusu yapmaz."""
    return kelime.lower() in _sozluk_cache


def sozluk_ekle(kelime):
    """TDK'dan dogrulanmis kelimeyi yerel sozluge ekler (DB + cache)."""
    kelime = kelime.lower()
    if kelime in _sozluk_cache:
        return
    try:
        c = db.cursor()
        c.execute("INSERT OR IGNORE INTO turkce_sozluk (kelime) VALUES (?)", (kelime,))
        db.commit()
        _sozluk_cache.add(kelime)
    except Exception as e:
        logger.warning(f"Sozluk ekleme hatasi: {e}")


# ══════════════════════════════════════════════
#  EKONOMİ (SUNUCU BAZLI)
# ══════════════════════════════════════════════
# Bakiye, XP, seviye, günlük ödül, işlem geçmişi, başarımlar ve envanter (sunucu_id, kullanici_id)
# anahtarlıdır: aynı kullanıcının her sunucuda ayrı bir ekonomisi vardır.

def _ekonomi_anahtari_dogrula(sunucu_id, kullanici_id):
    """Eski (global) imzayla yapılan çağrıları yakalar: ör. islem_kaydet(uid, 'tip', ...) sessizce
    yanlış satır yazmasın. İkisi de Discord ID'si (int) olmalı."""
    if not isinstance(sunucu_id, int) or not isinstance(kullanici_id, int):
        raise TypeError(f"Ekonomi anahtarı (sunucu_id, kullanici_id) int olmalı: {sunucu_id!r}, {kullanici_id!r}")


def ekonomi_kaydi_olustur(sunucu_id, kullanici_id, xp=0, seviye=1, bakiye=0):
    """Kullanıcının BU sunucudaki ekonomi satırını yoksa oluşturur (varsa dokunmaz).
    Yeni satır oluştuysa True döner. Commit çağıran tarafa aittir."""
    _ekonomi_anahtari_dogrula(sunucu_id, kullanici_id)
    c = db.cursor()
    c.execute("INSERT OR IGNORE INTO ekonomi (sunucu_id, kullanici_id, xp, seviye, bakiye, son_gunluk) VALUES (?, ?, ?, ?, ?, '')",
              (sunucu_id, kullanici_id, xp, seviye, bakiye))
    return c.rowcount > 0


def bakiye_al(sunucu_id, kullanici_id):
    """Kullanıcının BU sunucudaki bakiyesi; profili yoksa None."""
    _ekonomi_anahtari_dogrula(sunucu_id, kullanici_id)
    c = db.cursor()
    c.execute("SELECT bakiye FROM ekonomi WHERE sunucu_id = ? AND kullanici_id = ?", (sunucu_id, kullanici_id))
    row = c.fetchone()
    return row[0] if row else None


def islem_kaydet(sunucu_id, kullanici_id, tip, miktar, aciklama=None):
    """İşlem geçmişine (bu sunucu için) yeni kayıt ekler."""
    _ekonomi_anahtari_dogrula(sunucu_id, kullanici_id)
    try:
        c = db.cursor()
        c.execute("INSERT INTO islem_gecmisi (sunucu_id, kullanici_id, tip, miktar, aciklama) VALUES (?, ?, ?, ?, ?)",
                  (sunucu_id, kullanici_id, tip, miktar, aciklama))
        db.commit()
    except Exception as e:
        logger.warning(f"İşlem kaydedilemedi: {e}")


def islem_gecmisi_al(sunucu_id, kullanici_id, limit=10):
    """Kullanıcının BU sunucudaki son N işlemini döner."""
    _ekonomi_anahtari_dogrula(sunucu_id, kullanici_id)
    c = db.cursor()
    c.execute("SELECT tip, miktar, aciklama, tarih FROM islem_gecmisi WHERE sunucu_id = ? AND kullanici_id = ? "
              "ORDER BY tarih DESC, id DESC LIMIT ?",
              (sunucu_id, kullanici_id, limit))
    return c.fetchall()


# ══════════════════════════════════════════════
#  BAŞARIM SİSTEMİ
# ══════════════════════════════════════════════

BASARIM_LISTESI = {
    'zengin': {'isim': 'Zengin', 'emoji': '💰', 'aciklama': '10.000 Coin biriktir'},
    'kumar_krali': {'isim': 'Kumar Kralı', 'emoji': '🎰', 'aciklama': '50 kumar oyunu kazan'},
    'streak_5': {'isim': 'Sadık Üye', 'emoji': '🔥', 'aciklama': '5 gün üst üste günlük ödül al'},
    'streak_30': {'isim': 'Efsane Sadakat', 'emoji': '💎', 'aciklama': '30 gün üst üste günlük ödül al'},
    'seviye_10': {'isim': 'Deneyimli', 'emoji': '⭐', 'aciklama': 'Seviye 10\'a ulaş'},
    'seviye_25': {'isim': 'Veteranl', 'emoji': '🏆', 'aciklama': 'Seviye 25\'e ulaş'},
    'kelime_ustasi': {'isim': 'Kelime Ustası', 'emoji': '📝', 'aciklama': 'Kelime oyununda 50 kelime yaz'},
    'sosyal': {'isim': 'Sosyal Kelebek', 'emoji': '🦋', 'aciklama': '10 farklı kişiye transfer yap'},
    'ilk_kumar': {'isim': 'Şansını Dene', 'emoji': '🎲', 'aciklama': 'İlk kumar oyununu oyna'},
    'buyuk_kazanc': {'isim': 'Büyük İkramiye', 'emoji': '🎉', 'aciklama': 'Tek seferde 5.000+ Coin kazan'},
}


def basarim_kontrol(sunucu_id, kullanici_id, basarim_id):
    """Başarım BU sunucuda zaten kazanılmış mı kontrol eder."""
    _ekonomi_anahtari_dogrula(sunucu_id, kullanici_id)
    c = db.cursor()
    c.execute("SELECT 1 FROM basarimlar WHERE sunucu_id = ? AND kullanici_id = ? AND basarim_id = ?",
              (sunucu_id, kullanici_id, basarim_id))
    return c.fetchone() is not None


def basarim_ver(sunucu_id, kullanici_id, basarim_id):
    """Başarımı BU sunucu için verir. Zaten varsa False döner, yeni verilirse True döner."""
    if basarim_kontrol(sunucu_id, kullanici_id, basarim_id):
        return False
    try:
        c = db.cursor()
        c.execute("INSERT OR IGNORE INTO basarimlar (sunucu_id, kullanici_id, basarim_id) VALUES (?, ?, ?)",
                  (sunucu_id, kullanici_id, basarim_id))
        db.commit()
        return c.rowcount > 0
    except Exception as e:
        logger.warning(f"Başarım verilemedi: {e}")
        return False


def basarimlari_al(sunucu_id, kullanici_id):
    """Kullanıcının BU sunucudaki tüm başarımlarını döner."""
    _ekonomi_anahtari_dogrula(sunucu_id, kullanici_id)
    c = db.cursor()
    c.execute("SELECT basarim_id, kazanilma_tarihi FROM basarimlar WHERE sunucu_id = ? AND kullanici_id = ? "
              "ORDER BY kazanilma_tarihi",
              (sunucu_id, kullanici_id))
    return c.fetchall()


def basarim_sayisi(sunucu_id, kullanici_id):
    """Kullanıcının BU sunucudaki başarım sayısını döner."""
    _ekonomi_anahtari_dogrula(sunucu_id, kullanici_id)
    c = db.cursor()
    c.execute("SELECT COUNT(*) FROM basarimlar WHERE sunucu_id = ? AND kullanici_id = ?", (sunucu_id, kullanici_id))
    return c.fetchone()[0]


# ══════════════════════════════════════════════
#  KELIME OYUNU PUANLARI
# ══════════════════════════════════════════════

def kelime_puan_artir(sunucu_id, kullanici_id):
    """Kelime oyunu puanını +1 artırır."""
    c = db.cursor()
    c.execute("""INSERT INTO kelime_puanlari (sunucu_id, kullanici_id, puan) VALUES (?, ?, 1)
                 ON CONFLICT(sunucu_id, kullanici_id) DO UPDATE SET puan = puan + 1""",
              (sunucu_id, kullanici_id))
    db.commit()
    # Yeni puanı döner
    c.execute("SELECT puan FROM kelime_puanlari WHERE sunucu_id = ? AND kullanici_id = ?",
              (sunucu_id, kullanici_id))
    row = c.fetchone()
    return row[0] if row else 0


def kelime_liderlik(sunucu_id, limit=10):
    """Kelime oyunu liderlik tablosunu döner."""
    c = db.cursor()
    c.execute("SELECT kullanici_id, puan FROM kelime_puanlari WHERE sunucu_id = ? ORDER BY puan DESC LIMIT ?",
              (sunucu_id, limit))
    return c.fetchall()


# ══════════════════════════════════════════════
#  VIP KONTROL FONKSİYONLARI
# ══════════════════════════════════════════════

def vip_kontrol(member):
    """VIP kontrolü — member objesi ile çalışır (ctx gerektirmez).
    Tüm cog'larda tutarlı VIP tespiti sağlar."""
    if SAHIP_ID and member.id == SAHIP_ID:
        return True  # Bot sahibi (config.json → sahip_id)
    # DM'de discord.User gelir: sunucu yetkisi / rolü yoktur (AttributeError yerine False)
    izinler = getattr(member, 'guild_permissions', None)
    if izinler is not None and izinler.administrator:
        return True
    if member.id in _vip_kisiler:
        return True
    return any(rol.id in _vip_roller for rol in getattr(member, 'roles', ()))


def bouncer_kontrol(ctx):
    """VIP Kontrol fonksiyonu (commands.check uyumlu) — cache'den okur, DB sorgusu yapmaz."""
    return vip_kontrol(ctx.author)


# ══════════════════════════════════════════════
#  SUNUCU YÖNETİCİSİ KONTROLÜ (çok sunuculu)
# ══════════════════════════════════════════════

def yonetici_mi(member):
    """Bu sunucunun yöneticisi mi? Bot sahibi veya o sunucuda Yönetici (Administrator) ya da
    Sunucuyu Yönet (Manage Guild) yetkisi olan üye. Rol ID'si sabitlenmez — her sunucuda çalışır.
    Not: VIP ≠ yönetici; VIP'ler sunucu ayarlarını değiştiremez."""
    if SAHIP_ID and member.id == SAHIP_ID:
        return True
    izinler = getattr(member, 'guild_permissions', None)
    return bool(izinler is not None and (izinler.administrator or izinler.manage_guild))


def yonetici_kontrol(ctx):
    """commands.check uyumlu: sadece sunucu içinde ve yonetici_mi(ctx.author) ise geçer."""
    return ctx.guild is not None and yonetici_mi(ctx.author)


# ══════════════════════════════════════════════
#  EKONOMİ ŞEMASI + GLOBAL → SUNUCU BAZLI MİGRASYON
# ══════════════════════════════════════════════
# {tablo: (sunucu_id dışındaki kolonlar — sabit beyaz liste, tablo gövdesi)}
# Tablo/kolon adları SADECE bu sabitlerden SQL'e girer (kullanıcı girdisi değil).
EKONOMI_TABLOLARI = {
    'ekonomi': (
        ('kullanici_id', 'xp', 'seviye', 'bakiye', 'son_gunluk', 'streak', 'son_gunluk_tarih',
         'gunluk_kayip', 'gunluk_kayip_tarih', 'kumar_kazanma', 'transfer_sayisi'),
        """sunucu_id INTEGER NOT NULL,
        kullanici_id INTEGER NOT NULL,
        xp INTEGER DEFAULT 0,
        seviye INTEGER DEFAULT 1,
        bakiye INTEGER DEFAULT 0,
        son_gunluk TEXT,
        streak INTEGER DEFAULT 0,
        son_gunluk_tarih TEXT,
        gunluk_kayip INTEGER DEFAULT 0,
        gunluk_kayip_tarih TEXT,
        kumar_kazanma INTEGER DEFAULT 0,
        transfer_sayisi INTEGER DEFAULT 0,
        PRIMARY KEY (sunucu_id, kullanici_id)"""),
    'islem_gecmisi': (
        ('id', 'kullanici_id', 'tip', 'miktar', 'aciklama', 'tarih'),
        """id INTEGER PRIMARY KEY AUTOINCREMENT,
        sunucu_id INTEGER NOT NULL,
        kullanici_id INTEGER NOT NULL,
        tip TEXT NOT NULL,
        miktar INTEGER NOT NULL,
        aciklama TEXT,
        tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP"""),
    'basarimlar': (
        ('kullanici_id', 'basarim_id', 'kazanilma_tarihi'),
        """sunucu_id INTEGER NOT NULL,
        kullanici_id INTEGER NOT NULL,
        basarim_id TEXT NOT NULL,
        kazanilma_tarihi TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (sunucu_id, kullanici_id, basarim_id)"""),
    'envanter': (
        ('id', 'kullanici_id', 'urun_id', 'satin_alma_tarihi'),
        """id INTEGER PRIMARY KEY AUTOINCREMENT,
        sunucu_id INTEGER NOT NULL,
        kullanici_id INTEGER NOT NULL,
        urun_id INTEGER NOT NULL,
        satin_alma_tarihi TEXT,
        UNIQUE(sunucu_id, kullanici_id, urun_id)"""),
}
# Migrasyonda eski (global) tablo SİLİNMEZ, bu önekle yeniden adlandırılıp olduğu gibi saklanır
ESKI_GLOBAL_TABLO_ONEKI = "eski_global_"


class EkonomiMigrasyonHatasi(RuntimeError):
    """Global → sunucu bazlı ekonomi migrasyonu yapılamadı. İşlem geri alınmıştır; bot başlamamalı."""


def _tablo_var_mi(c, tablo):
    c.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (tablo,))
    return c.fetchone() is not None


def _tablo_kolonlari(c, tablo):
    return [r[1] for r in c.execute(f'PRAGMA table_info("{tablo}")')]


def _veritabani_yedekle(etiket, kontrol_tablolari=()):
    """Tutarlı bir yedek alır: <DB_DOSYA>.bak-<etiket>-<zaman> (DB ile aynı dizin, izin 0600).
    sqlite backup API'si kullanılır: WAL'daki commit edilmiş veriler de yedeğe girer (düz dosya
    kopyası bunu garanti etmez). Yedek doğrulanır (quick_check + tablo satır sayıları); hata → istisna."""
    zaman = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    yol = f"{DB_DOSYA}.bak-{etiket}-{zaman}"
    # O_EXCL: var olan bir dosyanın üzerine asla yazma; 0600: DB ile aynı gizlilik
    os.close(os.open(yol, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600))
    hedef = sqlite3.connect(yol)
    try:
        db.backup(hedef)
        sonuc = hedef.execute("PRAGMA quick_check").fetchone()[0]
        if sonuc != "ok":
            raise EkonomiMigrasyonHatasi(f"Yedek doğrulanamadı ({yol}): quick_check={sonuc}")
        for tablo in kontrol_tablolari:
            kaynak = db.execute(f'SELECT COUNT(*) FROM "{tablo}"').fetchone()[0]
            yedekte = hedef.execute(f'SELECT COUNT(*) FROM "{tablo}"').fetchone()[0]
            if kaynak != yedekte:
                raise EkonomiMigrasyonHatasi(f"Yedek eksik ({yol}): {tablo} {kaynak} != {yedekte}")
    finally:
        hedef.close()
    return yol


def _ekonomi_sunucu_bazli_migrasyon():
    """Eski GLOBAL ekonomi tablolarını (kullanici_id anahtarlı) sunucu bazlı şemaya taşır.

    - Sadece `sunucu_id` kolonu OLMAYAN tablolar taşınır → her açılışta güvenle çalışır (idempotent).
    - Eski satırların hepsi config.json → eski_ekonomi_sunucu_id sunucusuna atanır.
    - Önce DB yedeklenir (<db>.bak-ekonomi-<zaman>). Taşıma TEK transaction'dadır:
      eski tablo → eski_global_<tablo> olarak yeniden adlandırılır (SİLİNMEZ), yeni şemalı tablo
      oluşturulur, INSERT ... SELECT ile kopyalanır, satır satır doğrulanır. Herhangi bir hata →
      ROLLBACK (DB hiç değişmemiş olur) + EkonomiMigrasyonHatasi.
    Taşıma yapıldıysa True döner."""
    c = db.cursor()
    eski_tablolar = [t for t in EKONOMI_TABLOLARI
                     if _tablo_var_mi(c, t) and 'sunucu_id' not in _tablo_kolonlari(c, t)]
    if not eski_tablolar:
        return False

    satir_sayilari = {t: c.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in eski_tablolar}
    hedef_sunucu = ESKI_EKONOMI_SUNUCU_ID
    if hedef_sunucu is None and any(satir_sayilari.values()):
        raise EkonomiMigrasyonHatasi(
            "Eski (global) ekonomi verisi var ama config.json → 'eski_ekonomi_sunucu_id' boş. "
            f"Verinin atanacağı sunucu ID'sini yazıp botu yeniden başlat. Satırlar: {satir_sayilari}")

    for t in eski_tablolar:
        izinli = set(EKONOMI_TABLOLARI[t][0])
        fazla = [k for k in _tablo_kolonlari(c, t) if k not in izinli]
        if fazla:
            # Bilinmeyen kolon → kopyalanamaz; veri kaybı riskine girmek yerine dur
            raise EkonomiMigrasyonHatasi(f"{t}: beklenmeyen kolon(lar) {fazla} — migrasyon yapılmadı.")
        if _tablo_var_mi(c, ESKI_GLOBAL_TABLO_ONEKI + t):
            raise EkonomiMigrasyonHatasi(f"{ESKI_GLOBAL_TABLO_ONEKI + t} zaten var — migrasyon yapılmadı.")

    logger.warning(f"💾 Ekonomi sunucu bazlıya taşınıyor: {satir_sayilari} → sunucu {hedef_sunucu}")
    db.commit()  # yedekten önce bekleyen her şey diske
    try:
        yedek = _veritabani_yedekle("ekonomi", eski_tablolar)
    except (OSError, sqlite3.Error) as e:
        raise EkonomiMigrasyonHatasi(f"Migrasyon öncesi yedek alınamadı, hiçbir şey değiştirilmedi: {e}") from e
    logger.warning(f"💾 Yedek alındı: {yedek}")

    c.execute("BEGIN IMMEDIATE")
    try:
        for t in eski_tablolar:
            kolonlar, govde = EKONOMI_TABLOLARI[t]
            eski_ad = ESKI_GLOBAL_TABLO_ONEKI + t
            eski_kolonlar = set(_tablo_kolonlari(c, t))
            ortak = ", ".join(k for k in kolonlar if k in eski_kolonlar)

            c.execute(f'ALTER TABLE "{t}" RENAME TO "{eski_ad}"')
            c.execute(f'CREATE TABLE "{t}" ({govde})')
            c.execute(f'INSERT INTO "{t}" (sunucu_id, {ortak}) SELECT ?, {ortak} FROM "{eski_ad}"', (hedef_sunucu,))

            # AUTOINCREMENT sayacı: kopyalanan id'ler asla yeniden kullanılmasın (eski sayaç korunur)
            if 'id' in kolonlar:
                c.execute("SELECT seq FROM sqlite_sequence WHERE name = ?", (eski_ad,))
                eski_seq = c.fetchone()
                if eski_seq and eski_seq[0]:
                    c.execute("UPDATE sqlite_sequence SET seq = MAX(seq, ?) WHERE name = ?", (eski_seq[0], t))
                    if c.rowcount == 0:
                        c.execute("INSERT INTO sqlite_sequence (name, seq) VALUES (?, ?)", (t, eski_seq[0]))

            # Doğrulama: satır sayısı aynı ve eski tablodaki HER satır yeni tabloda birebir var
            yeni_sayi = c.execute(f'SELECT COUNT(*) FROM "{t}" WHERE sunucu_id IS ?', (hedef_sunucu,)).fetchone()[0]
            toplam_sayi = c.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
            eksik = c.execute(
                f'SELECT COUNT(*) FROM (SELECT {ortak} FROM "{eski_ad}" '
                f'EXCEPT SELECT {ortak} FROM "{t}" WHERE sunucu_id IS ?)', (hedef_sunucu,)).fetchone()[0]
            if not (yeni_sayi == toplam_sayi == satir_sayilari[t]) or eksik:
                raise EkonomiMigrasyonHatasi(
                    f"{t}: doğrulama başarısız (eski={satir_sayilari[t]}, yeni={yeni_sayi}/{toplam_sayi}, eksik={eksik})")
        if 'ekonomi' in eski_tablolar:
            eski_top = c.execute(f'SELECT COUNT(*), SUM(bakiye), SUM(xp) FROM "{ESKI_GLOBAL_TABLO_ONEKI}ekonomi"').fetchone()
            yeni_top = c.execute("SELECT COUNT(*), SUM(bakiye), SUM(xp) FROM ekonomi").fetchone()
            if tuple(eski_top) != tuple(yeni_top):
                raise EkonomiMigrasyonHatasi(f"ekonomi toplamları tutmuyor: {tuple(eski_top)} != {tuple(yeni_top)}")
            logger.warning(f"💾 ekonomi: {yeni_top[0]} kullanıcı, toplam bakiye {yeni_top[1]}, toplam XP {yeni_top[2]} "
                           f"→ sunucu {hedef_sunucu}")
        db.commit()
    except Exception as e:
        db.rollback()
        if isinstance(e, EkonomiMigrasyonHatasi):
            raise
        raise EkonomiMigrasyonHatasi(f"Ekonomi migrasyonu geri alındı (DB değişmedi, yedek: {yedek}): {e}") from e
    logger.warning(f"✅ Ekonomi sunucu bazlı şemaya taşındı ({', '.join(eski_tablolar)}). "
                   f"Eski tablolar '{ESKI_GLOBAL_TABLO_ONEKI}*' adıyla saklandı, yedek: {yedek}")
    return True


def veritabanini_kur():
    c = db.cursor()
    # AFK sunucu bazlıdır. Eski global 'afk_listesi' tablosu (varsa) olduğu gibi bırakılır, kullanılmaz.
    c.execute("""CREATE TABLE IF NOT EXISTS afk_durumlari (
        sunucu_id INTEGER NOT NULL,
        kullanici_id INTEGER NOT NULL,
        sebep TEXT,
        PRIMARY KEY (sunucu_id, kullanici_id)
    )""")
    c.execute("CREATE TABLE IF NOT EXISTS vip_kisiler (kullanici_id INTEGER PRIMARY KEY)")
    c.execute("CREATE TABLE IF NOT EXISTS vip_roller (rol_id INTEGER PRIMARY KEY)")
    c.execute("CREATE TABLE IF NOT EXISTS cizim_haklari (kullanici_id INTEGER PRIMARY KEY, kalan_hak INTEGER, son_kullanim TEXT)")
    # Ekonomi tabloları sunucu bazlıdır (EKONOMI_TABLOLARI). Yeni DB'de doğrudan bu şemayla kurulur;
    # eski (global) şemalı DB'de CREATE ... IF NOT EXISTS etkisizdir ve aşağıdaki migrasyon taşır.
    c.execute(f"CREATE TABLE IF NOT EXISTS ekonomi ({EKONOMI_TABLOLARI['ekonomi'][1]})")
    c.execute("CREATE TABLE IF NOT EXISTS moderasyon_log (id INTEGER PRIMARY KEY AUTOINCREMENT, islem TEXT, hedef_id INTEGER, moderator_id INTEGER, sebep TEXT, tarih TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS uyarilar (id INTEGER PRIMARY KEY AUTOINCREMENT, sunucu_id INTEGER, kullanici_id INTEGER, moderator_id INTEGER, sebep TEXT, tarih TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS bot_ayarlar (ayarlar_id INTEGER PRIMARY KEY, durum_metni TEXT, durum_tipi TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS kelime_oyunu (sunucu_id INTEGER PRIMARY KEY, kanal_id INTEGER, son_kelime TEXT, son_kullanici_id INTEGER)")
    c.execute("""CREATE TABLE IF NOT EXISTS sunucu_ayarlar (
        sunucu_id INTEGER PRIMARY KEY,
        hosgeldin_kanal_id INTEGER,
        hosgeldin_mesaj TEXT DEFAULT 'Hoş geldin {uye}! 🎉',
        otorol_id INTEGER,
        otomod_aktif INTEGER DEFAULT 0,
        itiraf_kanal_id INTEGER,
        log_kanal_id INTEGER,
        uyari_kanal_id INTEGER
    )""")

    # Migrasyonlar
    kolonlar = [
        ("sunucu_ayarlar", "itiraf_kanal_id", "INTEGER"),
        ("sunucu_ayarlar", "log_kanal_id", "INTEGER"),
        ("sunucu_ayarlar", "uyari_kanal_id", "INTEGER"),
        ("kelime_oyunu", "kelime_sayisi", "INTEGER DEFAULT 0"),
        ("dukkan_urunler", "renk_kodu2", "TEXT"),
        ("dukkan_urunler", "sunucu_id", "INTEGER"),
        ("sunucu_ayarlar", "oyun_kanal_id", "INTEGER"),
        ("sunucu_ayarlar", "satinal_kanal_id", "INTEGER"),
        ("sunucu_ayarlar", "kelimeoyunu_kanal_id", "INTEGER"),
        ("sunucu_ayarlar", "oygec_aktif", "INTEGER DEFAULT 0"),
        ("ekonomi", "streak", "INTEGER DEFAULT 0"),
        ("ekonomi", "son_gunluk_tarih", "TEXT"),
        ("ekonomi", "gunluk_kayip", "INTEGER DEFAULT 0"),
        ("ekonomi", "gunluk_kayip_tarih", "TEXT"),
        ("ekonomi", "kumar_kazanma", "INTEGER DEFAULT 0"),
        ("ekonomi", "transfer_sayisi", "INTEGER DEFAULT 0"),
        # Çok sunuculu: sunucu başına ayarlar / kayıtlar (sadece ekleme — mevcut veri değişmez)
        ("sunucu_ayarlar", "yama_notlari_kanal_id", "INTEGER"),
        ("sunucu_ayarlar", "xp_aktif", "INTEGER DEFAULT 0"),   # XP/seviye sunucu başına opt-in
        ("sunucu_ayarlar", "gorusuruz_kanal_id", "INTEGER"),
        ("sunucu_ayarlar", "gorusuruz_mesaj", "TEXT"),
        ("sunucu_ayarlar", "dil", "TEXT DEFAULT 'tr'"),
        ("moderasyon_log", "sunucu_id", "INTEGER"),
    ]
    for tablo, kolon, tip in kolonlar:
        try:
            c.execute(f"ALTER TABLE {tablo} ADD COLUMN {kolon} {tip}")
        except sqlite3.OperationalError:
            pass

    # Eski tablo migrasyonu
    try:
        c.execute("SELECT sunucu_id, log_kanal_id FROM ayarlar")
        eski_veriler = c.fetchall()
        for s_id, l_id in eski_veriler:
            c.execute("SELECT sunucu_id FROM sunucu_ayarlar WHERE sunucu_id = ?", (s_id,))
            if c.fetchone():
                c.execute("UPDATE sunucu_ayarlar SET log_kanal_id = ? WHERE sunucu_id = ?", (l_id, s_id))
            else:
                c.execute("INSERT INTO sunucu_ayarlar (sunucu_id, log_kanal_id) VALUES (?, ?)", (s_id, l_id))
    except sqlite3.OperationalError:
        pass

    # Dükkan ürünleri (renk rolleri + rozetler)
    # sunucu_id NULL = global ürün (tüm sunucularda), değer = sunucuya özel
    c.execute("""CREATE TABLE IF NOT EXISTS dukkan_urunler (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        isim TEXT NOT NULL,
        tip TEXT NOT NULL,
        fiyat INTEGER NOT NULL,
        aciklama TEXT,
        emoji TEXT,
        renk_kodu TEXT,
        renk_kodu2 TEXT,
        sunucu_id INTEGER
    )""")

    # Kullanıcı envanteri (sunucu bazlı; ürün kataloğu dukkan_urunler globaldir)
    c.execute(f"CREATE TABLE IF NOT EXISTS envanter ({EKONOMI_TABLOLARI['envanter'][1]})")

    # Dükkan ürünlerini ekle (eğer boşsa)
    c.execute("SELECT COUNT(*) FROM dukkan_urunler")
    if c.fetchone()[0] == 0:
        urunler = [
            # ═══ RENKLİ İSİM ROLLERİ (Holografik Gradyan) ═══
            # renk_kodu = 1. renk, renk_kodu2 = 2. renk (gradyan bitiş)

            # Temel Gradyanlar (500 Coin)
            ("Mavi Gradyan", "rol", 500, "Mavi → Cyan geçişi", "🔵", "#00aaff", "#00e5ff"),
            ("Kırmızı Gradyan", "rol", 500, "Kırmızı → Turuncu geçişi", "🔴", "#ff2d2d", "#ff6d00"),
            ("Yeşil Gradyan", "rol", 500, "Yeşil → Turkuaz geçişi", "🟢", "#00ff7f", "#00e5cc"),
            ("Sarı Gradyan", "rol", 500, "Sarı → Turuncu geçişi", "🟡", "#ffea00", "#ff9100"),
            ("Turuncu Gradyan", "rol", 500, "Turuncu → Kırmızı geçişi", "🟠", "#ff6d00", "#ff2d2d"),
            ("Mor Gradyan", "rol", 500, "Mor → Pembe geçişi", "🟣", "#aa00ff", "#ff4da6"),
            ("Pembe Gradyan", "rol", 500, "Pembe → Mor geçişi", "🩷", "#ff4da6", "#d500f9"),
            ("Beyaz Gradyan", "rol", 500, "Beyaz → Açık Mavi geçişi", "⚪", "#f0f0ff", "#80d8ff"),

            # Orta Gradyanlar (750 Coin) — doğa & pastel geçişler
            ("Turkuaz Okyanus", "rol", 750, "Turkuaz → Derin Mavi geçişi", "💎", "#00e5cc", "#0091ea"),
            ("Lacivert Gece", "rol", 750, "Lacivert → Mor geçişi", "🫐", "#1a1aff", "#7c4dff"),
            ("Mercan Gün Batımı", "rol", 750, "Mercan → Sarı geçişi", "🪸", "#ff5577", "#ffea00"),
            ("Lavanta Rüya", "rol", 750, "Lavanta → Pembe geçişi", "🪻", "#b388ff", "#ff80ab"),
            ("Nane Orman", "rol", 750, "Nane → Yeşil geçişi", "🍀", "#00e676", "#00c853"),
            ("Şeftali Alacakaranlık", "rol", 750, "Şeftali → Mor geçişi", "🍑", "#ff8a80", "#aa00ff"),
            ("Buzul Şafak", "rol", 750, "Buz Mavisi → Pembe geçişi", "🧊", "#80d8ff", "#ff80ab"),
            ("Gül Ateşi", "rol", 750, "Gül Kurusu → Turuncu geçişi", "🌹", "#ff1744", "#ff6d00"),
            ("Limon Enerji", "rol", 750, "Limon → Yeşil geçişi", "🍋", "#c6ff00", "#00e676"),
            ("Orkide Büyüsü", "rol", 750, "Orkide → Mor geçişi", "🌸", "#ea80fc", "#7c4dff"),

            # Premium Gradyanlar (1000 Coin) — mücevher geçişleri
            ("Altın Parıltı", "rol", 1000, "Altın → Turuncu geçişi", "✨", "#ffc400", "#ff6d00"),
            ("Gümüş Ay", "rol", 1000, "Gümüş → Buz Mavisi geçişi", "🪙", "#cfd8dc", "#80d8ff"),
            ("Bronz Alev", "rol", 1000, "Bronz → Kırmızı geçişi", "🥉", "#e6a23c", "#ff2d2d"),
            ("Zümrüt Orman", "rol", 1000, "Zümrüt → Turkuaz geçişi", "💚", "#00c853", "#00e5cc"),
            ("Yakut Ateş", "rol", 1000, "Yakut → Mor geçişi", "❤️‍🔥", "#ff1100", "#aa00ff"),
            ("Safir Derinlik", "rol", 1000, "Safir → Cyan geçişi", "💙", "#2962ff", "#00e5ff"),
            ("Ametist Sihir", "rol", 1000, "Ametist → Pembe geçişi", "🔮", "#7c4dff", "#ff4da6"),
            ("Akuamarin Dalga", "rol", 1000, "Akuamarin → Yeşil geçişi", "🐉", "#1de9b6", "#00ff7f"),
            ("Opal Işık", "rol", 1000, "Opal → Lavanta geçişi", "🦢", "#e8eaf6", "#b388ff"),
            ("Sitrin Güneş", "rol", 1000, "Sitrin → Sarı geçişi", "🌟", "#ffab00", "#ffea00"),

            # Nadir Gradyanlar (1500 Coin) — neon çift tonlar
            ("Neon Pembe-Mor", "rol", 1500, "Neon Pembe → Neon Mor", "💖", "#ff00aa", "#d500f9"),
            ("Neon Yeşil-Cyan", "rol", 1500, "Neon Yeşil → Neon Cyan", "☘️", "#00ff44", "#00ffee"),
            ("Neon Mavi-Mor", "rol", 1500, "Neon Mavi → Neon Mor", "💠", "#00ddff", "#aa00ff"),
            ("Neon Turuncu-Sarı", "rol", 1500, "Neon Turuncu → Neon Sarı", "🔶", "#ff6600", "#ffff00"),
            ("Neon Mor-Pembe", "rol", 1500, "Neon Mor → Neon Pembe", "🌙", "#d500f9", "#ff00aa"),
            ("Neon Kırmızı-Turuncu", "rol", 1500, "Neon Kırmızı → Neon Turuncu", "🩸", "#ff0033", "#ff6600"),
            ("Neon Cyan-Yeşil", "rol", 1500, "Neon Cyan → Neon Yeşil", "⚡", "#00ffee", "#00ff44"),
            ("Neon Sarı-Lime", "rol", 1500, "Neon Sarı → Neon Lime", "🔥", "#ffff00", "#aaff00"),
            ("Neon Fuşya-Cyan", "rol", 1500, "Neon Fuşya → Neon Cyan", "🪩", "#ff00ff", "#00ffee"),
            ("Neon Lime-Yeşil", "rol", 1500, "Neon Lime → Neon Yeşil", "🍈", "#aaff00", "#00ff44"),

            # Efsanevi Gradyanlar (2500 Coin) — epik holografik
            ("Holografik Prizma", "rol", 2500, "Pembe → Cyan prisma efekti", "🌈", "#ff44cc", "#00ffee"),
            ("Platin Işıltı", "rol", 2500, "Platin → Altın geçişi", "🏆", "#e0e7ee", "#ffc400"),
            ("Elmas Parıltı", "rol", 2500, "Elmas → Buz Mavisi geçişi", "💎", "#a7ffeb", "#80d8ff"),
            ("Galaktik Nebula", "rol", 2500, "Mor → Mavi galaksi efekti", "🌌", "#6200ea", "#00aaff"),
            ("Okyanus Derinlik", "rol", 2500, "Okyanus → Turkuaz geçişi", "🌊", "#0091ea", "#00e5cc"),
            ("Aurora Borealis", "rol", 2500, "Yeşil → Mor kuzey ışığı", "🌠", "#00e5ff", "#aa00ff"),
            ("Magma Akışı", "rol", 2500, "Kırmızı → Sarı lav akışı", "🌋", "#ff3d00", "#ffea00"),
            ("Kozmik Patlama", "rol", 2500, "Mor → Pembe kozmik efekt", "🔭", "#aa00ff", "#ff44cc"),

            # ═══ ROZETLER / UNVANLAR ═══
            # Başlangıç Rozetleri (300 Coin)
            ("Çaylak", "rozet", 300, "Yeni başlayanlar için rozet", "🐣", None, None),
            ("Sohbetçi", "rozet", 300, "Sohbet etmeyi seven biri", "💬", None, None),
            ("Gece Kuşu", "rozet", 300, "Gece aktif olan üye", "🦉", None, None),
            ("Erken Kuş", "rozet", 300, "Sabahın erken saatlerinde aktif", "🐓", None, None),

            # Orta Rozetler (600 Coin)
            ("Kumarbaz", "rozet", 600, "Kumar masalarının kralı", "🎲", None, None),
            ("Meloman", "rozet", 600, "Müzik tutkunu", "🎵", None, None),
            ("Söz Ustası", "rozet", 600, "Kelimelerle dans eden", "📝", None, None),
            ("Troll Avcısı", "rozet", 600, "Trollere göz açtırmaz", "🛡️", None, None),
            ("Sanatçı", "rozet", 600, "Yaratıcı ruh", "🎨", None, None),
            ("Kaşif", "rozet", 600, "Her yerde olan üye", "🧭", None, None),

            # Premium Rozetler (1000 Coin)
            ("Zengin", "rozet", 1000, "Ekonomik güç simgesi", "🎖️", None, None),
            ("Efsane", "rozet", 1000, "Sunucunun efsanesi", "⭐", None, None),
            ("Koruyucu", "rozet", 1000, "Sunucuyu koruyan kahraman", "🦸", None, None),
            ("Hacker", "rozet", 1000, "Dijital dünyaın ustası", "💻", None, None),
            ("Gladyatör", "rozet", 1000, "Düello meydanının kralı", "⚔️", None, None),
            ("Şanslı", "rozet", 1000, "Şans her zaman yanında", "🍀", None, None),
            ("Gizemli", "rozet", 1000, "Kimse onu tam tanıyamaz", "🎭", None, None),
            ("Fırtına", "rozet", 1000, "Geldiğinde ortalık karışır", "🌪️", None, None),

            # Nadir Rozetler (2000 Coin)
            ("Ejderha", "rozet", 2000, "Ateş püskürten güç", "🐲", None, None),
            ("Kral", "rozet", 2000, "Sunucunun kralı", "👑", None, None),
            ("Kraliçe", "rozet", 2000, "Sunucunun kraliçesi", "👸", None, None),
            ("Hayalet", "rozet", 2000, "Görünmez ama her yerde", "👻", None, None),
            ("Ninja", "rozet", 2000, "Sessiz ve ölümcül", "🥷", None, None),
            ("Uzay Yolcusu", "rozet", 2000, "Galaksiler arası gezgin", "🚀", None, None),
            ("Simyacı", "rozet", 2000, "Altın yapan usta", "⚗️", None, None),

            # Efsanevi Rozetler (3500 Coin)
            ("Titan", "rozet", 3500, "Yıkılmaz güç", "🗿", None, None),
            ("Phoenix", "rozet", 3500, "Küllerinden doğan", "🔥", None, None),
            ("Omega", "rozet", 3500, "Son ve en güçlü", "Ω", None, None),
            ("Tanrısal", "rozet", 3500, "İlahi güce sahip", "⚜️", None, None),
            ("Karanlık Lord", "rozet", 3500, "Karanlığın efendisi", "🖤", None, None),
        ]
        c.executemany(
            "INSERT INTO dukkan_urunler (isim, tip, fiyat, aciklama, emoji, renk_kodu, renk_kodu2) VALUES (?, ?, ?, ?, ?, ?, ?)",
            urunler
        )

    # Yerel Türkçe sözlük (offline kelime doğrulama)
    c.execute("CREATE TABLE IF NOT EXISTS turkce_sozluk (kelime TEXT PRIMARY KEY)")

    # Kullanılan kelimeler — kelime oyununda tekrar engeli (sunucu bazlı)
    c.execute("""CREATE TABLE IF NOT EXISTS kullanilan_kelimeler (
        sunucu_id INTEGER NOT NULL,
        kelime TEXT NOT NULL,
        PRIMARY KEY (sunucu_id, kelime)
    )""")

    # Gönderilen oyun fırsatları (tekrar göndermemek için)
    c.execute("""CREATE TABLE IF NOT EXISTS gonderilen_firsatlar (
        id TEXT PRIMARY KEY,
        tip TEXT NOT NULL,
        tarih TEXT NOT NULL
    )""")

    # İşlem geçmişi (ekonomi hareketleri, sunucu bazlı)
    c.execute(f"CREATE TABLE IF NOT EXISTS islem_gecmisi ({EKONOMI_TABLOLARI['islem_gecmisi'][1]})")

    # Başarımlar (sunucu bazlı)
    c.execute(f"CREATE TABLE IF NOT EXISTS basarimlar ({EKONOMI_TABLOLARI['basarimlar'][1]})")

    # Kelime oyunu puanları (liderlik tablosu)
    c.execute("""CREATE TABLE IF NOT EXISTS kelime_puanlari (
        sunucu_id INTEGER NOT NULL,
        kullanici_id INTEGER NOT NULL,
        puan INTEGER DEFAULT 0,
        PRIMARY KEY (sunucu_id, kullanici_id)
    )""")

    # Global → sunucu bazlı ekonomi migrasyonu (tek seferlik; sonraki açılışlarda hiçbir şey yapmaz).
    # Hata → EkonomiMigrasyonHatasi (transaction geri alınır), main.baslat() botu başlatmaz.
    db.commit()
    _ekonomi_sunucu_bazli_migrasyon()

    # İndeksler — sık sorgulanan kolonlar
    # (Eski global tabloların idx_ekonomi_bakiye / idx_envanter_kullanici / idx_islem_gecmisi_kullanici /
    #  idx_basarimlar_kullanici indeksleri eski_global_* tablolarında kalır; basarimlar/envanter için
    #  (sunucu_id, kullanici_id, ...) birincil/UNIQUE anahtarı yeterli.)
    try:
        c.execute("CREATE INDEX IF NOT EXISTS idx_ekonomi_sunucu_bakiye ON ekonomi(sunucu_id, bakiye DESC)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_uyarilar_sunucu_kullanici ON uyarilar(sunucu_id, kullanici_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_moderasyon_log_hedef ON moderasyon_log(hedef_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_moderasyon_log_tarih ON moderasyon_log(tarih)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_islem_gecmisi_sunucu_kullanici ON islem_gecmisi(sunucu_id, kullanici_id, tarih DESC)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_islem_gecmisi_tarih ON islem_gecmisi(tarih)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_kelime_puanlari_sunucu ON kelime_puanlari(sunucu_id, puan DESC)")
    except sqlite3.OperationalError:
        pass

    db.commit()

    # Cache'leri yükle
    cache_yukle()
    logger.info("✅ Veritabanı tabloları hazır.")


def eski_verileri_temizle(islem_gecmisi_gun=90, ses_aktivite_gun=90, moderasyon_log_gun=180, firsatlar_gun=30):
    """Eski geçmiş kayıtlarını temizler ve DB boyutunu optimize eder."""
    import time
    c = db.cursor()
    toplam_silinen = 0
    try:
        # 1. islem_gecmisi (90 günden eski)
        if _tablo_var_mi(c, "islem_gecmisi"):
            kesim_tarih = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=islem_gecmisi_gun)).strftime("%Y-%m-%d %H:%M:%S")
            c.execute("DELETE FROM islem_gecmisi WHERE tarih < ?", (kesim_tarih,))
            toplam_silinen += c.rowcount

        # 2. ses_aktivite (90 günden eski)
        if _tablo_var_mi(c, "ses_aktivite"):
            kesim_ts = time.time() - (ses_aktivite_gun * 86400)
            c.execute("DELETE FROM ses_aktivite WHERE giris_ts < ?", (kesim_ts,))
            toplam_silinen += c.rowcount

        # 3. moderasyon_log (180 günden eski)
        if _tablo_var_mi(c, "moderasyon_log"):
            kesim_iso = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=moderasyon_log_gun)).isoformat()
            c.execute("DELETE FROM moderasyon_log WHERE tarih < ?", (kesim_iso,))
            toplam_silinen += c.rowcount

        # 4. gonderilen_firsatlar (30 günden eski)
        if _tablo_var_mi(c, "gonderilen_firsatlar"):
            kesim_iso = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=firsatlar_gun)).isoformat()
            c.execute("DELETE FROM gonderilen_firsatlar WHERE tarih < ?", (kesim_iso,))
            toplam_silinen += c.rowcount

        db.commit()
        if toplam_silinen > 0:
            c.execute("PRAGMA optimize")
            logger.info(f"🧹 Veritabanı temizliği: {toplam_silinen} eski kayıt temizlendi.")
    except Exception as e:
        logger.error(f"Veritabanı temizleme hatası: {e}")
    return toplam_silinen

