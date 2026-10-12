"""
Kaynak çözümleme: YouTube (arama / video / playlist / YouTube Music), Spotify (API → embed sayfası,
spotify.link kısa linkleri), SoundCloud, doğrudan ses linkleri ve otomatik oynatma (YouTube Mix / "RD").

- yt-dlp ve Spotify ayrıştırma AYRI SÜREÇLERDE (isci.py, IsciHavuzu) çalışır → botun GIL'ini tutmaz,
  ses thread'i takılmaz. Sonuçlar kırpılmış JSON olarak gelir.
- Aynı anda en fazla ESZAMANLI_CIKARMA istek (bot geneli semafor).
- Arama sonuçları "flat" (hızlı) çekilir; tam akış bilgisi sadece çalmadan hemen önce (ön-çözme) alınır.
"""
import asyncio
import itertools
import json
import logging
import os
import re
import sys
import time
import urllib.parse

import aiohttp

from yapilandirma import BOT_DIZINI, YTDL_CACHE_DIZINI, YTDLP_JS_CALISMA_ORTAMLARI
from .kuyruk import Parca, normallestir
from dil import _t

logger = logging.getLogger('MezarBot.Muzik.Kaynak')

ESZAMANLI_CIKARMA = 3
ISCI_SAYISI = 2
TEK_ZAMAN_ASIMI = 30       # tek parça tam çıkarma (sn)
ARAMA_ZAMAN_ASIMI = 20
# YouTube "bot doğrulaması" önlemleri: PO token gerektirmeyen yedek istemciler + istek ritmi
YT_ISTEMCI_YEDEKLERI = ("web_embedded", "tv")
YT_MIN_ARALIK = 1.5        # ardışık YouTube isteklerinin başlangıcı arası en az (sn)
BOT_SOGUMA = 20            # tüm istemciler bot doğrulamasına takılırsa YouTube isteklerini bu kadar yavaşlat (sn)
SC_ADAY_SAYISI = 8         # SoundCloud yedeğinde aranan aday
SC_DENEME = 3              # en iyi bu kadar aday çözülmeye çalışılır (önizleme olanlar atlanır)
SC_MAX_PUAN = 45           # süre farkı + varyant cezası bundan büyükse "başka şarkı" sayılır
PLAYLIST_ZAMAN_ASIMI = 120
ILK_PARTI = 25             # büyük playlist'lerde önce bu kadarı eklenir, kalanı arka planda
ISCI_YOLU = os.path.join(os.path.dirname(os.path.abspath(__file__)), "isci.py")

_COOKIE_DOSYALARI = (
    os.path.join(BOT_DIZINI, "data", "cookies.txt"),
    os.path.join(BOT_DIZINI, "cookies.txt"),
)
_COOKIE_YOLU = next((p for p in _COOKIE_DOSYALARI if os.path.isfile(p)), None)

_YTDL_TEMEL = {
    'quiet': True,
    'no_warnings': True,
    'noprogress': True,
    'source_address': '0.0.0.0',   # IPv4 (IPv6 blokları YouTube'da daha sık kısıtlanıyor)
    'socket_timeout': 10,
    'retries': 3,
    'extractor_retries': 2,
    'cachedir': YTDL_CACHE_DIZINI,
    'js_runtimes': YTDLP_JS_CALISMA_ORTAMLARI,
    # yt-dlp-ejs kuruluysa yerel çözücü kullanılır; değilse GitHub'dan indirilen EJS betiği (önbelleğe alınır)
    'remote_components': ['ejs:github'],
    'logtostderr': False,
}
if _COOKIE_YOLU:
    _YTDL_TEMEL['cookiefile'] = _COOKIE_YOLU
    logger.info(f"🍪 yt-dlp çerez dosyası yüklendi: {_COOKIE_YOLU}")

# Tek parça: önce Opus (YouTube format 251 → Discord'a yeniden kodlamadan aktarılabilir)
ydl_opts = {
    **_YTDL_TEMEL,
    'format': 'bestaudio[acodec=opus]/bestaudio[ext=webm]/bestaudio[ext=m4a]/bestaudio/best',
    'noplaylist': True,
}
# Playlist / arama: sadece liste bilgisi (her video için ayrı istek YOK → hızlı)
ydl_playlist_opts = {
    **_YTDL_TEMEL,
    'extract_flat': 'in_playlist',
    'noplaylist': False,
    'ignoreerrors': True,
}

# ── URL kalıpları ──
SPOTIFY_REGEX = re.compile(
    r'(?:open\.spotify\.com/(?:intl-[a-z]{2}(?:-[a-z]{2})?/)?(?:embed/)?|spotify:)(track|album|playlist|artist)[/:]([A-Za-z0-9]{10,30})')
SPOTIFY_KISA_REGEX = re.compile(r'^https?://(?:spotify\.link|spoti\.fi|spotify\.app\.link)/\S+', re.I)
YT_LIST_REGEX = re.compile(r'[?&]list=([A-Za-z0-9_-]+)')
YT_VIDEO_REGEX = re.compile(r'(?:youtube\.com/(?:watch\?(?:.*&)?v=|shorts/|live/|embed/)|youtu\.be/)([A-Za-z0-9_-]{11})')
YT_HOST_REGEX = re.compile(r'^https?://(?:[a-z0-9-]+\.)?(?:youtube\.com|youtu\.be|youtube-nocookie\.com)/', re.I)
SC_SET_REGEX = re.compile(r'soundcloud\.com/[^/]+/sets/', re.I)

