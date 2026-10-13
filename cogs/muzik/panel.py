"""
Kontrol paneli (sunucu başına TEK kalıcı embed) + sayfalı görünümler (kuyruk, sözler, geçmiş, listeler).

Kalıcı görünüm: tüm bileşenlerin sabit custom_id'si var ('muzik:...'), timeout=None.
Cog yüklenirken bot.add_view(MuzikPaneli(cog)) ile kaydedilir → bot yeniden başlasa da eski paneldeki
butonlar çalışır. Tüm tıklamalar Muzik.panel_etkilesimi()'ne gider (tek yerde yetki + mantık).
"""
import logging

import discord
from discord.utils import escape_markdown

from arayuz import platform_bilgi
from .filtreler import FILTRE_SECENEKLERI
from .kuyruk import DONGU_ETIKET, DONGU_KUYRUK, DONGU_SARKI, ilerleme_cubugu, sure_metni
from dil import _t

logger = logging.getLogger('MezarBot.Muzik.Panel')

MUZIK_RENGI = 0x1DB954
KAYNAK_GOSTERIM = {
    'youtube': ('🔴', 'YouTube', 0xFF0000),
    'soundcloud': ('🟠', 'SoundCloud', 0xFF7700),
    'spotify': ('🟢', 'Spotify → YouTube', 0x1DB954),
    'http': ('🔗', 'Doğrudan Link', 0x5865F2),
}


def kaynak_bilgi(kaynak):
    if kaynak in KAYNAK_GOSTERIM:
        ikon, isim, renk = KAYNAK_GOSTERIM[kaynak]
        return ikon, _t(isim), renk
    b = platform_bilgi(kaynak)
    return b['ikon'], b['isim'], b['renk']


def _temiz(metin, n=80):
    metin = " ".join(str(metin or "").split())
    metin = metin if len(metin) <= n else metin[:n - 1] + "…"
    return escape_markdown(metin)


def parca_satiri(p, n=55, link=True):
    baslik = _temiz(p.baslik or p.gosterim(n), n)
    parca = f"[{baslik}]({p.url})" if (link and p.url) else f"**{baslik}**"
    sure = f" `{sure_metni(p.sure)}`" if p.sure else ""
    kim = " · 📻" if p.otomatik else (f" · <@{p.isteyen_id}>" if p.isteyen_id else "")
    return f"{parca}{sure}{kim}"


def _dave_durumu(vc):
    """DAVE (uçtan uca ses şifreleme) oturumu aktifse kısa etiket."""
    try:
        return "🔒 E2EE (DAVE)" if vc is not None and getattr(vc, 'voice_privacy_code', None) else ""
    except Exception:  # davey iç durumu okunamadı — sadece gösterim, sessizce geç
        return ""


# ══════════════════════════════════════════════
#  EMBED'LER
# ══════════════════════════════════════════════

def bot_adi(guild):
    """Panelde görünen bot adı: sunucudaki görünen adı (ikinci müzik botu kendi adını gösterir)."""
    me = guild.me if guild is not None else None
    return me.display_name if me is not None else "MezarBot"


