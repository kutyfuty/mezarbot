"""
MezarBot çevrimdışı duman testi — Discord'a BAĞLANMAZ, gerçek veritabanına DOKUNMAZ.

Çalıştırma (bot dizininden veya herhangi bir yerden):
    venv/bin/python tests/smoke_test.py
    venv/bin/python tests/smoke_test.py --gercek-db-kopyasi   # mezarbot.db'nin GEÇİCİ KOPYASINDA migrasyon denemesi

Yaptıkları:
 1. MEZARBOT_DB'yi geçici bir dosyaya yönlendirir (bot modüllerini import etmeden ÖNCE).
 2. Varsayılan: eski (global ekonomili) şemalı küçük bir DB oluşturur; --gercek-db-kopyasi: mezarbot.db'yi
    geçici dizine kopyalar. Sonra veritabanini_kur()'u iki kez çalıştırır (migrasyonlar idempotent olmalı).
 3. Ekonomi migrasyonu: tüm eski satırlar config.json → eski_ekonomi_sunucu_id sunucusuna birebir taşındı mı,
    toplamlar aynı mı, yedek alındı mı, hata durumunda geri alınıyor mu.
 4. main + database + her cog modülünü import eder, tüm extension'ları çevrimdışı Bot'a yükleyip kaldırır.
 5. Güvenlik düzeltmelerini ve sunucu bazlı ekonomiyi (iki sunucuda ayrı bakiye/XP/günlük/sıralama,
    transfer/düello/yazı-tura/blackjack emaneti tek sunucuda, DM reddi) sahte ctx ile komut kodu üzerinden doğrular.
 6. Gerçek mezarbot.db'nin boyut/mtime'ının değişmediğini doğrular.
"""
import asyncio
import glob
import importlib
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import threading
import types

BOT_DIZINI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GERCEK_DB = os.path.join(BOT_DIZINI, "mezarbot.db")
GERCEK_DB_KOPYASI = "--gercek-db-kopyasi" in sys.argv

def _config_eski_sunucu():
    try:
        with open(os.path.join(BOT_DIZINI, "config.json"), encoding="utf-8") as f:
            return int(str(json.load(f).get("eski_ekonomi_sunucu_id") or "0")) or None
    except (OSError, ValueError):
        return None


# config.json → eski_ekonomi_sunucu_id; boşsa (yeni kurulum) migrasyon testi bu sahte sunucuyla çalışır
CONFIG_ESKI_SUNUCU = _config_eski_sunucu()
BEKLENEN_ESKI_SUNUCU = CONFIG_ESKI_SUNUCU or 700000000000000009
EKONOMI_TABLOLARI = ("ekonomi", "islem_gecmisi", "basarimlar", "envanter")

# İki ayrı test sunucusu (eski veriyle karışmasın diye farklı ID'ler)
SUNUCU_A, SUNUCU_B = 700000000000000001, 700000000000000002


def kontrol(kosul, mesaj):
    if not kosul:
        raise AssertionError(mesaj)
    print(f"  ✓ {mesaj}")


def dosya_izi(yol):
    """Dosyanın (boyut, mtime) izi; yoksa None."""
    return (os.path.getsize(yol), os.path.getmtime(yol)) if os.path.exists(yol) else None


def eski_sema_olustur(yol):
    """Migrasyon öncesi (eski sürüm) şema: yeni kolonlar yok, eski 'ayarlar' tablosu var,
    ekonomi tabloları GLOBAL (kullanici_id anahtarlı) ve içlerinde veri var."""
    c = sqlite3.connect(yol)
    c.executescript("""
        CREATE TABLE sunucu_ayarlar (sunucu_id INTEGER PRIMARY KEY, hosgeldin_kanal_id INTEGER,
            hosgeldin_mesaj TEXT, otorol_id INTEGER, otomod_aktif INTEGER DEFAULT 0);
        CREATE TABLE kelime_oyunu (sunucu_id INTEGER PRIMARY KEY, kanal_id INTEGER, son_kelime TEXT, son_kullanici_id INTEGER);
        CREATE TABLE ekonomi (kullanici_id INTEGER PRIMARY KEY, xp INTEGER, seviye INTEGER, bakiye INTEGER, son_gunluk TEXT);
        CREATE TABLE moderasyon_log (id INTEGER PRIMARY KEY AUTOINCREMENT, islem TEXT, hedef_id INTEGER,
            moderator_id INTEGER, sebep TEXT, tarih TEXT);
        CREATE TABLE starboard (message_id INTEGER PRIMARY KEY, channel_id INTEGER NOT NULL, author_id INTEGER NOT NULL,
            stars INTEGER DEFAULT 0, starboard_msg_id INTEGER, created_at REAL);
        CREATE TABLE ayarlar (sunucu_id INTEGER, log_kanal_id INTEGER);
        CREATE TABLE islem_gecmisi (id INTEGER PRIMARY KEY AUTOINCREMENT, kullanici_id INTEGER NOT NULL,
            tip TEXT NOT NULL, miktar INTEGER NOT NULL, aciklama TEXT, tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE basarimlar (kullanici_id INTEGER NOT NULL, basarim_id TEXT NOT NULL,
            kazanilma_tarihi TIMESTAMP DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY (kullanici_id, basarim_id));
        CREATE TABLE envanter (id INTEGER PRIMARY KEY AUTOINCREMENT, kullanici_id INTEGER NOT NULL,
            urun_id INTEGER NOT NULL, satin_alma_tarihi TEXT, UNIQUE(kullanici_id, urun_id));
        CREATE INDEX idx_ekonomi_bakiye ON ekonomi(bakiye DESC);
        CREATE INDEX idx_islem_gecmisi_kullanici ON islem_gecmisi(kullanici_id, tarih DESC);
        INSERT INTO sunucu_ayarlar (sunucu_id, hosgeldin_mesaj) VALUES (111, 'selam {uye}');
        INSERT INTO ayarlar VALUES (111, 555), (222, 666);
        INSERT INTO ekonomi VALUES (10, 5, 1, 100, ''), (20, 0, 1, 100, ''), (30, 250, 3, 7, '2026-01-01');
        INSERT INTO kelime_oyunu VALUES (111, 1, 'elma', 3);
        INSERT INTO islem_gecmisi (kullanici_id, tip, miktar, aciklama, tarih) VALUES
            (10, 'gunluk', 100, 'İlk günlük maaş', '2026-01-01 10:00:00'),
            (20, 'transfer', -5, NULL, '2026-01-02 11:00:00'),
            (10, 'yazitura', 30, 'Yazı tura kazancı', '2026-01-03 12:00:00');
        DELETE FROM islem_gecmisi WHERE id = 3;
        INSERT INTO islem_gecmisi (kullanici_id, tip, miktar, aciklama, tarih) VALUES
            (30, 'blackjack', -20, 'Blackjack kaybı', '2026-01-04 13:00:00');
        INSERT INTO basarimlar VALUES (10, 'ilk_kumar', '2026-01-03 12:00:00'), (20, 'streak_5', '2026-01-05 09:00:00');
        INSERT INTO envanter (kullanici_id, urun_id, satin_alma_tarihi) VALUES (10, 1, '2026-01-06'), (30, 2, '2026-01-07');
    """)
    c.commit()
    c.close()


