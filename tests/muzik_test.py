"""
MezarBot müzik testleri — Discord'a BAĞLANMAZ, gerçek veritabanına DOKUNMAZ.

Çalıştırma:
    venv/bin/python tests/muzik_test.py            # hepsi (ağ gerektirenler dahil)
    venv/bin/python tests/muzik_test.py --agsiz    # sadece çevrimdışı testler

Bölümler:
  [1] Saf mantık: kuyruk / döngü / sarma / oylama / girdi sınıflandırma / Spotify embed / LRC / filtre durumu
  [2] Müzik veritabanı: migrasyon iki kez, eski !oygec taşıması, sunucu izolasyonu, beyaz liste, kişisel listeler
  [3] Sunucu başına oynatıcı izolasyonu
  [4] Oynatıcı durum makinesi — yerel ses dosyalarıyla, sahte ses istemcisiyle (FFmpeg gerçek):
      sıralı çalma, ısıtılmış geçiş, şarkı döngüsü, atla, sarma, filtre/ses değişimi, kısıtlı parça atlama,
      akış kopunca kaldığı yerden devam, otomatik oynatma, kapanışta FFmpeg temizliği
  [5] (ağ) Gerçek akış: her filtre zinciri + doğrudan aktarım, BİREBİR discord.FFmpegOpusAudio argümanlarıyla
      5 sn → çıkış kodu 0; 10 sn gerçek-zaman oranı (RTF); tampon üzerinden okuma + konum
  [6] (ağ) Kaynaklar: YouTube arama/video/playlist, YT Music, SoundCloud, doğrudan link, yaş kısıtlı,
      Spotify parça/albüm/playlist → YouTube, otomatik oynatma (Mix)
  [7] (ağ) LRCLIB sözler (Türkçe şarkı)
  [8] Kaynak temizliği: işçi süreçler kapandı, zombi / artık ffmpeg yok, gerçek DB değişmedi
"""
import asyncio
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import types

BOT_DIZINI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GERCEK_DB = os.path.join(BOT_DIZINI, "mezarbot.db")
AGSIZ = "--agsiz" in sys.argv
GECICI = tempfile.mkdtemp(prefix="mezarbot_muzik_test_")
os.environ["MEZARBOT_DB"] = os.path.join(GECICI, "test.db")   # database import edilmeden ÖNCE
sys.path.insert(0, BOT_DIZINI)

_sayac = {"gecti": 0, "atlandi": 0}


def kontrol(kosul, mesaj):
    if not kosul:
        raise AssertionError(mesaj)
    _sayac["gecti"] += 1
    print(f"  ✓ {mesaj}")


def atla(mesaj):
    _sayac["atlandi"] += 1
    print(f"  ⏭ ATLANDI: {mesaj}")


def dosya_izi(yol):
    return (os.path.getsize(yol), os.path.getmtime(yol)) if os.path.exists(yol) else None


class LogYakalayici(logging.Handler):
    def __init__(self):
        super().__init__(logging.INFO)
        self.kayitlar = []

    def emit(self, kayit):
        self.kayitlar.append(kayit.getMessage())

    def var_mi(self, parca):
        return any(parca in k for k in self.kayitlar)


async def bekle(kosul, zaman=15.0, aralik=0.02):
    son = time.monotonic() + zaman
    while time.monotonic() < son:
        if kosul():
            return True
        await asyncio.sleep(aralik)
    return kosul()


def ffmpeg_cocuklari():
    """Bu sürecin ffmpeg çocukları: [(pid, durum)] — 'Z' zombi demek."""
    sonuc = []
    for ad in os.listdir("/proc"):
        if not ad.isdigit():
            continue
        try:
            with open(f"/proc/{ad}/stat") as f:
                stat = f.read()
        except OSError:
            continue
        kapanis = stat.rfind(")")
        komut = stat[stat.find("(") + 1:kapanis]
        alanlar = stat[kapanis + 2:].split()
        if komut == "ffmpeg" and int(alanlar[1]) == os.getpid():
            sonuc.append((int(ad), alanlar[0]))
    return sonuc


# ══════════════════════════════════════════════
#  [1] SAF MANTIK
# ══════════════════════════════════════════════

