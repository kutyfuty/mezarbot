"""
Muzik cog'u: komutlar (slash + prefix, hybrid), panel etkileşimleri, şarkı istek kanalı, ses olayları,
bakım döngüleri (panel ilerleme çubuğu, boşta/yalnız kalınca ayrılma, yt-dlp güncelleme).

Temizlik TEK yerde: Muzik._cleanup_guild() (AGENTS.md).
"""
import asyncio
import logging
import os
import random
import time

import discord
from discord import app_commands
from discord.ext import commands, tasks

import muzik_veritabani as mdb
from database import db, yonetici_mi
from arayuz import DURUM_TIPLERI
from yapilandirma import MUZIK_PROFILI, PREFIX, YTDLP_JS_CALISMA_ORTAMLARI, SAHIP_ID
from . import guncelleyici, ornekler
from .filtreler import BAS_SEVIYELERI, FILTRE_SECENEKLERI, secenek_uygula
from .kaynaklar import (ILK_PARTI, SPOTIFY_REGEX, Cozucu, CozmeHatasi, IsciHatasi, girdi_turu, hata_sebebi)
from .kuyruk import (DONGU_ETIKET, DONGU_SIRASI, DONGU_TAKMA_ADLAR, KuyrukDolu, Parca, dongu_sonraki_mod,
                     hedef_konum, oylama_esigi, sure_coz, sure_metni)
from .oynatici import Oynatici
from .panel import (MUZIK_RENGI, MuzikPaneli, SayfaGorunumu, bosta_embedi, calma_embedi, gecmis_embedi,
                    kuyruk_embedi, parca_satiri)
from dil import _t, dil_ayarla, dilli_gorev

logger = logging.getLogger('MezarBot.Muzik')

PANEL_ARALIGI = 12          # sn — çalarken ilerleme çubuğu güncelleme sıklığı (rate limit dostu)
PANEL_MIN_ARALIK = 2.0      # iki panel düzenlemesi arası en az süre (olaylar birleştirilir)
SES_ADIMI = 10
ISTEK_BEKLEME = 3.0         # istek kanalında kullanıcı başına mesaj aralığı
YENIDEN_BAGLANMA_ARALIGI = 120
SORGU_UZUNLUK = 500


def js_ortamlarini_denetle():
    """yt-dlp'nin YouTube JS challenge çözümü için desteklenen bir JS çalışma ortamı var mı? Log'a yazar."""
    try:
        from yt_dlp.globals import supported_js_runtimes
    except ImportError:
        return
    uygunlar = []
    for ad, ayar in YTDLP_JS_CALISMA_ORTAMLARI.items():
        sinif = supported_js_runtimes.value.get(ad)
        bilgi = sinif(path=ayar.get('path')).info if sinif else None
        if bilgi and bilgi.supported:
            uygunlar.append(f"{ad} {bilgi.version} ({bilgi.path})")
        elif bilgi:
            logger.warning(f"JS çalışma ortamı {ad} {bilgi.version} ({bilgi.path}) bu yt-dlp sürümü için çok eski, kullanılamıyor.")
    if uygunlar:
        logger.info("✅ yt-dlp JS çalışma ortamı: " + ", ".join(uygunlar))
    else:
        logger.warning("⚠️ yt-dlp için desteklenen JS çalışma ortamı yok (Node>=22 / Deno>=2.3 / Bun>=1.2.11). "
                       "YouTube'da bazı videolar çalınamayabilir. config.json → node_yolu / deno_yolu.")


def dave_durumunu_raporla():
    """discord.py 2.7+ ses için DAVE (uçtan uca şifreleme) kütüphanesi `davey`'i ZORUNLU tutar
    (VoiceClient.__init__ yoksa RuntimeError). Discord 2 Mart 2026'dan beri DAVE'siz ses bağlantısını reddeder."""
    try:
        from discord.voice_state import has_dave
    except ImportError:
        has_dave = False
    if has_dave:
        import davey
        logger.info(f"🔒 DAVE (uçtan uca ses şifreleme) hazır: davey {davey.__version__}, protokol v{davey.DAVE_PROTOCOL_VERSION}")
    else:
        logger.critical("❌ davey kurulu değil → discord.py sese bağlanamaz (Discord E2EE'siz sesi reddediyor). "
                        "Kurulum: venv/bin/pip install davey")


async def kalici_durumu_yukle(bot):
    """Veritabanındaki kalıcı bot durumunu okur (presence'ı durum_rotator.py yönetir). main.py çağırır."""
    def _sorgu():
        c = db.cursor()
        c.execute("SELECT durum_metni, durum_tipi FROM bot_ayarlar WHERE ayarlar_id = 1")
        return c.fetchone()
    try:
        ayar = await asyncio.to_thread(_sorgu)
    except Exception as e:  # tablo yok vb. — presence zaten durum_rotator'da
        logger.debug(f"kalici_durumu_yukle: {e}")
        return
    if ayar:
        DURUM_TIPLERI.get(ayar[1], discord.ActivityType.listening)


def _ac_kapat(metin, mevcut):
    """'aç'/'kapat'/None → bool (None: tersine çevir). Geçersizse ValueError."""
    if metin is None or not str(metin).strip():
        return not mevcut
    m = str(metin).strip().casefold()
    if m in ("aç", "ac", "on", "açık", "acik", "evet", "1", "true", "aktif"):
        return True
    if m in ("kapat", "kapa", "off", "kapalı", "kapali", "hayır", "hayir", "0", "false", "pasif"):
        return False
    raise ValueError(metin)


def _tam_sayi(metin):
    try:
        return int(str(metin).strip().lstrip('#'))
    except (TypeError, ValueError):
        return None


async def _sessiz_sil(mesaj, gecikme=0.0):
    if gecikme:
        await asyncio.sleep(gecikme)
    try:
        await mesaj.delete()
    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
        pass