def tablo_sayimlari(yol):
    c = sqlite3.connect(yol)
    try:
        tablolar = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        return {t: c.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in tablolar}
    finally:
        c.close()


def _kolonlar(conn, tablo):
    return [r[1] for r in conn.execute(f'PRAGMA table_info("{tablo}")')]


def _satirlar(conn, tablo, kolonlar, kosul="", parametreler=()):
    sql = f'SELECT {", ".join(kolonlar)} FROM "{tablo}" {kosul}'
    return sorted((tuple(r) for r in conn.execute(sql, parametreler)), key=repr)


def eski_ekonomi_goruntusu(yol):
    """Migrasyon ÖNCESİ ekonomi tablolarının tam görüntüsü: {tablo: (kolonlar, sıralı satırlar)} + toplamlar."""
    c = sqlite3.connect(yol)
    try:
        goruntu = {}
        for t in EKONOMI_TABLOLARI:
            kolonlar = _kolonlar(c, t)
            if not kolonlar:
                continue
            assert "sunucu_id" not in kolonlar, f"{t} zaten sunucu bazlı — eski şema bekleniyordu"
            goruntu[t] = (kolonlar, _satirlar(c, t, kolonlar))
        toplam = tuple(c.execute("SELECT COUNT(*), COALESCE(SUM(bakiye), 0), COALESCE(SUM(xp), 0) FROM ekonomi").fetchone())
        return goruntu, toplam
    finally:
        c.close()


def ekonomi_sunucu_bazli_mi(yol):
    """Gerçek DB ilk açılışta zaten sunucu bazlıya taşınmış olabilir (--gercek-db-kopyasi)."""
    c = sqlite3.connect(yol)
    try:
        return "sunucu_id" in _kolonlar(c, "ekonomi")
    finally:
        c.close()


def sunucu_toplamlari(conn):
    """Sunucu başına (kullanıcı sayısı, bakiye, XP) — migrasyonun veriyi değiştirmediğini doğrulamak için."""
    return sorted(tuple(r) for r in conn.execute(
        "SELECT sunucu_id, COUNT(*), COALESCE(SUM(bakiye), 0), COALESCE(SUM(xp), 0) FROM ekonomi GROUP BY sunucu_id"))


# ── Sahte Discord nesneleri (komut kodunu çevrimdışı çalıştırmak için) ──

class SahteMesaj:
    def __init__(self, content=None, embed=None):
        self.content, self.embed = content, embed
        self.embeds = [embed] if embed else []

    async def edit(self, content=None, embed=None, view=None, **_):
        self.content, self.embed = content, embed

    async def delete(self):
        pass


class SahteKanal:
    def __init__(self):
        self.mesajlar = []

    async def send(self, content=None, embed=None, view=None, **_):
        mesaj = SahteMesaj(content, embed)
        self.mesajlar.append(mesaj)
        return mesaj

    def son_metin(self):
        m = self.mesajlar[-1]
        parcalar = [m.content or ""]
        if m.embed is not None:
            parcalar += [m.embed.description or "", m.embed.author.name or "", m.embed.footer.text or ""]
        return "\n".join(parcalar)


def sahte_uye(uid, ad):
    return types.SimpleNamespace(
        id=uid, bot=False, name=ad, display_name=ad, mention=f"<@{uid}>",
        display_avatar=types.SimpleNamespace(url="https://example.invalid/a.png"),
        guild_permissions=types.SimpleNamespace(administrator=False, manage_guild=False), roles=())


def sahte_ctx(sunucu_id, uye):
    kanal = SahteKanal()
    guild = types.SimpleNamespace(id=sunucu_id, name=f"Sunucu-{sunucu_id % 1000}", get_member=lambda _uid: None)
    return types.SimpleNamespace(guild=guild, author=uye, channel=kanal, send=kanal.send, kanal=kanal)


def sahte_etkilesim():
    kayit = []

    async def edit_message(**kw):
        kayit.append(kw)
    return types.SimpleNamespace(response=types.SimpleNamespace(edit_message=edit_message), kayit=kayit)