def calma_embedi(oyn):
    p = oyn.simdiki
    ikon, isim, renk = kaynak_bilgi(p.kaynak)
    vc = oyn.vc
    duraklatildi = oyn.duraklatildi_mi()
    if duraklatildi:
        durum = _t("⏸️ Duraklatıldı")
    elif p.canli:
        durum = _t("🔴 Canlı Yayın")
    else:
        durum = _t("🎶 Şu An Çalıyor")
    embed = discord.Embed(color=renk, title=_temiz(p.baslik or p.gosterim(80), 90), url=p.url or None)
    embed.set_author(name=f"{durum}  ·  {ikon} {isim}", icon_url=p.isteyen_avatar or None)
    if p.kucuk_resim:
        embed.set_thumbnail(url=p.kucuk_resim)

    gecen = oyn.konum()
    toplam = sure_metni(p.sure) if p.sure else "CANLI"
    satirlar = [
        ilerleme_cubugu(gecen, p.sure, 18),
        f"`{sure_metni(gecen)} / {toplam}`  ·  {'🔇' if oyn.ses == 0 else '🔉' if oyn.ses < 60 else '🔊'} {_t("**%{ses}**", ses=oyn.ses)}"
        + (f"  ·  🎤 {_temiz(p.sanatci, 40)}" if p.sanatci and p.sanatci.casefold() not in (p.baslik or "").casefold() else ""),
    ]
    if oyn.otomatik_duraklatildi:
        satirlar.append(_t("💤 *Kanalda kimse kalmadı — biri gelince kaldığı yerden devam edecek.*"))
    embed.description = "\n".join(satirlar)

    kim = f"<@{p.isteyen_id}>" if p.isteyen_id and not p.otomatik else (_t("📻 Otomatik") if p.otomatik else (p.isteyen_ad or "—"))
    embed.add_field(name=_t("👤 İsteyen"), value=kim, inline=True)
    embed.add_field(name=_t("🔁 Döngü"), value=_t(DONGU_ETIKET.get(oyn.dongu, "Kapalı")), inline=True)
    embed.add_field(name=_t("📋 Kuyruk"),
                    value=_t("{len} parça", len=len(oyn.kuyruk)) + (f" · {sure_metni(oyn.kuyruk.toplam_sure())}" if oyn.kuyruk.toplam_sure() else ""),
                    inline=True)
    embed.add_field(name=_t("📻 Otomatik"), value=_t("Açık") if oyn.otomatik else _t("Kapalı"), inline=True)
    ses_yolu = _t("Opus aktarım (kayıpsız)") if oyn.dogrudan_aktarim_mi() else _t("Opus · 160 kbps")
    embed.add_field(name=_t("🎚️ Ses Yolu"), value=ses_yolu, inline=True)
    embed.add_field(name=_t("📶 Ses Dengeleme"), value=_t("Açık") if oyn.filtre.normalizasyon else _t("Kapalı"), inline=True)

    sonraki = oyn.kuyruk.ilk()
    if oyn.dongu == DONGU_SARKI:
        sonraki_metin = _t("🔂 Aynı şarkı tekrar çalacak")
    elif sonraki:
        sonraki_metin = parca_satiri(sonraki, 60)
        if len(oyn.kuyruk) > 1:
            sonraki_metin += _t("\n-# … ve {d1} parça daha", d1=len(oyn.kuyruk) - 1)
    elif oyn.otomatik:
        sonraki_metin = _t("📻 Otomatik oynatma benzer bir parça bulacak")
    else:
        sonraki_metin = _t("Kuyruk boş — `/oynat` ile ekle")
    embed.add_field(name=_t("⏭️ Sıradaki"), value=sonraki_metin, inline=False)

    alt = [_t("{bot} Premium Müzik", bot=bot_adi(oyn.guild))]
    dave = _dave_durumu(vc)
    if dave:
        alt.append(dave)
    if vc and vc.channel:
        alt.append(f"🔈 {vc.channel.name}")
    embed.set_footer(text="  •  ".join(alt))
    return embed


def bosta_embedi(guild, istek_kanali=False, prefix="!", son_mesaj=None):
    embed = discord.Embed(color=MUZIK_RENGI, title=_t("🎵 {bot} Müzik", bot=bot_adi(guild)))
    if istek_kanali:
        nasil = (_t("**Bir ses kanalına gir ve bu kanala şarkı adı ya da link yaz** — gerisini ben hallederim.\n-# Mesajın sıraya eklenince otomatik silinir; kanal hep temiz kalır."))
    else:
        nasil = _t("Bir ses kanalına gir ve `/oynat <şarkı>` ya da `{prefix}oynat <şarkı>` yaz.", prefix=prefix)
    embed.description = _t("{d0}Şu an bir şey çalmıyor.\n\n{nasil}", d0=son_mesaj + chr(10) if son_mesaj else '', nasil=nasil)
    embed.add_field(name=_t("🌐 Kaynaklar"),
                    value=_t("🔴 YouTube · 🎵 YouTube Music · 🟢 Spotify · 🟠 SoundCloud · 🔗 Doğrudan ses linki"),
                    inline=False)
    embed.add_field(name=_t("✨ Öne Çıkanlar"),
                    value=_t("📻 Otomatik oynatma · 📶 Ses dengeleme · 🎤 Senkron sözler · ❤️ Kişisel listeler\n🛟 YouTube çalamazsa SoundCloud yedeği"),
                    inline=False)
    embed.set_footer(text=_t("{bot} Premium Müzik", bot=bot_adi(guild)))
    if guild and guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    return embed


