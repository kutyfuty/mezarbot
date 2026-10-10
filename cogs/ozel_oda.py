"""
Özel ses odaları (katıl → oda oluştur) — çok sunuculu, sunucu başına VARSAYILAN KAPALI.

Açma / kapama (sadece Sunucuyu Yönet / Yönetici):
    /ozelodaaktif  → sistemi açar ve her şeyi kendisi kurar (ya da var olanı kullanır/onarır):
                     "🔊 Özel Odalar" kategorisi (kanal listesinin EN ALTINDA), "➕ Oda Oluştur" ses kanalı,
                     "🎛️oda-paneli" metin kanalı + kalıcı panel mesajı. Botun eksik yetkilerini tek tek söyler.
    /ozelodakapat  → sistemi kapatır: hub + panel kanalı silinir, BOŞ odalar hemen silinir; içinde insan olan
                     odalar boşalınca silinir (bekleyen sayısı yöneticiye söylenir), kategori en son silinir.
    Kapalı sunucuda cog hiçbir şey yapmaz (tek istisna: kapatma öncesinden kalan odaların boşalınca silinmesi).

Ayarlar: /ozeloda ayar (varsayılan limit, ad şablonu, boş oda silme süresi, kişi başı oda, gizlemeye izin).
Oda sahibi: /oda … komutları + odanın ses kanalı sohbetine gönderilen kontrol paneli (kalıcı butonlar).

Tasarım kararları:
 - Sahip odadan çıkınca ve içeride başkaları varsa oda KORUNUR, sahiplik otomatik devredilmez; odadaki biri
   /oda sahiplen ya da paneldeki 🙋 Sahiplen ile devralabilir (sahip geri dönerse sahip olmaya devam eder).
 - Sahip yetkileri SADECE o kanalda üye izin geçersiz kılmasıyla verilir (Kanalı Yönet, Üyeleri Taşı,
   Sustur, Sağırlaştır); sunucu genelinde hiçbir yetki verilmez.
 - Kilitle = rollerin 'Bağlan' izni reddedilir; Gizle = rollerin 'Kanalı Gör' izni reddedilir. Aç/Göster = rol
   izinleri kategorinin haline geri döner. Davetliler / sahip / bot üye bazlı izinle her zaman girer.
 - Boş oda temizliği: olaylar 'boşalma zamanı'nı işaretler, 5 sn'lik tek döngü karar verir (temizlik_karari).
 - Kalıcı butonlar DynamicItem (custom_id = ozeloda:<eylem>:<kanal_id>) → yeniden başlatma sonrası da çalışır.
 - Ses olayı dinleyicisinde DB sorgusu yok (cache); DB'ye sadece oda oluştur/sil/devret gibi seyrek anlarda yazılır.
"""
import asyncio
import datetime
import logging
import re
import time

import discord
from discord import app_commands
from discord.ext import commands, tasks
from discord.utils import escape_markdown

import ozel_oda_veritabani as odb
from arayuz import AYIRICI, Renkler
from database import yonetici_kontrol, yonetici_mi

logger = logging.getLogger('MezarBot.OzelOda')

# ══════════════════════════════════════════════
#  SABİTLER
# ══════════════════════════════════════════════

KATEGORI_ADI = "🔊 Özel Odalar"
HUB_ADI = "➕ Oda Oluştur"
PANEL_KANAL_ADI = "🎛️oda-paneli"
PANEL_KANAL_ANAHTARI = "oda-paneli"          # Discord metin kanalı adını normalize edebilir → içerir mi?

AD_MAX = 50
LIMIT_MIN, LIMIT_MAX = 0, 99
SURE_MIN, SURE_MAX = 10, 3600               # boş oda silme süresi (sn)
KISI_BASI_MIN, KISI_BASI_MAX = 1, 5
OLUSTURMA_BEKLEMESI = 20                    # aynı kullanıcı için iki oda oluşturma arası (sn)
BUTON_ODA_EK_SURE = 120                     # panel butonuyla (seste değilken) açılan oda için katılma payı (sn)
AD_DEGISIM_HAKKI, AD_DEGISIM_PENCERESI = 2, 600   # Discord: kanal adı 10 dk'da en fazla 2 kez değişir
SAHIP_BILDIRIM_ARALIGI = 120                # "sahip ayrıldı" notu en sık bu aralıkla
YONETICI_BILDIRIM_ARALIGI = 6 * 3600        # "kurulum bozuldu" uyarısı en sık bu aralıkla
TEMIZLIK_ARALIGI = 5                        # sn
API_ZAMAN_ASIMI = 15                        # sn — rate limit beklemesi etkileşimi kilitlemesin

SABLON_ALANLARI = ("kullanici", "sayi")
AYAR_ANAHTARLARI = {
    # anahtar: (görünen ad, eş anlamlılar)
    'limit':   ("Varsayılan kişi limiti", ("limit", "kisi", "kişi")),
    'sablon':  ("Ad şablonu", ("sablon", "şablon", "ad", "isim")),
    'sure':    ("Boş oda silme süresi", ("sure", "süre", "silme", "gecikme")),
    'maxoda':  ("Kişi başı en fazla oda", ("maxoda", "max", "odasayisi", "oda")),
    'gizleme': ("Üyeler odasını gizleyebilir", ("gizleme", "gizle", "gizlilik")),
}

# Bot yetkileri: (Permissions özniteliği, Türkçe ad)
ZORUNLU_IZINLER = (
    ("view_channel", "Kanalları Görüntüle"),
    ("manage_channels", "Kanalları Yönet"),
    ("manage_roles", "Rolleri Yönet (izin geçersiz kılmaları için)"),
    ("move_members", "Üyeleri Taşı"),
    ("connect", "Bağlan"),
    ("send_messages", "Mesaj Gönder"),
    ("embed_links", "Bağlantı Yerleştir"),
)
ONERILEN_IZINLER = (
    ("mute_members", "Üyeleri Sustur (oda sahibine odasında verilir)"),
    ("deafen_members", "Üyeleri Sağırlaştır (oda sahibine odasında verilir)"),
    ("read_message_history", "Mesaj Geçmişini Oku"),
)


# ══════════════════════════════════════════════
#  SAF MANTIK (Discord'a dokunmaz — tests/ozel_oda_test.py)
# ══════════════════════════════════════════════

_MENTION_RE = re.compile(r"<(?:@[!&]?|#)\d+>")
_OZEL_EMOJI_RE = re.compile(r"<a?:(\w+):\d+>")
_HERKES_RE = re.compile(r"@\s*(?:everyone|here)", re.IGNORECASE)
_LINK_RE = re.compile(r"(?:https?://|www\.)\S+|(?:discord(?:app)?\.(?:gg|com/invite)|dsc\.gg)/\S*", re.IGNORECASE)
_KONTROL_RE = re.compile(r"[\x00-\x1f\x7f​-‏ -‮⁠-⁤﻿]")
_SABLON_ALANI_RE = re.compile(r"\{([^{}]*)\}")


def ad_temizle(metin, uzunluk=AD_MAX):
    """Kanal adı için güvenli metin: mention / @everyone / @here / link / kontrol karakteri silinir,
    boşluklar sadeleşir, `uzunluk` karaktere kırpılır. Boş kalabilir ("")."""
    metin = str(metin or "")
    metin = _KONTROL_RE.sub(" ", metin)
    metin = _MENTION_RE.sub("", metin)
    metin = _OZEL_EMOJI_RE.sub(r"\1", metin)
    metin = _LINK_RE.sub("", metin)
    metin = _HERKES_RE.sub("", metin)
    metin = metin.replace("@", "")
    metin = " ".join(metin.split())
    return metin[:uzunluk].strip()


def ad_dogrula(metin):
    """Kullanıcının yazdığı oda adı → temiz ad. Geçersizse Türkçe mesajlı ValueError."""
    ham = " ".join(str(metin or "").split())
    if len(ham) > AD_MAX:
        raise ValueError(f"Oda adı en fazla {AD_MAX} karakter olabilir (yazdığın: {len(ham)}).")
    temiz = ad_temizle(ham)
    if not temiz:
        raise ValueError("Geçerli bir oda adı yaz (etiket ve link kullanılamaz).")
    return temiz


def limit_dogrula(deger):
    """'5' / 5 / '0' / 'sınırsız' → 0-99 arası int. Geçersizse Türkçe mesajlı ValueError."""
    if isinstance(deger, bool):
        raise ValueError("Limit bir sayı olmalı.")
    if isinstance(deger, int):
        sayi = deger
    else:
        metin = str(deger or "").strip().casefold()
        if metin in ("sınırsız", "sinirsiz", "limitsiz", "yok", "kapat", "∞"):
            return 0
        if not re.fullmatch(r"[+-]?\d{1,4}", metin):
            raise ValueError(f"Limit {LIMIT_MIN}-{LIMIT_MAX} arası bir sayı olmalı (0 = sınırsız).")
        sayi = int(metin)
    if not LIMIT_MIN <= sayi <= LIMIT_MAX:
        raise ValueError(f"Limit {LIMIT_MIN}-{LIMIT_MAX} arası olmalı (0 = sınırsız).")
    return sayi


def sablon_dogrula(sablon):
    """Ad şablonunu doğrular → sadeleşmiş şablon. Sadece {kullanici} ve {sayi} alanları geçerlidir."""
    sablon = " ".join(str(sablon or "").split())
    if not sablon:
        raise ValueError("Şablon boş olamaz. Örnek: `🔊 {kullanici} odası`")
    if len(sablon) > AD_MAX + 10:
        raise ValueError(f"Şablon çok uzun (en fazla {AD_MAX + 10} karakter).")
    bilinmeyen = [a for a in _SABLON_ALANI_RE.findall(sablon) if a not in SABLON_ALANLARI]
    if bilinmeyen:
        raise ValueError("Bilinmeyen alan: " + ", ".join(f"`{{{a}}}`" for a in bilinmeyen)
                         + " — kullanılabilir: `{kullanici}`, `{sayi}`")
    # sablon_uygula boş sonuçta "Özel Oda"ya düşer → burada ham şablonu doğrudan temizleyerek kontrol et
    if not ad_temizle(sablon.replace("{kullanici}", "Ali").replace("{sayi}", "1")):
        raise ValueError("Bu şablondan geçerli bir oda adı çıkmıyor.")
    return sablon


def sablon_uygula(sablon, kullanici_adi, sayi=1):
    """Şablonu doldurur (str.format KULLANILMAZ — alan erişimi enjeksiyonu yok) ve adı temizler.
    Kullanıcı adındaki mention/link de temizlenir; sonuç boşsa 'Özel Oda'."""
    kullanici = ad_temizle(kullanici_adi, 32) or "Üye"
    ad = str(sablon or VARSAYILAN_SABLON).replace("{kullanici}", kullanici).replace("{sayi}", str(int(sayi)))
    return ad_temizle(ad) or "Özel Oda"


VARSAYILAN_SABLON = odb.VARSAYILAN_AYARLAR['ad_sablonu']


def sure_dogrula(deger):
    """'30' / '30s' / '2dk' / '1:30' → saniye (SURE_MIN-SURE_MAX). Geçersizse ValueError."""
    metin = str(deger or "").strip().casefold().replace(" ", "")
    m = re.fullmatch(r"(\d{1,2}):(\d{2})", metin)
    if m:
        sn = int(m[1]) * 60 + int(m[2])
    else:
        m = re.fullmatch(r"(\d{1,5})(s|sn|saniye|dk|d|m|dakika)?", metin)
        if not m:
            raise ValueError("Süreyi saniye (ör. `30`) ya da dakika (ör. `2dk`) olarak yaz.")
        sn = int(m[1]) * (60 if m[2] in ("dk", "d", "m", "dakika") else 1)
    if not SURE_MIN <= sn <= SURE_MAX:
        raise ValueError(f"Süre {SURE_MIN} sn ile {SURE_MAX // 60} dk arası olmalı.")
    return sn