def saf_mantik():
    print("\n[1] Saf mantık")
    from cogs.muzik.kuyruk import (DONGU_KAPALI, DONGU_KUYRUK, DONGU_SARKI, Gecmis, Kuyruk, KuyrukDolu, Parca,
                                   dongu_sonraki_mod, hedef_konum, oylama_esigi, sure_coz, sure_metni)
    P = lambda i, **k: Parca(sorgu=f"https://youtu.be/{i:011d}", baslik=f"Parça {i}", sure=100, **k)

    k = Kuyruk(limit=5)
    for i in range(1, 4):
        k.ekle(P(i))
    k.basa_ekle(P(9))
    kontrol([p.baslik for p in k] == ["Parça 9", "Parça 1", "Parça 2", "Parça 3"], "ekle + sıradakine ekle (başa)")
    kontrol(k.kaldir(2).baslik == "Parça 1" and len(k) == 3, "kaldır (1 tabanlı)")
    k.tasi(3, 1)
    kontrol([p.baslik for p in k] == ["Parça 3", "Parça 9", "Parça 2"], "taşı 3 → 1")
    try:
        k.tasi(0, 9)
        kontrol(False, "taşı geçersiz numara")
    except IndexError:
        kontrol(True, "taşı: geçersiz numara IndexError")
    k.ekle(P(4)), k.ekle(P(5))
    try:
        k.ekle(P(6))
        kontrol(False, "kuyruk limiti")
    except KuyrukDolu:
        kontrol(True, "kuyruk limiti (KuyrukDolu)")
    kontrol(k.toplu_ekle([P(7), P(8)]) == 0, "toplu_ekle limite saygı duyar")
    import random as _r
    once = [p.baslik for p in k]
    k.karistir(_r.Random(3))
    kontrol(sorted(p.baslik for p in k) == sorted(once), "karıştır: aynı parçalar")
    atilan = k.atla_konuma(3)
    kontrol(len(atilan) == 2 and len(k) == 3, "belirli numaraya atla")
    kontrol(k.temizle() == 3 and k.bos_mu(), "temizle")

    # Döngü modları
    k = Kuyruk()
    a, b = P(1), P(2)
    k.ekle(b)
    kontrol(k.sonraki(a, DONGU_SARKI) is a, "şarkı döngüsü: aynı parça (akış URL'si yeniden kullanılır)")
    kontrol(k.sonraki(a, DONGU_SARKI, atlandi=True) is b, "şarkı döngüsü + atla → sıradaki")
    k.ekle(b)
    nxt = k.sonraki(a, DONGU_KUYRUK)
    kontrol(nxt is b and len(k) == 1 and k[0].baslik == "Parça 1", "kuyruk döngüsü: biten sona eklenir")
    kontrol(k.sonraki(b, DONGU_KAPALI).baslik == "Parça 1" and k.bos_mu(), "döngü kapalı: sıradaki")
    kontrol(k.sonraki(P(3, otomatik=True), DONGU_KUYRUK) is None, "otomatik (radyo) parçaları kuyruk döngüsüne girmez")
    kontrol([dongu_sonraki_mod(m) for m in (DONGU_KAPALI, DONGU_SARKI, DONGU_KUYRUK)] == [DONGU_SARKI, DONGU_KUYRUK, DONGU_KAPALI],
            "döngü butonu: kapalı → şarkı → kuyruk → kapalı")
    g = Gecmis(limit=3)
    for i in range(5):
        g.ekle(P(i, video_id=f"v{i}"))
    kontrol(len(g) == 3 and g.geri_al().baslik == "Parça 4" and g.video_idleri() == {"v2", "v3"}, "geçmiş: limit + önceki")

    # Sarma matematiği
    kontrol(sure_coz("1:30") == (90, 0) and sure_coz("+30") == (30, 1) and sure_coz("-10") == (10, -1), "sure_coz: 1:30 / +30 / -10")
    kontrol(sure_coz("1:02:03") == (3723, 0) and sure_coz("2m15s") == (135, 0) and sure_coz("90") == (90, 0), "sure_coz: saat, 2m15s, düz saniye")
    kontrol(sure_coz("1:75") == (None, None) and sure_coz("abc") == (None, None) and sure_coz("") == (None, None), "sure_coz: geçersizler")
    kontrol(hedef_konum(50, 30, 1, 200) == 80 and hedef_konum(50, 70, -1, 200) == 0, "ileri/geri sar + alt sınır 0")
    kontrol(hedef_konum(50, 500, 0, 200) == 199 and hedef_konum(10, 30, 1, 0) == 40, "üst sınır (süre-1) / canlıda sınırsız")
    kontrol(sure_metni(185) == "3:05" and sure_metni(3725) == "1:02:05" and sure_metni(None) == "—", "sure_metni")

    # Oylama eşiği
    kontrol([oylama_esigi(n, 0.5) for n in (0, 1, 2, 3, 4, 5)] == [1, 1, 1, 2, 2, 3], "oylama eşiği %50: ceil(n/2)")
    kontrol(oylama_esigi(4, 0.75) == 3 and oylama_esigi(10, 1.0) == 10 and oylama_esigi(3, 0.01) == 1, "oylama eşiği %75 / %100 / alt sınır")

    # Parça akış geçerliliği
    p = P(1)
    p.akis_url = f"https://rr1.googlevideo.com/videoplayback?expire={int(time.time()) + 3600}&x=1"
    kontrol(p.akis_gecerli_mi() and not p.akis_gecerli_mi(pay=4000), "YouTube expire parametresi ile URL geçerliliği")
    p.akis_url, p.cozulme_zamani = "https://cdn.example/x.m3u8", time.time() - 400
    kontrol(not p.akis_gecerli_mi(), "expire'sız URL 5 dk sonra yenilenir")

    # Girdi sınıflandırma
    from cogs.muzik.kaynaklar import aday_puani, en_iyi_aday, girdi_turu, hata_sebebi, spotify_embed_coz
    ornekler = {
        "tarkan şımarık": "arama",
        "https://www.youtube.com/watch?v=cpp69ghR1IM": "url",
        "https://music.youtube.com/watch?v=cpp69ghR1IM&si=abc": "url",
        "https://youtu.be/cpp69ghR1IM": "url",
        "https://www.youtube.com/watch?v=cpp69ghR1IM&list=RDcpp69ghR1IM": "url",
        "https://www.youtube.com/playlist?list=PLFgquLnL59alCl_2TQvOiD5Vgm1hCaGSI": "playlist",
        "https://music.youtube.com/playlist?list=OLAK5uy_abc": "playlist",
        "https://soundcloud.com/tarkan/sets/best": "playlist",
        "https://soundcloud.com/tarkan/simarik": "url",
        "https://open.spotify.com/intl-tr/track/4cOdK2wGLETKBW3PvgPWqT?si=x": "spotify",
        "spotify:album:4aawyAB9vmqN3uQ7FjRGTy": "spotify",
        "https://spotify.link/AbCdEf123": "spotify_kisa",
        "https://example.com/radyo.mp3": "url",
    }
    kontrol(all(girdi_turu(g)[0] == t for g, t in ornekler.items()), f"girdi sınıflandırma ({len(ornekler)} örnek)")
    kontrol(girdi_turu("https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M")[1] == ("playlist", "37i9dQZF1DXcBWIGoYBM5M"),
            "Spotify tür + ID çıkarımı")
    h = hata_sebebi(Exception("ERROR: [youtube] x: Sign in to confirm your age."))
    kontrol(h.kalici and "yaş" in h.sebep, "yt-dlp hatası → Türkçe sebep (yaş kısıtı, kalıcı)")
    kontrol(not hata_sebebi(Exception("HTTP Error 429: Too Many Requests")).kalici, "429 geçici sayılır")
    varlik = {"type": "playlist", "name": "Test Listesi", "trackList": [
        {"title": "Şımarık", "subtitle": "Tarkan,\xa0Ozan", "duration": 192000, "uri": "spotify:track:AAAAAAAAAAAAAAAAAAAAAA"},
        {"title": "", "subtitle": "x"}]}
    baslik, parcalar = spotify_embed_coz(varlik)
    kontrol(baslik == "Test Listesi" and len(parcalar) == 1 and parcalar[0].sorgu == "ytsearch5:Tarkan, Ozan - Şımarık"
            and parcalar[0].beklenen_sure == 192, "Spotify embed → YouTube arama sorgusu (süre eşleşmeli)")
    adaylar = [{"id": "a", "title": "Tarkan - Şımarık (Live)", "duration": 193},
               {"id": "b", "title": "Tarkan - Şımarık (Official Audio)", "duration": 191},
               {"id": "c", "title": "Tarkan - Şımarık", "duration": 260}]
    kontrol(en_iyi_aday(adaylar, "Tarkan - Şımarık", 192)[0]["id"] == "b", "en iyi aday: süre + 'live' cezası")
    kontrol(aday_puani("x (8D Audio)", 192, "x", 192) > aday_puani("x", 200, "x", 192), "8D/slowed varyant cezası")

    # Sözler
    from cogs.muzik.sozler import anlik_indeks, baslik_temizle, canli_pencere, lrc_coz, sayfalara_bol
    lrc = lrc_coz("[00:01.00]bir\n[00:05.50]iki\n[00:09.123]üç\n[00:12.00][00:20.00]nakarat")
    kontrol([t for t, _ in lrc] == [1.0, 5.5, 9.123, 12.0, 20.0], "LRC ayrıştırma (çoklu zaman damgası)")
    kontrol(anlik_indeks(lrc, 6) == 1 and anlik_indeks(lrc, 0) == -1 and "**▶ iki**" in canli_pencere(lrc, 6), "senkron satır vurgusu")
    sayfalar = sayfalara_bol("\n".join(f"satır {i}" for i in range(500)), 300)
    kontrol(all(len(s) <= 300 for s in sayfalar) and sum(s.count("satır") for s in sayfalar) == 500, "uzun sözler sayfalanır")
    kontrol(baslik_temizle("TARKAN - Şımarık (Official Music Video)") == ("TARKAN", "Şımarık"), "başlık temizleme (Official Video)")
    kontrol(baslik_temizle("Kuzu Kuzu", "Tarkan - Topic") == ("Tarkan", "Kuzu Kuzu"), "başlık temizleme ('- Topic' kanal)")

    # Filtre durumu + FFmpeg argümanları
    import shlex
    from cogs.muzik.filtreler import FiltreDurumu, secenek_uygula
    from cogs.muzik.oynatici import ffmpeg_argumanlari
    f = FiltreDurumu()
    kontrol(not f.islem_gerekli_mi() and f.af_zinciri() == "", "filtresiz: -af yok")
    secenek_uygula(f, "nightcore")
    secenek_uygula(f, "hizlandir")
    kontrol(abs(f.hiz_carpani() - 1.5625) < 1e-9, "hız çarpanı: nightcore 1.25 × 1.25")
    secenek_uygula(f, "vaporwave")
    kontrol(f.perde == "vaporwave", "nightcore ↔ vaporwave birbirini dışlar")
    secenek_uygula(f, "bas3")
    secenek_uygula(f, "bas3")
    kontrol(f.bas == 0, "aynı bass seviyesi tekrar → kapatır")
    secenek_uygula(f, "kapat")
    kontrol(not f.aktif_mi(), "hepsini kapat")
    url = "https://rr1.googlevideo.com/videoplayback?a=1&b=2"
    once, sonra = ffmpeg_argumanlari(url, {"User-Agent": "Moz illa/5.0", "Accept": "*/*"}, 83.456, "bass=g=8,volume=0.50", kopya=False)
    parcalar = shlex.split(once)
    kontrol("-ss" in parcalar and parcalar[parcalar.index("-ss") + 1] == "83.46" and "-reconnect" in parcalar, "before_options: -ss + reconnect")
    kontrol(parcalar[parcalar.index("-headers") + 1] == "User-Agent: Moz illa/5.0\r\nAccept: */*\r\n", "HTTP başlıkları (CRLF) shlex'ten sağlam geçer")
    kontrol("-af" in shlex.split(sonra) and "-application" in sonra, "kodlama yolunda -af + libopus ayarları")
    _, sonra_k = ffmpeg_argumanlari(url, {}, 0, "bass=g=8", kopya=True)
    kontrol("-af" not in sonra_k and "-application" not in sonra_k, "doğrudan aktarımda -af / kodlayıcı ayarı yok")

    from cogs.muzik.guncelleyici import ayni_surum
    kontrol(ayni_surum("2026.08.19", "2026.8.19") and ayni_surum("2026.10.01", "2026.10.1"),
            "yt-dlp sürümü: 2026.08.19 == 2026.8.19 (boşuna yeniden başlatma yok)")
    kontrol(not ayni_surum("2026.08.19", "2026.10.1") and not ayni_surum("2026.8.19", "2026.8.19.1"),
            "yt-dlp sürümü: gerçekten yeni sürüm algılanır")