def kuyruk_embedi(oyn, sayfa, sayfa_boyu=10):
    """→ (embed, sayfa_sayisi). sayfa 0 tabanlı."""
    parcalar = list(oyn.kuyruk)
    sayfa_sayisi = max(1, (len(parcalar) + sayfa_boyu - 1) // sayfa_boyu)
    sayfa = max(0, min(sayfa, sayfa_sayisi - 1))
    embed = discord.Embed(color=MUZIK_RENGI, title=_t("📜 Kuyruk"))
    satirlar = []
    if oyn.simdiki:
        satirlar.append(_t("**▶ Şimdi:** {parca_satiri}\n", parca_satiri=parca_satiri(oyn.simdiki, 60)))
    bas = sayfa * sayfa_boyu
    for i, p in enumerate(parcalar[bas:bas + sayfa_boyu], start=bas + 1):
        satirlar.append(f"`{i:>3}.` {parca_satiri(p, 55)}")
    if not parcalar:
        satirlar.append(_t("*Kuyruk boş.*") + (_t(" 📻 Otomatik oynatma açık.") if oyn.otomatik else ""))
    embed.description = "\n".join(satirlar)[:4000]
    toplam = oyn.kuyruk.toplam_sure()
    embed.set_footer(text=_t("Sayfa {d1}/{sayfa_sayisi}  •  {len} parça", d1=sayfa + 1, sayfa_sayisi=sayfa_sayisi, len=len(parcalar))
                          + (f"  •  {sure_metni(toplam)}" if toplam else "")
                          + _t("  •  Döngü: {get}", get=_t(DONGU_ETIKET.get(oyn.dongu, "Kapalı"))))
    return embed, sayfa_sayisi


def gecmis_embedi(oyn, n=15):
    embed = discord.Embed(color=MUZIK_RENGI, title=_t("🕘 Son Çalınanlar"))
    son = oyn.gecmis.son(n)
    embed.description = "\n".join(f"`{i:>2}.` {parca_satiri(p, 60)}" for i, p in enumerate(son, 1)) or _t("*Henüz bir şey çalınmadı.*")
    embed.set_footer(text=_t("⏮️ önceki şarkıya dönmek için /onceki"))
    return embed


# ══════════════════════════════════════════════
#  KALICI KONTROL PANELİ
# ══════════════════════════════════════════════

class _PanelButonu(discord.ui.Button):
    def __init__(self, eylem, emoji, satir, stil=discord.ButtonStyle.secondary, etiket=None):
        super().__init__(custom_id=f"muzik:{eylem}", emoji=emoji, label=etiket, style=stil, row=satir)
        self.eylem = eylem

    async def callback(self, interaction):
        await self.view.cog.panel_etkilesimi(interaction, self.eylem)


class _FiltreMenusu(discord.ui.Select):
    def __init__(self):
        secenekler = [discord.SelectOption(label=_t(etiket), value=anahtar, emoji=emoji, description=_t(aciklama))
                      for anahtar, (etiket, emoji, aciklama) in FILTRE_SECENEKLERI.items()]
        super().__init__(custom_id="muzik:filtre", placeholder=_t("🎛️ Filtre / efekt seç…"), options=secenekler,
                         min_values=1, max_values=1, row=2)

    async def callback(self, interaction):
        await self.view.cog.panel_etkilesimi(interaction, "filtre", self.values[0])


class MuzikPaneli(discord.ui.View):
    """Sunucu başına bir örnek (cog.panel_gorunumu). Durumu guncelle(oyn) ile yansıtır."""

    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog
        S = discord.ButtonStyle
        self.butonlar = {}
        for eylem, emoji, satir, stil in (
            ("onceki", "⏮️", 0, S.secondary), ("duraklat", "⏸️", 0, S.primary), ("atla", "⏭️", 0, S.secondary),
            ("durdur", "⏹️", 0, S.danger), ("dongu", "🔁", 0, S.secondary),
            ("karistir", "🔀", 1, S.secondary), ("sesazalt", "🔉", 1, S.secondary), ("sesartir", "🔊", 1, S.secondary),
            ("kuyruk", "📜", 1, S.secondary),
        ):
            b = _PanelButonu(eylem, emoji, satir, stil)
            self.butonlar[eylem] = b
            self.add_item(b)
        # Filtre menüsü ve 🎤 butonu kaldırıldı (efektler sunulmuyor; sözler panelin içinde).
        self.butonlar["otomatik"] = _PanelButonu("otomatik", "📻", 2, S.secondary, _t("Otomatik: Kapalı"))
        self.butonlar["favori"] = _PanelButonu("favori", "❤️", 2, S.secondary, _t("Favorilerime ekle"))
        self.add_item(self.butonlar["otomatik"])
        self.add_item(self.butonlar["favori"])

    def guncelle(self, oyn):
        aktif = oyn is not None and oyn.simdiki is not None
        S = discord.ButtonStyle
        for eylem, b in self.butonlar.items():
            b.disabled = not aktif and eylem not in ("otomatik",)
        if not aktif:
            self.butonlar["otomatik"].disabled = oyn is None
        if oyn is None:
            self.butonlar["otomatik"].label = _t("Otomatik: Kapalı")
            self.butonlar["otomatik"].style = S.secondary
            return self
        dur = oyn.duraklatildi_mi()
        self.butonlar["duraklat"].emoji = "▶️" if dur else "⏸️"
        self.butonlar["duraklat"].style = S.success if dur else S.primary
        self.butonlar["dongu"].emoji = "🔂" if oyn.dongu == DONGU_SARKI else "🔁"
        self.butonlar["dongu"].style = (S.success if oyn.dongu == DONGU_SARKI
                                        else S.primary if oyn.dongu == DONGU_KUYRUK else S.secondary)
        self.butonlar["onceki"].disabled = not aktif or len(oyn.gecmis) == 0
        self.butonlar["karistir"].disabled = not aktif or len(oyn.kuyruk) < 2
        self.butonlar["sesazalt"].disabled = not aktif or oyn.ses <= 0
        self.butonlar["sesartir"].disabled = not aktif or oyn.ses >= 150
        self.butonlar["otomatik"].label = _t("Otomatik: {d1}", d1=_t("Açık") if oyn.otomatik else _t("Kapalı"))
        self.butonlar["favori"].label = _t("Favorilerime ekle")   # sunucu dili sonradan değişmiş olabilir
        self.butonlar["otomatik"].style = S.success if oyn.otomatik else S.secondary
        return self

    async def on_error(self, interaction, error, item):
        logger.error(f"Panel etkileşim hatası ({getattr(item, 'custom_id', '?')}): {error!r}", exc_info=error)
        try:
            if interaction.response.is_done():
                await interaction.followup.send(_t("⚠️ Bir hata oluştu, tekrar dene."), ephemeral=True)
            else:
                await interaction.response.send_message(_t("⚠️ Bir hata oluştu, tekrar dene."), ephemeral=True)
        except discord.HTTPException:
            pass


# ══════════════════════════════════════════════
#  SAYFALI GÖRÜNÜM (kuyruk / sözler / listeler)
# ══════════════════════════════════════════════

class SayfaGorunumu(discord.ui.View):
    """uretici(sayfa) → (embed, sayfa_sayisi). Her tıklamada canlı veriden yeniden üretilir."""

    def __init__(self, uretici, kullanici_id=None, zaman_asimi=180, yenile_etiketi="🔄"):
        super().__init__(timeout=zaman_asimi)
        self.uretici = uretici
        self.kullanici_id = kullanici_id
        self.sayfa = 0
        self.mesaj = None
        self.yenile_btn.label = None
        self.yenile_btn.emoji = yenile_etiketi

    def ilk(self):
        embed, n = self.uretici(self.sayfa)
        self._butonlari_ayarla(n)
        return embed

    def _butonlari_ayarla(self, n):
        self.ilk_btn.disabled = self.geri_btn.disabled = self.sayfa <= 0
        self.son_btn.disabled = self.ileri_btn.disabled = self.sayfa >= n - 1

    async def interaction_check(self, interaction):
        if self.kullanici_id and interaction.user.id != self.kullanici_id:
            await interaction.response.send_message(_t("Bu menü sana ait değil — kendi komutunu kullan."), ephemeral=True)
            return False
        return True

    async def _goster(self, interaction, sayfa):
        self.sayfa = sayfa
        embed, n = self.uretici(self.sayfa)
        self.sayfa = max(0, min(self.sayfa, n - 1))
        embed, n = self.uretici(self.sayfa)
        self._butonlari_ayarla(n)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(emoji="⏮️", style=discord.ButtonStyle.secondary)
    async def ilk_btn(self, interaction, button):
        await self._goster(interaction, 0)

    @discord.ui.button(emoji="◀️", style=discord.ButtonStyle.secondary)
    async def geri_btn(self, interaction, button):
        await self._goster(interaction, self.sayfa - 1)

    @discord.ui.button(emoji="🔄", style=discord.ButtonStyle.primary)
    async def yenile_btn(self, interaction, button):
        await self._goster(interaction, self.sayfa)

    @discord.ui.button(emoji="▶️", style=discord.ButtonStyle.secondary)
    async def ileri_btn(self, interaction, button):
        await self._goster(interaction, self.sayfa + 1)

    @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.secondary)
    async def son_btn(self, interaction, button):
        await self._goster(interaction, 10 ** 6)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.mesaj is not None:
            try:
                await self.mesaj.edit(view=self)
            except discord.HTTPException:
                pass
