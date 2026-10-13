"""
Çoklu müzik botu (MezarBot + MüzikBaba) testi — Discord'a BAĞLANMAZ, gerçek veritabanına DOKUNMAZ.

Çalıştırma: venv/bin/python tests/ornekler_test.py

1. Yönlendirme kuralları (cogs/muzik/ornekler.py): sahte sunucu / ses kanallarıyla önekli komutta tam olarak
   BİR botun "sorumlu" seçildiği, slash komutunda yanlış bota doğru botun söylendiği.
2. MEZARBOT_PROFIL=muzik: ayrı token dosyası / kilit / log / veritabanı, yalnızca müzik cog'ları yüklenir,
   çevrimdışı Bot'a yüklenip kaldırılabilir.
"""
import asyncio
import os
import subprocess
import sys
import tempfile
import types

BOT_DIZINI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BOT_DIZINI)
_tmp = tempfile.mkdtemp(prefix="ornekler_test_")
os.environ["MEZARBOT_DB"] = os.path.join(_tmp, "test.db")   # bot modüllerini import etmeden ÖNCE

import discord  # noqa: E402
from discord.ext import commands  # noqa: E402

GECTI = 0


def ok(kosul, mesaj):
    global GECTI
    if not kosul:
        raise AssertionError(mesaj)
    GECTI += 1
    print("  ✓", mesaj)


# ── 1. yönlendirme ──
from cogs.muzik import ornekler  # noqa: E402

ANA, IKINCI = 1000000000000000001, 1000000000000000002   # sahte bot ID'leri (config.json'dan bağımsız)
ornekler.MUZIK_ORNEKLERI = [ANA, IKINCI]                  # sıra = öncelik: ana bot önce


class Kanal:
    def __init__(self, ad, botlar=(), insanlar=()):
        self.name = ad
        self.voice_states = {i: object() for i in list(botlar) + [u.id for u in insanlar]}
        self.members = [types.SimpleNamespace(id=i, bot=True) for i in botlar] + list(insanlar)


class Sunucu:
    def __init__(self, kanallar, botlar=(ANA, IKINCI)):
        self.id = 1
        self.voice_channels, self.stage_channels = kanallar, []
        self._botlar = set(botlar)

    def get_member(self, i):
        return types.SimpleNamespace(display_name={ANA: "MezarBot", IKINCI: "MüzikBaba"}[i]) if i in self._botlar else None

    async def fetch_member(self, i):
        if i in self._botlar:
            return self.get_member(i)
        raise discord.NotFound(types.SimpleNamespace(status=404, reason="yok"), "yok")


def uye(kanal):
    u = types.SimpleNamespace(id=42, bot=False)
    u.voice = types.SimpleNamespace(channel=kanal) if kanal else None
    if kanal:
        kanal.voice_states[42] = object()
        kanal.members.append(u)
    return u


def ctx(bot_id, guild, u, komut="oynat", slash=False):
    cog = types.SimpleNamespace(bot=types.SimpleNamespace(user=types.SimpleNamespace(id=bot_id)))
    c = types.SimpleNamespace(guild=guild, author=u, interaction=object() if slash else None,
                              command=types.SimpleNamespace(qualified_name=komut))
    return cog, c


async def kim_cevaplar(guild, u, komut="oynat"):
    """Önekli komutta hangi botlar çalıştırır? (tam olarak biri olmalı)"""
    cevap = []
    for b in (ANA, IKINCI):
        if b not in guild._botlar:
            continue
        ornekler._uyelik.clear()
        try:
            await ornekler.denetle(*ctx(b, guild, u, komut))
            cevap.append(b)
        except ornekler.BaskaOrnekte:
            pass
    return cevap


async def slash(bot_id, guild, u, komut="oynat"):
    ornekler._uyelik.clear()
    try:
        await ornekler.denetle(*ctx(bot_id, guild, u, komut, slash=True))
        return None
    except ornekler.OrnekYonlendirme as e:
        return str(e)