# ══════════════════════════════════════════════
#  [2] VERİTABANI
# ══════════════════════════════════════════════

def veritabani():
    print("\n[2] Müzik veritabanı (geçici DB)")
    import database as d
    d.veritabanini_kur()
    d.sunucu_ayar_guncelle(7777, oygec_aktif=1)   # eski !oygec ayarı
    import muzik_veritabani as mdb
    mdb.muzik_veritabanini_kur()
    mdb.muzik_veritabanini_kur()
    kolonlar = {r[1] for r in d.db.execute('PRAGMA table_info("muzik_ayarlar")')}
    kontrol(set(mdb.MUZIK_AYAR_KOLONLARI) <= kolonlar, "muzik_ayarlar: tüm kolonlar (migrasyon iki kez)")
    for tablo in ("muzik_calma_listeleri", "muzik_calma_listesi_parcalari", "muzik_bot_durum"):
        kontrol(d.db.execute("SELECT 1 FROM sqlite_master WHERE name = ?", (tablo,)).fetchone() is not None, f"tablo var: {tablo}")
    kontrol(mdb.muzik_ayar_al(7777)["oylama_aktif"] == 1, "eski oygec_aktif → oylama_aktif taşındı")
    mdb.muzik_ayar_guncelle(7777, oylama_aktif=0)
    mdb.muzik_veritabanini_kur()
    kontrol(mdb.muzik_ayar_al(7777)["oylama_aktif"] == 0, "yeniden kurulum yeni ayarı ezmez")

    mdb.muzik_ayar_guncelle(1, dj_rol_id=555, son_ses=80, istek_kanal_id=42)
    mdb.muzik_ayar_guncelle(2, surekli_mod=1)
    a1, a2 = mdb.muzik_ayar_al(1), mdb.muzik_ayar_al(2)
    kontrol(a1["dj_rol_id"] == 555 and a2["dj_rol_id"] is None and a2["surekli_mod"] == 1 and a1["surekli_mod"] == 0,
            "ayarlar sunucu bazlı")
    kontrol(mdb.muzik_ayar_al(3) == {**mdb.VARSAYILAN_AYARLAR, "sunucu_id": 3}, "ayarlanmamış sunucu → varsayılanlar")
    kontrol(mdb.istek_kanali_mi(1, 42) and not mdb.istek_kanali_mi(2, 42), "istek kanalı kontrolü (cache)")
    a1["dj_rol_id"] = 1
    kontrol(mdb.muzik_ayar_al(1)["dj_rol_id"] == 555, "muzik_ayar_al kopya döner (cache korunur)")
    try:
        mdb.muzik_ayar_guncelle(1, **{"dj_rol_id = 0; DROP TABLE ekonomi; --": 1})
        kontrol(False, "beyaz liste")
    except ValueError:
        kontrol(True, "beyaz liste dışı kolon reddedildi")
    once = dict(mdb._muzik_ayar_cache)
    mdb.muzik_cache_yukle()
    kontrol({k: dict(v) for k, v in once.items()} == {k: dict(v) for k, v in mdb._muzik_ayar_cache.items()},
            "cache = DB (yeniden yükleme sonrası aynı)")

    lid = mdb.liste_olustur(100, "Favoriler")
    kontrol(mdb.liste_olustur(100, "favoriler") == lid, "liste adı büyük/küçük harf duyarsız")
    n = mdb.listeye_parca_ekle(lid, [{"sorgu": f"https://youtu.be/{i:011d}", "baslik": f"P{i}", "sure": 100} for i in range(3)])
    kontrol(n == 3 and [p["baslik"] for p in mdb.liste_parcalari(lid)] == ["P0", "P1", "P2"], "listeye ekle (sıralı)")
    kontrol(mdb.listeden_parca_cikar(lid, 2) == "P1" and len(mdb.liste_parcalari(lid)) == 2, "listeden çıkar")
    mdb.listeye_parca_ekle(lid, [{"sorgu": "x", "baslik": "yeni"}], bastan_yaz=True)
    kontrol([p["baslik"] for p in mdb.liste_parcalari(lid)] == ["yeni"], "kaydet: üzerine yaz")
    kontrol(mdb.liste_bul(200, "Favoriler", genel_ara=False) is None and not mdb.liste_sil(200, lid), "başkasının listesi kendi listesi sayılmaz / silinemez")
    kontrol(mdb.listeleri_al(100)[0][1:3] == ("Favoriler", 1), "listeleri_al")
    kontrol(mdb.liste_sil(100, lid) and not mdb.listeleri_al(100), "liste sil")
    try:
        for i in range(mdb.LISTE_LIMITI + 1):
            mdb.liste_olustur(300, f"l{i}")
        kontrol(False, "liste limiti")
    except mdb.ListeHatasi:
        kontrol(True, f"kullanıcı başına {mdb.LISTE_LIMITI} liste sınırı")
    mdb.bot_durum_yaz("x", 1.5)
    mdb.bot_durum_yaz("x", 2.5)
    kontrol(mdb.bot_durum_al("x") == "2.5", "bot_durum anahtar/değer (upsert)")


