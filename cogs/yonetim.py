import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import random
import re
import datetime
import logging
from collections import defaultdict, deque
from typing import Optional
from database import (db, yonetici_kontrol, sunucu_ayar_al, sunucu_ayar_guncelle,
                      afk_al, afk_ayarla, afk_kaldir, kelime_oyunu_al, eski_verileri_temizle,
                      sunucu_dil_al, sunucu_dil_ayarla)
from yapilandirma import GUVENILIR_IDLER, SAHIP_ID
from arayuz import Renkler, premium_embed, sure_insana_cevir, AYIRICI, bilgi_kutusu, DURUM_TIPLERI

logger = logging.getLogger('MezarBot.Yonetim')

AFK_SEBEP_MAKS = 300
_URL_REGEX = re.compile(r'https?://\S+', re.IGNORECASE)


def afk_sebep_temizle(sebep):
    """Kullanıcının AFK sebebini güvenli hale getirir: URL'ler ve (maskeli) linkler kaldırılır,
    @everyone/@here/rol/kullanıcı mention'ları etkisizleştirilir, markdown kaçışlanır, uzunluk sınırlanır."""
    sebep = _URL_REGEX.sub('[link]', sebep)
    sebep = discord.utils.escape_mentions(sebep)
    sebep = discord.utils.escape_markdown(sebep)
    return sebep[:AFK_SEBEP_MAKS]


DOKUNULMAZ_MESAJ = "Bu kullanıcıya ceza verilemez, verilmesi teklif dahi edilemez."