async def yonlendirme():
    print("Yönlendirme (önekli komut → tek bot):")
    insan = types.SimpleNamespace(id=7, bot=False)
    v1, v2 = Kanal("Oda 1"), Kanal("Oda 2")
    ok(await kim_cevaplar(Sunucu([v1, v2]), uye(v1)) == [ANA], "iki bot da boşta → MezarBot gelir, MüzikBaba susar")

    v1, v2 = Kanal("Oda 1", [ANA], [insan]), Kanal("Oda 2")
    ok(await kim_cevaplar(Sunucu([v1, v2]), uye(v2)) == [IKINCI], "MezarBot Oda 1'de çalarken Oda 2'den yazan → MüzikBaba gelir")

    v1, v2 = Kanal("Oda 1", [ANA], [insan]), Kanal("Oda 2", [IKINCI])
    ok(await kim_cevaplar(Sunucu([v1, v2]), uye(v1), "atla") == [ANA], "Oda 1'den !atla → yalnızca Oda 1'deki MezarBot")
    v1, v2 = Kanal("Oda 1", [ANA], [insan]), Kanal("Oda 2", [IKINCI])
    ok(await kim_cevaplar(Sunucu([v1, v2]), uye(v2), "atla") == [IKINCI], "Oda 2'den !atla → yalnızca Oda 2'deki MüzikBaba")

    v1, v2, v3 = Kanal("Oda 1", [ANA], [insan]), Kanal("Oda 2"), Kanal("Oda 3", [IKINCI], [insan])
    ok(await kim_cevaplar(Sunucu([v1, v2, v3]), uye(v2)) == [ANA], "iki bot da meşgul → MezarBot cevaplar (kendi uyarısını verir)")

    v1, v2 = Kanal("Oda 1", [ANA], [insan]), Kanal("Oda 2")
    ok(await kim_cevaplar(Sunucu([v1, v2], botlar=[ANA]), uye(v2)) == [ANA], "MüzikBaba sunucuda yoksa her şeyi MezarBot yapar")
    v1 = Kanal("Oda 1")
    ok(await kim_cevaplar(Sunucu([v1], botlar=[IKINCI]), uye(v1)) == [IKINCI], "MezarBot sunucuda yoksa MüzikBaba tek başına çalışır")

    ok(await kim_cevaplar(Sunucu([Kanal("Oda 1")]), uye(None), "kuyruk") == [ANA], "seste olmayanın komutu → yalnızca MezarBot")

    v1, v2 = Kanal("Oda 1", [ANA], [insan]), Kanal("Oda 2")
    cevap = []
    for b in (ANA, IKINCI):
        ornekler._uyelik.clear()
        try:
            await ornekler.denetle(*ctx(b, Sunucu([v1, v2]), uye(v2), "ytdlpguncelle"))
            cevap.append(b)
        except ornekler.BaskaOrnekte:
            pass
    ok(cevap == [ANA, IKINCI], "sahip komutu (ytdlpguncelle) yönlendirilmez")

    print("Slash (kullanıcı botu seçti):")
    v1, v2 = Kanal("Oda 1", [ANA], [insan]), Kanal("Oda 2", [IKINCI])
    m = await slash(ANA, Sunucu([v1, v2]), uye(v2), "atla")
    ok(m and "MüzikBaba" in m, "Oda 2'deyken MezarBot'un /atla'sı → 'senin odanda MüzikBaba çalıyor'")
    v1, v2 = Kanal("Oda 1", [ANA], [insan]), Kanal("Oda 2")
    m = await slash(ANA, Sunucu([v1, v2]), uye(v2), "oynat")
    ok(m and "Oda 1" in m and "MüzikBaba" in m, "MezarBot meşgulken boş odadan /oynat → 'MüzikBaba boşta' önerisi")
    v1, v2 = Kanal("Oda 1", [ANA], [insan]), Kanal("Oda 2")
    ok(await slash(IKINCI, Sunucu([v1, v2]), uye(v2), "oynat") is None, "aynı durumda MüzikBaba'nın /oynat'ı çalışır")
    v1, v2 = Kanal("Oda 1", [ANA], [insan]), Kanal("Oda 2")
    ok(await slash(ANA, Sunucu([v1, v2]), uye(v2), "kuyruk") is None, "bağlanmayan komut (/kuyruk) yönlendirilmez")
    v1, v2 = Kanal("Oda 1", [ANA]), Kanal("Oda 2")   # MezarBot odada ama yalnız (insan yok)
    ok(await slash(ANA, Sunucu([v1, v2]), uye(v2), "oynat") is None, "MezarBot boş odada beklerken /oynat ile taşınabilir")