# ══════════════════════════════════════════════
#  SAHTE DISCORD NESNELERİ (oynatıcı testleri için)
# ══════════════════════════════════════════════

class SahteSesIstemcisi:
    """discord.VoiceClient'ın oynatıcının kullandığı kısmı; ses thread'i discord.py'nin AudioPlayer'ı gibi davranır."""

    def __init__(self, kare_suresi=0.002):
        self.kare_suresi = kare_suresi
        self._oynatici = None
        self._dur = None
        self._duraklat = threading.Event()
        self.gonderilen = 0
        self.channel = None

    def is_connected(self):
        return True

    def is_playing(self):
        return self._oynatici is not None and self._oynatici.is_alive() and not self._duraklat.is_set()

    def is_paused(self):
        return self._oynatici is not None and self._oynatici.is_alive() and self._duraklat.is_set()

    def play(self, kaynak, after=None):
        import discord
        if self.is_playing() or self.is_paused():
            raise discord.ClientException("Already playing audio.")
        dur = threading.Event()
        self._dur = dur
        self._duraklat = threading.Event()
        duraklat = self._duraklat

        def calis():
            hata = None
            try:
                while not dur.is_set():
                    if duraklat.is_set():
                        time.sleep(0.005)
                        continue
                    veri = kaynak.read()
                    if not veri:
                        break
                    self.gonderilen += 1
                    time.sleep(self.kare_suresi)
            except Exception as e:  # AudioPlayer da hatayı after'a iletir
                hata = e
            finally:
                if after:
                    after(hata)
                kaynak.cleanup()
        self._oynatici = threading.Thread(target=calis, daemon=True)
        self._oynatici.start()

    def stop(self):
        if self._dur is not None:
            self._dur.set()
        self._oynatici = None

    def pause(self):
        self._duraklat.set()

    def resume(self):
        self._duraklat.clear()


class SahteCozucu:
    def __init__(self, radyo_dosyasi=None):
        self.radyo_dosyasi = radyo_dosyasi
        self.coz_sayisi = 0

    async def coz(self, parca, zorla=False):
        from cogs.muzik.kaynaklar import CozmeHatasi
        if not zorla and parca.akis_gecerli_mi():
            return parca
        self.coz_sayisi += 1
        if parca.sorgu.startswith("yok:"):
            raise CozmeHatasi("yaş kısıtlamalı (giriş gerekiyor)")
        parca.akis_url = parca.sorgu
        parca.akis_codec = "opus" if parca.sorgu.endswith(".webm") else "aac"
        parca.cozulme_zamani = time.time()
        return parca

    async def radyo(self, tohum, haric_idler=(), haric_basliklar=(), adet=5):
        from cogs.muzik.kuyruk import Parca
        return [Parca(sorgu=self.radyo_dosyasi, baslik="Radyo Parçası", sure=3, video_id="radyo1", otomatik=True)]


class SahteCog:
    def __init__(self, bot, cozucu):
        self.bot = bot
        self.cozucu = cozucu
        self.bildirimler = []
        self.panel = 0

    async def panel_guncelle(self, gid, hemen=False):
        self.panel += 1

    async def bildir(self, gid, metin, sure=12):
        self.bildirimler.append(metin)


def sahte_ortam(ayar=None, kare_suresi=0.002, radyo_dosyasi=None, gid=1):
    vc = SahteSesIstemcisi(kare_suresi)
    guild = types.SimpleNamespace(id=gid, voice_client=vc, me=None)
    bot = types.SimpleNamespace(loop=asyncio.get_running_loop(), get_guild=lambda _gid: guild)
    cog = SahteCog(bot, SahteCozucu(radyo_dosyasi))
    from cogs.muzik.oynatici import Oynatici
    import muzik_veritabani as mdb
    oyn = Oynatici(cog, gid, ayar or mdb.muzik_ayar_al(gid))
    return oyn, vc, cog


# ══════════════════════════════════════════════
#  [3] İZOLASYON
# ══════════════════════════════════════════════

