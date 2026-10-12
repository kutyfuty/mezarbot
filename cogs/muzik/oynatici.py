"""
Sunucu başına bağımsız oynatıcı (Oynatici).

Ses zinciri (Python'da ses işleme YOK — takılmayı önlemek için her şey FFmpeg'de):
  yt-dlp akış URL'si → FFmpeg ─┬─ Opus doğrudan aktarım (-c:a copy): kaynak Opus + filtre yok + ses %100
                               └─ -af "filtreler,volume=X" → libopus (160 kbps, 20 ms, application=audio)
  → discord.FFmpegOpusAudio → OnbellekliKaynak (okuma-önü tampon thread'i, ~10 sn) → discord.py ses thread'i

  OnbellekliKaynak:
   - FFmpeg'den ayrı bir thread'de okur; discord.py'nin 20 ms'lik döngüsü hazır paketi anında alır.
   - Oynatma, tampon ön-doldurulduktan SONRA başlar (şarkı başında takılma yok).
   - Ağ takılırsa sessizlik paketi gönderir (discord.py "yetişmek için" paket patlatmaz); 8 sn'yi aşarsa
     akış biter ve kaldığı yerden yeniden bağlanılır.
   - Gönderilen gerçek paketleri sayar → duraklatma/sarma/hız filtrelerinden etkilenmeyen DOĞRU konum.

Geçişler:
  - Sarma / filtre / ses değişiminde YENİ akış arka planda hazırlanır, tampon dolunca eskisiyle değiştirilir.
  - Sıradaki parça önceden çözülür ve bitmeden ~12 sn önce FFmpeg'i ısıtılır → neredeyse boşluksuz geçiş.
  - "nesil" sayacı: eski akışın after-callback'i yok sayılır (yarış yok).
  - Akış erken biterse / FFmpeg hata verirse: URL yenilenir, KALDIĞI YERDEN devam (en fazla 3 deneme).
  - Kısıtlı/silinmiş videolar mesajla atlanır; üst üste çok hata olursa durur (sonsuz döngü yok).
"""
import asyncio
import logging
import queue
import shlex
import threading
import time

import discord

from arayuz import FFMPEG_YOLU
from .filtreler import FiltreDurumu
from .kaynaklar import CozmeHatasi, YT_ISTEMCI_YEDEKLERI, hata_sebebi
from .kuyruk import DONGU_KAPALI, DONGU_SARKI, Gecmis, Kuyruk, VARSAYILAN_KUYRUK_LIMITI
from dil import _t, dilli_gorev

logger = logging.getLogger('MezarBot.Muzik.Oynatici')

KARE_SURESI = 0.02            # Opus paketi = 20 ms
OPUS_BIT_HIZI = 160           # kbps (libopus kodlamada)
OPUS_SESSIZLIK = b'\xf8\xff\xfe'
ON_TAMPON_KARE = 15           # oynatmaya başlamadan önce hazır olması gereken paket (300 ms)
TAMPON_KAPASITE = 500         # okuma-önü tampon (10 sn)
TAKILMA_SINIRI = 8.0          # bu kadar sn veri gelmezse akışı bitir → kaldığı yerden yeniden bağlan
HAZIRLIK_ZAMAN_ASIMI = 12.0   # FFmpeg ilk paketleri bu sürede üretmezse başarısız say
ISITMA_ONCESI = 12.0          # sıradaki parçanın FFmpeg'i bu kadar sn önce ısıtılır
SES_GECIKMESI = 0.7           # ses butonuna art arda basılınca tek yeniden başlatma
YENIDEN_DENEME_LIMITI = 3
ARDISIK_HATA_LIMITI = 8
OTOMATIK_EKLEME = 3

_RECONNECT = "-reconnect 1 -reconnect_streamed 1 -reconnect_on_network_error 1 -reconnect_delay_max 5"
_KODLAYICI = "-application audio -frame_duration 20 -vbr on -compression_level 10"


class HataTamponu:
    """FFmpeg stderr'inin son 4 KB'si. discord.py'nin okuyucu thread'i write() çağırır (dosya/geçici dosya yok)."""

    def __init__(self, limit=4096):
        self._veri = bytearray()
        self._limit = limit
        self._kilit = threading.Lock()

    def write(self, veri):
        with self._kilit:
            self._veri += veri
            if len(self._veri) > self._limit:
                del self._veri[:-self._limit]
        return len(veri)

    def flush(self):
        pass

    def metin(self):
        with self._kilit:
            return bytes(self._veri).decode(errors='ignore').strip()


