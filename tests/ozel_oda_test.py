"""
Özel ses odası testleri — Discord'a BAĞLANMAZ, gerçek veritabanına DOKUNMAZ.

Çalıştırma:
    venv/bin/python tests/ozel_oda_test.py

Bölümler:
  [1] Saf mantık: ad temizleme, ad/limit/süre/şablon doğrulama, şablon uygulama, bekleme, ad değişim hakkı,
      temizlik kararı, bot izin kontrolü, sahip izni
  [2] Veritabanı: migrasyon iki kez, varsayılan KAPALI, sunucu izolasyonu, beyaz liste, cache tutarlılığı
  [3] Kalıcı butonlar: custom_id şablonu, panel görünümü, kurulum paneli
  [4] Cog: çevrimdışı yükleme, komut/izin yapısı, kapalı sunucuda ses olayı hiçbir şey yapmaz
  [5] Gerçek DB değişmedi
"""
import asyncio
import os
import shutil
import sys
import tempfile
import types

BOT_DIZINI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GERCEK_DB = os.path.join(BOT_DIZINI, "mezarbot.db")
GECICI = tempfile.mkdtemp(prefix="mezarbot_ozel_oda_test_")
os.environ["MEZARBOT_DB"] = os.path.join(GECICI, "test.db")   # database import edilmeden ÖNCE
sys.path.insert(0, BOT_DIZINI)

_sayac = {"gecti": 0}


def kontrol(kosul, mesaj):
    if not kosul:
        raise AssertionError(mesaj)
    _sayac["gecti"] += 1
    print(f"  ✓ {mesaj}")


def hata_verir(fonk, *args):
    try:
        fonk(*args)
    except ValueError:
        return True
    return False


def dosya_izi(yol):
    return (os.path.getsize(yol), os.path.getmtime(yol)) if os.path.exists(yol) else None