async def sc_yedek_secimi():
    """SoundCloud yedeği (ağsız): önizleme atlanır, süresi tutmayan aday reddedilir, başlıksız YT linki oEmbed'den aranır."""
    print("\n[3b] SoundCloud yedeği seçimi")
    from cogs.muzik.kaynaklar import Cozucu, CozmeHatasi, IsciHatasi
    from cogs.muzik.kuyruk import Parca
    c = Cozucu()
    cagrilar = []

    async def ara(metin, adet=5, platform='yt'):
        cagrilar.append(("ara", platform, metin))
        if platform == 'yt':
            raise IsciHatasi("Sign in to confirm you're not a bot")
        return [{"id": "a", "title": "Sanatçı - Şarkı", "duration": 200, "url": "https://soundcloud.com/x/a", "ie_key": "Soundcloud"},
                {"id": "b", "title": "Sanatçı - Şarkı", "duration": 201, "url": "https://soundcloud.com/x/b", "ie_key": "Soundcloud"},
                {"id": "c", "title": "Sanatçı - Şarkı (1 hour)", "duration": 3600, "url": "https://soundcloud.com/x/c", "ie_key": "Soundcloud"}]

    async def ytdl(secenekler, hedef, zaman_asimi, mod="tam"):
        cagrilar.append(("ytdl", hedef))
        if "youtube" in hedef:
            raise IsciHatasi("ERROR: Sign in to confirm your age. This video may be inappropriate for some users.")
        if hedef.endswith("/a"):
            return {"url": "https://cdn/a", "format_id": "hls_mp3_preview", "extractor_key": "Soundcloud", "title": "Şarkı", "webpage_url": hedef}
        return {"url": "https://cdn/b", "format_id": "hls_opus_0_0", "extractor_key": "Soundcloud", "title": "Şarkı",
                "webpage_url": hedef, "duration": 201}

    c.ara, c._ytdl = ara, ytdl
    p = Parca(sorgu="ytsearch5:Sanatçı - Şarkı", baslik="Sanatçı - Şarkı", beklenen_sure=200, arama_metni="Sanatçı - Şarkı")
    await c.coz(p)
    kontrol(p.kaynak == "soundcloud" and p.akis_url == "https://cdn/b", "YouTube araması bot doğrulamasına takıldı → SoundCloud (önizleme atlandı)")
    kontrol(p.sorgu == "https://soundcloud.com/x/b", "yeniden çözme doğrudan SoundCloud linkinden")
    uzun = Parca(sorgu="ytsearch5:x", baslik="Sanatçı - Şarkı", beklenen_sure=30, arama_metni="Sanatçı - Şarkı")
    try:
        await c.coz(uzun)
        kontrol(False, "süresi tutmayan aday reddedilmeli")
    except CozmeHatasi:
        kontrol(True, "süresi çok farklı adaylar reddedildi (yanlış şarkı çalınmaz)")

    async def yt_baslik(parca):
        return "Sanatçı Şarkı" if "youtube.com" in parca.sorgu else ""
    c._yedek_arama_metni = yt_baslik
    yk = Parca(sorgu="https://www.youtube.com/watch?v=07FYdnEawAQ")
    await c.coz(yk)
    kontrol(yk.kaynak == "soundcloud" and ("ara", "sc", "Sanatçı Şarkı") in cagrilar, "başlıksız yaş kısıtlı YouTube linki → başlıkla SoundCloud")
    from cogs.muzik.kaynaklar import baslik_uyar_mi
    kontrol(not baslik_uyar_mi("Sezen Aksu - Firuze", "Sezen Aksu - Geri Dön"), "başka şarkı (aynı sanatçı) reddedilir")
    kontrol(baslik_uyar_mi("Sezen Aksu - Firuze", "FİRUZE", "sezenaksu"), "Türkçe harf + bitişik yükleyici adı eşleşir")
    kontrol(not baslik_uyar_mi("Tarkan - Şımarık", "Şımarık", "baska biri"), "sanatçısı tutmayan aynı adlı şarkı reddedilir")
    await c.kapat()


async def izolasyon():
    print("\n[3] Sunucu başına oynatıcı izolasyonu")
    import muzik_veritabani as mdb
    from cogs.muzik.kuyruk import DONGU_SARKI, Parca
    mdb.muzik_ayar_guncelle(11, son_ses=40, otomatik_oynatma=1, normalizasyon=1)
    mdb.muzik_ayar_guncelle(12, varsayilan_ses=120)
    o1, _, _ = sahte_ortam(mdb.muzik_ayar_al(11), gid=11)
    o2, _, _ = sahte_ortam(mdb.muzik_ayar_al(12), gid=12)
    kontrol(o1.ses == 40 and o2.ses == 120, "ses: hatırlanan son ses / varsayılan ses sunucuya özel")
    kontrol(o1.otomatik and not o2.otomatik and o1.filtre.normalizasyon and not o2.filtre.normalizasyon,
            "otomatik oynatma + normalizasyon varsayılanları sunucuya özel")
    o1.kuyruk.ekle(Parca(sorgu="a"))
    o1.dongu = DONGU_SARKI
    o2.filtre.bas = 3
    kontrol(len(o2.kuyruk) == 0 and o2.dongu != DONGU_SARKI and o1.filtre.bas == 0, "kuyruk / döngü / filtre bağımsız")
    kontrol(o1.kuyruk is not o2.kuyruk and o1.gecmis is not o2.gecmis and o1._kilit is not o2._kilit, "ayrı nesneler (kilit dahil)")


# ══════════════════════════════════════════════
#  [4] OYNATICI DURUM MAKİNESİ (yerel dosyalar)
# ══════════════════════════════════════════════

def ton_uret(yol, sure, codec_args):
    subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
                    "-i", f"sine=frequency=440:sample_rate=48000:duration={sure}", "-ac", "2", *codec_args, yol],
                   check=True, timeout=60)