# YouTube video başlıklarındaki "(Official Video)", "[Lyrics]" gibi ekler — SoundCloud araması için atılır
_VIDEO_EKI = re.compile(r"\s*[\(\[][^\)\]]*(?:official|video|audio|lyric|klip|visuali[sz]er|hd|4k|explicit|clean)[^\)\]]*[\)\]]", re.I)

_TARAYICI_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36'


def girdi_turu(metin):
    """Kullanıcı girdisini sınıflandırır → (tur, ek)
    tur: 'spotify' (ek=(alt_tur, id)) | 'spotify_kisa' (ek=url) | 'playlist' (ek=url) | 'url' (ek=url) | 'arama' (ek=metin)"""
    metin = metin.strip().strip('<>')
    sp = SPOTIFY_REGEX.search(metin)
    if sp:
        return 'spotify', (sp.group(1), sp.group(2))
    if SPOTIFY_KISA_REGEX.match(metin):
        return 'spotify_kisa', metin
    if re.match(r'^https?://', metin, re.I):
        if YT_HOST_REGEX.match(metin):
            liste = YT_LIST_REGEX.search(metin)
            # RD… = YouTube Mix (sonsuz, kişiye özel) → sadece videoyu çal; normal liste → playlist
            if liste and not liste.group(1).startswith('RD'):
                return 'playlist', metin
            return 'url', metin
        if SC_SET_REGEX.search(metin):
            return 'playlist', metin
        return 'url', metin
    return 'arama', metin


def youtube_video_id(url):
    m = YT_VIDEO_REGEX.search(url or "")
    return m.group(1) if m else ""


# ══════════════════════════════════════════════
#  HATA SINIFLANDIRMA
# ══════════════════════════════════════════════

class CozmeHatasi(Exception):
    """Parça çözülemedi. `sebep`: kullanıcıya gösterilecek Türkçe açıklama.
    `kalici`: True ise aynı video tekrar denenmemeli (yaş kısıtı, silinmiş ...); aramalarda sıradaki aday denenir."""

    def __init__(self, sebep, kalici=True, ham=""):
        super().__init__(sebep)
        self.sebep = sebep
        self.kalici = kalici
        self.ham = ham


class IsciHatasi(Exception):
    """İşçi sürecinde oluşan hata (mesaj yt-dlp/spotipy'nin orijinal metni)."""

    def __init__(self, mesaj, tur="", http_status=None):
        super().__init__(mesaj)
        self.tur = tur
        self.http_status = http_status


_HATA_KALIPLARI = (
    # (anahtar kelimeler, sebep, kalici)
    (("confirm your age", "age-restricted", "age restricted", "inappropriate for some users"), "yaş kısıtlamalı (giriş gerekiyor)", True),
    (("private video",), "özel (gizli) video", True),
    (("members-only", "join this channel", "members only"), "sadece kanal üyelerine açık", True),
    (("copyright",), "telif nedeniyle kaldırılmış", True),
    (("not available in your country", "blocked it in your country", "geo restrict", "geo-restrict"), "bölge engeli", True),
    (("drm",), "DRM korumalı", True),
    (("premieres in", "live event will begin", "this live event"), "yayın henüz başlamadı", True),
    (("not a bot", "sign in to confirm you"), "YouTube bot doğrulaması istedi (geçici)", False),
    (("http error 429", "too many requests", "rate-limit", "rate limit"), "YouTube istek sınırı (geçici)", False),
    (("video unavailable", "is unavailable", "has been removed", "no longer available", "does not exist",
      "http error 404", "not found"), "video kullanılamıyor / kaldırılmış", True),
    (("requested format is not available", "no video formats"), "çalınabilir ses formatı yok", True),
    (("unsupported url",), "desteklenmeyen link", True),
    (("timed out", "timeout", "zaman aşımı"), "zaman aşımı", False),
    (("işçi süreci",), "çözücü süreci yeniden başlatıldı (geçici)", False),
)


def _bot_hatasi(hata):
    return "bot doğrulaması" in (getattr(hata, "sebep", "") or "")


def hata_sebebi(hata):
    """Exception → CozmeHatasi (Türkçe sebep + kalıcılık)."""
    if isinstance(hata, CozmeHatasi):
        return hata
    if isinstance(hata, (asyncio.TimeoutError, TimeoutError)):
        return CozmeHatasi(_t("zaman aşımı"), kalici=False, ham="timeout")
    ham = str(hata)
    kucuk = ham.lower()
    for kelimeler, sebep, kalici in _HATA_KALIPLARI:
        if any(k in kucuk for k in kelimeler):
            return CozmeHatasi(sebep, kalici=kalici, ham=ham[:300])
    return CozmeHatasi(_t("çözülemedi"), kalici=False, ham=ham[:300])


# ══════════════════════════════════════════════
#  İŞÇİ SÜREÇ HAVUZU
# ══════════════════════════════════════════════

