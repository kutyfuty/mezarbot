"""
MüzikBaba — yalnızca müzik çalan ikinci bot hesabının ek cog'u (MEZARBOT_PROFIL=muzik ile yüklenir).

- Durum (presence): ne çaldığını / nasıl çağrılacağını gösterir.
- /yardim: yalnızca slash (önekli !yardim'i ana bot MezarBot cevaplar; iki bot aynı mesaja cevap vermesin).
- Ana bot sunucuda yoksa da tek başına tam müzik botu olarak çalışır.
"""
import discord
from discord import app_commands
from discord.ext import commands, tasks

from yapilandirma import PREFIX

KOMUTLAR = [
    ("🎵 Çalma", [
        ("oynat <şarkı / link>", "YouTube, YouTube Music, Spotify, SoundCloud ya da doğrudan link çalar"),
        ("siradaki <şarkı>", "Şarkıyı kuyruğun başına ekler"),
        ("atla · onceki · oylaatla", "Sonraki / önceki şarkı, oylamalı atlama"),
        ("duraklat · devam · durdur", "Duraklat, sürdür, durdur ve kuyruğu temizle"),
        ("sar 1:30 · ileri 10 · geri 10", "Şarkıda ileri / geri sar"),
    ]),
    ("📜 Kuyruk", [
        ("kuyruk · simdi", "Kuyruğu ve çalan şarkıyı gösterir"),
        ("kaldir · tasi · karistir · temizle", "Kuyruğu düzenle"),
        ("dongu · otomatik", "Tekrar modu ve otomatik oynatma (radyo)"),
    ]),
    ("🎚️ Ses", [
        ("ses 0-150 · normalizasyon", "Ses seviyesi ve ses dengeleme"),
        ("katil · cik", "Odaya çağır / odadan çıkar"),
    ]),
    ("💾 Listeler ve ayarlar", [
        ("calmalistesi", "Kişisel çalma listelerin (kaydet, ekle, oynat, sil)"),
        ("muzikayar", "DJ rolü, 7/24 modu, istek kanalı, zaman aşımı (yönetici)"),
    ]),
]


class MuzikBaba(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._i = 0

    async def cog_load(self):
        self.durum_dongusu.start()

    async def cog_unload(self):
        self.durum_dongusu.cancel()

    @tasks.loop(seconds=30)
    async def durum_dongusu(self):
        muzik = self.bot.get_cog("Muzik")
        calan = muzik.aktif_oynatici_sayisi() if muzik else 0
        durumlar = [
            (discord.ActivityType.listening, "/oynat · ikinci oda benden"),
            (discord.ActivityType.listening, f"{calan} odada müzik" if calan else "/yardim"),
        ]
        tip, metin = durumlar[self._i % len(durumlar)]
        self._i += 1
        try:
            await self.bot.change_presence(activity=discord.Activity(type=tip, name=metin))
        except Exception:
            pass

    @durum_dongusu.before_loop
    async def _once(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="yardim", description="MüzikBaba müzik komutları ve nasıl çalıştığı")
    async def yardim(self, interaction: discord.Interaction):
        e = discord.Embed(
            title=f"🎶 {self.bot.user.display_name}",
            description=(
                "Yalnızca müzik çalan bot. **MezarBot** başka bir odada çalarken senin odana ben gelirim — "
                "iki odada aynı anda müzik.\n\n"
                f"**Akıllı komutlar:** `{PREFIX}oynat` yazman yeterli; *senin* ses kanalındaki bot cevap verir. "
                "Odanda bot yoksa boştaki bot gelir. Slash komutlarında listeden botu seçebilirsin."),
            color=0xE8A33D)
        for baslik, satirlar in KOMUTLAR:
            e.add_field(name=baslik, value="\n".join(f"`/{k}` — {a}" for k, a in satirlar), inline=False)
        e.set_footer(text=f"Önek: {PREFIX} · Slash: /")
        await interaction.response.send_message(embed=e, ephemeral=True)


async def setup(bot):
    await bot.add_cog(MuzikBaba(bot))
