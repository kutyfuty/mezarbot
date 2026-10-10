import discord
import datetime
from discord.ext import commands
from arayuz import Renkler, AYIRICI
from database import sunucu_dil_al


class YardimMenusu(discord.ui.Select):
    def __init__(self, dil: str = "tr"):
        self.dil = dil
        if dil == "en":
            secenekler = [
                discord.SelectOption(label="Music", description="Play music, manage queue", value="muzik", emoji="🎵"),
                discord.SelectOption(label="Moderation", description="Moderation & server settings", value="yonetim", emoji="🛡️"),
                discord.SelectOption(label="AI & Drawing", description="AI chat & Flux Schnell drawing", value="yapayzeka", emoji="🤖"),
                discord.SelectOption(label="Custom Rooms", description="Temporary customizable voice channels", value="ozeloda", emoji="🔊"),
                discord.SelectOption(label="Translation", description="Flag reactions & instant translation", value="ceviri", emoji="🌐"),
                discord.SelectOption(label="Voice Stats", description="Voice channel leaderboards", value="istatistik", emoji="📊"),
                discord.SelectOption(label="Text to Speech", description="Speak messages in voice channels", value="konusma", emoji="🗣️"),
            ]
            placeholder = "📂 Select a category..."
        else:
            secenekler = [
                discord.SelectOption(label="Müzik", description="Şarkı çalma, sıra yönetimi", value="muzik", emoji="🎵"),
                discord.SelectOption(label="Yönetim", description="Moderasyon ve sunucu ayarları", value="yonetim", emoji="🛡️"),
                discord.SelectOption(label="Yapay Zeka", description="AI sohbet ve çizim", value="yapayzeka", emoji="🤖"),
                discord.SelectOption(label="Özel Odalar", description="Kendi ses odanı aç ve yönet", value="ozeloda", emoji="🔊"),
                discord.SelectOption(label="Çeviri", description="Bayrak tepkileri ve anlık çeviri", value="ceviri", emoji="🌐"),
                discord.SelectOption(label="Ses İstatistik", description="Ses aktivite ve süre sıralaması", value="istatistik", emoji="📊"),
                discord.SelectOption(label="Sesli Okuma", description="Mesajları seste sesli okut", value="konusma", emoji="🗣️"),
            ]
            placeholder = "📂 Bir kategori seç..."

        super().__init__(placeholder=placeholder, options=secenekler)

    async def callback(self, interaction: discord.Interaction):
        kategori = self.values[0]
        embed = None
        en = (self.dil == "en")

        if kategori == "muzik":
            embed = discord.Embed(color=Renkler.MUZIK, timestamp=datetime.datetime.now())
            if en:
                embed.set_author(name="🎵 Music Commands")
                embed.description = (
                    f"YouTube · YT Music · Spotify · SoundCloud · Direct Links\n{AYIRICI}\n"
                    "**Playback:**\n"
                    "> `!oynat` / `/oynat` `<song/link>` (or `!play`) ── Play music (playlists & albums supported)\n"
                    "> `!atla` / `/atla` (or `!skip`) ── Skip song · `!oylaatla` · `!onceki`\n"
                    "> `!duraklat` (or `!pause`) · `!devam` (or `!resume`) · `!durdur` (or `!stop`)\n"
                    "> `!sar` `1:30` · `!ileri` `30` · `!geri` `10`\n"
                    "**Queue:**\n"
                    "> `!kuyruk` / `/kuyruk` (or `!queue`) · `!kaldir` `<no>` · `!karistir` · `!temizle` (or `!clear`)\n"
                    "> `!dongu` `[off/song/queue]` · `!ses` `<0-150>` (or `!volume`) · `!simdi` (or `!now`)\n"
                    "**Features & Settings:**\n"
                    "> `!normalizasyon` ── Audio volume normalization\n"
                    "> `!otomatik` ── Auto-play similar tracks\n"
                    "> `!calmalistesi` ── Personal custom playlists\n"
                    "> `!muzikayar` ── DJ role, vote skip, 24/7 mode, request channel\n"
                    f"{AYIRICI}\n"
                    "> 💡 *All music commands work with both `/` and `!`.*"
                )
            else:
                embed.set_author(name="🎵 Müzik Komutları")
                embed.description = (
                    f"YouTube · YT Music · Spotify · SoundCloud · doğrudan link\n{AYIRICI}\n"
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
                    f"{AYIRICI}\n"
                    "> 💡 *Tüm müzik komutları `/oynat`, `/kuyruk`, `/duraklat` gibi hem `/` hem de `!` ile çalışır.*"
                )

        elif kategori == "yonetim":
            embed = discord.Embed(color=Renkler.MODERASYON, timestamp=datetime.datetime.now())
            if en:
                embed.set_author(name="🛡️ Moderation & Settings")
                embed.description = f"Server moderation, automod, and bot configuration\n{AYIRICI}"
                embed.add_field(name="🔨 Moderation", value=(
                    "> `!uyar` / `/uyar` @user [reason] ── Warn user\n"
                    "> `!uyarilar` / `/uyarilar` [@user] ── View warnings\n"
                    "> `!uyarisil` / `/uyarisil` @user ── Clear warnings\n"
                    "> `!sustur` / `/sustur` @user <duration> [reason] ── Timeout\n"
                    "> `!at` / `/at` @user [reason] ── Kick member\n"
                    "> `!yasak` / `/yasak` @user [reason] ── Ban member\n"
                    "> `!sil` / `/sil` <1-100> (or `!clear`) ── Purge messages"
                ), inline=False)
                embed.add_field(name="⚙️ Server Settings (Admin)", value=(
                    "> `/settings` / `/ayarlar` ── View and change server settings\n"
                    "> `/language` / `/dil` `en/tr` ── Switch bot language for server\n"
                    "> `!otomod` / `/otomod` ── Anti-spam & flood protection\n"
                    "> `!hosgeldinayarla` #channel ── Welcome channel\n"
                    "> `!gorusuruzayarla` #channel ── Goodbye channel\n"
                    "> `!otorolayarla` @role ── Auto-assign role on join\n"
                    "> `!logayarla` #channel ── Moderation log channel"
                ), inline=False)
            else:
                embed.set_author(name="🛡️ Yönetim Komutları")
                embed.description = f"Sunucu moderasyon ve ayar komutları\n{AYIRICI}"
                embed.add_field(name="🔨 Moderasyon", value=(
                    "> `!uyar` / `/uyar` @kişi [sebep]\n"
                    "> `!uyarilar` / `/uyarilar` [@kişi]\n"
                    "> `!uyarisil` / `/uyarisil` @kişi\n"
                    "> `!sustur` / `/sustur` @kişi <süre> [sebep]\n"
                    "> `!susturmakald` / `/susturmakald` @kişi\n"
                    "> `!at` / `/at` @kişi [sebep]\n"
                    "> `!yasak` / `/yasak` @kişi [sebep]\n"
                    "> `!sil` / `/sil` <1-100>\n"
                    "> `!yaz` / `/yaz` [#kanal] <mesaj> ── Bota mesaj yazdır"
                ), inline=False)
                embed.add_field(name="⚙️ Sunucu Ayarları (Yönetici)", value=(
                    "> `!ayarlar` / `/settings` ── Bu sunucunun tüm ayarları ve dili\n"
                    "> `!dil` / `/language` `tr/en` ── Sunucu bot dilini değiştir\n"
                    "> `!otomod` / `/otomod` ── Flood koruması\n"
                    "> `!hosgeldinayarla` / `/hosgeldinayarla` #kanal [mesaj]\n"
                    "> `!gorusuruzayarla` / `/gorusuruzayarla` [#kanal] [mesaj]\n"
                    "> `!otorolayarla` / `/otorolayarla` @rol\n"
                    "> `!logayarla` / `/logayarla` #kanal\n"
                    "> `!uyarayarla` / `/uyarayarla` [#kanal]\n"
                    "> `!yamanotukanal` / `/yamanotukanal` [#kanal | kapat]"
                ), inline=False)

        elif kategori == "yapayzeka":
            embed = discord.Embed(color=Renkler.PREMIUM, timestamp=datetime.datetime.now())
            if en:
                embed.set_author(name="🤖 AI & Drawing Commands")
                embed.description = (
                    f"Chat with AI and generate images!\n{AYIRICI}\n"
                    "> `@MezarBot` `<message>` ── AI conversation (memory included)\n"
                    "> `/draw` / `!draw` `<prompt>` (or `/ciz`) ── AI Flux Schnell image generation\n"
                    "> `!kisilik` / `/kisilik` `<mode>` ── Change AI personality\n"
                    "> `/sifirla` / `!reset` ── Reset AI chat history\n"
                    f"{AYIRICI}\n"
                    "> 💡 *Commands can be used with both `/` and `!`.*"
                )
            else:
                embed.set_author(name="🤖 Yapay Zeka Komutları")
                embed.description = (
                    f"AI ile sohbet et ve resim çiz!\n{AYIRICI}\n"
                    "> `@MezarBot` `<mesaj>` ── AI sohbet (5 mesaj hafıza)\n"
                    "> `!ciz` / `/ciz` (veya `/draw`) `<açıklama>` ── AI resim çizimi\n"
                    "> `!kisilik` / `/kisilik` `<mod>` ── AI kişilik (normal/komik/akademik/agresif)\n"
                    "> `!sifirla` / `/sifirla` ── Sohbet geçmişini temizle\n"
                    f"{AYIRICI}\n"
                    "> 💡 *Komutları `/ciz`, `/kisilik`, `/sifirla` olarak da kullanabilirsiniz.*"
                )

        elif kategori == "ozeloda":
            embed = discord.Embed(color=Renkler.PREMIUM, timestamp=datetime.datetime.now())
            if en:
                embed.set_author(name="🔊 Custom Voice Rooms")
                embed.description = (
                    f"Join **➕ Oda Oluştur** (Create Room) → Your private room is created and you are moved.\n"
                    f"Empty rooms are automatically cleaned up.\n{AYIRICI}"
                )
                embed.add_field(name="🎛️ Room Owner (`/oda` · `!oda`)", value=(
                    "> `info` ── Room status, allowed users, ban list\n"
                    "> `name` <new name> · `limit` <0-99>\n"
                    "> `lock` · `unlock` ── Private room lock/unlock\n"
                    "> `hide` · `show` ── Toggle room visibility\n"
                    "> `invite` @user · `kick` @user · `ban` @user\n"
                    "> `transfer` @user · `claim` ── Claim room if owner left\n"
                    "> `panel` ── Re-send control panel to voice chat"
                ), inline=False)
            else:
                embed.set_author(name="🔊 Özel Ses Odaları")
                embed.description = (
                    f"**➕ Oda Oluştur** kanalına gir → sana ait oda açılır, oraya taşınırsın.\n"
                    f"Oda boş kalınca kendiliğinden silinir. *Sunucu başına varsayılan kapalıdır.*\n{AYIRICI}"
                )
                embed.add_field(name="🎛️ Oda Sahibi (`/oda` · `!oda`)", value=(
                    "> `bilgi` ── Oda durumu, davetliler, yasaklılar\n"
                    "> `ad` <yeni ad> · `limit` <0-99>\n"
                    "> `kilitle` · `ac` ── Sadece davetliler / herkes girer\n"
                    "> `gizle` · `goster` ── Odayı gizle / göster\n"
                    "> `davet` @üye · `at` @üye · `yasakla` @üye · `yasak-kaldir` @üye\n"
                    "> `devret` @üye · `sahiplen` ── Sahip odada yoksa devral\n"
                    "> `panel` ── Kontrol panelini odanın sohbetine yeniden gönder"
                ), inline=False)

        elif kategori == "ceviri":
            embed = discord.Embed(color=discord.Color.from_rgb(52, 152, 219), timestamp=datetime.datetime.now())
            if en:
                embed.set_author(name="🌐 Translation Bridge")
                embed.description = (
                    f"Real-time multilingual translation powered by Groq Free Tier.\n{AYIRICI}\n"
                    "**Flag Reactions:**\n"
                    "> React with 🇬🇧 or 🇺🇸 to any message to translate it to English.\n"
                    "> React with 🇹🇷 to any message to translate it to Turkish.\n\n"
                    "**Slash Command:**\n"
                    "> `/cevir [target] [text]` ── Translate any text immediately (e.g. `/cevir en Merhaba`)\n"
                    f"{AYIRICI}\n"
                    "> 💡 *Translation is cached in memory with zero API cost.*"
                )
            else:
                embed.set_author(name="🌐 Çeviri Köprüsü")
                embed.description = (
                    f"Groq ücretsiz katmanıyla çalışan gerçek zamanlı çeviri köprüsü.\n{AYIRICI}\n"
                    "**Bayrak Tepkileri:**\n"
                    "> Herhangi bir mesaja 🇬🇧 veya 🇺🇸 emojisi bırakarak İngilizceye çevirin.\n"
                    "> Herhangi bir mesaja 🇹🇷 emojisi bırakarak Türkçeye çevirin.\n\n"
                    "**Komut ile Çeviri:**\n"
                    "> `/cevir [hedef_dil] [metin]` ── Metni doğrudan çevirir (Örn: `/cevir en Nasılsınız`)\n"
                    f"{AYIRICI}\n"
                    "> 💡 *Çeviriler önbelleklenir ve sıfır maliyetle çalışır.*"
                )

        elif kategori == "istatistik":
            embed = discord.Embed(color=Renkler.BILGI, timestamp=datetime.datetime.now())
            if en:
                embed.set_author(name="📊 Voice Activity Stats (/sesstat)")
                embed.description = (
                    f"Track voice channel duration and leaderboards.\n{AYIRICI}\n"
                    "> `/sesstat top` ── All-time voice duration leaderboard\n"
                    "> `/sesstat hafta` ── Weekly voice duration leaderboard\n"
                    "> `/sesstat ay` ── Monthly voice duration leaderboard\n"
                    "> `/sesstat ben` `[@user]` ── View personal voice statistics"
                )
            else:
                embed.set_author(name="📊 Ses Aktivite & İstatistik Komutları (/sesstat)")
                embed.description = (
                    f"Ses kanallarında geçirilen süreleri ve liderlik sıralamasını gösterir.\n{AYIRICI}\n"
                    "> `/sesstat top` ── Tüm zamanlar ses liderlik tablosu\n"
                    "> `/sesstat hafta` ── Bu haftanın en çok seste kalanları\n"
                    "> `/sesstat ay` ── Bu ayın ses sıralaması\n"
                    "> `/sesstat ben` `[@üye]` ── Seste kalma istatistiğini gösterir"
                )

        elif kategori == "konusma":
            embed = discord.Embed(color=Renkler.DISCORD, timestamp=datetime.datetime.now())
            if en:
                embed.set_author(name="🗣️ Text to Speech (TTS)")
                embed.description = (
                    f"Let the bot read your messages aloud in your voice channel.\n{AYIRICI}\n"
                    "> `/konus` `<text>` `[voice=male/female]` ── Speak text aloud\n"
                    "> `!konus` `<text>` (or `!konusm` for male voice)\n"
                    "> `!ayril` / `/ayril` ── Disconnect bot from voice\n"
                )
            else:
                embed.set_author(name="🗣️ Sesli Okuma (TTS)")
                embed.description = (
                    f"Botun ses kanalında yazdığın mesajı sesli okumasını sağla.\n{AYIRICI}\n"
                    "> `/konus` `<metin>` `[ses=kadın/erkek]` ── Sesli oku\n"
                    "> `!konus` `<metin>` (kadın sesi) · `!konusm` `<metin>` (erkek sesi)\n"
                    "> `!ayril` / `/ayril` ── Botu sesten çıkar\n"
                )

        if embed is None:
            return

        embed.set_footer(text="MezarBot • /yardim · /help")
        await interaction.response.edit_message(embed=embed, view=YardimView(dil=self.dil))