def evet_hayir(deger):
    metin = str(deger or "").strip().casefold()
    if metin in ("evet", "aç", "ac", "açık", "acik", "1", "true", "on", "izin", "izinli"):
        return True
    if metin in ("hayır", "hayir", "kapat", "kapalı", "kapali", "0", "false", "off", "yasak"):
        return False
    raise ValueError("`evet` ya da `hayır` yaz.")


def ayar_anahtari_coz(anahtar):
    """Kullanıcının yazdığı ayar adı → AYAR_ANAHTARLARI anahtarı ya da None."""
    metin = str(anahtar or "").strip().casefold()
    for k, (_, esler) in AYAR_ANAHTARLARI.items():
        if metin == k or metin in esler:
            return k
    return None


def bekleme_kalan(son_zaman, simdi, aralik=OLUSTURMA_BEKLEMESI):
    """Bekleme süresinden kalan saniye (0 = serbest)."""
    if son_zaman is None:
        return 0.0
    return max(0.0, aralik - (simdi - son_zaman))


def ad_degisim_kalan(zamanlar, simdi, hak=AD_DEGISIM_HAKKI, pencere=AD_DEGISIM_PENCERESI):
    """Son `pencere` sn içindeki değişiklik zamanlarına göre yeni ad değişikliği için beklenecek sn (0 = serbest)."""
    son = sorted(z for z in zamanlar if simdi - z < pencere)
    if len(son) < hak:
        return 0.0
    return max(0.0, pencere - (simdi - son[-hak]))


def temizlik_karari(insan_sayisi, bos_baslangic, simdi, gecikme):
    """Oda temizliği kararı:
      'tut'      → içeride insan var (boşalma işareti kaldırılmalı)
      'zamanla'  → boş ama henüz işaretlenmemiş (bos_baslangic = simdi yapılmalı)
      'bekle'    → boş, süre dolmadı
      'sil'      → `gecikme` sn'dir boş → silinmeli
    bos_baslangic gelecekte olabilir (butonla açılan odaya katılma payı)."""
    if insan_sayisi > 0:
        return 'tut'
    if bos_baslangic is None:
        return 'zamanla'
    return 'sil' if simdi - bos_baslangic >= gecikme else 'bekle'


def eksik_izinler(izinler):
    """discord.Permissions → (zorunlu_eksik, onerilen_eksik) Türkçe ad listeleri. Yönetici her şeyi karşılar."""
    if izinler.administrator:
        return [], []
    zorunlu = [ad for attr, ad in ZORUNLU_IZINLER if not getattr(izinler, attr)]
    onerilen = [ad for attr, ad in ONERILEN_IZINLER if not getattr(izinler, attr)]
    return zorunlu, onerilen


def sahip_izni(bot_izinleri):
    """Oda sahibine SADECE bu kanalda verilecek izin (bot'un sahip olmadığı izin verilemez → atlanır)."""
    ow = discord.PermissionOverwrite(view_channel=True, connect=True, speak=True, stream=True,
                                     use_voice_activation=True, send_messages=True,
                                     manage_channels=True, move_members=True)
    if bot_izinleri.administrator or bot_izinleri.mute_members:
        ow.mute_members = True
    if bot_izinleri.administrator or bot_izinleri.deafen_members:
        ow.deafen_members = True
    return ow


def bot_izni():
    return discord.PermissionOverwrite(view_channel=True, connect=True, send_messages=True, embed_links=True,
                                       read_message_history=True, manage_channels=True, move_members=True)


def uye_izni():
    """Davetli / eski sahip: odayı görür ve girer."""
    return discord.PermissionOverwrite(view_channel=True, connect=True)


# ══════════════════════════════════════════════
#  GÖRÜNÜMLER (butonlar, modallar, seçim menüleri)
# ══════════════════════════════════════════════

def _cog(interaction):
    return interaction.client.get_cog("OzelOda")


async def _gizli_yanit(interaction, metin=None, embed=None, view=None):
    """Etkileşime gizli (ephemeral) yanıt; zaten yanıtlandıysa followup. Hata yutulur (loglanır)."""
    kw = {'content': metin, 'ephemeral': True, 'allowed_mentions': discord.AllowedMentions.none()}
    if embed is not None:
        kw['embed'] = embed
    if view is not None:
        kw['view'] = view
    try:
        if interaction.response.is_done():
            await interaction.followup.send(**kw)
        else:
            await interaction.response.send_message(**kw)
    except discord.HTTPException as e:
        logger.debug(f"Etkileşim yanıtı gönderilemedi: {e}")


PANEL_EYLEMLERI = ("kilit", "gizlilik", "limit", "ad", "davet", "at", "devret", "sahiplen")


class OdaButonu(discord.ui.DynamicItem[discord.ui.Button],
                template=r"ozeloda:(?P<eylem>kilit|gizlilik|limit|ad|davet|at|devret|sahiplen):(?P<kanal>[0-9]{15,21})"):
    """Oda kontrol paneli butonu. custom_id kanal ID'sini taşır → bot yeniden başlasa da çalışır
    (cog_load'da bot.add_dynamic_items ile tek sefer kaydedilir)."""

    def __init__(self, eylem, kanal_id, etiket=None, emoji=None, stil=discord.ButtonStyle.secondary, satir=None):
        super().__init__(discord.ui.Button(custom_id=f"ozeloda:{eylem}:{kanal_id}", label=etiket, emoji=emoji,
                                           style=stil, row=satir))
        self.eylem = eylem
        self.kanal_id = int(kanal_id)

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(match["eylem"], int(match["kanal"]))

    async def callback(self, interaction):
        cog = _cog(interaction)
        if cog is None:
            return await _gizli_yanit(interaction, "⚠️ Özel oda sistemi şu an yüklü değil.")
        try:
            await cog.panel_etkilesimi(interaction, self.eylem, self.kanal_id)
        except Exception as e:  # DynamicItem hataları sadece loglanır → kullanıcıya da söyle
            logger.error(f"Oda paneli hatası ({self.eylem}, {self.kanal_id}): {e!r}", exc_info=e)
            await _gizli_yanit(interaction, "⚠️ Bir hata oluştu, tekrar dene.")


def oda_paneli_gorunumu(kanal_id, kilitli, gizli):
    """Odanın o anki durumuna göre etiketlenmiş kalıcı panel görünümü."""
    S = discord.ButtonStyle
    v = discord.ui.View(timeout=None)
    v.add_item(OdaButonu("kilit", kanal_id, "Aç" if kilitli else "Kilitle", "🔓" if kilitli else "🔒",
                         S.success if kilitli else S.secondary, 0))
    v.add_item(OdaButonu("gizlilik", kanal_id, "Göster" if gizli else "Gizle", "👁️",
                         S.success if gizli else S.secondary, 0))
    v.add_item(OdaButonu("limit", kanal_id, "Limit", "👥", S.secondary, 0))
    v.add_item(OdaButonu("ad", kanal_id, "Ad", "✏️", S.secondary, 0))
    v.add_item(OdaButonu("davet", kanal_id, "Davet", "➕", S.primary, 1))
    v.add_item(OdaButonu("at", kanal_id, "At", "🚫", S.danger, 1))
    v.add_item(OdaButonu("devret", kanal_id, "Devret", "👑", S.secondary, 1))
    v.add_item(OdaButonu("sahiplen", kanal_id, "Sahiplen", "🙋", S.secondary, 1))
    return v


class KurulumPaneli(discord.ui.View):
    """🎛️oda-paneli kanalındaki kalıcı panel (sabit custom_id'ler; tüm sunucularda aynı görünüm)."""

    def __init__(self):
        super().__init__(timeout=None)

    async def _yonlendir(self, interaction, eylem):
        cog = _cog(interaction)
        if cog is None:
            return await _gizli_yanit(interaction, "⚠️ Özel oda sistemi şu an yüklü değil.")
        await cog.kurulum_paneli_etkilesimi(interaction, eylem)

    @discord.ui.button(label="Oda oluştur", emoji="➕", style=discord.ButtonStyle.success, custom_id="ozeloda:kur:olustur")
    async def olustur(self, interaction, button):
        await self._yonlendir(interaction, "olustur")

    @discord.ui.button(label="Odamı yönet", emoji="🎛️", style=discord.ButtonStyle.primary, custom_id="ozeloda:kur:yonet")
    async def yonet(self, interaction, button):
        await self._yonlendir(interaction, "yonet")

    @discord.ui.button(label="Yardım", emoji="❔", style=discord.ButtonStyle.secondary, custom_id="ozeloda:kur:yardim")
    async def yardim(self, interaction, button):
        await self._yonlendir(interaction, "yardim")

    async def on_error(self, interaction, error, item):
        logger.error(f"Kurulum paneli hatası ({getattr(item, 'custom_id', '?')}): {error!r}", exc_info=error)
        await _gizli_yanit(interaction, "⚠️ Bir hata oluştu, tekrar dene.")


class LimitModali(discord.ui.Modal, title="👥 Kişi limiti"):
    def __init__(self, kanal_id, mevcut):
        super().__init__(timeout=300)
        self.kanal_id = kanal_id
        self.deger = discord.ui.TextInput(label="Limit (0 = sınırsız, en fazla 99)", max_length=3,
                                          default=str(mevcut), placeholder="ör. 5")
        self.add_item(self.deger)

    async def on_submit(self, interaction):
        await _cog(interaction).limit_uygula_etkilesim(interaction, self.kanal_id, self.deger.value)

    async def on_error(self, interaction, error):
        logger.error(f"Limit modalı hatası: {error!r}", exc_info=error)
        await _gizli_yanit(interaction, "⚠️ Bir hata oluştu, tekrar dene.")


class AdModali(discord.ui.Modal, title="✏️ Oda adı"):
    def __init__(self, kanal_id, mevcut):
        super().__init__(timeout=300)
        self.kanal_id = kanal_id
        self.deger = discord.ui.TextInput(label=f"Yeni ad (en fazla {AD_MAX} karakter)", max_length=AD_MAX,
                                          default=(mevcut or "")[:AD_MAX])
        self.add_item(self.deger)

    async def on_submit(self, interaction):
        await _cog(interaction).ad_uygula_etkilesim(interaction, self.kanal_id, self.deger.value)

    async def on_error(self, interaction, error):
        logger.error(f"Ad modalı hatası: {error!r}", exc_info=error)
        await _gizli_yanit(interaction, "⚠️ Bir hata oluştu, tekrar dene.")


class UyeSecimi(discord.ui.UserSelect):
    def __init__(self, eylem, kanal_id):
        yer_tutucu = {"davet": "Davet edilecek üyeleri seç…", "at": "Odadan atılacak üyeleri seç…",
                      "devret": "Yeni oda sahibini seç…"}[eylem]
        super().__init__(placeholder=yer_tutucu, min_values=1, max_values=1 if eylem == "devret" else 10)
        self.eylem = eylem
        self.kanal_id = kanal_id

    async def callback(self, interaction):
        await _cog(interaction).secim_uygula_etkilesim(interaction, self.eylem, self.kanal_id, list(self.values))


class UyeSecimGorunumu(discord.ui.View):
    """Geçici (gizli mesajda) üye seçimi — sadece açan kişi kullanır."""

    def __init__(self, eylem, kanal_id, kullanici_id):
        super().__init__(timeout=120)
        self.kullanici_id = kullanici_id
        self.add_item(UyeSecimi(eylem, kanal_id))

    async def interaction_check(self, interaction):
        return interaction.user.id == self.kullanici_id

    async def on_error(self, interaction, error, item):
        logger.error(f"Üye seçimi hatası: {error!r}", exc_info=error)
        await _gizli_yanit(interaction, "⚠️ Bir hata oluştu, tekrar dene.")