def saf_mantik(oo):
    import discord
    print("\n[1] Saf mantık")
    kontrol(oo.ad_temizle("  Ali'nin   odası \n ") == "Ali'nin odası", "ad_temizle: boşluk / satır sonu sadeleşir")
    kontrol(oo.ad_temizle("@everyone selam @here") == "selam", "ad_temizle: @everyone / @here silinir")
    kontrol(oo.ad_temizle("oda <@123456789012345678> <@&123456789012345678> <#123456789012345678>") == "oda",
            "ad_temizle: kullanıcı / rol / kanal etiketleri silinir")
    kontrol(oo.ad_temizle("gel https://kotu.example/x www.a.com discord.gg/abc discord.com/invite/x") == "gel",
            "ad_temizle: linkler ve davetler silinir")
    kontrol(oo.ad_temizle("<:pepe:123456789012345678> oda") == "pepe oda", "ad_temizle: özel emoji → adı")
    kontrol(oo.ad_temizle("a​b\x00c") == "a b c", "ad_temizle: görünmez / kontrol karakterleri")
    kontrol(oo.ad_temizle("mail@ornek") == "mailornek", "ad_temizle: kalan @ işaretleri silinir")
    kontrol(len(oo.ad_temizle("x" * 80)) == oo.AD_MAX, "ad_temizle: 50 karaktere kırpılır")
    kontrol(oo.ad_temizle("🔊 Öğrenci Çayı") == "🔊 Öğrenci Çayı", "ad_temizle: emoji ve Türkçe karakter korunur")

    kontrol(oo.ad_dogrula("  Sohbet  ") == "Sohbet", "ad_dogrula: geçerli ad")
    kontrol(hata_verir(oo.ad_dogrula, "x" * 51), "ad_dogrula: 51 karakter reddedilir")
    kontrol(not hata_verir(oo.ad_dogrula, "x" * 50), "ad_dogrula: 50 karakter kabul")
    kontrol(hata_verir(oo.ad_dogrula, "@everyone") and hata_verir(oo.ad_dogrula, "https://a.b") and hata_verir(oo.ad_dogrula, "   "),
            "ad_dogrula: sadece etiket / link / boşluk reddedilir")

    kontrol([oo.limit_dogrula(x) for x in ("0", "5", " 99 ", 7, "sınırsız", "Limitsiz", "yok")] == [0, 5, 99, 7, 0, 0, 0],
            "limit_dogrula: 0-99, int ve 'sınırsız'")
    kontrol(all(hata_verir(oo.limit_dogrula, x) for x in ("-1", "100", "abc", "", "5.5", 100, -3, True, None)),
            "limit_dogrula: negatif / 100+ / metin / ondalık / bool reddedilir")

    kontrol(oo.sure_dogrula("30") == 30 and oo.sure_dogrula("45s") == 45 and oo.sure_dogrula("2dk") == 120
            and oo.sure_dogrula("1:30") == 90, "sure_dogrula: 30 / 45s / 2dk / 1:30")
    kontrol(all(hata_verir(oo.sure_dogrula, x) for x in ("5", "2 saat", "", "999999")), "sure_dogrula: sınır dışı / geçersiz")

    kontrol(oo.sablon_uygula("🔊 {kullanici} odası", "Ali") == "🔊 Ali odası", "şablon: {kullanici}")
    kontrol(oo.sablon_uygula("Oda #{sayi}", "Ali", 3) == "Oda #3", "şablon: {sayi}")
    kontrol(oo.sablon_uygula("🔊 {kullanici} odası", "@everyone https://x.y") == "🔊 Üye odası",
            "şablon: kullanıcı adındaki etiket/link temizlenir, boşsa 'Üye'")
    kontrol(oo.sablon_uygula("{kullanici.__class__} {0}", "Ali") == "{kullanici.__class__} {0}",
            "şablon: str.format kullanılmaz (alan erişimi enjeksiyonu yok)")
    kontrol(len(oo.sablon_uygula("{kullanici} " + "x" * 60, "Ali")) == oo.AD_MAX, "şablon: sonuç 50 karaktere kırpılır")
    kontrol(oo.sablon_uygula("", "Ali") == "🔊 Ali odası", "şablon boşsa varsayılan şablon")
    kontrol(oo.sablon_dogrula("  {kullanici}  | {sayi} ") == "{kullanici} | {sayi}", "sablon_dogrula: geçerli")
    kontrol(all(hata_verir(oo.sablon_dogrula, x) for x in ("", "{isim} odası", "{kullanici.__class__}", "x" * 61, "@everyone")),
            "sablon_dogrula: boş / bilinmeyen alan / çok uzun / boş sonuç reddedilir")

    kontrol(oo.evet_hayir("Evet") and not oo.evet_hayir("hayır") and hata_verir(oo.evet_hayir, "belki"), "evet_hayir")
    kontrol(oo.ayar_anahtari_coz("Şablon") == "sablon" and oo.ayar_anahtari_coz("süre") == "sure"
            and oo.ayar_anahtari_coz("x") is None, "ayar anahtarı eş anlamlıları")

    kontrol(oo.bekleme_kalan(None, 100) == 0 and oo.bekleme_kalan(100, 105, 20) == 15 and oo.bekleme_kalan(100, 130, 20) == 0,
            "oluşturma bekleme süresi (20 sn)")
    kontrol(oo.ad_degisim_kalan([], 1000) == 0 and oo.ad_degisim_kalan([900], 1000) == 0, "ad değişimi: 2 hak")
    kontrol(oo.ad_degisim_kalan([900, 950], 1000) == 500, "ad değişimi: 2 hak dolu → en eski değişiklik + 600 sn")
    kontrol(oo.ad_degisim_kalan([100, 950], 1000) == 0, "ad değişimi: 10 dk'dan eski değişiklik sayılmaz")

    K = oo.temizlik_karari
    kontrol(K(2, None, 100, 30) == "tut" and K(1, 50, 100, 30) == "tut", "temizlik: içeride insan varsa tut")
    kontrol(K(0, None, 100, 30) == "zamanla", "temizlik: yeni boşaldı → zamanla")
    kontrol(K(0, 80, 100, 30) == "bekle" and K(0, 70, 100, 30) == "sil" and K(0, 60, 100, 30) == "sil",
            "temizlik: süre dolmadan bekle, dolunca sil")
    kontrol(K(0, 200, 100, 30) == "bekle", "temizlik: butonla açılan odanın katılma payı (gelecekteki başlangıç)")

    P = discord.Permissions
    tam = P(view_channel=True, manage_channels=True, manage_roles=True, move_members=True, connect=True,
            send_messages=True, embed_links=True, mute_members=True, deafen_members=True, read_message_history=True)
    kontrol(oo.eksik_izinler(tam) == ([], []), "bot izinleri: tam yetki → eksik yok")
    kontrol(oo.eksik_izinler(P(administrator=True)) == ([], []), "bot izinleri: Yönetici her şeyi karşılar")
    zorunlu, onerilen = oo.eksik_izinler(P(view_channel=True, connect=True, send_messages=True, embed_links=True))
    kontrol(zorunlu == ["Kanalları Yönet", "Rolleri Yönet (izin geçersiz kılmaları için)", "Üyeleri Taşı"]
            and len(onerilen) == 3, f"bot izinleri: eksikler tek tek Türkçe listelenir ({len(zorunlu)} zorunlu)")
    sahip = oo.sahip_izni(P(manage_channels=True))
    kontrol(sahip.manage_channels and sahip.move_members and sahip.mute_members is None and sahip.deafen_members is None
            and sahip.manage_roles is None and sahip.administrator is None,
            "sahip izni: bot'ta olmayan (sustur/sağırlaştır) verilmez, rol yönetimi asla verilmez")
    kontrol(oo.sahip_izni(tam).mute_members and oo.sahip_izni(tam).deafen_members, "sahip izni: bot'ta varsa sustur/sağırlaştır")