class _Isci:
    def __init__(self, surec, okuyucu):
        self.surec = surec
        self.okuyucu = okuyucu
        self.bekleyen = set()
        self.zaman_asimi = 0

    def canli(self):
        return self.surec.returncode is None


class IsciHavuzu:
    """isci.py süreçlerini yönetir: tembel başlatma, en az meşgule gönderme, ölürse yeniden başlatma."""

    def __init__(self, sayi=ISCI_SAYISI):
        self._isciler = [None] * sayi
        self._bekleyen = {}
        self._sayac = itertools.count(1)
        self._baslatma_kilidi = asyncio.Lock()
        self._kapandi = False

    async def _baslat(self, i):
        env = dict(os.environ)
        env.setdefault("PYTHONIOENCODING", "utf-8")
        surec = await asyncio.create_subprocess_exec(
            sys.executable, "-u", ISCI_YOLU,
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=None,
            limit=32 * 1024 * 1024, env=env)
        isci = _Isci(surec, None)
        isci.okuyucu = asyncio.create_task(self._oku(isci), name=f"muzik-isci-okuyucu-{surec.pid}")
        self._isciler[i] = isci
        logger.info(f"🧵 Müzik işçi süreci başlatıldı (pid {surec.pid})")
        return isci

    async def _oku(self, isci):
        try:
            while True:
                satir = await isci.surec.stdout.readline()
                if not satir:
                    break
                try:
                    yanit = json.loads(satir)
                except json.JSONDecodeError:
                    continue
                fut = self._bekleyen.pop(yanit.get("id"), None)
                if fut is not None and not fut.done():
                    fut.set_result(yanit)
        except (asyncio.CancelledError, ValueError, ConnectionError):
            pass
        finally:
            for istek_id in list(isci.bekleyen):
                fut = self._bekleyen.pop(istek_id, None)
                if fut is not None and not fut.done():
                    fut.set_exception(IsciHatasi(_t("işçi süreci kapandı")))
            if isci.surec.returncode is None:
                try:
                    isci.surec.kill()
                except ProcessLookupError:
                    pass
            try:
                await asyncio.wait_for(isci.surec.wait(), timeout=5)   # zombi kalmasın
            except (asyncio.TimeoutError, asyncio.CancelledError):
                pass

    async def _isci_sec(self):
        async with self._baslatma_kilidi:
            for i, isci in enumerate(self._isciler):
                if isci is None or not isci.canli():
                    if isci is not None:
                        logger.warning("Müzik işçi süreci ölmüş, yeniden başlatılıyor.")
                    return await self._baslat(i)
            return min(self._isciler, key=lambda x: len(x.bekleyen))

    async def calistir(self, islem, zaman_asimi, **arg):
        if self._kapandi:
            raise IsciHatasi(_t("işçi süreci kapandı"))
        isci = await self._isci_sec()
        istek_id = next(self._sayac)
        fut = asyncio.get_running_loop().create_future()
        self._bekleyen[istek_id] = fut
        isci.bekleyen.add(istek_id)
        try:
            isci.surec.stdin.write((json.dumps({"id": istek_id, "islem": islem, "arg": arg}) + "\n").encode())
            await isci.surec.stdin.drain()
            yanit = await asyncio.wait_for(fut, timeout=zaman_asimi)
        except (BrokenPipeError, ConnectionResetError):
            raise IsciHatasi(_t("işçi süreci kapandı"))
        except asyncio.TimeoutError:
            isci.zaman_asimi += 1
            if isci.zaman_asimi >= 3:   # takılmış iş parçacıkları birikti → süreci yenile
                logger.warning(f"Müzik işçi süreci (pid {isci.surec.pid}) üst üste zaman aşımı → yeniden başlatılıyor")
                try:
                    isci.surec.kill()
                except ProcessLookupError:
                    pass
            raise
        finally:
            self._bekleyen.pop(istek_id, None)
            isci.bekleyen.discard(istek_id)
        if yanit.get("ok"):
            isci.zaman_asimi = 0
            return yanit.get("sonuc")
        raise IsciHatasi(yanit.get("hata") or _t("bilinmeyen hata"), yanit.get("tur", ""), yanit.get("http_status"))

    async def kapat(self):
        self._kapandi = True
        for isci in self._isciler:
            if isci is None:
                continue
            try:
                isci.surec.stdin.close()
            except (OSError, RuntimeError):
                pass
        for isci in self._isciler:
            if isci is None:
                continue
            try:
                await asyncio.wait_for(isci.surec.wait(), timeout=3)
            except asyncio.TimeoutError:
                try:
                    isci.surec.kill()
                except ProcessLookupError:
                    pass
                await isci.surec.wait()
            if isci.okuyucu and not isci.okuyucu.done():
                isci.okuyucu.cancel()
        self._isciler = [None] * len(self._isciler)

    def pidler(self):
        return [i.surec.pid for i in self._isciler if i is not None and i.canli()]


# ══════════════════════════════════════════════
#  YARDIMCILAR
# ══════════════════════════════════════════════

