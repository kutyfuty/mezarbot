import discord
from discord.ext import commands
import edge_tts
import os
import asyncio
import logging
import uuid
from database import vip_kontrol
from arayuz import Renkler, premium_embed, hata_embed, basari_embed, FFMPEG_YOLU
from yapilandirma import GECICI_DIZIN

logger = logging.getLogger('MezarBot.Konusma')


class Konusma(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.male_voice = "tr-TR-AhmetNeural"
        self.female_voice = "tr-TR-EmelNeural"
        # Erkek ses: derin ayar (yavaş + düşük perde); kadın sesi varsayılan kalır
        self.voice_ayar = {"tr-TR-AhmetNeural": {"rate": "-10%", "pitch": "-30Hz"}}

    @commands.hybrid_command(description="Metni sesli kanalda seslendir", name="konus")
    @discord.app_commands.describe(metin="Seslendirilecek metin", ses="Ses türü (erkek veya kadın)")
    @discord.app_commands.choices(ses=[
        discord.app_commands.Choice(name="Erkek (Ahmet)", value="erkek"),
        discord.app_commands.Choice(name="Kadın (Emel)", value="kadin")
    ])
    async def konus(self, ctx, metin: str, ses: str = "erkek"):
        """[VIP ONLY] Yazılan metni seslendirir. Kullanım: !konus <mesaj> veya !konus <mesaj> kadin"""
        secilen_ses = self.female_voice if str(ses).lower() in ("kadin", "kadın", "female", "emel") else self.male_voice
        await self._seslendir(ctx, metin, secilen_ses)

    @commands.command(name="konusm")
    async def konusm_prefix(self, ctx, *, metin: str):
        """[VIP ONLY] Yazılan metni KADIN sesiyle seslendirir. Kullanım: !konusm <mesaj>"""
        await self._seslendir(ctx, metin, self.female_voice)

    async def _seslendir(self, ctx, metin, voice):
        is_vip = vip_kontrol(ctx.author)
        if not is_vip:
            return await ctx.send(embed=hata_embed("Bu komutu sadece **VIP** üyeler kullanabilir!"), delete_after=5)

        if not ctx.author.voice:
            return await ctx.send(embed=hata_embed("Önce bir ses kanalına girmelisin!"), delete_after=5)

        if not metin.strip():
            return await ctx.send(embed=hata_embed("Boş metin gönderilemez!"), delete_after=5)

        limit = 2000 if is_vip else 300
        if len(metin) > limit:
            return await ctx.send(embed=hata_embed(f"Mesaj çok uzun! (Sınırınız: {limit} karakter)"), delete_after=5)

        voice_channel = ctx.author.voice.channel
        vc = ctx.voice_client

        # Müzik çalıyorsa TTS'i engelle
        if vc and vc.is_playing():
            muzik_cog = self.bot.get_cog('Muzik')
            if muzik_cog and ctx.guild.id in muzik_cog.guncel_sarki:
                return await ctx.send(embed=hata_embed("Şu an müzik çalıyor! Önce müziği kapat veya bitir."), delete_after=5)

        if vc:
            if vc.channel.id != voice_channel.id:
                await vc.move_to(voice_channel)
        else:
            try:
                vc = await voice_channel.connect()
            except (discord.Forbidden, discord.ClientException) as e:
                return await ctx.send(embed=hata_embed(f"Ses kanalına bağlanılamadı: {e}"), delete_after=7)

        # Recheck voice client after await (might have disconnected)
        vc = ctx.voice_client
        if not vc or not vc.is_connected():
            return await ctx.send(embed=hata_embed("Ses kanalına bağlanılamadı!"), delete_after=5)

        # Geçici dosya bot dizininde (systemd ProtectSystem=strict altında da yazılabilir)
        os.makedirs(GECICI_DIZIN, exist_ok=True)
        filename = os.path.join(GECICI_DIZIN, f"tts_{ctx.guild.id}_{uuid.uuid4().hex[:8]}.mp3")
        try:
            communicate = edge_tts.Communicate(metin, voice, **self.voice_ayar.get(voice, {}))
            await communicate.save(filename)

            if vc.is_playing():
                vc.stop()

            source = discord.FFmpegPCMAudio(filename, executable=FFMPEG_YOLU)
            def _after(err):
                if err:
                    logger.warning(f"TTS oynatma hatası: {err}")
                self.cleanup(filename)
            vc.play(source, after=_after)

            if ctx.interaction is None:  # /komutta silinecek/tepki verilecek mesaj yok
                await ctx.message.add_reaction("🗣️")

        except Exception as e:
            logger.error(f"TTS Hatası: {e}")
            await ctx.send(embed=hata_embed("Seslendirme sırasında bir hata oluştu."))
            self.cleanup(filename)

    def cleanup(self, filename):
        if os.path.exists(filename):
            try:
                os.remove(filename)
            except Exception as e:
                logger.error(f"Dosya silme hatası: {e}")

    @commands.hybrid_command(description="Seslendirme için bağlanan botu kanaldan çıkar")
    async def ayril(self, ctx):
        """Botu ses kanalından çıkarır."""
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
            await ctx.send(embed=basari_embed("Ses kanalından ayrıldım. 👋"))
        else:
            await ctx.send(embed=hata_embed("Zaten bir ses kanalında değilim."))

async def setup(bot):
    await bot.add_cog(Konusma(bot))