def veritabani():
    print("\n[2] Veritabanı")
    import database as d
    import ozel_oda_veritabani as odb
    d.veritabanini_kur()
    odb.ozel_oda_veritabanini_kur()
    odb.ozel_oda_veritabanini_kur()
    kolonlar = {r[1] for r in d.db.execute("PRAGMA table_info(ozel_oda_ayarlar)")}
    kontrol(set(odb.OZEL_ODA_AYAR_KOLONLARI) <= kolonlar, "ozel_oda_ayarlar: tüm kolonlar (migrasyon iki kez)")
    kontrol({"kanal_id", "sunucu_id", "sahip_id", "olusturma", "kilitli", "gizli", "panel_mesaj_id"}
            <= {r[1] for r in d.db.execute("PRAGMA table_info(ozel_odalar)")}, "ozel_odalar şeması")
    A, B = 700000000000000001, 700000000000000002
    kontrol(not odb.aktif_mi(A) and odb.ayar_al(A) is None, "varsayılan: sistem KAPALI, kayıt yok")
    odb.ayar_guncelle(A, kategori_id=11, hub_id=12)
    kontrol(not odb.aktif_mi(A) and odb.ayar_al(A)['bos_silme_suresi'] == 30 and odb.ayar_al(A)['kisi_basi_oda'] == 1
            and odb.ayar_al(A)['ad_sablonu'] == "🔊 {kullanici} odası", "kurulum kaydı açmaz; varsayılanlar (30 sn, 1 oda)")
    odb.ayar_guncelle(A, aktif=1, varsayilan_limit=5)
    kontrol(odb.aktif_mi(A) and not odb.aktif_mi(B), "açma sunucu bazlı")
    try:
        odb.ayar_guncelle(A, **{"aktif = 1; DROP TABLE ozel_odalar; --": 1})
        kontrol(False, "beyaz liste")
    except ValueError:
        kontrol(True, "ayar_guncelle: beyaz liste dışı kolon reddedildi")
    try:
        odb.oda_guncelle(1, sunucu_id=5)
        kontrol(False, "oda beyaz listesi")
    except ValueError:
        kontrol(True, "oda_guncelle: sunucu_id gibi kolonlar değiştirilemez")
    odb.oda_ekle(A, 1001, 42)
    odb.oda_ekle(A, 1002, 43)
    odb.oda_ekle(B, 2001, 42)
    kontrol([o['kanal_id'] for o in odb.sahibin_odalari(A, 42)] == [1001] and len(odb.sunucu_odalari(B)) == 1,
            "odalar sunucu bazlı (aynı kullanıcı iki sunucuda ayrı)")
    odb.oda_guncelle(1001, sahip_id=43, kilitli=1)
    satir = d.db.execute("SELECT sahip_id, kilitli FROM ozel_odalar WHERE kanal_id = 1001").fetchone()
    kontrol(tuple(satir) == (43, 1) and odb.oda_al(1001)['sahip_id'] == 43, "oda_guncelle: DB ve cache birlikte")
    odb.ozel_oda_cache_yukle()
    kontrol(odb.oda_al(1001)['kilitli'] == 1 and odb.ayar_al(A)['varsayilan_limit'] == 5, "cache DB'den aynen yeniden yüklenir")
    kontrol(odb.oda_sil(1001) and not odb.oda_sil(1001) and not odb.oda_mi(1001), "oda_sil idempotent")
    odb.sunucu_odalarini_unut(B)
    kontrol(not odb.sunucu_odalari(B) and odb.sunucu_odalari(A), "sunucudan çıkınca sadece o sunucunun odaları unutulur")
    odb.oda_sil(1002)
    return odb