class Muzik(commands.Cog):
    """🎵 Premium müzik: YouTube / YT Music / Spotify / SoundCloud, filtreler, sözler, kişisel listeler."""

    def __init__(self, bot):
        self.bot = bot
        sp_aktif = bool((os.getenv("SPOTIFY_CLIENT_ID") or "").strip() and (os.getenv("SPOTIFY_CLIENT_SECRET") or "").strip())
        if not sp_aktif:
            logger.warning("SPOTIFY_CLIENT_ID/SECRET boş — Spotify API devre dışı; Spotify linkleri embed sayfasından çözülür.")
        self.cozucu = Cozucu(spotify_aktif=sp_aktif)
        self.oynaticilar = {}
        self.paneller = {}
        self.panel_gorunumleri = {}
        self._panel_son = {}
        self._panel_gorev = {}
        self._bilincli_ayrilma = set()
        self._yeniden_baglanma_son = {}
        self._istek_son = {}
        self._baslangic_yapildi = False
        self._arka_gorevler = set()

    # ══════════════════════════════════════════════
    #  YAŞAM DÖNGÜSÜ
    # ══════════════════════════════════════════════

    async def cog_load(self):
        mdb.muzik_veritabanini_kur()
        self.bot.add_view(MuzikPaneli(self))   # kalıcı panel butonları (yeniden başlatma sonrası da çalışır)
        dave_durumunu_raporla()
        js_ortamlarini_denetle()
        self.panel_dongusu.start()
        self.bakim_dongusu.start()
        self.ytdlp_dongusu.start()
        if self.bot.is_ready():
            self._arka_gorev(self._baslangic_toparla())

    async def cog_unload(self):
        for dongu in (self.panel_dongusu, self.bakim_dongusu, self.ytdlp_dongusu):
            dongu.cancel()
        for gid in list(self.oynaticilar):
            try:
                await asyncio.wait_for(self._cleanup_guild(gid), timeout=5)
            except (asyncio.TimeoutError, discord.HTTPException):
                pass
        for t in list(self._panel_gorev.values()) + list(self._arka_gorevler):
            t.cancel()
        await self.cozucu.kapat()

    def _arka_gorev(self, coro):
        t = asyncio.create_task(coro)
        self._arka_gorevler.add(t)
        t.add_done_callback(self._arka_gorevler.discard)
        return t

    async def cog_check(self, ctx):
        if ctx.guild is None:
            raise commands.NoPrivateMessage()
        return await ornekler.denetle(self, ctx)   # çoklu müzik botu: komutu doğru bot üstlensin

    async def cog_before_invoke(self, ctx):
        # Prefix komut mesajlarını sil (kanal temiz kalsın); slash komutlarında mesaj yok
        if ctx.interaction is None and ctx.guild is not None:
            self._arka_gorev(_sessiz_sil(ctx.message, 0.5))

    # ══════════════════════════════════════════════
    #  YARDIMCILAR
    # ══════════════════════════════════════════════

    def oynatici_al(self, gid, olustur=True):
        oyn = self.oynaticilar.get(gid)
        if oyn is None and olustur:
            oyn = Oynatici(self, gid, mdb.muzik_ayar_al(gid))
            self.oynaticilar[gid] = oyn
        return oyn

    def aktif_oynatici_sayisi(self):
        return sum(1 for o in self.oynaticilar.values() if o.simdiki is not None and o.caliyor_mu())

    @staticmethod
    def _insanlar(vc):
        return [m for m in vc.channel.members if not m.bot] if (vc and vc.channel) else []

    @staticmethod
    def _dinleyiciler(vc):
        """Oylamada sayılanlar: kanaldaki, sağırlaştırılmamış insanlar."""
        return [m for m in Muzik._insanlar(vc)
                if not (m.voice and (m.voice.self_deaf or m.voice.deaf))]

    def _dj_mi(self, uye, ayar=None):
        if yonetici_mi(uye):
            return True
        ayar = ayar or mdb.muzik_ayar_al(uye.guild.id)
        rol_id = ayar.get('dj_rol_id')
        if not rol_id:
            return True   # DJ sistemi kapalı → herkes kontrol eder
        if any(r.id == rol_id for r in getattr(uye, 'roles', ())):
            return True
        vc = uye.guild.voice_client
        insanlar = self._insanlar(vc)
        return len(insanlar) == 1 and insanlar[0].id == uye.id   # botla yalnızsa DJ sayılır

    def _ayar_yetkisi(self, uye, sadece_yonetici=False):
        if yonetici_mi(uye):
            return True
        if sadece_yonetici:
            return False
        rol_id = mdb.muzik_ayar_al(uye.guild.id).get('dj_rol_id')
        return bool(rol_id and any(r.id == rol_id for r in uye.roles))

    def _kontrol_hatasi(self, uye, dj_gerekli=True):
        """Kontrol komutları için yetki/konum kontrolü. Hata metni ya da None."""
        vc = uye.guild.voice_client
        if vc and vc.channel and not (uye.voice and uye.voice.channel == vc.channel) and not yonetici_mi(uye):
            return _t("🎧 Bunu yapmak için benimle aynı ses kanalında (**{name}**) olmalısın.", name=vc.channel.name)
        if dj_gerekli and not self._dj_mi(uye):
            rol_id = mdb.muzik_ayar_al(uye.guild.id).get('dj_rol_id')
            return _t("🎚️ Bu işlem için **DJ rolü** (<@&{rol_id}>) gerekli.", rol_id=rol_id)
        return None

    async def _yanit(self, ctx, icerik=None, embed=None, gizli=True, sure=10, view=None):
        kw = {'content': icerik, 'embed': embed, 'allowed_mentions': discord.AllowedMentions.none()}
        if view is not None:
            kw['view'] = view
        if ctx.interaction is not None:
            kw['ephemeral'] = gizli
            if not gizli and sure:
                kw['delete_after'] = sure
        elif sure:
            kw['delete_after'] = sure
        try:
            return await ctx.send(**kw)
        except discord.HTTPException as e:
            logger.debug(f"Yanıt gönderilemedi: {e}")
            return None

    def _istek_kanali(self, guild):
        kanal_id = mdb.muzik_ayar_al(guild.id).get('istek_kanal_id')
        kanal = guild.get_channel(kanal_id) if kanal_id else None
        return kanal if isinstance(kanal, discord.TextChannel) else None

    def _panel_kanali(self, guild, oyn):
        istek = self._istek_kanali(guild)
        if istek:
            return istek
        if oyn and oyn.metin_kanal_id:
            return guild.get_channel(oyn.metin_kanal_id)
        return None

    async def bildir(self, gid, metin, sure=12):
        """Oynatıcı olaylarını (atlanan parça vb.) panel kanalına kısa ömürlü mesaj olarak yazar."""
        guild = self.bot.get_guild(gid)
        if not guild:
            return
        kanal = self._panel_kanali(guild, self.oynaticilar.get(gid))
        if kanal is None:
            return
        try:
            await kanal.send(metin, delete_after=sure, allowed_mentions=discord.AllowedMentions.none())
        except discord.HTTPException:
            pass

    # ══════════════════════════════════════════════
    #  PANEL
    # ══════════════════════════════════════════════

    def _gorunum(self, gid):
        g = self.panel_gorunumleri.get(gid)
        if g is None:
            g = MuzikPaneli(self)
            self.panel_gorunumleri[gid] = g
        return g

    def _panel_icerigi(self, guild, oyn):
        if oyn is not None and oyn.simdiki is not None:
            embed = calma_embedi(oyn)
        else:
            istek = self._istek_kanali(guild)
            embed = bosta_embedi(guild, istek_kanali=istek is not None, prefix=PREFIX)
        return embed, self._gorunum(guild.id).guncelle(oyn)

    async def panel_guncelle(self, gid, hemen=False):
        """Paneli günceller (en fazla PANEL_MIN_ARALIK'ta bir; aradaki istekler birleştirilir). Asla bloklamaz."""
        gorev = self._panel_gorev.get(gid)
        if gorev is not None and not gorev.done():
            return
        gecen = time.monotonic() - self._panel_son.get(gid, 0.0)
        bekle = 0.0 if hemen else max(0.0, PANEL_MIN_ARALIK - gecen)
        self._panel_gorev[gid] = dilli_gorev(self._panel_yaz(gid, bekle), gid)

    async def _panel_yaz(self, gid, bekle):
        if bekle:
            await asyncio.sleep(bekle)
        try:
            await self._panel_yaz_simdi(gid)
        except discord.HTTPException as e:
            logger.debug(f"[{gid}] Panel güncellenemedi: {e}")

    async def _panel_yaz_simdi(self, gid):
        guild = self.bot.get_guild(gid)
        if guild is None:
            return
        oyn = self.oynaticilar.get(gid)
        embed, gorunum = self._panel_icerigi(guild, oyn)
        self._panel_son[gid] = time.monotonic()
        mesaj = self.paneller.get(gid)
        if mesaj is not None:
            try:
                await mesaj.edit(embed=embed, view=gorunum)
                return
            except discord.NotFound:
                self.paneller.pop(gid, None)
        caliyor = oyn is not None and oyn.simdiki is not None
        istek = self._istek_kanali(guild)
        if not caliyor and istek is None:
            return   # boştayken yeni panel açma
        kanal = istek or self._panel_kanali(guild, oyn)
        if kanal is None:
            return
        izin = kanal.permissions_for(guild.me)
        if not (izin.send_messages and izin.embed_links):
            return
        mesaj = await kanal.send(embed=embed, view=gorunum)
        self.paneller[gid] = mesaj
        mdb.muzik_ayar_guncelle(gid, panel_kanal_id=kanal.id, panel_mesaj_id=mesaj.id)
        if istek is not None and izin.manage_messages:
            try:
                await mesaj.pin(reason=_t("{bot} müzik paneli", bot=self.bot.user.name))
            except discord.HTTPException:
                pass

    async def _panel_kaldir(self, gid):
        """Paneli kaldırır: istek kanalındaysa boşta görünümüne döner, değilse silinir."""
        gorev = self._panel_gorev.pop(gid, None)
        if gorev and not gorev.done():
            gorev.cancel()
        guild = self.bot.get_guild(gid)
        mesaj = self.paneller.get(gid)
        if mesaj is None or guild is None:
            return
        istek = self._istek_kanali(guild)
        if istek is not None and mesaj.channel.id == istek.id:
            try:
                await mesaj.edit(embed=bosta_embedi(guild, True, PREFIX), view=self._gorunum(gid).guncelle(None))
            except discord.NotFound:
                self.paneller.pop(gid, None)
            except discord.HTTPException:
                pass
            return
        self.paneller.pop(gid, None)
        await _sessiz_sil(mesaj)
        mdb.muzik_ayar_guncelle(gid, panel_kanal_id=None, panel_mesaj_id=None)

    async def _panel_tasi(self, guild, kanal):
        """Paneli bu kanala taşır (eskisini siler)."""
        oyn = self.oynaticilar.get(guild.id)
        if oyn:
            oyn.metin_kanal_id = kanal.id
        eski = self.paneller.pop(guild.id, None)
        if eski is not None:
            await _sessiz_sil(eski)
        await self._panel_yaz_simdi(guild.id)

    async def _baslangic_toparla(self):
        """Yeniden başlatma sonrası: eski 'şu an çalıyor' panellerini sil, istek kanalı panellerini boşta göster."""
        if self._baslangic_yapildi:
            return
        self._baslangic_yapildi = True
        for sid, kanal_id, mesaj_id, istek_id in mdb.panel_kayitlari():
            guild = self.bot.get_guild(sid)
            if guild is None:
                continue
            kanal = guild.get_channel(kanal_id)
            if kanal is None:
                mdb.muzik_ayar_guncelle(sid, panel_kanal_id=None, panel_mesaj_id=None)
                continue
            mesaj = kanal.get_partial_message(mesaj_id)
            if kanal_id == istek_id:
                self.paneller[sid] = mesaj
                try:
                    await mesaj.edit(embed=bosta_embedi(guild, True, PREFIX), view=self._gorunum(sid).guncelle(None))
                except discord.NotFound:
                    self.paneller.pop(sid, None)
                    mdb.muzik_ayar_guncelle(sid, panel_kanal_id=None, panel_mesaj_id=None)
                except discord.HTTPException as e:
                    logger.debug(f"İstek paneli düzenlenemedi ({sid}): {e}")
            else:
                await _sessiz_sil(mesaj)
                mdb.muzik_ayar_guncelle(sid, panel_kanal_id=None, panel_mesaj_id=None)
        for sid, _ in mdb.istek_kanallari():
            if sid not in self.paneller and self.bot.get_guild(sid):
                try:
                    await self._panel_yaz_simdi(sid)
                except discord.HTTPException as e:
                    logger.debug(f"İstek paneli oluşturulamadı ({sid}): {e}")
        logger.info(f"🎛️ Müzik panelleri toparlandı ({len(self.paneller)} istek kanalı paneli)")

    # ══════════════════════════════════════════════
    #  TEMİZLİK (tek merkez)
    # ══════════════════════════════════════════════

    async def _cleanup_guild(self, guild_id, vc=None, sebep=None):
        """Bir sunucunun müzik durumunu tamamen temizler: oynatıcı (FFmpeg, görevler), panel, ses bağlantısı."""
        oyn = self.oynaticilar.pop(guild_id, None)
        metin_kanal_id = oyn.metin_kanal_id if oyn else None
        if oyn is not None:
            oyn.kapat()
        await self._panel_kaldir(guild_id)
        if guild_id not in self.paneller:   # istek kanalı paneli kalıcı; diğerlerinin görünümü atılır
            self.panel_gorunumleri.pop(guild_id, None)
        self._panel_son.pop(guild_id, None)
        guild = self.bot.get_guild(guild_id)
        vc = vc or (guild.voice_client if guild else None)
        if vc is not None:
            self._bilincli_ayrilma.add(guild_id)
            try:
                await vc.disconnect(force=True)
            except Exception as e:  # bağlantı zaten kopmuş olabilir
                logger.debug(f"[{guild_id}] disconnect: {e}")
                self._bilincli_ayrilma.discard(guild_id)
        if sebep and guild is not None:
            kanal = self._istek_kanali(guild) or (guild.get_channel(metin_kanal_id) if metin_kanal_id else None)
            if kanal is not None:
                try:
                    await kanal.send(sebep, delete_after=20)
                except discord.HTTPException:
                    pass

    async def _durdur(self, guild):
        """⏹️: 7/24 modunda kanalda kalır (kuyruk temizlenir), değilse ayrılır."""
        oyn = self.oynaticilar.get(guild.id)
        if mdb.muzik_ayar_al(guild.id).get('surekli_mod') and oyn is not None:
            oyn.durdur()
            await self.panel_guncelle(guild.id, hemen=True)
            return _t("⏹️ Durduruldu, kuyruk temizlendi. (7/24 modu: kanalda kalıyorum)")
        await self._cleanup_guild(guild.id)
        return _t("⏹️ Durduruldu ve kanaldan ayrıldım.")

    # ══════════════════════════════════════════════
    #  SES BAĞLANTISI + ÇALMA
    # ══════════════════════════════════════════════

    async def _sese_baglan(self, uye, metin_kanal):
        """→ (oynatici, hata_metni)."""
        guild = uye.guild
        if not uye.voice or not uye.voice.channel:
            return None, _t("❌ Önce bir ses kanalına gir!")
        kanal = uye.voice.channel
        izin = kanal.permissions_for(guild.me)
        if not (izin.connect and izin.speak):
            return None, _t("❌ **{name}** kanalına bağlanma/konuşma yetkim yok.", name=kanal.name)
        vc = guild.voice_client
        oyn = self.oynaticilar.get(guild.id)
        if vc is None or not vc.is_connected():
            if vc is not None:
                try:
                    await vc.disconnect(force=True)
                except Exception as e:  # yarım kalmış bağlantı
                    logger.debug(f"Eski ses bağlantısı kapatılamadı: {e}")
            try:
                self._bilincli_ayrilma.discard(guild.id)
                vc = await kanal.connect(timeout=20, reconnect=True, self_deaf=True)
            except asyncio.TimeoutError:
                return None, _t("❌ Ses bağlantısı zaman aşımına uğradı, tekrar dene.")
            except discord.ClientException as e:
                return None, _t("❌ Sese bağlanılamadı: {e}", e=e)
            except RuntimeError as e:   # davey / PyNaCl eksik
                logger.critical(f"Ses kütüphanesi eksik: {e}")
                return None, _t("❌ Botun ses kütüphaneleri eksik (DAVE/davey). Bot sahibine haber ver.")
            if isinstance(kanal, discord.StageChannel):
                try:
                    await guild.me.edit(suppress=False)
                except discord.HTTPException:
                    pass
        elif vc.channel != kanal:
            baska_dinleyen = [m for m in self._insanlar(vc) if m.id != uye.id]
            if oyn and oyn.simdiki and baska_dinleyen and not self._dj_mi(uye):
                return None, _t("🎧 Şu an **{name}** kanalında çalıyorum — oraya gel ya da DJ'e söyle.", name=vc.channel.name)
            try:
                await vc.move_to(kanal)
            except (discord.HTTPException, asyncio.TimeoutError) as e:
                return None, _t("❌ Kanala taşınamadım: {e}", e=e)
        oyn = self.oynatici_al(guild.id)
        if metin_kanal is not None:
            oyn.metin_kanal_id = metin_kanal.id
        return oyn, None

    @staticmethod
    def _isteyen_ata(parcalar, uye):
        for p in parcalar:
            p.isteyen_id = uye.id
            p.isteyen_ad = uye.display_name
            p.isteyen_avatar = str(uye.display_avatar.url)
        return parcalar

    async def _girdiden_parcalar(self, sorgu, limit):
        """Kullanıcı girdisi → (liste_basligi | None, [Parca], devam_url | None, toplam). Hata → CozmeHatasi."""
        tur, ek = girdi_turu(sorgu)
        if tur == 'spotify_kisa':
            uzun = await self.cozucu.kisa_link_coz(ek)
            if not uzun:
                raise CozmeHatasi(_t("Spotify kısa linki çözülemedi"))
            tur, ek = girdi_turu(uzun)
            if tur != 'spotify':
                raise CozmeHatasi(_t("Spotify kısa linki tanınmayan bir sayfaya gidiyor"))
        if tur == 'arama':
            parca = await self.cozucu.arama_parcasi(ek)
            if parca is None:
                raise CozmeHatasi(_t("sonuç bulunamadı"))
            return None, [parca], None, 1
        if tur == 'url':
            parca = Parca(sorgu=ek, url=ek)
            await self.cozucu.coz(parca)
            return None, [parca], None, 1
        if tur == 'spotify':
            alt, sp_id = ek
            baslik, parcalar = await self.cozucu.spotify(alt, sp_id, limit=limit)
            if not parcalar:
                raise CozmeHatasi(_t("Spotify içeriği okunamadı (özel liste olabilir)"))
            return (baslik if alt != 'track' else None), parcalar, None, len(parcalar)
        # playlist (YouTube / YT Music / SoundCloud set)
        ilk = min(ILK_PARTI, limit)
        try:
            baslik, parcalar, toplam = await self.cozucu.playlist(ek, 1, ilk)
        except (IsciHatasi, asyncio.TimeoutError) as e:
            raise hata_sebebi(e)
        if not parcalar:
            raise CozmeHatasi(_t("playlist boş ya da özel"))
        devam = ek if (toplam > ilk or (not toplam and len(parcalar) >= ilk)) and limit > ilk else None
        return baslik, parcalar, devam, max(toplam, len(parcalar))

    @staticmethod
    def _otomatik_oncesi(oyn):
        """Biri elle şarkı ekliyor: kuyruktaki otomatik öneriler çıkarılır (eklenen şarkı onları beklemez; kuyruk bitince
        otomatik oynatma son çalandan yeni öneri bulur). → Şu an otomatik bir öneri çalıyorsa True (hemen geçilecek)."""
        oyn.kuyruk.otomatikleri_kaldir()
        return bool(oyn.simdiki is not None and oyn.simdiki.otomatik and oyn.caliyor_mu() and not oyn.mesgul_mu())

    async def _ekleme_sonrasi(self, oyn, gid, onune_gec):
        """Kuyruğa ekledikten sonra: çalan otomatik öneriyse eklenen şarkıya hemen geç, değilse ön çözme + panel."""
        if onune_gec and await oyn.atla() == 'ok':
            return
        oyn._on_coz_baslat()
        await self.panel_guncelle(gid)

    async def _oynat_ortak(self, uye, metin_kanal, sorgu, basa, yanit):
        """oynat / sıradaki / istek kanalı ortak mantığı. yanit(icerik=None, embed=None) coroutine."""
        oyn, hata = await self._sese_baglan(uye, metin_kanal)
        if hata:
            return await yanit(hata)
        bos_yer = oyn.kuyruk.bos_yer()
        if bos_yer <= 0:
            return await yanit(_t("❌ Kuyruk dolu ({limit} parça). Biraz çalınmasını bekle ya da `/temizle`.", limit=oyn.kuyruk.limit))
        try:
            liste_basligi, parcalar, devam, toplam = await self._girdiden_parcalar(sorgu, bos_yer)
        except CozmeHatasi as h:
            return await yanit(_t("❌ Çalınamıyor: {sebep}", sebep=_t(h.sebep)))
        except (IsciHatasi, asyncio.TimeoutError) as e:
            return await yanit(_t("❌ Çalınamıyor: {sebep}", sebep=_t(hata_sebebi(e).sebep)))
        self._isteyen_ata(parcalar, uye)
        onune_gec = self._otomatik_oncesi(oyn)
        bos_yer = oyn.kuyruk.bos_yer()
        if basa:
            eklenen = 0
            for p in reversed(parcalar[:bos_yer]):
                oyn.kuyruk.basa_ekle(p, zorla=True)
                eklenen += 1
        else:
            eklenen = oyn.kuyruk.toplu_ekle(parcalar)
        oyn.son_aktivite = time.monotonic()
        baslayacak = oyn.simdiki is None and not oyn.caliyor_mu() and not oyn.mesgul_mu()

        if liste_basligi is not None or len(parcalar) > 1:
            satirlar = [_t("📋 **{escape_markdown}** — **{eklenen}** parça {d5} eklendi.", escape_markdown=discord.utils.escape_markdown(liste_basligi or 'Liste'), eklenen=eklenen, d5=_t("sıranın başına") if basa else _t("kuyruğa"))]
            if devam:
                satirlar.append(_t("⏳ Kalan parçalar arka planda ekleniyor… (toplam ~{toplam})", toplam=toplam))
            if onune_gec:
                satirlar.append(_t("📻 Otomatik öneri yerine hemen senin listen başlıyor."))
            if eklenen < len(parcalar):
                satirlar.append(_t("⚠️ Kuyruk sınırı ({limit}) nedeniyle {d3} parça eklenemedi.", limit=oyn.kuyruk.limit, d3=len(parcalar) - eklenen))
            embed = discord.Embed(color=MUZIK_RENGI, description="\n".join(satirlar))
            if parcalar[0].kucuk_resim:
                embed.set_thumbnail(url=parcalar[0].kucuk_resim)
        else:
            p = parcalar[0]
            if baslayacak:
                durum = _t("▶️ **Şimdi çalınıyor**")
            elif onune_gec:
                durum = _t("▶️ **Şimdi çalınıyor** — otomatik önerinin yerine")
            elif basa:
                durum = _t("⏭️ **Sıradaki olarak eklendi**")
            else:
                durum = _t("✅ **Kuyruğa eklendi** · #{len}", len=len(oyn.kuyruk))
            embed = discord.Embed(color=MUZIK_RENGI, description=f"{durum}\n{parca_satiri(p, 70)}")
            if p.kucuk_resim:
                embed.set_thumbnail(url=p.kucuk_resim)
        await yanit(embed=embed)

        if devam and not basa:
            oyn.gorev(self._playlist_devam(oyn, devam, ILK_PARTI + 1, uye), ad=f"muzik-playlist-{uye.guild.id}")
        if baslayacak:
            await oyn.baslat_bossa()
        else:
            await self._ekleme_sonrasi(oyn, uye.guild.id, onune_gec)

    async def _playlist_devam(self, oyn, url, bas, uye):
        """Büyük playlist'in kalanını arka planda (işçi süreçte) çekip kuyruğa ekler."""
        bos = oyn.kuyruk.bos_yer()
        if bos <= 0:
            return
        try:
            _, parcalar, _ = await self.cozucu.playlist(url, bas, bas + bos - 1)
        except (IsciHatasi, asyncio.TimeoutError) as e:
            await self.bildir(oyn.guild_id, _t("⚠️ Playlist'in kalanı yüklenemedi: {sebep}", sebep=_t(hata_sebebi(e).sebep)))
            return
        if oyn.kapandi:
            return
        eklenen = oyn.kuyruk.toplu_ekle(self._isteyen_ata(parcalar, uye))
        if eklenen:
            await self.bildir(oyn.guild_id, _t("📋 Playlist'in kalan **{eklenen}** parçası da kuyruğa eklendi.", eklenen=eklenen))
            oyn._on_coz_baslat()
            await self.panel_guncelle(oyn.guild_id)

    async def _calmalistesi_oynat_dahili(self, ctx, bulunan, karistir=None, basa=False):
        liste_id, sahip_id, liste_adi = bulunan
        kayitlar = mdb.liste_parcalari(liste_id)
        if not kayitlar:
            return await self._yanit(ctx, _t("❌ **{liste_adi}** listesi boş.", liste_adi=liste_adi))
        if not ctx.interaction or not ctx.interaction.response.is_done():
            await ctx.defer()
        oyn, hata = await self._sese_baglan(ctx.author, ctx.channel)
        if hata:
            return await self._yanit(ctx, hata)
        parcalar = [_kayittan_parca(k) for k in kayitlar]
        try:
            if karistir and _ac_kapat(karistir, False):
                random.SystemRandom().shuffle(parcalar)
        except ValueError:
            pass
        self._isteyen_ata(parcalar, ctx.author)
        onune_gec = self._otomatik_oncesi(oyn)
        if basa:
            eklenen = 0
            for p in reversed(parcalar[:oyn.kuyruk.bos_yer()]):
                oyn.kuyruk.basa_ekle(p, zorla=True)
                eklenen += 1
        else:
            eklenen = oyn.kuyruk.toplu_ekle(parcalar)
        sahip_notu = ""
        if sahip_id != ctx.author.id:
            sahip_notu = _t(" (⭐ Sunucu Listesi)") if sahip_id == SAHIP_ID else _t(" (Paylaşılan)")
        yer_metni = _t("sıranın başına") if basa else _t("kuyruğa")
        await self._yanit(ctx, _t("📂 **{liste_adi}**{sahip_notu} — **{eklenen}** parça {yer_metni} eklendi.", liste_adi=liste_adi, sahip_notu=sahip_notu, eklenen=eklenen, yer_metni=yer_metni)
                          + (_t(" (Kuyruk sınırı: {d1} eklenemedi)", d1=len(parcalar) - eklenen) if eklenen < len(parcalar) else ""),
                          gizli=False, sure=15)
        if oyn.simdiki is None and not oyn.caliyor_mu():
            await oyn.baslat_bossa()
        else:
            await self._ekleme_sonrasi(oyn, ctx.guild.id, onune_gec)

    async def _oynat_komutu(self, ctx, sorgu, basa):
        if not sorgu and ctx.message and ctx.message.attachments:
            sorgu = ctx.message.attachments[0].url
        if not sorgu:
            return await self._yanit(ctx, _t("❌ Bir şarkı adı ya da link yaz: `/oynat tarkan şımarık`"))
        if len(sorgu) > SORGU_UZUNLUK:
            return await self._yanit(ctx, _t("❌ Arama metni çok uzun!"))
        if basa:
            hata = self._kontrol_hatasi(ctx.author)
            if hata:
                return await self._yanit(ctx, hata)

        temiz_sorgu = sorgu.strip()
        liste_adi = None
        if temiz_sorgu.lower().startswith(("liste:", "cl:", "playlist:")):
            liste_adi = temiz_sorgu.split(":", 1)[1].strip()
        elif temiz_sorgu.casefold() in ("favoriler", "favori"):
            liste_adi = "Favoriler"

        if liste_adi:
            bulunan = mdb.liste_bul_ayrintili(ctx.author.id, liste_adi, genel_ara=True)
            if bulunan:
                return await self._calmalistesi_oynat_dahili(ctx, bulunan, karistir=None, basa=basa)

        await ctx.defer()

        async def yanit(icerik=None, embed=None):
            await self._yanit(ctx, icerik, embed=embed, gizli=icerik is not None, sure=20)
        await self._oynat_ortak(ctx.author, ctx.channel, sorgu, basa, yanit)

    # ══════════════════════════════════════════════
    #  ORTAK KONTROL MANTIĞI (komutlar + panel)
    # ══════════════════════════════════════════════

    async def _atla_istegi(self, uye, oyn, oy_kullan=False):
        """Atlama: DJ / şarkıyı isteyen / oylama kapalıysa anında; değilse oy toplar. → mesaj"""
        if oyn is None or oyn.simdiki is None:
            return _t("❌ Çalan bir şey yok.")
        hata = self._kontrol_hatasi(uye, dj_gerekli=False)
        if hata:
            return hata
        ayar = mdb.muzik_ayar_al(uye.guild.id)
        oylama = bool(ayar.get('dj_rol_id') or ayar.get('oylama_aktif'))
        yetkili = self._dj_mi(uye, ayar) or oyn.simdiki.isteyen_id == uye.id
        if not oylama or (yetkili and not oy_kullan):
            sonuc = await oyn.atla()
            return {"ok": "⏭️ Atlandı.", "mesgul": "⏳ Geçiş sürüyor, bir saniye…"}.get(sonuc, "❌ Çalan bir şey yok.")
        dinleyiciler = self._dinleyiciler(uye.guild.voice_client)
        idler = {m.id for m in dinleyiciler}
        oyn.oylar.add(uye.id)
        oyn.oylar &= idler | {uye.id}
        gerekli = oylama_esigi(len(dinleyiciler), ayar.get('oylama_orani', 0.5))
        if len(oyn.oylar) >= gerekli:
            n = len(oyn.oylar)
            sonuc = await oyn.atla()
            return _t("🗳️ Oylama tamam ({n}/{gerekli}) — ⏭️ atlandı.", n=n, gerekli=gerekli) if sonuc == "ok" else _t("⏳ Geçiş sürüyor…")
        return _t("🗳️ Atlama oyu: **{len}/{gerekli}** — dinleyicilerin %{int}'i gerekli.", len=len(oyn.oylar), gerekli=gerekli, int=int(ayar.get('oylama_orani', 0.5) * 100))

    async def _ses_uygula(self, oyn, deger):
        deger = max(mdb.SES_MIN, min(mdb.SES_MAX, int(deger)))
        oyn.ses_ayarla(deger)
        mdb.muzik_ayar_guncelle(oyn.guild_id, son_ses=deger)
        await self.panel_guncelle(oyn.guild_id)
        return deger

    async def _filtre_uygula(self, oyn, anahtar, deger=None):
        anahtar = _FILTRE_TAKMA.get(anahtar.casefold(), anahtar.casefold())
        if anahtar == "bas" or anahtar == "bassboost":
            seviye = _tam_sayi(deger) if deger is not None else 2
            anahtar = f"bas{min(4, max(0, seviye or 0))}" if seviye else "bas0"
            deger = None
        if anahtar == "bas0":
            oyn.filtre.bas = 0
            metin = _t("Bassboost: Kapalı")
        else:
            try:
                sayi = float(str(deger).replace(",", ".").rstrip("x")) if deger is not None else None
            except ValueError:
                sayi = None
            metin = secenek_uygula(oyn.filtre, anahtar, sayi)
        if oyn.simdiki is not None:
            await oyn.yeniden_baslat()
        await self.panel_guncelle(oyn.guild_id)
        return metin

    # ══════════════════════════════════════════════
    #  PANEL ETKİLEŞİMLERİ
    # ══════════════════════════════════════════════

    async def panel_etkilesimi(self, interaction, eylem, deger=None):
        guild = interaction.guild
        if guild is None:
            return
        uye = interaction.user
        oyn = self.oynaticilar.get(guild.id)
        panel_mesaji = self.paneller.get(guild.id)
        panel_bu = interaction.message is not None and panel_mesaji is not None and interaction.message.id == panel_mesaji.id
        if panel_mesaji is None and interaction.message is not None:
            self.paneller[guild.id] = interaction.message   # yeniden başlatma sonrası tıklanan eski panel
            panel_bu = True

        async def gizli(metin=None, embed=None, view=None):
            kw = {'ephemeral': True, 'allowed_mentions': discord.AllowedMentions.none()}
            if embed is not None:
                kw['embed'] = embed
            if view is not None:
                kw['view'] = view
            if interaction.response.is_done():
                return await interaction.followup.send(metin, wait=True, **kw)
            await interaction.response.send_message(metin, **kw)
            return await interaction.original_response()

        # ── Herkese açık, sadece görüntüleme ──
        if eylem == "kuyruk":
            if oyn is None:
                return await gizli(_t("🎶 Kuyruk boş."))
            gorunum = SayfaGorunumu(lambda s: kuyruk_embedi(oyn, s), kullanici_id=uye.id)
            gorunum.mesaj = await gizli(embed=gorunum.ilk(), view=gorunum)
            return
        if eylem == "favori":
            if oyn is None or oyn.simdiki is None:
                return await gizli(_t("❌ Çalan bir şey yok."))
            return await gizli(self._favoriye_ekle(uye.id, oyn.simdiki))

        if oyn is None or (oyn.simdiki is None and eylem != "otomatik"):
            return await gizli(_t("❌ Şu an çalan bir şey yok. `/oynat` ile başla."))

        if eylem == "atla":
            await interaction.response.defer()
            metin = await self._atla_istegi(uye, oyn)
            if not metin.startswith("⏭️"):
                await interaction.followup.send(metin, ephemeral=True)
            return

        hata = self._kontrol_hatasi(uye, dj_gerekli=True)
        if hata:
            return await gizli(hata)

        mesaj = None
        yavas = eylem in ("filtre", "onceki", "durdur", "sesazalt", "sesartir")
        if yavas:
            await interaction.response.defer()
        vc = guild.voice_client
        if eylem == "duraklat":
            if vc and vc.is_paused():
                vc.resume()
                oyn.otomatik_duraklatildi = False
            elif vc and vc.is_playing():
                vc.pause()
        elif eylem == "onceki":
            sonuc = await oyn.onceki()
            if sonuc is None:
                mesaj = _t("⏮️ Geçmişte önceki bir şarkı yok.")
            elif sonuc == "mesgul":
                mesaj = _t("⏳ Geçiş sürüyor, bir saniye…")
        elif eylem == "durdur":
            mesaj = await self._durdur(guild)
            return await interaction.followup.send(mesaj, ephemeral=True)
        elif eylem == "dongu":
            oyn.dongu = dongu_sonraki_mod(oyn.dongu)
            oyn._on_coz_baslat()
            oyn._isitma_planla()
        elif eylem == "karistir":
            if len(oyn.kuyruk) < 2:
                mesaj = _t("🔀 Karıştırmak için kuyrukta en az 2 parça olmalı.")
            else:
                oyn.kuyruk.karistir()
                oyn._on_coz_baslat()
                oyn._isitma_planla()
        elif eylem in ("sesazalt", "sesartir"):
            yeni = oyn.ses + (SES_ADIMI if eylem == "sesartir" else -SES_ADIMI)
            yeni = await self._ses_uygula(oyn, yeni)
            mesaj = None
        elif eylem == "otomatik":
            oyn.otomatik = not oyn.otomatik
            mdb.muzik_ayar_guncelle(guild.id, otomatik_oynatma=int(oyn.otomatik))
            if not oyn.otomatik:
                oyn.kuyruk.otomatikleri_kaldir()
            oyn._on_coz_baslat()
        elif eylem == "filtre":
            metin = await self._filtre_uygula(oyn, deger)
            mesaj = f"🎛️ {metin}"

        if interaction.response.is_done():
            await self.panel_guncelle(guild.id, hemen=True)
            if mesaj:
                await interaction.followup.send(mesaj, ephemeral=True)
            return
        if panel_bu:
            embed, gorunum = self._panel_icerigi(guild, oyn)
            self._panel_son[guild.id] = time.monotonic()
            await interaction.response.edit_message(embed=embed, view=gorunum)
            if mesaj:
                await interaction.followup.send(mesaj, ephemeral=True)
        else:
            await gizli(mesaj or "✅")
            await self.panel_guncelle(guild.id)

    def _favoriye_ekle(self, kullanici_id, parca):
        try:
            liste_id = mdb.liste_olustur(kullanici_id, "Favoriler")
        except mdb.ListeHatasi as h:
            return f"❌ {h}"
        kayit = parca.veritabani_bicimi()
        if any(p['sorgu'] == kayit['sorgu'] for p in mdb.liste_parcalari(liste_id)):
            return _t("❤️ Bu şarkı zaten **Favoriler** listende.")
        if not mdb.listeye_parca_ekle(liste_id, [kayit]):
            return _t("❌ Liste dolu ({LISTE_PARCA_LIMITI} parça).", LISTE_PARCA_LIMITI=mdb.LISTE_PARCA_LIMITI)
        return _t("❤️ **{gosterim}** → **Favoriler** listene eklendi. (`/calmalistesi oynat Favoriler`)", gosterim=parca.gosterim(60))

    # ══════════════════════════════════════════════
    #  KOMUTLAR — ÇALMA
    # ══════════════════════════════════════════════

    @commands.hybrid_command(name="oynat", aliases=["cal", "çal", "play", "p"],
                             description="Şarkı / playlist çalar (YouTube, YT Music, Spotify, SoundCloud, link)")
    @app_commands.describe(sorgu="Şarkı adı ya da link (YouTube, YT Music, Spotify, SoundCloud, doğrudan ses linki)")
    async def oynat(self, ctx, *, sorgu: str = None):
        await self._oynat_komutu(ctx, sorgu, basa=False)

    @commands.hybrid_command(name="siradaki", aliases=["sıradaki", "playnext", "pn", "oncecal"],
                             description="Şarkıyı kuyruğun en başına ekler (sıradaki çalar)")
    @app_commands.describe(sorgu="Şarkı adı ya da link")
    async def siradaki(self, ctx, *, sorgu: str = None):
        await self._oynat_komutu(ctx, sorgu, basa=True)

    @commands.hybrid_command(name="atla", aliases=["skip", "s", "geç", "gec", "next"],
                             description="Şarkıyı atlar (oylama açıksa oy verir) · numara verirsen o parçaya atlar")
    @app_commands.describe(hedef="İsteğe bağlı: kuyruktaki şu numaralı parçaya atla")
    async def atla(self, ctx, hedef: str = None):
        oyn = self.oynaticilar.get(ctx.guild.id)
        if hedef:
            n = _tam_sayi(hedef)
            if n is None:
                return await self._yanit(ctx, _t("❌ Numara gir: `/atla 3` (sarmak için `/sar 1:30`)"))
            hata = self._kontrol_hatasi(ctx.author)
            if hata:
                return await self._yanit(ctx, hata)
            if oyn is None or oyn.simdiki is None:
                return await self._yanit(ctx, _t("❌ Çalan bir şey yok."))
            try:
                oyn.kuyruk.atla_konuma(n)
            except IndexError:
                return await self._yanit(ctx, _t("❌ Geçersiz numara (1-{len}).", len=len(oyn.kuyruk)))
            await oyn.atla()
            return await self._yanit(ctx, _t("⏭️ {n}. parçaya atlandı.", n=n), gizli=False, sure=6)
        metin = await self._atla_istegi(ctx.author, oyn)
        await self._yanit(ctx, metin, gizli=not metin.startswith(("⏭️", "🗳️")), sure=8)

    @commands.hybrid_command(name="oylaatla", aliases=["voteskip", "oyla", "vs"],
                             description="Şarkıyı atlamak için oy verir")
    async def oylaatla(self, ctx):
        metin = await self._atla_istegi(ctx.author, self.oynaticilar.get(ctx.guild.id), oy_kullan=True)
        await self._yanit(ctx, metin, gizli=False, sure=10)

    @commands.hybrid_command(name="onceki", aliases=["önceki", "previous", "prev", "back"],
                             description="Önceki şarkıya döner")
    async def onceki(self, ctx):
        oyn = self.oynaticilar.get(ctx.guild.id)
        hata = self._kontrol_hatasi(ctx.author)
        if hata:
            return await self._yanit(ctx, hata)
        if oyn is None:
            return await self._yanit(ctx, _t("❌ Çalan bir şey yok."))
        sonuc = await oyn.onceki()
        if sonuc is None:
            return await self._yanit(ctx, _t("⏮️ Geçmişte önceki bir şarkı yok."))
        if sonuc == "mesgul":
            return await self._yanit(ctx, _t("⏳ Geçiş sürüyor, bir saniye…"))
        await self._yanit(ctx, _t("⏮️ **{gosterim}** tekrar çalıyor.", gosterim=sonuc.gosterim(60)), gizli=False, sure=6)

    @commands.hybrid_command(name="duraklat", aliases=["pause"], description="Müziği duraklatır")
    async def duraklat(self, ctx):
        hata = self._kontrol_hatasi(ctx.author)
        if hata:
            return await self._yanit(ctx, hata)
        vc = ctx.guild.voice_client
        if not vc or not vc.is_playing():
            return await self._yanit(ctx, _t("❌ Çalan bir şey yok."))
        vc.pause()
        await self.panel_guncelle(ctx.guild.id, hemen=True)
        await self._yanit(ctx, _t("⏸️ Duraklatıldı."), gizli=False, sure=5)

    @commands.hybrid_command(name="devam", aliases=["resume", "surdur", "sürdür"], description="Duraklatılan müziği sürdürür")
    async def devam(self, ctx):
        hata = self._kontrol_hatasi(ctx.author)
        if hata:
            return await self._yanit(ctx, hata)
        vc = ctx.guild.voice_client
        if not vc or not vc.is_paused():
            return await self._yanit(ctx, _t("❌ Duraklatılmış bir şey yok."))
        vc.resume()
        oyn = self.oynaticilar.get(ctx.guild.id)
        if oyn:
            oyn.otomatik_duraklatildi = False
        await self.panel_guncelle(ctx.guild.id, hemen=True)
        await self._yanit(ctx, _t("▶️ Devam ediyor."), gizli=False, sure=5)

    @commands.hybrid_command(name="durdur", aliases=["stop"],
                             description="Çalmayı durdurur ve kuyruğu temizler (7/24 kapalıysa kanaldan ayrılır)")
    async def durdur(self, ctx):
        hata = self._kontrol_hatasi(ctx.author)
        if hata:
            return await self._yanit(ctx, hata)
        if ctx.guild.voice_client is None and ctx.guild.id not in self.oynaticilar:
            return await self._yanit(ctx, _t("❌ Zaten çalan bir şey yok."))
        await self._yanit(ctx, await self._durdur(ctx.guild), gizli=False, sure=8)

    async def _sar_ortak(self, ctx, metin, isaret_zorla=None):
        hata = self._kontrol_hatasi(ctx.author)
        if hata:
            return await self._yanit(ctx, hata)
        oyn = self.oynaticilar.get(ctx.guild.id)
        if oyn is None or oyn.simdiki is None:
            return await self._yanit(ctx, _t("❌ Çalan bir şey yok."))
        if oyn.simdiki.canli:
            return await self._yanit(ctx, _t("🔴 Canlı yayında sarılamaz."))
        saniye, isaret = sure_coz(metin)
        if saniye is None:
            return await self._yanit(ctx, _t("❌ Geçersiz süre. Örnekler: `1:30`, `90`, `+30`, `-10`, `2m15s`"))
        if isaret_zorla is not None:
            isaret = isaret_zorla
        hedef = hedef_konum(oyn.konum(), saniye, isaret, oyn.simdiki.sure)
        await ctx.defer()
        if await oyn.yeniden_baslat(hedef):
            await self.panel_guncelle(ctx.guild.id, hemen=True)
            ok = "⏩" if isaret >= 0 else "⏪"
            await self._yanit(ctx, _t("{ok} `{sure_metni}` konumuna sarıldı.", ok=ok, sure_metni=sure_metni(hedef)), gizli=False, sure=5)
        else:
            await self._yanit(ctx, _t("❌ Sarma başarısız oldu."))

    @commands.hybrid_command(name="sar", aliases=["seek"], description="Şarkıda belirli bir ana sarar (1:30, +30, -10)")
    @app_commands.describe(zaman="Örnek: 1:30 (mutlak), +30 (ileri), -10 (geri)")
    async def sar(self, ctx, zaman: str):
        await self._sar_ortak(ctx, zaman)

    @commands.hybrid_command(name="ileri", aliases=["ff", "forward"], description="Şarkıyı ileri sarar (varsayılan 10 sn)")
    @app_commands.describe(saniye="Kaç saniye (ya da 1:00 gibi)")
    async def ileri(self, ctx, saniye: str = "10"):
        await self._sar_ortak(ctx, saniye.lstrip("+-"), isaret_zorla=1)

    @commands.hybrid_command(name="geri", aliases=["rewind", "rw"], description="Şarkıyı geri sarar (varsayılan 10 sn)")
    @app_commands.describe(saniye="Kaç saniye (ya da 1:00 gibi)")
    async def geri(self, ctx, saniye: str = "10"):
        await self._sar_ortak(ctx, saniye.lstrip("+-"), isaret_zorla=-1)

    # ══════════════════════════════════════════════
    #  KOMUTLAR — KUYRUK
    # ══════════════════════════════════════════════

    @commands.hybrid_command(name="kuyruk", aliases=["liste", "queue", "q", "sira", "sıra"],
                             description="Kuyruğu sayfa sayfa gösterir")
    async def kuyruk(self, ctx):
        oyn = self.oynaticilar.get(ctx.guild.id)
        if oyn is None or (oyn.simdiki is None and oyn.kuyruk.bos_mu()):
            return await self._yanit(ctx, _t("🎶 Kuyruk boş. `/oynat` ile şarkı ekle."))
        gorunum = SayfaGorunumu(lambda s: kuyruk_embedi(oyn, s), kullanici_id=ctx.author.id)
        gorunum.mesaj = await self._yanit(ctx, embed=gorunum.ilk(), view=gorunum, gizli=True, sure=180)

    @commands.hybrid_command(name="kaldir", aliases=["kaldır", "remove", "rm"], description="Kuyruktan parça kaldırır")
    @app_commands.describe(numara="Kaldırılacak parçanın kuyruk numarası")
    async def kaldir(self, ctx, numara: str):
        oyn = self.oynaticilar.get(ctx.guild.id)
        n = _tam_sayi(numara)
        if oyn is None or oyn.kuyruk.bos_mu():
            return await self._yanit(ctx, _t("❌ Kuyruk boş."))
        if n is None or not 1 <= n <= len(oyn.kuyruk):
            return await self._yanit(ctx, _t("❌ Geçersiz numara (1-{len}).", len=len(oyn.kuyruk)))
        parca = oyn.kuyruk[n - 1]
        if parca.isteyen_id != ctx.author.id:
            hata = self._kontrol_hatasi(ctx.author)
            if hata:
                return await self._yanit(ctx, hata + _t(" (Kendi eklediğin parçaları kaldırabilirsin.)"))
        oyn.kuyruk.kaldir(n)
        oyn._on_coz_baslat()
        oyn._isitma_planla()
        await self.panel_guncelle(ctx.guild.id)
        await self._yanit(ctx, _t("🗑️ **{gosterim}** kaldırıldı.", gosterim=parca.gosterim(60)), gizli=False, sure=6)

    @commands.hybrid_command(name="tasi", aliases=["taşı", "move", "mv"], description="Kuyrukta parçanın yerini değiştirir")
    @app_commands.describe(kimden="Taşınacak parçanın numarası", kime="Yeni konumu")
    async def tasi(self, ctx, kimden: str, kime: str):
        hata = self._kontrol_hatasi(ctx.author)
        if hata:
            return await self._yanit(ctx, hata)
        oyn = self.oynaticilar.get(ctx.guild.id)
        a, b = _tam_sayi(kimden), _tam_sayi(kime)
        if oyn is None or oyn.kuyruk.bos_mu():
            return await self._yanit(ctx, _t("❌ Kuyruk boş."))
        try:
            parca = oyn.kuyruk.tasi(a or 0, b or 0)
        except IndexError:
            return await self._yanit(ctx, _t("❌ Geçersiz numara (1-{len}).", len=len(oyn.kuyruk)))
        oyn._on_coz_baslat()
        oyn._isitma_planla()
        await self.panel_guncelle(ctx.guild.id)
        await self._yanit(ctx, f"↕️ **{parca.gosterim(50)}** → #{b}", gizli=False, sure=6)

    @commands.hybrid_command(name="karistir", aliases=["karıştır", "shuffle"], description="Kuyruğu karıştırır")
    async def karistir(self, ctx):
        hata = self._kontrol_hatasi(ctx.author)
        if hata:
            return await self._yanit(ctx, hata)
        oyn = self.oynaticilar.get(ctx.guild.id)
        if oyn is None or len(oyn.kuyruk) < 2:
            return await self._yanit(ctx, _t("❌ Karıştırmak için kuyrukta en az 2 parça olmalı."))
        oyn.kuyruk.karistir()
        oyn._on_coz_baslat()
        oyn._isitma_planla()
        await self.panel_guncelle(ctx.guild.id)
        await self._yanit(ctx, _t("🔀 Kuyruk karıştırıldı!"), gizli=False, sure=5)

    @commands.hybrid_command(name="temizle", aliases=["clear", "kuyruktemizle"],
                             description="Kuyruğu temizler (DJ değilsen sadece kendi eklediklerini)")
    async def temizle(self, ctx):
        oyn = self.oynaticilar.get(ctx.guild.id)
        if oyn is None or oyn.kuyruk.bos_mu():
            return await self._yanit(ctx, _t("❌ Kuyruk zaten boş."))
        if self._kontrol_hatasi(ctx.author):
            n = oyn.kuyruk.kullanicinin_parcalarini_kaldir(ctx.author.id)
            metin = _t("🧹 Kendi eklediğin **{n}** parça kaldırıldı.", n=n)
        else:
            n = oyn.kuyruk.temizle()
            metin = _t("🧹 Kuyruk temizlendi ({n} parça).", n=n)
        oyn._on_coz_baslat()
        oyn._isitma_planla()
        await self.panel_guncelle(ctx.guild.id)
        await self._yanit(ctx, metin, gizli=False, sure=6)

    @commands.hybrid_command(name="dongu", aliases=["döngü", "tekrar", "loop", "repeat"],
                             description="Döngü modu: kapalı / şarkı / kuyruk")
    @app_commands.describe(mod="kapalı, şarkı ya da kuyruk (boş: sıradaki moda geç)")
    async def dongu(self, ctx, mod: str = None):
        hata = self._kontrol_hatasi(ctx.author)
        if hata:
            return await self._yanit(ctx, hata)
        oyn = self.oynatici_al(ctx.guild.id)
        if mod:
            yeni = DONGU_TAKMA_ADLAR.get(mod.casefold())
            if yeni is None:
                return await self._yanit(ctx, _t("❌ Mod: `kapalı`, `şarkı` ya da `kuyruk`"))
        else:
            yeni = dongu_sonraki_mod(oyn.dongu)
        oyn.dongu = yeni
        oyn._on_coz_baslat()
        oyn._isitma_planla()
        await self.panel_guncelle(ctx.guild.id)
        emoji = {"kapali": "➡️", "sarki": "🔂", "kuyruk": "🔁"}[yeni]
        await self._yanit(ctx, _t("{emoji} Döngü: **{DONGU_ETIKET}**", emoji=emoji, DONGU_ETIKET=_t(DONGU_ETIKET[yeni])), gizli=False, sure=5)

    @dongu.autocomplete("mod")
    async def _dongu_ac(self, interaction, current: str):
        return [app_commands.Choice(name=_t(DONGU_ETIKET[m]), value=m) for m in DONGU_SIRASI
                if current.casefold() in _t(DONGU_ETIKET[m]).casefold() or current.casefold() in m]

    @commands.hybrid_command(name="ses", aliases=["volume", "vol"], description="Ses seviyesi (0-150, sunucuya özel hatırlanır)")
    @app_commands.describe(seviye="0-150 arası, ya da +10 / -10")
    async def ses(self, ctx, seviye: str = None):
        oyn = self.oynaticilar.get(ctx.guild.id)
        mevcut = oyn.ses if oyn else (mdb.muzik_ayar_al(ctx.guild.id).get('son_ses') or mdb.muzik_ayar_al(ctx.guild.id)['varsayilan_ses'])
        if seviye is None:
            return await self._yanit(ctx, _t("🔊 Ses: **%{mevcut}**  (değiştirmek: `/ses 80`, `/ses +10`)", mevcut=mevcut))
        hata = self._kontrol_hatasi(ctx.author)
        if hata:
            return await self._yanit(ctx, hata)
        metin = seviye.strip().rstrip("%").lstrip("%")
        goreli = metin[:1] in "+-"
        sayi = _tam_sayi(metin)
        if sayi is None:
            return await self._yanit(ctx, _t("❌ 0-150 arası bir sayı gir."))
        hedef = mevcut + sayi if goreli else sayi
        if not goreli and not mdb.SES_MIN <= hedef <= mdb.SES_MAX:
            return await self._yanit(ctx, _t("❌ Ses {SES_MIN}-{SES_MAX} arası olmalı.", SES_MIN=mdb.SES_MIN, SES_MAX=mdb.SES_MAX))
        if oyn is None:
            hedef = max(mdb.SES_MIN, min(mdb.SES_MAX, hedef))
            mdb.muzik_ayar_guncelle(ctx.guild.id, son_ses=hedef)
        else:
            hedef = await self._ses_uygula(oyn, hedef)
        emoji = "🔇" if hedef == 0 else "🔉" if hedef < 60 else "🔊"
        await self._yanit(ctx, _t("{emoji} Ses **%{hedef}**", emoji=emoji, hedef=hedef) + (_t(" · 📢 %100 üstü sesi bozabilir") if hedef > 100 else ""),
                          gizli=False, sure=5)

    @commands.hybrid_command(name="simdi", aliases=["şimdi", "np", "nowplaying", "simdiki", "şimdiki", "calan"],
                             description="Şu an çalanı ve kontrol panelini gösterir (paneli bu kanala taşır)")
    async def simdi(self, ctx):
        oyn = self.oynaticilar.get(ctx.guild.id)
        if oyn is None or oyn.simdiki is None:
            return await self._yanit(ctx, _t("🎶 Şu an bir şey çalmıyor."))
        if self._istek_kanali(ctx.guild) is not None:
            return await self._yanit(ctx, embed=calma_embedi(oyn))
        await self._panel_tasi(ctx.guild, ctx.channel)
        if ctx.interaction is not None:
            await self._yanit(ctx, _t("🎛️ Kontrol paneli bu kanala taşındı."))

    @commands.hybrid_command(name="muzikgecmis", aliases=["mgecmis", "history", "sonçalanlar", "soncalanlar"],
                             description="Bu sunucuda son çalınan şarkılar")
    async def muzikgecmis(self, ctx):
        oyn = self.oynaticilar.get(ctx.guild.id)
        if oyn is None or len(oyn.gecmis) == 0:
            return await self._yanit(ctx, _t("🕘 Henüz bir şey çalınmadı."))
        await self._yanit(ctx, embed=gecmis_embedi(oyn), gizli=True, sure=60)

    # ══════════════════════════════════════════════
    #  KOMUTLAR — FİLTRELER
    # ══════════════════════════════════════════════

    async def _filtre_komutu(self, ctx, secim, deger=None):
        oyn = self.oynaticilar.get(ctx.guild.id)
        if not secim:
            aktif = oyn.filtre.ozet() if oyn else []
            satirlar = [f"{emoji} `{k}` — {_t(etiket)}: {_t(aciklama)}" for k, (etiket, emoji, aciklama) in FILTRE_SECENEKLERI.items()]
            embed = discord.Embed(color=MUZIK_RENGI, title=_t("🎛️ Filtreler"),
                                  description=_t("**Aktif:** {d1}\n\n", d1=', '.join(aktif) if aktif else 'Yok') + "\n".join(satirlar))
            embed.set_footer(text=_t("Kullanım: /filtre nightcore · /filtre bas 3 · /filtre hiz 1.25 · /filtre kapat"))
            return await self._yanit(ctx, embed=embed, sure=60)
        hata = self._kontrol_hatasi(ctx.author)
        if hata:
            return await self._yanit(ctx, hata)
        if oyn is None or oyn.simdiki is None:
            return await self._yanit(ctx, _t("❌ Çalan bir şey yok."))
        anahtar = _FILTRE_TAKMA.get(secim.casefold(), secim.casefold())
        if anahtar not in FILTRE_SECENEKLERI and anahtar not in ("bas", "bas0", "hiz", "bassboost"):
            return await self._yanit(ctx, _t("❌ Bilinmeyen filtre: `{secim}` — liste için `/filtre`", secim=secim))
        await ctx.defer()
        try:
            metin = await self._filtre_uygula(oyn, anahtar, deger)
        except ValueError:
            return await self._yanit(ctx, _t("❌ Geçersiz değer."))
        aktif = oyn.filtre.ozet()
        await self._yanit(ctx, f"🎛️ {metin}" + (_t("\n-# Aktif: {join}", join=', '.join(aktif)) if aktif else ""), gizli=False, sure=8)

    # Efekt komutları (/filtre, !bassboost, !nightcore, !vaporwave, !8d, !karaoke, !hiz) sahibin isteğiyle
    # kaldırıldı (2026-09-13) — varsayılan "normal" ses. Sadece ses dengeleme kalıyor (+ /muzikayar normalizasyon).
    @commands.hybrid_command(name="normalizasyon", aliases=["normalize", "norm", "dengele"],
                             description="Ses dengeleme (şarkılar arası ses farkını eşitler) aç/kapat")
    async def normalizasyon(self, ctx):
        """Ses dengeleme (şarkılar arası ses farkını eşitler) aç/kapat."""
        await self._filtre_komutu(ctx, "normalizasyon")

    @commands.hybrid_command(name="otomatik", aliases=["autoplay", "radyo", "ap"],
                             description="Otomatik oynatma: kuyruk bitince benzer şarkılarla devam eder")
    @app_commands.describe(durum="aç / kapat (boş: değiştir)")
    async def otomatik(self, ctx, durum: str = None):
        hata = self._kontrol_hatasi(ctx.author)
        if hata:
            return await self._yanit(ctx, hata)
        oyn = self.oynatici_al(ctx.guild.id)
        try:
            yeni = _ac_kapat(durum, oyn.otomatik)
        except ValueError:
            return await self._yanit(ctx, _t("❌ `aç` ya da `kapat` yaz."))
        oyn.otomatik = yeni
        mdb.muzik_ayar_guncelle(ctx.guild.id, otomatik_oynatma=int(yeni))
        if not yeni:
            oyn.kuyruk.otomatikleri_kaldir()
        oyn._on_coz_baslat()
        await self.panel_guncelle(ctx.guild.id)
        await self._yanit(ctx, _t("📻 Otomatik oynatma: **{d1}**", d1=_t("Açık") if yeni else _t("Kapalı"))
                          + (_t(" — kuyruk bitince benzer şarkılar çalacak.") if yeni else ""), gizli=False, sure=6)

    # ══════════════════════════════════════════════
    #  KOMUTLAR — BAĞLANTI
    # ══════════════════════════════════════════════

    @commands.hybrid_command(name="katil", aliases=["katıl", "join", "gel", "zorla"], description="Botu ses kanalına çağırır")
    async def katil(self, ctx):
        oyn, hata = await self._sese_baglan(ctx.author, ctx.channel)
        if hata:
            return await self._yanit(ctx, hata)
        await self._yanit(ctx, _t("✅ **{name}** kanalındayım. `/oynat` ile başla!", name=ctx.author.voice.channel.name), gizli=False, sure=8)

    @commands.hybrid_command(name="cik", aliases=["çık", "leave", "dc", "disconnect", "bye"],
                             description="Botu ses kanalından çıkarır (kuyruk temizlenir)")
    async def cik(self, ctx):
        if ctx.guild.voice_client is None and ctx.guild.id not in self.oynaticilar:
            return await self._yanit(ctx, _t("❌ Zaten bir ses kanalında değilim."))
        hata = self._kontrol_hatasi(ctx.author)
        if hata:
            return await self._yanit(ctx, hata)
        await self._cleanup_guild(ctx.guild.id)
        await self._yanit(ctx, _t("👋 Görüşürüz!"), gizli=False, sure=5)

    # ══════════════════════════════════════════════
    #  KOMUTLAR — KİŞİSEL ÇALMA LİSTELERİ
    # ══════════════════════════════════════════════

    @commands.hybrid_group(name="calmalistesi", aliases=["cl", "playlist", "pl", "listem", "listelerim"],
                           fallback="goster", invoke_without_command=True,
                           description="Çalma listeleri (kişisel ve paylaşılan listeler)")
    @app_commands.describe(ad="Liste adı (boş: tüm listeler)")
    async def calmalistesi(self, ctx, *, ad: str = None):
        uid = ctx.author.id
        if not ad:
            kisisel = mdb.listeleri_al(uid)
            genel = mdb.genel_listeleri_al(haric_kullanici_id=uid)
            if not kisisel and not genel:
                return await self._yanit(ctx, _t("📂 Henüz kayıtlı liste yok. Çalan kuyruğu kaydet: `/calmalistesi kaydet <ad>` · ya da panelde ❤️ ile favorilere ekle."))
            embed = discord.Embed(color=MUZIK_RENGI, title=_t("📂 Çalma Listeleri"))
            alanlar = []
            if kisisel:
                alanlar.append(_t("👤 **Kişisel Listelerin:**\n") + "\n".join(
                    f"• **{discord.utils.escape_markdown(lad)}** — {n} parça"
                    + (f" · {sure_metni(sure)}" if sure else "") for _, lad, n, sure in kisisel
                ))
            if genel:
                alanlar.append(_t("⭐ **Genel / Paylaşılan Listeler:**\n") + "\n".join(
                    f"• **{discord.utils.escape_markdown(lad)}** — {n} parça"
                    + (f" · {sure_metni(sure)}" if sure else "") for _, lad, n, sure, _ in genel
                ))
            embed.description = "\n\n".join(alanlar)
            embed.set_footer(text=_t("Çal: /calmalistesi oynat <ad> · İçerik: /calmalistesi goster <ad>"))
            return await self._yanit(ctx, embed=embed, sure=60)

        bulunan = mdb.liste_bul_ayrintili(uid, ad, genel_ara=True)
        if bulunan is None:
            return await self._yanit(ctx, _t("❌ **{ad}** adında bir liste bulunamadı.", ad=ad))
        liste_id, sahip_id, liste_adi = bulunan
        parcalar = mdb.liste_parcalari(liste_id)

        def uretici(sayfa, boy=15):
            n = max(1, (len(parcalar) + boy - 1) // boy)
            sayfa = max(0, min(sayfa, n - 1))
            satirlar = []
            for i, p in enumerate(parcalar[sayfa * boy:(sayfa + 1) * boy], start=sayfa * boy + 1):
                baslik = discord.utils.escape_markdown((p['baslik'] or p['sorgu'])[:60])
                satirlar.append(f"`{i:>3}.` " + (f"[{baslik}]({p['url']})" if p.get('url') else baslik)
                                + (f" `{sure_metni(p['sure'])}`" if p.get('sure') else ""))
            etiket = _t(" (Sana ait)") if sahip_id == uid else (_t(" (⭐ Sunucu Listesi)") if sahip_id == SAHIP_ID else _t(" (Paylaşılan)"))
            embed = discord.Embed(color=MUZIK_RENGI, title=f"📂 {liste_adi}{etiket}", description="\n".join(satirlar) or _t("*Boş liste*"))
            embed.set_footer(text=_t("Sayfa {d1}/{n} • {len} parça", d1=sayfa + 1, n=n, len=len(parcalar)))
            return embed, n
        gorunum = SayfaGorunumu(uretici, kullanici_id=uid)
        gorunum.mesaj = await self._yanit(ctx, embed=gorunum.ilk(), view=gorunum, sure=180)

    @calmalistesi.command(name="kaydet", description="Çalan şarkı + kuyruğu kişisel listene kaydeder (aynı ad varsa üzerine yazar)")
    @app_commands.describe(ad="Liste adı")
    async def cl_kaydet(self, ctx, *, ad: str):
        oyn = self.oynaticilar.get(ctx.guild.id)
        parcalar = ([oyn.simdiki] if oyn and oyn.simdiki else []) + (list(oyn.kuyruk) if oyn else [])
        parcalar = [p for p in parcalar if not p.otomatik] or parcalar
        if not parcalar:
            return await self._yanit(ctx, _t("❌ Kaydedilecek bir şey yok (çalan şarkı / kuyruk boş)."))
        try:
            liste_id = mdb.liste_olustur(ctx.author.id, ad)
        except mdb.ListeHatasi as h:
            return await self._yanit(ctx, f"❌ {h}")
        n = mdb.listeye_parca_ekle(liste_id, [p.veritabani_bicimi() for p in parcalar], bastan_yaz=True)
        await self._yanit(ctx, _t("💾 **{ad}** listesine **{n}** parça kaydedildi.", ad=ad, n=n))

    @calmalistesi.command(name="ekle", description="Listene şarkı ekler (boş: çalan şarkı)")
    @app_commands.describe(ad="Liste adı", sorgu="Şarkı adı / link (boş: çalan şarkı)")
    async def cl_ekle(self, ctx, ad: str, *, sorgu: str = None):
        try:
            liste_id = mdb.liste_olustur(ctx.author.id, ad)
        except mdb.ListeHatasi as h:
            return await self._yanit(ctx, f"❌ {h}")
        if not sorgu:
            oyn = self.oynaticilar.get(ctx.guild.id)
            if oyn is None or oyn.simdiki is None:
                return await self._yanit(ctx, _t("❌ Çalan bir şey yok — eklemek için şarkı adı/link yaz."))
            parcalar = [oyn.simdiki]
        else:
            await ctx.defer(ephemeral=True)
            try:
                _, parcalar, _, _ = await self._girdiden_parcalar(sorgu[:SORGU_UZUNLUK], mdb.LISTE_PARCA_LIMITI)
            except (CozmeHatasi, IsciHatasi, asyncio.TimeoutError) as e:
                return await self._yanit(ctx, _t("❌ Eklenemedi: {sebep}", sebep=_t(hata_sebebi(e).sebep)))
        n = mdb.listeye_parca_ekle(liste_id, [p.veritabani_bicimi() for p in parcalar])
        if not n:
            return await self._yanit(ctx, _t("❌ Liste dolu ({LISTE_PARCA_LIMITI} parça).", LISTE_PARCA_LIMITI=mdb.LISTE_PARCA_LIMITI))
        await self._yanit(ctx, _t("➕ **{ad}** listesine {n} parça eklendi", ad=ad, n=n) + (f": **{parcalar[0].gosterim(50)}**" if n == 1 else "."))

    @calmalistesi.command(name="oynat", description="Çalma listesini kuyruğa ekler")
    @app_commands.describe(ad="Liste adı (varsayılan: Favoriler)", karistir="Karıştırarak ekle (evet/hayır)")
    async def cl_oynat(self, ctx, ad: str = "Favoriler", karistir: str = None):
        bulunan = mdb.liste_bul_ayrintili(ctx.author.id, ad, genel_ara=True)
        if bulunan is None:
            return await self._yanit(ctx, _t("❌ **{ad}** adında bir liste bulunamadı.", ad=ad))
        await self._calmalistesi_oynat_dahili(ctx, bulunan, karistir=karistir, basa=False)

    @calmalistesi.command(name="cikar", description="Listenden bir parçayı çıkarır")
    @app_commands.describe(ad="Liste adı", numara="Parça numarası")
    async def cl_cikar(self, ctx, ad: str, numara: str):
        liste_id = mdb.liste_bul(ctx.author.id, ad, genel_ara=False)
        if liste_id is None:
            return await self._yanit(ctx, _t("❌ **{ad}** adında sana ait bir liste yok.", ad=ad))
        baslik = mdb.listeden_parca_cikar(liste_id, _tam_sayi(numara) or 0)
        await self._yanit(ctx, _t("🗑️ **{baslik}** listeden çıkarıldı.", baslik=baslik) if baslik else _t("❌ Geçersiz numara."))

    @calmalistesi.command(name="sil", description="Kişisel listeni tamamen siler")
    @app_commands.describe(ad="Liste adı")
    async def cl_sil(self, ctx, *, ad: str):
        liste_id = mdb.liste_bul(ctx.author.id, ad, genel_ara=False)
        if liste_id is None or not mdb.liste_sil(ctx.author.id, liste_id):
            return await self._yanit(ctx, _t("❌ **{ad}** adında sana ait bir liste yok.", ad=ad))
        await self._yanit(ctx, _t("🗑️ **{ad}** listesi silindi.", ad=ad))

    async def _liste_ac(self, interaction, current: str):
        c = (current or "").casefold()
        secenekler = []
        gorulen = set()

        # 1. Kullanıcının kendi listeleri
        for _, lad, n, _ in mdb.listeleri_al(interaction.user.id):
            if not c or c in lad.casefold():
                secenekler.append(app_commands.Choice(name=f"👤 {lad} ({n} parça)"[:100], value=lad))
                gorulen.add(lad.casefold())

        # 2. Genel / paylaşılan listeler
        for _, lad, n, _, sahip_id in mdb.genel_listeleri_al(haric_kullanici_id=interaction.user.id):
            if lad.casefold() in gorulen:
                continue
            if not c or c in lad.casefold():
                rozet = "⭐" if sahip_id == SAHIP_ID else "🌐"
                secenekler.append(app_commands.Choice(name=f"{rozet} {lad} ({n} parça)"[:100], value=lad))
                gorulen.add(lad.casefold())

        return secenekler[:25]

    async def _kisisel_liste_ac(self, interaction, current: str):
        c = (current or "").casefold()
        return [app_commands.Choice(name=f"{lad} ({n} parça)"[:100], value=lad)
                for _, lad, n, _ in mdb.listeleri_al(interaction.user.id) if not c or c in lad.casefold()][:25]

    calmalistesi.autocomplete("ad")(_liste_ac)
    cl_oynat.autocomplete("ad")(_liste_ac)
    cl_ekle.autocomplete("ad")(_kisisel_liste_ac)
    cl_cikar.autocomplete("ad")(_kisisel_liste_ac)
    cl_sil.autocomplete("ad")(_kisisel_liste_ac)

    # ══════════════════════════════════════════════
    #  KOMUTLAR — SUNUCU AYARLARI (yönetici / DJ)
    # ══════════════════════════════════════════════

    def _ayarlar_embedi(self, guild):
        a = mdb.muzik_ayar_al(guild.id)
        embed = discord.Embed(color=MUZIK_RENGI, title=_t("⚙️ Müzik Ayarları"))
        embed.add_field(name=_t("🎚️ DJ rolü"), value=f"<@&{a['dj_rol_id']}>" if a['dj_rol_id'] else _t("Kapalı (herkes kontrol eder)"))
        oylama = bool(a['dj_rol_id'] or a['oylama_aktif'])
        embed.add_field(name=_t("🗳️ Oylamalı atla"),
                        value=f"{_t("Açık") if oylama else _t("Kapalı")} · %{int(a['oylama_orani'] * 100)}"
                              + (_t(" (DJ rolü ayarlı → otomatik)") if a['dj_rol_id'] and not a['oylama_aktif'] else ""))
        embed.add_field(name=_t("🔊 Ses"), value=_t("Varsayılan %{a} · Son %{d3}", a=a['varsayilan_ses'], d3=a['son_ses'] if a['son_ses'] is not None else '—'))
        embed.add_field(name=_t("🌙 7/24 modu"), value=_t("Açık") if a['surekli_mod'] else _t("Kapalı"))
        embed.add_field(name=_t("📻 Otomatik oynatma"), value=_t("Açık") if a['otomatik_oynatma'] else _t("Kapalı"))
        embed.add_field(name=_t("⏱️ Boşta ayrılma"), value=_t("{d0} dk {d2} sn", d0=a['bosta_zaman_asimi'] // 60, d2=a['bosta_zaman_asimi'] % 60))
        embed.add_field(name=_t("📶 Normalizasyon"), value=_t("Açık") if a['normalizasyon'] else _t("Kapalı"))
        embed.add_field(name=_t("📨 İstek kanalı"), value=f"<#{a['istek_kanal_id']}>" if a['istek_kanal_id'] else "Yok")
        embed.set_footer(text=_t("Değiştir: /muzikayar dj · oylama · varsayilanses · surekli · otomatik · zamanasimi · istekkanali · normalizasyon"))
        return embed

    async def _ayar_kontrol(self, ctx, sadece_yonetici=False):
        if self._ayar_yetkisi(ctx.author, sadece_yonetici):
            return True
        await self._yanit(ctx, _t("🚫 Bu ayar için sunucu yöneticisi (Yönetici / Sunucuyu Yönet)")
                          + ("" if sadece_yonetici else _t(" ya da DJ rolü")) + _t(" gerekli."))
        return False

    @commands.hybrid_group(name="muzikayar", aliases=["müzikayar", "muzikayarlar", "müzikayarlar"],
                           fallback="goster", invoke_without_command=True, description="Sunucunun müzik ayarları")
    async def muzikayar(self, ctx):
        await self._yanit(ctx, embed=self._ayarlar_embedi(ctx.guild), sure=60)

    @muzikayar.command(name="dj", description="DJ rolünü ayarlar (boş: kapatır). DJ'ler kontrol komutlarını kullanır.")
    @app_commands.describe(rol="DJ rolü (boş bırak = DJ sistemini kapat)")
    async def ayar_dj(self, ctx, rol: discord.Role = None):
        if not await self._ayar_kontrol(ctx, sadece_yonetici=True):
            return
        mdb.muzik_ayar_guncelle(ctx.guild.id, dj_rol_id=rol.id if rol else None)
        await self._yanit(ctx, _t("🎚️ DJ rolü: {mention}. Artık kontrol komutları DJ'lere/yöneticilere özel, diğerleri oyla atlar.", mention=rol.mention) if rol else _t("🎚️ DJ sistemi kapatıldı — herkes kontrol edebilir."))

    @muzikayar.command(name="oylama", description="Oylamalı atla: aç / kapat ya da gereken oran (ör. 60)")
    @app_commands.describe(deger="aç, kapat ya da yüzde (10-100)")
    async def ayar_oylama(self, ctx, deger: str = None):
        if not await self._ayar_kontrol(ctx):
            return
        a = mdb.muzik_ayar_al(ctx.guild.id)
        sayi = _tam_sayi(str(deger or "").rstrip("%")) if deger else None
        if sayi is not None:
            if not 10 <= sayi <= 100:
                return await self._yanit(ctx, _t("❌ Oran %10-%100 arası olmalı."))
            mdb.muzik_ayar_guncelle(ctx.guild.id, oylama_orani=sayi / 100, oylama_aktif=1)
            return await self._yanit(ctx, _t("🗳️ Oylamalı atla açık — dinleyicilerin **%{sayi}**'i gerekli.", sayi=sayi))
        try:
            yeni = _ac_kapat(deger, bool(a['oylama_aktif']))
        except ValueError:
            return await self._yanit(ctx, _t("❌ `aç`, `kapat` ya da bir yüzde yaz."))
        mdb.muzik_ayar_guncelle(ctx.guild.id, oylama_aktif=int(yeni))
        await self._yanit(ctx, _t("🗳️ Oylamalı atla: **{d1}**", d1=_t("Açık") if yeni else _t("Kapalı"))
                          + (_t(" (DJ rolü ayarlı olduğu için DJ olmayanlar yine oyla atlar)") if not yeni and a['dj_rol_id'] else ""))

    @muzikayar.command(name="varsayilanses", description="Yeni oturumların başlangıç sesi (0-150)")
    @app_commands.describe(seviye="0-150")
    async def ayar_ses(self, ctx, seviye: str):
        if not await self._ayar_kontrol(ctx):
            return
        n = _tam_sayi(seviye.rstrip("%"))
        if n is None or not mdb.SES_MIN <= n <= mdb.SES_MAX:
            return await self._yanit(ctx, _t("❌ 0-150 arası bir sayı gir."))
        mdb.muzik_ayar_guncelle(ctx.guild.id, varsayilan_ses=n, son_ses=None)
        await self._yanit(ctx, _t("🔊 Varsayılan ses **%{n}** (hatırlanan son ses sıfırlandı).", n=n))

    @muzikayar.command(name="surekli", aliases=["247", "7/24"], description="7/24 modu: boşta/yalnızken kanaldan ayrılma")
    @app_commands.describe(durum="aç / kapat")
    async def ayar_surekli(self, ctx, durum: str = None):
        if not await self._ayar_kontrol(ctx):
            return
        try:
            yeni = _ac_kapat(durum, bool(mdb.muzik_ayar_al(ctx.guild.id)['surekli_mod']))
        except ValueError:
            return await self._yanit(ctx, _t("❌ `aç` ya da `kapat` yaz."))
        mdb.muzik_ayar_guncelle(ctx.guild.id, surekli_mod=int(yeni))
        await self._yanit(ctx, _t("🌙 7/24 modu: **{d1}**", d1=_t("Açık") if yeni else _t("Kapalı")))

    @muzikayar.command(name="otomatik", description="Otomatik oynatmanın varsayılan durumu")
    @app_commands.describe(durum="aç / kapat")
    async def ayar_otomatik(self, ctx, durum: str = None):
        if not await self._ayar_kontrol(ctx):
            return
        try:
            yeni = _ac_kapat(durum, bool(mdb.muzik_ayar_al(ctx.guild.id)['otomatik_oynatma']))
        except ValueError:
            return await self._yanit(ctx, _t("❌ `aç` ya da `kapat` yaz."))
        mdb.muzik_ayar_guncelle(ctx.guild.id, otomatik_oynatma=int(yeni))
        oyn = self.oynaticilar.get(ctx.guild.id)
        if oyn:
            oyn.otomatik = yeni
            await self.panel_guncelle(ctx.guild.id)
        await self._yanit(ctx, _t("📻 Otomatik oynatma (varsayılan): **{d1}**", d1=_t("Açık") if yeni else _t("Kapalı")))

    @muzikayar.command(name="zamanasimi", description="Boşta ya da kanalda yalnız kalınca kaç dakika sonra ayrılsın")
    @app_commands.describe(sure="Dakika (ör. 3) ya da 90s, 1:30 (30 sn – 60 dk)")
    async def ayar_zamanasimi(self, ctx, sure: str):
        if not await self._ayar_kontrol(ctx):
            return
        metin = sure.strip().casefold()
        if metin.isdigit():
            saniye = int(metin) * 60
        else:
            saniye, _ = sure_coz(metin.replace("dk", "m").replace("sn", "s"))
        if saniye is None or not 30 <= saniye <= 3600:
            return await self._yanit(ctx, _t("❌ 30 saniye ile 60 dakika arası bir süre gir (ör. `3` = 3 dk, `90s`)."))
        mdb.muzik_ayar_guncelle(ctx.guild.id, bosta_zaman_asimi=saniye)
        await self._yanit(ctx, _t("⏱️ Boşta/yalnız kalınca **{sure_metni}** sonra ayrılacağım (7/24 kapalıyken).", sure_metni=sure_metni(saniye)))

    @muzikayar.command(name="normalizasyon", description="Ses normalizasyonunun varsayılan durumu")
    @app_commands.describe(durum="aç / kapat")
    async def ayar_normalizasyon(self, ctx, durum: str = None):
        if not await self._ayar_kontrol(ctx):
            return
        try:
            yeni = _ac_kapat(durum, bool(mdb.muzik_ayar_al(ctx.guild.id)['normalizasyon']))
        except ValueError:
            return await self._yanit(ctx, _t("❌ `aç` ya da `kapat` yaz."))
        mdb.muzik_ayar_guncelle(ctx.guild.id, normalizasyon=int(yeni))
        await self._yanit(ctx, _t("📶 Normalizasyon (varsayılan): **{d1}** — yeni oturumlarda geçerli; şu anki oturum için `/filtre normalizasyon`.", d1=_t("Açık") if yeni else _t("Kapalı")))

    @muzikayar.command(name="istekkanali", description="Şarkı istek kanalı: bu kanala yazılan her mesaj aranıp kuyruğa eklenir")
    @app_commands.describe(kanal="Kanal (boş: yeni kanal oluştur)", kapat="'kapat' yazarsan istek kanalı kapatılır")
    async def ayar_istek(self, ctx, kanal: discord.TextChannel = None, kapat: str = None):
        if not await self._ayar_kontrol(ctx, sadece_yonetici=True):
            return
        if kapat and kapat.casefold() in ("kapat", "kapa", "off"):
            eski = self.paneller.pop(ctx.guild.id, None)
            mdb.muzik_ayar_guncelle(ctx.guild.id, istek_kanal_id=None, panel_kanal_id=None, panel_mesaj_id=None)
            if eski is not None:
                await _sessiz_sil(eski)
            return await self._yanit(ctx, _t("📨 Şarkı istek kanalı kapatıldı."))
        if kanal is None:
            if not ctx.guild.me.guild_permissions.manage_channels:
                return await self._yanit(ctx, _t("❌ Kanal oluşturma yetkim yok — mevcut bir kanal belirt: `/muzikayar istekkanali #kanal`"))
            kanal = await ctx.guild.create_text_channel(
                "🎵・müzik-istek", topic="Şarkı adı ya da link yaz → kuyruğa eklenir. Mesajlar otomatik silinir.",
                reason=f"{self.bot.user.name} müzik istek kanalı ({ctx.author})")
        izin = kanal.permissions_for(ctx.guild.me)
        if not (izin.send_messages and izin.embed_links and izin.manage_messages and izin.read_message_history):
            return await self._yanit(ctx, _t("❌ {mention} kanalında **Mesaj Gönder, Bağlantı Yerleştir, Mesajları Yönet, Mesaj Geçmişini Oku** yetkilerim olmalı.", mention=kanal.mention))
        eski = self.paneller.pop(ctx.guild.id, None)
        if eski is not None:
            await _sessiz_sil(eski)
        mdb.muzik_ayar_guncelle(ctx.guild.id, istek_kanal_id=kanal.id, panel_kanal_id=None, panel_mesaj_id=None)
        await self._panel_yaz_simdi(ctx.guild.id)
        await self._yanit(ctx, _t("📨 Şarkı istek kanalı: {mention} — oraya yazılan her mesaj aranıp kuyruğa eklenir, kontrol paneli de orada durur.", mention=kanal.mention))

    @commands.hybrid_command(name="oygec", aliases=["oyilegec"],
                             description="Oylamalı atlamayı açar/kapatır ya da gereken oranı ayarlar")
    @app_commands.describe(durum="aç / kapat ya da gereken oran (ör. 60)")
    async def oygec(self, ctx, durum: str = None):
        """Oylamalı atlamayı açar/kapatır → /muzikayar oylama"""
        await self.ayar_oylama.callback(self, ctx, durum)

    # ══════════════════════════════════════════════
    #  SAHİP: yt-dlp güncelleme
    # ══════════════════════════════════════════════

    @commands.hybrid_command(name="ytdlpguncelle", aliases=["ytdlp", "ytdlpgüncelle"],
                             description="[Bot Sahibi] yt-dlp'yi venv'de günceller")
    @app_commands.describe(secenek="bekle: çalan şarkılar bitince yeniden başlat")
    @commands.is_owner()
    async def ytdlpguncelle(self, ctx, secenek: str = None):
        """(Sahip) yt-dlp'yi venv'de günceller; yeni sürüm gelirse botu yeniden başlatır (systemd).
        !ytdlpguncelle bekle → çalan müzikler bitince yeniden başlat."""
        mesaj = await ctx.send(_t("⏳ yt-dlp güncelleniyor… (çalışan sürüm: `{calisan_surum}`)", calisan_surum=guncelleyici.calisan_surum()))
        sonuc = await guncelleyici.guncelle(_t("sahip komutu"))
        mdb.bot_durum_yaz(guncelleyici.DURUM_ANAHTARI, time.time())
        if not sonuc['basarili']:
            return await mesaj.edit(content=_t("❌ Güncelleme başarısız:\n```{sonuc}```", sonuc=sonuc['cikti'][-1500:]))
        if not sonuc['degisti']:
            return await mesaj.edit(content=_t("✅ yt-dlp zaten güncel: `{sonuc}`", sonuc=sonuc['yeni']))
        bekle = (secenek or "").casefold() in ("bekle", "sonra", "wait")
        await mesaj.edit(content=_t("✅ yt-dlp `{sonuc}` → `{sonuc2}`. ", sonuc=sonuc['eski'], sonuc2=sonuc['yeni'])
                                 + (_t("Çalan müzikler bitince yeniden başlatacağım.") if bekle else _t("Yeniden başlatılıyor… 🔄")))
        self._arka_gorev(guncelleyici.yeniden_baslat(self.bot, self, aninda=not bekle))

    @tasks.loop(hours=12)
    async def ytdlp_dongusu(self):
        if MUZIK_PROFILI:
            # yt-dlp'yi yalnızca ana bot günceller (aynı venv). İkinci bot, kurulu sürüm değiştiyse boşta kalınca yeniden başlar.
            calisan, kurulu = guncelleyici.calisan_surum(), await asyncio.to_thread(guncelleyici.kurulu_surum)
            if "?" not in (calisan, kurulu) and not guncelleyici.ayni_surum(calisan, kurulu):
                self._arka_gorev(guncelleyici.yeniden_baslat(self.bot, self, aninda=False))
            return
        son = float(mdb.bot_durum_al(guncelleyici.DURUM_ANAHTARI, 0) or 0)
        if time.time() - son < guncelleyici.KONTROL_ARALIGI:
            return
        sonuc = await guncelleyici.guncelle(_t("haftalık kontrol"))
        mdb.bot_durum_yaz(guncelleyici.DURUM_ANAHTARI, time.time())
        if sonuc['degisti']:
            self._arka_gorev(guncelleyici.yeniden_baslat(self.bot, self, aninda=False))

    @ytdlp_dongusu.before_loop
    async def _ytdlp_once(self):
        await self.bot.wait_until_ready()
        await asyncio.sleep(600)   # açılışta hemen değil (yeniden başlatma döngüsüne girmesin)

    # ══════════════════════════════════════════════
    #  DÖNGÜLER
    # ══════════════════════════════════════════════

    @tasks.loop(seconds=PANEL_ARALIGI)
    async def panel_dongusu(self):
        for gid, oyn in list(self.oynaticilar.items()):
            vc = oyn.vc
            if oyn.simdiki is not None and vc is not None and vc.is_playing():
                await self.panel_guncelle(gid)

    @panel_dongusu.before_loop
    async def _panel_once(self):
        await self.bot.wait_until_ready()

    @tasks.loop(seconds=15)
    async def bakim_dongusu(self):
        simdi = time.monotonic()
        for gid, oyn in list(self.oynaticilar.items()):
            dil_ayarla(gid)
            guild = self.bot.get_guild(gid)
            if guild is None:
                await self._cleanup_guild(gid)
                continue
            vc = guild.voice_client
            ayar = mdb.muzik_ayar_al(gid)
            zaman_asimi = ayar['bosta_zaman_asimi']
            surekli = bool(ayar['surekli_mod'])
            if vc is None or not vc.is_connected():
                if simdi - oyn.son_aktivite > 60 and not oyn.mesgul_mu():
                    await self._cleanup_guild(gid)
                continue
            insanlar = self._insanlar(vc)
            if not insanlar:
                if oyn.yalniz_baslangic is None:
                    await self._kanal_durumu(guild)
                elif not surekli and simdi - oyn.yalniz_baslangic > zaman_asimi:
                    await self._cleanup_guild(gid, sebep=_t("👋 Kanalda kimse kalmadı, ayrıldım. Tekrar görüşmek üzere!"))
                continue
            if oyn.simdiki is None and not oyn.caliyor_mu() and not oyn.mesgul_mu() and not surekli \
                    and simdi - oyn.son_aktivite > zaman_asimi:
                await self._cleanup_guild(gid, sebep=_t("💤 Bir süredir boştayım, kanaldan ayrıldım."))

    @bakim_dongusu.before_loop
    async def _bakim_once(self):
        await self.bot.wait_until_ready()

    # ══════════════════════════════════════════════
    #  DİNLEYİCİLER
    # ══════════════════════════════════════════════

    @commands.Cog.listener()
    async def on_ready(self):
        if not self._baslangic_yapildi:
            await self._baslangic_toparla()

    async def _kanal_durumu(self, guild):
        """Kanalda insan kalmadıysa otomatik duraklat; biri gelince otomatik devam."""
        vc = guild.voice_client
        oyn = self.oynaticilar.get(guild.id)
        if oyn is None or vc is None or vc.channel is None:
            return
        insanlar = self._insanlar(vc)
        if not insanlar:
            if oyn.yalniz_baslangic is None:
                oyn.yalniz_baslangic = time.monotonic()
                if vc.is_playing():
                    vc.pause()
                    oyn.otomatik_duraklatildi = True
                    await self.panel_guncelle(guild.id)
        else:
            oyn.yalniz_baslangic = None
            oyn.oylar &= {m.id for m in insanlar}
            if oyn.otomatik_duraklatildi:
                oyn.otomatik_duraklatildi = False
                if vc.is_paused():
                    vc.resume()
                await self.panel_guncelle(guild.id)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        guild = member.guild
        if self.bot.user and member.id == self.bot.user.id:
            if before.channel is not None and after.channel is None:
                if guild.id in self._bilincli_ayrilma:
                    self._bilincli_ayrilma.discard(guild.id)
                    return
                oyn = self.oynaticilar.get(guild.id)
                if oyn is not None and oyn.simdiki is not None and not oyn.kapandi:
                    await self._beklenmedik_ayrilma(guild, before.channel, oyn)
                elif oyn is not None:
                    await self._cleanup_guild(guild.id)
            elif after.channel is not None and before.channel != after.channel:
                await self.panel_guncelle(guild.id)
                await self._kanal_durumu(guild)
            return
        vc = guild.voice_client
        if vc is None or vc.channel is None:
            return
        if vc.channel in (before.channel, after.channel):
            await self._kanal_durumu(guild)

    async def _beklenmedik_ayrilma(self, guild, kanal, oyn):
        """Ses bağlantısı beklenmedik koptu: atıldıysak temizle; ağ kopmasıysa bir kez yeniden bağlan ve kaldığı yerden devam."""
        gid = guild.id
        konum = oyn.konum()
        oyn.nesil += 1   # ölü akışın bitiş callback'i sıradakine geçirmesin
        simdi = time.monotonic()
        if simdi - self._yeniden_baglanma_son.get(gid, 0) < YENIDEN_BAGLANMA_ARALIGI:
            return await self._cleanup_guild(gid, sebep=_t("🔌 Ses bağlantısı koptu."))
        try:
            async for kayit in guild.audit_logs(limit=5, action=discord.AuditLogAction.member_disconnect):
                if (discord.utils.utcnow() - kayit.created_at).total_seconds() < 20:
                    return await self._cleanup_guild(gid, sebep=_t("👋 Ses kanalından çıkarıldım."))
        except (discord.Forbidden, discord.HTTPException):
            pass   # denetim kaydı yetkisi yok → ağ kopması varsay
        self._yeniden_baglanma_son[gid] = simdi
        await asyncio.sleep(3)
        if gid not in self.oynaticilar or oyn.kapandi:
            return
        try:
            eski = guild.voice_client
            if eski is not None:
                await eski.disconnect(force=True)
            await kanal.connect(timeout=20, reconnect=True, self_deaf=True)
        except (asyncio.TimeoutError, discord.ClientException, discord.HTTPException, RuntimeError) as e:
            logger.warning(f"[{gid}] Yeniden bağlanılamadı: {e}")
            return await self._cleanup_guild(gid, sebep=_t("🔌 Ses bağlantısı koptu ve yeniden bağlanamadım."))
        logger.info(f"[{gid}] Ses bağlantısı yenilendi, {konum:.0f}. saniyeden devam ediliyor.")
        if not await oyn.yeniden_baslat(konum):
            await oyn.sonrakine_gec(biten=oyn.simdiki)
        await self.bildir(gid, _t("🔌 Ses bağlantısı koptu — yeniden bağlandım, kaldığı yerden devam ediyorum."))

    @commands.Cog.listener()
    async def on_member_join(self, uye):
        if uye.bot:
            ornekler.uyelik_degisti(uye.guild.id, uye.id)   # yeni müzik botu eklendi → yönlendirme hemen bilsin

    @commands.Cog.listener()
    async def on_member_remove(self, uye):
        if uye.bot:
            ornekler.uyelik_degisti(uye.guild.id, uye.id)

    @commands.Cog.listener()
    async def on_message(self, message):
        """Şarkı istek kanalı: komut olmayan her mesaj arama olarak kuyruğa eklenir, mesaj silinir. (Sadece cache.)"""
        if message.author.bot or message.guild is None:
            return
        if not mdb.istek_kanali_mi(message.guild.id, message.channel.id):
            return
        icerik = message.content.strip()
        if icerik.startswith(PREFIX):
            self._arka_gorev(_sessiz_sil(message, 8))   # komutlar çalışsın, sonra kanal temizlensin
            return
        self._arka_gorev(_sessiz_sil(message, 1.0))
        if not icerik and message.attachments:
            ek = message.attachments[0]
            if (ek.content_type or "").startswith(("audio/", "video/")):
                icerik = ek.url
        if not icerik:
            return
        anahtar = (message.guild.id, message.author.id)
        simdi = time.monotonic()
        if simdi - self._istek_son.get(anahtar, 0) < ISTEK_BEKLEME:
            try:
                await message.channel.send(_t("⏳ {mention} biraz yavaş — {ISTEK_BEKLEME:.0f} sn bekle.", mention=message.author.mention, ISTEK_BEKLEME=ISTEK_BEKLEME),
                                           delete_after=5)
            except discord.HTTPException:
                pass
            return
        self._istek_son[anahtar] = simdi

        async def yanit(icerik_=None, embed=None):
            try:
                await message.channel.send(content=(f"{message.author.mention} {icerik_}" if icerik_ else None),
                                           embed=embed, delete_after=10,
                                           allowed_mentions=discord.AllowedMentions(users=True))
            except discord.HTTPException:
                pass
        async with message.channel.typing():
            await self._oynat_ortak(message.author, message.channel, icerik[:SORGU_UZUNLUK], False, yanit)


# ── Modül düzeyi yardımcılar ──

_FILTRE_TAKMA = {
    "bassboost": "bas", "bass": "bas", "bb": "bas", "bas": "bas",
    "8d": "8d", "sekizd": "8d", "nc": "nightcore", "vw": "vaporwave",
    "hız": "hiz", "speed": "hiz", "tempo": "hiz", "hızlandır": "hizlandir", "yavaşlat": "yavaslat",
    "normalize": "normalizasyon", "norm": "normalizasyon",
    "sifirla": "kapat", "sıfırla": "kapat", "reset": "kapat", "off": "kapat", "temizle": "kapat", "yok": "kapat",
}


def _kayittan_parca(kayit):
    """Kişisel liste satırı → Parca. Spotify linkleri YouTube'da süre eşleşmeli aranır."""
    sorgu = kayit['sorgu']
    baslik = kayit.get('baslik') or ""
    sure = kayit.get('sure') or 0
    if SPOTIFY_REGEX.search(sorgu) and baslik:
        return Parca(sorgu=f"ytsearch5:{baslik}", baslik=baslik, url=kayit.get('url') or sorgu, sure=sure,
                     kaynak='spotify', beklenen_sure=sure, arama_metni=baslik)
    if sorgu.startswith(("http://", "https://")):
        return Parca(sorgu=sorgu, baslik=baslik, url=kayit.get('url') or sorgu, sure=sure,
                     arama_metni=baslik if 'youtube.com' in sorgu or 'youtu.be' in sorgu else "")
    return Parca(sorgu=f"ytsearch5:{sorgu}", baslik=baslik, sure=sure, arama_metni=sorgu)