def migrasyon_hata_senaryolari(d, gecici):
    """Hata yollarını AYRI geçici DB'lerde dener (database modülünün bağlantısı geçici olarak değiştirilir)."""
    orijinal = (d.db, d.DB_DOSYA, d.ESKI_EKONOMI_SUNUCU_ID)
    try:
        # (i) eski veri var ama config'te hedef sunucu yok → hata, DB'ye ve diske hiçbir şey yazılmaz
        yol = os.path.join(gecici, "hata_config.db")
        eski_sema_olustur(yol)
        once = eski_ekonomi_goruntusu(yol)
        conn = sqlite3.connect(yol)
        d.db, d.DB_DOSYA, d.ESKI_EKONOMI_SUNUCU_ID = conn, yol, None
        try:
            d._ekonomi_sunucu_bazli_migrasyon()
            kontrol(False, "config boşken migrasyon reddedilmeliydi")
        except d.EkonomiMigrasyonHatasi:
            pass
        conn.close()
        kontrol(eski_ekonomi_goruntusu(yol) == once and not glob.glob(yol + ".bak-ekonomi-*"),
                "eski_ekonomi_sunucu_id boş + eski veri → migrasyon reddedildi, DB ve yedek dosyası yok")

        # (ii) transaction ortasında hata (islem_gecmisi'nde NOT NULL'a uymayan eski satır) → tam geri alma
        yol = os.path.join(gecici, "hata_rollback.db")
        c = sqlite3.connect(yol)
        c.executescript("""
            CREATE TABLE ekonomi (kullanici_id INTEGER PRIMARY KEY, xp INTEGER, seviye INTEGER, bakiye INTEGER, son_gunluk TEXT);
            CREATE TABLE islem_gecmisi (id INTEGER PRIMARY KEY AUTOINCREMENT, kullanici_id INTEGER, tip TEXT,
                miktar INTEGER, aciklama TEXT, tarih TIMESTAMP);
            INSERT INTO ekonomi VALUES (1, 0, 1, 50, ''), (2, 0, 1, 60, '');
            INSERT INTO islem_gecmisi (kullanici_id, tip, miktar) VALUES (1, NULL, 5);
        """)
        c.commit()
        c.close()
        once = eski_ekonomi_goruntusu(yol)
        conn = sqlite3.connect(yol)
        d.db, d.DB_DOSYA, d.ESKI_EKONOMI_SUNUCU_ID = conn, yol, 123
        try:
            d._ekonomi_sunucu_bazli_migrasyon()
            kontrol(False, "bozuk eski satırda migrasyon başarısız olmalıydı")
        except d.EkonomiMigrasyonHatasi:
            pass
        tablolar = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        conn.close()
        kontrol(eski_ekonomi_goruntusu(yol) == once and not any(t.startswith("eski_global_") for t in tablolar),
                "transaction ortasında hata → ROLLBACK: ekonomi eski şemada ve birebir aynı (yarım migrasyon yok)")
        kontrol(len(glob.glob(yol + ".bak-ekonomi-*")) == 1, "hata durumunda da önceden alınmış yedek duruyor")
    finally:
        d.db, d.DB_DOSYA, d.ESKI_EKONOMI_SUNUCU_ID = orijinal


