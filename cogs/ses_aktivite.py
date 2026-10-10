"""
Ses Aktivite — Kullanıcıların ses kanalında kalma sürelerini izler,
toplam/haftalık/aylık leaderboard gösterir.

• Her VC giriş-çıkış kaydedilir
• Sadece "insan" kullanıcılar (bot'lar hariç)
• Sunucu başına bağımsız leaderboard
• Komutlar:
    /ses-top      → sunucu top 10
    /ses-hafta    → bu hafta top 10
    /ses-ben      → kişisel istatistik
    /ses-kanal    → sadece hangi kanal(lar) izlensin (admin, opsiyonel)
"""
import discord
from discord.ext import commands, tasks
from discord import app_commands
import time
import asyncio
import logging
from collections import defaultdict
from database import db
from arayuz import sayi_formatla, Renkler

logger = logging.getLogger('MezarBot.SesAktivite')


class SesAktivite(commands.Cog):
    """🎙️ Ses Aktivite Leaderboard"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # user_id -> {guild_id, kanal_id, giris_ts}
        self._aktif = {}
        self._init_db()

    # ── DB ─────────────────────────────────────────────────────
    def _init_db(self):
        c = db.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS ses_aktivite (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                guild_id    INTEGER NOT NULL,
                kanal_id    INTEGER NOT NULL,
                giris_ts    REAL NOT NULL,
                cikis_ts    REAL NOT NULL,
                sure_sn     INTEGER NOT NULL
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_ses_user_guild ON ses_aktivite(user_id, guild_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_ses_guild_tarih ON ses_aktivite(guild_id, giris_ts)")
        c.execute("""
            CREATE TABLE IF NOT EXISTS ses_kanal_ayar (
                guild_id  INTEGER NOT NULL,
                kanal_id  INTEGER NOT NULL,
                PRIMARY KEY (guild_id, kanal_id)
            )
        """)
        db.commit()

    # ── Event ──────────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before, after):
        # Botları sayma
        if member.bot:
            return
        # Sunucu ayarı: belirli kanallar mı izlenecek?
        def _izinli_kanal_mi(kanal_id):
            c = db.cursor()
            c.execute("SELECT 1 FROM ses_kanal_ayar WHERE guild_id = ? AND kanal_id = ?",
                      (member.guild.id, kanal_id))
            row = c.fetchone()
            if row:
                return True
            # Hiç ayar yoksa TÜM kanalları izle
            c.execute("SELECT COUNT(*) as n FROM ses_kanal_ayar WHERE guild_id = ?", (member.guild.id,))
            return c.fetchone()['n'] == 0

        # Giriş
        if after.channel and (not before.channel or before.channel.id != after.channel.id):
            if not _izinli_kanal_mi(after.channel.id):
                return
            self._aktif[member.id] = {
                'guild_id': member.guild.id,
                'kanal_id': after.channel.id,
                'giris_ts': time.time()
            }

        # Çıkış
        if before.channel and (not after.channel or before.channel.id != after.channel.id):
            session = self._aktif.pop(member.id, None)
            if not session or session['guild_id'] != member.guild.id:
                return
            sure_sn = int(time.time() - session['giris_ts'])
            if sure_sn < 5:  # 5 saniyeden kısa giriş-çıkışları loglama (join spam)
                return
            c = db.cursor()
            c.execute("""INSERT INTO ses_aktivite
                (user_id, guild_id, kanal_id, giris_ts, cikis_ts, sure_sn)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (member.id, session['guild_id'], session['kanal_id'],
                 session['giris_ts'], time.time(), sure_sn))
            db.commit()

    sesstat_grup = app_commands.Group(name="sesstat", description="Ses kanalı istatistikleri ve süre sıralaması")

    # ── Slash: leaderboard ─────────────────────────────────────
    @sesstat_grup.command(name="top", description="Sunucuda en çok ses kanalında kalan kullanıcılar (tüm zamanlar)")
    async def slash_top(self, interaction: discord.Interaction):
        await self._leaderboard_gonder(interaction, sure_gun=None, baslik="🏆 Ses Kanalı Şampiyonları (Tüm Zamanlar)")

    @sesstat_grup.command(name="hafta", description="Bu hafta en çok ses kanalında kalan kullanıcılar")
    async def slash_hafta(self, interaction: discord.Interaction):
        await self._leaderboard_gonder(interaction, sure_gun=7, baslik="📅 Bu Hafta Ses Şampiyonları")

    @sesstat_grup.command(name="ay", description="Bu ay en çok ses kanalında kalan kullanıcılar")
    async def slash_ay(self, interaction: discord.Interaction):
        await self._leaderboard_gonder(interaction, sure_gun=30, baslik="📆 Bu Ay Ses Şampiyonları")

    async def _leaderboard_gonder(self, interaction, sure_gun, baslik):
        await interaction.response.defer()
        guild = interaction.guild
        def _q():
            c = db.cursor()
            if sure_gun is None:
                c.execute("""SELECT user_id, SUM(sure_sn) as total, COUNT(*) as sessions
                             FROM ses_aktivite WHERE guild_id = ?
                             GROUP BY user_id ORDER BY total DESC LIMIT 10""",
                          (guild.id,))
            else:
                ts = time.time() - sure_gun * 86400
                c.execute("""SELECT user_id, SUM(sure_sn) as total, COUNT(*) as sessions
                             FROM ses_aktivite WHERE guild_id = ? AND giris_ts >= ?
                             GROUP BY user_id ORDER BY total DESC LIMIT 10""",
                          (guild.id, ts))
            return c.fetchall()
        rows = await asyncio.to_thread(_q)
        e = discord.Embed(title=baslik, color=Renkler.MUZIK if hasattr(Renkler, 'MUZIK') else 0x9B59B6)
        if not rows:
            e.description = "Henüz veri yok. Kullanıcılar VC'ye girip çıksın."
            return await interaction.followup.send(embed=e)
        medals = ['🥇', '🥈', '🥉'] + ['▫️'] * 7

        async def _isim_al(uid):
            # Önce yerel cache (API çağrısı yok); yoksa fetch — silinmiş hesapta çökme yok
            uye = guild.get_member(uid) or self.bot.get_user(uid)
            if uye:
                return uye.display_name
            try:
                return (await self.bot.fetch_user(uid)).display_name
            except discord.HTTPException:
                return f"User#{uid}"

        isimler = await asyncio.gather(*(_isim_al(r['user_id']) for r in rows))
        lines = []
        for i, (r, display) in enumerate(zip(rows, isimler)):
            saat = r['total'] // 3600
            dakika = (r['total'] % 3600) // 60
            sure_str = f"{saat} sa {dakika} dk" if saat else f"{dakika} dk"
            lines.append(f"{medals[i]} **{display}** — {sure_str} ({r['sessions']} oturum)")
        e.description = "\n".join(lines)
        await interaction.followup.send(embed=e)

    # ── Slash: kişisel istatistik ──────────────────────────────
    @sesstat_grup.command(name="ben", description="Ses kanalı istatistiklerin")
    @app_commands.describe(üye="İstatistikleri görüntülenecek üye (boş bırakırsan kendin)")
    async def slash_ben(self, interaction: discord.Interaction, üye: discord.Member = None):
        target = üye or interaction.user
        await interaction.response.defer()
        def _q():
            c = db.cursor()
            c.execute("""SELECT SUM(sure_sn) as total, COUNT(*) as sessions,
                                MIN(giris_ts) as ilk, MAX(giris_ts) as son
                         FROM ses_aktivite WHERE guild_id = ? AND user_id = ?""",
                      (interaction.guild.id, target.id))
            toplam = c.fetchone()
            ts = time.time() - 7 * 86400
            c.execute("""SELECT SUM(sure_sn) as hafta FROM ses_aktivite
                         WHERE guild_id = ? AND user_id = ? AND giris_ts >= ?""",
                      (interaction.guild.id, target.id, ts))
            hafta = c.fetchone()['hafta'] or 0
            c.execute("""SELECT kanal_id, SUM(sure_sn) as t FROM ses_aktivite
                         WHERE guild_id = ? AND user_id = ?
                         GROUP BY kanal_id ORDER BY t DESC LIMIT 5""",
                      (interaction.guild.id, target.id))
            return toplam, hafta, c.fetchall()
        toplam, hafta_sure, top_kanal = await asyncio.to_thread(_q)

        e = discord.Embed(title=f"🎙️ {target.display_name} — Ses İstatistikleri",
                          color=target.color.value if target.color.value else 0x9B59B6)
        e.set_thumbnail(url=target.display_avatar.url)
        if toplam['total']:
            t = toplam['total']
            saat, dakika = t // 3600, (t % 3600) // 60
            e.add_field(name="⏱️ Toplam", value=f"**{saat} saat {dakika} dk**", inline=True)
            e.add_field(name="📅 Bu hafta", value=f"**{hafta_sure // 3600} sa {(hafta_sure % 3600) // 60} dk**", inline=True)
            e.add_field(name="🔁 Oturum", value=f"**{toplam['sessions']}**", inline=True)
            if top_kanal:
                lines = []
                for r in top_kanal:
                    ch = interaction.guild.get_channel(r['kanal_id'])
                    if not ch: continue
                    s = r['t']
                    saat, dakika = s // 3600, (s % 3600) // 60
                    lines.append(f"🔊 **{ch.name}** — {saat} sa {dakika} dk")
                e.add_field(name="📊 En çok bulunduğu kanallar", value="\n".join(lines), inline=False)
        else:
            e.description = "Henüz ses kanalı aktivitesi kaydedilmemiş."
        await interaction.followup.send(embed=e)

    # ── Slash: admin — kanal ayarı ─────────────────────────────
    @sesstat_grup.command(name="kanal", description="Ses takibi için kanal ayarla (boş bırakırsan TÜM kanallar izlenir)")
    @app_commands.describe(kanal="İzlenecek kanal (yoksa tüm kanallar izlenir)")
    @app_commands.default_permissions(administrator=True)
    async def slash_kanal_ayar(self, interaction: discord.Interaction, kanal: discord.VoiceChannel = None):
        await interaction.response.defer()
        def _q():
            c = db.cursor()
            c.execute("DELETE FROM ses_kanal_ayar WHERE guild_id = ?", (interaction.guild.id,))
            if kanal:
                c.execute("INSERT INTO ses_kanal_ayar (guild_id, kanal_id) VALUES (?, ?)",
                          (interaction.guild.id, kanal.id))
            db.commit()
        await asyncio.to_thread(_q)
        msg = f"✅ Artık **tüm** ses kanalları izleniyor." if not kanal else f"✅ Sadece {kanal.mention} izleniyor."
        await interaction.followup.send(msg)

    @sesstat_grup.command(name="sifirla", description="Tüm ses aktivite verisini siler (GERİ ALINAMAZ)")
    @app_commands.default_permissions(administrator=True)
    async def slash_sifirla(self, interaction: discord.Interaction):
        await interaction.response.defer()
        def _q():
            c = db.cursor()
            c.execute("DELETE FROM ses_aktivite WHERE guild_id = ?", (interaction.guild.id,))
            db.commit()
            return c.rowcount
        n = await asyncio.to_thread(_q)
        await interaction.followup.send(f"🗑️ {n} ses aktivite kaydı silindi.")


async def setup(bot: commands.Bot):
    await bot.add_cog(SesAktivite(bot))