class OnayGorunumu(discord.ui.View):
    """Evet / Vazgeç onayı (sadece komutu kullanan kişi)."""

    def __init__(self, kullanici_id, evet_etiketi="Evet"):
        super().__init__(timeout=60)
        self.kullanici_id = kullanici_id
        self.sonuc = None
        self.evet.label = evet_etiketi

    async def interaction_check(self, interaction):
        if interaction.user.id != self.kullanici_id:
            await _gizli_yanit(interaction, "Bu onay sana ait değil.")
            return False
        return True

    @discord.ui.button(label="Evet", style=discord.ButtonStyle.danger)
    async def evet(self, interaction, button):
        self.sonuc = True
        await interaction.response.edit_message(content="⏳ İşleniyor…", embed=None, view=None)
        self.stop()

    @discord.ui.button(label="Vazgeç", style=discord.ButtonStyle.secondary)
    async def vazgec(self, interaction, button):
        self.sonuc = False
        await interaction.response.edit_message(content="İptal edildi.", embed=None, view=None)
        self.stop()


# ══════════════════════════════════════════════
#  COG
# ══════════════════════════════════════════════

KAPALI_MESAJI = ("🔕 Özel oda sistemi bu sunucuda **kapalı**. "
                 "Bir yönetici (*Sunucuyu Yönet*) `/ozelodaaktif` ile açabilir.")


class OdaHatasi(Exception):
    """Kullanıcıya gösterilecek (Türkçe) oda işlemi hatası."""


def _insanlar(kanal):
    return [m for m in getattr(kanal, "members", ()) if not m.bot]


async def _api(coro, zaman_asimi=API_ZAMAN_ASIMI):
    """Discord API çağrısını zaman aşımıyla çalıştırır (uzun rate-limit beklemesi etkileşimi kilitlemesin)."""
    return await asyncio.wait_for(coro, timeout=zaman_asimi)