def ffmpeg_argumanlari(akis_url, basliklar, konum, af_zinciri, kopya, canli=False):
    """(before_options, options) — discord.FFmpegOpusAudio için. Saf fonksiyon (test edilebilir).
    discord.py kendisi şunları ekler: -map_metadata -1 -f opus -c:a <copy|libopus> -ar 48000 -ac 2
    -b:a <bitrate>k -loglevel warning -fec true -packet_loss 15 -blocksize 8192."""
    once = ["-nostdin"]
    if konum and konum > 0.5 and not canli:
        once.append(f"-ss {konum:.2f}")
    if akis_url.startswith(("http://", "https://")):
        once.append(_RECONNECT)
        once.append("-rw_timeout 15000000")   # 15 sn veri gelmezse bağlantıyı yenile
    once.append("-thread_queue_size 1024 -probesize 256K -analyzeduration 1000000 -fflags +discardcorrupt")
    if basliklar:
        baslik_metni = "".join(f"{k}: {v}\r\n" for k, v in basliklar.items() if k and v)
        once.append(f"-headers {shlex.quote(baslik_metni)}")
    sonra = ["-vn", "-sn", "-dn", "-loglevel error"]
    if not kopya:
        if af_zinciri:
            sonra.append(f"-af {shlex.quote(af_zinciri)}")
        sonra.append(_KODLAYICI)
    return " ".join(once), " ".join(sonra)


def opus_kaynagi_olustur(akis_url, basliklar, konum, af_zinciri, kopya, canli, tampon):
    once, sonra = ffmpeg_argumanlari(akis_url, basliklar, konum, af_zinciri, kopya, canli)
    # DİKKAT: discord.py 2.7.1 player.py → codec in ('opus', 'libopus', 'copy') ise '-c:a copy' seçer!
    # ('libopus' = "kaynak zaten libopus" anlamında). Kodlama için başka bir değer (None) verilmeli.
    return discord.FFmpegOpusAudio(akis_url, executable=FFMPEG_YOLU, bitrate=OPUS_BIT_HIZI,
                                   codec='copy' if kopya else None,
                                   before_options=once, options=sonra, stderr=tampon)


