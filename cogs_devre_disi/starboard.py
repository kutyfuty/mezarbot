"""
Starboard — Belirli sayıda ⭐ alan mesajları ayrı bir kanala taşır.

• Varsayılan eşik: 3 yıldız
• Kendi mesajına yıldız sayılmaz
• Starboard kanalındaki mesajlar tekrar starboard'a düşmez
• Aynı mesaj için yıldız sayısı arttıkça starboard mesajı güncellenir
"""
import discord
from discord.ext import commands
from discord import app_commands
import sqlite3
import asyncio
import time
import logging
from database import db
from arayuz import Renkler

logger = logging.getLogger('MezarBot.Starboard')

# Global ayarlar (sunucu başına override edilebilir)
VARSAYILAN_ESIK = 3
YILDIZ_EMOJI = '⭐'
STARBOARD_KANAL_AD = 'yıldız'  # kanal bulunamazsa bu adla aranır


class Starboard(commands.Cog):
    """⭐ Yıldız Panosu"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._init_db()

    # ── DB kurulumu ─────────────────────────────────────────────
    def _init_db(self):
        """Senkron DB kurulumu. check_same_thread=False sayesinde main thread'de güvenli."""
        c = db.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS starboard (
                message_id       INTEGER PRIMARY KEY,
                channel_id       INTEGER NOT NULL,
                author_id        INTEGER NOT NULL,
                stars            INTEGER DEFAULT 0,
                starboard_msg_id INTEGER,
                created_at       REAL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS starboard_ayarlar (
                guild_id INTEGER PRIMARY KEY,
                esik     INTEGER DEFAULT 3,
                kanal_id INTEGER
            )
        """)
        # Çok sunuculu: eski kurulumlarda starboard.guild_id yok (sadece ekleme, veri silinmez)
        try:
            c.execute("ALTER TABLE starboard ADD COLUMN guild_id INTEGER")
        except sqlite3.OperationalError:
            pass
        c.execute("CREATE INDEX IF NOT EXISTS idx_starboard_guild ON starboard(guild_id)")
        db.commit()

    # ── Ayar getter ─────────────────────────────────────────────
    def _ayar_getir(self, guild_id: int):
        c = db.cursor()
        c.execute("SELECT esik, kanal_id FROM starboard_ayarlar WHERE guild_id = ?", (guild_id,))
        row = c.fetchone()
        if row:
            return row['esik'], row['kanal_id']
        return VARSAYILAN_ESIK, None

    def _ayar_kaydet(self, guild_id: int, esik: int = None, kanal_id: int = None):
        c = db.cursor()
        mevcut_esik, mevcut_kanal = self._ayar_getir(guild_id)
        yeni_esik = esik if esik is not None else mevcut_esik
        yeni_kanal = kanal_id if kanal_id is not None else mevcut_kanal
        c.execute("""
            INSERT INTO starboard_ayarlar (guild_id, esik, kanal_id) VALUES (?, ?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET esik = excluded.esik, kanal_id = excluded.kanal_id
        """, (guild_id, yeni_esik, yeni_kanal))
        db.commit()

    # ── Kanal bul ──────────────────────────────────────────────
    async def _kanal_bul(self, guild: discord.Guild, kanal_id: int = None):
        if kanal_id:
            ch = guild.get_channel(kanal_id)
            if ch: return ch
        # "yıldız" adlı kanal ara
        for ch in guild.text_channels:
            if ch.name.lower() in (STARBOARD_KANAL_AD, 'starboard', 'yildiz'):
                return ch
        return None

    # ── Embed oluştur ──────────────────────────────────────────
    def _embed(self, message: discord.Message, stars: int) -> discord.Embed:
        e = discord.Embed(
            color=0xF1C40F,
            description=message.content[:1900] if message.content else "*[Embed/medya içeriği]*",
            timestamp=message.created_at
        )
        e.set_author(
            name=message.author.display_name,
            icon_url=message.author.display_avatar.url
        )
        e.add_field(name="📎 Kaynak", value=f"[Mesaja atla]({message.jump_url})", inline=False)
        # ilk attachment görselini göster
        for att in message.attachments:
            if att.content_type and att.content_type.startswith('image/'):
                e.set_image(url=att.url)
                break
        e.set_footer(text=f"{stars} ⭐  •  #{message.channel.name}")
        return e

    # ── Reaction event ────────────────────────────────────────
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.emoji.name != YILDIZ_EMOJI:
            return
        # Kendi yıldızını sayma
        if payload.member and payload.member.bot:
            return
        await self._handle_star(payload)

    @commands.Cog.listener()
    async def on_raw_reaction_clear(self, payload: discord.RawReactionClearEvent):
        """Mesajın TÜM tepkileri temizlenirse starboard mesajını sil.
        (Eskiden payload.emoji'ye erişiyordu — bu event'te emoji yok → her seferinde AttributeError.)"""
        await self._starboard_kaydini_sil(payload.guild_id, payload.message_id)

    @commands.Cog.listener()
    async def on_raw_reaction_clear_emoji(self, payload: discord.RawReactionClearEmojiEvent):
        """Sadece ⭐ tepkileri temizlenirse starboard mesajını sil."""
        if payload.emoji.name == YILDIZ_EMOJI:
            await self._starboard_kaydini_sil(payload.guild_id, payload.message_id)

    async def _starboard_kaydini_sil(self, guild_id, message_id):
        c = db.cursor()
        c.execute("SELECT starboard_msg_id FROM starboard WHERE message_id = ?", (message_id,))
        row = c.fetchone()
        if not row:
            return
        guild = self.bot.get_guild(guild_id) if guild_id else None
        if guild and row['starboard_msg_id']:
            # Starboard mesajı kaynak kanalda değil, starboard kanalındadır
            _, kanal_id = self._ayar_getir(guild.id)
            sb_kanal = await self._kanal_bul(guild, kanal_id)
            if sb_kanal:
                try:
                    msg = await sb_kanal.fetch_message(row['starboard_msg_id'])
                    await msg.delete()
                except (discord.NotFound, discord.HTTPException):
                    pass
        c.execute("DELETE FROM starboard WHERE message_id = ?", (message_id,))
        db.commit()

    # ── Ana mantık ─────────────────────────────────────────────
    async def _handle_star(self, payload):
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        # Çok sunuculu: bot izinsiz kanal OLUŞTURMAZ. Sunucu /starboard-kanal ile ayarlamadıysa ve
        # 'yıldız' / 'starboard' adlı bir kanal da yoksa özellik bu sunucuda atlanır
        # (mesaj bile çekilmez — gereksiz API çağrısı yok).
        esik, kanal_id = self._ayar_getir(guild.id)
        starboard_kanal = await self._kanal_bul(guild, kanal_id)
        if not starboard_kanal:
            return
        # Mesajı çek
        channel = guild.get_channel(payload.channel_id)
        if not channel:
            return
        # Starboard kanalındaki mesajı tekrar starboard'lama
        if channel.id == starboard_kanal.id:
            return
        try:
            message = await channel.fetch_message(payload.message_id)
        except (discord.NotFound, discord.HTTPException):
            return

        # Yıldız sayısını say (raw count, sadece ⭐ olan)
        star_count = 0
        for r in message.reactions:
            if r.emoji == YILDIZ_EMOJI or (hasattr(r.emoji, 'name') and r.emoji.name == YILDIZ_EMOJI):
                star_count = r.count
                break

        if star_count < esik:
            return

        # DB kontrol
        c = db.cursor()
        c.execute("SELECT starboard_msg_id, stars FROM starboard WHERE message_id = ?", (message.id,))
        row = c.fetchone()

        embed = self._embed(message, star_count)

        if row:
            # Mesaj zaten starboard'da — güncelle
            try:
                sb_msg = await starboard_kanal.fetch_message(row['starboard_msg_id'])
                await sb_msg.edit(embed=embed)
            except (discord.NotFound, discord.HTTPException):
                sb_msg = None
            if not sb_msg:
                sb_msg = await starboard_kanal.send(embed=embed)
                c.execute("UPDATE starboard SET starboard_msg_id = ?, stars = ? WHERE message_id = ?",
                          (sb_msg.id, star_count, message.id))
        else:
            # Yeni starboard entry
            sb_msg = await starboard_kanal.send(embed=embed)
            c.execute("""INSERT INTO starboard
                (message_id, channel_id, author_id, stars, starboard_msg_id, created_at, guild_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (message.id, message.channel.id, message.author.id, star_count, sb_msg.id, time.time(), guild.id))
        c.execute("UPDATE starboard SET stars = ? WHERE message_id = ?", (star_count, message.id))
        db.commit()

    # ── Slash komutlar (admin) ─────────────────────────────────
    @app_commands.command(name="starboard-esik", description="Yıldız eşiğini ayarla (mesajın taşınması için kaç ⭐ gerekli)")
    @app_commands.describe(esik="Yeni eşik (1-50)")
    @app_commands.default_permissions(administrator=True)
    async def slash_esik(self, interaction: discord.Interaction, esik: int):
        if not 1 <= esik <= 50:
            return await interaction.response.send_message("❌ Eşik 1-50 arası olmalı.", ephemeral=True)
        await asyncio.to_thread(self._ayar_kaydet, interaction.guild.id, esik=esik)
        await interaction.response.send_message(f"✅ Yıldız eşiği **{esik}** olarak ayarlandı.", ephemeral=True)

    @app_commands.command(name="starboard-kanal", description="Yıldız kanalını ayarla")
    @app_commands.describe(kanal="Yıldız kanalı (boş bırakırsan 'yıldız' adlı kanal kullanılır)")
    @app_commands.default_permissions(administrator=True)
    async def slash_kanal(self, interaction: discord.Interaction, kanal: discord.TextChannel = None):
        await asyncio.to_thread(self._ayar_kaydet, interaction.guild.id, kanal_id=kanal.id if kanal else None)
        hedef = kanal.mention if kanal else f"`#{STARBOARD_KANAL_AD}` (otomatik)"
        await interaction.response.send_message(f"✅ Yıldız kanalı {hedef} olarak ayarlandı.", ephemeral=True)

    @app_commands.command(name="starboard-durum", description="Starboard ayarlarını gösterir")
    async def slash_durum(self, interaction: discord.Interaction):
        esik, kanal_id = await asyncio.to_thread(self._ayar_getir, interaction.guild.id)
        kanal = await self._kanal_bul(interaction.guild, kanal_id)
        c = db.cursor()
        c.execute("SELECT COUNT(*) as n, COALESCE(SUM(stars), 0) as total FROM starboard WHERE guild_id = ?",
                  (interaction.guild.id,))
        row = c.fetchone()
        e = discord.Embed(title="⭐ Starboard Durumu", color=0xF1C40F)
        e.add_field(name="Eşik", value=f"**{esik}** ⭐", inline=True)
        e.add_field(name="Kanal", value=kanal.mention if kanal else "❌ Ayarlı değil — `/starboard-kanal` ile ayarla (özellik kapalı)", inline=True)
        e.add_field(name="Taşınan mesaj", value=f"**{row['n']}**", inline=True)
        e.add_field(name="Toplam yıldız", value=f"**{row['total']}** ⭐", inline=True)
        await interaction.response.send_message(embed=e, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Starboard(bot))