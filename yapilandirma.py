"""
MezarBot Yapılandırma
Tüm dosya yolları bot dizinine göre çözülür (çalışma dizininden bağımsız).

- .env        → gizli anahtarlar (DISCORD_TOKEN, GROQ_API_KEY, ...). Bot dizininden yüklenir.
- config.json → gizli OLMAYAN, bot geneli ayarlar (sahip_id, prefix, JS çalışma ortamı yolları).

Sunucuya özel ayarlar (log / hoşgeldin / mağaza / yama notu kanalı vb.) burada DEĞİL,
veritabanındaki `sunucu_ayarlar` tablosunda tutulur ve her sunucunun yöneticisi komutla ayarlar.
"""
import json
import logging
import os
import shutil

from dotenv import load_dotenv

logger = logging.getLogger('MezarBot.Yapilandirma')

# ── Profil ──
# MEZARBOT_PROFIL=muzik → aynı kodla yalnızca müzik çalan ikinci bot hesabı (ör. MüzikBaba). Kendi token'ı
# (.env.muzikbaba), kilidi, log'u ve veritabanı (data/muzikbaba.db) olur; ana botla çakışmaz. Bkz. cogs/muzik/ornekler.py
PROFIL = (os.getenv("MEZARBOT_PROFIL") or "").strip().lower()
MUZIK_PROFILI = PROFIL == "muzik"

# ── Yollar ──
BOT_DIZINI = os.path.dirname(os.path.abspath(__file__))
ENV_DOSYA = os.path.join(BOT_DIZINI, ".env")
PROFIL_ENV_DOSYA = os.path.join(BOT_DIZINI, ".env.muzikbaba") if MUZIK_PROFILI else None
CONFIG_DOSYA = os.path.join(BOT_DIZINI, "config.json")
VERI_DIZINI = os.path.join(BOT_DIZINI, "data")
GECICI_DIZIN = os.path.join(VERI_DIZINI, "tmp")            # TTS mp3 vb. geçici dosyalar
YTDL_CACHE_DIZINI = os.path.join(VERI_DIZINI, ".ytdl_cache")
LOG_DOSYA = os.path.join(BOT_DIZINI, "muzikbaba.log" if MUZIK_PROFILI else "mezarbot.log")
KILIT_DOSYA = os.path.join(BOT_DIZINI, "muzikbaba.lock" if MUZIK_PROFILI else "bot.lock")

# .env'yi bot dizininden yükle (CWD'den değil). Ortamda zaten tanımlı değişkenleri ezmez.
# Müzik profilinde önce kendi dosyası yüklenir (DISCORD_TOKEN oradan gelir); ortak anahtarlar (Spotify vb.) .env'den.
if PROFIL_ENV_DOSYA:
    load_dotenv(PROFIL_ENV_DOSYA, override=False)
load_dotenv(ENV_DOSYA, override=False)

# Veritabanı yolu. MEZARBOT_DB ortam değişkeni sadece test/araç amaçlıdır (ör. geçici kopya).
_VARSAYILAN_DB = os.path.join(VERI_DIZINI, "muzikbaba.db") if MUZIK_PROFILI else os.path.join(BOT_DIZINI, "mezarbot.db")
DB_DOSYA = os.path.abspath(os.getenv("MEZARBOT_DB") or _VARSAYILAN_DB)


def _config_oku():
    """config.json'u okur. Dosya yoksa boş sözlük döner; bozuksa açık bir hata ile durur."""
    try:
        with open(CONFIG_DOSYA, encoding="utf-8") as f:
            veri = json.load(f)
    except FileNotFoundError:
        logger.warning(f"config.json bulunamadı ({CONFIG_DOSYA}), varsayılanlar kullanılıyor.")
        return {}
    except json.JSONDecodeError as e:
        logger.critical(f"config.json okunamadı (geçersiz JSON): {e}")
        raise SystemExit(78)
    return veri if isinstance(veri, dict) else {}