async def durum_makinesi():
    print("\n[4] Oynatıcı durum makinesi (yerel ses dosyaları, sahte ses istemcisi, gerçek FFmpeg)")
    from cogs.muzik import oynatici as om
    from cogs.muzik.kuyruk import DONGU_KAPALI, DONGU_SARKI, Parca
    yakala = LogYakalayici()
    logging.getLogger("MezarBot.Muzik.Oynatici").addHandler(yakala)
    logging.getLogger("MezarBot.Muzik.Oynatici").setLevel(logging.INFO)
    ton1 = os.path.join(GECICI, "ton1.webm")
    ton2 = os.path.join(GECICI, "ton2.m4a")
    ton3 = os.path.join(GECICI, "ton3.webm")
    uzun = os.path.join(GECICI, "uzun.webm")
    ton_uret(ton1, 6, ["-c:a", "libopus", "-b:a", "96k"])
    ton_uret(ton2, 4, ["-c:a", "aac", "-b:a", "96k"])
    ton_uret(ton3, 3, ["-c:a", "libopus", "-b:a", "96k"])
    # Uzun dosya tampondan (≤10 sn + pipe) çok daha uzun olmalı; yoksa kopma testinde kalan ses
    # zaten tamponda olur ve FFmpeg'i öldürmek gerçek bir kopma yaratmaz.
    ton_uret(uzun, 120, ["-c:a", "libopus", "-b:a", "96k"])

    import muzik_veritabani as mdb
    kontrol(mdb.muzik_ayar_al(999)["varsayilan_ses"] == 60, "yeni sunucularda varsayılan ses %60")
    mdb.muzik_ayar_guncelle(50, varsayilan_ses=100)   # doğrudan aktarım (-c:a copy) testi %100 ister
    oyn, vc, cog = sahte_ortam(mdb.muzik_ayar_al(50), kare_suresi=0.002, radyo_dosyasi=ton3, gid=50)
    p1 = Parca(sorgu=ton1, baslik="Ton 1", sure=6)
    p2 = Parca(sorgu=ton2, baslik="Ton 2", sure=4)
    oyn.kuyruk.toplu_ekle([p1, p2])
    await oyn.baslat_bossa()
    kontrol(oyn.simdiki is p1 and oyn.kaynak is not None and oyn.kaynak.kopya, "Opus kaynak + ses %100 + filtre yok → doğrudan aktarım (-c:a copy)")
    kontrol(await bekle(lambda: oyn.simdiki is p2), "birinci parça bitince ikinciye geçildi")
    kontrol(not oyn.kaynak.kopya, "AAC kaynak → libopus kodlama")
    kontrol(yakala.var_mi("Sıradaki akış ısıtıldı") and yakala.var_mi("Isıtılmış akış kullanılıyor"),
            "sıradaki parçanın FFmpeg'i önceden ısıtıldı ve kullanıldı (boşluksuz geçiş)")
    kontrol(await bekle(lambda: oyn.simdiki is None), "kuyruk bitti → boşta")
    kontrol([p.baslik for p in oyn.gecmis.son(5)] == ["Ton 2", "Ton 1"], "geçmiş sırası")

    # Şarkı döngüsü + atla
    oyn.dongu = DONGU_SARKI
    p3 = Parca(sorgu=ton3, baslik="Ton 3", sure=3)
    oyn.kuyruk.ekle(p3)
    oyn.kuyruk.ekle(Parca(sorgu=ton1, baslik="Ton 1b", sure=6))
    await oyn.baslat_bossa()
    baslangic = len(oyn.gecmis)
    kontrol(await bekle(lambda: len(oyn.gecmis) >= baslangic + 2) and oyn.simdiki is p3, "şarkı döngüsü: aynı parça tekrar çalıyor")
    kontrol(await oyn.atla() == "ok", "atla")
    kontrol(await bekle(lambda: oyn.simdiki is not None and oyn.simdiki.baslik == "Ton 1b"), "döngüdeyken atla → sıradaki parça")
    oyn.dongu = DONGU_KAPALI
    oyn.durdur()
    kontrol(oyn.simdiki is None and oyn.kuyruk.bos_mu() and not vc.is_playing(), "durdur: kuyruk temiz, çalma durdu")

    # Gerçek zamanlı: sarma, filtre, ses (uzun dosya)
    vc.kare_suresi = 0.02
    pu = Parca(sorgu=uzun, baslik="Uzun", sure=120)
    oyn.kuyruk.ekle(pu)
    await oyn.baslat_bossa()
    await asyncio.sleep(1.0)
    k = oyn.konum()
    kontrol(0.6 < k < 1.6, f"konum paket sayımıyla takip ediliyor ({k:.2f} sn)")
    vc.pause()
    await asyncio.sleep(0.6)
    kontrol(abs(oyn.konum() - k) < 0.3, "duraklatılınca konum ilerlemiyor")
    vc.resume()
    kontrol(await oyn.yeniden_baslat(20.0) and oyn.kaynak.baslangic == 20.0 and oyn.simdiki is pu, "sar → 20. saniyeden yeni akış")
    await asyncio.sleep(0.5)
    kontrol(20.2 < oyn.konum() < 21.5, f"sarma sonrası konum ({oyn.konum():.2f})")
    from cogs.muzik.filtreler import secenek_uygula
    secenek_uygula(oyn.filtre, "nightcore")
    k = oyn.konum()
    kontrol(await oyn.yeniden_baslat(), "filtre değişimi → konumdan yeniden başlat")
    args = " ".join(oyn.kaynak._ic._process.args)
    kontrol(not oyn.kaynak.kopya and "asetrate=60000" in args and "libopus" in args, "filtre → -af asetrate + libopus")
    kontrol(abs(oyn.kaynak.baslangic - k) < 0.6, "filtre değişince konum korunur")
    t0 = oyn.konum()
    await asyncio.sleep(1.0)
    kontrol(1.0 < oyn.konum() - t0 < 1.6, f"nightcore: 1 sn'de ~1.25 sn ilerler ({oyn.konum() - t0:.2f})")
    secenek_uygula(oyn.filtre, "kapat")
    oyn.ses_ayarla(50)
    kontrol(await bekle(lambda: "volume=0.50" in " ".join(oyn.kaynak._ic._process.args), zaman=5), "ses değişimi → FFmpeg -af volume (Python'da ses işleme yok)")
    oyn.ses_ayarla(100)
    kontrol(await bekle(lambda: oyn.kaynak.kopya, zaman=5), "ses %100 + filtre yok → tekrar doğrudan aktarım")

    # Akış kopması → kaldığı yerden devam.
    # Not: tampon (≤10 sn) + pipe'taki veri önce çalınır; kopma ancak bunlar bitince algılanır (doğru davranış).
    await asyncio.sleep(0.5)
    eski = oyn.kaynak
    eski._ic._process.kill()
    kontrol(await bekle(lambda: eski._bitti.is_set(), zaman=10), "FFmpeg öldü → okuyucu akış sonunu gördü")
    kontrol(await bekle(lambda: yakala.var_mi("Akış kesildi"), zaman=25), "tampon boşalınca kopma algılandı")
    kontrol(await bekle(lambda: oyn.kaynak is not eski and oyn.kaynak is not None and oyn.kaynak.kareler > 5, zaman=15)
            and oyn.simdiki is pu and abs(oyn.kaynak.baslangic - eski.konum) < 0.5,
            f"akış yenilendi, tam kaldığı yerden devam ({eski.konum:.2f} → "
            f"{getattr(oyn.kaynak, 'baslangic', float('nan')):.2f} sn)")
    oyn.durdur()

    # Kısıtlı parça atlanır + otomatik oynatma
    vc.kare_suresi = 0.002
    oyn.otomatik = True
    oyn.kuyruk.toplu_ekle([Parca(sorgu="yok:1", baslik="Yaş Kısıtlı"), Parca(sorgu=ton3, baslik="Ton 3c", sure=3, video_id="t3")])
    await oyn.baslat_bossa()
    kontrol(any("Yaş Kısıtlı" in b and "yaş kısıtlamalı" in b for b in cog.bildirimler), "kısıtlı parça mesajla atlandı")
    kontrol(await bekle(lambda: oyn.simdiki is not None and oyn.simdiki.baslik == "Radyo Parçası", zaman=10),
            "kuyruk bitince otomatik oynatma benzer parça ekledi ve çaldı")
    oyn.kapat()
    kontrol(await bekle(lambda: not ffmpeg_cocuklari(), zaman=5), "kapat(): tüm FFmpeg süreçleri sonlandı ve toplandı (zombi yok)")
    logging.getLogger("MezarBot.Muzik.Oynatici").removeHandler(yakala)