class OzelOda(commands.Cog):
    """🔊 Özel ses odaları (katıl → oda oluştur). Sunucu başına varsayılan KAPALI."""

    def __init__(self, bot):
        self.bot = bot
        self._bos_baslangic = {}      # {kanal_id: monotonic} — odada insan kalmadığı an
        self._siliniyor = set()       # silme isteği yolda olan kanallar
        self._hub_islemde = set()     # {(sunucu_id, kullanici_id)} — çift oda oluşturma engeli
        self._son_olusturma = {}      # {(sunucu_id, kullanici_id): monotonic}
        self._ad_degisimleri = {}     # {kanal_id: [monotonic,...]}
        self._sahip_bildirim = {}     # {kanal_id: monotonic}
        self._yonetici_bildirim = {}  # {sunucu_id: monotonic}
        self._onarim_gorevleri = {}   # {sunucu_id: Task}
        self._arka_gorevler = set()
        self._baslangic_yapildi = False

    # ── Yaşam döngüsü ─────────────────────────────

    async def cog_load(self):
        odb.ozel_oda_veritabanini_kur()
        self.bot.add_view(KurulumPaneli())
        self.bot.add_dynamic_items(OdaButonu)
        self.temizlik_dongusu.start()
        if self.bot.is_ready():
            self._arka_gorev(self._baslangic_toparla())

    async def cog_unload(self):
        self.temizlik_dongusu.cancel()
        self.bot.remove_dynamic_items(OdaButonu)
        for t in list(self._arka_gorevler) + list(self._onarim_gorevleri.values()):
            t.cancel()

    def _arka_gorev(self, coro):
        t = asyncio.create_task(coro)
        self._arka_gorevler.add(t)
        t.add_done_callback(self._arka_gorev_bitti)
        return t

    def _arka_gorev_bitti(self, t):
        self._arka_gorevler.discard(t)
        if not t.cancelled() and t.exception() is not None:
            logger.error(f"Özel oda arka görev hatası: {t.exception()!r}", exc_info=t.exception())

    async def cog_check(self, ctx):
        if ctx.guild is None:
            raise commands.NoPrivateMessage()
        return True

    # ── Başlangıç uzlaştırması ────────────────────

    @commands.Cog.listener()
    async def on_ready(self):
        if not self._baslangic_yapildi:
            await self._baslangic_toparla()

    async def _baslangic_toparla(self):
        """Kayıtlı odaları Discord ile uzlaştırır: silinmiş kanalları unutur, BOŞ odaları siler; açık sunucularda
        eksik kurulum parçalarını onarır ve bot kapalıyken hub'a girmiş üyeler için oda açar."""
        if self._baslangic_yapildi:
            return
        self._baslangic_yapildi = True
        unutulan = silinen = 0
        for oda in odb.tum_odalar():
            guild = self.bot.get_guild(oda['sunucu_id'])
            if guild is None or guild.unavailable:
                continue   # sunucu erişilemez: kaydı körlemesine silme
            kanal = guild.get_channel(oda['kanal_id'])
            if kanal is None:
                odb.oda_sil(oda['kanal_id'])
                unutulan += 1
            elif not _insanlar(kanal):
                if await self._odayi_sil(kanal, "Özel oda: bot yeniden başladığında boştu"):
                    silinen += 1
        if unutulan or silinen:
            logger.info(f"🔊 Başlangıç: {unutulan} silinmiş oda unutuldu, {silinen} boş oda silindi")
        for sid in odb.kayitli_sunucular():
            guild = self.bot.get_guild(sid)
            if guild is None or not odb.aktif_mi(sid):
                continue
            await self._kurulumu_onar(guild, "başlangıç")
            ayar = odb.ayar_al(sid)
            hub = guild.get_channel(ayar['hub_id']) if ayar and ayar['hub_id'] else None
            for uye in _insanlar(hub) if hub else ():
                self._arka_gorev(self._hub_katilimi(uye))

    # ── Dinleyiciler ──────────────────────────────

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if before.channel == after.channel:
            return
        guild = member.guild
        # Kapatılmış sunucuda sadece kapatmadan kalan odaların boşalması izlenir (sonra silinsinler)
        if before.channel is not None and odb.oda_mi(before.channel.id):
            self._ayrilma(before.channel, member)
        if after.channel is not None and not member.bot and odb.oda_mi(after.channel.id):
            self._bos_baslangic.pop(after.channel.id, None)
        if not odb.aktif_mi(guild.id) or member.bot or after.channel is None:
            return
        ayar = odb.ayar_al(guild.id)
        if after.channel.id == ayar['hub_id']:
            self._arka_gorev(self._hub_katilimi(member))

    def _ayrilma(self, kanal, member):
        if _insanlar(kanal):
            oda = odb.oda_al(kanal.id)
            if (oda and member.id == oda['sahip_id'] and not member.bot and odb.aktif_mi(kanal.guild.id)
                    and time.monotonic() - self._sahip_bildirim.get(kanal.id, -1e9) >= SAHIP_BILDIRIM_ARALIGI):
                self._sahip_bildirim[kanal.id] = time.monotonic()
                self._arka_gorev(self._kanala_yaz(
                    kanal, "👑 Oda sahibi ayrıldı. Odadaki biri **🙋 Sahiplen** butonu ya da `/oda sahiplen` ile "
                           "odayı devralabilir (sahip geri dönerse sahip olmaya devam eder)."))
        else:
            self._bos_baslangic.setdefault(kanal.id, time.monotonic())

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, kanal):
        if odb.oda_sil(kanal.id):
            self._kanal_durumunu_unut(kanal.id)
            return
        ayar = odb.ayar_al(kanal.guild.id)
        if not ayar or not ayar['aktif']:
            return
        if kanal.id in (ayar['kategori_id'], ayar['hub_id'], ayar['panel_kanal_id']):
            logger.warning(f"🔊 [{kanal.guild.id}] Özel oda kurulum kanalı silindi ({kanal.name}) → onarılacak")
            self._onarim_zamanla(kanal.guild)

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload):
        if payload.guild_id is None:
            return
        ayar = odb.ayar_al(payload.guild_id)
        if ayar and ayar['aktif'] and payload.message_id == ayar['panel_mesaj_id']:
            guild = self.bot.get_guild(payload.guild_id)
            if guild is not None:
                self._onarim_zamanla(guild)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        odb.sunucu_odalarini_unut(guild.id)

    def _kanal_durumunu_unut(self, kanal_id):
        for sozluk in (self._bos_baslangic, self._ad_degisimleri, self._sahip_bildirim):
            sozluk.pop(kanal_id, None)

    # ── Boş oda temizliği ─────────────────────────

    @tasks.loop(seconds=TEMIZLIK_ARALIGI)
    async def temizlik_dongusu(self):
        simdi = time.monotonic()
        for oda in odb.tum_odalar():
            kid = oda['kanal_id']
            if kid in self._siliniyor:
                continue
            guild = self.bot.get_guild(oda['sunucu_id'])
            if guild is None or guild.unavailable:
                continue
            kanal = guild.get_channel(kid)
            if kanal is None:
                odb.oda_sil(kid)
                self._kanal_durumunu_unut(kid)
                continue
            ayar = odb.ayar_al(guild.id) or odb.VARSAYILAN_AYARLAR
            karar = temizlik_karari(len(_insanlar(kanal)), self._bos_baslangic.get(kid), simdi,
                                    ayar['bos_silme_suresi'])
            if karar == 'tut':
                self._bos_baslangic.pop(kid, None)
            elif karar == 'zamanla':
                self._bos_baslangic[kid] = simdi
            elif karar == 'sil':
                self._arka_gorev(self._odayi_sil(kanal, f"Özel oda {ayar['bos_silme_suresi']} sn boş kaldı"))
        # Kapatılmış sunucular: son bekleyen oda da gidince kategoriyi kaldır
        for sid in odb.kayitli_sunucular():
            ayar = odb.ayar_al(sid)
            if ayar['aktif'] or not ayar['kategori_id'] or odb.sunucu_odalari(sid):
                continue
            guild = self.bot.get_guild(sid)
            if guild is not None and not guild.unavailable:
                self._arka_gorev(self._kategoriyi_kaldir(guild))

    @temizlik_dongusu.before_loop
    async def _temizlik_once(self):
        await self.bot.wait_until_ready()

    @temizlik_dongusu.error
    async def _temizlik_hata(self, error):
        logger.error(f"Özel oda temizlik döngüsü hatası: {error!r}", exc_info=error)

    async def _odayi_sil(self, kanal, sebep):
        """Odayı siler ve kaydını unutur. Başarılıysa (ya da kanal zaten yoksa) True."""
        if kanal.id in self._siliniyor:
            return False
        self._siliniyor.add(kanal.id)
        try:
            await _api(kanal.delete(reason=sebep))
        except discord.NotFound:
            pass
        except discord.Forbidden:
            logger.warning(f"🔊 [{kanal.guild.id}] Oda silinemedi (yetki yok): {kanal.id} — 10 dk sonra tekrar denenecek")
            self._bos_baslangic[kanal.id] = time.monotonic() + 600
            return False
        except (discord.HTTPException, asyncio.TimeoutError) as e:
            logger.warning(f"🔊 [{kanal.guild.id}] Oda silinemedi ({kanal.id}): {e!r} — tekrar denenecek")
            self._bos_baslangic[kanal.id] = time.monotonic()
            return False
        finally:
            self._siliniyor.discard(kanal.id)
        odb.oda_sil(kanal.id)
        self._kanal_durumunu_unut(kanal.id)
        logger.info(f"🔊 [{kanal.guild.id}] Oda silindi: {kanal.id} ({sebep})")
        return True

    async def _kategoriyi_kaldir(self, guild):
        """Kapatılmış sunucuda: kategori boşsa siler; içinde başka kanal varsa dokunmaz. Kaydı temizler."""
        ayar = odb.ayar_al(guild.id)
        if not ayar or ayar['aktif'] or not ayar['kategori_id']:
            return
        kategori = guild.get_channel(ayar['kategori_id'])
        odb.ayar_guncelle(guild.id, kategori_id=None)
        if isinstance(kategori, discord.CategoryChannel):
            if kategori.channels:
                logger.info(f"🔊 [{guild.id}] Kategori boş değil, silinmedi: {kategori.name}")
                return
            try:
                await _api(kategori.delete(reason="Özel oda sistemi kapatıldı"))
            except (discord.HTTPException, asyncio.TimeoutError) as e:
                logger.warning(f"🔊 [{guild.id}] Kategori silinemedi: {e!r}")

    # ── Genel yardımcılar ─────────────────────────

    async def _kanala_yaz(self, kanal, metin=None, embed=None, view=None, bahset=None, sil=None):
        """Kanala mesaj (ses kanalı sohbeti dahil). Sadece `bahset` (Member) etiketlenir. Hata → None."""
        kw = {'content': metin, 'allowed_mentions': (discord.AllowedMentions(users=list(bahset), everyone=False, roles=False)
                                                     if bahset else discord.AllowedMentions.none())}
        if embed is not None:
            kw['embed'] = embed
        if view is not None:
            kw['view'] = view
        if sil:
            kw['delete_after'] = sil
        try:
            return await _api(kanal.send(**kw))
        except (discord.HTTPException, asyncio.TimeoutError) as e:
            logger.debug(f"🔊 Mesaj gönderilemedi ({getattr(kanal, 'id', '?')}): {e!r}")
            return None

    def _yetkili_mi(self, uye, oda):
        return uye.id == oda['sahip_id'] or yonetici_mi(uye)

    def _gecerli_odalar(self, guild, kullanici_id):
        """Kullanıcının hâlâ var olan odaları (eskiden yeniye); kanalı silinmiş kayıtlar unutulur."""
        sonuc = []
        for oda in odb.sahibin_odalari(guild.id, kullanici_id):
            kanal = guild.get_channel(oda['kanal_id'])
            if kanal is None:
                odb.oda_sil(oda['kanal_id'])
                self._kanal_durumunu_unut(oda['kanal_id'])
            else:
                sonuc.append(kanal)
        return sonuc

    @staticmethod
    def _durum(kanal):
        """(kilitli, gizli) — kanalın @everyone izninden okunur (Discord'daki gerçek durum)."""
        ow = kanal.overwrites_for(kanal.guild.default_role)
        return ow.connect is False, ow.view_channel is False

    def _oda_ve_yetki(self, kanal_id, kullanici, sahip_gerekli=True):
        """→ (kanal, oda). Sistem kapalıysa / oda yoksa / yetki yoksa OdaHatasi."""
        guild = kullanici.guild
        if not odb.aktif_mi(guild.id):
            raise OdaHatasi(KAPALI_MESAJI)
        oda = odb.oda_al(kanal_id)
        kanal = guild.get_channel(kanal_id) if oda else None
        if oda is None or kanal is None or oda['sunucu_id'] != guild.id:
            raise OdaHatasi("Bu oda artık yok.")
        if sahip_gerekli and not self._yetkili_mi(kullanici, oda):
            raise OdaHatasi(f"Bunu sadece oda sahibi (<@{oda['sahip_id']}>) ya da sunucu yöneticileri yapabilir.")
        return kanal, oda

    def _yoneticilere_bildir(self, guild, metin):
        """Kurulum sorununu yöneticilere söyler (panel kanalı → sistem kanalı), sunucu başına 6 saatte bir."""
        logger.warning(f"🔊 [{guild.id}] {metin}")
        simdi = time.monotonic()
        if simdi - self._yonetici_bildirim.get(guild.id, -1e9) < YONETICI_BILDIRIM_ARALIGI:
            return
        self._yonetici_bildirim[guild.id] = simdi
        ayar = odb.ayar_al(guild.id) or {}
        for kanal in (guild.get_channel(ayar.get('panel_kanal_id') or 0), guild.system_channel):
            if isinstance(kanal, discord.TextChannel) and kanal.permissions_for(guild.me).send_messages:
                self._arka_gorev(self._kanala_yaz(kanal, f"⚠️ **Özel oda sistemi (yöneticiler için):** {metin}"))
                return

    # ── Kurulum / onarım ──────────────────────────

    def _baska_sistemler(self, guild):
        """Başka bir botun özel oda sistemine benzeyen kanallar (ör. '🔊 ÖZEL ODALAR', '➕özel-oda-kur')."""
        ayar = odb.ayar_al(guild.id) or {}
        bizim = {ayar.get('kategori_id'), ayar.get('hub_id'), ayar.get('panel_kanal_id')}
        sonuc = []
        for k in guild.channels:
            ad = k.name.casefold()
            if k.id in bizim or k.name in (KATEGORI_ADI, HUB_ADI) or PANEL_KANAL_ANAHTARI in ad:
                continue
            if any(s in ad for s in ("özel oda", "ozel oda", "özel-oda", "ozel-oda", "private room")):
                sonuc.append(k.name)
        return sonuc[:5]

    def _kurulum_paneli_embedi(self, guild):
        ayar = odb.ayar_al(guild.id) or odb.VARSAYILAN_AYARLAR
        hub = guild.get_channel(ayar.get('hub_id') or 0)
        e = discord.Embed(title="🔊 Özel Ses Odaları", color=Renkler.BILGI)
        e.description = (
            f"Kendine ait bir ses odası aç, istediğin kişileri çağır!\n{AYIRICI}\n"
            f"**1.** {hub.mention if hub else f'**{HUB_ADI}**'} ses kanalına gir → odan açılır ve oraya taşınırsın.\n"
            "**2.** Odanın **sohbet** sekmesindeki panelden kilitle, gizle, limit koy, davet et, at…\n"
            "**3.** Herkes çıkınca oda kendiliğinden silinir.\n"
            f"{AYIRICI}\n"
            "Aşağıdaki butonlarla da oda açabilir, odanı yönetebilirsin. Komutlar: `/oda` "
        )
        limit = ayar['varsayilan_limit']
        e.add_field(name="👥 Varsayılan limit", value="Sınırsız" if not limit else f"{limit} kişi", inline=True)
        e.add_field(name="⏱️ Boş oda silinir", value=f"{ayar['bos_silme_suresi']} sn sonra", inline=True)
        e.add_field(name="🏠 Kişi başı", value=f"{ayar['kisi_basi_oda']} oda", inline=True)
        e.set_footer(text="MezarBot • Özel Odalar")
        return e

    async def _kurulumu_onar(self, guild, sebep):
        """İdempotent kurulum/onarım: kategori, hub ve panel kanalını (kayıtlı ID → ad → yeni) bulur ya da
        oluşturur, panel mesajını günceller/yeniden gönderir, ID'leri kaydeder. `aktif`e DOKUNMAZ.
        → dict(rapor=[satır], zorunlu=[eksik izin], onerilen=[eksik izin], hata=str|None)"""
        sonuc = {'rapor': [], 'zorunlu': [], 'onerilen': [], 'hata': None}
        me = guild.me
        sonuc['zorunlu'], sonuc['onerilen'] = eksik_izinler(me.guild_permissions)
        if sonuc['zorunlu']:
            sonuc['hata'] = "Botun sunucu yetkileri eksik."
            return sonuc
        ayar = odb.ayar_al(guild.id) or {}
        neden = f"Özel oda kurulumu ({sebep})"
        try:
            # 1) Kategori — kanal listesinin en altında
            kategori = guild.get_channel(ayar.get('kategori_id') or 0)
            if not isinstance(kategori, discord.CategoryChannel):
                kategori = discord.utils.get(guild.categories, name=KATEGORI_ADI)
                if kategori is not None:
                    sonuc['rapor'].append(f"♻️ Var olan kategori kullanıldı: **{KATEGORI_ADI}**")
                else:
                    en_alt = max((c.position for c in guild.categories), default=-1) + 1
                    kategori = await _api(guild.create_category(
                        KATEGORI_ADI, overwrites={me: bot_izni()}, position=en_alt, reason=neden))
                    sonuc['rapor'].append(f"✅ Kategori oluşturuldu: **{KATEGORI_ADI}** (listenin en altında)")
            eksik_kat, _ = eksik_izinler(kategori.permissions_for(me))
            if eksik_kat:
                sonuc['zorunlu'] = eksik_kat
                sonuc['hata'] = f"Botun **{kategori.name}** kategorisindeki yetkileri eksik (kategori izinlerini kontrol et)."
                odb.ayar_guncelle(guild.id, kategori_id=kategori.id)
                return sonuc

            # 2) Hub (katıl → oda oluştur)
            hub = guild.get_channel(ayar.get('hub_id') or 0)
            if not isinstance(hub, discord.VoiceChannel):
                hub = discord.utils.get(kategori.voice_channels, name=HUB_ADI)
                if hub is not None:
                    sonuc['rapor'].append(f"♻️ Var olan kanal kullanıldı: {hub.mention}")
                else:
                    hub = await _api(kategori.create_voice_channel(HUB_ADI, reason=neden))
                    sonuc['rapor'].append(f"✅ Ses kanalı oluşturuldu: {hub.mention}")

            # 3) Panel metin kanalı (üyeler yazamaz, sadece butonlar)
            panel_kanal = guild.get_channel(ayar.get('panel_kanal_id') or 0)
            if not isinstance(panel_kanal, discord.TextChannel):
                panel_kanal = next((k for k in kategori.text_channels if PANEL_KANAL_ANAHTARI in k.name), None)
                if panel_kanal is not None:
                    sonuc['rapor'].append(f"♻️ Var olan panel kanalı kullanıldı: {panel_kanal.mention}")
                else:
                    izinler = dict(kategori.overwrites)
                    herkes = discord.PermissionOverwrite(**dict(izinler.get(guild.default_role, discord.PermissionOverwrite())))
                    herkes.update(send_messages=False, add_reactions=False, create_public_threads=False,
                                  create_private_threads=False)
                    izinler[guild.default_role] = herkes
                    izinler[me] = bot_izni()
                    panel_kanal = await _api(kategori.create_text_channel(
                        PANEL_KANAL_ADI, overwrites=izinler, reason=neden,
                        topic=f"Özel ses odası paneli — {HUB_ADI} kanalına gir ya da aşağıdaki butonları kullan."))
                    sonuc['rapor'].append(f"✅ Panel kanalı oluşturuldu: {panel_kanal.mention}")
            odb.ayar_guncelle(guild.id, kategori_id=kategori.id, hub_id=hub.id, panel_kanal_id=panel_kanal.id)

            # 4) Panel mesajı (varsa düzenle, yoksa gönder)
            embed, gorunum = self._kurulum_paneli_embedi(guild), KurulumPaneli()
            mesaj_id = ayar.get('panel_mesaj_id')
            mesaj = None
            if mesaj_id and ayar.get('panel_kanal_id') == panel_kanal.id:
                try:
                    mesaj = await _api(panel_kanal.get_partial_message(mesaj_id).edit(embed=embed, view=gorunum))
                except discord.NotFound:
                    mesaj = None
            if mesaj is None:
                mesaj = await _api(panel_kanal.send(embed=embed, view=gorunum))
                sonuc['rapor'].append("✅ Panel mesajı gönderildi")
            odb.ayar_guncelle(guild.id, panel_mesaj_id=mesaj.id)
        except discord.Forbidden as e:
            sonuc['hata'] = f"Discord işlemi reddetti (yetki yok): {e.text or e}"
        except (discord.HTTPException, asyncio.TimeoutError) as e:
            sonuc['hata'] = f"Discord hatası: {e!r}"
        if sonuc['hata']:
            logger.warning(f"🔊 [{guild.id}] Kurulum/onarım tamamlanamadı ({sebep}): {sonuc['hata']}")
        return sonuc

    def _onarim_zamanla(self, guild):
        """Kurulum kanalı/mesajı silindiğinde 5 sn sonra TEK onarım (toplu silmelerde tekrar tekrar değil)."""
        eski = self._onarim_gorevleri.get(guild.id)
        if eski is not None and not eski.done():
            return

        async def _onar():
            await asyncio.sleep(5)
            if not odb.aktif_mi(guild.id):
                return
            sonuc = await self._kurulumu_onar(guild, "silinen kanal/mesaj")
            if sonuc['hata']:
                eksik = f" Eksik yetkiler: {', '.join(sonuc['zorunlu'])}." if sonuc['zorunlu'] else ""
                self._yoneticilere_bildir(guild, f"Kurulum onarılamadı: {sonuc['hata']}{eksik} "
                                                 "Düzeltip `/ozelodaaktif` komutunu tekrar çalıştırın.")
            elif sonuc['rapor']:
                logger.info(f"🔊 [{guild.id}] Kurulum onarıldı: {'; '.join(sonuc['rapor'])}")

        self._onarim_gorevleri[guild.id] = self._arka_gorev(_onar())

    async def _devre_disi_birak(self, guild):
        """Sistemi kapatır. → (silinen_oda, bekleyen_oda, hatalar). Önce kayıt kapatılır (silme olayları onarım
        tetiklemesin), sonra hub + panel kanalı, boş odalar ve (bekleyen oda yoksa) kategori silinir."""
        ayar = odb.ayar_al(guild.id) or {}
        odb.ayar_guncelle(guild.id, aktif=0, hub_id=None, panel_kanal_id=None, panel_mesaj_id=None)
        gorev = self._onarim_gorevleri.pop(guild.id, None)
        if gorev is not None:
            gorev.cancel()
        hatalar = []
        for kid in (ayar.get('hub_id'), ayar.get('panel_kanal_id')):
            kanal = guild.get_channel(kid or 0)
            if kanal is None:
                continue
            try:
                await _api(kanal.delete(reason="Özel oda sistemi kapatıldı"))
            except discord.NotFound:
                pass
            except (discord.HTTPException, asyncio.TimeoutError) as e:
                hatalar.append(f"{kanal.name} silinemedi ({e.__class__.__name__})")
        silinen = bekleyen = 0
        for oda in odb.sunucu_odalari(guild.id):
            kanal = guild.get_channel(oda['kanal_id'])
            if kanal is None:
                odb.oda_sil(oda['kanal_id'])
            elif not _insanlar(kanal):
                if await self._odayi_sil(kanal, "Özel oda sistemi kapatıldı"):
                    silinen += 1
                else:
                    bekleyen += 1
            else:
                bekleyen += 1
                self._arka_gorev(self._kanala_yaz(
                    kanal, "🔕 Özel oda sistemi bu sunucuda kapatıldı. Bu oda herkes çıkınca silinecek."))
        if not odb.sunucu_odalari(guild.id):
            await self._kategoriyi_kaldir(guild)
        logger.info(f"🔊 [{guild.id}] Özel oda sistemi kapatıldı: {silinen} oda silindi, {bekleyen} bekliyor")
        return silinen, bekleyen, hatalar

    # ── Oda oluşturma ─────────────────────────────

    async def _oda_olustur(self, uye, butondan=False):
        """Odayı oluşturur ve kaydeder (taşımaz). → (kanal, None) ya da (None, Türkçe hata)."""
        guild = uye.guild
        ayar = odb.ayar_al(guild.id)
        if not ayar or not ayar['aktif']:
            return None, KAPALI_MESAJI
        kategori = guild.get_channel(ayar['kategori_id'] or 0)
        if not isinstance(kategori, discord.CategoryChannel):
            await self._kurulumu_onar(guild, "oda oluştururken kategori yoktu")
            ayar = odb.ayar_al(guild.id)
            kategori = guild.get_channel(ayar['kategori_id'] or 0)
            if not isinstance(kategori, discord.CategoryChannel):
                self._yoneticilere_bildir(guild, "Özel odalar kategorisi yok ve oluşturulamadı. `/ozelodaaktif` ile onarın.")
                return None, "Özel odalar kategorisi bulunamadı; bir yönetici `/ozelodaaktif` ile onarmalı."
        bot_izinleri = kategori.permissions_for(guild.me)
        eksik, _ = eksik_izinler(bot_izinleri)
        if eksik:
            self._yoneticilere_bildir(guild, f"Oda oluşturulamıyor, botun yetkileri eksik: {', '.join(eksik)}")
            return None, f"Botun yetkileri eksik ({', '.join(eksik)}); yöneticilere haber verildi."
        ad = sablon_uygula(ayar['ad_sablonu'], uye.display_name, len(odb.sunucu_odalari(guild.id)) + 1)
        izinler = dict(kategori.overwrites)
        izinler[guild.me] = bot_izni()
        izinler[uye] = sahip_izni(bot_izinleri)
        try:
            kanal = await _api(guild.create_voice_channel(
                ad, category=kategori, user_limit=ayar['varsayilan_limit'], overwrites=izinler,
                bitrate=int(min(guild.bitrate_limit, 384000)), reason=f"Özel oda: {uye} ({uye.id})"))
        except discord.Forbidden as e:
            self._yoneticilere_bildir(guild, f"Oda oluşturulamadı (yetki yok): {e.text or e}")
            return None, "Discord oda oluşturmama izin vermedi; yöneticilere haber verildi."
        except (discord.HTTPException, asyncio.TimeoutError) as e:
            logger.warning(f"🔊 [{guild.id}] Oda oluşturulamadı: {e!r}")
            return None, "Oda şu an oluşturulamadı (Discord hatası / hız sınırı). Biraz sonra tekrar dene."
        odb.oda_ekle(guild.id, kanal.id, uye.id)
        simdi = time.monotonic()
        self._son_olusturma[(guild.id, uye.id)] = simdi
        self._bos_baslangic[kanal.id] = simdi + (BUTON_ODA_EK_SURE if butondan else 0)
        logger.info(f"🔊 [{guild.id}] Oda oluşturuldu: {kanal.id} sahibi {uye.id}")
        return kanal, None

    async def _paneli_gonder(self, kanal, sahip):
        """Kontrol panelini odanın ses kanalı sohbetine gönderir ve mesaj ID'sini kaydeder."""
        oda = odb.oda_al(kanal.id)
        if oda is None:
            return None
        kilitli, gizli = self._durum(kanal)
        mesaj = await self._kanala_yaz(kanal, sahip.mention if sahip else None, embed=self._panel_embedi(kanal, oda),
                                       view=oda_paneli_gorunumu(kanal.id, kilitli, gizli),
                                       bahset=[sahip] if sahip else None)
        if mesaj is not None:
            odb.oda_guncelle(kanal.id, panel_mesaj_id=mesaj.id)
        return mesaj

    def _panel_embedi(self, kanal, oda):
        ayar = odb.ayar_al(kanal.guild.id) or odb.VARSAYILAN_AYARLAR
        kilitli, gizli = self._durum(kanal)
        e = discord.Embed(title="🎛️ Oda Kontrol Paneli", color=Renkler.PREMIUM)
        e.description = (f"{kanal.mention} · sahibi <@{oda['sahip_id']}>\n"
                         "Butonları sadece oda sahibi ve sunucu yöneticileri kullanabilir; yanıtlar sadece sana görünür.")
        e.add_field(name="🔐 Erişim", value="🔒 Kilitli" if kilitli else "🔓 Herkese açık", inline=True)
        e.add_field(name="👁️ Görünürlük", value="🙈 Gizli" if gizli else "👁️ Görünür", inline=True)
        e.add_field(name="👥 Limit", value="Sınırsız" if not kanal.user_limit else f"{kanal.user_limit} kişi", inline=True)
        e.add_field(name="ℹ️ Nasıl?", inline=False, value=(
            "➕ **Davet** — kilitli/gizli odana girebilsin · 🚫 **At** — sesten düşür, tekrar giremesin\n"
            "👑 **Devret** — sahipliği ver · 🙋 **Sahiplen** — sahip odada yoksa devral\n"
            "Komutlar: `/oda bilgi`, `/oda yasakla`, `/oda yasak-kaldir` …"))
        e.set_footer(text=f"Oda {ayar['bos_silme_suresi']} sn boş kalınca otomatik silinir • MezarBot")
        return e

    async def _paneli_guncelle(self, kanal):
        oda = odb.oda_al(kanal.id)
        if not oda or not oda['panel_mesaj_id']:
            return
        kilitli, gizli = self._durum(kanal)
        try:
            await _api(kanal.get_partial_message(oda['panel_mesaj_id']).edit(
                embed=self._panel_embedi(kanal, oda), view=oda_paneli_gorunumu(kanal.id, kilitli, gizli)))
        except discord.NotFound:
            odb.oda_guncelle(kanal.id, panel_mesaj_id=None)
        except (discord.HTTPException, asyncio.TimeoutError) as e:
            logger.debug(f"🔊 Panel güncellenemedi ({kanal.id}): {e!r}")

    async def _tasi(self, uye, kanal, hub=None):
        try:
            await _api(uye.move_to(kanal, reason="Özel oda"))
            return True
        except (discord.HTTPException, asyncio.TimeoutError) as e:
            logger.info(f"🔊 [{uye.guild.id}] {uye.id} odaya taşınamadı: {e!r}")
            if hub is not None and isinstance(e, discord.Forbidden):
                await self._kanala_yaz(hub, f"⚠️ {uye.mention}, seni {kanal.mention} odasına taşıyamadım — kendin gir.",
                                       bahset=[uye], sil=20)
            return False

    async def _hub_katilimi(self, uye):
        """Üye hub'a girdi: sınırdaysa var olan odasına taşı, değilse (bekleme süresi dolunca) oda aç ve taşı."""
        guild = uye.guild
        anahtar = (guild.id, uye.id)
        if anahtar in self._hub_islemde:
            return
        self._hub_islemde.add(anahtar)
        try:
            ayar = odb.ayar_al(guild.id)
            if not ayar or not ayar['aktif']:
                return
            hub = guild.get_channel(ayar['hub_id'] or 0)
            mevcut = self._gecerli_odalar(guild, uye.id)
            if len(mevcut) >= ayar['kisi_basi_oda']:
                await self._tasi(uye, mevcut[-1], hub)
                return
            kalan = bekleme_kalan(self._son_olusturma.get(anahtar), time.monotonic())
            if kalan > 0:
                if hub is not None:
                    await self._kanala_yaz(hub, f"⏳ {uye.mention}, yeni oda için **{int(kalan) + 1} sn** bekle — "
                                                "süre dolunca otomatik taşınacaksın.", bahset=[uye], sil=kalan + 3)
                await asyncio.sleep(kalan)
                guncel = guild.get_member(uye.id)
                if (guncel is None or guncel.voice is None or guncel.voice.channel is None
                        or guncel.voice.channel.id != ayar['hub_id'] or not odb.aktif_mi(guild.id)):
                    return
                uye = guncel
            kanal, hata = await self._oda_olustur(uye)
            if kanal is None:
                if hub is not None:
                    await self._kanala_yaz(hub, f"⚠️ {uye.mention} {hata}", bahset=[uye], sil=20)
                return
            if not await self._tasi(uye, kanal):
                # Üye taşınmadan sesten ayrıldı (ya da taşınamadı): boş odayı hemen kaldır
                await self._odayi_sil(kanal, "Özel oda: sahip taşınamadı / sesten ayrıldı")
                return
            await self._paneli_gonder(kanal, uye)
        finally:
            self._hub_islemde.discard(anahtar)

    # ── Oda eylemleri (komutlar ve butonlar ortak kullanır; hata → OdaHatasi) ──

    async def _rol_izinleri(self, kanal, izin, reddet, sebep):
        """reddet=True: kanaldaki TÜM rol izinlerinde (@everyone dahil) `izin` reddedilir; False: rol izinleri
        kategorinin haline döner. Üye bazlı izinler (sahip, davetliler, bot) etkilenmez → onlar girmeye devam eder.
        Tek API çağrısı (kanal.edit(overwrites=...))."""
        yeni = dict(kanal.overwrites)
        roller = {h for h in yeni if isinstance(h, discord.Role)
                  or (isinstance(h, discord.Object) and h.type is discord.Role)}
        roller.add(kanal.guild.default_role)
        for rol in roller:
            ow = discord.PermissionOverwrite(**dict(yeni.get(rol, discord.PermissionOverwrite())))
            if reddet:
                setattr(ow, izin, False)
            else:
                kat = kanal.category.overwrites_for(rol) if kanal.category else discord.PermissionOverwrite()
                setattr(ow, izin, getattr(kat, izin))
            if ow.is_empty():
                yeni.pop(rol, None)
            else:
                yeni[rol] = ow
        await _api(kanal.edit(overwrites=yeni, reason=sebep))

    async def eylem_kilit(self, kanal, yapan, kilitle=None):
        kilitli, _ = self._durum(kanal)
        kilitle = (not kilitli) if kilitle is None else kilitle
        if kilitle == kilitli:
            return "🔒 Oda zaten kilitli." if kilitli else "🔓 Oda zaten açık."
        await self._rol_izinleri(kanal, "connect", kilitle, f"Özel oda {'kilitlendi' if kilitle else 'açıldı'}: {yapan.id}")
        odb.oda_guncelle(kanal.id, kilitli=int(kilitle))
        await self._paneli_guncelle(kanal)
        return ("🔒 Oda kilitlendi — sadece davet ettiklerin girebilir (içeridekiler kalır)." if kilitle
                else "🔓 Oda herkese açıldı.")

    async def eylem_gizlilik(self, kanal, yapan, gizle=None):
        _, gizli = self._durum(kanal)
        gizle = (not gizli) if gizle is None else gizle
        if gizle == gizli:
            return "🙈 Oda zaten gizli." if gizli else "👁️ Oda zaten görünür."
        ayar = odb.ayar_al(kanal.guild.id) or odb.VARSAYILAN_AYARLAR
        if gizle and not ayar['gizlemeye_izin'] and not yonetici_mi(yapan):
            raise OdaHatasi("Bu sunucuda odaları gizlemek yöneticiler tarafından kapatılmış.")
        await self._rol_izinleri(kanal, "view_channel", gizle, f"Özel oda {'gizlendi' if gizle else 'gösterildi'}: {yapan.id}")
        odb.oda_guncelle(kanal.id, gizli=int(gizle))
        await self._paneli_guncelle(kanal)
        return ("🙈 Oda gizlendi — sadece davetliler görebilir." if gizle else "👁️ Oda artık herkese görünüyor.")

    async def eylem_limit(self, kanal, yapan, deger):
        try:
            limit = limit_dogrula(deger)
        except ValueError as e:
            raise OdaHatasi(str(e)) from None
        await _api(kanal.edit(user_limit=limit, reason=f"Özel oda limiti: {yapan.id}"))
        await self._paneli_guncelle(kanal)
        return "👥 Limit kaldırıldı (sınırsız)." if limit == 0 else f"👥 Limit **{limit} kişi** yapıldı."

    async def eylem_ad(self, kanal, yapan, metin):
        try:
            ad = ad_dogrula(metin)
        except ValueError as e:
            raise OdaHatasi(str(e)) from None
        if ad == kanal.name:
            return "✏️ Oda zaten bu adda."
        simdi = time.monotonic()
        zamanlar = self._ad_degisimleri.setdefault(kanal.id, [])
        kalan = ad_degisim_kalan(zamanlar, simdi)
        if kalan > 0:
            raise OdaHatasi(f"Discord bir kanalın adının 10 dakikada en fazla {AD_DEGISIM_HAKKI} kez değişmesine izin "
                            f"veriyor. **{int(kalan // 60)} dk {int(kalan % 60)} sn** sonra tekrar dene.")
        try:
            await _api(kanal.edit(name=ad, reason=f"Özel oda adı: {yapan.id}"), zaman_asimi=8)
        except asyncio.TimeoutError:
            raise OdaHatasi("Discord şu an ad değişikliğine izin vermiyor (hız sınırı). Birkaç dakika sonra dene.") from None
        zamanlar[:] = [z for z in zamanlar if simdi - z < AD_DEGISIM_PENCERESI] + [simdi]
        await self._paneli_guncelle(kanal)
        return f"✏️ Oda adı **{escape_markdown(ad)}** yapıldı."

    def _hedef_uyeler(self, guild, secilenler):
        """Seçim menüsünden gelen User/Member → sunucudaki Member listesi (botlar hariç)."""
        sonuc = []
        for u in secilenler:
            uye = u if isinstance(u, discord.Member) else guild.get_member(u.id)
            if uye is not None and not uye.bot and uye not in sonuc:
                sonuc.append(uye)
        return sonuc

    async def eylem_davet(self, kanal, yapan, secilenler):
        oda = odb.oda_al(kanal.id)
        uyeler = [u for u in self._hedef_uyeler(kanal.guild, secilenler) if u.id != oda['sahip_id']]
        if not uyeler:
            raise OdaHatasi("Davet edilecek geçerli bir üye seçmedin (botlar ve oda sahibi hariç).")
        eklenen = []
        for uye in uyeler:
            try:
                await _api(kanal.set_permissions(uye, overwrite=uye_izni(), reason=f"Özel oda daveti: {yapan.id}"))
                eklenen.append(uye)
            except (discord.HTTPException, asyncio.TimeoutError) as e:
                logger.info(f"🔊 Davet izni verilemedi ({kanal.id} → {uye.id}): {e!r}")
        if not eklenen:
            raise OdaHatasi("Kimse davet edilemedi (Discord hatası).")
        await self._kanala_yaz(kanal, f"🔔 {' '.join(u.mention for u in eklenen)} — {yapan.mention} seni bu odaya "
                                      f"davet etti! Girmek için 👉 {kanal.mention}", bahset=eklenen)
        return f"➕ Davet edildi: {' '.join(u.mention for u in eklenen)}"

    async def eylem_at(self, kanal, yapan, secilenler, yasakla=False):
        oda = odb.oda_al(kanal.id)
        atilan, atlanan = [], []
        for uye in self._hedef_uyeler(kanal.guild, secilenler):
            if uye.id in (oda['sahip_id'], yapan.id) or yonetici_mi(uye):
                atlanan.append(uye)
                continue
            ow = discord.PermissionOverwrite(connect=False, view_channel=False if yasakla else None)
            try:
                await _api(kanal.set_permissions(uye, overwrite=ow,
                                                 reason=f"Özel oda {'yasağı' if yasakla else 'atma'}: {yapan.id}"))
                if uye.voice is not None and uye.voice.channel == kanal:
                    await _api(uye.move_to(None, reason="Özel odadan atıldı"))
                atilan.append(uye)
            except (discord.HTTPException, asyncio.TimeoutError) as e:
                logger.info(f"🔊 Atılamadı ({kanal.id} → {uye.id}): {e!r}")
        if not atilan:
            raise OdaHatasi("Kimse atılamadı" + (" (oda sahibi, sen ve sunucu yöneticileri atılamaz)." if atlanan else "."))
        ek = f"\n-# Atlananlar (sahip / yönetici): {' '.join(u.mention for u in atlanan)}" if atlanan else ""
        if yasakla:
            return f"⛔ Yasaklandı (odayı göremez, giremez): {' '.join(u.mention for u in atilan)}{ek}"
        return f"🚫 Atıldı (tekrar giremez; `/oda davet` ile geri alınır): {' '.join(u.mention for u in atilan)}{ek}"

    async def eylem_yasak_kaldir(self, kanal, yapan, uye):
        ow = kanal.overwrites_for(uye)
        if ow.connect is not False and ow.view_channel is not False:
            raise OdaHatasi(f"{uye.mention} bu odada yasaklı / atılmış değil.")
        await _api(kanal.set_permissions(uye, overwrite=None, reason=f"Özel oda yasağı kaldırıldı: {yapan.id}"))
        return f"✅ {uye.mention} için yasak kaldırıldı."

    async def eylem_devret(self, kanal, yapan, yeni):
        guild = kanal.guild
        oda = odb.oda_al(kanal.id)
        yeni = yeni if isinstance(yeni, discord.Member) else guild.get_member(yeni.id)
        if yeni is None or yeni.bot:
            raise OdaHatasi("Sahipliği sadece sunucudaki bir üyeye (bot olmayan) devredebilirsin.")
        if yeni.id == oda['sahip_id']:
            raise OdaHatasi(f"{yeni.mention} zaten bu odanın sahibi.")
        ayar = odb.ayar_al(guild.id) or odb.VARSAYILAN_AYARLAR
        if len(self._gecerli_odalar(guild, yeni.id)) >= ayar['kisi_basi_oda']:
            raise OdaHatasi(f"{yeni.mention} zaten en fazla oda sayısına ({ayar['kisi_basi_oda']}) sahip.")
        yeni_izinler = dict(kanal.overwrites)
        eski = guild.get_member(oda['sahip_id'])
        for hedef in [h for h in yeni_izinler if h.id == oda['sahip_id']]:
            yeni_izinler.pop(hedef)
        if eski is not None:
            yeni_izinler[eski] = uye_izni()     # eski sahip odaya girebilmeye devam eder, yönetemez
        yeni_izinler[yeni] = sahip_izni(kanal.permissions_for(guild.me))
        await _api(kanal.edit(overwrites=yeni_izinler, reason=f"Özel oda devri: {oda['sahip_id']} → {yeni.id} ({yapan.id})"))
        odb.oda_guncelle(kanal.id, sahip_id=yeni.id)
        await self._paneli_guncelle(kanal)
        await self._kanala_yaz(kanal, f"👑 Bu odanın yeni sahibi: {yeni.mention}", bahset=[yeni])
        return f"👑 Oda sahipliği {yeni.mention} kişisine geçti."

    async def eylem_sahiplen(self, kanal, uye):
        oda = odb.oda_al(kanal.id)
        if uye.id == oda['sahip_id']:
            raise OdaHatasi("Bu oda zaten senin.")
        if uye.voice is None or uye.voice.channel != kanal:
            raise OdaHatasi("Sahiplenmek için odanın içinde (seste) olmalısın.")
        sahip = kanal.guild.get_member(oda['sahip_id'])
        if sahip is not None and sahip.voice is not None and sahip.voice.channel == kanal:
            raise OdaHatasi(f"Oda sahibi ({sahip.mention}) hâlâ odada; ancak o devredebilir.")
        return await self.eylem_devret(kanal, uye, uye)

    def bilgi_embedi(self, kanal, oda):
        kilitli, gizli = self._durum(kanal)
        davetli, yasakli = [], []
        for hedef, ow in kanal.overwrites.items():
            if isinstance(hedef, discord.Role) or hedef.id in (oda['sahip_id'], kanal.guild.me.id):
                continue
            if ow.connect is False or ow.view_channel is False:
                yasakli.append(f"<@{hedef.id}>")
            elif ow.connect:
                davetli.append(f"<@{hedef.id}>")
        e = discord.Embed(title=f"🔊 {escape_markdown(kanal.name)}", color=Renkler.BILGI)
        e.add_field(name="👑 Sahip", value=f"<@{oda['sahip_id']}>", inline=True)
        e.add_field(name="🕒 Açıldı", value=f"<t:{int(oda['olusturma'])}:R>", inline=True)
        e.add_field(name="🎧 İçeride", value=f"{len(_insanlar(kanal))} kişi", inline=True)
        e.add_field(name="🔐 Durum", value=f"{'🔒 Kilitli' if kilitli else '🔓 Açık'} · {'🙈 Gizli' if gizli else '👁️ Görünür'}",
                    inline=True)
        e.add_field(name="👥 Limit", value="Sınırsız" if not kanal.user_limit else f"{kanal.user_limit} kişi", inline=True)
        e.add_field(name="➕ Davetliler", value=(" ".join(davetli[:20]) or "—")[:1024], inline=False)
        e.add_field(name="⛔ Atılan / yasaklı", value=(" ".join(yasakli[:20]) or "—")[:1024], inline=False)
        return e

    # ── Etkileşimler (butonlar / modallar / seçimler) ──

    async def _calistir(self, interaction, fabrika):
        """Etkileşimi (gizli) erteler, fabrika()'yı çalıştırır, sonucu ya da Türkçe hatayı gizli yanıtlar."""
        try:
            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=True, thinking=True)
            metin = await fabrika()
        except OdaHatasi as e:
            metin = f"❌ {e}"
        except discord.Forbidden:
            metin = "❌ Botun bu işlem için yetkisi yok (kanal / kategori izinlerini kontrol et)."
        except (discord.HTTPException, asyncio.TimeoutError) as e:
            logger.warning(f"🔊 Etkileşim işlemi başarısız: {e!r}")
            metin = "⚠️ Discord şu an isteği tamamlayamadı, biraz sonra tekrar dene."
        await _gizli_yanit(interaction, metin)

    async def panel_etkilesimi(self, interaction, eylem, kanal_id):
        if interaction.guild is None:
            return
        try:
            kanal, _ = self._oda_ve_yetki(kanal_id, interaction.user, sahip_gerekli=(eylem != "sahiplen"))
        except OdaHatasi as e:
            return await _gizli_yanit(interaction, f"❌ {e}")
        uye = interaction.user
        if eylem == "limit":
            return await interaction.response.send_modal(LimitModali(kanal_id, kanal.user_limit))
        if eylem == "ad":
            return await interaction.response.send_modal(AdModali(kanal_id, kanal.name))
        if eylem in ("davet", "at", "devret"):
            metin = {"davet": "➕ Davet edeceğin üyeleri seç (kilitli/gizli odaya girebilirler):",
                     "at": "🚫 Atılacak üyeleri seç (sesten düşer, tekrar giremez):",
                     "devret": "👑 Yeni oda sahibini seç:"}[eylem]
            return await _gizli_yanit(interaction, metin, view=UyeSecimGorunumu(eylem, kanal_id, uye.id))
        eylemler = {
            "kilit": lambda: self.eylem_kilit(kanal, uye),
            "gizlilik": lambda: self.eylem_gizlilik(kanal, uye),
            "sahiplen": lambda: self.eylem_sahiplen(kanal, uye),
        }
        await self._calistir(interaction, eylemler[eylem])

    async def limit_uygula_etkilesim(self, interaction, kanal_id, deger):
        async def fabrika():
            kanal, _ = self._oda_ve_yetki(kanal_id, interaction.user)
            return await self.eylem_limit(kanal, interaction.user, deger)
        await self._calistir(interaction, fabrika)

    async def ad_uygula_etkilesim(self, interaction, kanal_id, deger):
        async def fabrika():
            kanal, _ = self._oda_ve_yetki(kanal_id, interaction.user)
            return await self.eylem_ad(kanal, interaction.user, deger)
        await self._calistir(interaction, fabrika)

    async def secim_uygula_etkilesim(self, interaction, eylem, kanal_id, secilenler):
        async def fabrika():
            kanal, _ = self._oda_ve_yetki(kanal_id, interaction.user)
            if eylem == "davet":
                return await self.eylem_davet(kanal, interaction.user, secilenler)
            if eylem == "at":
                return await self.eylem_at(kanal, interaction.user, secilenler)
            return await self.eylem_devret(kanal, interaction.user, secilenler[0])
        await self._calistir(interaction, fabrika)

    def _yardim_embedi(self):
        e = discord.Embed(title="❔ Özel Odalar — Yardım", color=Renkler.BILGI)
        e.description = (
            f"**Oda açmak:** **{HUB_ADI}** ses kanalına gir ya da **➕ Oda oluştur** butonuna bas.\n"
            "**Yönetmek:** odanın ses kanalındaki **sohbet** sekmesinde kontrol paneli var; "
            "ya da **🎛️ Odamı yönet** butonu / `/oda` komutları.\n"
            f"{AYIRICI}\n"
            "> `/oda bilgi` · `/oda ad` · `/oda limit`\n"
            "> `/oda kilitle` · `/oda ac` · `/oda gizle` · `/oda goster`\n"
            "> `/oda davet` · `/oda at` · `/oda yasakla` · `/oda yasak-kaldir`\n"
            "> `/oda devret` · `/oda sahiplen` · `/oda panel`\n"
            f"{AYIRICI}\n"
            "• Sahip çıkınca oda korunur; odadaki biri **🙋 Sahiplen** ile devralabilir.\n"
            "• Herkes çıkınca oda kısa süre sonra silinir.\n"
            "• Oda adı Discord kuralı gereği 10 dakikada en fazla 2 kez değişebilir.")
        return e

    async def kurulum_paneli_etkilesimi(self, interaction, eylem):
        if interaction.guild is None:
            return
        if eylem == "yardim":
            return await _gizli_yanit(interaction, embed=self._yardim_embedi())
        if not odb.aktif_mi(interaction.guild.id):
            return await _gizli_yanit(interaction, KAPALI_MESAJI)
        uye = interaction.user
        guild = interaction.guild
        if eylem == "yonet":
            odalar = self._gecerli_odalar(guild, uye.id)
            if not odalar:
                return await _gizli_yanit(interaction, "Henüz bir odan yok. **➕ Oda oluştur** butonuna bas ya da "
                                                       f"**{HUB_ADI}** ses kanalına gir.")
            simdiki = uye.voice.channel if uye.voice else None
            kanal = simdiki if simdiki in odalar else odalar[-1]
            kilitli, gizli = self._durum(kanal)
            return await _gizli_yanit(interaction, embed=self.bilgi_embedi(kanal, odb.oda_al(kanal.id)),
                                      view=oda_paneli_gorunumu(kanal.id, kilitli, gizli))

        async def olustur():
            ayar = odb.ayar_al(guild.id)
            odalar = self._gecerli_odalar(guild, uye.id)
            if len(odalar) >= ayar['kisi_basi_oda']:
                if uye.voice is not None and uye.voice.channel not in odalar:
                    await self._tasi(uye, odalar[-1])
                return f"Zaten bir odan var 👉 {odalar[-1].mention}"
            kalan = bekleme_kalan(self._son_olusturma.get((guild.id, uye.id)), time.monotonic())
            if kalan > 0:
                raise OdaHatasi(f"Yeni oda için **{int(kalan) + 1} sn** bekle.")
            seste = uye.voice is not None and uye.voice.channel is not None
            kanal, hata = await self._oda_olustur(uye, butondan=not seste)
            if kanal is None:
                raise OdaHatasi(hata)
            tasindi = seste and await self._tasi(uye, kanal)
            await self._paneli_gonder(kanal, uye)
            if tasindi:
                return f"✅ Odan hazır, seni taşıdım 👉 {kanal.mention}"
            return (f"✅ Odan hazır 👉 {kanal.mention}\nİçine gir; kimse girmezse "
                    f"{BUTON_ODA_EK_SURE // 60} dakika sonra kendiliğinden silinir.")
        await self._calistir(interaction, olustur)

    # ── Komut yardımcıları ────────────────────────

    async def _yanit(self, ctx, metin=None, embed=None, view=None, sure=20):
        kw = {'content': metin, 'allowed_mentions': discord.AllowedMentions.none()}
        if embed is not None:
            kw['embed'] = embed
        if view is not None:
            kw['view'] = view
        if ctx.interaction is not None:
            kw['ephemeral'] = True
        elif sure:
            kw['delete_after'] = sure
        try:
            return await ctx.send(**kw)
        except discord.HTTPException as e:
            logger.debug(f"🔊 Yanıt gönderilemedi: {e}")
            return None

    def _komut_odasi(self, ctx, sahip_gerekli=True):
        """Komutun hedef odası: komutun yazıldığı oda sohbeti → yazanın bulunduğu oda → yazanın kendi odası."""
        if not odb.aktif_mi(ctx.guild.id):
            raise OdaHatasi(KAPALI_MESAJI)
        adaylar = [ctx.channel]
        if ctx.author.voice is not None:
            adaylar.append(ctx.author.voice.channel)
        kanal = next((k for k in adaylar if k is not None and odb.oda_mi(k.id)), None)
        if kanal is None:
            odalar = self._gecerli_odalar(ctx.guild, ctx.author.id)
            if not odalar:
                raise OdaHatasi(f"Bir özel odada değilsin ve açık bir odan yok. **{HUB_ADI}** kanalına girerek oda açabilirsin.")
            kanal = odalar[-1]
        return self._oda_ve_yetki(kanal.id, ctx.author, sahip_gerekli)

    async def _komut(self, ctx, fabrika, sahip_gerekli=True):
        """fabrika(kanal, oda) → metin | Embed. Hataları Türkçe yanıtlar."""
        try:
            if ctx.interaction is not None:
                await ctx.defer(ephemeral=True)
            kanal, oda = self._komut_odasi(ctx, sahip_gerekli)
            sonuc = await fabrika(kanal, oda)
        except OdaHatasi as e:
            sonuc = f"❌ {e}"
        except discord.Forbidden:
            sonuc = "❌ Botun bu işlem için yetkisi yok (kanal / kategori izinlerini kontrol et)."
        except (discord.HTTPException, asyncio.TimeoutError) as e:
            logger.warning(f"🔊 Komut işlemi başarısız ({ctx.command}): {e!r}")
            sonuc = "⚠️ Discord şu an isteği tamamlayamadı, biraz sonra tekrar dene."
        if isinstance(sonuc, discord.Embed):
            await self._yanit(ctx, embed=sonuc, sure=60)
        else:
            await self._yanit(ctx, sonuc)

    # ── Yönetici komutları ────────────────────────

    @commands.hybrid_command(name="ozelodaaktif", aliases=["özelodaaktif", "ozelodaac", "özelodaaç"],
                             description="Özel ses odası sistemini bu sunucuda açar ve kanallarını kurar/onarır")
    @app_commands.default_permissions(manage_guild=True)
    @commands.guild_only()
    @commands.check(yonetici_kontrol)
    async def ozelodaaktif(self, ctx):
        await ctx.defer(ephemeral=True)
        guild = ctx.guild
        zaten_aktif = odb.aktif_mi(guild.id)
        sonuc = await self._kurulumu_onar(guild, f"{ctx.author} ({ctx.author.id}) tarafından")
        if sonuc['hata']:
            e = discord.Embed(title="❌ Özel odalar açılamadı", color=Renkler.HATA, description=sonuc['hata'])
            if sonuc['zorunlu']:
                e.add_field(name="Botta eksik yetkiler", value="\n".join(f"• {i}" for i in sonuc['zorunlu']), inline=False)
                e.add_field(name="Nasıl düzeltilir?", inline=False,
                            value="Sunucu Ayarları → Roller → bot rolüne bu yetkileri ver (kategori izinleri de "
                                  "engellememeli), sonra komutu tekrar çalıştır.")
            if sonuc['rapor']:
                e.add_field(name="Yapılanlar", value="\n".join(sonuc['rapor'])[:1024], inline=False)
            e.set_footer(text="Sistem " + ("açık kaldı" if zaten_aktif else "kapalı kaldı"))
            return await self._yanit(ctx, embed=e, sure=120)
        odb.ayar_guncelle(guild.id, aktif=1)
        ayar = odb.ayar_al(guild.id)
        e = discord.Embed(title="✅ Özel odalar " + ("onarıldı / güncellendi" if zaten_aktif else "açıldı"),
                          color=Renkler.BASARI)
        hub = guild.get_channel(ayar['hub_id'])
        e.description = (f"Üyeler {hub.mention if hub else HUB_ADI} kanalına girince kendi odaları açılır.\n"
                         "Varsayılanlar: `/ozeloda ayar` · Kapatmak: `/ozelodakapat`")
        e.add_field(name="Yapılanlar", value="\n".join(sonuc['rapor']) or "Her şey zaten yerindeydi ✅", inline=False)
        if sonuc['onerilen']:
            e.add_field(name="⚠️ Önerilen ama eksik yetkiler", inline=False,
                        value="\n".join(f"• {i}" for i in sonuc['onerilen'])
                              + "\n-# Eksikse oda sahipleri odalarında susturma/sağırlaştırma yapamaz.")
        baska = self._baska_sistemler(guild)
        if baska:
            e.add_field(name="⚠️ Başka bir özel oda sistemi var gibi görünüyor", inline=False,
                        value=", ".join(f"`{escape_markdown(a)}`" for a in baska)
                              + "\nİki sistem aynı anda kafa karıştırır: birini kapatın (bu bot için `/ozelodakapat`).")
        logger.info(f"🔊 [{guild.id}] Özel oda sistemi açıldı/onarıldı ({ctx.author.id})")
        await self._yanit(ctx, embed=e, sure=120)

    @commands.hybrid_command(name="ozelodakapat", aliases=["özelodakapat"],
                             description="Özel ses odası sistemini kapatır ve kanallarını kaldırır")
    @app_commands.default_permissions(manage_guild=True)
    @commands.guild_only()
    @commands.check(yonetici_kontrol)
    async def ozelodakapat(self, ctx):
        guild = ctx.guild
        odalar = odb.sunucu_odalari(guild.id)
        if not odb.aktif_mi(guild.id):
            ek = f" ({len(odalar)} oda boşalınca silinecek.)" if odalar else ""
            return await self._yanit(ctx, f"🔕 Özel oda sistemi bu sunucuda zaten kapalı.{ek}")
        dolu = sum(1 for o in odalar if _insanlar(guild.get_channel(o['kanal_id'])))
        onay = OnayGorunumu(ctx.author.id, "Evet, kapat")
        e = discord.Embed(title="🔕 Özel odalar kapatılsın mı?", color=Renkler.UYARI, description=(
            f"• **{HUB_ADI}**, panel kanalı ve (boşalınca) **{KATEGORI_ADI}** kategorisi silinir.\n"
            f"• Boş odalar hemen silinir ({len(odalar) - dolu}).\n"
            f"• İçinde insan olan **{dolu}** oda herkes çıkınca silinir (kimse sesten atılmaz).\n"
            "• Ayarlar saklanır; `/ozelodaaktif` ile tekrar açabilirsin."))
        await self._yanit(ctx, embed=e, view=onay, sure=65)
        if await onay.wait() or not onay.sonuc:
            return
        silinen, bekleyen, hatalar = await self._devre_disi_birak(guild)
        metin = f"🔕 Özel oda sistemi kapatıldı. {silinen} boş oda silindi."
        if bekleyen:
            metin += (f"\n⏳ **{bekleyen}** odada hâlâ insan var; boşalınca silinecek, kategori de en son kaldırılacak.")
        if hatalar:
            metin += "\n⚠️ " + "; ".join(hatalar) + " — elle silebilirsin."
        logger.info(f"🔊 [{guild.id}] Kapatan: {ctx.author.id}")
        await self._yanit(ctx, metin, sure=60)

    @commands.hybrid_group(name="ozeloda", aliases=["özeloda"], fallback="durum", invoke_without_command=True,
                           description="Özel oda sisteminin durumu ve ayarları (yönetici)")
    @app_commands.default_permissions(manage_guild=True)
    @commands.guild_only()
    @commands.check(yonetici_kontrol)
    async def ozeloda(self, ctx):
        guild = ctx.guild
        if not odb.aktif_mi(guild.id):
            return await self._yanit(ctx, KAPALI_MESAJI)
        ayar = odb.ayar_al(guild.id)
        e = discord.Embed(title="🔊 Özel Odalar — Durum", color=Renkler.BILGI)

        def kanal_metni(kid):
            k = guild.get_channel(kid or 0)
            return k.mention if k else "❌ yok (`/ozelodaaktif` onarır)"
        e.add_field(name="Kanallar", inline=False, value=(
            f"Kategori: {kanal_metni(ayar['kategori_id'])}\nOda oluştur: {kanal_metni(ayar['hub_id'])}\n"
            f"Panel: {kanal_metni(ayar['panel_kanal_id'])}"))
        e.add_field(name="Ayarlar", inline=False, value=self._ayar_ozeti(ayar))
        e.add_field(name="Açık oda", value=str(len(odb.sunucu_odalari(guild.id))), inline=True)
        zorunlu, onerilen = eksik_izinler(guild.me.guild_permissions)
        if zorunlu or onerilen:
            e.add_field(name="⚠️ Botta eksik yetkiler", value="\n".join(f"• {i}" for i in zorunlu + onerilen), inline=False)
        await self._yanit(ctx, embed=e, sure=60)

    @staticmethod
    def _ayar_ozeti(ayar):
        return (f"`limit` Varsayılan limit: **{'Sınırsız' if not ayar['varsayilan_limit'] else ayar['varsayilan_limit']}**\n"
                f"`sablon` Ad şablonu: **{escape_markdown(ayar['ad_sablonu'])}**\n"
                f"`sure` Boş oda silme: **{ayar['bos_silme_suresi']} sn**\n"
                f"`maxoda` Kişi başı oda: **{ayar['kisi_basi_oda']}**\n"
                f"`gizleme` Üyeler gizleyebilir: **{'Evet' if ayar['gizlemeye_izin'] else 'Hayır'}**")

    @ozeloda.command(name="ayar", description="Özel oda varsayılanlarını değiştirir (boş: gösterir)")
    @app_commands.describe(anahtar="Değiştirilecek ayar", deger="Yeni değer (ör. 5, 🔊 {kullanici} odası, 30, 1, evet)")
    @app_commands.choices(anahtar=[app_commands.Choice(name=ad, value=k) for k, (ad, _) in AYAR_ANAHTARLARI.items()])
    @commands.check(yonetici_kontrol)
    async def ozeloda_ayar(self, ctx, anahtar: str = None, *, deger: str = None):
        guild = ctx.guild
        if not odb.aktif_mi(guild.id):
            return await self._yanit(ctx, KAPALI_MESAJI)
        if anahtar is None:
            e = discord.Embed(title="⚙️ Özel oda ayarları", color=Renkler.BILGI, description=self._ayar_ozeti(odb.ayar_al(guild.id)))
            e.set_footer(text="Değiştir: /ozeloda ayar <anahtar> <değer> · şablonda {kullanici} ve {sayi} kullanılabilir")
            return await self._yanit(ctx, embed=e, sure=60)
        k = ayar_anahtari_coz(anahtar)
        if k is None:
            return await self._yanit(ctx, "❌ Bilinmeyen ayar. Geçerli: `limit`, `sablon`, `sure`, `maxoda`, `gizleme`.")
        if deger is None:
            return await self._yanit(ctx, f"❌ Yeni değeri de yaz: `{ctx.clean_prefix}ozeloda ayar {k} <değer>`")
        try:
            if k == 'limit':
                guncelleme = {'varsayilan_limit': limit_dogrula(deger)}
            elif k == 'sablon':
                guncelleme = {'ad_sablonu': sablon_dogrula(deger)}
            elif k == 'sure':
                guncelleme = {'bos_silme_suresi': sure_dogrula(deger)}
            elif k == 'maxoda':
                if not re.fullmatch(r"\d{1,2}", deger.strip()) or not KISI_BASI_MIN <= int(deger) <= KISI_BASI_MAX:
                    raise ValueError(f"Kişi başı oda {KISI_BASI_MIN}-{KISI_BASI_MAX} arası olmalı.")
                guncelleme = {'kisi_basi_oda': int(deger)}
            else:
                guncelleme = {'gizlemeye_izin': int(evet_hayir(deger))}
        except ValueError as e:
            return await self._yanit(ctx, f"❌ {e}")
        odb.ayar_guncelle(guild.id, **guncelleme)
        ayar = odb.ayar_al(guild.id)
        panel = guild.get_channel(ayar['panel_kanal_id'] or 0)
        if isinstance(panel, discord.TextChannel) and ayar['panel_mesaj_id']:
            try:
                await _api(panel.get_partial_message(ayar['panel_mesaj_id']).edit(embed=self._kurulum_paneli_embedi(guild)))
            except (discord.HTTPException, asyncio.TimeoutError):
                pass
        await self._yanit(ctx, f"✅ **{AYAR_ANAHTARLARI[k][0]}** güncellendi (yeni odalar için geçerli).\n{self._ayar_ozeti(ayar)}")

    # ── Oda sahibi komutları ──────────────────────

    @commands.hybrid_group(name="oda", fallback="bilgi", invoke_without_command=True,
                           description="Özel ses odanın bilgisi ve yönetimi")
    @commands.guild_only()
    async def oda(self, ctx):
        await self._komut(ctx, lambda kanal, oda: self._bilgi(kanal, oda), sahip_gerekli=False)

    async def _bilgi(self, kanal, oda):
        return self.bilgi_embedi(kanal, oda)

    @oda.command(name="ad", aliases=["isim"], description="Odanın adını değiştirir (en fazla 50 karakter)")
    @app_commands.describe(ad="Yeni oda adı")
    async def oda_ad(self, ctx, *, ad: str):
        await self._komut(ctx, lambda kanal, oda: self.eylem_ad(kanal, ctx.author, ad))

    @oda.command(name="limit", description="Kişi limitini ayarlar (0 = sınırsız, en fazla 99)")
    @app_commands.describe(limit="0-99 (0 = sınırsız)")
    async def oda_limit(self, ctx, limit: str):
        await self._komut(ctx, lambda kanal, oda: self.eylem_limit(kanal, ctx.author, limit))

    @oda.command(name="kilitle", description="Odayı kilitler: sadece davet ettiklerin girebilir")
    async def oda_kilitle(self, ctx):
        await self._komut(ctx, lambda kanal, oda: self.eylem_kilit(kanal, ctx.author, True))

    @oda.command(name="ac", aliases=["aç"], description="Odanın kilidini açar: herkes girebilir")
    async def oda_ac(self, ctx):
        await self._komut(ctx, lambda kanal, oda: self.eylem_kilit(kanal, ctx.author, False))

    @oda.command(name="gizle", description="Odayı gizler: sadece davetliler görebilir")
    async def oda_gizle(self, ctx):
        await self._komut(ctx, lambda kanal, oda: self.eylem_gizlilik(kanal, ctx.author, True))

    @oda.command(name="goster", aliases=["göster"], description="Odayı tekrar herkese görünür yapar")
    async def oda_goster(self, ctx):
        await self._komut(ctx, lambda kanal, oda: self.eylem_gizlilik(kanal, ctx.author, False))

    @oda.command(name="davet", description="Üyeyi odana davet eder (kilitli/gizli odaya girebilir)")
    @app_commands.describe(uye="Davet edilecek üye")
    async def oda_davet(self, ctx, uye: discord.Member):
        await self._komut(ctx, lambda kanal, oda: self.eylem_davet(kanal, ctx.author, [uye]))

    @oda.command(name="at", description="Üyeyi odadan atar ve tekrar girmesini engeller")
    @app_commands.describe(uye="Atılacak üye")
    async def oda_at(self, ctx, uye: discord.Member):
        await self._komut(ctx, lambda kanal, oda: self.eylem_at(kanal, ctx.author, [uye]))

    @oda.command(name="yasakla", description="Üyeyi odadan atar; odayı göremez ve giremez")
    @app_commands.describe(uye="Yasaklanacak üye")
    async def oda_yasakla(self, ctx, uye: discord.Member):
        await self._komut(ctx, lambda kanal, oda: self.eylem_at(kanal, ctx.author, [uye], yasakla=True))

    @oda.command(name="yasak-kaldir", aliases=["yasakkaldir", "yasakkaldır"], description="Üyenin oda yasağını kaldırır")
    @app_commands.describe(uye="Yasağı kaldırılacak üye")
    async def oda_yasak_kaldir(self, ctx, uye: discord.Member):
        await self._komut(ctx, lambda kanal, oda: self.eylem_yasak_kaldir(kanal, ctx.author, uye))

    @oda.command(name="devret", description="Oda sahipliğini başka bir üyeye verir")
    @app_commands.describe(uye="Yeni oda sahibi")
    async def oda_devret(self, ctx, uye: discord.Member):
        await self._komut(ctx, lambda kanal, oda: self.eylem_devret(kanal, ctx.author, uye))

    @oda.command(name="sahiplen", description="Sahibi odada değilse odayı devralırsın (odada olmalısın)")
    async def oda_sahiplen(self, ctx):
        await self._komut(ctx, lambda kanal, oda: self.eylem_sahiplen(kanal, ctx.author), sahip_gerekli=False)

    @oda.command(name="panel", description="Kontrol panelini odanın sohbetine yeniden gönderir")
    async def oda_panel(self, ctx):
        async def gonder(kanal, oda):
            mesaj = await self._paneli_gonder(kanal, None)
            if mesaj is None:
                raise OdaHatasi("Panel gönderilemedi (botun odanın sohbetine yazma yetkisi var mı?).")
            return f"🎛️ Panel gönderildi 👉 {mesaj.jump_url}"
        await self._komut(ctx, gonder)


async def setup(bot):
    await bot.add_cog(OzelOda(bot))
