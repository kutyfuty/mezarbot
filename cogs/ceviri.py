"""
Diller Arası Çeviri Köprüsü (TR <-> EN)
- Bir mesaja 🇬🇧 veya 🇺🇸 emojisi basıldığında İngilizceye çevirir.
- Bir mesaja 🇹🇷 emojisi basıldığında Türkçeye çevirir.
- /cevir slash komutu ile anlık metin çevirisi sağlar.
- %100 Ücretsiz: Groq Cloud ücretsiz API katmanını kullanır.
- Önbellek (Cache) korumalıdır: Aynı mesaja birden fazla kişi reaksiyon verse bile tek API çağrısı yapılır.
"""
import logging
import time
import discord
from discord.ext import commands
from discord import app_commands
from groq_yardimci import HIZLI_MODELLER, groq_istemci, groq_tamamla

logger = logging.getLogger('MezarBot.Ceviri')

# Emojiler
EMOJI_EN = ("🇬🇧", "🇺🇸", "🇬", "🇺")
EMOJI_TR = ("🇹🇷", "🇹")


class Ceviri(commands.Cog):
    """TR <-> EN Diller Arası Anlık Çeviri Köprüsü"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # (message_id, hedef_dil) -> cevirilmis_metin
        self._onbellek = {}
        # kullanici_id -> son_islem_zamani (rate-limit koruması)
        self._kullanici_sure = {}

    def _metin_cevir(self, metin: str, hedef_dil: str) -> str:
        """Groq API ile metni hedef dile çevirir (Senkron)."""
        dil_adi = "English" if hedef_dil == "en" else "Turkish"
        prompt_sistem = (
            f"You are a professional technical and community translator. "
            f"Translate the user input into {dil_adi}. "
            "Preserve code snippets, technical terms (e.g. GPIO, baud rate, PCB, pull-up), formatting, and emojis. "
            "Output ONLY the translated text without conversational filler, explanations, or quotes."
        )

        return groq_tamamla(groq_istemci(), [
            {"role": "system", "content": prompt_sistem},
            {"role": "user", "content": metin},
        ], temperature=0.2, max_tokens=600, modeller=HIZLI_MODELLER)

    # ── Reaksiyon Dinleyicisi ───────────────────────

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionPayload):
        emoji_str = str(payload.emoji.name)
        hedef_dil = None

        if emoji_str in ("🇬🇧", "🇺🇸"):
            hedef_dil = "en"
        elif emoji_str == "🇹🇷":
            hedef_dil = "tr"
        else:
            return

        # Botun kendi reaksiyonlarını yoksay
        if payload.user_id == self.bot.user.id:
            return

        # Kullanıcı rate-limit (3 saniyede 1 çeviri)
        simdi = time.time()
        son_zaman = self._kullanici_sure.get(payload.user_id, 0)
        if simdi - son_zaman < 3.0:
            return
        self._kullanici_sure[payload.user_id] = simdi

        channel = self.bot.get_channel(payload.channel_id)
        if not channel or not isinstance(channel, discord.TextChannel):
            return

        try:
            message = await channel.fetch_message(payload.message_id)
        except Exception:
            return

        # Boş mesaj veya bot mesajı kontrolü
        ham_metin = message.content.strip()
        if not ham_metin or len(ham_metin) < 2:
            return

        # Önbellek kontrolü
        cache_key = (message.id, hedef_dil)
        if cache_key in self._onbellek:
            cevrilmis = self._onbellek[cache_key]
        else:
            cevrilmis = await self.bot.loop.run_in_executor(None, self._metin_cevir, ham_metin, hedef_dil)
            if cevrilmis:
                self._onbellek[cache_key] = cevrilmis

        if not cevrilmis:
            return

        # Çeviri embedi
        bayrak = "🇬🇧" if hedef_dil == "en" else "🇹🇷"
        dil_baslik = "English Translation" if hedef_dil == "en" else "Türkçe Çeviri"

        embed = discord.Embed(
            description=f"> {cevrilmis}",
            color=discord.Color.from_rgb(52, 152, 219) if hedef_dil == "en" else discord.Color.from_rgb(231, 76, 60)
        )
        embed.set_author(
            name=f"{bayrak} {dil_baslik} ({message.author.display_name})",
            icon_url=message.author.display_avatar.url
        )
        embed.set_footer(text="MezarBot • Otomatik Çeviri Köprüsü (Groq Free Tier)")

        try:
            await message.reply(embed=embed, mention_author=False)
        except Exception as e:
            logger.debug(f"Çeviri yanıtı gönderilemedi: {e}")

    # ── Slash Komutu: /cevir ────────────────────────

    @app_commands.command(name="cevir", description="Metni Türkçe veya İngilizceye çevirir")
    @app_commands.describe(
        metin="Çevrilecek metin",
        hedef_dil="Hangi dile çevrilsin?"
    )
    @app_commands.choices(hedef_dil=[
        app_commands.Choice(name="🇬🇧 English", value="en"),
        app_commands.Choice(name="🇹🇷 Türkçe", value="tr"),
    ])
    async def cevir_komutu(self, interaction: discord.Interaction, metin: str, hedef_dil: str = "en"):
        await interaction.response.defer()

        cevrilmis = await self.bot.loop.run_in_executor(None, self._metin_cevir, metin, hedef_dil)
        if not cevrilmis:
            return await interaction.followup.send("⚠️ Çeviri gerçekleştirilemedi, lütfen tekrar deneyin.")

        bayrak = "🇬🇧" if hedef_dil == "en" else "🇹🇷"
        dil_etiket = "İngilizce" if hedef_dil == "en" else "Türkçe"

        embed = discord.Embed(
            color=discord.Color.from_rgb(46, 204, 113),
            title=f"{bayrak} {dil_etiket} Çevirisi"
        )
        embed.add_field(name="Orijinal Metin", value=f"```text\n{metin[:1000]}\n```", inline=False)
        embed.add_field(name="Çeviri", value=f"```text\n{cevrilmis[:1000]}\n```", inline=False)
        embed.set_footer(text="MezarBot • Groq Çeviri Servisi")

        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Ceviri(bot))
