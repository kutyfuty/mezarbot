from discord.ext import commands, tasks
import asyncio
import time
import logging
from collections import defaultdict
from groq_yardimci import groq_istemci, groq_tamamla
from dil import _t

logger = logging.getLogger('MezarBot.YapayZeka')

DISCORD_MESAJ_SINIRI = 1900


class YapayZeka(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.client = None
        self.ai_aktif = False
        # Konuşma geçmişi — her (sunucu_id, kullanici_id) çifti için son 5 mesaj.
        # Sunucu bazlı: bir sunucudaki sohbet bağlamı başka sunucuya taşınmaz.
        self.konusma_gecmisi = defaultdict(list)
        self.MAX_GECMIS = 5
        # Her kullanıcı için son etkileşim zamanı (bellek temizleme için)
        self._gecmis_son_aktif = {}
        # AI mention rate limiter: {kullanici_id: son_kullanim_zamani}
        self._ai_cooldown = {}

        self.client = groq_istemci()
        if self.client is not None:
            self.ai_aktif = True
            logger.info("✅ Groq AI motoru aktif.")
        else:
            logger.warning("GROQ_API_KEY boş — AI sohbet devre dışı.")

        self.mezar_prompt = (
            _t("Senin adın MezarBot. Discord'da takılan sıradan birisin. Sadece gerektiği kadar konuş. Genelde küçük harfle yaz. Kısa ve öz cevaplar ver. Emoji kullanabilirsin ama abartma. Eğer birisi sana kötü bir şey söylerse espriyle karşılık ver.")
        )

        # Bellek temizleme görevi
        self.bellek_temizle.start()

    def cog_unload(self):
        self.bellek_temizle.cancel()
        self.ai_aktif = False
        logger.info("✅ YapayZeka motoru durduruldu.")

    @tasks.loop(minutes=30)
    async def bellek_temizle(self):
        """30 dakikadır aktif olmayan kullanıcıların konuşma geçmişini temizler."""
        su_an = time.time()

        # Konuşma geçmişi: 30 dakikadır aktif olmayan kullanıcıları temizle
        temizlenecek_gecmis = [uid for uid, t in self._gecmis_son_aktif.items() if su_an - t > 1800]
        for uid in temizlenecek_gecmis:
            self.konusma_gecmisi.pop(uid, None)
            del self._gecmis_son_aktif[uid]

        # AI cooldown temizle
        temizlenecek_cd = [uid for uid, t in self._ai_cooldown.items() if su_an - t > 60]
        for uid in temizlenecek_cd:
            del self._ai_cooldown[uid]

    async def ai_cevap_uret(self, anahtar, mesaj):
        """anahtar: (sunucu_id, kullanici_id) — konuşma geçmişi sunucu bazlı tutulur."""
        if not self.ai_aktif or not self.client:
            return _t("Beynim yok şu an.")

        # Geçmişin kopyasını al (thread safety — list shared between event loop and thread)
        gecmis_kopya = list(self.konusma_gecmisi[anahtar])
        aktif_prompt = self.mezar_prompt

        def istek_gonder():
            try:
                mesajlar = [{"role": "system", "content": aktif_prompt}]
                mesajlar.extend(gecmis_kopya)
                mesajlar.append({"role": "user", "content": mesaj})

                cevap = groq_tamamla(self.client, mesajlar, temperature=0.6, max_tokens=900)
                return cevap[:DISCORD_MESAJ_SINIRI] if cevap else _t("bi hata oldu ya, kusura bakma")
            except Exception as e:
                logger.error(f"AI cevap hatası: {e}")
                return _t("bi hata oldu ya, kusura bakma")

        cevap = await asyncio.to_thread(istek_gonder)

        # Geçmişe kaydet (event loop thread'de — güvenli)
        gecmis = self.konusma_gecmisi[anahtar]
        gecmis.append({"role": "user", "content": mesaj})
        gecmis.append({"role": "assistant", "content": cevap})
        # Geçmişi sınırla
        if len(gecmis) > self.MAX_GECMIS * 2:
            self.konusma_gecmisi[anahtar] = gecmis[-(self.MAX_GECMIS * 2):]

        # Son aktif zamanı güncelle
        self._gecmis_son_aktif[anahtar] = time.time()

        return cevap

    @commands.hybrid_command(name="sifirla", aliases=["reset"], description="Yapay zekâ sohbet geçmişini sıfırla / Reset AI chat history")
    async def sifirla(self, ctx):
        """AI sohbet geçmişini (bu sunucudaki) sıfırlar."""
        anahtar = (ctx.guild.id if ctx.guild else 0, ctx.author.id)
        self.konusma_gecmisi.pop(anahtar, None)
        self._gecmis_son_aktif.pop(anahtar, None)
        await ctx.send(_t("🧹 Sohbet geçmişin sıfırlandı!"), delete_after=5)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return
        if self.bot.user.mentioned_in(message) and not message.mention_everyone:
            temiz = message.content.replace(f"<@{self.bot.user.id}>", "").strip()
            if temiz:
                # Rate limit: kişi başı 5 saniye cooldown
                su_an = time.time()
                son = self._ai_cooldown.get(message.author.id, 0)
                if su_an - son < 5:
                    return await message.reply(_t("⏳ Biraz yavaş, 5 saniye bekle."), delete_after=3)
                self._ai_cooldown[message.author.id] = su_an

                async with message.channel.typing():
                    cvp = await self.ai_cevap_uret((message.guild.id, message.author.id), temiz)
                    await message.reply(cvp)


async def setup(bot):
    await bot.add_cog(YapayZeka(bot))