def _id_oku(veri, anahtar):
    """Discord ID'sini int olarak döner. Boş / geçersiz ise None."""
    deger = veri.get(anahtar)
    if deger is None or str(deger).strip() in ("", "0"):
        return None
    try:
        return int(str(deger).strip())
    except ValueError:
        logger.warning(f"config.json: '{anahtar}' geçerli bir Discord ID değil ({deger!r}), yok sayılıyor.")
        return None


def _calistirilabilir_mi(yol):
    return bool(yol) and os.path.isfile(yol) and os.access(yol, os.X_OK)


_config = _config_oku()

# ── Bot geneli ayarlar ──
PREFIX = str(_config.get("prefix") or "!")
# Bot sahibi: tek kaynak. VIP bypass, itiraf logu, satın alma bildirimi ve commands.is_owner() bunu kullanır.
SAHIP_ID = _id_oku(_config, "sahip_id")
# Ekonomi sunucu bazlıdır. Eski (global) ekonomi kayıtları tek seferlik migrasyonda bu sunucuya atanır
# (bkz. database._ekonomi_sunucu_bazli_migrasyon). Sadece migrasyon kullanır.
ESKI_EKONOMI_SUNUCU_ID = _id_oku(_config, "eski_ekonomi_sunucu_id")


def _id_listesi(veri, anahtar):
    sonuc = []
    for deger in veri.get(anahtar) or []:
        try:
            sonuc.append(int(str(deger).strip()))
        except ValueError:
            logger.warning(f"config.json: '{anahtar}' içinde geçersiz ID ({deger!r}), yok sayılıyor.")
    return sonuc


# Sahip + güvenilir kişiler: moderasyon cezası verilemez (dokunulmaz), /yaz komutunu yetkisiz kullanabilir
GUVENILIR_IDLER = frozenset(([SAHIP_ID] if SAHIP_ID else []) + _id_listesi(_config, "guvenilir_idler"))
# Ek cog'lar (ör. sadece bu kuruluma özel tanıtım komutları): ["cogs.ornek"]
EK_COGLAR = [str(c) for c in _config.get("ek_coglar") or [] if str(c).strip()]
# Durum (presence) döngüsü: [["metin", "playing|watching|listening"], ...]. Boşsa varsayılan liste.
DURUM_MESAJLARI = [tuple(x) for x in _config.get("durum_mesajlari") or [] if isinstance(x, list) and len(x) == 2]

# Çoklu müzik botu: aynı sunucuda farklı ses kanallarında çalan bot hesaplarının ID'leri (sıra = öncelik).
MUZIK_ORNEKLERI = _id_listesi(_config, "muzik_ornekleri")

# Üye onay kapısı (cogs/sunucu_onay.py) — tek bir sunucu için; sunucu_id boşsa sistem kapalıdır.
_onay = _config.get("onay_sistemi") or {}
ONAY_SUNUCU_ID = _id_oku(_onay, "sunucu_id")
ONAY_KURUCU_ID = _id_oku(_onay, "kurucu_id") or SAHIP_ID      # kendi davetiyle gelenler otomatik onaylanır
ONAY_GENEL_DAVET_KODU = str(_onay.get("genel_davet_kodu") or "").strip()   # bu davetle gelenler onay bekler


def _js_calisma_ortamlari():
    """yt-dlp 'js_runtimes' ayarını oluşturur (YouTube JS challenge çözümü için).
    Öncelik: config.json'daki yol → bot bin dizini → PATH."""
    ortamlar = {}
    bot_deno = os.path.join(BOT_DIZINI, "bin", "deno")
    adaylar = (
        ("deno", "deno_yolu", bot_deno if _calistirilabilir_mi(bot_deno) else None),
        ("node", "node_yolu", None),
    )
    for ad, anahtar, varsayilan in adaylar:
        yol = str(_config.get(anahtar) or "").strip()
        if not _calistirilabilir_mi(yol):
            yol = varsayilan or shutil.which(ad)
        if _calistirilabilir_mi(yol):
            ortamlar[ad] = {"path": yol}
            if ad == "deno":
                # Deno modern ve tam destekli; eski Node 20 uyarısını engelle
                break
    return ortamlar


YTDLP_JS_CALISMA_ORTAMLARI = _js_calisma_ortamlari()
