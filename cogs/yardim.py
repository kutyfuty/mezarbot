import discord
import datetime
from discord.ext import commands
from arayuz import Renkler, AYIRICI
from database import sunucu_dil_al
from dil import _t


class YardimMenusu(discord.ui.Select):
    def __init__(self, dil: str = "tr"):
        self.dil = dil
        secenekler = [
            discord.SelectOption(label=_t("Müzik"), description=_t("Şarkı çalma, sıra yönetimi"), value="muzik", emoji="🎵"),
            discord.SelectOption(label=_t("Yönetim"), description=_t("Moderasyon ve sunucu ayarları"), value="yonetim", emoji="🛡️"),
            discord.SelectOption(label=_t("Yapay Zeka"), description=_t("AI sohbet asistanı"), value="yapayzeka", emoji="🤖"),
            discord.SelectOption(label=_t("Özel Odalar"), description=_t("Kendi ses odanı aç ve yönet"), value="ozeloda", emoji="🔊"),
            discord.SelectOption(label=_t("Ses İstatistik"), description=_t("Ses aktivite ve süre sıralaması"), value="istatistik", emoji="📊"),
        ]
        placeholder = _t("📂 Bir kategori seç...")

        super().__init__(placeholder=placeholder, options=secenekler)

    async def callback(self, interaction: discord.Interaction):
        kategori = self.values[0]
        embed = None

        if kategori == "muzik":
            embed = discord.Embed(color=Renkler.MUZIK, timestamp=datetime.datetime.now())
            embed.set_author(name=_t("🎵 Müzik Komutları"))
            embed.description = (
                _t("YouTube · YT Music · Spotify · SoundCloud · doğrudan link\n"
                   "{AYIRICI}\n"
                   "**Çalma:**\n"
                   "> `!oynat` / `/oynat` `<şarkı/link>` ── Çal (playlist/albüm de olur) · `!siradaki` / `/siradaki`\n"
                   "> `!atla` / `/atla` ── Atla (oylama açıksa oy) · `!oylaatla` · `!onceki`\n"
                   "> `!duraklat` · `!devam` · `!durdur` ── Durdur + kuyruğu temizle\n"
                   "> `!sar` `1:30` · `!ileri` `30` · `!geri` `10`\n"
                   "**Kuyruk:**\n"
                   "> `!kuyruk` / `/kuyruk` · `!kaldir` `<no>` · `!tasi` `<a> <b>` · `!karistir` · `!temizle`\n"
                   "> `!dongu` `[kapalı/şarkı/kuyruk]` · `!ses` `<0-150>` · `!simdi` · `!muzikgecmis`\n"
                   "**Özellikler & Ayarlar:**\n"
                   "> `!normalizasyon` / `/normalizasyon` ── Ses dengeleme aç/kapat\n"
                   "> `!otomatik` / `/otomatik` ── Benzer şarkılarla otomatik devam\n"
                   "> `!calmalistesi` / `/calmalistesi` ── Kişisel listeler (kaydet / ekle / oynat / sil)\n"
                   "> `!katil` · `!cik`\n"
                   "> `!muzikayar` / `/muzikayar` ── DJ rolü, oylama, 7/24, istek kanalı…\n"
                   "{AYIRICI}\n"
                   "> 💡 *Tüm müzik komutları `/oynat`, `/kuyruk`, `/duraklat` gibi hem `/` hem de `!` ile çalışır.*", AYIRICI=AYIRICI)
            )

        elif kategori == "yonetim":
            embed = discord.Embed(color=Renkler.MODERASYON, timestamp=datetime.datetime.now())
            embed.set_author(name=_t("🛡️ Yönetim Komutları"))
            embed.description = _t("Sunucu moderasyon ve ayar komutları\n{AYIRICI}", AYIRICI=AYIRICI)
            embed.add_field(name=_t("🔨 Moderasyon"), value=(
                _t("> `!uyar` / `/uyar` @kişi [sebep]\n"
                   "> `!uyarilar` / `/uyarilar` [@kişi]\n"
                   "> `!uyarisil` / `/uyarisil` @kişi\n"
                   "> `!sustur` / `/sustur` @kişi <süre> [sebep]\n"
                   "> `!susturmakald` / `/susturmakald` @kişi\n"
                   "> `!at` / `/at` @kişi [sebep]\n"
                   "> `!yasak` / `/yasak` @kişi [sebep]\n"
                   "> `!sil` / `/sil` <1-100>\n"
                   "> `!yaz` / `/yaz` [#kanal] <mesaj> ── Bota mesaj yazdır")
            ), inline=False)
            embed.add_field(name=_t("⚙️ Sunucu Ayarları (Yönetici)"), value=(
                _t("> `!ayarlar` / `/ayarlar` ── Bu sunucunun tüm ayarları ve dili\n"
                   "> `!dil` / `/dil` `tr/en` ── Sunucu bot dilini değiştir\n"
                   "> `!otomod` / `/otomod` ── Flood koruması\n"
                   "> `!hosgeldinayarla` / `/hosgeldinayarla` #kanal [mesaj]\n"
                   "> `!gorusuruzayarla` / `/gorusuruzayarla` [#kanal] [mesaj]\n"
                   "> `!otorolayarla` / `/otorolayarla` @rol\n"
                   "> `!logayarla` / `/logayarla` #kanal\n"
                   "> `!uyarayarla` / `/uyarayarla` [#kanal]")
            ), inline=False)

        elif kategori == "yapayzeka":
            embed = discord.Embed(color=Renkler.PREMIUM, timestamp=datetime.datetime.now())
            embed.set_author(name=_t("🤖 Yapay Zeka Komutları"))
            embed.description = (
                _t("AI ile sohbet et!\n"
                   "{AYIRICI}\n"
                   "> `@MezarBot` `<mesaj>` ── AI sohbet (5 mesaj hafıza)\n"
                   "> `!sifirla` / `/sifirla` ── Sohbet geçmişini temizle", AYIRICI=AYIRICI)
            )

        elif kategori == "ozeloda":
            embed = discord.Embed(color=Renkler.PREMIUM, timestamp=datetime.datetime.now())
            embed.set_author(name=_t("🔊 Özel Ses Odaları"))
            embed.description = (
                _t("**➕ Oda Oluştur** kanalına gir → sana ait oda açılır, oraya taşınırsın.\n"
                   "Oda boş kalınca kendiliğinden silinir. *Sunucu başına varsayılan kapalıdır.*\n"
                   "{AYIRICI}", AYIRICI=AYIRICI)
            )
            embed.add_field(name=_t("🎛️ Oda Sahibi (`/oda` · `!oda`)"), value=(
                _t("> `bilgi` ── Oda durumu, davetliler, yasaklılar\n"
                   "> `ad` <yeni ad> · `limit` <0-99>\n"
                   "> `kilitle` · `ac` ── Sadece davetliler / herkes girer\n"
                   "> `gizle` · `goster` ── Odayı gizle / göster\n"
                   "> `davet` @üye · `at` @üye · `yasakla` @üye · `yasak-kaldir` @üye\n"
                   "> `devret` @üye · `sahiplen` ── Sahip odada yoksa devral\n"
                   "> `panel` ── Kontrol panelini odanın sohbetine yeniden gönder")
            ), inline=False)

        elif kategori == "istatistik":
            embed = discord.Embed(color=Renkler.BILGI, timestamp=datetime.datetime.now())
            embed.set_author(name=_t("📊 Ses Aktivite & İstatistik Komutları (/sesstat)"))
            embed.description = (
                _t("Ses kanallarında geçirilen süreleri ve liderlik sıralamasını gösterir.\n"
                   "{AYIRICI}\n"
                   "> `/sesstat top` ── Tüm zamanlar ses liderlik tablosu\n"
                   "> `/sesstat hafta` ── Bu haftanın en çok seste kalanları\n"
                   "> `/sesstat ay` ── Bu ayın ses sıralaması\n"
                   "> `/sesstat ben` `[@üye]` ── Seste kalma istatistiğini gösterir", AYIRICI=AYIRICI)
            )

        if embed is None:
            return

        embed.set_footer(text="MezarBot • /yardim · !help")
        await interaction.response.edit_message(embed=embed, view=YardimView(dil=self.dil))


