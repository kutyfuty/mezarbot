"""
Çok dilli (TR/EN) üye onay ve kapı (gate) sistemi — config.json → onay_sistemi ile TEK bir sunucu için açılır
(sunucu_id boşsa cog hiçbir şey yapmaz).
- Kanallar dil bazlı dinamik görünür: 🇹🇷 Türkçe seçene Türkçe kanallar, 🇬🇧 English seçene İngilizce kanallar görünür.
- Girişte (🚪・giris) kalıcı butonlarla dil seçimi yapılır.
- Kurucunun (onay_sistemi.kurucu_id, boşsa sahip_id) şahsi davetiyle gelenler otomatik onaylanır.
- Genel davetle (onay_sistemi.genel_davet_kodu, ör. web sitesindeki link) gelenler onay bekler, onaylanana kadar kanalları göremez.
- Kurucuya 🛡️・onay-bekleyenler kanalında üyenin seçtiği dil bilgisi ve tek tıkla onay/red butonları sunulur.
- DynamicItem ve persistent view desteği sayesinde bot yeniden başlasa da tüm butonlar çalışır.
"""
import logging
import datetime
import re
import sqlite3
import discord
from discord.ext import commands
from discord import app_commands

from yapilandirma import DB_DOSYA, ONAY_GENEL_DAVET_KODU, ONAY_KURUCU_ID, ONAY_SUNUCU_ID

logger = logging.getLogger('MezarBot.SunucuOnay')

ONAY_KANAL_ADI = "onay-bekleyenler"
GIRIS_KANAL_ADI = "giris"

ROL_TOPLULUK = "🛠️ Topluluk"
ROL_MAKER = "⚡ Maker / Geliştirici"
ROL_TR = "🇹🇷 Türkçe"
ROL_EN = "🇬🇧 English"


# ══════════════════════════════════════════════
#  VERİTABANI YARDIMCILARI
# ══════════════════════════════════════════════

DIL_ETIKETLERI = {"tr": "🇹🇷 Türkçe", "en": "🇬🇧 English", "both": "🌐 Her İkisi / Both"}


def _kurucu_mu(kullanici) -> bool:
    return kullanici.id == ONAY_KURUCU_ID or kullanici.guild_permissions.administrator


async def _onay_rolleri_ver(guild, uye, rol: str, dil: str, sebep: str):
    """Onaylanan üyeye unvan (Topluluk / Maker) + dil rollerini verir. Sunucuda olmayan rol atlanır."""
    adlar = [ROL_MAKER] if rol == "maker" else []
    adlar.append(ROL_TOPLULUK)
    adlar += {"en": [ROL_EN], "both": [ROL_TR, ROL_EN]}.get(dil, [ROL_TR])
    roller = [r for r in (discord.utils.get(guild.roles, name=ad) for ad in adlar) if r and r not in uye.roles]
    if roller:
        await uye.add_roles(*roller, reason=sebep)


def _db_baglan():
    con = sqlite3.connect(DB_DOSYA)
    con.row_factory = sqlite3.Row
    return con


def _db_kur():
    with _db_baglan() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS sunucu_onay_tercih (
                uye_id INTEGER PRIMARY KEY,
                dil TEXT DEFAULT 'tr',
                onay_mesaj_id INTEGER DEFAULT 0,
                guncelleme TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)


def _dil_kaydet(uye_id: int, dil: str):
    with _db_baglan() as con:
        con.execute("""
            INSERT INTO sunucu_onay_tercih (uye_id, dil, guncelleme)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(uye_id) DO UPDATE SET
                dil = excluded.dil,
                guncelleme = CURRENT_TIMESTAMP
        """, (uye_id, dil))


def _dil_al(uye_id: int) -> str:
    with _db_baglan() as con:
        cur = con.cursor()
        cur.execute("SELECT dil FROM sunucu_onay_tercih WHERE uye_id = ?", (uye_id,))
        row = cur.fetchone()
        return row['dil'] if row and row['dil'] else 'tr'


def _onay_mesaj_kaydet(uye_id: int, mesaj_id: int):
    with _db_baglan() as con:
        con.execute("""
            INSERT INTO sunucu_onay_tercih (uye_id, onay_mesaj_id, guncelleme)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(uye_id) DO UPDATE SET
                onay_mesaj_id = excluded.onay_mesaj_id,
                guncelleme = CURRENT_TIMESTAMP
        """, (uye_id, mesaj_id))


