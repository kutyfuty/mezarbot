"""
README ekran görüntüleri için sahne üretici — embed'ler ve butonlar BOTUN GERÇEK KODUNDAN üretilir
(calma_embedi, MuzikPaneli, _panel_embedi, _yardim_embedi, _ayarlar_embedi, _leaderboard_gonder …),
sadece Discord nesneleri sahte. Çıktı: docs/ekran/sahneler.json → cizici.js bunu Discord görünümünde PNG'ye çevirir.

    venv/bin/python docs/ekran/sahneler.py && node docs/ekran/cizici.js
"""
import asyncio
import json
import os
import sqlite3
import sys
import tempfile
import time
import types

KOK = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["MEZARBOT_DB"] = os.path.join(tempfile.mkdtemp(prefix="mezarbot_ekran_"), "ekran.db")   # gerçek DB'ye dokunma
sys.path.insert(0, KOK)

import discord  # noqa: E402

import database  # noqa: E402
from cogs.muzik import panel as mp  # noqa: E402
from cogs.muzik.filtreler import FiltreDurumu  # noqa: E402
from cogs.muzik.kuyruk import DONGU_KUYRUK, Gecmis, Kuyruk, Parca  # noqa: E402

database.veritabanini_kur()
NS = types.SimpleNamespace

# Örnek kişiler / kanallar (kurgu) — çizici <@id> ve <#id>'yi bu adlarla gösterir
KISILER = {101: "Deniz", 102: "Mert", 103: "Elif", 104: "Can", 105: "Ayşe", 106: "Bora", 107: "Zeynep"}
KANALLAR = {201: "📋・log", 202: "⚠️・uyarılar", 203: "👋・hoş-geldin", 204: "📤・görüşürüz", 205: "📢・duyurular",
            900000000000000301: "🎧 Deniz'in odası", 302: "🎵 Müzik"}
ODA_ID = 900000000000000301
ROLLER = {401: "Üye"}


def bilesenler(view):
    satirlar = {}
    for c in view.children:
        if isinstance(c, discord.ui.DynamicItem):
            c = c.item
        satir = c._rendered_row if getattr(c, "_rendered_row", None) is not None else (c.row or 0)
        if isinstance(c, discord.ui.Button):
            oge = {"tur": "buton", "etiket": c.label or "", "emoji": str(c.emoji) if c.emoji else "",
                   "stil": c.style.name, "kapali": c.disabled}
        else:
            oge = {"tur": "menu", "yer_tutucu": c.placeholder or ""}
        satirlar.setdefault(satir, []).append(oge)
    return [satirlar[k] for k in sorted(satirlar)]


def sahne(ad, embed, view=None, komut=None, genislik=560):
    return {"ad": ad, "embed": embed.to_dict(), "bilesenler": bilesenler(view) if view else [],
            "komut": komut, "genislik": genislik}


def parca(baslik, sanatci, sure, kim, url):
    return Parca(sorgu=url, baslik=baslik, url=url, sure=sure, kaynak="youtube", sanatci=sanatci, isteyen_id=kim)


def muzik_sahneleri():
    simdiki = parca("Barış Manço - Gülpembe", "Barış Manço", 287, 101, "https://youtu.be/ornek1")
    simdiki.kucuk_resim = "kapak"
    kuyruk = Kuyruk()
    for p in (parca("Sezen Aksu - Firuze", "Sezen Aksu", 263, 102, "https://youtu.be/ornek2"),
              parca("Duman - Bu Akşam", "Duman", 222, 103, "https://youtu.be/ornek3"),
              parca("Tarkan - Şımarık", "Tarkan", 234, 101, "https://youtu.be/ornek4"),
              parca("MFÖ - Ele Güne Karşı", "MFÖ", 256, 104, "https://youtu.be/ornek5"),
              parca("Athena - Holigan", "Athena", 211, 105, "https://youtu.be/ornek6"),
              parca("Cem Karaca - Resimdeki Gözyaşları", "Cem Karaca", 318, 102, "https://youtu.be/ornek7")):
        kuyruk.ekle(p)
    gecmis = Gecmis()
    gecmis.ekle(parca("Teoman - İstanbul'da Sonbahar", "Teoman", 270, 103, "https://youtu.be/ornek8"))
    oyn = NS(simdiki=simdiki, vc=NS(voice_privacy_code="1234", channel=NS(name=KANALLAR[302])),
             duraklatildi_mi=lambda: False, konum=lambda: 104, ses=80, otomatik_duraklatildi=False,
             dongu=DONGU_KUYRUK, kuyruk=kuyruk, gecmis=gecmis, otomatik=True,
             dogrudan_aktarim_mi=lambda: True, filtre=FiltreDurumu(normalizasyon=False))
    panel = mp.MuzikPaneli(NS()).guncelle(oyn)
    kuyruk_embed, _ = mp.kuyruk_embedi(oyn, 0)
    return [sahne("muzik-paneli", mp.calma_embedi(oyn), panel, komut="/oynat gülpembe"),
            sahne("kuyruk", kuyruk_embed, komut="/kuyruk")]


