import discord
from discord.ext import commands
from discord import app_commands
import logging
from database import (
    db, kelime_oyunu_al, kelime_oyunu_guncelle, kelime_oyunu_sayac_artir,
    vip_kontrol, yonetici_kontrol, sozluk_kontrol,
    kullanilan_kelime_kontrol, kullanilan_kelime_ekle, kullanilan_kelimeler_sifirla,
    kullanilan_kelime_sayisi, kelime_puan_artir, kelime_liderlik,
    basarim_ver, BASARIM_LISTESI, islem_kaydet, ekonomi_kaydi_olustur
)
from arayuz import Renkler, premium_embed, AYIRICI, sayi_formatla

logger = logging.getLogger('MezarBot.KelimeOyunu')


class KelimeOyunu(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.is_processing = set()

    def kelime_dogrula(self, kelime):
        """Kelimenin geçerli Türkçe kelime olup olmadığını kontrol eder.
        Tamamen yerel sözlük (turkce_sozluk tablosu — 64K+ kelime, offline, anında).
        TDK API'ye bağımlılık yok.
        """
        return sozluk_kontrol(kelime.lower())

    # ── Yönetim Komutları ─────────────────────────────
    @commands.hybrid_group(name="kelimeoyunu", fallback="durum", invoke_without_command=True, description="Kelime oyunu ayarları ve durumu")
    @app_commands.default_permissions(manage_guild=True)
    @commands.guild_only()
    @commands.check(yonetici_kontrol)
    async def kelimeoyunu(self, ctx):
        """Kelime oyunu ayarları ve durumu."""
        sayi = kullanilan_kelime_sayisi(ctx.guild.id)
        kayit = kelime_oyunu_al(ctx.guild.id)
        kanal_id = kayit.get('kanal_id') if kayit else None
        kanal_str = f"<#{kanal_id}>" if kanal_id else "Ayarlanmamış"
        embed = premium_embed(
            "📝 Kelime Oyunu Durumu",
            f"Kanal: {kanal_str}\n"
            f"Kullanılan Kelime Sayısı: `{sayi}`\n\n"
            f"**Komutlar:**\n"
            f"`/kelimeoyunu kanal [#kanal]` — Oyun kanalını ayarla\n"
            f"`/kelimeoyunu sifirla` — Oyunu sıfırla\n"
            f"`/kelimepuan` — Liderlik tablosu",
            renk=Renkler.BILGI
        )
        await ctx.send(embed=embed)

    @kelimeoyunu.command(name="kanal", description="Kelime oyunu kanalını ayarlar")
    @app_commands.describe(kanal="Kelime oyununun oynanacağı kanal (boşsa mevcut kanal)")
    @commands.check(yonetici_kontrol)
    async def kanal(self, ctx, kanal: discord.TextChannel = None):
        """Kelime oyunu kanalını ayarlar."""
        hedef_kanal = kanal or ctx.channel
        kelime_oyunu_guncelle(ctx.guild.id, kanal_id=hedef_kanal.id, son_kelime='', son_kullanici_id=0)
        kullanilan_kelimeler_sifirla(ctx.guild.id)
        await ctx.send(f"✅ Kelime oyunu kanalı {hedef_kanal.mention} olarak ayarlandı!")

    @kelimeoyunu.command(name="sifirla", aliases=["sıfırla", "reset"], description="Kelime oyununu sıfırlar (son kelime ve kullanılanlar)")
    @commands.check(yonetici_kontrol)
    async def sıfırla_komut(self, ctx):
        """Kelime oyununu sıfırlar (son kelime + kullanılan kelimeler)."""
        try:
            kelime_oyunu_guncelle(ctx.guild.id, son_kelime='', son_kullanici_id=0)
            kullanilan_kelimeler_sifirla(ctx.guild.id)
            await ctx.send("✅ Kelime oyunu sıfırlandı! Tüm kelimeler tekrar kullanılabilir.")
        except Exception as e:
            logger.error(f"Sıfırlama hatası: {e}")
            await ctx.send("❌ Sıfırlarken bir hata oluştu.")

    # ── Oyun Listener ─────────────────────────────
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild or not message.content or message.content.startswith('!'):
            return
        if self.bot.user.mentioned_in(message) and not message.mention_everyone:
            return

        kayit = kelime_oyunu_al(message.guild.id)
        if not kayit or message.channel.id != kayit.get('kanal_id'):
            return

        if message.channel.id in self.is_processing:
            return

        is_vip = vip_kontrol(message.author)
        kelime = message.content.strip().lower()

        if not kelime:
            return

        # Tek kelime kontrolü (boşluk varsa birden fazla kelime — isalpha'dan önce kontrol)
        if len(kelime.split()) > 1:
            if not is_vip:
                try: await message.delete()
                except (discord.NotFound, discord.Forbidden): pass
            return await message.channel.send(
                f"⚠️ {message.author.mention}, sadece **tek bir kelime** yazmalısın!", delete_after=5)

        if not kelime.isalpha():
            return

        self.is_processing.add(message.channel.id)

        try:

            son_kelime = kayit.get('son_kelime', '')
            son_kullanici_id = kayit.get('son_kullanici_id', 0)

            # Aynı kişi üst üste yazamaz
            if message.author.id == son_kullanici_id:
                if not is_vip:
                    try: await message.delete()
                    except (discord.NotFound, discord.Forbidden): pass
                return await message.channel.send(
                    f"⚠️ {message.author.mention}, **üst üste iki kelime** yazamazsın!", delete_after=5)

            # Harf kontrolü
            if son_kelime:
                son_kelime_temiz = son_kelime.replace('İ', 'i').replace('I', 'ı').lower()
                son_harf = son_kelime_temiz[-1]

                if son_harf == 'ğ':
                    son_harf = son_kelime_temiz[-2] if len(son_kelime_temiz) > 1 else 'g'

                if not kelime.startswith(son_harf):
                    if not is_vip:
                        try: await message.delete()
                        except (discord.NotFound, discord.Forbidden): pass
                    return await message.channel.send(
                        f"⚠️ {message.author.mention}, kelime **'{son_harf.upper()}'** harfi ile başlamalı!", delete_after=5)

            # Tekrar kontrolü
            if kullanilan_kelime_kontrol(message.guild.id, kelime):
                if not is_vip:
                    try: await message.delete()
                    except (discord.NotFound, discord.Forbidden): pass
                return await message.channel.send(
                    f"⚠️ {message.author.mention}, **'{kelime}'** daha önce kullanıldı!", delete_after=5)

            # Sözlük doğrulama (tamamen yerel — 64K+ kelime)
            if not self.kelime_dogrula(kelime):
                if not is_vip:
                    try: await message.delete()
                    except (discord.NotFound, discord.Forbidden): pass
                return await message.channel.send(
                    f"❌ {message.author.mention}, **'{kelime}'** geçerli bir Türkçe kelime değil!", delete_after=5)

            # ✅ Kelime kabul edildi
            try:
                kelime_oyunu_guncelle(message.guild.id, son_kelime=kelime, son_kullanici_id=message.author.id)
                kullanilan_kelime_ekle(message.guild.id, kelime)

                # Ödül bu sunucunun ekonomisine (sunucu bazlı bakiye)
                sunucu_id, kullanici_id = message.guild.id, message.author.id
                ekonomi_kaydi_olustur(sunucu_id, kullanici_id)
                c = db.cursor()
                c.execute("UPDATE ekonomi SET bakiye = bakiye + 10 WHERE sunucu_id = ? AND kullanici_id = ?",
                          (sunucu_id, kullanici_id))
                db.commit()

                yeni_sayi = kelime_oyunu_sayac_artir(message.guild.id)
                kisi_puan = kelime_puan_artir(message.guild.id, message.author.id)
                islem_kaydet(sunucu_id, kullanici_id, 'kelime_oyunu', 10, f'Kelime: {kelime}')

                kelime_temiz = kelime.replace('İ', 'i').replace('I', 'ı').lower()
                siradaki_harf = kelime_temiz[-1]
                if siradaki_harf == 'ğ':
                    siradaki_harf = kelime_temiz[-2] if len(kelime_temiz) > 1 else 'g'

                await message.add_reaction("✅")
                # Sıradaki harfi sadece reaction ile belirt — chat kirliliğini önle
                harf_emoji_map = {
                    'a': '🇦', 'b': '🇧', 'c': '🇨', 'd': '🇩', 'e': '🇪', 'f': '🇫',
                    'g': '🇬', 'h': '🇭', 'i': '🇮', 'j': '🇯', 'k': '🇰', 'l': '🇱',
                    'm': '🇲', 'n': '🇳', 'o': '🇴', 'p': '🇵', 'r': '🇷', 's': '🇸',
                    't': '🇹', 'u': '🇺', 'v': '🇻', 'y': '🇾', 'z': '🇿',
                    'ç': '🇨', 'ş': '🇸', 'ö': '🇴', 'ü': '🇺', 'ı': '🇮',
                }
                harf_reaction = harf_emoji_map.get(siradaki_harf, '🔤')
                try:
                    await message.add_reaction(harf_reaction)
                except discord.HTTPException:
                    pass

                # Başarım: Kelime ustası (50 kelime)
                if kisi_puan >= 50:
                    if basarim_ver(sunucu_id, kullanici_id, 'kelime_ustasi'):
                        try:
                            bilgi = BASARIM_LISTESI['kelime_ustasi']
                            embed = premium_embed(
                                f"🏅 Başarım: {bilgi['emoji']} {bilgi['isim']}",
                                f"{bilgi['aciklama']}\nTebrikler {message.author.mention}!",
                                renk=0xFFD700
                            )
                            await message.channel.send(embed=embed, delete_after=15)
                        except Exception:
                            pass

                if yeni_sayi and yeni_sayi % 50 == 0:
                    embed = premium_embed(
                        "🎉 Kelime Oyunu Milestone!",
                        f"Bu sunucuda toplam **{yeni_sayi}** kelime yazıldı! Tebrikler!",
                        renk=Renkler.BASARI
                    )
                    await message.channel.send(embed=embed)
            except Exception as e:
                logger.error(f"DB güncelleme hatası: {e}")
        finally:
            self.is_processing.discard(message.channel.id)


    @commands.hybrid_command(description="Kelime oyunu puan tablosu")
    @commands.guild_only()
    async def kelimepuan(self, ctx):
        """Kelime oyunu liderlik tablosunu gösterir."""
        sonuclar = kelime_liderlik(ctx.guild.id, 10)
        if not sonuclar:
            return await ctx.send("📝 Henüz kelime oyunu puanı yok.", delete_after=7)

        madalyalar = ["🥇", "🥈", "🥉"]
        satirlar = []
        for i, (kullanici_id, puan) in enumerate(sonuclar):
            kullanici = self.bot.get_user(kullanici_id)
            isim = kullanici.display_name if kullanici else f"Bilinmeyen ({kullanici_id})"
            medal = madalyalar[i] if i < 3 else f"`#{i+1}`"
            satirlar.append(f"{medal} **{isim}** — `{puan}` kelime")

        embed = premium_embed(
            "📝 Kelime Oyunu Liderlik Tablosu",
            f"{AYIRICI}\n" + "\n".join(satirlar) + f"\n{AYIRICI}",
            renk=Renkler.BILGI
        )
        embed.set_footer(text=f"MezarBot • {ctx.guild.name}")
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(KelimeOyunu(bot))