class YardimView(discord.ui.View):
    def __init__(self, dil: str = "tr"):
        super().__init__(timeout=120)
        self.add_item(YardimMenusu(dil=dil))


class Yardim(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def _yardim_embedi(self, guild) -> discord.Embed:
        lang = sunucu_dil_al(guild.id if guild else 0)
        embed = discord.Embed(color=Renkler.DISCORD, timestamp=datetime.datetime.now())
        if lang == "en":
            embed.set_author(name="📖 MezarBot Help Menu")
            embed.description = (
                f"{AYIRICI}\n"
                "Select a category from the dropdown menu below\nto explore all available commands.\n\n"
                "💡 **All commands can be used with both `/` (slash) and `!` (prefix)!**\n"
                "*(For example: `/help` or `!help`, `/draw` or `!draw`, `/oynat` or `!play`)*\n"
                f"{AYIRICI}\n\n"
                "> 🎵 **Music** ── Play songs, queues, playlists\n"
                "> 🛡️ **Moderation & Settings** ── Moderation tools, server settings\n"
                "> 🤖 **AI & Drawing** ── AI chat and Flux Schnell drawing\n"
                "> 🔊 **Custom Rooms** ── Temporary private voice channels\n"
                "> 🌐 **Translation** ── Flag reaction bridge & translation\n"
                "> 📊 **Voice Stats** ── Voice channel duration leaderboards\n"
                "> 🗣️ **Text to Speech** ── Read messages in voice channels"
            )
            embed.set_footer(text="MezarBot • Select a category below 👇 • /help")
        else:
            embed.set_author(name="📖 MezarBot Yardım Menüsü")
            embed.description = (
                f"{AYIRICI}\n"
                "Aşağıdaki menüden bir kategori seçerek\nkomutları görebilirsin.\n\n"
                "💡 **Tüm komutlar hem `/` (slash) hem de `!` (prefix) ile kullanılabilir!**\n"
                "*(Örneğin: `/yardim` veya `!yardim`, `/oynat` veya `!oynat`)*\n"
                f"{AYIRICI}\n\n"
                "> 🎵 **Müzik** ── Şarkı çalma, sıra, çalma listeleri\n"
                "> 🛡️ **Yönetim** ── Moderasyon, ceza ve sunucu ayarları\n"
                "> 🤖 **Yapay Zeka** ── AI sohbet ve Flux Schnell çizim\n"
                "> 🔊 **Özel Odalar** ── Kendi ses odanı aç ve yönet\n"
                "> 🌐 **Çeviri** ── Bayrak tepkisi ve anlık çeviri köprüsü\n"
                "> 📊 **Ses & İstatistik** ── Ses kanalı liderlik tablosu\n"
                "> 🗣️ **Sesli Okuma** ── Metinleri ses kanalında okutma"
            )
            embed.set_footer(text="MezarBot • Tüm komutlar / ve ! ile çalışır • Kategori seç 👇")
        return embed

    @commands.hybrid_command(name="yardim", description="MezarBot komut rehberini gösterir / View command guide")
    async def yardim(self, ctx):
        """Tüm komutların listesini gösterir / Show list of all commands."""
        lang = sunucu_dil_al(ctx.guild.id if ctx.guild else 0)
        embed = self._yardim_embedi(ctx.guild)
        await ctx.send(embed=embed, view=YardimView(dil=lang))

    @commands.hybrid_command(name="help", description="View MezarBot command guide and help menu")
    async def help_cmd(self, ctx):
        """Show list of all commands / Tüm komutların listesini gösterir."""
        lang = sunucu_dil_al(ctx.guild.id if ctx.guild else 0)
        embed = self._yardim_embedi(ctx.guild)
        await ctx.send(embed=embed, view=YardimView(dil=lang))


async def setup(bot):
    await bot.add_cog(Yardim(bot))
