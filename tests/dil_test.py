"""
Çok dillilik testi (ağsız, Discord'a bağlanmaz, gerçek DB'ye dokunmaz):
  1. Koddaki her _t("…") anahtarının ve _t(SABIT) ile çevrilen sabitlerin dil_en.EN'de İngilizcesi var
  2. Yer tutucular ({ad}) Türkçe ve İngilizcede birebir aynı; İngilizce metinde Türkçe karakter kalmamış
  3. Slash komut/parametre açıklamaları ve seçenek adları DilCevirmeni ile İngilizceye çevriliyor
  4. Etkin dil: contextvar sunucunun diline göre ayarlanıyor, görevler doğru dili alıyor

    venv/bin/python tests/dil_test.py            # kontrol
    venv/bin/python tests/dil_test.py --eksik    # eksik anahtarları JSON olarak yazdır (çeviri için)
"""
import ast
import asyncio
import glob
import json
import os
import re
import string
import sys
import tempfile

BOT_DIZINI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ["MEZARBOT_DB"] = os.path.join(tempfile.mkdtemp(prefix="mezarbot_dil_test_"), "test.db")
sys.path.insert(0, BOT_DIZINI)

DOSYALAR = sorted(set(glob.glob(os.path.join(BOT_DIZINI, "cogs", "*.py")) + glob.glob(os.path.join(BOT_DIZINI, "cogs", "muzik", "*.py"))
                      + [os.path.join(BOT_DIZINI, f) for f in ("main.py", "arayuz.py", "muzik_veritabani.py", "ozel_oda_veritabani.py")]))
# Türkçe harf İngilizce çeviride olmamalı — dil adları / bayrak etiketleri gibi bilinçli istisnalar
TR_HARF = re.compile(r"[çğıöşüÇĞİÖŞÜ]")
TR_IZINLI = ("Türkçe", "➕ Oda Oluştur", "🔊 Özel Odalar", "Özel Oda")

_sayac = {"gecti": 0}


def kontrol(kosul, mesaj):
    if not kosul:
        raise AssertionError(mesaj)
    _sayac["gecti"] += 1
    print(f"  ✓ {mesaj}")


def koddaki_anahtarlar():
    anahtarlar = {}
    for yol in DOSYALAR:
        agac = ast.parse(open(yol, encoding="utf-8").read())
        for n in ast.walk(agac):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "_t" and n.args:
                a = n.args[0]
                if isinstance(a, ast.Constant) and isinstance(a.value, str):
                    anahtarlar.setdefault(a.value, f"{os.path.relpath(yol, BOT_DIZINI)}:{n.lineno}")
    return anahtarlar


def sabit_anahtarlar():
    """_t(SABIT) ile çalışma anında çevrilen modül düzeyi sabitler."""
    from cogs import ozel_oda, yonetim
    from cogs.muzik import filtreler, kaynaklar, kuyruk, panel
    import ozel_oda_veritabani as odb
    k = set(kuyruk.DONGU_ETIKET.values())
    k |= {isim for _, isim, _ in panel.KAYNAK_GOSTERIM.values()}
    k |= {e for e, _, a in filtreler.FILTRE_SECENEKLERI.values()} | {a for _, _, a in filtreler.FILTRE_SECENEKLERI.values()}
    k |= {sebep for _, sebep, _ in kaynaklar._HATA_KALIPLARI}
    k |= {ozel_oda.KAPALI_MESAJI, yonetim.DOKUNULMAZ_MESAJ, odb.VARSAYILAN_AYARLAR["ad_sablonu"]}
    k |= {ad for _, ad in ozel_oda.ZORUNLU_IZINLER + ozel_oda.ONERILEN_IZINLER}
    k |= {ad for ad, _ in ozel_oda.AYAR_ANAHTARLARI.values()}
    k |= {"Oda oluştur", "Odamı yönet", "Yardım"}   # KurulumPaneli buton etiketleri (_t(buton.label))
    return {a: "sabit" for a in k}


async def slash_anahtarlari():
    """Komut ağacındaki açıklamalar / seçenek adları (DilCevirmeni'nin çevireceği metinler)."""
    import main
    from discord import app_commands
    for v in main.vagonlar:
        if v not in main.bot.extensions:
            await main.bot.load_extension(v)
    k = {}

    def ekle(m, yer):
        if m and m != "…":
            k.setdefault(m, yer)

    for c in main.bot.tree.walk_commands():
        ekle(c.description, f"/{c.qualified_name}")
        if isinstance(c, app_commands.Command):
            for p in c.parameters:
                ekle(p.description, f"/{c.qualified_name} {p.name}")
                for ch in p.choices or []:
                    ekle(ch.name, f"/{c.qualified_name} {p.name} seçenek")
    return k


async def _slash_ve_kapat():
    sonuc = await slash_anahtarlari()
    import main
    for ad in list(main.bot.extensions):
        await main.bot.unload_extension(ad)   # cog döngüleri (wait_until_ready) asılı kalmasın
    return sonuc


def yer_tutucular(s):
    return sorted({ad for _, ad, _, _ in string.Formatter().parse(s) if ad is not None})