def ozel_oda_sahnesi():
    from cogs import ozel_oda
    cog = ozel_oda.OzelOda.__new__(ozel_oda.OzelOda)
    cog._durum = lambda kanal: (True, False)
    kanal = NS(id=ODA_ID, mention=f"<#{ODA_ID}>", user_limit=5, guild=NS(id=1))
    return sahne("ozel-oda", cog._panel_embedi(kanal, {"sahip_id": 101}), ozel_oda.oda_paneli_gorunumu(ODA_ID, True, False))


def dil_sahneleri():
    from cogs import yardim, yonetim
    sahneler = []
    guild = NS(id=1, name="Mezar Kafe", icon=None, get_role=lambda rid: NS(mention=f"<@&{rid}>") if rid else None)
    ayar = {"log_kanal_id": 201, "uyari_kanal_id": 202, "hosgeldin_kanal_id": 203, "gorusuruz_kanal_id": 204,
            "otorol_id": 401, "yama_notlari_kanal_id": 205, "otomod_aktif": 1, "oygec_aktif": 0}
    for dil in ("tr", "en"):
        yardim.sunucu_dil_al = lambda _gid, d=dil: d
        y = yardim.Yardim.__new__(yardim.Yardim)
        sahneler.append(sahne(f"yardim-{dil}", y._yardim_embedi(guild), yardim.YardimView(dil=dil),
                              komut="/yardim" if dil == "tr" else "/help"))
        yonetim.sunucu_dil_al = lambda _gid, d=dil: d
        yonetim.sunucu_ayar_al = lambda _gid, d=dil: dict(ayar, dil=d)
        yonetim.kelime_oyunu_al = lambda _gid: {}
        cog = yonetim.Yonetim.__new__(yonetim.Yonetim)
        sahneler.append(sahne(f"ayarlar-{dil}", cog._ayarlar_embedi(guild), yonetim.AyarlarDilGorunumu(cog, 1),
                              komut="/ayarlar" if dil == "tr" else "/settings"))
    return sahneler


def sesstat_sahnesi():
    from cogs import ses_aktivite
    cog = ses_aktivite.SesAktivite.__new__(ses_aktivite.SesAktivite)
    cog._init_db()
    c = database.db.cursor()
    simdi = time.time()
    for uid, saat, oturum in ((101, 86.4, 212), (103, 71.2, 160), (102, 64.9, 188), (105, 40.3, 97),
                              (104, 33.7, 120), (107, 21.0, 64), (106, 9.5, 31)):
        sn = int(saat * 3600)
        for i in range(oturum):
            sure = sn // oturum + (sn % oturum if i == 0 else 0)
            c.execute("INSERT INTO ses_aktivite (guild_id, user_id, kanal_id, giris_ts, cikis_ts, sure_sn) VALUES (?, ?, ?, ?, ?, ?)",
                      (1, uid, 302, simdi - i * 3600, simdi - i * 3600 + sure, sure))
    database.db.commit()
    cog.bot = NS(get_user=lambda uid: None)
    yakalanan = {}

    async def defer():
        pass

    async def send(embed=None, **_):
        yakalanan["embed"] = embed
    etkilesim = NS(response=NS(defer=defer), followup=NS(send=send),
                   guild=NS(id=1, get_member=lambda uid: NS(display_name=KISILER[uid])))
    asyncio.run(cog._leaderboard_gonder(etkilesim, None, "🏆 Ses Kanalı Şampiyonları (Tüm Zamanlar)"))
    return sahne("sesstat", yakalanan["embed"], komut="/sesstat top")


def main():
    sahneler = muzik_sahneleri() + [ozel_oda_sahnesi()] + dil_sahneleri() + [sesstat_sahnesi()]
    cikti = {"kisiler": KISILER, "kanallar": KANALLAR, "roller": ROLLER, "sahneler": sahneler}
    yol = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sahneler.json")
    with open(yol, "w", encoding="utf-8") as f:
        json.dump(cikti, f, ensure_ascii=False, indent=1)
    print(f"{len(sahneler)} sahne → {yol}")


if __name__ == "__main__":
    main()