async def ekonomi_sunucu_bazli_testleri(d, e):
    """Komut kodunu sahte ctx ile çalıştırır: iki sunucu, aynı kullanıcılar."""
    import main
    from discord.ext import commands

    cog = e.Ekonomi.__new__(e.Ekonomi)   # __init__ yok → arka plan task'ları başlamaz
    cog.bot = types.SimpleNamespace(get_user=lambda uid: types.SimpleNamespace(display_name=f"K{uid}"))
    cog._xp_buffer = {}
    cog._xp_lock = threading.Lock()

    ali, veli, ayse = sahte_uye(910001, "Ali"), sahte_uye(910002, "Veli"), sahte_uye(910003, "Ayse")

    def bakiye(sunucu, uye):
        return d.bakiye_al(sunucu, uye.id)

    def islem_sayisi(sunucu, uye):
        return d.db.execute("SELECT COUNT(*) FROM islem_gecmisi WHERE sunucu_id = ? AND kullanici_id = ?",
                            (sunucu, uye.id)).fetchone()[0]

    # ── DM reddi ──
    try:
        await cog.cog_check(types.SimpleNamespace(guild=None, author=ali))
        kontrol(False, "DM'de ekonomi komutu reddedilmeli")
    except commands.NoPrivateMessage as hata:
        dm = SahteKanal()
        await main.on_command_error(types.SimpleNamespace(send=dm.send, invoked_with="bakiye"), hata)
        kontrol("sadece sunucularda" in dm.son_metin(), "DM: ekonomi komutu 'sadece sunucularda çalışır' yanıtı verir")
    kontrol(await cog.cog_check(sahte_ctx(SUNUCU_A, ali)), "sunucuda ekonomi komutu geçer (cog_check)")

    # ── Günlük: her sunucuda ayrı ──
    for uye in (ali, veli):
        await cog.gunluk.callback(cog, sahte_ctx(SUNUCU_A, uye))
    await cog.gunluk.callback(cog, sahte_ctx(SUNUCU_B, ali))
    kontrol((bakiye(SUNUCU_A, ali), bakiye(SUNUCU_B, ali), bakiye(SUNUCU_A, veli), bakiye(SUNUCU_B, veli)) == (100, 100, 100, None),
            "!gunluk: aynı kullanıcı iki sunucuda ayrı maaş alır, profili olmayan sunucuda bakiye yok")
    ctx = sahte_ctx(SUNUCU_A, ali)
    await cog.gunluk.callback(cog, ctx)
    kontrol("zaten" in ctx.kanal.son_metin() and bakiye(SUNUCU_A, ali) == 100, "!gunluk: aynı sunucuda ikinci kez alınamaz")
    kontrol(bakiye(BEKLENEN_ESKI_SUNUCU, ali) is None, "yeni sunucudaki profil eski (Mezar) sunucusuna sızmadı")

    # ── paraekle (sahip aracı): sadece komutun kullanıldığı sunucu ──
    await cog.paraekle.callback(cog, sahte_ctx(SUNUCU_B, ali), 400)
    kontrol((bakiye(SUNUCU_A, ali), bakiye(SUNUCU_B, ali)) == (100, 500), "!paraekle: sadece bu sunucunun bakiyesi")

    # ── Transfer: tek sunucu içinde ──
    ctx = sahte_ctx(SUNUCU_B, ali)
    await cog.transfer.callback(cog, ctx, veli, 50)
    kontrol("bu sunucuda profili yok" in ctx.kanal.son_metin() and bakiye(SUNUCU_B, ali) == 500,
            "!transfer: alıcının bu sunucuda profili yoksa para çıkmaz (başka sunucudaki profil sayılmaz)")
    await cog.transfer.callback(cog, sahte_ctx(SUNUCU_A, ali), veli, 30)
    kontrol((bakiye(SUNUCU_A, ali), bakiye(SUNUCU_A, veli), bakiye(SUNUCU_B, ali)) == (70, 130, 500),
            "!transfer: para aynı sunucuda taşındı, diğer sunucu etkilenmedi")
    ctx = sahte_ctx(SUNUCU_A, ali)
    await cog.transfer.callback(cog, ctx, veli, 400)
    kontrol(bakiye(SUNUCU_A, ali) == 70, "!transfer: başka sunucudaki bakiye (500) bu sunucuda harcanamaz")

    # ── Yazı tura: bahis tek sunucuda ──
    once_a, once_b = bakiye(SUNUCU_A, ali), bakiye(SUNUCU_B, ali)
    await cog.yazitura.callback(cog, sahte_ctx(SUNUCU_A, ali), "yazı", 40)
    kontrol(bakiye(SUNUCU_A, ali) in (once_a - 40, once_a + 40) and bakiye(SUNUCU_B, ali) == once_b,
            f"!yazitura: sonuç ±40 sadece bu sunucuda (A: {once_a}→{bakiye(SUNUCU_A, ali)}, B sabit {once_b})")
    kayip_b = d.db.execute("SELECT COALESCE(gunluk_kayip, 0) FROM ekonomi WHERE sunucu_id = ? AND kullanici_id = ?",
                           (SUNUCU_B, ali.id)).fetchone()[0]
    kontrol(kayip_b == 0, "günlük kumar kayıp sayacı sunucu bazlı")

    # ── Blackjack: emanet sunucu bazlı ──
    d.db.execute("UPDATE ekonomi SET bakiye = 200 WHERE sunucu_id = ? AND kullanici_id = ?", (SUNUCU_A, ali.id))
    d.db.commit()
    ctx_a = sahte_ctx(SUNUCU_A, ali)
    await cog.blackjack.callback(cog, ctx_a, 50)
    kontrol((bakiye(SUNUCU_A, ali), bakiye(SUNUCU_B, ali)) == (150, 500) and (SUNUCU_A, ali.id) in e.aktif_oyuncular,
            "!blackjack: bahis sadece bu sunucudan emanete alındı")
    ctx_a2 = sahte_ctx(SUNUCU_A, ali)
    await cog.blackjack.callback(cog, ctx_a2, 50)
    kontrol("aktif bir oyunun" in ctx_a2.kanal.son_metin() and bakiye(SUNUCU_A, ali) == 150,
            "!blackjack: aynı sunucuda ikinci oyun açılamaz")
    ctx_b = sahte_ctx(SUNUCU_B, ali)
    await cog.blackjack.callback(cog, ctx_b, 100)
    kontrol(bakiye(SUNUCU_B, ali) == 400, "!blackjack: başka sunucuda ayrı oyun/emanet açılabilir")
    # Sahte kanal gönderilen view'ı saklamaz: oyunun sonucunu aynı ctx ile kurulan view üzerinden çalıştır
    # (bahis yukarıda komut tarafından zaten emanete alındı; final() sadece ödeme/iade yapar)
    view_a = e.BlackjackView(ctx_a, 50)
    kontrol(view_a.sunucu_id == SUNUCU_A, "BlackjackView sunucu_id'yi ctx.guild'den taşır")
    await view_a.final(sahte_etkilesim(), "Kazandın! (test)")
    kontrol((bakiye(SUNUCU_A, ali), bakiye(SUNUCU_B, ali)) == (250, 400) and (SUNUCU_A, ali.id) not in e.aktif_oyuncular,
            "blackjack kazancı (2x) sadece oyunun sunucusuna ödendi, A'daki aktif oyun kapandı")
    view_b = e.BlackjackView(ctx_b, 100)
    await view_b.final(sahte_etkilesim(), "Berabere! (test)")
    kontrol(bakiye(SUNUCU_B, ali) == 500 and bakiye(SUNUCU_A, ali) == 250, "blackjack beraberlik iadesi sadece B'de")
    e.aktif_oyuncular.clear()

    # ── Düello emaneti: tek sunucuda ──
    d.ekonomi_kaydi_olustur(SUNUCU_A, ayse.id, bakiye=100)
    d.ekonomi_kaydi_olustur(SUNUCU_B, ayse.id, bakiye=10)
    d.db.commit()
    kontrol(e._bakiye_rezerve_et(SUNUCU_A, ali.id, 80) and e._bakiye_rezerve_et(SUNUCU_A, ayse.id, 80),
            "düello: iki bahis A'da emanete alındı")
    d.db.commit()
    kontrol(not e._bakiye_rezerve_et(SUNUCU_B, ayse.id, 80), "düello: B'deki yetersiz bakiye A'daki parayla karşılanamaz")
    kontrol(not e._bakiye_rezerve_et(SUNUCU_A, ayse.id, 80), "emanetteki para ikinci kez harcanamaz")
    zar = e.DuelloZarView(SUNUCU_A, ali, ayse, 80)
    zar.zarlar = {ali.id: 10, ayse.id: 90}
    await zar.sonuclandir(sahte_etkilesim())
    kontrol((bakiye(SUNUCU_A, ali), bakiye(SUNUCU_A, ayse), bakiye(SUNUCU_B, ayse), bakiye(SUNUCU_B, ali)) == (170, 180, 10, 500),
            "düello (zar): kazanana pot (2x) A'da ödendi, B etkilenmedi")
    e._bakiye_rezerve_et(SUNUCU_A, ali.id, 50)
    e._bakiye_rezerve_et(SUNUCU_A, ayse.id, 50)
    d.db.commit()
    tkm = e.DuelloTKMView(SUNUCU_A, ali, ayse, 50, mesaj_ref=SahteMesaj())
    await tkm.on_timeout()
    kontrol((bakiye(SUNUCU_A, ali), bakiye(SUNUCU_A, ayse)) == (170, 180), "düello (TKM) zaman aşımı: iade A'da")

    # ── XP buffer + seviye bonusu: sunucu bazlı ──
    d.sunucu_ayar_guncelle(SUNUCU_A, xp_aktif=1)
    d.sunucu_ayar_guncelle(SUNUCU_B, xp_aktif=1)
    e.xp_cooldown.clear()
    for sunucu in (SUNUCU_A, SUNUCU_B):
        mesaj = types.SimpleNamespace(author=veli, content="merhaba", guild=types.SimpleNamespace(id=sunucu), channel=SahteKanal())
        await cog.on_message(mesaj)
    kontrol(set(cog._xp_buffer) == {(SUNUCU_A, veli.id), (SUNUCU_B, veli.id)}, "XP buffer (sunucu, kullanıcı) anahtarlı")
    kontrol(cog._xp_buffer[(SUNUCU_B, veli.id)].get("yeni") and not cog._xp_buffer[(SUNUCU_A, veli.id)].get("yeni"),
            "XP: A'da profil var, B'de yeni profil olarak işaretli")
    cog._flush_xp_to_db()
    xp_a = d.db.execute("SELECT xp FROM ekonomi WHERE sunucu_id = ? AND kullanici_id = ?", (SUNUCU_A, veli.id)).fetchone()[0]
    xp_b = d.db.execute("SELECT xp FROM ekonomi WHERE sunucu_id = ? AND kullanici_id = ?", (SUNUCU_B, veli.id)).fetchone()[0]
    kontrol(5 <= xp_a <= 15 and 5 <= xp_b <= 15 and bakiye(SUNUCU_B, veli) == 0, "XP flush: iki sunucuya ayrı satır")
    once_a, once_b = bakiye(SUNUCU_A, veli), bakiye(SUNUCU_B, veli)
    d.db.execute("UPDATE ekonomi SET xp = 99 WHERE sunucu_id = ? AND kullanici_id = ?", (SUNUCU_A, veli.id))
    d.db.commit()
    e.xp_cooldown.clear()
    await cog.on_message(types.SimpleNamespace(author=veli, content="selam", guild=types.SimpleNamespace(id=SUNUCU_A), channel=SahteKanal()))
    cog._flush_xp_to_db()
    seviye_a = d.db.execute("SELECT seviye FROM ekonomi WHERE sunucu_id = ? AND kullanici_id = ?", (SUNUCU_A, veli.id)).fetchone()[0]
    kontrol(seviye_a == 2 and bakiye(SUNUCU_A, veli) == once_a + 50 and bakiye(SUNUCU_B, veli) == once_b,
            "seviye atlama (+50 bonus) sadece mesajın atıldığı sunucuda")

    # ── Sıralama / geçmiş / başarımlar: sadece bu sunucu ──
    ctx = sahte_ctx(SUNUCU_B, ali)
    await cog.siralama.callback(cog, ctx)
    metin = ctx.kanal.son_metin()
    kontrol(f"K{ali.id}" in metin and f"K{ayse.id}" in metin and "**K10**" not in metin and "toplam 3 oyuncu" in metin,
            "!siralama: sadece bu sunucunun oyuncuları (B: 3 oyuncu, eski Mezar verisi yok)")
    # A: Ayse 180, Veli 180, Ali 170 → Ali #3; B: Ali 500 → #1
    kontrol(cog._siralama_getir(SUNUCU_B, ali.id) == "`#1`" and cog._siralama_getir(SUNUCU_A, ali.id) == "`#3`",
            "profil sırası sunucu bazlı (B'de #1, A'da #3)")
    kontrol(islem_sayisi(SUNUCU_A, ali) > 0 and all(r[0] != "paraekle" for r in d.islem_gecmisi_al(SUNUCU_A, ali.id, 50)),
            "işlem geçmişi sunucu bazlı (B'deki paraekle A'da görünmez)")
    d.basarim_ver(SUNUCU_A, ali.id, "ilk_kumar")
    kontrol(d.basarim_kontrol(SUNUCU_A, ali.id, "ilk_kumar") and not d.basarim_kontrol(SUNUCU_B, ali.id, "ilk_kumar"),
            "başarımlar sunucu bazlı")
    try:
        d.islem_kaydet(ali.id, "transfer", 5, "eski imza")
        kontrol(False, "eski (global) imzalı çağrı reddedilmeli")
    except TypeError:
        kontrol(True, "eski imzalı ekonomi çağrısı TypeError ile reddedildi (sessiz yanlış kayıt yok)")

    # Para korunumu: A ve B'de yapılan her şeyden sonra eski Mezar verisi aynı kalmalı (ayrı kontrol main'de)


