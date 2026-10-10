import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import datetime
import logging
from database import db, yonetici_kontrol, sunucu_ayar_al, sunucu_ayar_guncelle
from arayuz import Renkler, premium_embed, AYIRICI, bilgi_kutusu
from yapilandirma import SAHIP_ID  # itiraf logları bot sahibine gider (config.json → sahip_id)

logger = logging.getLogger('MezarBot.Itiraf')

ITIRAF_MAKS = 1000  # !itiraf komutunun kabul ettiği en uzun mesaj; embed'lerde de bu sınır uygulanır


def _itiraf_listesi_embed(rows):
    """Mod listesi embed'i. Discord sınırları: en fazla 25 alan ve toplam ~6000 karakter."""
    e = discord.Embed(title=f"📜 İtiraflar ({len(rows)})", color=Renkler.BILGI)
    gosterilen = 0
    for r in rows:
        tur = "🕵️ Gizli" if r['gizli'] else "👤 Açık"
        tarih = r['tarih'][:16].replace('T', ' ')
        uye_bilgi = f"<@{r['user_id']}>" if not r['gizli'] else f"`{r['user_id']}`"
        ad = f"#{r['id']} • {tur} • {tarih} • {uye_bilgi}"
        deger = r['mesaj'][:500] + ('…' if len(r['mesaj']) > 500 else '')
        if len(e.fields) >= 25 or len(e) + len(ad) + len(deger) > 5700:
            break
        e.add_field(name=ad, value=deger, inline=False)
        gosterilen += 1
    alt = "Sadece moderatörler görebilir • Gizli itiraflarda kullanıcı ID görünür"
    if gosterilen < len(rows):
        alt = f"{gosterilen}/{len(rows)} kayıt gösteriliyor (Discord sınırı) • {alt}"
    e.set_footer(text=alt)
    return e