def _kucuk_resim(entry):
    if entry.get('thumbnail'):
        return entry['thumbnail']
    kucukler = entry.get('thumbnails') or []
    if kucukler:
        return kucukler[-1].get('url') or ""
    vid = entry.get('id') if (entry.get('ie_key') or '').lower().startswith('youtube') else ""
    return f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg" if vid else ""


def _kaynak_adi(entry):
    anahtar = (entry.get('extractor_key') or entry.get('ie_key') or entry.get('extractor') or "").lower()
    if anahtar.startswith('youtube'):
        return 'youtube'
    if 'soundcloud' in anahtar:
        return 'soundcloud'
    if anahtar in ('generic', 'http', ''):
        return 'http'
    return anahtar


def _entry_url(entry):
    """Flat entry → oynatılabilir sayfa URL'si."""
    url = entry.get('webpage_url') or entry.get('url') or ""
    if _kaynak_adi(entry) == 'youtube' and entry.get('id') and not url.startswith('http'):
        url = f"https://www.youtube.com/watch?v={entry['id']}"
    return url


def flat_entry_parca(entry, **ek):
    """Flat playlist/arama entry'sinden Parca oluşturur (çözülmemiş)."""
    kaynak = _kaynak_adi(entry)
    url = _entry_url(entry)
    return Parca(
        sorgu=url,
        baslik=entry.get('title') or "",
        url=url if url.startswith('http') else "",
        sure=int(entry.get('duration') or 0),
        kucuk_resim=_kucuk_resim(entry),
        kaynak=kaynak,
        sanatci=entry.get('artist') or entry.get('channel') or entry.get('uploader') or "",
        video_id=entry.get('id', "") if kaynak == 'youtube' else "",
        **ek,
    )


_GECERSIZ_BASLIKLAR = {"[private video]", "[deleted video]", "[unavailable video]"}

# Spotify → YouTube eşleştirmesinde istenmeyen varyantlar (Spotify başlığında yoksa ceza)
_ISTENMEYEN = ("live", "canlı", "cover", "remix", "8d", "slowed", "sped up", "nightcore", "karaoke",
               "instrumental", "reverb", "lyrics", "sözleri", "1 hour", "1 saat", "reaction",
               "bootleg", "mashup", "rework", "tiktok", "acoustic", "akustik", "piano")


def aday_puani(aday_baslik, aday_sure, hedef_baslik, hedef_sure):
    """Düşük puan = daha iyi eşleşme. Süre farkı + istenmeyen varyant cezası."""
    puan = 0.0
    if hedef_sure and aday_sure:
        fark = abs(aday_sure - hedef_sure)
        puan += fark if fark <= 10 else 10 + (fark - 10) * 3
    elif hedef_sure and not aday_sure:
        puan += 30
    a, h = normallestir(aday_baslik), normallestir(hedef_baslik)
    for kelime in _ISTENMEYEN:
        if kelime in a and kelime not in h:
            puan += 40
    if "official audio" in a or "topic" in a:
        puan -= 3
    return puan


_HARF_ESLE = str.maketrans("ıİşŞğĞüÜöÖçÇâÂîÎûÛ", "iissgguuooccaaiiuu")


def _kelimeler(metin):
    metin = normallestir(str(metin or "").translate(_HARF_ESLE))   # önce eşle: casefold("İ") birleşik nokta üretir
    return {k for k in re.split(r"[^0-9a-z]+", metin) if k}


def baslik_uyar_mi(hedef, aday_baslik, aday_kanal=""):
    """SoundCloud yedeğinde yanlış şarkıyı elemek için: hedefin şarkı adı ("Sanatçı - Şarkı" ise sağ taraf)
    kelimelerinin çoğu adayın başlığında geçmeli; sanatçı kelimeleri başlıkta ya da yükleyicide."""
    if " - " in hedef:
        sanatci, sarki = hedef.split(" - ", 1)
    else:
        sanatci, sarki = "", hedef
    sarki_k, aday_k = _kelimeler(sarki), _kelimeler(aday_baslik)
    if not sarki_k:
        return True
    if len(sarki_k & aday_k) / len(sarki_k) < 0.6:
        return False
    sanatci_k = _kelimeler(sanatci)
    if not sanatci_k or sanatci_k & (aday_k | _kelimeler(aday_kanal)):
        return True
    bitisik = lambda m: re.sub(r"[^0-9a-z]+", "", normallestir(str(m or "").translate(_HARF_ESLE)))   # noqa: E731
    return bitisik(sanatci) in bitisik(aday_kanal) + bitisik(aday_baslik)   # "sezenaksu" gibi bitişik kullanıcı adları


def en_iyi_aday(adaylar, hedef_baslik, hedef_sure, haric=()):
    """adaylar: flat entry listesi → puana göre sıralı entry listesi (haric id'ler çıkarılmış)."""
    uygun = [e for e in adaylar if e and e.get('id') not in haric
             and normallestir(e.get('title')) not in _GECERSIZ_BASLIKLAR]
    return sorted(uygun, key=lambda e: aday_puani(e.get('title'), e.get('duration'), hedef_baslik, hedef_sure))


# ══════════════════════════════════════════════
#  ÇÖZÜCÜ
# ══════════════════════════════════════════════