def _onay_mesaj_al(uye_id: int) -> int:
    with _db_baglan() as con:
        cur = con.cursor()
        cur.execute("SELECT onay_mesaj_id FROM sunucu_onay_tercih WHERE uye_id = ?", (uye_id,))
        row = cur.fetchone()
        return row['onay_mesaj_id'] if row and row['onay_mesaj_id'] else 0


# ══════════════════════════════════════════════
#  DİL SEÇİM GÖRÜNÜMÜ (🚪・giris kanalı için)
# ══════════════════════════════════════════════

class DilSecimGorunumu(discord.ui.View):
    """Giriş kanalındaki kalıcı dil seçim butonları."""
    def __init__(self):
        super().__init__(timeout=None)

    async def _dil_isle(self, interaction: discord.Interaction, secim: str):
        guild = interaction.guild
        if not guild:
            return await interaction.response.send_message("Sunucu bulunamadı.", ephemeral=True)

        uye = guild.get_member(interaction.user.id)
        if not uye:
            return await interaction.response.send_message("Üye bilgisi alınamadı.", ephemeral=True)

        rol_topluluk = discord.utils.get(guild.roles, name=ROL_TOPLULUK)
        rol_maker = discord.utils.get(guild.roles, name=ROL_MAKER)
        rol_kurucu = discord.utils.get(guild.roles, name="👑 Kurucu")
        rol_tr = discord.utils.get(guild.roles, name=ROL_TR)
        rol_en = discord.utils.get(guild.roles, name=ROL_EN)

        # Kullanıcı zaten onaylı mı?
        onayli_mi = (
            uye.id == ONAY_KURUCU_ID
            or (rol_kurucu and rol_kurucu in uye.roles)
            or (rol_maker and rol_maker in uye.roles)
            or (rol_topluluk and rol_topluluk in uye.roles)
        )

        _dil_kaydet(uye.id, secim)

        if onayli_mi:
            # Onaylı üye: Rolleri doğrudan güncelle
            to_add = []
            to_remove = []
            if secim == "tr":
                if rol_tr and rol_tr not in uye.roles: to_add.append(rol_tr)
                if rol_en and rol_en in uye.roles: to_remove.append(rol_en)
                msg = "🇹🇷 Dil tercihiniz **Türkçe** olarak güncellendi! Türkçe kanallar sol panelde açıldı."
            elif secim == "en":
                if rol_en and rol_en not in uye.roles: to_add.append(rol_en)
                if rol_tr and rol_tr in uye.roles: to_remove.append(rol_tr)
                msg = "🇬🇧 Language preference set to **English**! English channels are now visible on the sidebar."
            else: # both
                if rol_tr and rol_tr not in uye.roles: to_add.append(rol_tr)
                if rol_en and rol_en not in uye.roles: to_add.append(rol_en)
                msg = "🌐 Dil tercihiniz **Her İkisi / Both** olarak güncellendi! Tüm kanallar açıldı."

            if to_add:
                await uye.add_roles(*to_add, reason="Dil seçimi güncellendi")
            if to_remove:
                await uye.remove_roles(*to_remove, reason="Dil seçimi güncellendi")

            return await interaction.response.send_message(msg, ephemeral=True)

        # Onaysız üye: Kanalları henüz açma (kapı güvenliği), tercihi kaydet ve onay kartını güncelle
        mid = _onay_mesaj_al(uye.id)
        if mid:
            onay_kanali = next((c for c in guild.text_channels if ONAY_KANAL_ADI in c.name), None)
            if onay_kanali:
                try:
                    msg_obj = await onay_kanali.fetch_message(mid)
                    if msg_obj and msg_obj.embeds:
                        emb = msg_obj.embeds[0]
                        dil_etiket = {"tr": "🇹🇷 Türkçe", "en": "🇬🇧 English", "both": "🌐 Her İkisi / Both"}.get(secim, secim)
                        # Var olan dil alanını güncelle veya ekle
                        alanlar = [f for f in emb.fields if "Dil" not in f.name and "Language" not in f.name]
                        alanlar.append(discord.EmbedField(name="🌐 Seçilen Dil", value=f"**{dil_etiket}**", inline=True))
                        emb.clear_fields()
                        for f in alanlar:
                            emb.add_field(name=f.name, value=f.value, inline=f.inline)
                        await msg_obj.edit(embed=emb)
                except Exception as e:
                    logger.debug(f"Onay embed güncelleme hatası: {e}")

        if secim == "en":
            txt = (
                "🇬🇧 **Language preference recorded as English!**\n\n"
                "Your request is currently waiting for founder approval. "
                "Once approved, the English channels will unlock for you automatically."
            )
        elif secim == "both":
            txt = (
                "🌐 **Dil tercihiniz Her İkisi / Both olarak kaydedildi!**\n\n"
                "Sunucuya katılımınız kurucu tarafından onaylandığında tüm kanallar erişiminize açılacaktır."
            )
        else:
            txt = (
                "🇹🇷 **Dil tercihiniz Türkçe olarak kaydedildi!**\n\n"
                "Sunucuya katılımınız kurucu tarafından onaylandığında Türkçe kanallar erişiminize açılacaktır."
            )
        await interaction.response.send_message(txt, ephemeral=True)

    @discord.ui.button(label="Türkçe", emoji="🇹🇷", style=discord.ButtonStyle.secondary, custom_id="dilsecim:tr")
    async def buton_tr(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._dil_isle(interaction, "tr")

    @discord.ui.button(label="English", emoji="🇬🇧", style=discord.ButtonStyle.secondary, custom_id="dilsecim:en")
    async def buton_en(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._dil_isle(interaction, "en")

    @discord.ui.button(label="Her İkisi / Both", emoji="🌐", style=discord.ButtonStyle.secondary, custom_id="dilsecim:both")
    async def buton_both(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._dil_isle(interaction, "both")


# ══════════════════════════════════════════════
#  DİNAMİK ONAY BUTONU & GÖRÜNÜMÜ
# ══════════════════════════════════════════════

class OnayButonu(discord.ui.DynamicItem[discord.ui.Button],
                 template=r"onay:(?P<eylem>topluluk|maker|reddet):(?P<uye_id>[0-9]{15,21})"):
    """
    Onay butonları DynamicItem olarak çalışır.
    Bot yeniden başlasa dahi custom_id üzerinden uye_id'yi çözer.
    """
    def __init__(self, eylem: str, uye_id: int, etiket: str = None, emoji: str = None, stil = discord.ButtonStyle.secondary):
        super().__init__(discord.ui.Button(
            custom_id=f"onay:{eylem}:{uye_id}",
            label=etiket,
            emoji=emoji,
            style=stil
        ))
        self.eylem = eylem
        self.uye_id = int(uye_id)

    @classmethod
    async def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Button, match: re.Match):
        return cls(match["eylem"], int(match["uye_id"]))

    async def callback(self, interaction: discord.Interaction):
        # Yetki kontrolü
        if not _kurucu_mu(interaction.user):
            return await interaction.response.send_message("❌ Bu işlemi yalnızca sunucu kurucusu yapabilir.", ephemeral=True)

        await interaction.response.defer()
        guild = interaction.guild
        uye = guild.get_member(self.uye_id)
        if not uye:
            return await interaction.followup.send("⚠️ Bu üye artık sunucuda bulunmuyor.", ephemeral=True)

        if self.eylem == "reddet":
            try:
                await uye.send(f"❌ **{guild.name}** sunucusuna giriş talebiniz onaylanmadı.")
            except Exception:
                pass
            await uye.kick(reason=f"{interaction.user} tarafından onay verilmedi")

            view = discord.ui.View.from_message(interaction.message)
            for child in view.children:
                child.disabled = True
            embed = interaction.message.embeds[0] if interaction.message.embeds else discord.Embed()
            embed.color = discord.Color.red()
            embed.add_field(name="Durum", value=f"❌ <@{interaction.user.id}> tarafından reddedildi ve sunucudan atıldı.", inline=False)
            return await interaction.edit_original_response(embed=embed, view=view)

        # Onay İşlemi (Topluluk veya Maker)
        secilen_dil = _dil_al(self.uye_id)
        await _onay_rolleri_ver(guild, uye, self.eylem, secilen_dil, f"{interaction.user} tarafından onaylandı")

        # Butonları devre dışı bırak
        view = discord.ui.View.from_message(interaction.message)
        for child in view.children:
            child.disabled = True

        embed = interaction.message.embeds[0] if interaction.message.embeds else discord.Embed()
        embed.color = discord.Color.teal() if self.eylem == "maker" else discord.Color.green()
        unvan = ROL_MAKER if self.eylem == "maker" else ROL_TOPLULUK
        dil_etiket = DIL_ETIKETLERI.get(secilen_dil, DIL_ETIKETLERI["tr"])
        embed.add_field(
            name="Onay Sonucu",
            value=f"✅ <@{interaction.user.id}> tarafından **{unvan}** olarak onaylandı.\n🌐 **Erişim Dili:** {dil_etiket}",
            inline=False
        )
        await interaction.edit_original_response(embed=embed, view=view)

        # DM Bildirimi
        try:
            if secilen_dil == "en":
                await uye.send(
                    f"🎉 **Welcome to {guild.name}!**\n"
                    f"Your membership has been approved as **{unvan}**.\n"
                    "The English channels are now visible to you. Have fun!"
                )
            else:
                await uye.send(
                    f"🎉 **{guild.name}** sunucusuna girişiniz onaylandı!\n"
                    f"Rolünüz: **{unvan}**\n"
                    "Kanallar erişiminize açıldı. Hoş geldiniz!"
                )
        except Exception:
            pass


def onay_gorunumu_olustur(uye_id: int) -> discord.ui.View:
    """Üye için onay butonlarını içeren görünüm."""
    v = discord.ui.View(timeout=None)
    v.add_item(OnayButonu("topluluk", uye_id, "Topluluk Olarak Onayla", "✅", discord.ButtonStyle.success))
    v.add_item(OnayButonu("maker", uye_id, "Maker Olarak Onayla", "⚡", discord.ButtonStyle.primary))
    v.add_item(OnayButonu("reddet", uye_id, "Reddet ve At", "❌", discord.ButtonStyle.danger))
    return v


# ══════════════════════════════════════════════
#  COG
# ══════════════════════════════════════════════

class SunucuOnay(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.davet_onbellegi = {}

    async def cog_load(self):
        _db_kur()
        self.bot.add_view(DilSecimGorunumu())
        self.bot.add_dynamic_items(OnayButonu)
        logger.info("SunucuOnay cog yüklendi: DilSecimGorunumu ve OnayButonu kaydedildi")

    async def cog_unload(self):
        self.bot.remove_dynamic_items(OnayButonu)

    async def _davetleri_guncelle(self, guild: discord.Guild):
        try:
            invites = await guild.invites()
            self.davet_onbellegi[guild.id] = {
                inv.code: {'uses': inv.uses, 'inviter_id': inv.inviter.id if inv.inviter else None}
                for inv in invites
            }
        except Exception as e:
            logger.warning(f"Davetler önbelleğe alınamadı ({guild.id}): {e}")

    async def _giris_panelini_denetle(self, guild: discord.Guild):
        """🚪・giris kanalında kalıcı dil seçim mesajı yoksa oluşturur."""
        giris_kanali = next((c for c in guild.text_channels if GIRIS_KANAL_ADI in c.name), None)
        if not giris_kanali:
            return

        # Botun son 10 mesajını tara
        panel_var = False
        async for m in giris_kanali.history(limit=10):
            if m.author.id == self.bot.user.id and m.embeds and "Topluluk" in (m.embeds[0].title or ""):
                panel_var = True
                break

        if not panel_var:
            embed = discord.Embed(
                title="🌍 Topluluk Sunucusuna Hoş Geldiniz / Welcome!",
                color=discord.Color.from_rgb(52, 152, 219),
                description=(
                    "Elektronik, yazılım, robotik ve teknoloji topluluğumuza hoş geldiniz.\n\n"
                    "Lütfen sunucuyu kullanmak istediğiniz dili aşağıdan seçin:\n"
                    "Please select your preferred language for the server below:\n\n"
                    "🇹🇷 **Türkçe:** Kanalları ve duyuruları Türkçe olarak görüntülersiniz.\n"
                    "🇬🇧 **English:** View community channels and announcements in English.\n"
                    "🌐 **Her İkisi / Both:** Tüm kanalları birlikte görüntülersiniz.\n\n"
                    "───────────────────────────────────\n"
                    "ℹ️ *Onay bekliyorsanız seçiminiz kurucu onayından sonra devreye girer.*\n"
                    "ℹ️ *If pending approval, your channels will unlock once approved.*"
                )
            )
            embed.set_footer(text="Topluluk • Language & Gate System")
            msg = await giris_kanali.send(embed=embed, view=DilSecimGorunumu())
            try:
                await msg.pin(reason="Dil seçim paneli")
            except Exception:
                pass
            logger.info("Giriş kanalına kalıcı dil paneli gönderildi")

    @commands.Cog.listener()
    async def on_ready(self):
        guild = self.bot.get_guild(ONAY_SUNUCU_ID)
        if guild:
            await self._davetleri_guncelle(guild)
            await self._giris_panelini_denetle(guild)
            logger.info(f"SunucuOnay hazır: {guild.name} ({len(self.davet_onbellegi.get(guild.id, {}))} davet önbelleklendi)")

    @commands.Cog.listener()
    async def on_invite_create(self, invite: discord.Invite):
        if invite.guild.id == ONAY_SUNUCU_ID:
            await self._davetleri_guncelle(invite.guild)

    @commands.Cog.listener()
    async def on_invite_delete(self, invite: discord.Invite):
        if invite.guild.id == ONAY_SUNUCU_ID:
            await self._davetleri_guncelle(invite.guild)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.guild.id != ONAY_SUNUCU_ID or member.bot:
            return

        guild = member.guild
        eski_davetler = self.davet_onbellegi.get(guild.id, {})
        kullanilan_davet = None
        kuran_sahip_mi = False

        try:
            yeni_davetler = await guild.invites()
            for inv in yeni_davetler:
                eski = eski_davetler.get(inv.code)
                if eski and inv.uses > eski['uses']:
                    kullanilan_davet = inv
                    break
            self.davet_onbellegi[guild.id] = {
                inv.code: {'uses': inv.uses, 'inviter_id': inv.inviter.id if inv.inviter else None}
                for inv in yeni_davetler
            }
        except Exception as e:
            logger.warning(f"Katılımda davet kontrolü hatası: {e}")

        onay_kanali = next((c for c in guild.text_channels if ONAY_KANAL_ADI in c.name), None)

        if kullanilan_davet and kullanilan_davet.inviter:
            if kullanilan_davet.inviter.id == ONAY_KURUCU_ID and kullanilan_davet.code != ONAY_GENEL_DAVET_KODU:
                kuran_sahip_mi = True

        if kuran_sahip_mi:
            # Kurucu şahsi daveti -> Otomatik onay
            secilen_dil = _dil_al(member.id)
            rol_topluluk = discord.utils.get(guild.roles, name=ROL_TOPLULUK)
            rol_tr = discord.utils.get(guild.roles, name=ROL_TR)
            rol_en = discord.utils.get(guild.roles, name=ROL_EN)
            
            roller = [r for r in (rol_topluluk, rol_tr if secilen_dil != 'en' else rol_en) if r]
            if roller:
                await member.add_roles(*roller, reason="Kurucunun şahsi davetiyle katıldı (Otomatik Onay)")

            if onay_kanali:
                embed = discord.Embed(
                    title="✨ Doğrudan Davet Edilen Üye Katıldı",
                    color=discord.Color.gold(),
                    description=(
                        f"{member.mention} (`{member.name}` - ID: `{member.id}`)\n\n"
                        f"Bu üye bizzat **Kurucu (<@{ONAY_KURUCU_ID}>)** davetiyle "
                        f"(`{kullanilan_davet.code}`) katıldığı için **otomatik olarak onaylandı**."
                    ),
                    timestamp=datetime.datetime.now(datetime.timezone.utc)
                )
                embed.set_thumbnail(url=member.display_avatar.url)
                await onay_kanali.send(embed=embed)
            logger.info(f"Otomatik onaylandı (Kurucu daveti): {member.name}")
            return

        # Genel davet / web -> Onay bekleme akışı
        secilen_dil = _dil_al(member.id)
        dil_etiket = {"tr": "🇹🇷 Türkçe", "en": "🇬🇧 English", "both": "🌐 Her İkisi / Both"}.get(secilen_dil, "Henüz seçmedi (Varsayılan Türkçe)")

        if onay_kanali:
            embed = discord.Embed(
                title="⏳ Yeni Üye Onay Bekliyor",
                color=discord.Color.from_rgb(241, 196, 15),
                description=(
                    f"**Üye:** {member.mention} (`{member.name}`)\n"
                    f"**ID:** `{member.id}`\n"
                    f"**Hesap Kuruluş:** <t:{int(member.created_at.timestamp())}:R>\n"
                    f"**Davet:** `{kullanilan_davet.code if kullanilan_davet else 'Web/Genel Davet'}`\n"
                    f"**Seçtiği Dil:** {dil_etiket}\n\n"
                    "Bu üye şu anda hiçbir odayı görememektedir. Sunucuya kabul etmek veya reddetmek için aşağıdaki butonları kullanabilirsiniz."
                ),
                timestamp=datetime.datetime.now(datetime.timezone.utc)
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            view = onay_gorunumu_olustur(member.id)
            onay_mesaji = await onay_kanali.send(content=f"<@{ONAY_KURUCU_ID}> yeni bir üye onay bekliyor!", embed=embed, view=view)
            _onay_mesaj_kaydet(member.id, onay_mesaji.id)
            logger.info(f"Onay bekleyen üye: {member.name} (Dil: {secilen_dil})")

    # ── Slash Komutları ────────────────────────────

    @app_commands.command(name="onayla", description="Onay bekleyen bir üyeyi onaylayıp kanalları açar")
    @app_commands.describe(
        uye="Onaylanacak üye",
        rol="Verilecek yetki rolü",
        dil="Atanacak dil (Varsayılan: Üyenin tercihi)"
    )
    @app_commands.choices(
        rol=[
            app_commands.Choice(name="Topluluk", value="topluluk"),
            app_commands.Choice(name="Maker / Geliştirici", value="maker")
        ],
        dil=[
            app_commands.Choice(name="Otomatik (Üyenin Tercihi)", value="auto"),
            app_commands.Choice(name="🇹🇷 Türkçe", value="tr"),
            app_commands.Choice(name="🇬🇧 English", value="en"),
            app_commands.Choice(name="🌐 Her İkisi / Both", value="both")
        ]
    )
    async def onayla_komutu(self, interaction: discord.Interaction, uye: discord.Member, rol: str = "topluluk", dil: str = "auto"):
        if interaction.guild.id != ONAY_SUNUCU_ID:
            return await interaction.response.send_message("Bu komut bu sunucuda kullanılamaz.", ephemeral=True)
        if not _kurucu_mu(interaction.user):
            return await interaction.response.send_message("❌ Yalnızca kurucu onay verebilir.", ephemeral=True)

        guild = interaction.guild
        secilen_dil = _dil_al(uye.id) if dil == "auto" else dil
        _dil_kaydet(uye.id, secilen_dil)

        await _onay_rolleri_ver(guild, uye, rol, secilen_dil, f"{interaction.user} tarafından slash komutuyla onaylandı")

        dil_adi = DIL_ETIKETLERI.get(secilen_dil, secilen_dil)
        await interaction.response.send_message(
            f"✅ {uye.mention} onaylandı!\nRol: **{ROL_MAKER if rol == 'maker' else ROL_TOPLULUK}** | Dil: **{dil_adi}**"
        )

        try:
            if secilen_dil == "en":
                await uye.send(f"🎉 Welcome to **{guild.name}**! Your access has been approved. The English channels are now open.")
            else:
                await uye.send(f"🎉 **{guild.name}** sunucusuna girişiniz onaylandı! Kanallar erişiminize açıldı.")
        except Exception:
            pass

    @app_commands.command(name="reddet", description="Onay bekleyen bir üyeyi reddeder ve sunucudan atar")
    @app_commands.describe(uye="Reddedilecek üye", sebep="Reddetme sebebi")
    async def reddet_komutu(self, interaction: discord.Interaction, uye: discord.Member, sebep: str = "Onaylanmadı"):
        if interaction.guild.id != ONAY_SUNUCU_ID:
            return await interaction.response.send_message("Bu komut bu sunucuda kullanılamaz.", ephemeral=True)
        if not _kurucu_mu(interaction.user):
            return await interaction.response.send_message("❌ Yalnızca kurucu ret işlemi yapabilir.", ephemeral=True)

        await uye.kick(reason=f"{interaction.user} tarafından reddedildi: {sebep}")
        await interaction.response.send_message(f"❌ {uye.mention} reddedildi ve sunucudan atıldı.")

    @app_commands.command(name="dilpaneli", description="🚪・giris kanalındaki dil seçim panelini yeniden gönderir")
    async def dilpaneli_komutu(self, interaction: discord.Interaction):
        if interaction.guild.id != ONAY_SUNUCU_ID:
            return await interaction.response.send_message("Bu komut bu sunucuda kullanılamaz.", ephemeral=True)
        if not _kurucu_mu(interaction.user):
            return await interaction.response.send_message("❌ Yalnızca kurucu kullanabilir.", ephemeral=True)

        await interaction.response.defer(ephemeral=True)
        await self._giris_panelini_denetle(interaction.guild)
        await interaction.followup.send("✅ Dil seçim paneli kontrol edildi ve güncellendi.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(SunucuOnay(bot))