def kalici_butonlar(oo):
    print("\n[3] Kalıcı butonlar")
    import discord
    kid = 123456789012345678
    v = oo.oda_paneli_gorunumu(kid, kilitli=True, gizli=False)
    kimlikler = [c.custom_id for c in v.children]
    kontrol(v.timeout is None and len(kimlikler) == 8 and all(k.endswith(f":{kid}") for k in kimlikler),
            "oda paneli: 8 buton, custom_id kanal ID'sini taşır, zaman aşımı yok")
    kontrol(all(oo.OdaButonu.__discord_ui_compiled_template__.fullmatch(k) for k in kimlikler),
            "tüm panel custom_id'leri DynamicItem şablonuna uyar (yeniden başlatma sonrası çözülür)")
    etiketler = {c.custom_id.split(":")[1]: c.item.label for c in v.children}   # DynamicItem → sarılı Button
    kontrol(etiketler["kilit"] == "Aç" and etiketler["gizlilik"] == "Gizle", "buton etiketleri odanın durumunu yansıtır")
    eslesme = oo.OdaButonu.__discord_ui_compiled_template__.fullmatch(f"ozeloda:devret:{kid}")
    oge = asyncio.run(oo.OdaButonu.from_custom_id(None, None, eslesme))
    kontrol(oge.eylem == "devret" and oge.kanal_id == kid, "from_custom_id: eylem + kanal ID çözülür")
    kontrol(not oo.OdaButonu.__discord_ui_compiled_template__.fullmatch("ozeloda:kur:olustur")
            and not oo.OdaButonu.__discord_ui_compiled_template__.fullmatch(f"ozeloda:sil:{kid}"),
            "kurulum paneli / bilinmeyen eylem şablona uymaz")

    async def kurulum_paneli():
        return oo.KurulumPaneli()
    kp = asyncio.run(kurulum_paneli())
    kontrol(kp.is_persistent() and sorted(c.custom_id for c in kp.children)
            == ["ozeloda:kur:olustur", "ozeloda:kur:yardim", "ozeloda:kur:yonet"], "kurulum paneli kalıcı, sabit custom_id")
    kontrol(isinstance(oo.LimitModali(kid, 5).deger, discord.ui.TextInput) and oo.AdModali(kid, "x").deger.max_length == 50,
            "modallar: ad en fazla 50 karakter")