def main():
    gercek_izler_once = {ek: dosya_izi(GERCEK_DB + ek) for ek in ("", "-wal")}
    # Bot dizininde önceden var olan yedekler (ör. gerçek ilk açılıştaki migrasyon yedeği) hata sayılmaz;
    # yalnızca test sırasında YENİ yedek oluşmamalı.
    gercek_yedekler_once = set(glob.glob(GERCEK_DB + ".bak-ekonomi-*"))
    gecici = tempfile.mkdtemp(prefix="mezarbot_smoke_")
    test_db = os.path.join(gecici, "mezarbot.db")

    if GERCEK_DB_KOPYASI:
        if not os.path.exists(GERCEK_DB):
            print(f"HATA: {GERCEK_DB} yok, kopya testi yapılamaz.")
            return 2
        for ek in ("", "-wal", "-shm"):
            if os.path.exists(GERCEK_DB + ek):
                shutil.copy2(GERCEK_DB + ek, test_db + ek)
        print(f"• Gerçek DB'nin kopyası kullanılıyor: {test_db}")
    else:
        eski_sema_olustur(test_db)
        print(f"• Eski şemalı test DB'si: {test_db}")
    sayim_once = tablo_sayimlari(test_db)
    zaten_tasinmis = GERCEK_DB_KOPYASI and ekonomi_sunucu_bazli_mi(test_db)
    if zaten_tasinmis:
        print("• Gerçek DB zaten sunucu bazlı (ilk açılışta taşınmış) → migrasyonun tekrar çalışınca veriye dokunmadığı doğrulanacak")
        ekonomi_once = {}
        _c = sqlite3.connect(test_db)
        try:
            sunucu_toplam_once = sunucu_toplamlari(_c)
        finally:
            _c.close()
        # [6]'daki "Mezar ekonomisi değişmedi" kontrolü için Mezar sunucusunun başlangıç toplamı
        toplam_once = next(((n, b, x) for s, n, b, x in sunucu_toplam_once if s == BEKLENEN_ESKI_SUNUCU), (0, 0, 0))
    else:
        ekonomi_once, toplam_once = eski_ekonomi_goruntusu(test_db)

    # Bot modüllerini import etmeden ÖNCE: database.py import anında bağlanır
    os.environ["MEZARBOT_DB"] = test_db
    sys.path.insert(0, BOT_DIZINI)

    try:
        print("\n[1] Yapılandırma")
        import yapilandirma as y
        kontrol(y.DB_DOSYA == test_db and y.DB_DOSYA != GERCEK_DB, "DB yolu geçici dosyaya yönlendirildi")
        kontrol(os.path.isabs(y.YTDL_CACHE_DIZINI) and y.YTDL_CACHE_DIZINI.startswith(BOT_DIZINI), "yt-dlp cache dizini bot dizininde")
        if CONFIG_ESKI_SUNUCU:
            kontrol(y.ESKI_EKONOMI_SUNUCU_ID == BEKLENEN_ESKI_SUNUCU, "config.json → eski_ekonomi_sunucu_id okundu")
        else:
            y.ESKI_EKONOMI_SUNUCU_ID = BEKLENEN_ESKI_SUNUCU   # database bunu import anında alır
        import arayuz
        kontrol(os.path.isabs(arayuz.FFMPEG_YOLU), f"FFMPEG_YOLU mutlak: {arayuz.FFMPEG_YOLU}")

        print("\n[2] Şema + migrasyonlar (iki kez)")
        import database as d
        d.veritabanini_kur()
        d.veritabanini_kur()

        def kolonlar(tablo):
            return {r[1] for r in d.db.execute(f'PRAGMA table_info("{tablo}")')}

        kontrol(set(d.SUNUCU_AYAR_KOLONLARI) <= kolonlar("sunucu_ayarlar"), "sunucu_ayarlar: beyaz listedeki tüm kolonlar mevcut")
        kontrol(set(d.KELIME_OYUNU_KOLONLARI) <= kolonlar("kelime_oyunu"), "kelime_oyunu: kelime_sayisi migrasyonu")
        kontrol({"streak", "gunluk_kayip", "kumar_kazanma", "transfer_sayisi"} <= kolonlar("ekonomi"), "ekonomi migrasyonları")
        kontrol("sunucu_id" in kolonlar("moderasyon_log"), "moderasyon_log.sunucu_id migrasyonu")
        for tablo in ("afk_durumlari", "dukkan_urunler", "envanter", "turkce_sozluk", "kullanilan_kelimeler",
                      "islem_gecmisi", "basarimlar", "kelime_puanlari", "gonderilen_firsatlar"):
            kontrol(tablo in tablo_sayimlari(test_db), f"tablo var: {tablo}")

        # Migrasyonlar veri SİLMEMELİ. (Artış olabilir: ör. eski 'ayarlar' → sunucu_ayarlar taşıması,
        # boş dukkan_urunler tohumlaması, eski_global_* yedek tabloları.) Sadece azalan/kaybolan tablo hata sayılır.
        sayim_sonra = tablo_sayimlari(test_db)
        kaybolan = {t: (n, sayim_sonra.get(t)) for t, n in sayim_once.items()
                    if sayim_sonra.get(t) is None or sayim_sonra[t] < n}
        kontrol(not kaybolan, f"hiçbir tablo/satır kaybolmadı {kaybolan or ''}")
        if GERCEK_DB_KOPYASI:
            # sqlite_sequence = SQLite'ın AUTOINCREMENT sayaç defteri (veri değil): ekonomi migrasyonu yeni
            # islem_gecmisi/envanter tablolarına sayaç satırı ekler. Sayacın korunması [3]'te ayrıca doğrulanır.
            degisen = {t: (n, sayim_sonra[t]) for t, n in sayim_once.items()
                       if sayim_sonra[t] != n and t != "sqlite_sequence"}
            kontrol(not degisen, f"gerçek veri kopyasında mevcut tabloların satır sayıları birebir aynı {degisen or ''}")
        if not GERCEK_DB_KOPYASI:
            kontrol(d.sunucu_ayar_al(111)["log_kanal_id"] == 555, "eski 'ayarlar' tablosu → sunucu_ayarlar (güncelleme)")
            kontrol(d.sunucu_ayar_al(222)["log_kanal_id"] == 666, "eski 'ayarlar' tablosu → sunucu_ayarlar (ekleme)")
            kontrol(d.kelime_oyunu_al(111)["son_kelime"] == "elma", "kelime oyunu verisi korundu")

        print("\n[3] Ekonomi migrasyonu: global → sunucu bazlı")
        for t in EKONOMI_TABLOLARI:
            kontrol("sunucu_id" in kolonlar(t), f"{t}: sunucu_id kolonu var")
        pk = {r[1]: r[5] for r in d.db.execute('PRAGMA table_info("ekonomi")') if r[5]}
        kontrol(pk == {"sunucu_id": 1, "kullanici_id": 2}, "ekonomi birincil anahtarı (sunucu_id, kullanici_id)")
        for t, (eski_kolonlar, eski_satirlar) in ekonomi_once.items():
            yeni = _satirlar(d.db, t, eski_kolonlar, "WHERE sunucu_id = ?", (BEKLENEN_ESKI_SUNUCU,))
            baska = d.db.execute(f'SELECT COUNT(*) FROM "{t}" WHERE sunucu_id IS NOT ?', (BEKLENEN_ESKI_SUNUCU,)).fetchone()[0]
            yedek_tablo = _satirlar(d.db, f"eski_global_{t}", eski_kolonlar)
            kontrol(yeni == eski_satirlar and baska == 0 and yedek_tablo == eski_satirlar,
                    f"{t}: {len(eski_satirlar)} eski satırın hepsi birebir Mezar sunucusunda; eski_global_{t} aynen saklandı")
        if zaten_tasinmis:
            kontrol(sunucu_toplamlari(d.db) == sunucu_toplam_once,
                    f"zaten taşınmış DB: sunucu başına toplamlar birebir aynı {sunucu_toplam_once}")
            kontrol(not glob.glob(test_db + ".bak-ekonomi-*"),
                    "zaten taşınmış DB: migrasyon tekrar çalışınca yedek almadı (bir şey yapmadı)")
        else:
            toplam_sonra = tuple(d.db.execute(
                "SELECT COUNT(*), COALESCE(SUM(bakiye), 0), COALESCE(SUM(xp), 0) FROM ekonomi WHERE sunucu_id = ?",
                (BEKLENEN_ESKI_SUNUCU,)).fetchone())
            kontrol(toplam_sonra == toplam_once,
                    f"ekonomi toplamları aynı: {toplam_once[0]} kullanıcı, bakiye {toplam_once[1]}, XP {toplam_once[2]}")
            if "islem_gecmisi" in ekonomi_once:
                eski_seq = d.db.execute("SELECT seq FROM sqlite_sequence WHERE name = 'eski_global_islem_gecmisi'").fetchone()
                yeni_seq = d.db.execute("SELECT seq FROM sqlite_sequence WHERE name = 'islem_gecmisi'").fetchone()
                kontrol(not eski_seq or (yeni_seq and yeni_seq[0] >= eski_seq[0]),
                        "islem_gecmisi AUTOINCREMENT sayacı korundu (silinmiş id'ler tekrar kullanılmaz)")
            yedekler = glob.glob(test_db + ".bak-ekonomi-*")
            kontrol(len(yedekler) == 1, f"migrasyon öncesi tek yedek alındı (iki çalıştırmada): {os.path.basename(yedekler[0]) if yedekler else '-'}")
            kontrol(oct(os.stat(yedekler[0]).st_mode & 0o777) == oct(0o600), "yedek dosyası izni 0600")
            # Yedek, ekonomi migrasyonundan HEMEN önceki durumdur: veritabanini_kur()'un eklemeli ALTER'ları
            # (streak vb. varsayılanlı kolonlar) uygulanmış olabilir → orijinal kolonlar üzerinden karşılaştır.
            yedek = sqlite3.connect(yedekler[0])
            try:
                yedek_sunucusuz = all("sunucu_id" not in _kolonlar(yedek, t) for t in ekonomi_once)
                yedek_satirlar = {t: _satirlar(yedek, t, k) for t, (k, _) in ekonomi_once.items()}
                yedek_toplam = tuple(yedek.execute(
                    "SELECT COUNT(*), COALESCE(SUM(bakiye), 0), COALESCE(SUM(xp), 0) FROM ekonomi").fetchone())
            finally:
                yedek.close()
            kontrol(yedek_sunucusuz and yedek_satirlar == {t: s for t, (_, s) in ekonomi_once.items()}
                    and yedek_toplam == toplam_once,
                    "yedek = migrasyon öncesi (global) ekonomi, birebir (sadece eklemeli ALTER kolonları fazla)")
        kontrol(d._ekonomi_sunucu_bazli_migrasyon() is False, "üçüncü çağrı: migrasyon bir şey yapmadı (idempotent)")
        migrasyon_hata_senaryolari(d, gecici)

        print("\n[4] Güvenlik")
        try:
            d.sunucu_ayar_guncelle(1, **{"log_kanal_id = 1; DROP TABLE ekonomi; --": 1})
            kontrol(False, "kolon beyaz listesi")
        except ValueError:
            kontrol(True, "sunucu_ayar_guncelle: beyaz liste dışı kolon reddedildi")
        try:
            d.kelime_oyunu_guncelle(1, bilinmeyen=1)
            kontrol(False, "kelime oyunu beyaz listesi")
        except ValueError:
            kontrol(True, "kelime_oyunu_guncelle: beyaz liste dışı kolon reddedildi")
        if d.SAHIP_ID is None:   # yeni kurulum: sahip_id boş → testte sahte sahip
            d.SAHIP_ID = 700000000000000099
        kontrol(d.vip_kontrol(types.SimpleNamespace(id=d.SAHIP_ID)), "sahip ID config.json'dan (vip_kontrol)")

        print("\n[5] Modül import + tüm cog'ları çevrimdışı yükleme")
        import main
        kontrol(not any(v in main.vagonlar for v in ("cogs.bedwars", "cogs.cs2sunucu", "cogs.ekonomi", "cogs.kelimeoyunu", "cogs.oyun_indirimleri", "cogs.itiraf", "cogs.starboard", "cogs.wishlist")), "devre dışı cog'lar yüklenmiyor")
        kontrol(not os.path.exists(os.path.join(BOT_DIZINI, "cogs", "bedwars.py")), "eski cog'lar cogs/ dışında")
        kontrol(main.bot.owner_id == y.SAHIP_ID, "bot.owner_id = sahip_id")
        for vagon in main.vagonlar:
            importlib.import_module(vagon)

        async def yukle_kaldir():
            for vagon in main.vagonlar:
                await main.bot.load_extension(vagon)
            kontrol(len(main.bot.cogs) == len(main.vagonlar), f"{len(main.bot.cogs)} cog yüklendi (beklenen: {len(main.vagonlar)})")
            for komut in ("ayarlar", "yamanotukanal", "cal", "ozelodaaktif", "ozelodakapat", "ozeloda", "oda", "ciz", "draw", "yardim", "help"):
                kontrol(main.bot.get_command(komut) is not None, f"komut kayıtlı: !{komut}")
            for vagon in list(main.bot.extensions):
                await main.bot.unload_extension(vagon)
        asyncio.run(yukle_kaldir())

        from cogs import muzik
        kontrol("nocheckcertificate" not in muzik.ydl_opts and "nocheckcertificate" not in muzik.ydl_playlist_opts,
                "yt-dlp TLS doğrulaması açık")

        print("\n[6] Sunucu bazlı ekonomi (komut kodu, sahte ctx) + çok sunuculu davranış")
        from cogs_devre_disi import ekonomi as e
        asyncio.run(ekonomi_sunucu_bazli_testleri(d, e))
        toplam_son = tuple(d.db.execute(
            "SELECT COUNT(*), COALESCE(SUM(bakiye), 0), COALESCE(SUM(xp), 0) FROM ekonomi WHERE sunucu_id = ?",
            (BEKLENEN_ESKI_SUNUCU,)).fetchone())
        kontrol(toplam_son == toplam_once, "başka sunuculardaki tüm işlemlerden sonra Mezar sunucusunun ekonomisi değişmedi")

        from cogs.yonetim import afk_sebep_temizle
        temiz = afk_sebep_temizle("@everyone [tikla](https://kotu.example) <@&123456789012345678>")
        kontrol("https://" not in temiz and "@everyone" not in temiz, "AFK sebebi: link ve mention etkisiz")
        d.afk_ayarla(1, 42, "yemek")
        kontrol(d.afk_al(1, 42) == "yemek" and d.afk_al(2, 42) is None, "AFK sunucu bazlı")
        d.afk_kaldir(1, 42)
        uye = types.SimpleNamespace(id=5, guild_permissions=types.SimpleNamespace(administrator=False, manage_guild=True))
        sade = types.SimpleNamespace(id=6, guild_permissions=types.SimpleNamespace(administrator=False, manage_guild=False))
        kontrol(d.yonetici_mi(uye) and not d.yonetici_mi(sade), "yonetici_mi: Sunucuyu Yönet yetkisine göre")
        d.sunucu_ayar_guncelle(333, xp_aktif=1, yama_notlari_kanal_id=4444)
        kontrol(d.sunucu_ayar_al(333)["xp_aktif"] == 1 and d.sunucu_ayar_al(444) is None, "sunucu ayarları sunucu bazlı (cache)")

        print("\n[7] Gerçek veritabanı")
        kontrol({ek: dosya_izi(GERCEK_DB + ek) for ek in ("", "-wal")} == gercek_izler_once,
                "gerçek mezarbot.db (+wal) boyut/mtime değişmedi")
        kontrol(set(glob.glob(GERCEK_DB + ".bak-ekonomi-*")) == gercek_yedekler_once,
                "bot dizininde yeni yedek dosyası oluşmadı (test yedekleri geçici dizinde)")

        print("\nTÜM KONTROLLER GEÇTİ ✅")
        return 0
    except AssertionError as hata:
        print(f"\n❌ BAŞARISIZ: {hata}\n   (geçici dosyalar incelemek için bırakıldı: {gecici})")
        return 1
    finally:
        try:
            import database as d
            d.db.close()
        except Exception:
            pass
        if {ek: dosya_izi(GERCEK_DB + ek) for ek in ("", "-wal")} != gercek_izler_once:
            print("‼️ UYARI: gerçek mezarbot.db'nin izi değişti!")


if __name__ == "__main__":
    kod = main()
    if kod == 0:
        gecici_dizinler = [p for p in (os.environ.get("MEZARBOT_DB"),) if p]
        for p in gecici_dizinler:
            shutil.rmtree(os.path.dirname(p), ignore_errors=True)
    sys.exit(kod)
