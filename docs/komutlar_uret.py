"""KOMUTLAR.md (TR) ve COMMANDS.md (EN) — botun komut ağacından üretilir. venv/bin/python docs/komutlar_uret.py"""
import asyncio, logging, os, sys, tempfile
os.environ["MEZARBOT_DB"] = os.path.join(tempfile.mkdtemp(prefix="mezarbot_komut_"), "k.db")
KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)
logging.disable(logging.CRITICAL)
import main  # noqa: E402
from discord import app_commands  # noqa: E402
from dil_en import EN  # noqa: E402

BOLUMLER = [("cogs.muzik.cog", "🎵 Müzik", "🎵 Music"), ("cogs.ozel_oda", "🔊 Özel ses odaları", "🔊 Private voice rooms"),
            ("cogs.ses_aktivite", "📊 Ses istatistikleri", "📊 Voice stats"),
            ("cogs.yonetim", "🛡️ Moderasyon ve sunucu ayarları", "🛡️ Moderation & server settings"),
            ("cogs.yapayzeka", "🤖 Yapay zekâ", "🤖 AI"), ("cogs.konusma", "🗣️ Seslendirme (TTS)", "🗣️ Text to speech"),
            ("cogs.ceviri", "🌐 Çeviri", "🌐 Translation"), ("cogs.yardim", "❓ Yardım", "❓ Help"),
            ("cogs.sunucu_onay", "🚪 Üye onay kapısı (opsiyonel, config ile açılır)", "🚪 Member approval gate (optional, enabled in config)")]


async def topla():
    for v in main.vagonlar:
        if v not in main.bot.extensions:
            await main.bot.load_extension(v)
    satirlar = []
    for c in main.bot.tree.walk_commands():
        if isinstance(c, app_commands.Command):
            satirlar.append((c.module, f"/{c.qualified_name}", c.description))
    for ad in list(main.bot.extensions):
        await main.bot.unload_extension(ad)
    return sorted(satirlar)


def yaz(satirlar, dil):
    en = dil == "en"
    out = ["# MezarBot commands" if en else "# MezarBot komutları", "",
           ("Most commands work with both `/` (slash) and `!` (prefix); grouped commands (e.g. `/oda`, `/sesstat`) are "
            "slash-only. Command names are Turkish (prefix commands also have English aliases like `!play`, `!skip`). "
            "Generated from the bot's command tree.") if en else
           ("Komutların çoğu hem `/` (slash) hem de `!` (önek) ile kullanılabilir; alt komutlu gruplar (ör. `/oda`, "
            "`/sesstat`) sadece slash ile çalışır. Liste botun komut ağacından üretildi."), ""]
    for modul, tr_b, en_b in BOLUMLER:
        out += [f"## {en_b if en else tr_b}", "", "| Command | Description |" if en else "| Komut | Açıklama |", "|---|---|"]
        for m, ad, aciklama in satirlar:
            if m == modul:
                out.append(f"| `{ad}` | {(EN.get(aciklama, aciklama) if en else aciklama).replace('|', '/')} |")
        out.append("")
    out += ["## Message reactions" if en else "## Mesaj tepkileri", ""]
    out += (["- React with 🇬🇧 / 🇺🇸 to translate a message to English, 🇹🇷 to Turkish (Groq).",
             "- Mention the bot to chat with the AI.", ""] if en else
            ["- Bir mesaja 🇬🇧 / 🇺🇸 tepkisi → İngilizce çeviri, 🇹🇷 → Türkçe çeviri (Groq).",
             "- Botu etiketleyerek yapay zekâyla sohbet edilir.", ""])
    open(os.path.join(KOK, "COMMANDS.md" if en else "KOMUTLAR.md"), "w", encoding="utf-8").write("\n".join(out))


s = asyncio.run(topla())
yaz(s, "tr"); yaz(s, "en")
print(f"{len(s)} komut → KOMUTLAR.md, COMMANDS.md")