# ══════════════════════════════════════════════
#  [5] GERÇEK AKIŞ: FİLTRELER + RTF
# ══════════════════════════════════════════════

async def gercek_akis(cozucu):
    print("\n[5] Gerçek akış — birebir discord.FFmpegOpusAudio argümanlarıyla")
    from cogs.muzik.filtreler import FiltreDurumu, tum_test_zincirleri
    from cogs.muzik.kuyruk import Parca
    from cogs.muzik.oynatici import HataTamponu, OnbellekliKaynak, opus_kaynagi_olustur
    p = Parca(sorgu="https://www.youtube.com/watch?v=cpp69ghR1IM")
    await cozucu.coz(p)
    kontrol(p.akis_codec == "opus", f"YouTube akışı Opus (format 251) — {p.akis_protokol}")

    def birebir_argumanlar(parca, af, kopya, konum=0):
        src = opus_kaynagi_olustur(parca.akis_url, parca.akis_basliklari, konum, af, kopya, False, HataTamponu())
        args = list(src._process.args)
        src.cleanup()
        kontrol_edilen = args[-1] == "pipe:1"
        return args[:-1], kontrol_edilen

    def calistir(args, saniye):
        t = time.monotonic()
        r = subprocess.run(args + ["-t", str(saniye), "-y", "/dev/null"], capture_output=True, timeout=120)
        return r.returncode, time.monotonic() - t, r.stderr.decode(errors="ignore")[-300:]

    zincirler = [("dogrudan-aktarim(copy)", "", True)] + [(ad, z, False) for ad, z in tum_test_zincirleri()]
    zincirler.append(("ses%50", "volume=0.50", False))
    hatalar = []
    for ad, af, kopya in zincirler:
        args, pipe = birebir_argumanlar(p, af, kopya)
        rc, sure, err = calistir(args, 5)
        if rc != 0 or not pipe:
            hatalar.append(f"{ad}: rc={rc} {err}")
    kontrol(not hatalar, f"{len(zincirler)} zincir (tüm filtreler + kombinasyonlar + copy) 5 sn → çıkış kodu 0 {hatalar or ''}")

    for ad, af, kopya in (("copy", "", True), ("libopus", "", False),
                          ("libopus+bas3+nightcore+8d+norm", FiltreDurumu(bas=3, perde="nightcore", sekiz_d=True, normalizasyon=True).af_zinciri(), False)):
        args, _ = birebir_argumanlar(p, af, kopya)
        rc, sure, err = calistir(args, 10)
        rtf = sure / 10
        kontrol(rc == 0 and rtf < 0.5, f"RTF {ad}: 10 sn ses {sure:.2f} sn'de → {rtf:.3f}x gerçek zaman ({1 / max(rtf, 1e-6):.0f}× hızlı)")

    args, _ = birebir_argumanlar(p, "", True, konum=95)
    rc, _, err = calistir(args, 5)
    kontrol(rc == 0, "sarma (-ss 95) + copy → çıkış kodu 0")

    # Tampon üzerinden gerçek okuma
    ic = opus_kaynagi_olustur(p.akis_url, p.akis_basliklari, 30, "", True, False, HataTamponu())
    kaynak = OnbellekliKaynak(ic, True, 30, 1.0, HataTamponu())
    t = time.monotonic()
    hazir = await kaynak.hazir_bekle()
    ilk_paket = time.monotonic() - t
    paketler = []
    while len(paketler) < 250:
        veri = await asyncio.to_thread(kaynak.read)
        if not veri:
            break
        if veri != b'\xf8\xff\xfe':
            paketler.append(veri)
    surec = ic._process
    kontrol(hazir and len(paketler) == 250 and abs(kaynak.konum - 35.0) < 0.05,
            f"tampon: ilk 15 paket {ilk_paket * 1000:.0f} ms'de hazır; 250 paket = 5 sn, konum {kaynak.konum:.2f}")
    kaynak.cleanup()
    kontrol(surec.poll() is not None, "cleanup: FFmpeg sonlandırıldı ve toplandı")

    # SoundCloud (HLS AAC) → libopus
    try:
        sc = await cozucu.ara("tarkan simarik", adet=1, platform="sc")
        from cogs.muzik.kaynaklar import flat_entry_parca
        scp = flat_entry_parca(sc[0])
        await cozucu.coz(scp)
        args, _ = birebir_argumanlar(scp, "bass=g=8:f=110:w=0.6", False)
        rc, sure, err = calistir(args, 5)
        kontrol(rc == 0, f"SoundCloud ({scp.akis_protokol}, {scp.akis_codec}) + filtre → çıkış kodu 0")
    except Exception as e:  # SoundCloud erişimi olmayabilir (bölge/ağ)
        atla(f"SoundCloud akış testi: {e}")


# ══════════════════════════════════════════════
#  [6] KAYNAKLAR
# ══════════════════════════════════════════════