class OnbellekliKaynak(discord.AudioSource):
    """FFmpegOpusAudio'yu okuma-önü tampon thread'iyle sarar; paketleri sayar (konum)."""

    def __init__(self, ic, kopya, baslangic, hiz, tampon, kapasite=TAMPON_KAPASITE):
        self._ic = ic
        self.kopya = kopya
        self.baslangic = float(baslangic or 0)
        self.hiz = float(hiz or 1.0)
        self.tampon = tampon
        self.kareler = 0
        self.okunan = 0          # FFmpeg'den okunan paket sayısı (üretilen ses; çalınandan önde olabilir)
        self.ffmpeg_kodu = None  # akış bitince FFmpeg çıkış kodu (0 = doğal son; ≠0 = öldü/hata)
        self.sessizlik = 0
        self.okuma_hatasi = None
        self._kuyruk = queue.Queue(maxsize=kapasite)
        self._dur = threading.Event()
        self._bitti = threading.Event()
        self._takilma_basi = None
        self._thread = threading.Thread(target=self._oku, daemon=True, name="muzik-tampon")
        self._thread.start()

    def _oku(self):
        try:
            while not self._dur.is_set():
                paket = self._ic.read()
                if not paket:
                    break
                self.okunan += 1
                while not self._dur.is_set():
                    try:
                        self._kuyruk.put(paket, timeout=0.25)
                        break
                    except queue.Full:
                        continue
        except Exception as e:  # kapatılan pipe (ValueError/OSError) vb. — akış sonu olarak ele alınır
            self.okuma_hatasi = e
        finally:
            # Çıkış kodu: stdout EOF'tan hemen sonra süreç henüz kapanmamış olabilir → kısa süre bekle.
            surec = getattr(self._ic, "_process", None)
            if surec is not None:
                son = time.monotonic() + 1.0
                while self.ffmpeg_kodu is None and time.monotonic() < son and not self._dur.is_set():
                    self.ffmpeg_kodu = surec.poll()
                    if self.ffmpeg_kodu is None:
                        time.sleep(0.02)
            self._bitti.set()

    def hazir_paket(self):
        return self._kuyruk.qsize()

    def bitti_mi(self):
        return self._bitti.is_set() and self._kuyruk.empty()

    async def hazir_bekle(self, n=ON_TAMPON_KARE, zaman_asimi=HAZIRLIK_ZAMAN_ASIMI):
        """Tamponda n paket birikene (ya da akış bitene) kadar bekler. En az 1 paket varsa True."""
        son = time.monotonic() + zaman_asimi
        while time.monotonic() < son:
            if self._kuyruk.qsize() >= n or self._bitti.is_set():
                break
            await asyncio.sleep(0.02)
        return self._kuyruk.qsize() > 0

    def read(self):
        try:
            paket = self._kuyruk.get(timeout=0.015)
        except queue.Empty:
            if self._bitti.is_set():
                return b''
            simdi = time.monotonic()
            if self._takilma_basi is None:
                self._takilma_basi = simdi
            elif simdi - self._takilma_basi > TAKILMA_SINIRI:
                return b''   # uzun takılma → bitir; Oynatici kaldığı yerden yeniden bağlanır
            self.sessizlik += 1
            return OPUS_SESSIZLIK
        self._takilma_basi = None
        self.kareler += 1
        return paket

    def is_opus(self):
        return True

    def cleanup(self):
        self._dur.set()
        try:
            self._ic.cleanup()   # FFmpeg: kill + wait (zombi yok)
        finally:
            if self._thread.is_alive() and threading.current_thread() is not self._thread:
                self._thread.join(timeout=2)
            while not self._kuyruk.empty():
                try:
                    self._kuyruk.get_nowait()
                except queue.Empty:
                    break

    @property
    def konum(self):
        return self.baslangic + self.kareler * KARE_SURESI * self.hiz

    @property
    def uretilen_konum(self):
        """FFmpeg'in ürettiği sesin ulaştığı konum (tampon + boru dahil; çalınan konumdan ileride olabilir)."""
        return self.baslangic + self.okunan * KARE_SURESI * self.hiz

    @property
    def ffmpeg_kirildi(self):
        """FFmpeg hata/sinyalle bittiyse True (doğal sonda çıkış kodu 0)."""
        return self.ffmpeg_kodu not in (None, 0)