def main():
    import dil
    from dil_en import EN
    kod = koddaki_anahtarlar()
    sabit = sabit_anahtarlar()
    slash = asyncio.run(_slash_ve_kapat())
    hepsi = {**slash, **sabit, **kod}

    if "--eksik" in sys.argv:
        eksik = {a: yer for a, yer in hepsi.items() if a not in EN}
        print(json.dumps(eksik, ensure_ascii=False, indent=1))
        return

    print("\n[1] Kapsam")
    eksik = [f"{yer}: {a[:70]!r}" for a, yer in hepsi.items() if a not in EN]
    kontrol(not eksik, f"{len(hepsi)} anahtarın hepsi çevrilmiş" + ("" if not eksik else " — EKSİK:\n    " + "\n    ".join(eksik[:40])))
    fazla = [a for a in EN if a not in hepsi]
    if fazla:
        print(f"  ℹ kullanılmayan {len(fazla)} çeviri (zararsız): {fazla[:5]}")

    print("\n[2] Biçim")
    for a, yer in hepsi.items():
        tr_yt = yer_tutucular(a) if a in kod else []
        en_yt = yer_tutucular(EN[a]) if a in kod else []
        assert tr_yt == en_yt, f"{yer}: yer tutucular farklı {tr_yt} ≠ {en_yt}: {a[:60]!r}"
        kalan = TR_HARF.sub("", "".join(x for x in [EN[a]] for _ in [0]))
        tr_kalan = [m for m in TR_HARF.findall(EN[a])]
        if tr_kalan and not any(i in EN[a] for i in TR_IZINLI):
            raise AssertionError(f"{yer}: İngilizce metinde Türkçe karakter: {EN[a][:80]!r}")
    kontrol(True, "yer tutucular birebir, İngilizce metinlerde Türkçe karakter yok")

    print("\n[3] Etkin dil")
    dil.dil_zorla("tr")
    kontrol(dil._t("Kuyruk boş.") == "Kuyruk boş.", "Türkçe: anahtar olduğu gibi")
    ornek = next(a for a in kod if "{" in a and a in EN)
    dil.dil_zorla("en")
    ad = yer_tutucular(ornek)
    kontrol(dil._t(ornek, **{x: "X" for x in ad}) == EN[ornek].format(**{x: "X" for x in ad}), f"İngilizce + yer tutucu: {EN[ornek][:50]!r}")
    dil.dil_zorla("tr")
    import database
    database.veritabanini_kur()
    database.sunucu_dil_ayarla(555, "en")

    async def gorev_dili():
        return dil.aktif_dil()

    async def dene():
        t1 = await dil.dilli_gorev(gorev_dili(), 555)
        t2 = await dil.dilli_gorev(gorev_dili(), 556)
        return t1, t2, dil.aktif_dil()
    kontrol(asyncio.run(dene()) == ("en", "tr", "tr"), "dilli_gorev: görev sunucunun dilinde, çağıranın dili değişmez")
    kontrol(dil.dil_ayarla(type("I", (), {"guild_id": 555})()) == "en", "dil_ayarla: guild_id taşıyan nesneden sunucu dili")

    print("\n[3b] Otomatik dil kancaları (buton / olay / slash)")
    import discord
    import types
    dil.kancalari_kur()
    database.sunucu_dil_ayarla(556, "tr")
    sonuc = {}

    async def kancalar():
        class V(discord.ui.View):
            @discord.ui.button(label="x")
            async def b(self, interaction, button):
                sonuc["buton"] = dil.aktif_dil()

        v = V()

        async def izin(_i):
            return True
        v.interaction_check = izin
        await v._scheduled_task(v.children[0], types.SimpleNamespace(guild_id=555, guild=None, user=types.SimpleNamespace(id=1), data={}, response=types.SimpleNamespace(is_done=lambda: True)))
        c = discord.Client(intents=discord.Intents.none())

        async def olay(_m):
            sonuc.setdefault("olay", []).append(dil.aktif_dil())
        await c._run_event(olay, "message", types.SimpleNamespace(guild=types.SimpleNamespace(id=555)))
        await c._run_event(olay, "message", types.SimpleNamespace(guild=types.SimpleNamespace(id=556)))
        await dil.DilAgaci(c).interaction_check(types.SimpleNamespace(guild_id=555, guild=None))
        sonuc["slash"] = dil.aktif_dil()
    asyncio.run(kancalar())
    kontrol(sonuc.get("buton") == "en", "buton tıklaması sunucunun dilinde (View görevi)")
    kontrol(sonuc.get("olay") == ["en", "tr"], "olay dinleyicileri sunucunun dilinde (EN sunucu → en, TR sunucu → tr)")
    kontrol(sonuc.get("slash") == "en", "slash komutu sunucunun dilinde (DilAgaci)")
    dil.dil_zorla("tr")

    print("\n[4] Slash çevirmeni")
    from discord import app_commands, Locale

    async def cevir(m, yer):
        return await dil.DilCevirmeni().translate(app_commands.locale_str(m), Locale.american_english,
                                                  app_commands.TranslationContext(yer, None))
    ornek_slash = next(iter(slash))
    kontrol(asyncio.run(cevir(ornek_slash, app_commands.TranslationContextLocation.command_description)) == EN[ornek_slash],
            f"açıklama İngilizce istemcide çevrilir: {EN[ornek_slash][:50]!r}")
    kontrol(asyncio.run(cevir("oynat", app_commands.TranslationContextLocation.command_name)) is None,
            "komut adları çevrilmez")

    print(f"\nTÜM DİL KONTROLLERİ GEÇTİ ✅ ({_sayac['gecti']})")


if __name__ == "__main__":
    main()