def _init_db():
    """İtiraflar tablosunu oluştur."""
    c = db.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS itiraflar (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id    INTEGER NOT NULL,
            user_id     INTEGER NOT NULL,
            gizli       INTEGER DEFAULT 1,
            mesaj       TEXT NOT NULL,
            tarih       TEXT NOT NULL
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_itiraf_guild ON itiraflar(guild_id, tarih DESC)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_itiraf_user ON itiraflar(user_id)")
    db.commit()


_init_db()


class ItirafButonlari(discord.ui.View):
    def __init__(self, bot, user, mesaj, kanal_id, sunucu_id):
        super().__init__(timeout=60)
        self.bot = bot
        self.user = user
        self.mesaj = mesaj
        self.kanal_id = kanal_id
        self.sunucu_id = sunucu_id

    async def itiraf_gonder(self, interaction: discord.Interaction, gizli: bool):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("❌ Bu itiraf senin değil!", ephemeral=True)
        kanal = self.bot.get_channel(self.kanal_id)
        if not kanal:
            return await interaction.response.send_message("❌ İtiraf kanalı bulunamadı. Lütfen yöneticiye bildirin.", ephemeral=True)

        baslik = "🕵️ GİZLİ KULLANICI" if gizli else f"👤 {self.user.name}"
        renk = Renkler.BILGI if gizli else Renkler.BASARI

        embed = discord.Embed(color=renk, timestamp=datetime.datetime.now())
        embed.set_author(name="📢 Yeni Bir İtiraf Geldi!")
        embed.description = f"**{baslik}:**\n{AYIRICI}\n\n>>> {self.mesaj[:ITIRAF_MAKS]}"
        embed.set_footer(text="MezarBot • DM'den !itiraf <mesaj> ile itiraf gönder")

        if not gizli:
            embed.set_thumbnail(url=self.user.display_avatar.url)

        await kanal.send(embed=embed)
        await interaction.response.send_message(f"✅ İtirafınız başarıyla {'gizli' if gizli else 'açık'} olarak gönderildi!", ephemeral=True)

        # ── DB'ye kaydet (kalıcılık) ─────────────────────────────
        try:
            c = db.cursor()
            c.execute("""INSERT INTO itiraflar (guild_id, user_id, gizli, mesaj, tarih)
                         VALUES (?, ?, ?, ?, ?)""",
                      (self.sunucu_id, self.user.id, 1 if gizli else 0, self.mesaj,
                       datetime.datetime.now().isoformat()))
            db.commit()
        except Exception as e:
            logger.error(f"DB kayıt hatası: {e}")

        # Sahibe log gönder
        owner = self.bot.get_user(SAHIP_ID) if SAHIP_ID else None
        if owner:
            log_embed = discord.Embed(color=Renkler.NOTR, timestamp=datetime.datetime.now())
            log_embed.set_author(name="🕵️ İtiraf Logu")
            log_embed.description = (
                f"{bilgi_kutusu(('👤', 'Gönderen', f'{self.user.mention} (`{self.user.id}`)'), ('🏛️', 'Sunucu', f'`{self.sunucu_id}`'), ('🔒', 'Tür', 'Gizli' if gizli else 'Açık'))}\n\n"
                f">>> {self.mesaj[:ITIRAF_MAKS]}"
            )
            try:
                await owner.send(embed=log_embed)
            except (discord.Forbidden, discord.HTTPException):
                pass

        self.stop()

    @discord.ui.button(label="Gizli İtiraf Et", style=discord.ButtonStyle.secondary, emoji="🕵️")
    async def gizli_itiraf(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.itiraf_gonder(interaction, True)

    @discord.ui.button(label="Açık İtiraf Et", style=discord.ButtonStyle.success, emoji="👤")
    async def acik_itiraf(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.itiraf_gonder(interaction, False)


class ItirafSunucuSec(discord.ui.View):
    def __init__(self, bot, user, mesaj, secenekler):
        super().__init__(timeout=60)
        self.bot = bot
        self.user = user
        self.mesaj = mesaj
        self.secim = discord.ui.Select(
            placeholder="İtirafın hangi sunucuya gitsin?",
            min_values=1, max_values=1,
            options=[discord.SelectOption(label=ad[:100], value="%d:%d" % (gid, kid)) for gid, ad, kid in secenekler[:25]]
        )
        self.secim.callback = self._secildi
        self.add_item(self.secim)

    async def _secildi(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("❌ Bu menü senin değil!", ephemeral=True)
        gid_s, kid_s = self.secim.values[0].split(":")
        view = ItirafButonlari(self.bot, self.user, self.mesaj, int(kid_s), int(gid_s))
        embed = premium_embed(
            "❓ İtiraf Türünü Seçin",
            "İtirafın seçtiğin sunucuya gönderilecek. Nasıl göndermek istersin?\n\n**Mesajınız:**\n" + self.mesaj,
            renk=Renkler.BILGI
        )
        await interaction.response.edit_message(embed=embed, view=view)


class Itiraf(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(description="İtiraf kanalını ayarla")
    @app_commands.default_permissions(manage_guild=True)
    @commands.guild_only()
    @commands.check(yonetici_kontrol)
    async def itirafayarla(self, ctx, kanal: discord.TextChannel = None):
        """[Yönetici] Bulunduğunuz kanalı veya etiketlediğiniz kanalı bu sunucunun itiraf kanalı yapar."""
        kanal = kanal or ctx.channel
        sunucu_ayar_guncelle(ctx.guild.id, itiraf_kanal_id=kanal.id)
        embed = premium_embed("✅ İtiraf Kanalı Ayarlandı", f"Artık bu sunucudaki itiraflar {kanal.mention} kanalına düşecek.", renk=Renkler.BASARI)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="itiraf", description="İtiraf gönder (gizli veya açık)")
    @app_commands.describe(mesaj="Göndermek istediğin itiraf mesajı")
    async def itiraf(self, ctx, *, mesaj: str):
        """İtiraf etmek için kullanılır. Sunucuda slash (/itiraf) veya bota DM üzerinden kullanılabilir."""
        if len(mesaj) > ITIRAF_MAKS:
            return await ctx.send(f"❌ İtiraf mesajı çok uzun! (Maks {ITIRAF_MAKS} karakter)", ephemeral=True)

        if ctx.guild:
            if ctx.interaction is None:
                # Prefix ile sunucu kanalına yazıldıysa gizlilik için mesajı sil ve uyar
                try:
                    await ctx.message.delete()
                except (discord.NotFound, discord.Forbidden):
                    pass
                return await ctx.send("❌ Gizliliğiniz için sunucu sohbetinde `!itiraf` kullanamazsınız (mesajınız herkesçe görülür). Lütfen `/itiraf` slash komutunu kullanın veya bota DM atın!", delete_after=10)

            # Slash komutu (/itiraf) ile sunucuda çağrıldıysa:
            ayar = sunucu_ayar_al(ctx.guild.id)
            if not ayar or not ayar.get('itiraf_kanal_id'):
                return await ctx.send("❌ Bu sunucuda itiraf kanalı ayarlanmamış.", ephemeral=True)

            view = ItirafButonlari(self.bot, ctx.author, mesaj, ayar['itiraf_kanal_id'], ctx.guild.id)
            embed = premium_embed(
                "❓ İtiraf Türünü Seçin",
                f"İtirafın bu sunucunun itiraf kanalına gönderilecek. Nasıl göndermek istersin?\n\n**Mesajınız:**\n{mesaj}",
                renk=Renkler.BILGI
            )
            return await ctx.send(embed=embed, view=view, ephemeral=True)

        # Kullanıcının ortak sunucularındaki TÜM itiraf kanallarını topla
        secenekler = []  # (guild_id, guild_name, kanal_id)
        for guild in self.bot.guilds:
            if guild.get_member(ctx.author.id):
                ayar = sunucu_ayar_al(guild.id)
                if ayar and ayar.get('itiraf_kanal_id'):
                    secenekler.append((guild.id, guild.name, ayar['itiraf_kanal_id']))

        if not secenekler:
            return await ctx.send("❌ Herhangi bir sunucuda itiraf kanalı ayarlanmamış veya bu botun bulunduğu bir sunucuda değilsiniz.")

        if len(secenekler) == 1:
            target_sunucu_id, sunucu_adi, itiraf_kanal_id = secenekler[0]
            view = ItirafButonlari(self.bot, ctx.author, mesaj, itiraf_kanal_id, target_sunucu_id)
            embed = premium_embed(
                "❓ İtiraf Türünü Seçin",
                f"İtirafın **{sunucu_adi}** sunucusuna gönderilecek. Nasıl göndermek istersin?\n\n**Mesajınız:**\n{mesaj}",
                renk=Renkler.BILGI
            )
            return await ctx.send(embed=embed, view=view)

        view = ItirafSunucuSec(self.bot, ctx.author, mesaj, secenekler)
        embed = premium_embed(
            "🏛️ İtiraf Hangi Sunucuya Gitsin?",
            f"Birden fazla sunucuda itiraf kanalı ayarlı. Önce sunucuyu seç, sonra gizli/açık belirle.\n\n**Mesajınız:**\n{mesaj}",
            renk=Renkler.BILGI
        )
        await ctx.send(embed=embed, view=view)

    # ── Yeni: İtiraf yönetim komutları ──────────────────────────
    @commands.has_permissions(manage_messages=True)
    @commands.command(name="itiraflar")
    async def itiraflar_prefix(self, ctx, uye: discord.Member = None, limit: int = 10):
        """Son itirafları listeler (mod). İsteğe bağlı: @üye ile o kullanıcının itiraflarını gösterir."""
        if not 1 <= limit <= 50:
            return await ctx.send("❌ Limit 1-50 arası olmalı.", delete_after=5)

        def _q():
            c = db.cursor()
            if uye:
                c.execute("""SELECT id, user_id, gizli, mesaj, tarih FROM itiraflar
                             WHERE guild_id = ? AND user_id = ?
                             ORDER BY id DESC LIMIT ?""",
                          (ctx.guild.id, uye.id, limit))
            else:
                c.execute("""SELECT id, user_id, gizli, mesaj, tarih FROM itiraflar
                             WHERE guild_id = ?
                             ORDER BY id DESC LIMIT ?""",
                          (ctx.guild.id, limit))
            return c.fetchall()

        rows = await asyncio.to_thread(_q)
        if not rows:
            return await ctx.send("📭 İtiraf kaydı yok.")
        await ctx.send(embed=_itiraf_listesi_embed(rows))

    @commands.has_permissions(manage_messages=True)
    @commands.command(name="itiraf-sil", aliases=["itirafsil"])
    async def itiraf_sil_prefix(self, ctx, itiraf_id: int):
        """İtiraf kaydını siler (mod). Sadece DB kaydını siler, gönderilen embed'i etkilemez."""
        def _q():
            c = db.cursor()
            c.execute("DELETE FROM itiraflar WHERE id = ? AND guild_id = ?", (itiraf_id, ctx.guild.id))
            db.commit()
            return c.rowcount
        n = await asyncio.to_thread(_q)
        if n:
            await ctx.send(f"🗑️ İtiraf #{itiraf_id} silindi.")
        else:
            await ctx.send(f"❌ İtiraf #{itiraf_id} bulunamadı.", delete_after=5)

    # ── Slash komutlar ──────────────────────────────────────────
    @app_commands.command(name="itiraflar", description="[Mod] Son itirafları listeler")
    @app_commands.describe(üye="Belirli bir üyenin itirafları (boş = tümü)", limit="Gösterilecek kayıt sayısı (1-50)")
    @app_commands.default_permissions(manage_messages=True)
    async def slash_itiraflar(self, interaction: discord.Interaction, üye: discord.Member = None, limit: int = 10):
        if not 1 <= limit <= 50:
            return await interaction.response.send_message("❌ Limit 1-50 arası olmalı.", ephemeral=True)
        await interaction.response.defer()

        def _q():
            c = db.cursor()
            if üye:
                c.execute("""SELECT id, user_id, gizli, mesaj, tarih FROM itiraflar
                             WHERE guild_id = ? AND user_id = ?
                             ORDER BY id DESC LIMIT ?""",
                          (interaction.guild.id, üye.id, limit))
            else:
                c.execute("""SELECT id, user_id, gizli, mesaj, tarih FROM itiraflar
                             WHERE guild_id = ?
                             ORDER BY id DESC LIMIT ?""",
                          (interaction.guild.id, limit))
            return c.fetchall()
        rows = await asyncio.to_thread(_q)
        if not rows:
            return await interaction.followup.send("📭 İtiraf kaydı yok.")
        await interaction.followup.send(embed=_itiraf_listesi_embed(rows))

    @app_commands.command(name="itiraf-sil", description="[Mod] İtiraf kaydını siler (sadece DB, embed kalır)")
    @app_commands.describe(id="Silinecek itirafın ID'si")
    @app_commands.default_permissions(manage_messages=True)
    async def slash_itiraf_sil(self, interaction: discord.Interaction, id: int):
        def _q():
            c = db.cursor()
            c.execute("DELETE FROM itiraflar WHERE id = ? AND guild_id = ?", (id, interaction.guild.id))
            db.commit()
            return c.rowcount
        n = await asyncio.to_thread(_q)
        if n:
            await interaction.response.send_message(f"🗑️ İtiraf #{id} silindi.")
        else:
            await interaction.response.send_message(f"❌ İtiraf #{id} bulunamadı.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Itiraf(bot))