class YardimView(discord.ui.View):
    def __init__(self, dil: str = "tr"):
        super().__init__(timeout=120)
        self.add_item(YardimMenusu(dil=dil))


class Yardim(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def _yardim_embedi(self, guild) -> discord.Embed:
        embed = discord.Embed(color=Renkler.DISCORD, timestamp=datetime.datetime.now())
        embed.set_author(name=_t("📖 MezarBot Yardım Menüsü"))
        embed.description = (
            _t("{AYIRICI}\n"
               "Aşağıdaki menüden bir kategori seçerek\n"
               "komutları görebilirsin.\n"
               "\n"
               "💡 **Tüm komutlar hem `/` (slash) hem de `!` (prefix) ile kullanılabilir!**\n"
               "*(Örneğin: `/yardim` veya `!yardim`, `/oynat` veya `!oynat`)*\n"
               "{AYIRICI}\n"
               "\n"
               "> 🎵 **Müzik** ── Şarkı çalma, sıra, çalma listeleri\n"
               "> 🛡️ **Yönetim** ── Moderasyon, ceza ve sunucu ayarları\n"
               "> 🤖 **Yapay Zeka** ── AI sohbet asistanı\n"
               "> 🔊 **Özel Odalar** ── Kendi ses odanı aç ve yönet\n"
               "> 📊 **Ses & İstatistik** ── Ses kanalı liderlik tablosu", AYIRICI=AYIRICI)
        )
        embed.set_footer(text=_t("MezarBot • Tüm komutlar / ve ! ile çalışır • Kategori seç 👇"))
        return embed

    @commands.hybrid_command(name="yardim", aliases=["help", "komutlar", "commands"], description="MezarBot komut rehberini gösterir / View command guide")
    async def yardim(self, ctx):
        """Tüm komutların listesini gösterir / Show list of all commands."""
        lang = sunucu_dil_al(ctx.guild.id if ctx.guild else 0)
        embed = self._yardim_embedi(ctx.guild)
        await ctx.send(embed=embed, view=YardimView(dil=lang))


async def setup(bot):
    await bot.add_cog(Yardim(bot))
