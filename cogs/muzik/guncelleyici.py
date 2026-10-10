"""
yt-dlp tazeliği. YouTube sık değişir; eski yt-dlp = çalmayan şarkılar.

- Sahip komutu (!ytdlpguncelle) ve haftalık arka plan kontrolü venv'de şunu çalıştırır:
      <venv>/bin/python -m pip install -U "yt-dlp[default]"
  ([default] ekstrası yt-dlp-ejs'yi — YouTube JS çözücüsünü — yt-dlp sürümüyle uyumlu tutar.)
- pip bir executor thread'inde (subprocess) çalışır → olay döngüsü bloklanmaz.
- Yeni sürüm kurulduysa süreç YENİDEN_BASLATMA_KODU (75) ile çıkar: bot.cikis_kodu ayarlanır,
  bot.close() ile düzgün kapanılır (XP buffer vb. yazılır), main.baslat() bu kodla sys.exit eder.
  systemd birimi Restart=on-failure olduğu için sıfırdan farklı kodla çıkan süreci yeni sürümle
  yeniden başlatır (RestartPreventExitStatus sadece 3 ve 78).
- Arka plan kontrolü müzik çalan sunucu varken yeniden başlatmaz; herkes bitene kadar bekler (en fazla 6 saat).
"""
import asyncio
import importlib.metadata
import logging
import subprocess
import sys
import time
from dil import _t

logger = logging.getLogger('MezarBot.Muzik.Guncelleyici')

YENIDEN_BASLATMA_KODU = 75            # EX_TEMPFAIL — systemd Restart=on-failure bununla yeniden başlatır
KONTROL_ARALIGI = 7 * 24 * 3600       # haftalık
BOSTA_BEKLEME_SINIRI = 6 * 3600
PIP_ZAMAN_ASIMI = 300
DURUM_ANAHTARI = "ytdlp_son_kontrol"


def calisan_surum():
    try:
        from yt_dlp.version import __version__
        return __version__
    except ImportError:
        return "?"


def kurulu_surum():
    """Diskteki (pip'in kurduğu) yt-dlp sürümü — ayrı süreçte okunur (bu süreçteki modül eski kalır)."""
    try:
        cikti = subprocess.run(
            [sys.executable, "-c", "import importlib.metadata as m; print(m.version('yt-dlp'))"],
            capture_output=True, text=True, timeout=30)
        return cikti.stdout.strip() or "?"
    except (OSError, subprocess.SubprocessError):
        try:
            return importlib.metadata.version("yt-dlp")
        except importlib.metadata.PackageNotFoundError:
            return "?"


def pip_guncelle():
    """Senkron: pip ile yt-dlp'yi günceller → dict(basarili, eski, yeni, cikti). Executor'da çağrılmalı."""
    eski = calisan_surum()
    komut = [sys.executable, "-m", "pip", "install", "--upgrade", "--disable-pip-version-check",
             "--no-input", "yt-dlp[default]"]
    try:
        sonuc = subprocess.run(komut, capture_output=True, text=True, timeout=PIP_ZAMAN_ASIMI)
        basarili = sonuc.returncode == 0
        cikti = (sonuc.stdout[-1500:] + ("\n" + sonuc.stderr[-1500:] if sonuc.stderr else "")).strip()
    except subprocess.TimeoutExpired:
        basarili, cikti = False, _t("pip {PIP_ZAMAN_ASIMI} sn içinde bitmedi", PIP_ZAMAN_ASIMI=PIP_ZAMAN_ASIMI)
    except OSError as e:
        basarili, cikti = False, _t("pip çalıştırılamadı: {e}", e=e)
    yeni = kurulu_surum()
    return {'basarili': basarili, 'eski': eski, 'yeni': yeni, 'cikti': cikti,
            'degisti': basarili and yeni not in ("?", eski)}


async def guncelle(neden):
    loop = asyncio.get_running_loop()
    sonuc = await loop.run_in_executor(None, pip_guncelle)
    if sonuc['basarili']:
        logger.info(f"yt-dlp güncelleme kontrolü ({neden}): {sonuc['eski']} → {sonuc['yeni']}"
                    f"{' (YENİ SÜRÜM)' if sonuc['degisti'] else ' (zaten güncel)'}")
    else:
        logger.error(f"yt-dlp güncellemesi başarısız ({neden}): {sonuc['cikti'][-500:]}")
    return sonuc


async def yeniden_baslat(bot, cog, aninda=False):
    """Yeni yt-dlp sürümünü yüklemek için süreci 75 koduyla kapatır (systemd yeniden başlatır).
    aninda=False: müzik çalan sunucu kalmayana kadar bekler (en fazla BOSTA_BEKLEME_SINIRI)."""
    if not aninda:
        baslangic = time.monotonic()
        while cog.aktif_oynatici_sayisi() and time.monotonic() - baslangic < BOSTA_BEKLEME_SINIRI:
            await asyncio.sleep(300)
    logger.warning(f"yt-dlp güncellendi → süreç {YENIDEN_BASLATMA_KODU} koduyla yeniden başlatılıyor "
                   f"(systemd Restart=on-failure).")
    bot.cikis_kodu = YENIDEN_BASLATMA_KODU
    # cog.cog_unload bu görevi iptal edebilir → close'u bağımsız görev olarak başlat
    asyncio.get_running_loop().create_task(bot.close())