def cog_testleri(oo, odb):
    print("\n[4] Cog (çevrimdışı)")
    import discord
    from discord.ext import commands

    async def calis():
        bot = commands.Bot(command_prefix="!", intents=discord.Intents.default())
        await bot.load_extension("cogs.ozel_oda")
        cog = bot.get_cog("OzelOda")
        kontrol(cog is not None, "cogs.ozel_oda yüklendi")
        agac = {c.name: c for c in bot.tree.get_commands()}
        kontrol({"ozelodaaktif", "ozelodakapat", "ozeloda", "oda"} <= set(agac), "slash komutları kayıtlı")
        for ad in ("ozelodaaktif", "ozelodakapat", "ozeloda"):
            kontrol(agac[ad].default_permissions is not None and agac[ad].default_permissions.manage_guild,
                    f"/{ad}: varsayılan olarak sadece Sunucuyu Yönet")
        kontrol(agac["oda"].default_permissions is None, "/oda herkese açık (yetki komut içinde: sahip / yönetici)")
        alt = sorted(c.name for c in agac["oda"].commands)
        kontrol(alt == sorted(["bilgi", "ad", "limit", "kilitle", "ac", "gizle", "goster", "davet", "at", "yasakla",
                               "yasak-kaldir", "devret", "sahiplen", "panel"]), f"/oda alt komutları: {', '.join(alt)}")
        kontrol(sorted(c.name for c in agac["ozeloda"].commands) == ["ayar", "durum"], "/ozeloda durum + ayar")
        kontrol(bot.get_command("oda davet") is not None and bot.get_command("ozeloda ayar") is not None,
                "prefix (!) komutları da kayıtlı")

        # Kapalı sunucu: ses olayı hiçbir şey başlatmaz (hub ID'si eşleşse bile)
        A = 700000000000000003
        odb.ayar_guncelle(A, hub_id=555, aktif=0)
        baslatilan = []
        cog._arka_gorev = lambda coro: (baslatilan.append(coro), coro.close())
        guild = types.SimpleNamespace(id=A)
        uye = types.SimpleNamespace(id=1, bot=False, guild=guild)
        hub = types.SimpleNamespace(id=555, members=[uye])
        await cog.on_voice_state_update(uye, types.SimpleNamespace(channel=None), types.SimpleNamespace(channel=hub))
        kontrol(not baslatilan, "kapalı sunucuda hub'a girmek oda açmaz")
        odb.ayar_guncelle(A, aktif=1)
        await cog.on_voice_state_update(uye, types.SimpleNamespace(channel=None), types.SimpleNamespace(channel=hub))
        kontrol(len(baslatilan) == 1, "açık sunucuda hub'a girmek oda açma görevini başlatır")
        bot_uye = types.SimpleNamespace(id=2, bot=True, guild=guild)
        await cog.on_voice_state_update(bot_uye, types.SimpleNamespace(channel=None), types.SimpleNamespace(channel=hub))
        kontrol(len(baslatilan) == 1, "botlar hub'a girince oda açılmaz")

        # Kapatmadan kalan oda: sistem kapalıyken de boşalması izlenir (sonra silinsin diye)
        odb.ayar_guncelle(A, aktif=0)
        odb.oda_ekle(A, 3001, 1)
        oda_kanal = types.SimpleNamespace(id=3001, members=[], guild=guild)
        await cog.on_voice_state_update(uye, types.SimpleNamespace(channel=oda_kanal), types.SimpleNamespace(channel=None))
        kontrol(3001 in cog._bos_baslangic and not baslatilan[1:], "kapalı sunucuda kalan oda boşalınca silinmek üzere işaretlenir")
        await cog.on_voice_state_update(uye, types.SimpleNamespace(channel=None), types.SimpleNamespace(channel=oda_kanal))
        kontrol(3001 not in cog._bos_baslangic, "biri geri girince silme işareti kalkar")
        odb.oda_sil(3001)
        await bot.unload_extension("cogs.ozel_oda")
        kontrol("OzelOda" not in bot.cogs, "cog kaldırıldı (döngü durdu)")
    asyncio.run(calis())


def main():
    gercek_iz = {ek: dosya_izi(GERCEK_DB + ek) for ek in ("", "-wal")}
    try:
        from cogs import ozel_oda as oo
        saf_mantik(oo)
        odb = veritabani()
        kalici_butonlar(oo)
        cog_testleri(oo, odb)
        print("\n[5] Gerçek veritabanı")
        kontrol({ek: dosya_izi(GERCEK_DB + ek) for ek in ("", "-wal")} == gercek_iz, "gerçek mezarbot.db (+wal) değişmedi")
        print(f"\nTÜM KONTROLLER GEÇTİ ✅ ({_sayac['gecti']})")
        return 0
    except AssertionError as e:
        print(f"\n❌ BAŞARISIZ: {e}")
        return 1
    finally:
        shutil.rmtree(GECICI, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