class Oynatici:
    """Bir sunucunun tüm müzik durumu. Cog `oynaticilar[guild_id]` sözlüğünde tutar."""

    def __init__(self, cog, guild_id, ayar, kuyruk_limiti=VARSAYILAN_KUYRUK_LIMITI):
        self.cog = cog
        self.bot = cog.bot
        self.guild_id = guild_id
        self.kuyruk = Kuyruk(kuyruk_limiti)
        self.gecmis = Gecmis()
        self.simdiki = None
        self.kaynak = None
        son_ses = ayar.get('son_ses')
        self.ses = int(son_ses if son_ses is not None else ayar.get('varsayilan_ses', 100))
        self.filtre = FiltreDurumu(normalizasyon=bool(ayar.get('normalizasyon')))
        self.dongu = DONGU_KAPALI
        self.otomatik = bool(ayar.get('otomatik_oynatma'))
        self.metin_kanal_id = None
        self.nesil = 0
        self.oylar = set()
        self.son_aktivite = time.monotonic()
        self.yalniz_baslangic = None
        self.otomatik_duraklatildi = False
        self.baslama_zamani = 0.0
        self.kapandi = False
        self._niyet = None
        self._deneme = 0
        self._kilit = asyncio.Lock()
        self._otomatik_kilit = asyncio.Lock()   # arka plan + sonrakine_gec aynı anda doldurmasın (çift ekleme)
        self._on_cozme = None          # (parca, task)
        self._isitilmis = None          # (parca, kaynak, imza)
        self._isitma_gorevi = None
        self._ses_gorevi = None
        self._gorevler = set()

    # ── Durum ──
    @property
    def guild(self):
        return self.bot.get_guild(self.guild_id)

    @property
    def vc(self):
        g = self.guild
        return g.voice_client if g else None

    def bagli_mi(self):
        vc = self.vc
        return bool(vc and vc.is_connected())

    def caliyor_mu(self):
        vc = self.vc
        return bool(vc and (vc.is_playing() or vc.is_paused()))

    def duraklatildi_mi(self):
        vc = self.vc
        return bool(vc and vc.is_paused())

    def mesgul_mu(self):
        return self._kilit.locked()

    def konum(self):
        if not self.kaynak:
            return 0.0
        k = self.kaynak.konum
        return min(k, self.simdiki.sure) if (self.simdiki and self.simdiki.sure) else k

    def dogrudan_aktarim_mi(self):
        return bool(self.kaynak and self.kaynak.kopya)

    def _af(self):
        zincir = self.filtre.af_zinciri()
        if self.ses != 100:
            ses = f"volume={self.ses / 100:.2f}"
            zincir = f"{zincir},{ses}" if zincir else ses
        return zincir

    def _kopya_mi(self, parca):
        return parca.akis_codec == 'opus' and self.ses == 100 and not self.filtre.islem_gerekli_mi()

    def _imza(self, parca):
        return (parca.akis_url, self._kopya_mi(parca), self._af())

    def gorev(self, coro, ad=None):
        """Arka plan görevi — referansı tutulur (GC'ye gitmesin), kapanışta iptal edilir."""
        t = dilli_gorev(coro, self.guild_id, name=ad)   # mesajlar sunucunun dilinde
        self._gorevler.add(t)
        t.add_done_callback(self._gorev_bitti)
        return t

    def _gorev_bitti(self, t):
        self._gorevler.discard(t)
        if not t.cancelled() and t.exception():
            logger.error(f"[{self.guild_id}] arka plan görevi hatası: {t.exception()!r}", exc_info=t.exception())

    # ── Kaynak oluşturma ──
    def _kaynak_olustur(self, parca, konum):
        kopya = self._kopya_mi(parca)
        tampon = HataTamponu()
        ic = opus_kaynagi_olustur(parca.akis_url, parca.akis_basliklari, konum, self._af(), kopya, parca.canli, tampon)
        return OnbellekliKaynak(ic, kopya, konum, self.filtre.hiz_carpani(), tampon)

    async def _cal(self, parca, konum):
        """Yeni akışı hazırlar (tampon dolana kadar eski akış çalmaya devam eder), sonra değiştirir."""
        if not self.bagli_mi():
            return False
        kaynak = None
        isitilmis = self._isitilmis
        if isitilmis and isitilmis[0] is parca and konum < 0.5 and isitilmis[2] == self._imza(parca) \
                and not isitilmis[1].bitti_mi():
            kaynak = isitilmis[1]
            self._isitilmis = None
            logger.info(f"[{self.guild_id}] Isıtılmış akış kullanılıyor ({kaynak.hazir_paket()} paket hazır)")
        else:
            if isitilmis and isitilmis[0] is parca:
                self._isitilmis_iptal()
            try:
                kaynak = self._kaynak_olustur(parca, konum)
            except discord.ClientException as e:
                logger.error(f"[{self.guild_id}] FFmpeg başlatılamadı: {e}")
                return False
            if not await kaynak.hazir_bekle():
                logger.warning(f"[{self.guild_id}] FFmpeg veri üretmedi: {kaynak.tampon.metin()[-300:]}")
                kaynak.cleanup()
                return False
        vc = self.vc
        if self.kapandi or not vc or not vc.is_connected():
            kaynak.cleanup()
            return False
        self.nesil += 1
        nesil = self.nesil
        self._niyet = None
        if vc.is_playing() or vc.is_paused():
            vc.stop()   # eski nesil → after-callback'i yok sayılır
        try:
            vc.play(kaynak, after=lambda hata, n=nesil: self._bitti_cb(n, hata))
        except (discord.ClientException, TypeError, OSError) as e:
            logger.error(f"[{self.guild_id}] vc.play hatası: {e}")
            kaynak.cleanup()
            return False
        yeni = parca is not self.simdiki
        self.kaynak = kaynak
        self.simdiki = parca
        self.son_aktivite = time.monotonic()
        if yeni:
            self.baslama_zamani = time.time()
        ozet = self.filtre.ozet()
        logger.info(f"[{self.guild_id}] ▶ {parca.gosterim(70)} @ {konum:.0f}s "
                    f"({'Opus aktarım' if kaynak.kopya else f'libopus {OPUS_BIT_HIZI}k'}, ses %{self.ses}"
                    f"{', ' + ', '.join(ozet) if ozet else ''})")
        self._isitma_planla()
        return True

    async def _cal_dayanikli(self, parca, konum):
        """_cal başarısızsa (ör. URL 403) akış URL'sini yenileyip bir kez daha dener; YouTube yeni URL'yi de
        reddederse son olarak yedek istemcinin (web_embedded) URL'siyle dener."""
        if await self._cal(parca, konum):
            return True
        for istemci in (None, YT_ISTEMCI_YEDEKLERI[0]):
            if self.kapandi or not self.bagli_mi():
                return False
            if istemci and "googlevideo.com" not in (parca.akis_url or ""):
                return False   # YouTube dışı kaynak: yedek istemci anlamsız
            try:
                await self.cog.cozucu.coz(parca, zorla=True, istemci=istemci)
            except CozmeHatasi:
                return False
            if await self._cal(parca, konum):
                if istemci:
                    logger.info(f"[{self.guild_id}] 403 sonrası '{istemci}' istemcisiyle kurtarıldı: {parca.gosterim(50)}")
                return True
        return False

    def _bitti_cb(self, nesil, hata):
        """discord.py ses thread'inden çağrılır → olay döngüsüne aktar."""
        try:
            asyncio.run_coroutine_threadsafe(self._bitti(nesil, hata), self.bot.loop)
        except RuntimeError:
            pass  # döngü kapanıyor

    # ── Ana akış ──
    async def baslat_bossa(self):
        """Çalan bir şey yoksa sıradakini başlatır."""
        if not self.caliyor_mu() and self.simdiki is None and not self.mesgul_mu():
            await self.sonrakine_gec()

    async def sonrakine_gec(self, biten=None, atlandi=False, onceki_modu=False):
        async with self._kilit:
            if self.kapandi:
                return
            if biten is not None and not onceki_modu:
                self.gecmis.ekle(biten)
            self.oylar.clear()
            self._deneme = 0
            parca = self.kuyruk.al() if onceki_modu else self.kuyruk.sonraki(biten, self.dongu, atlandi)
            ardisik_hata = 0
            while not self.kapandi:
                if parca is None and self.otomatik:
                    if await self._otomatik_doldur(biten or self.simdiki):
                        parca = self.kuyruk.al()
                if parca is None:
                    self._bosa_gec()
                    await self.cog.panel_guncelle(self.guild_id)
                    return
                try:
                    await self._on_cozme_bekle(parca)
                    await self.cog.cozucu.coz(parca)
                except CozmeHatasi as h:
                    ardisik_hata += 1
                    await self.cog.bildir(self.guild_id, _t("⚠️ **{gosterim}** atlandı: {sebep}", gosterim=parca.gosterim(60), sebep=_t(h.sebep)))
                    if ardisik_hata >= ARDISIK_HATA_LIMITI:
                        await self.cog.bildir(self.guild_id, _t("❌ Üst üste çok fazla parça çözülemedi, oynatma durduruldu."))
                        self._bosa_gec()
                        await self.cog.panel_guncelle(self.guild_id)
                        return
                    parca = self.kuyruk.al()
                    continue
                if await self._cal_dayanikli(parca, 0.0):
                    break
                if not self.bagli_mi():
                    self._bosa_gec()
                    return
                ardisik_hata += 1
                await self.cog.bildir(self.guild_id, _t("⚠️ **{gosterim}** akışı başlatılamadı, atlanıyor.", gosterim=parca.gosterim(60)))
                parca = self.kuyruk.al()
            await self.cog.panel_guncelle(self.guild_id)
            self._on_coz_baslat()

    def _bosa_gec(self):
        vc = self.vc
        if vc and (vc.is_playing() or vc.is_paused()):
            self.nesil += 1
            vc.stop()
        self.simdiki = None
        self.kaynak = None
        self.son_aktivite = time.monotonic()
        self._isitilmis_iptal()

    async def _bitti(self, nesil, hata):
        if nesil != self.nesil or self.kapandi:
            return
        parca, kaynak = self.simdiki, self.kaynak
        niyet, self._niyet = self._niyet, None
        if niyet == 'durdur' or parca is None:
            return
        if not self.bagli_mi():
            return   # ses bağlantısı koptu — cog yeniden bağlanıp kaldığı yerden devam ettirir
        if niyet == 'atla':
            return await self.sonrakine_gec(biten=parca, atlandi=True)

        konum = kaynak.konum if kaynak else 0.0
        stderr = kaynak.tampon.metin() if kaynak else ""
        # Erken kopma: çalınan konuma değil FFmpeg'e bakılır — tampon/boru dolu olduğu için akış
        # sürenin son saniyelerinde "bitmiş" görünebilir. FFmpeg hatayla bittiyse ya da ürettiği ses
        # sürenin gerisinde kaldıysa kopmadır; kaldığı (çalınan) yerden devam edilir.
        # - Üretilen ses sona (son 2 sn) ulaştıysa: doğal son (FFmpeg sonradan öldürülmüş olsa bile).
        # - FFmpeg öldü/hata verdi ve ses sona ulaşmadı: kopma.
        # - FFmpeg 0 ile çıktı ama ses sürenin >5 sn gerisinde: kopma (ağ kopunca FFmpeg sessizce 0 ile çıkar).
        uretilen = kaynak.uretilen_konum if kaynak else 0.0
        if not parca.sure or parca.canli or kaynak is None or uretilen >= parca.sure - 2:
            erken = False
        elif kaynak.ffmpeg_kirildi:
            erken = True
        else:
            erken = uretilen < parca.sure - 5
        bos = kaynak is not None and kaynak.kareler == 0
        if (hata or erken or bos) and self._deneme < YENIDEN_DENEME_LIMITI:
            self._deneme += 1
            logger.warning(f"[{self.guild_id}] Akış kesildi ({konum:.0f}/{parca.sure}s, hata={hata!r}, "
                           f"okuma={getattr(kaynak, 'okuma_hatasi', None)!r}) deneme {self._deneme}/{YENIDEN_DENEME_LIMITI}: "
                           f"{stderr[-300:]}")
            await asyncio.sleep(self._deneme)
            if nesil != self.nesil or self.kapandi:
                return
            try:
                async with self._kilit:
                    await self.cog.cozucu.coz(parca, zorla=True)   # URL süresi dolmuş/403 olabilir → yenile
                    if await self._cal(parca, konum):
                        await self.cog.panel_guncelle(self.guild_id)
                        return
            except CozmeHatasi as h:
                await self.cog.bildir(self.guild_id, _t("⚠️ **{gosterim}** yeniden bağlanamadı: {sebep}", gosterim=parca.gosterim(60), sebep=_t(h.sebep)))
        elif erken:
            await self.cog.bildir(self.guild_id, _t("⚠️ **{gosterim}** akışı koptu, sıradakine geçiliyor.", gosterim=parca.gosterim(60)))
        await self.sonrakine_gec(biten=parca)

    # ── Ön çözme, ısıtma, otomatik oynatma ──
    def _siradaki_tahmini(self):
        if self.dongu == DONGU_SARKI:
            return self.simdiki
        return self.kuyruk.ilk()

    def _on_coz_baslat(self):
        eski = self._on_cozme
        sonraki = self.kuyruk.ilk()
        if eski and not eski[1].done() and eski[0] is not sonraki:
            eski[1].cancel()
        if self.dongu == DONGU_SARKI:
            return
        if sonraki is None:
            if self.otomatik and self.simdiki:
                self.gorev(self._otomatik_arkaplan(), ad=f"muzik-otomatik-{self.guild_id}")
            return
        if eski and eski[0] is sonraki and not eski[1].done():
            return
        self._on_cozme = (sonraki, self.gorev(self._on_coz(sonraki), ad=f"muzik-oncoz-{self.guild_id}"))

    async def _on_coz(self, parca):
        try:
            await self.cog.cozucu.coz(parca)
            logger.info(f"[{self.guild_id}] Ön çözme hazır: {parca.gosterim(50)}")
            await self.cog.panel_guncelle(self.guild_id)
        except CozmeHatasi as h:
            logger.info(f"[{self.guild_id}] Ön çözme başarısız ({h.sebep}): {parca.gosterim(50)}")

    async def _on_cozme_bekle(self, parca):
        eski = self._on_cozme
        if eski and eski[0] is parca and not eski[1].done():
            try:
                await asyncio.wait_for(asyncio.shield(eski[1]), timeout=35)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                pass

    def _isitma_planla(self):
        if self._isitma_gorevi and not self._isitma_gorevi.done():
            self._isitma_gorevi.cancel()
        p = self.simdiki
        if not p or not p.sure or p.canli or not self.kaynak:
            return
        kalan = max(0.0, (p.sure - self.konum()) / max(0.25, self.kaynak.hiz))
        self._isitma_gorevi = self.gorev(self._isit(max(0.0, kalan - ISITMA_ONCESI), self.nesil),
                                         ad=f"muzik-isitma-{self.guild_id}")

    async def _isit(self, bekle, nesil):
        await asyncio.sleep(bekle)
        if nesil != self.nesil or self.kapandi:
            return
        hedef = self._siradaki_tahmini()
        if hedef is None:
            return
        self._isitilmis_iptal()
        try:
            await self._on_cozme_bekle(hedef)
            kalan_pay = (hedef.sure or 0) + ISITMA_ONCESI + 120
            if not hedef.akis_gecerli_mi(pay=kalan_pay):
                await self.cog.cozucu.coz(hedef, zorla=bool(hedef.akis_url))
            if nesil != self.nesil or self.kapandi or hedef is not self._siradaki_tahmini():
                return
            kaynak = self._kaynak_olustur(hedef, 0.0)
        except (CozmeHatasi, discord.ClientException) as e:
            logger.info(f"[{self.guild_id}] Isıtma atlandı: {e}")
            return
        if await kaynak.hazir_bekle(n=50) and nesil == self.nesil and not self.kapandi:
            self._isitilmis = (hedef, kaynak, self._imza(hedef))
            logger.info(f"[{self.guild_id}] Sıradaki akış ısıtıldı: {hedef.gosterim(50)}")
        else:
            kaynak.cleanup()

    def _isitilmis_iptal(self):
        isitilmis, self._isitilmis = self._isitilmis, None
        if isitilmis:
            isitilmis[1].cleanup()

    async def _otomatik_arkaplan(self):
        if self.kuyruk.bos_mu() and await self._otomatik_doldur(self.simdiki):
            await self.cog.panel_guncelle(self.guild_id)
            self._on_coz_baslat()
            self._isitma_planla()

    async def _otomatik_doldur(self, tohum):
        """Kuyruk bittiğinde benzer parçaları ekler (YouTube Mix). Eklenen sayısını döner
        (başka bir doldurma bu sırada kuyruğu doldurduysa kuyruktaki parça sayısını)."""
        async with self._otomatik_kilit:
            if not self.kuyruk.bos_mu():
                return len(self.kuyruk)
            return await self._otomatik_doldur_kilitli(tohum)

    def _haric_idler(self):
        haric = self.gecmis.video_idleri() | {p.video_id for p in self.kuyruk if p.video_id}
        if self.simdiki and self.simdiki.video_id:
            haric.add(self.simdiki.video_id)
        return haric

    async def _otomatik_doldur_kilitli(self, tohum):
        tohum = tohum or (self.gecmis.son(1) or [None])[0]
        if tohum is None:
            return 0
        try:
            yeniler = await self.cog.cozucu.radyo(tohum, self._haric_idler(), self.gecmis.basliklar(), adet=OTOMATIK_EKLEME)
        except Exception as e:  # işçi / yt-dlp / ağ hataları: otomatik oynatma sessizce durur
            logger.warning(f"[{self.guild_id}] Otomatik oynatma önerisi alınamadı: {hata_sebebi(e).sebep}")
            return 0
        haric = self._haric_idler()   # beklerken çalan/kuyruk değişmiş olabilir
        yeniler = [p for p in yeniler if not p.video_id or p.video_id not in haric]
        me = self.guild.me if self.guild else None
        for p in yeniler:
            p.isteyen_id = me.id if me else 0
            p.isteyen_ad = _t("Otomatik Oynatma")
            p.isteyen_avatar = str(me.display_avatar.url) if me else ""
        eklenen = self.kuyruk.toplu_ekle(yeniler)
        if eklenen:
            logger.info(f"[{self.guild_id}] 📻 Otomatik oynatma {eklenen} parça ekledi (tohum: {tohum.gosterim(40)})")
        return eklenen

    # ── Kontroller ──
    async def atla(self):
        """→ 'ok' | 'bos' | 'mesgul'. Sıradaki hazırsa (çözülmüş/ısıtılmış) kesintisiz geçer."""
        if self.simdiki is None or not self.caliyor_mu():
            return 'bos'
        if self.mesgul_mu():
            return 'mesgul'
        await self._gecis(atlandi=True)
        return 'ok'

    async def onceki(self):
        """Geçmişteki son parçaya döner (çalan parça sıranın başına geri konur). Başarılıysa parça."""
        if self.mesgul_mu():
            return 'mesgul'
        onceki = self.gecmis.geri_al()
        if onceki is None:
            return None
        if self.simdiki is not None:
            self.kuyruk.basa_ekle(self.simdiki, zorla=True)
        self.kuyruk.basa_ekle(onceki, zorla=True)
        await self._gecis(onceki_modu=True)
        return onceki

    async def _gecis(self, atlandi=False, onceki_modu=False):
        """Kullanıcı kaynaklı geçiş: sıradaki hazırsa eski akış yenisi hazır olana dek çalar; değilse hemen susar."""
        hedef = self.kuyruk.ilk()
        hazir = hedef is not None and ((self._isitilmis and self._isitilmis[0] is hedef) or hedef.akis_gecerli_mi())
        self.nesil += 1   # eski akışın bitişi yok sayılır
        vc = self.vc
        if not hazir and vc and (vc.is_playing() or vc.is_paused()):
            vc.stop()
        biten = self.simdiki
        self.gorev(self.sonrakine_gec(biten=biten, atlandi=atlandi, onceki_modu=onceki_modu),
                   ad=f"muzik-gecis-{self.guild_id}")

    def durdur(self):
        """Kuyruğu temizler ve çalmayı durdurur (kanalda kalır)."""
        self.kuyruk.temizle()
        if self.simdiki is not None:
            self.gecmis.ekle(self.simdiki)
        self._niyet = 'durdur'
        self._on_cozme_iptal()
        self._bosa_gec()

    async def yeniden_baslat(self, konum=None):
        """Aynı parçayı verilen (ya da mevcut) konumdan yeniden başlatır: sarma, filtre, ses değişimi.
        Yeni akış hazır olana dek eskisi çalmaya devam eder."""
        async with self._kilit:
            parca = self.simdiki
            vc = self.vc
            if parca is None or not vc or not vc.is_connected():
                return False
            konum = self.konum() if konum is None else konum
            duraklatilmisti = vc.is_paused()
            eski_nesil = self.nesil
            self.nesil += 1   # hazırlık sırasında eski akış biterse sonrakine geçilmesin
            kalan = (parca.sure - konum) if parca.sure else 0
            try:
                if not parca.akis_gecerli_mi(pay=kalan + 60):
                    await self.cog.cozucu.coz(parca, zorla=True)
            except CozmeHatasi as h:
                self.nesil = eski_nesil
                await self.cog.bildir(self.guild_id, _t("⚠️ Akış yenilenemedi: {sebep}", sebep=_t(h.sebep)))
                return False
            if not await self._cal_dayanikli(parca, konum):
                if self.caliyor_mu():
                    self.nesil = eski_nesil   # eski akış hâlâ çalıyor → normal akışına devam
                return False
            if duraklatilmisti:
                vc.pause()
            return True

    def ses_ayarla(self, deger):
        """Sesi ayarlar; çalıyorsa kısa bir gecikmeyle (art arda basmalar birleşir) akışı konumdan yeniler."""
        deger = int(deger)
        degisti = deger != self.ses
        self.ses = deger
        if not degisti or self.simdiki is None:
            return
        if self._ses_gorevi and not self._ses_gorevi.done():
            self._ses_gorevi.cancel()
        self._ses_gorevi = self.gorev(self._ses_uygula(), ad=f"muzik-ses-{self.guild_id}")

    async def _ses_uygula(self):
        await asyncio.sleep(SES_GECIKMESI)
        if self.kaynak is not None and self.kaynak.kopya == self._kopya_mi(self.simdiki) and self.kaynak.kopya:
            return   # hâlâ doğrudan aktarım uygun (ses %100'e döndü) → yeniden başlatmaya gerek yok
        await self.yeniden_baslat()
        await self.cog.panel_guncelle(self.guild_id)

    def _on_cozme_iptal(self):
        if self._on_cozme and not self._on_cozme[1].done():
            self._on_cozme[1].cancel()
        self._on_cozme = None

    def kapat(self):
        """Tüm görevleri iptal eder, FFmpeg'leri durdurur. (Ses bağlantısını cog._cleanup_guild keser.)"""
        self.kapandi = True
        self.nesil += 1
        self._on_cozme_iptal()
        for t in list(self._gorevler):
            t.cancel()
        self._isitilmis_iptal()
        vc = self.vc
        if vc and (vc.is_playing() or vc.is_paused()):
            vc.stop()   # discord.py ses thread'i kaynak.cleanup() → FFmpeg kill + wait (zombi yok)
        elif self.kaynak is not None:
            self.kaynak.cleanup()
        self.kaynak = None
        self.simdiki = None
        self.kuyruk.temizle()