class Cozucu:
    """Bot geneli tek örnek (Muzik cog'u sahiplenir). Tüm yt-dlp / Spotify çağrıları buradan (işçi süreçlere) gider."""

    def __init__(self, spotify_aktif=False, eszamanli=ESZAMANLI_CIKARMA, isci_sayisi=ISCI_SAYISI):
        self._sem = asyncio.Semaphore(eszamanli)
        self.havuz = IsciHavuzu(isci_sayisi)
        self.spotify_aktif = spotify_aktif
        self._sp_kapali_bitis = 0.0     # Spotify API 403/429 verirse bir süre embed'e geç
        self._oturum = None
        self._yt_sonraki = 0.0          # bir sonraki YouTube isteğinin en erken başlama zamanı (monotonic)

    async def kapat(self):
        await self.havuz.kapat()
        if self._oturum and not self._oturum.closed:
            await self._oturum.close()

    async def _http(self):
        if self._oturum is None or self._oturum.closed:
            self._oturum = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15),
                                                 headers={'User-Agent': _TARAYICI_UA})
        return self._oturum

    async def _ytdl(self, secenekler, hedef, zaman_asimi, mod="tam"):
        """yt-dlp extract_info → işçi süreçte (semafor ile sınırlı)."""
        async with self._sem:
            if not str(hedef).startswith('scsearch') and 'soundcloud.com' not in str(hedef):
                await self._yt_ritim()
            return await self.havuz.calistir("cikar", zaman_asimi, secenekler=secenekler, hedef=hedef, mod=mod)

    async def _yt_ritim(self):
        """YouTube isteklerini en az YT_MIN_ARALIK arayla başlatır (ani istek patlaması bot doğrulamasını tetikler)."""
        simdi = time.monotonic()
        baslangic = max(self._yt_sonraki, simdi)
        self._yt_sonraki = baslangic + YT_MIN_ARALIK
        if baslangic > simdi:
            await asyncio.sleep(baslangic - simdi)

    # ── Arama ──
    async def ara(self, metin, adet=5, platform='yt'):
        """Flat arama → [entry]. platform: 'yt' | 'sc'."""
        onek = 'scsearch' if platform == 'sc' else 'ytsearch'
        bilgi = await self._ytdl(ydl_playlist_opts, f"{onek}{adet}:{metin}", ARAMA_ZAMAN_ASIMI, mod="flat")
        return [e for e in (bilgi or {}).get('entries') or [] if e]

    async def arama_parcasi(self, metin, **ek):
        """Kullanıcı araması → ilk uygun sonucun Parca'sı (flat, hızlı). YouTube sonuç vermezse SoundCloud."""
        for platform in ('yt', 'sc'):
            try:
                adaylar = await self.ara(metin, adet=5, platform=platform)
            except (IsciHatasi, asyncio.TimeoutError) as e:
                logger.warning(f"Arama hatası ({platform}): {hata_sebebi(e).sebep} — {metin[:60]}")
                continue
            adaylar = [a for a in adaylar if normallestir(a.get('title')) not in _GECERSIZ_BASLIKLAR]
            if adaylar:
                return flat_entry_parca(adaylar[0], arama_metni=metin, **ek)
        return None

    # ── Tam çözüm (akış URL'si) ──
    async def coz(self, parca, zorla=False, istemci=None):
        """Parca'nın akış URL'sini doldurur. Arama sorgularında (Spotify eşleşmesi dahil) en iyi adayı seçer,
        kısıtlı videolarda sıradaki adayı dener. Başarısızsa CozmeHatasi.
        istemci: YouTube player_client (ör. varsayılan istemcinin URL'si 403 verdiyse yedek istemci)."""
        if not zorla and parca.akis_gecerli_mi():
            return parca
        denenen = set()
        son_hata = None
        try:
            hedef = parca.sorgu
            if hedef.startswith(('ytsearch', 'scsearch')):
                hedef = await self._aramadan_hedef(parca, denenen)
            secenek = {**ydl_opts, 'extractor_args': {'youtube': {'player_client': [istemci]}}} if istemci else ydl_opts
            bot_denemesi = 0
            for deneme in range(1 + len(YT_ISTEMCI_YEDEKLERI)):
                try:
                    bilgi = await self._ytdl(secenek, hedef, TEK_ZAMAN_ASIMI)
                    if not bilgi or not bilgi.get('url'):
                        raise CozmeHatasi(_t("çalınabilir ses formatı yok"))
                    self._bilgi_uygula(parca, bilgi)
                    return parca
                except (IsciHatasi, CozmeHatasi, asyncio.TimeoutError) as e:
                    son_hata = hata_sebebi(e)
                    logger.warning(f"Çözme hatası [{son_hata.sebep}] {parca.gosterim(50)}: {son_hata.ham[:160]}")
                    aranabilir = bool(parca.arama_metni) or parca.sorgu.startswith(('ytsearch', 'scsearch'))
                    if son_hata.kalici and aranabilir:
                        denenen.add(youtube_video_id(hedef) or hedef)
                        hedef = await self._aramadan_hedef(parca, denenen)
                        continue
                    if _bot_hatasi(son_hata) and bot_denemesi < len(YT_ISTEMCI_YEDEKLERI):
                        istemci = YT_ISTEMCI_YEDEKLERI[bot_denemesi]
                        bot_denemesi += 1
                        logger.info(f"YouTube bot doğrulaması → '{istemci}' istemcisiyle yeniden deneniyor: {parca.gosterim(50)}")
                        secenek = {**ydl_opts, 'extractor_args': {'youtube': {'player_client': [istemci]}}}
                        await asyncio.sleep(1)
                        continue
                    if not son_hata.kalici and deneme == 0:
                        await asyncio.sleep(2)
                        continue
                    break
        except (IsciHatasi, CozmeHatasi, asyncio.TimeoutError) as e:   # arama adımı başarısız / aday kalmadı
            if son_hata is None or not isinstance(e, CozmeHatasi):
                son_hata = hata_sebebi(e)   # "aday kalmadı" asıl sebebi (yaş kısıtı vb.) ezmesin
        if son_hata is not None and _bot_hatasi(son_hata):
            self._yt_sonraki = max(self._yt_sonraki, time.monotonic() + BOT_SOGUMA)   # YouTube'u kısa süre dinlendir
        # YouTube'da çalınamadı (geçici ya da kalıcı: bot doğrulaması, yaş/bölge kısıtı, kaldırılmış ...) → SoundCloud
        yedek = await self._soundcloud_yedek(parca)
        if yedek is not None:
            return yedek
        raise son_hata or CozmeHatasi(_t("çözülemedi"))

    async def _yedek_arama_metni(self, parca):
        """SoundCloud'da aranacak metin: arama metni → sanatçı + başlık → (başlıksız YouTube linki) oEmbed başlığı."""
        metin = parca.arama_metni or " ".join(x for x in (parca.sanatci, parca.baslik) if x).strip()
        if metin or not YT_HOST_REGEX.match(parca.sorgu or ""):
            return metin
        try:   # oEmbed yaş/bölge kısıtlı videolarda da başlık verir; yt-dlp gerektirmez
            oturum = await self._http()
            async with oturum.get("https://www.youtube.com/oembed",
                                  params={"url": parca.sorgu, "format": "json"}) as yanit:
                if yanit.status != 200:
                    return ""
                veri = await yanit.json(content_type=None)
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
            return ""
        baslik = _VIDEO_EKI.sub("", veri.get("title") or "").strip()
        kanal = re.sub(r"(?i)(vevo|\s*-\s*topic)$", "", veri.get("author_name") or "").strip()
        # "Sanatçı - Şarkı" biçimindeyse kanal adı gereksiz (çoğu zaman VEVO/plak şirketi)
        return baslik if " - " in baslik or not kanal else f"{kanal} {baslik}"

    async def _soundcloud_yedek(self, parca):
        """YouTube'da çalınamayan şarkıyı SoundCloud'da arar. 30 sn'lik önizlemeleri (Go+) ve süresi/varyantı
        tutmayan adayları atlar. Bulamazsa None (asıl hata kullanıcıya gösterilir)."""
        if parca.kaynak == 'soundcloud' or parca.sorgu.startswith('scsearch') or 'soundcloud.com' in (parca.url or ''):
            return None
        metin = await self._yedek_arama_metni(parca)
        if not metin:
            return None
        hedef_sure = parca.beklenen_sure or parca.sure
        try:
            adaylar = await self.ara(metin, adet=SC_ADAY_SAYISI, platform='sc')
        except (IsciHatasi, asyncio.TimeoutError) as e:
            logger.warning(f"SoundCloud yedeği araması başarısız: {hata_sebebi(e).sebep} — {metin[:60]}")
            return None
        # Süre bilinmiyorsa (başlıksız link) tek ölçüt varyant cezası: cover/remix/live... hiç kabul edilmez
        sinir = SC_MAX_PUAN if hedef_sure else 39
        deneme = 0
        for aday in en_iyi_aday(adaylar, metin, hedef_sure, ()):
            if aday_puani(aday.get('title'), aday.get('duration'), metin, hedef_sure) > sinir:
                break   # sıralı: bundan sonrakiler daha da kötü eşleşme (yanlış şarkı çalmaktansa hata)
            if not baslik_uyar_mi(metin, aday.get('title') or "", aday.get('uploader') or aday.get('channel') or ""):
                continue
            if not hedef_sure and 0 < (aday.get('duration') or 0) < 90:
                continue   # süre bilinmiyorsa 1,5 dk altı yüklemeler büyük ihtimalle kesit/önizleme
            if deneme >= SC_DENEME:
                break
            deneme += 1
            try:
                bilgi = await self._ytdl(ydl_opts, _entry_url(aday), TEK_ZAMAN_ASIMI)
            except (IsciHatasi, asyncio.TimeoutError) as e:
                logger.warning(f"SoundCloud adayı çözülemedi: {hata_sebebi(e).sebep} — {aday.get('title')}")
                continue
            if not bilgi or not bilgi.get('url') or 'preview' in (bilgi.get('format_id') or ''):
                continue   # sadece 30 sn önizleme var (SoundCloud Go+)
            self._bilgi_uygula(parca, bilgi)
            parca.sorgu = bilgi.get('webpage_url') or parca.sorgu   # yeniden çözmede (link süresi dolunca) doğrudan SoundCloud
            logger.info(f"SoundCloud yedeği kullanıldı: {parca.gosterim(60)}")
            return parca
        logger.info(f"SoundCloud yedeği bulunamadı: {metin[:60]}")
        return None

    async def _aramadan_hedef(self, parca, haric):
        metin = parca.arama_metni or parca.sorgu.split(':', 1)[-1]
        platform = 'sc' if parca.sorgu.startswith('scsearch') else 'yt'
        adaylar = await self.ara(metin, adet=5, platform=platform)
        sirali = en_iyi_aday(adaylar, parca.baslik or metin, parca.beklenen_sure, haric)
        if not sirali:
            raise CozmeHatasi(_t("uygun sonuç bulunamadı"))
        return _entry_url(sirali[0])

    @staticmethod
    def _bilgi_uygula(parca, bilgi):
        parca.akis_url = bilgi['url']
        parca.akis_basliklari = dict(bilgi.get('http_headers') or {})
        parca.akis_codec = (bilgi.get('acodec') or "").lower()
        parca.akis_protokol = (bilgi.get('protocol') or "").lower()
        parca.canli = bool(bilgi.get('is_live'))
        parca.cozulme_zamani = time.time()
        kaynak = _kaynak_adi(bilgi)
        spotify = parca.kaynak == 'spotify'
        if not spotify:
            parca.kaynak = kaynak
            parca.baslik = bilgi.get('title') or parca.baslik
            parca.url = bilgi.get('webpage_url') or parca.url
        elif not parca.baslik:
            parca.baslik = bilgi.get('title') or ""
        parca.sure = int(bilgi.get('duration') or parca.sure or 0)
        if kaynak == 'youtube':
            parca.video_id = bilgi.get('id') or parca.video_id
        parca.kucuk_resim = bilgi.get('thumbnail') or parca.kucuk_resim
        parca.sanatci = parca.sanatci or bilgi.get('artist') or bilgi.get('channel') or bilgi.get('uploader') or ""

    # ── Playlist ──
    async def playlist(self, url, bas=1, son=None):
        """Flat playlist → (baslik, [Parca], toplam_bilinen). bas/son: 1 tabanlı, dahil."""
        secenekler = dict(ydl_playlist_opts)
        secenekler['playlist_items'] = f"{bas}-{son}" if son else f"{bas}-"
        bilgi = await self._ytdl(secenekler, url, PLAYLIST_ZAMAN_ASIMI, mod="flat")
        if not bilgi:
            return None, [], 0
        parcalar = []
        for entry in bilgi.get('entries') or []:
            if not entry or normallestir(entry.get('title')) in _GECERSIZ_BASLIKLAR:
                continue
            p = flat_entry_parca(entry)
            if p.sorgu.startswith('http'):
                parcalar.append(p)
        return bilgi.get('title') or "Playlist", parcalar, int(bilgi.get('playlist_count') or 0)

    # ── Otomatik oynatma (radyo) ──
    async def radyo(self, tohum, haric_idler=(), haric_basliklar=(), adet=5):
        """Tohum parçaya benzer parçalar: YouTube Mix (RD) listesi. Tohum YouTube değilse önce YouTube'da aranır."""
        vid = tohum.video_id or youtube_video_id(tohum.url)
        if not vid:
            try:
                adaylar = await self.ara(f"{tohum.sanatci} {tohum.baslik}".strip() if tohum.kaynak != 'spotify'
                                         else tohum.baslik, adet=1)
                vid = adaylar[0].get('id') if adaylar else ""
            except (IsciHatasi, asyncio.TimeoutError) as e:
                logger.warning(f"Radyo tohum araması başarısız: {hata_sebebi(e).sebep}")
        if not vid:
            return []
        secenekler = dict(ydl_playlist_opts)
        secenekler['playlistend'] = 30   # Mix listeleri yüzlerce/binlerce parça döndürebilir
        bilgi = await self._ytdl(secenekler, f"https://www.youtube.com/watch?v={vid}&list=RD{vid}",
                                 PLAYLIST_ZAMAN_ASIMI, mod="flat")
        haric_idler = set(haric_idler) | {vid}
        sonuc = []
        for entry in (bilgi or {}).get('entries') or []:
            if not entry or entry.get('id') in haric_idler:
                continue
            baslik = normallestir(entry.get('title'))
            if not baslik or baslik in _GECERSIZ_BASLIKLAR or baslik in haric_basliklar:
                continue
            sure = entry.get('duration') or 0
            if sure and not 60 <= sure <= 900:   # kısa/uzun (derleme) videoları atla
                continue
            sonuc.append(flat_entry_parca(entry, otomatik=True))
            if len(sonuc) >= adet:
                break
        return sonuc

    # ── Spotify ──
    async def kisa_link_coz(self, url):
        """spotify.link / spoti.fi → open.spotify.com/... (yönlendirme ya da sayfa içindeki link)."""
        oturum = await self._http()
        try:
            async with oturum.get(url, allow_redirects=True) as yanit:
                son_url = str(yanit.url)
                if SPOTIFY_REGEX.search(son_url):
                    return son_url
                html = await yanit.text()
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            logger.warning(f"Spotify kısa link çözülemedi: {e}")
            return None
        m = re.search(r'https://open\.spotify\.com/(?:intl-[a-z-]+/)?(?:track|album|playlist|artist)/[A-Za-z0-9]{10,30}', html)
        return m.group(0) if m else None

    async def spotify(self, tur, sp_id, limit=500):
        """Spotify track/album/playlist → (baslik, [Parca]). Önce Web API (client credentials),
        başarısızsa (anahtar yok / 403 'premium şartı' / 429) herkese açık embed sayfası."""
        if tur == 'artist':
            raise CozmeHatasi(_t("Spotify sanatçı linkleri desteklenmiyor — şarkı, albüm ya da playlist linki gönder."))
        if self.spotify_aktif and time.time() >= self._sp_kapali_bitis:
            try:
                async with self._sem:
                    sonuc = await self.havuz.calistir("spotify_api", 45, tur=tur, sp_id=sp_id, limit=limit)
                parcalar = [_spotify_parca_olustur(t.get('name') or "", ", ".join(t.get('artists') or []),
                                                   (t.get('duration_ms') or 0) / 1000, t.get('id') or "")
                            for t in sonuc.get('parcalar') or [] if t.get('name')]
                if parcalar:
                    return sonuc.get('baslik') or "Spotify", parcalar
            except (IsciHatasi, asyncio.TimeoutError) as e:
                durum = getattr(e, 'http_status', None)
                if durum in (401, 403, 429):
                    # 403 "Active premium subscription required for the owner of the app" kalıcıdır:
                    # her saat yeniden denemek yerine bu oturumda API bırakılır (embed sayfası sorunsuz çalışıyor).
                    kalici = durum == 403 and "premium" in str(e).casefold()
                    self._sp_kapali_bitis = float("inf") if kalici else time.time() + 3600
                    if kalici:
                        logger.warning("Spotify API: uygulama sahibinin Spotify Premium üyeliği yok (403) — bu oturumda "
                                       "API kullanılmayacak; Spotify linkleri herkese açık embed sayfasından çözülür.")
                    else:
                        logger.warning(f"Spotify API {durum} döndü — 1 saat embed sayfasına geçiliyor. ({str(e)[:140]})")
                else:
                    logger.warning(f"Spotify API hatası, embed'e geçiliyor: {str(e)[:160]}")
        try:
            async with self._sem:
                varlik = await self.havuz.calistir("spotify_embed", 60, tur=tur, sp_id=sp_id)
        except (IsciHatasi, asyncio.TimeoutError) as e:
            logger.warning(f"Spotify embed çözülemedi ({tur}/{sp_id}): {e}")
            return None, []
        return spotify_embed_coz(varlik, limit)