# ── 2. MüzikBaba profili ──
def profil():
    print("MEZARBOT_PROFIL=muzik:")
    kod = (
        "import os, json; import yapilandirma as y, main as m;"
        "print(json.dumps({'profil': y.MUZIK_PROFILI, 'kilit': os.path.basename(y.KILIT_DOSYA), 'log': os.path.basename(y.LOG_DOSYA),"
        "'env': os.path.basename(y.PROFIL_ENV_DOSYA or ''), 'db': os.path.relpath(y.DB_DOSYA, y.BOT_DIZINI), 'vagonlar': m.vagonlar,"
        "'token_var': bool(os.getenv('DISCORD_TOKEN'))}))"
    )
    ortam = {k: v for k, v in os.environ.items() if k not in ("MEZARBOT_DB", "DISCORD_TOKEN")}
    ortam["MEZARBOT_PROFIL"] = "muzik"
    import json
    d = json.loads(subprocess.run([sys.executable, "-c", kod], cwd=BOT_DIZINI, env=ortam, capture_output=True, text=True, check=True).stdout.strip().splitlines()[-1])
    ok(d["profil"] and d["kilit"] == "muzikbaba.lock" and d["log"] == "muzikbaba.log", "ayrı kilit ve log (ana botla aynı anda çalışabilir)")
    ok(d["env"] == ".env.muzikbaba", "token dosyası: .env.muzikbaba")
    if os.path.exists(os.path.join(BOT_DIZINI, ".env.muzikbaba")):
        ok(d["token_var"], "token .env.muzikbaba'dan yükleniyor")
    ok(d["db"] == os.path.join("data", "muzikbaba.db"), "ayrı veritabanı: data/muzikbaba.db (panel/istek kanalı ayarları çakışmaz)")
    ok(d["vagonlar"] == ["cogs.muzik", "cogs.muzikbaba"], "yalnızca müzik cog'ları yüklenir (yönetim/ekonomi/AI yok)")
    d2 = json.loads(subprocess.run([sys.executable, "-c", kod], cwd=BOT_DIZINI, env={k: v for k, v in ortam.items() if k != "MEZARBOT_PROFIL"},
                                   capture_output=True, text=True, check=True).stdout.strip().splitlines()[-1])
    ok(not d2["profil"] and d2["kilit"] == "bot.lock" and d2["db"] == "mezarbot.db" and "cogs.yonetim" in d2["vagonlar"],
       "profil yokken ana bot eskisi gibi (bot.lock, mezarbot.db, tüm cog'lar)")

    # Çevrimdışı Bot'a müzik profili cog'larını yükle / kaldır (geçici DB)
    yukle = (
        "import asyncio, discord; from discord.ext import commands; from database import veritabanini_kur; veritabanini_kur();\n"
        "async def t():\n"
        "    b = commands.Bot(command_prefix='!', intents=discord.Intents.default())\n"
        "    for v in ['cogs.muzik', 'cogs.muzikbaba']: await b.load_extension(v)\n"
        "    print('KOMUTLAR', len(b.commands), sorted(c.name for c in b.tree.get_commands())[:3], 'yardim' in [c.name for c in b.tree.get_commands()])\n"
        "    for v in ['cogs.muzikbaba', 'cogs.muzik']: await b.unload_extension(v)\n"
        "asyncio.run(t())"
    )
    ortam2 = dict(ortam, MEZARBOT_DB=os.path.join(_tmp, "muzikbaba.db"))
    r = subprocess.run([sys.executable, "-c", yukle], cwd=BOT_DIZINI, env=ortam2, capture_output=True, text=True, timeout=120)
    ok(r.returncode == 0 and "KOMUTLAR" in r.stdout and r.stdout.strip().endswith("True"),
       "müzik + MüzikBaba cog'ları çevrimdışı yüklenip kaldırıldı, /yardim var: " + (r.stdout.strip().splitlines() or [r.stderr[-300:]])[-1])


asyncio.run(yonlendirme())
profil()
print(f"\nTÜM KONTROLLER GEÇTİ ✅ ({GECTI})")