class AyarlarDilGorunumu(discord.ui.View):
    def __init__(self, cog, guild_id: int):
        super().__init__(timeout=180)
        self.cog = cog
        self.guild_id = guild_id

    @discord.ui.button(label="Türkçe", emoji="🇹🇷", style=discord.ButtonStyle.secondary, custom_id="ayarlar_dil_tr")
    async def buton_tr(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._dil_degis(interaction, "tr")

    @discord.ui.button(label="English", emoji="🇬🇧", style=discord.ButtonStyle.secondary, custom_id="ayarlar_dil_en")
    async def buton_en(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._dil_degis(interaction, "en")

    async def _dil_degis(self, interaction: discord.Interaction, yeni_dil: str):
        if not interaction.user.guild_permissions.manage_guild and interaction.user.id != SAHIP_ID:
            msg = "❌ You need 'Manage Server' permission." if yeni_dil == "en" else "❌ Bu işlem için 'Sunucuyu Yönet' yetkisi gerekir."
            return await interaction.response.send_message(msg, ephemeral=True)

        sunucu_dil_ayarla(interaction.guild.id, yeni_dil)
        embed = self.cog._ayarlar_embedi(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)

        txt = (
            "✅ Server language has been set to **English**! Commands and menus will now respond in English."
            if yeni_dil == "en" else
            "✅ Sunucu dili **Türkçe** olarak ayarlandı! Komutlar ve menüler artık Türkçe yanıt verecektir."
        )
        await interaction.followup.send(txt, ephemeral=True)


class Yonetim(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Flood koruması: {kullanıcı_id: deque([{icerik, zaman}])}
        self.mesaj_gecmisi = defaultdict(lambda: deque(maxlen=10))
        self.spam_sayaci = defaultdict(int)
        # Dokunulmaz kullanıcıya ceza vermeye çalışanların deneme sayacı: {kullanıcı_id: deneme_sayisi}
        self.dokunulmaz_ceza_sayaci = defaultdict(int)
        # Günlük DB temizlik takip zamanı
        self._son_db_temizlik = 0
        # Bellek temizleme görevi
        self.bellek_temizle.start()

    async def dokunulmazlik_kontrol(self, ctx, uye) -> bool:
        """Sahip ve config.json → guvenilir_idler kişilerine ceza verilmesini engeller.
        2'den fazla (yani 3. kez ve üzeri) deneme yapan kişiye 1 saat mute uygular."""
        hedef_id = getattr(uye, 'id', uye)
        if hedef_id in GUVENILIR_IDLER:
            # Kendisi deniyorsa ceza verme
            if ctx.author.id in GUVENILIR_IDLER:
                await ctx.send(f"❌ {DOKUNULMAZ_MESAJ}", delete_after=5)
                return True

            self.dokunulmaz_ceza_sayaci[ctx.author.id] += 1
            deneme = self.dokunulmaz_ceza_sayaci[ctx.author.id]

            if deneme > 2:
                self.dokunulmaz_ceza_sayaci[ctx.author.id] = 0
                await self.gecici_mute_uygula(
                    ctx.guild, ctx.author, 3600,
                    "Dokunulmaz kullanıcıya ceza verme girişimi (2'den fazla deneme)"
                )
                await ctx.send(
                    f"❌ **{DOKUNULMAZ_MESAJ}**\n"
                    f"⚠️ {ctx.author.mention}, bu kullanıcıya 2'den fazla kez ceza vermeye çalıştığınız için **1 saat susturuldunuz**!"
                )
            else:
                kalan = 2 - deneme
                uyari_ek = " (Tekrar denerseniz 1 saat susturulacaksınız!)" if kalan == 0 else f" (Kalan hak: {kalan})"
                await ctx.send(f"❌ **{DOKUNULMAZ_MESAJ}**{uyari_ek}")

            return True
        return False

    def cog_unload(self):
        self.bellek_temizle.cancel()

    @tasks.loop(minutes=30)
    async def bellek_temizle(self):
        """Eski flood/spam verilerini temizler."""
        su_an = datetime.datetime.now().timestamp()
        # 5 dakikadan eski mesaj geçmişlerini temizle
        temizlenecek = [uid for uid, gecmis in self.mesaj_gecmisi.items()
                        if not gecmis or su_an - gecmis[-1]['zaman'] > 300]
        for uid in temizlenecek:
            del self.mesaj_gecmisi[uid]
        # Spam sayacında sıfır olanları temizle (bellek tasarrufu)
        temizlenecek_spam = [k for k, v in self.spam_sayaci.items() if v == 0]
        for k in temizlenecek_spam:
            del self.spam_sayaci[k]
        # Günde bir kez eski veritabanı kayıtlarını temizle (non-blocking)
        if su_an - self._son_db_temizlik > 86400:
            self._son_db_temizlik = su_an
            try:
                await asyncio.to_thread(eski_verileri_temizle)
            except Exception as e:
                logger.error(f"Veritabanı otomatik temizlik hatası: {e}")

    # ══════════════════════════════════════════════
    #  OTO-MOD SİSTEMİ
    # ══════════════════════════════════════════════

    def flood_kontrol(self, kullanici_id, icerik, guild_id=None):
        """Aynı mesajı tekrarlayan kullanıcıları tespit eder."""
        su_an = datetime.datetime.now().timestamp()
        anahtar = (guild_id, kullanici_id) if guild_id else kullanici_id
        gecmis = self.mesaj_gecmisi[anahtar]

        gecmis.append({'icerik': icerik, 'zaman': su_an})

        # Son 10 saniyedeki aynı mesajları say
        ayni_mesaj_sayisi = sum(1 for m in gecmis if m['icerik'] == icerik and su_an - m['zaman'] < 10)

        if ayni_mesaj_sayisi >= 3:
            return "flood"

        return None

    async def otomod_cezalandir(self, message, sebep):
        """Oto-mod ihlali tespit edildiğinde ceza uygular."""
        if message.author.id in GUVENILIR_IDLER:
            return
        spam_key = (message.guild.id, message.author.id)
        self.spam_sayaci[spam_key] += 1
        ihlal = self.spam_sayaci[spam_key]

        try:
            await message.delete()
        except (discord.NotFound, discord.Forbidden):
            pass

        try:
            if ihlal >= 3:
                await self.gecici_mute_uygula(message.guild, message.author, 300, f"Oto-Mod: {sebep} (3. ihlal)")
                self.spam_sayaci[spam_key] = 0
                await message.channel.send(
                    f"🔇 **{message.author.display_name}** oto-mod tarafından 5 dakika susturuldu. Sebep: **{sebep}**",
                    delete_after=10)
            else:
                await message.channel.send(
                    f"⚠️ **{message.author.display_name}**, {sebep}! (İhlal: {ihlal}/3)",
                    delete_after=5)
        except (discord.Forbidden, discord.HTTPException):
            pass

    # ══════════════════════════════════════════════
    #  GEÇİCİ MUTE SİSTEMİ
    # ══════════════════════════════════════════════

    async def gecici_mute_uygula(self, guild, uye, sure_saniye, sebep="Belirtilmedi"):
        """Kullanıcıya geçici timeout uygular."""
        until = discord.utils.utcnow() + datetime.timedelta(seconds=sure_saniye)
        try:
            await uye.timeout(until, reason=sebep)
            c = db.cursor()
            c.execute(
                "INSERT INTO moderasyon_log (sunucu_id, islem, hedef_id, moderator_id, sebep, tarih) VALUES (?, ?, ?, ?, ?, ?)",
                (guild.id, "MUTE", uye.id,self.bot.user.id, f"{sebep} ({sure_saniye}sn)", datetime.datetime.now(datetime.timezone.utc).isoformat()))
            db.commit()
        except discord.Forbidden:
            logger.warning(f"Mute uygulanamadı (yetki yok): {uye.display_name}")
        except Exception as e:
            logger.error(f"Mute hatası: {e}")

    # ══════════════════════════════════════════════
    #  LISTENERS
    # ══════════════════════════════════════════════

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        # Cache'den oku — DB sorgusu yok
        ayar = sunucu_ayar_al(message.guild.id)

        # ── Oto-Mod Kontrolü ──
        if ayar and ayar.get('otomod_aktif'):
            if not message.author.guild_permissions.administrator:
                if message.content:
                    flood_sonuc = self.flood_kontrol(message.author.id, message.content, message.guild.id)
                    if flood_sonuc == "flood":
                        await self.otomod_cezalandir(message, "Aynı mesajı tekrarlıyorsun (flood)")
                        return

        # ── AFK Kontrolü (sunucu bazlı, cache'den — DB sorgusu yok) ──
        sid = message.guild.id
        sebep = afk_al(sid, message.author.id)
        if sebep:
            afk_kaldir(sid, message.author.id)
            await message.channel.send(
                f"☀️ **{message.author.display_name}** AFK modundan çıktı.", delete_after=5)

        if message.mentions:
            for m in message.mentions:
                m_sebep = afk_al(sid, m.id)
                if m_sebep:
                    await message.channel.send(
                        f"🤫 **{m.display_name}** şu an AFK: *{m_sebep}*", delete_after=7)

    # ── Hoşgeldin & Otorol ──
    @commands.Cog.listener()
    async def on_member_join(self, member):
        if member.bot:
            return
        # Hoşgeldin/otorol sunucu başına opt-in: sadece !hosgeldinayarla / !otorolayarla ile ayarlandıysa çalışır

        ayar = sunucu_ayar_al(member.guild.id)
        if not ayar:
            return

        hosgeldin_kanal_id = ayar.get('hosgeldin_kanal_id')
        hosgeldin_mesaj = ayar.get('hosgeldin_mesaj')
        otorol_id = ayar.get('otorol_id')

        # Hoşgeldin mesajı
        if hosgeldin_kanal_id:
            kanal = self.bot.get_channel(hosgeldin_kanal_id)
            if kanal:
                mesaj_icerik = (hosgeldin_mesaj or "Hoş geldin {uye}! 🎉").replace("{uye}", member.mention)
                uye_sayisi = member.guild.member_count

                embed = discord.Embed(color=Renkler.BASARI, timestamp=datetime.datetime.now(datetime.timezone.utc))
                embed.set_author(name="👋 ʏᴇɴɪ ᴜ̈ʏᴇ ᴋᴀᴛɪʟᴅɪ!", icon_url=member.display_avatar.url)
                embed.set_thumbnail(url=member.display_avatar.url)
                embed.description = (
                    f"{mesaj_icerik}\n\n"
                    f"{bilgi_kutusu(('📅', 'ʜᴇsᴀᴘ', member.created_at.strftime('%d/%m/%Y')), ('👥', 'ᴜ̈ʏᴇ sᴀʏɪsɪ', f'`{uye_sayisi}`'))}"
                )
                embed.set_footer(text=f"{member.guild.name} • ID: {member.id}")
                try:
                    await kanal.send(embed=embed)
                except (discord.Forbidden, discord.HTTPException):
                    pass

        # Otorol
        if otorol_id:
            rol = member.guild.get_role(otorol_id)
            if rol:
                try:
                    await member.add_roles(rol, reason="Otorol sistemi")
                    logger.info(f"Otorol verildi: {member.display_name} -> {rol.name}")
                except discord.Forbidden:
                    logger.warning(f"Otorol verilemedi (yetki yok): {rol.name}")

    # ── Görüşürüz (Ayrılma) Bildirimi ──
    @commands.Cog.listener()
    async def on_member_remove(self, member):
        if member.bot:
            return
        ayar = sunucu_ayar_al(member.guild.id)
        if not ayar:
            return

        gorusuruz_kanal_id = ayar.get('gorusuruz_kanal_id')
        gorusuruz_mesaj = ayar.get('gorusuruz_mesaj')
        if not gorusuruz_kanal_id:
            return

        kanal = self.bot.get_channel(gorusuruz_kanal_id)
        if not kanal:
            return

        mesaj_icerik = (gorusuruz_mesaj or "Görüşürüz **{uye}**... Yolun açık olsun. 🕊️").replace("{uye}", member.name)
        uye_sayisi = member.guild.member_count

        embed = discord.Embed(color=Renkler.HATA, timestamp=datetime.datetime.now(datetime.timezone.utc))
        embed.set_author(name="📤 Bir Üye Ayrıldı", icon_url=member.display_avatar.url)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.description = (
            f"{mesaj_icerik}\n\n"
            f"{bilgi_kutusu(('👤', 'Kullanıcı', f'`{member.name}` (`{member.id}`)'), ('👥', 'Kalan Üye', f'`{uye_sayisi}`'))}"
        )
        embed.set_footer(text=f"{member.guild.name}")
        try:
            await kanal.send(embed=embed)
        except (discord.Forbidden, discord.HTTPException):
            pass

    # ── Log: Silinen Mesajlar ──
    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.author.bot or not message.guild:
            return

        ayar = sunucu_ayar_al(message.guild.id)
        log_kanal_id = ayar.get('log_kanal_id') if ayar else None
        if log_kanal_id:
            log_kanali = self.bot.get_channel(log_kanal_id)
            if log_kanali:
                icerik = message.content[:900] if message.content else "*[İçerik Yok veya Medya]*"
                embed = discord.Embed(color=Renkler.HATA, timestamp=datetime.datetime.now(datetime.timezone.utc))
                embed.set_author(name="🗑️ Mesaj Silindi", icon_url=message.author.display_avatar.url)
                embed.description = (
                    f"{bilgi_kutusu(('👤', 'Kullanıcı', message.author.mention), ('📝', 'Kanal', message.channel.mention))}\n\n"
                    f"**Silinen İçerik:**\n>>> {icerik}"
                )
                embed.set_footer(text=f"MezarBot • ID: {message.author.id}")
                try:
                    await log_kanali.send(embed=embed)
                except (discord.Forbidden, discord.HTTPException):
                    pass

    # ── Log: Düzenlenen Mesajlar ──
    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if before.author.bot or not before.guild or before.content == after.content:
            return

        ayar = sunucu_ayar_al(before.guild.id)
        log_kanal_id = ayar.get('log_kanal_id') if ayar else None
        if log_kanal_id:
            log_kanali = self.bot.get_channel(log_kanal_id)
            if log_kanali:
                eski = before.content[:400] if before.content else "*[Boş]*"
                yeni = after.content[:400] if after.content else "*[Boş]*"
                embed = discord.Embed(color=Renkler.UYARI, timestamp=datetime.datetime.now(datetime.timezone.utc))
                embed.set_author(name="✏️ Mesaj Düzenlendi", icon_url=before.author.display_avatar.url)
                embed.description = (
                    f"{bilgi_kutusu(('👤', 'Kullanıcı', before.author.mention), ('📝', 'Kanal', before.channel.mention))}\n\n"
                    f"**Eski:**\n>>> {eski}"
                )
                embed.add_field(name="Yeni İçerik", value=yeni, inline=False)
                embed.set_footer(text=f"MezarBot • Mesaj ID: {before.id}")
                try:
                    await log_kanali.send(embed=embed)
                except (discord.Forbidden, discord.HTTPException):
                    pass

    # ══════════════════════════════════════════════
    #  KOMUTLAR
    # ══════════════════════════════════════════════

    # ── Oto-Mod Aç/Kapat ──
    @commands.hybrid_command(description="Otomatik moderasyonu aç/kapat")
    @app_commands.default_permissions(manage_guild=True)
    @commands.guild_only()
    @commands.check(yonetici_kontrol)
    async def otomod(self, ctx):
        """Oto-mod sistemini açar/kapatır. Küfür filtresi ve flood koruması."""
        ayar = sunucu_ayar_al(ctx.guild.id)
        if ayar:
            yeni_durum = 0 if ayar.get('otomod_aktif') else 1
        else:
            yeni_durum = 1
        sunucu_ayar_guncelle(ctx.guild.id, otomod_aktif=yeni_durum)

        durum = "✅ AKTİF" if yeni_durum else "❌ KAPALI"
        embed = premium_embed("🤖 Oto-Mod Sistemi", f"Oto-mod durumu: **{durum}**", renk=Renkler.BASARI if yeni_durum else Renkler.HATA)
        embed.set_footer(text="Küfür filtresi devre dışı.")
        if yeni_durum:
            embed.add_field(name="🛡️ Korumalar", value="• Flood koruması (aynı mesajı 3x tekrarlarsa ceza)", inline=False)
            embed.add_field(name="⚡ Cezalar", value="• 1-2. ihlal: Uyarı\n• 3. ihlal: 5dk mute", inline=False)
        await ctx.send(embed=embed)

    # ── Uyar (Warn) ──
    @commands.hybrid_command(description="Üyeyi uyar")
    @app_commands.default_permissions(moderate_members=True)
    @commands.guild_only()
    @commands.has_guild_permissions(moderate_members=True)
    async def uyar(self, ctx, uye: discord.Member, *, sebep="Sebep belirtilmedi"):
        """Kullanıcıya uyarı verir. 3 uyarıda otomatik mute. Kullanım: !uyar @kişi sebep"""
        try:
            if ctx.interaction is None:  # /komutta silinecek/tepki verilecek mesaj yok
                await ctx.message.delete()
        except (discord.NotFound, discord.Forbidden):
            pass

        if await self.dokunulmazlik_kontrol(ctx, uye):
            return

        if uye.bot:
            return await ctx.send("❌ Botları uyaramazsın!", delete_after=5)

        c = db.cursor()

        # Uyarıyı kaydet
        c.execute(
            "INSERT INTO uyarilar (sunucu_id, kullanici_id, moderator_id, sebep, tarih) VALUES (?, ?, ?, ?, ?)",
            (ctx.guild.id, uye.id, ctx.author.id, sebep, datetime.datetime.now(datetime.timezone.utc).isoformat()))
        db.commit()

        # Toplam uyarı sayısını al
        c.execute("SELECT COUNT(*) FROM uyarilar WHERE sunucu_id = ? AND kullanici_id = ?",
                   (ctx.guild.id, uye.id))
        toplam = c.fetchone()[0]

        # Uyarı kanalına mesaj gönder
        ayar = sunucu_ayar_al(ctx.guild.id)
        uyari_kanal_id = ayar.get('uyari_kanal_id') if ayar else None
        if uyari_kanal_id:
            kanal = self.bot.get_channel(uyari_kanal_id)
            if kanal:
                w_embed = discord.Embed(color=Renkler.UYARI, timestamp=datetime.datetime.now(datetime.timezone.utc))
                w_embed.set_author(name="⚠️ Kullanıcı Uyarıldı", icon_url=uye.display_avatar.url)
                w_embed.set_thumbnail(url=uye.display_avatar.url)
                w_embed.description = (
                    f"{bilgi_kutusu(('👤', 'Kullanıcı', uye.mention), ('🔨', 'Moderatör', ctx.author.mention), ('📊', 'Uyarı', f'`{toplam}/3`'), ('📝', 'Sebep', sebep))}"
                )
                w_embed.set_footer(text=f"MezarBot • ID: {uye.id}")
                await kanal.send(content=uye.mention, embed=w_embed)

        # 3 uyarıda otomatik ceza
        if toplam >= 3:
            logger.info(f"Kullanıcı {uye.display_name} ({uye.id}) 3 uyarıya ulaştı. Mute uygulanıyor.")
            await self.gecici_mute_uygula(ctx.guild, uye, 3600, f"3 uyarıya ulaştı")

            embed = discord.Embed(color=Renkler.HATA, timestamp=datetime.datetime.now(datetime.timezone.utc))
            embed.set_author(name="⚠️ Uyarı & Otomatik Ceza", icon_url=uye.display_avatar.url)
            embed.set_thumbnail(url=uye.display_avatar.url)
            embed.description = (
                f"{bilgi_kutusu(('👤', 'Kullanıcı', uye.mention), ('🔨', 'Moderatör', ctx.author.mention), ('📝', 'Sebep', sebep), ('📊', 'Uyarı', f'`{toplam}/3`'), ('🔇', 'Ceza', '**1 saat mute**'))}"
            )
            embed.set_footer(text="MezarBot • Moderasyon")

            # Uyarıları sıfırla
            c.execute("DELETE FROM uyarilar WHERE sunucu_id = ? AND kullanici_id = ?",
                       (ctx.guild.id, uye.id))
            db.commit()
        else:
            embed = discord.Embed(color=Renkler.UYARI, timestamp=datetime.datetime.now(datetime.timezone.utc))
            embed.set_author(name="⚠️ Kullanıcı Uyarıldı", icon_url=uye.display_avatar.url)
            embed.set_thumbnail(url=uye.display_avatar.url)
            embed.description = (
                f"{bilgi_kutusu(('👤', 'Kullanıcı', uye.mention), ('🔨', 'Moderatör', ctx.author.mention), ('📝', 'Sebep', sebep), ('📊', 'Uyarı', f'`{toplam}/3`'))}"
            )
            embed.set_footer(text="MezarBot • Moderasyon")

        # Moderasyon loguna kaydet
        c.execute(
            "INSERT INTO moderasyon_log (sunucu_id, islem, hedef_id, moderator_id, sebep, tarih) VALUES (?, ?, ?, ?, ?, ?)",
            (ctx.guild.id, "WARN", uye.id,ctx.author.id, sebep, datetime.datetime.now(datetime.timezone.utc).isoformat()))
        db.commit()

        # Kullanıcıya DM bildir
        try:
            dm_embed = premium_embed("⚠️ Uyarı Aldın!", f"**{ctx.guild.name}** sunucusunda uyarıldın.", renk=Renkler.UYARI)
            dm_embed.add_field(name="📝 Sebep", value=sebep, inline=False)
            dm_embed.add_field(name="📊 Toplam Uyarı", value=f"**{toplam}/3**", inline=True)
            if toplam >= 3:
                dm_embed.add_field(name="🔇 Ceza", value="1 saat mute uygulandı", inline=True)
            await uye.send(embed=dm_embed)
        except (discord.Forbidden, discord.HTTPException):
            pass  # DM kapalıysa sessizce atla

        await ctx.send(embed=embed)

    @commands.hybrid_command(description="Uyarı log kanalını ayarla")
    @app_commands.default_permissions(manage_guild=True)
    @commands.guild_only()
    @commands.check(yonetici_kontrol)
    async def uyarayarla(self, ctx, kanal: discord.TextChannel = None):
        """Uyarıların gideceği kanalı ayarlar. Kullanım: !uyarayarla [#kanal]"""
        hedef_kanal = kanal or ctx.channel
        sunucu_ayar_guncelle(ctx.guild.id, uyari_kanal_id=hedef_kanal.id)
        await ctx.send(f"✅ Uyarı kanalı {hedef_kanal.mention} olarak ayarlandı!")

    @commands.hybrid_command(name="durumayarla", description="[Bot Sahibi] Botun durumunu kalıcı olarak ayarlar")
    @app_commands.describe(tip="Durum tipi (oynuyor, dinliyor, izliyor, yarismada)", metin="Durum metni")
    @app_commands.choices(tip=[
        app_commands.Choice(name="Oynuyor", value="oynuyor"),
        app_commands.Choice(name="Dinliyor", value="dinliyor"),
        app_commands.Choice(name="İzliyor", value="izliyor"),
        app_commands.Choice(name="Yarışmada", value="yarismada")
    ])
    @commands.guild_only()
    @commands.is_owner()
    async def durumayarla(self, ctx, tip: str, *, metin: str):
        """[Bot Sahibi] Botun durumunu kalıcı olarak ayarlar (tüm sunucularda görünür — global).
        Tipler: oynuyor, dinliyor, izliyor, yarismada
        Kullanım: !durumayarla izliyor Mezarcı belgesini veya /durumayarla tip:izliyor metin:Mezarcı belgesini
        """
        tip = tip.lower()

        if tip not in DURUM_TIPLERI:
            return await ctx.send(f"❌ Geçersiz tip! Kullanabileceklerin: `{', '.join(DURUM_TIPLERI.keys())}`", ephemeral=True)

        c = db.cursor()
        c.execute("REPLACE INTO bot_ayarlar (ayarlar_id, durum_metni, durum_tipi) VALUES (1, ?, ?)",
                   (metin, tip))
        db.commit()

        try:
            await self.bot.change_presence(activity=discord.Activity(type=DURUM_TIPLERI[tip], name=metin))
            await ctx.send(f"✅ Bot durumu ayarlandı: **{tip.capitalize()} {metin}**")
        except Exception as e:
            await ctx.send(f"❌ Durum güncellenirken hata oluştu: {e}")

    # ── Uyarıları Görüntüle ──
    @commands.hybrid_command(description="Üyenin uyarılarını göster")
    @commands.guild_only()
    async def uyarilar(self, ctx, uye: discord.Member = None):
        """Kullanıcının uyarılarını gösterir. Kullanım: !uyarilar @kişi"""
        hedef = uye or ctx.author
        c = db.cursor()
        c.execute("SELECT moderator_id, sebep, tarih FROM uyarilar WHERE sunucu_id = ? AND kullanici_id = ? ORDER BY tarih DESC",
                   (ctx.guild.id, hedef.id))
        kayitlar = c.fetchall()

        if not kayitlar:
            return await ctx.send(f"✅ **{hedef.display_name}** için uyarı kaydı yok.", delete_after=5)

        embed = premium_embed(f"⚠️ {hedef.display_name} — Uyarılar ({len(kayitlar)}/3)", None, renk=Renkler.UYARI)
        for i, kayit in enumerate(kayitlar, 1):
            mod_id, sebep, tarih = kayit[0], kayit[1], kayit[2]
            tarih_kisa = tarih[:10] if tarih else "?"
            embed.add_field(name=f"#{i} — {tarih_kisa}", value=f"📝 {sebep}\n🔨 <@{mod_id}>", inline=False)
        await ctx.send(embed=embed)

    # ── Uyarı Sil ──
    @commands.hybrid_command(description="Üyenin uyarılarını sil")
    @app_commands.default_permissions(moderate_members=True)
    @commands.guild_only()
    @commands.has_guild_permissions(moderate_members=True)
    async def uyarisil(self, ctx, uye: discord.Member):
        """Kullanıcının tüm uyarılarını siler. Kullanım: !uyarisil @kişi"""
        c = db.cursor()
        c.execute("DELETE FROM uyarilar WHERE sunucu_id = ? AND kullanici_id = ?",
                   (ctx.guild.id, uye.id))
        db.commit()
        await ctx.send(f"✅ **{uye.display_name}** için tüm uyarılar silindi.", delete_after=7)

    # ── Mute (Sustur) ──
    @commands.hybrid_command(description="Üyeyi süreli sustur (ör. 10m, 1h)")
    @app_commands.default_permissions(moderate_members=True)
    @commands.guild_only()
    @commands.has_guild_permissions(moderate_members=True)
    async def sustur(self, ctx, uye: discord.Member, sure: str = "10m", *, sebep="Sebep belirtilmedi"):
        """Kullanıcıyı geçici olarak susturur. Kullanım: !sustur @kişi 10m sebep
        Süre formatları: 30s (saniye), 10m (dakika), 2h (saat), 1d (gün)"""
        if await self.dokunulmazlik_kontrol(ctx, uye):
            return

        if uye.bot:
            return await ctx.send("❌ Botları susturamazsın!", delete_after=5)
        if uye.top_role >= ctx.author.top_role:
            return await ctx.send("❌ Kendinden üst rütbeli birini susturamazsın!", delete_after=5)

        sure_saniye = self.sure_parse(sure)
        if sure_saniye is None or sure_saniye < 1:
            return await ctx.send("❌ Geçersiz süre! Örnekler: `30s`, `10m`, `2h`, `1d`", delete_after=7)
        if sure_saniye > 2419200:
            return await ctx.send("❌ Maksimum süre 28 gündür!", delete_after=5)

        await self.gecici_mute_uygula(ctx.guild, uye, sure_saniye, f"{ctx.author.name}: {sebep}")

        sure_metin = sure_insana_cevir(sure_saniye)
        embed = discord.Embed(color=Renkler.UYARI, timestamp=datetime.datetime.now(datetime.timezone.utc))
        embed.set_author(name="🔇 Kullanıcı Susturuldu", icon_url=uye.display_avatar.url)
        embed.description = (
            f"{bilgi_kutusu(('👤', 'Kullanıcı', uye.mention), ('🔨', 'Moderatör', ctx.author.mention), ('⏱️', 'Süre', sure_metin), ('📝', 'Sebep', sebep))}"
        )
        embed.set_footer(text="MezarBot • Moderasyon")
        await ctx.send(embed=embed)

        # Kullanıcıya DM bildir
        try:
            dm_embed = premium_embed("🔇 Susturuldun!", f"**{ctx.guild.name}** sunucusunda susturuldun.", renk=Renkler.UYARI)
            dm_embed.add_field(name="⏱️ Süre", value=sure_metin, inline=True)
            dm_embed.add_field(name="📝 Sebep", value=sebep, inline=False)
            await uye.send(embed=dm_embed)
        except (discord.Forbidden, discord.HTTPException):
            pass

    # ── Unmute (Susturma Kaldır) ──
    @commands.hybrid_command(description="Üyenin susturmasını kaldır")
    @app_commands.default_permissions(moderate_members=True)
    @commands.guild_only()
    @commands.has_guild_permissions(moderate_members=True)
    async def susturmakald(self, ctx, uye: discord.Member):
        """Kullanıcının susturmasını kaldırır. Kullanım: !susturmakald @kişi"""
        try:
            await uye.timeout(None, reason=f"Susturma kaldırıldı: {ctx.author.name}")
            c = db.cursor()
            c.execute(
                "INSERT INTO moderasyon_log (sunucu_id, islem, hedef_id, moderator_id, sebep, tarih) VALUES (?, ?, ?, ?, ?, ?)",
                (ctx.guild.id, "UNMUTE", uye.id,ctx.author.id, "Susturma kaldırıldı", datetime.datetime.now(datetime.timezone.utc).isoformat()))
            db.commit()
            embed = premium_embed("🔊 Susturma Kaldırıldı", f"**{uye.display_name}** artık konuşabilir.", renk=Renkler.BASARI)
            await ctx.send(embed=embed)
        except discord.Forbidden:
            await ctx.send("❌ Susturmayı kaldırmak için yetkim yok!", delete_after=5)

    # ── Hoşgeldin Ayarla ──
    @commands.hybrid_command(description="Hoş geldin kanalını ve mesajını ayarla")
    @app_commands.default_permissions(manage_guild=True)
    @commands.guild_only()
    @commands.check(yonetici_kontrol)
    async def hosgeldinayarla(self, ctx, kanal: discord.TextChannel, *, mesaj: str = None):
        """Hoşgeldin kanalı ve mesajını ayarlar. {uye} yazan yere üye etiketi gelir.
        Kullanım: !hosgeldinayarla #kanal Hoş geldin {uye}! Aramıza katıldığın için mutluyuz!"""
        varsayilan = "ʜᴏs ɢᴇʟᴅɪɴ {uye}! 🎉 ᴀʀᴀᴍɪᴢᴀ ᴋᴀᴛɪʟᴅɪɢ̆ɪɴ ɪᴄ̧ɪɴ ᴍᴜᴛʟᴜʏᴜᴢ! 🪦"
        mesaj_icerik = mesaj or varsayilan
        sunucu_ayar_guncelle(ctx.guild.id, hosgeldin_kanal_id=kanal.id, hosgeldin_mesaj=mesaj_icerik)

        embed = premium_embed("👋 Hoşgeldin Sistemi Ayarlandı", None, renk=Renkler.BASARI)
        embed.add_field(name="📝 Kanal", value=kanal.mention, inline=True)
        embed.add_field(name="💬 Mesaj", value=mesaj_icerik.replace("{uye}", ctx.author.mention), inline=False)
        await ctx.send(embed=embed)

    # ── Görüşürüz Ayarla ──
    @commands.hybrid_command(description="Görüşürüz (ayrılma) kanalını ve mesajını ayarla ya da kapat")
    @app_commands.describe(kanal="Ayrılma mesajının gönderileceği kanal", mesaj="Özel veda mesajı ({uye} üye adıdır)")
    @app_commands.default_permissions(manage_guild=True)
    @commands.guild_only()
    @commands.check(yonetici_kontrol)
    async def gorusuruzayarla(self, ctx, kanal: Optional[discord.TextChannel] = None, *, mesaj: str = None):
        """Ayrılma kanalı ve mesajını ayarlar. Kanal belirtilmezse kapatılır.
        Kullanım: /gorusuruzayarla #kanal Görüşürüz {uye}! veya /gorusuruzayarla (kapatmak için)"""
        if kanal is None:
            sunucu_ayar_guncelle(ctx.guild.id, gorusuruz_kanal_id=None, gorusuruz_mesaj=None)
            return await ctx.send("🔕 Görüşürüz bildirimleri bu sunucuda kapatıldı.")

        varsayilan = "Görüşürüz **{uye}**... Yolun açık olsun. 🕊️"
        mesaj_icerik = mesaj or varsayilan
        sunucu_ayar_guncelle(ctx.guild.id, gorusuruz_kanal_id=kanal.id, gorusuruz_mesaj=mesaj_icerik)

        embed = premium_embed("📤 Görüşürüz Sistemi Ayarlandı", None, renk=Renkler.BASARI)
        embed.add_field(name="📝 Kanal", value=kanal.mention, inline=True)
        embed.add_field(name="💬 Mesaj", value=mesaj_icerik.replace("{uye}", ctx.author.name), inline=False)
        await ctx.send(embed=embed)

    # ── Otorol Ayarla ──
    @commands.hybrid_command(description="Yeni üyelere otomatik verilecek rolü ayarla")
    @app_commands.default_permissions(manage_guild=True)
    @commands.guild_only()
    @commands.check(yonetici_kontrol)
    async def otorolayarla(self, ctx, rol: discord.Role):
        """Yeni üyelere otomatik verilecek rolü ayarlar. Kullanım: !otorolayarla @rol"""
        if rol >= ctx.guild.me.top_role:
            return await ctx.send("❌ Bu rol benim rütbemden yüksek, veremem!", delete_after=5)
        sunucu_ayar_guncelle(ctx.guild.id, otorol_id=rol.id)
        embed = premium_embed("🏷️ Otorol Ayarlandı", f"Yeni üyelere otomatik olarak {rol.mention} rolü verilecek.", renk=Renkler.BILGI)
        await ctx.send(embed=embed)

    # ── Log Kanal Ayarla ──
    @commands.hybrid_command(description="Moderasyon log kanalını ayarla")
    @app_commands.default_permissions(manage_guild=True)
    @commands.guild_only()
    @commands.check(yonetici_kontrol)
    async def logayarla(self, ctx, kanal: discord.TextChannel):
        """Log kanalını ayarlar. Kullanım: !logayarla #kanal"""
        sunucu_ayar_guncelle(ctx.guild.id, log_kanal_id=kanal.id)
        embed = discord.Embed(color=Renkler.BASARI, timestamp=datetime.datetime.now(datetime.timezone.utc))
        embed.set_author(name="✅ Log Kanalı Ayarlandı")
        embed.description = f"Silinen ve düzenlenen mesajlar artık {kanal.mention} kanalına kaydedilecek."
        embed.set_footer(text="MezarBot • Ayarlar")
        await ctx.send(embed=embed)

    # ── Takım Kur ──
    @commands.hybrid_command(description="Ses kanalındakileri rastgele takımlara böl")
    @commands.guild_only()
    async def takimkur(self, ctx, takim_sayisi: int = 2):
        """Ses kanalındaki kişileri takımlara böler. Kullanım: !takimkur 3"""
        if not ctx.author.voice:
            return await ctx.send("❌ Seste olmalısın.", delete_after=5)
        uyeler = [m for m in ctx.author.voice.channel.members if not m.bot]
        if len(uyeler) < takim_sayisi:
            return await ctx.send("❌ Yeterli kişi yok!", delete_after=5)
        random.shuffle(uyeler)
        takimlar = [uyeler[i::takim_sayisi] for i in range(takim_sayisi)]
        embed = premium_embed("⚔️ Takımlar Oluşturuldu", None, renk=Renkler.UYARI)
        for i, takim in enumerate(takimlar, 1):
            isimler = "\n".join(m.display_name for m in takim) if takim else "Boş"
            embed.add_field(name=f"🛡️ Takım {i} ({len(takim)} kişi)", value=isimler, inline=True)
        await ctx.send(embed=embed)

    # ── AFK ──
    @commands.hybrid_command(description="AFK ol (etiketlenince sebebin gösterilir)")
    @commands.guild_only()
    async def afk(self, ctx, *, sebep="Buralarda yokum"):
        """Bu sunucuda AFK moduna geçersin. Kullanım: !afk yemek yiyorum"""
        sebep = afk_sebep_temizle(sebep)
        afk_ayarla(ctx.guild.id, ctx.author.id, sebep)
        embed = premium_embed("💤 AFK Modu", f"**{ctx.author.display_name}** AFK modunda: *{sebep}*", renk=Renkler.BILGI)
        await ctx.send(embed=embed)

    # ── Mesaj Sil ──
    @commands.hybrid_command(description="Kanaldan mesaj sil (varsayılan 5)")
    @app_commands.default_permissions(manage_messages=True)
    @commands.guild_only()
    @commands.has_guild_permissions(manage_messages=True)
    async def sil(self, ctx, miktar: int = 5):
        """Belirtilen sayıda mesaj siler. Kullanım: !sil 10"""
        if miktar < 1 or miktar > 100:
            return await ctx.send("❌ 1-100 arası bir sayı gir.", delete_after=5)
        try:
            if ctx.interaction is None:  # /komutta silinecek/tepki verilecek mesaj yok
                await ctx.message.delete()
        except discord.NotFound:
            pass
        try:
            silinen = await ctx.channel.purge(limit=miktar)
        except discord.HTTPException as e:
            return await ctx.send(f"❌ Mesaj silinemedi: {e}", delete_after=7)
        msg = await ctx.send(f"✅ {len(silinen)} mesaj temizlendi.")
        await asyncio.sleep(3)
        try:
            await msg.delete()
        except discord.NotFound:
            pass

    # ── Bot ile Mesaj Yazdır ──
    @commands.hybrid_command(name="yaz", description="Seçilen kanala bot aracılığıyla mesaj gönder")
    @app_commands.describe(
        mesaj="Gönderilecek mesaj metni",
        kanal="Mesajın gönderileceği kanal (boş bırakılırsa bu kanal)"
    )
    @commands.guild_only()
    async def yaz(self, ctx, kanal: Optional[discord.TextChannel] = None, *, mesaj: str):
        """[Moderatör] Bota belirtilen kanalda mesaj yazdırır.
        Kullanım:
          /yaz kanal:#sohbet mesaj:Bu kanalda flood yasaktır
          /yaz mesaj:Bu kanalda flood yasaktır
          !yaz #sohbet Bu kanalda flood yasaktır
        """
        izinler_uye = ctx.author.guild_permissions
        if not (izinler_uye.manage_messages or izinler_uye.administrator or ctx.author.id in GUVENILIR_IDLER):
            return await ctx.send("❌ Bu komutu kullanmak için `Mesajları Yönet` yetkisine sahip olmalısın!", ephemeral=True, delete_after=5)

        hedef_kanal = kanal or ctx.channel

        # Botun hedef kanala mesaj gönderme yetkisi kontrolü
        bot_izinler = hedef_kanal.permissions_for(ctx.guild.me)
        if not bot_izinler.send_messages:
            return await ctx.send(f"❌ {hedef_kanal.mention} kanalına mesaj gönderme yetkim yok!", ephemeral=True, delete_after=5)

        metin = (mesaj or "").strip()
        if not metin:
            return await ctx.send("❌ Gönderilecek mesaj boş olamaz!", ephemeral=True, delete_after=5)

        if len(metin) > 2000:
            return await ctx.send("❌ Mesaj 2000 karakterden uzun olamaz!", ephemeral=True, delete_after=5)

        # Prefix komutsa (!yaz), komut mesajını sil
        try:
            if ctx.interaction is None:
                await ctx.message.delete()
        except (discord.NotFound, discord.Forbidden):
            pass

        # Mention güvenliği: kullanıcının mention_everyone yetkisi yoksa @everyone/@here tetiklenmez
        allowed = discord.AllowedMentions(
            everyone=bool(izinler_uye.mention_everyone or izinler_uye.administrator or ctx.author.id in GUVENILIR_IDLER),
            roles=bool(izinler_uye.mention_everyone or izinler_uye.administrator or ctx.author.id in GUVENILIR_IDLER),
            users=True
        )

        try:
            await hedef_kanal.send(metin, allowed_mentions=allowed)
        except discord.HTTPException as e:
            return await ctx.send(f"❌ Mesaj gönderilemedi: {e}", ephemeral=True, delete_after=5)

        # Yanıt: Slash komutsa sadece yazan görsün (ephemeral)
        if ctx.interaction:
            await ctx.send(f"✅ Mesaj {hedef_kanal.mention} kanalına gönderildi.", ephemeral=True)
        elif hedef_kanal.id != ctx.channel.id:
            await ctx.send(f"✅ Mesaj {hedef_kanal.mention} kanalına iletildi.", delete_after=3)

    # ── Kick ──
    @commands.hybrid_command(description="Üyeyi sunucudan at")
    @app_commands.default_permissions(kick_members=True)
    @commands.guild_only()
    @commands.has_guild_permissions(kick_members=True)
    async def at(self, ctx, uye: discord.Member, *, sebep="Sebep belirtilmedi"):
        """Kullanıcıyı sunucudan atar. Kullanım: !at @kişi sebep"""
        if await self.dokunulmazlik_kontrol(ctx, uye):
            return

        if uye.top_role >= ctx.author.top_role:
            return await ctx.send("❌ Kendinden üst rütbeli birini atamazsın!", delete_after=5)
        # Atılmadan önce DM gönder
        try:
            dm_embed = premium_embed("👢 Sunucudan Atıldın!", f"**{ctx.guild.name}** sunucusundan atıldın.", renk=Renkler.HATA)
            dm_embed.add_field(name="📝 Sebep", value=sebep, inline=False)
            await uye.send(embed=dm_embed)
        except (discord.Forbidden, discord.HTTPException):
            pass

        try:
            await uye.kick(reason=f"{ctx.author.name}: {sebep}")
            c = db.cursor()
            c.execute(
                "INSERT INTO moderasyon_log (sunucu_id, islem, hedef_id, moderator_id, sebep, tarih) VALUES (?, ?, ?, ?, ?, ?)",
                (ctx.guild.id, "KICK", uye.id,ctx.author.id, sebep, datetime.datetime.now(datetime.timezone.utc).isoformat()))
            db.commit()
            embed = discord.Embed(color=Renkler.HATA, timestamp=datetime.datetime.now(datetime.timezone.utc))
            embed.set_author(name="👢 Kullanıcı Atıldı", icon_url=ctx.author.display_avatar.url)
            embed.description = (
                f"{bilgi_kutusu(('👤', 'Kullanıcı', f'{uye.display_name} (`{uye.id}`)'), ('🔨', 'Moderatör', ctx.author.mention), ('📝', 'Sebep', sebep))}"
            )
            embed.set_footer(text="MezarBot • Moderasyon")
            await ctx.send(embed=embed)
        except discord.Forbidden:
            await ctx.send("❌ Bu kullanıcıyı atmak için yetkim yok!", delete_after=5)
        except Exception as e:
            logger.error(f"Kick hatası: {e}")
            await ctx.send(f"❌ Bir hata oluştu: {e}", delete_after=7)

    # ── Ban ──
    @commands.hybrid_command(description="Üyeyi sunucudan yasakla")
    @app_commands.default_permissions(ban_members=True)
    @commands.guild_only()
    @commands.has_guild_permissions(ban_members=True)
    async def yasak(self, ctx, uye: discord.Member, *, sebep="Sebep belirtilmedi"):
        """Kullanıcıyı sunucudan yasaklar. Kullanım: !yasak @kişi sebep"""
        if await self.dokunulmazlik_kontrol(ctx, uye):
            return

        if uye.top_role >= ctx.author.top_role:
            return await ctx.send("❌ Kendinden üst rütbeli birini yasaklayamazsın!", delete_after=5)
        # Yasaklanmadan önce DM gönder
        try:
            dm_embed = premium_embed("🔨 Sunucudan Yasaklandın!", f"**{ctx.guild.name}** sunucusundan yasaklandın.", renk=Renkler.HATA)
            dm_embed.add_field(name="📝 Sebep", value=sebep, inline=False)
            await uye.send(embed=dm_embed)
        except (discord.Forbidden, discord.HTTPException):
            pass

        try:
            await uye.ban(reason=f"{ctx.author.name}: {sebep}", delete_message_seconds=86400)
            c = db.cursor()
            c.execute(
                "INSERT INTO moderasyon_log (sunucu_id, islem, hedef_id, moderator_id, sebep, tarih) VALUES (?, ?, ?, ?, ?, ?)",
                (ctx.guild.id, "BAN", uye.id,ctx.author.id, sebep, datetime.datetime.now(datetime.timezone.utc).isoformat()))
            db.commit()
            embed = discord.Embed(color=Renkler.HATA, timestamp=datetime.datetime.now(datetime.timezone.utc))
            embed.set_author(name="🔨 Kullanıcı Yasaklandı", icon_url=ctx.author.display_avatar.url)
            embed.description = (
                f"{bilgi_kutusu(('👤', 'Kullanıcı', f'{uye.display_name} (`{uye.id}`)'), ('🔨', 'Moderatör', ctx.author.mention), ('📝', 'Sebep', sebep))}"
            )
            embed.set_footer(text="MezarBot • Moderasyon")
            await ctx.send(embed=embed)
        except discord.Forbidden:
            await ctx.send("❌ Bu kullanıcıyı yasaklamak için yetkim yok!", delete_after=5)
        except Exception as e:
            logger.error(f"Ban hatası: {e}")
            await ctx.send(f"❌ Bir hata oluştu: {e}", delete_after=7)

    # ══════════════════════════════════════════════
    #  SUNUCU AYARLARI (çok sunuculu)
    # ══════════════════════════════════════════════

    def _ayarlar_embedi(self, guild: discord.Guild) -> discord.Embed:
        ayar = sunucu_ayar_al(guild.id) or {}
        lang = sunucu_dil_al(guild.id)

        def kanal(kanal_id):
            return f"<#{kanal_id}>" if kanal_id else ("`not set`" if lang == "en" else "`ayarlı değil`")

        def acik_mi(deger):
            if lang == "en":
                return "✅ Enabled" if deger else "❌ Disabled"
            return "✅ Açık" if deger else "❌ Kapalı"

        otorol = guild.get_role(ayar.get('otorol_id') or 0)
        kelime = kelime_oyunu_al(guild.id) or {}

        if lang == "en":
            satirlar = [
                ("🌐 Server Language", "**🇬🇧 English**", "/dil tr · en  (or the buttons below)"),
                ("📋 Log Channel", kanal(ayar.get('log_kanal_id')), "!logayarla #channel"),
                ("⚠️ Warning Channel", kanal(ayar.get('uyari_kanal_id')), "!uyarayarla #channel"),
                ("👋 Welcome Channel", kanal(ayar.get('hosgeldin_kanal_id')), "!hosgeldinayarla #channel [msg]"),
                ("📤 Goodbye Channel", kanal(ayar.get('gorusuruz_kanal_id')), "!gorusuruzayarla #channel"),
                ("🏷️ Auto-role", otorol.mention if otorol else "`not set`", "!otorolayarla @role"),
                ("📢 Patch Notes", kanal(ayar.get('yama_notlari_kanal_id')), "!yamanotukanal #channel · off"),
                ("🤖 Auto-mod", acik_mi(ayar.get('otomod_aktif')), "!otomod"),
                ("🗳️ Vote Skip", acik_mi(ayar.get('oygec_aktif')), "!oygec on · off"),
            ]
            embed = discord.Embed(color=Renkler.BILGI, timestamp=datetime.datetime.now(datetime.timezone.utc))
            embed.set_author(name=f"⚙️ {guild.name} — MezarBot Settings")
            embed.description = "\n".join(f"**{ad}:** {deger}\n> `{komut}`" for ad, deger, komut in satirlar)
            embed.set_footer(text="Unconfigured features are disabled on this server • MezarBot")
        else:
            satirlar = [
                ("🌐 Sunucu Dili", "**🇹🇷 Türkçe**", "/dil tr · en  (ya da aşağıdaki butonlar)"),
                ("📋 Log kanalı", kanal(ayar.get('log_kanal_id')), "!logayarla #kanal"),
                ("⚠️ Uyarı kanalı", kanal(ayar.get('uyari_kanal_id')), "!uyarayarla #kanal"),
                ("👋 Hoşgeldin kanalı", kanal(ayar.get('hosgeldin_kanal_id')), "!hosgeldinayarla #kanal [mesaj]"),
                ("📤 Görüşürüz kanalı", kanal(ayar.get('gorusuruz_kanal_id')), "!gorusuruzayarla #kanal"),
                ("🏷️ Otorol", otorol.mention if otorol else "`ayarlı değil`", "!otorolayarla @rol"),
                ("📢 Yama notları", kanal(ayar.get('yama_notlari_kanal_id')), "!yamanotukanal #kanal · kapat"),
                ("🤖 Oto-mod", acik_mi(ayar.get('otomod_aktif')), "!otomod"),
                ("🗳️ Oy ile geç", acik_mi(ayar.get('oygec_aktif')), "!oygec ac · kapat"),
            ]
            embed = discord.Embed(color=Renkler.BILGI, timestamp=datetime.datetime.now(datetime.timezone.utc))
            embed.set_author(name=f"⚙️ {guild.name} — MezarBot Ayarları")
            embed.description = "\n".join(f"**{ad}:** {deger}\n> `{komut}`" for ad, deger, komut in satirlar)
            embed.set_footer(text="Ayarlanmamış özellikler bu sunucuda devre dışıdır • MezarBot")
        return embed

    @commands.hybrid_command(name="ayarlar", description="Sunucunun bot ayarlarını göster ve değiştir")
    @app_commands.default_permissions(manage_guild=True)
    @commands.guild_only()
    @commands.check(yonetici_kontrol)
    async def ayarlar(self, ctx):
        """[Yönetici] Bu sunucunun MezarBot ayarlarını ve dilini gösterir/değiştirir."""
        embed = self._ayarlar_embedi(ctx.guild)
        view = AyarlarDilGorunumu(self, ctx.guild.id)
        await ctx.send(embed=embed, view=view)

    @commands.hybrid_command(name="settings", description="View and change bot settings and language for this server")
    @app_commands.default_permissions(manage_guild=True)
    @commands.guild_only()
    @commands.check(yonetici_kontrol)
    async def settings(self, ctx):
        """[Admin] View and change bot settings and language for this server."""
        embed = self._ayarlar_embedi(ctx.guild)
        view = AyarlarDilGorunumu(self, ctx.guild.id)
        await ctx.send(embed=embed, view=view)

    @commands.hybrid_command(name="dil", aliases=["language", "lang"], description="Sunucunun bot dilini değiştirir (tr / en)")
    @app_commands.describe(yeni_dil="Seçilecek dil (tr / en)")
    @app_commands.choices(yeni_dil=[
        app_commands.Choice(name="🇹🇷 Türkçe", value="tr"),
        app_commands.Choice(name="🇬🇧 English", value="en")
    ])
    @app_commands.default_permissions(manage_guild=True)
    @commands.guild_only()
    @commands.check(yonetici_kontrol)
    async def dil_ayar(self, ctx, yeni_dil: str = "tr"):
        """[Yönetici] Botun bu sunucudaki varsayılan dilini ayarlar. Kullanım: !dil tr | !dil en | !language en"""
        dil_kod = sunucu_dil_ayarla(ctx.guild.id, yeni_dil)
        if dil_kod == "en":
            await ctx.send("✅ Server language set to **English**. The bot will now respond in English in this server.")
        else:
            await ctx.send("✅ Sunucu dili **Türkçe** olarak ayarlandı. Bot bu sunucuda artık Türkçe yanıt verecektir.")

    @commands.hybrid_command(description="Yama notu kanalını ayarla ya da kapat")
    @app_commands.default_permissions(manage_guild=True)
    @commands.guild_only()
    @commands.check(yonetici_kontrol)
    async def yamanotukanal(self, ctx, kanal: Optional[discord.TextChannel] = None, *, secenek: str = None):
        """[Yönetici] MezarBot yama notlarının (güncelleme duyurularının) geleceği kanalı ayarlar.
        Kullanım: !yamanotukanal #kanal  |  !yamanotukanal kapat  |  argümansız: bu kanal"""
        if kanal is None and secenek and secenek.lower() in ('kapat', 'kapali', 'kapalı', 'off'):
            sunucu_ayar_guncelle(ctx.guild.id, yama_notlari_kanal_id=None)
            return await ctx.send("🔕 Yama notları bu sunucuda kapatıldı.")
        hedef_kanal = kanal or ctx.channel
        sunucu_ayar_guncelle(ctx.guild.id, yama_notlari_kanal_id=hedef_kanal.id)
        await ctx.send(embed=premium_embed("📢 Yama Notu Kanalı Ayarlandı",
                                           f"MezarBot güncelleme notları artık {hedef_kanal.mention} kanalına gönderilecek.",
                                           renk=Renkler.BASARI))

    @commands.hybrid_command(name="yamanotu", description="[Bot Sahibi] Yama notunu tüm sunuculara duyurur")
    @app_commands.describe(metin="Yama notu metni")
    @commands.is_owner()
    async def yamanotu(self, ctx, *, metin: str):
        """[Bot Sahibi] Yama notunu, yama notu kanalı ayarlı olan TÜM sunuculara gönderir.
        Kanalı ayarlamamış sunucular atlanır."""
        if len(metin) > 4000:
            return await ctx.send("❌ Yama notu çok uzun! (Maks 4000 karakter)", ephemeral=True)
        embed = discord.Embed(title="📢 MezarBot Yama Notları", description=metin, color=Renkler.BILGI,
                              timestamp=datetime.datetime.now(datetime.timezone.utc))
        embed.set_footer(text="MezarBot • Güncelleme")
        gonderilen = atlanan = hatali = 0
        for guild in self.bot.guilds:
            kanal_id = (sunucu_ayar_al(guild.id) or {}).get('yama_notlari_kanal_id')
            kanal = guild.get_channel(kanal_id) if kanal_id else None
            if not kanal:
                atlanan += 1
                continue
            try:
                await kanal.send(embed=embed)
                gonderilen += 1
            except (discord.Forbidden, discord.HTTPException) as e:
                hatali += 1
                logger.warning(f"Yama notu gönderilemedi ({guild.name} / {guild.id}): {e}")
        await ctx.send(f"📢 Yama notu gönderildi: **{gonderilen}** sunucu · atlanan (kanal ayarsız): **{atlanan}** · hata: **{hatali}**")

    # ── Sahip Komutu: Slash Sync ──
    @commands.hybrid_command(name="sync", description="[Bot Sahibi] Slash komutlarını global senkronize eder")
    @commands.is_owner()
    async def sync_komut(self, ctx):
        """[Bot Sahibi] Komutları global senkronize eder ve sunuculardaki eski yerel kopyaları siler.
        (Global + sunucu kopyası birlikte olunca Discord her komutu iki kez gösterir.)"""
        mesaj = await ctx.send("🔄 Senkronizasyon başlatılıyor...")
        try:
            senkron = await self.bot.tree.sync()
            for g in self.bot.guilds:
                self.bot.tree.clear_commands(guild=g)
                await self.bot.tree.sync(guild=g)
            await mesaj.edit(content=f"✅ **{len(senkron)}** slash komutu global senkronize edildi, "
                                     f"{len(self.bot.guilds)} sunucudaki yerel kopyalar temizlendi. (Görünmüyorsa Ctrl+R)")
        except Exception as e:
            await mesaj.edit(content=f"❌ Senkronizasyon hatası: {e}")

    # ══════════════════════════════════════════════
    #  YARDIMCI METODLAR
    # ══════════════════════════════════════════════

    def sure_parse(self, sure_str):
        """'10m', '2h', '30s', '1d' gibi süreleri saniyeye çevirir."""
        sure_str = sure_str.lower().strip()
        if not sure_str:
            return None
        carpanlar = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}
        if sure_str[-1] in carpanlar:
            try:
                return int(sure_str[:-1]) * carpanlar[sure_str[-1]]
            except ValueError:
                return None
        try:
            return int(sure_str) * 60
        except ValueError:
            return None


async def setup(bot):
    await bot.add_cog(Yonetim(bot))