def _temiz(metin):
    return " ".join(str(metin or "").replace("\xa0", " ").split())


def _spotify_parca_olustur(ad, sanatci, sure, sp_id):
    ad, sanatci = _temiz(ad), _temiz(sanatci)
    tam = f"{sanatci} - {ad}" if sanatci else ad
    return Parca(
        sorgu=f"ytsearch5:{tam}",
        baslik=tam,
        url=f"https://open.spotify.com/track/{sp_id}" if sp_id else "",
        sure=int(sure or 0),
        kaynak='spotify',
        sanatci=sanatci,
        beklenen_sure=int(sure or 0),
        arama_metni=tam,
    )


def spotify_embed_coz(varlik, limit=500):
    """Embed sayfasındaki (kırpılmış) `entity` → (baslik, [Parca]). Saf fonksiyon — test edilebilir."""
    baslik = _temiz(varlik.get('name') or varlik.get('title') or 'Spotify')
    parcalar = []
    if varlik.get('type') == 'track' and not varlik.get('trackList'):
        sanatci = ", ".join(_temiz(a.get('name')) for a in varlik.get('artists') or [] if a.get('name'))
        ad = _temiz(varlik.get('title') or varlik.get('name'))
        if ad:
            parcalar.append(_spotify_parca_olustur(ad, sanatci, (varlik.get('duration') or 0) / 1000,
                                                   varlik.get('id') or ""))
        return baslik, parcalar
    for t in varlik.get('trackList') or []:
        if not isinstance(t, dict) or not t.get('title'):
            continue
        uri = t.get('uri') or ""
        sp_id = uri.rsplit(':', 1)[-1] if uri.startswith('spotify:track:') else ""
        parcalar.append(_spotify_parca_olustur(t['title'], t.get('subtitle'), (t.get('duration') or 0) / 1000, sp_id))
        if len(parcalar) >= limit:
            break
    return baslik, parcalar


def sayfa_url_temizle(url):
    """Paylaşım linklerindeki izleme parametrelerini (si=, feature=) at — log/gösterim için."""
    try:
        p = urllib.parse.urlparse(url)
        q = [(k, v) for k, v in urllib.parse.parse_qsl(p.query) if k not in ('si', 'feature', 'pp')]
        return urllib.parse.urlunparse(p._replace(query=urllib.parse.urlencode(q)))
    except ValueError:
        return url