async def kaynaklar(cozucu):
    print("\n[6] Kaynaklar (işçi süreçte yt-dlp + Deno)")
    from cogs.muzik.kaynaklar import CozmeHatasi
    from cogs.muzik.kuyruk import Parca
    t = time.monotonic()
    p = await cozucu.arama_parcasi("tarkan şımarık")
    kontrol(p is not None and p.video_id and p.sure > 0, f"YouTube arama: {p.baslik} ({time.monotonic() - t:.1f} sn)")
    await cozucu.coz(p)
    kontrol(p.akis_url.startswith("https://") and p.akis_codec == "opus", "tam çıkarma: Opus akış URL'si")
    ytm = Parca(sorgu="https://music.youtube.com/watch?v=cpp69ghR1IM")
    await cozucu.coz(ytm)
    kontrol(ytm.kaynak == "youtube" and ytm.akis_url, f"YouTube Music linki: {ytm.baslik}")
    baslik, parcalar, toplam = await cozucu.playlist("https://www.youtube.com/playlist?list=PLFgquLnL59alCl_2TQvOiD5Vgm1hCaGSI", 1, 25)
    kontrol(len(parcalar) == 25 and toplam > 25 and all(x.video_id for x in parcalar), f"YouTube playlist ilk parti: 25/{toplam} ({baslik})")
    _, kalan, _ = await cozucu.playlist("https://www.youtube.com/playlist?list=PLFgquLnL59alCl_2TQvOiD5Vgm1hCaGSI", 26, 60)
    kontrol(len(kalan) > 0 and kalan[0].video_id not in {x.video_id for x in parcalar}, f"playlist devamı (26-60): {len(kalan)} parça")
    try:
        yk = Parca(sorgu="https://www.youtube.com/watch?v=07FYdnEawAQ")
        await cozucu.coz(yk)
        kontrol(yk.kaynak == "soundcloud" and yk.akis_url, f"yaş kısıtlı video → SoundCloud yedeği: {yk.baslik}")
    except CozmeHatasi as h:
        kontrol(h.kalici and "yaş" in h.sebep, f"yaş kısıtlı video → '{h.sebep}' (SoundCloud'da da yok, atlanır)")
    try:
        await cozucu.coz(Parca(sorgu="https://www.youtube.com/watch?v=aaaaaaaaaaa"))
        kontrol(False, "olmayan video")
    except CozmeHatasi as h:
        kontrol("kullanılamıyor" in h.sebep, f"olmayan video → '{h.sebep}'")
    kisitli_arama = Parca(sorgu="https://www.youtube.com/watch?v=07FYdnEawAQ", arama_metni="tarkan kuzu kuzu")
    await cozucu.coz(kisitli_arama)
    kontrol(kisitli_arama.akis_url and kisitli_arama.video_id != "07FYdnEawAQ", "aramadan gelen kısıtlı video → sıradaki aday seçildi")
    try:
        sc = await cozucu.ara("tarkan simarik", adet=1, platform="sc")
        kontrol(bool(sc), f"SoundCloud arama: {sc[0].get('title')}")
    except Exception as e:  # ağ/bölge
        atla(f"SoundCloud: {e}")
    try:
        d = Parca(sorgu="https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3")
        await cozucu.coz(d)
        kontrol(d.akis_url and d.kaynak == "http", f"doğrudan ses linki (generic): codec={d.akis_codec or '?'}")
    except CozmeHatasi as e:
        atla(f"doğrudan link sunucusu erişilemedi: {e}")

    t = time.monotonic()
    baslik, sp = await cozucu.spotify("track", "4cOdK2wGLETKBW3PvgPWqT")
    kontrol(sp and sp[0].sorgu.startswith("ytsearch5:") and "Never Gonna Give You Up" in sp[0].baslik,
            f"Spotify parça → '{sp[0].sorgu}' ({time.monotonic() - t:.1f} sn, API {'açık' if cozucu.spotify_aktif else 'yok'})")
    await cozucu.coz(sp[0])
    kontrol(sp[0].video_id and abs(sp[0].sure - 213) <= 10, f"Spotify → YouTube eşleşmesi süreye göre: {sp[0].video_id} ({sp[0].sure} sn)")
    baslik, sp = await cozucu.spotify("playlist", "37i9dQZF1DXcBWIGoYBM5M")
    kontrol(len(sp) >= 20 and all(x.beklenen_sure for x in sp), f"Spotify playlist: {baslik} — {len(sp)} parça")
    baslik, sp = await cozucu.spotify("album", "4aawyAB9vmqN3uQ7FjRGTy")
    kontrol(len(sp) >= 10, f"Spotify albüm: {baslik} — {len(sp)} parça")
    try:
        await cozucu.spotify("artist", "1Q4Hj2rq6eTzzNJF3MA7Hn")
        kontrol(False, "sanatçı linki")
    except CozmeHatasi:
        kontrol(True, "Spotify sanatçı linki → açıklayıcı hata")

    radyo = await cozucu.radyo(p, haric_idler={p.video_id}, adet=3)
    kontrol(len(radyo) == 3 and all(r.otomatik and r.video_id != p.video_id for r in radyo),
            f"otomatik oynatma (Mix): {', '.join(r.baslik[:25] for r in radyo)}")


# ══════════════════════════════════════════════
#  [7] SÖZLER
# ══════════════════════════════════════════════

async def sozler():
    print("\n[7] LRCLIB sözler")
    from cogs.muzik.sozler import SozIstemcisi
    s = SozIstemcisi()
    try:
        t = time.monotonic()
        r = await s.bul("TARKAN - Şımarık (Official Music Video)", "Tarkan", 192)
        kontrol(r is not None and r["senkron"] and "Takmış koluna" in (r["duz"] or " ".join(x for _, x in r["senkron"])),
                f"Tarkan - Şımarık: {len(r['senkron'])} senkron satır ({time.monotonic() - t:.1f} sn)")
        t = time.monotonic()
        r2 = await s.bul("TARKAN - Şımarık (Official Music Video)", "Tarkan", 192)
        kontrol(r2 is r and time.monotonic() - t < 0.05, "önbellek: ikinci istek ağa gitmez")
        r3 = await s.bul("", serbest_sorgu="sezen aksu gülümse")
        kontrol(r3 is not None and (r3["duz"] or r3["senkron"]), f"serbest arama: {r3['sanatci']} - {r3['baslik']}")
        kontrol(await s.bul("zzqxw asdkjh qwpoeiru", "") is None, "bulunamayan şarkı → None")
    finally:
        await s.kapat()


# ══════════════════════════════════════════════

async def ag_testleri():
    from cogs.muzik.kaynaklar import Cozucu
    cozucu = Cozucu(spotify_aktif=bool((os.getenv("SPOTIFY_CLIENT_ID") or "").strip()))
    try:
        await kaynaklar(cozucu)
        await gercek_akis(cozucu)
        await sozler()
    finally:
        pidler = cozucu.havuz.pidler()
        await cozucu.kapat()
    print("\n[8] Kaynak temizliği")
    kontrol(pidler and not any(os.path.exists(f"/proc/{p}") and open(f"/proc/{p}/stat").read().split()[2] != "Z" for p in pidler)
            and cozucu.havuz.pidler() == [], f"işçi süreçler ({pidler}) kapandı")


def main():
    gercek_iz = dosya_izi(GERCEK_DB)
    try:
        saf_mantik()
        veritabani()
        asyncio.run(sc_yedek_secimi())
        asyncio.run(izolasyon())
        asyncio.run(durum_makinesi())
        if AGSIZ:
            atla("ağ testleri (--agsiz)")
        else:
            asyncio.run(ag_testleri())
        kontrol(not ffmpeg_cocuklari(), "artık/zombi ffmpeg süreci yok")
        kontrol(dosya_izi(GERCEK_DB) == gercek_iz, "gerçek mezarbot.db değişmedi")
        print(f"\nTÜM MÜZİK TESTLERİ GEÇTİ ✅  ({_sayac['gecti']} kontrol, {_sayac['atlandi']} atlandı)")
        return 0
    except AssertionError as e:
        print(f"\n❌ BAŞARISIZ: {e}\n   (geçici dosyalar: {GECICI})")
        return 1


if __name__ == "__main__":
    kod = main()
    try:
        import database
        database.db.close()
    except Exception:  # test sonu temizliği
        pass
    if kod == 0:
        shutil.rmtree(GECICI, ignore_errors=True)
    sys.exit(kod)
