import discord
from discord.ext import commands, tasks
import itertools

from yapilandirma import DURUM_MESAJLARI

# Botun GERÇEK aktif özellikleri — sırayla döner (her 25 sn). config.json → durum_mesajlari ile değiştirilebilir.
VARSAYILAN_DURUMLAR = [
    ("/yardim / /help",                        "watching"),
    ("/oynat ile kesintisiz müzik",            "listening"),
    ("/ciz / /draw ile yapay zekâ",            "playing"),
    ("/cevir ile anlık çeviri",                "watching"),
    ("/oda ile özel ses odası",                "listening"),
    ("/sesstat ile ses liderliği",             "watching"),
    ("/ayarlar / /settings ile yönetim",       "watching"),
]
_TIPLER = {"playing": discord.ActivityType.playing, "watching": discord.ActivityType.watching,
           "listening": discord.ActivityType.listening, "competing": discord.ActivityType.competing}
PRESENCE_LISTESI = [(metin, _TIPLER.get(str(tip).lower(), discord.ActivityType.watching))
                    for metin, tip in (DURUM_MESAJLARI or VARSAYILAN_DURUMLAR)]


class DurumRotator(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._dongu = itertools.cycle(PRESENCE_LISTESI)
        self._sayac = 0

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.rotator_loop.is_running():
            self.rotator_loop.start()

    @tasks.loop(seconds=25)
    async def rotator_loop(self):
        metin, tip = next(self._dongu)
        try:
            await self.bot.change_presence(
                status=discord.Status.online,
                activity=discord.Activity(type=tip, name=metin)
            )
            self._sayac += 1
        except Exception:
            pass

    @rotator_loop.before_loop
    async def _before(self):
        await self.bot.wait_until_ready()
        metin, tip = next(self._dongu)
        try:
            await self.bot.change_presence(
                status=discord.Status.online,
                activity=discord.Activity(type=tip, name=metin)
            )
        except Exception:
            pass


async def setup(bot: commands.Bot):
    await bot.add_cog(DurumRotator(bot))
