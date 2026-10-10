import discord
from discord import app_commands
from discord.ext import commands, tasks
import replicate
import aiohttp
import asyncio
import time
import datetime
import os
import logging
from collections import defaultdict
from database import db, bouncer_kontrol, vip_kontrol
from groq_yardimci import groq_istemci, groq_tamamla

logger = logging.getLogger('MezarBot.YapayZeka')

DISCORD_MESAJ_SINIRI = 1900


class YapayZeka(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ciz_kisisel_sure = {}
        self.ciz_global_sure = 0
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
            logger.warning("GROQ_API_KEY boş — AI sohbet devre dışı; !ciz prompt'ları çevrilmeden kullanılır.")
        if not (os.getenv("REPLICATE_API_TOKEN") or "").strip():
            logger.warning("REPLICATE_API_TOKEN boş — !ciz (resim çizimi) devre dışı.")

        self._kisilik = {}  # {kullanici_id: "normal" | "komik" | "akademik" | "agresif"}
        self._kisilik_promptlari = {
            "normal": (
                "Senin adın MezarBot. Discord'da takılan sıradan birisin. "
                "Sadece gerektiği kadar konuş. Genelde küçük harfle yaz. "
                "Kısa ve öz cevaplar ver. Emoji kullanabilirsin ama abartma. "
                "Eğer birisi sana kötü bir şey söylerse espriyle karşılık ver."
            ),
            "komik": (
                "Senin adın MezarBot. Sen çok komik ve eğlenceli bir botsun. "
                "Her şeye espriyle yaklaş, şakalar yap, komik benzetmeler kullan. "
                "Argo ve günlük dil kullan. Emojileri bol kullan. "
                "Ciddi sorulara bile hafif bir espriyle cevap ver."
            ),
            "akademik": (
                "Senin adın MezarBot. Sen bilgili ve akademik bir asistansın. "
                "Sorulara detaylı, bilimsel ve düzgün Türkçe ile cevap ver. "
                "Gerektiğinde kaynak belirt. Formal bir dil kullan. "
                "Açıklayıcı ve öğretici ol."
            ),
            "agresif": (
                "Senin adın MezarBot. Sen sert, laf sokucu ama eğlenceli bir botsun. "
                "İğneleyici ve alaycı cevaplar ver ama kırıcı olma. "
                "Rakip takıma laf sokar gibi konuş. Kendine güvenli ol. "
                "Küçük harfle ve günlük dil ile yaz."
            ),
        }
        self.mezar_prompt = self._kisilik_promptlari["normal"]

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
        temizlenecek_ciz = [uid for uid, t in self.ciz_kisisel_sure.items() if su_an - t > 300]
        for uid in temizlenecek_ciz:
            del self.ciz_kisisel_sure[uid]

        # Konuşma geçmişi: 30 dakikadır aktif olmayan kullanıcıları temizle
        temizlenecek_gecmis = [uid for uid, t in self._gecmis_son_aktif.items() if su_an - t > 1800]
        for uid in temizlenecek_gecmis:
            self.konusma_gecmisi.pop(uid, None)
            del self._gecmis_son_aktif[uid]

        # AI cooldown temizle
        temizlenecek_cd = [uid for uid, t in self._ai_cooldown.items() if su_an - t > 60]
        for uid in temizlenecek_cd:
            del self._ai_cooldown[uid]

    async def prompt_cevir(self, metin):
        if not self.ai_aktif or not self.client:
            return metin

        def istek_gonder():
            try:
                ceviri = groq_tamamla(self.client, [
                    {"role": "system",
                     "content": "You are a prompt translator. Translate the user's Turkish image request into a highly detailed English prompt suitable for Flux. Reply ONLY with the English translation."},
                    {"role": "user", "content": metin},
                ], temperature=0.3, max_tokens=600)
                return ceviri or metin
            except Exception as e:
                logger.error(f"Prompt çevirme hatası: {e}")
                return metin

        return await asyncio.to_thread(istek_gonder)

    async def ai_cevap_uret(self, anahtar, kullanici_id, mesaj):
        """anahtar: (sunucu_id, kullanici_id) — konuşma geçmişi sunucu bazlı tutulur.
        Kişilik tercihi kullanıcı bazlıdır (kullanici_id)."""
        if not self.ai_aktif or not self.client:
            return "Beynim yok şu an."

        # Geçmişin kopyasını al (thread safety — list shared between event loop and thread)
        gecmis_kopya = list(self.konusma_gecmisi[anahtar])

        def istek_gonder():
            try:
                kisilik = self._kisilik.get(kullanici_id, "normal")
                aktif_prompt = self._kisilik_promptlari.get(kisilik, self.mezar_prompt)
                mesajlar = [{"role": "system", "content": aktif_prompt}]
                mesajlar.extend(gecmis_kopya)
                mesajlar.append({"role": "user", "content": mesaj})

                cevap = groq_tamamla(self.client, mesajlar, temperature=0.6, max_tokens=900)
                return cevap[:DISCORD_MESAJ_SINIRI] if cevap else "bi hata oldu ya, kusura bakma"
            except Exception as e:
                logger.error(f"AI cevap hatası: {e}")
                return "bi hata oldu ya, kusura bakma"

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

    @commands.hybrid_command(name="ciz", description="Yapay zekâ ile resim çiz / Draw an image with AI")
    async def ciz(self, ctx, *, prompt: str):
        """AI ile resim çizer. Kullanım: !ciz bir kedi uzayda / !draw a cat in space"""
        if len(prompt) > 500:
            return await ctx.send("❌ Prompt çok uzun! (Maks 500 karakter)", delete_after=5)
        if not (os.getenv("REPLICATE_API_TOKEN") or "").strip():
            return await ctx.send("❌ Çizim özelliği şu an devre dışı.", delete_after=7)
        vip_mi = vip_kontrol(ctx.author)
        su_an = time.time()
        kullanici_id = ctx.author.id

        if not vip_mi:
            if su_an - self.ciz_global_sure < 45:
                return await ctx.send(
                    f"⏳ **Global Soğuma:** Bot resim çiziyor. Lütfen **{int(45 - (su_an - self.ciz_global_sure))} sn** bekle.",
                    delete_after=7)
            son_kullanim = self.ciz_kisisel_sure.get(kullanici_id, 0)
            if su_an - son_kullanim < 60:
                return await ctx.send(
                    f"⏳ **Kişisel Soğuma:** Yeni istek için **{int(60 - (su_an - son_kullanim))} sn** bekle.",
                    delete_after=7)

        bugun = datetime.date.today().isoformat()
        c = db.cursor()
        c.execute("SELECT kalan_hak, son_kullanim FROM cizim_haklari WHERE kullanici_id = ?", (kullanici_id,))
        kayit = c.fetchone()
        kalan_hak = 5

        if kayit:
            kayitli_hak, son_tarih = kayit[0], kayit[1]
            if son_tarih != bugun:
                kalan_hak = 5
            else:
                kalan_hak = kayitli_hak

        if not vip_mi and kalan_hak <= 0:
            return await ctx.send(f"❌ **{ctx.author.name}**, bugünkü bedava çizim hakkını tükettin.", delete_after=7)

        yeni_hak = kalan_hak
        if not vip_mi:
            yeni_hak -= 1
            self.ciz_kisisel_sure[kullanici_id] = su_an
            self.ciz_global_sure = su_an
            c.execute("REPLACE INTO cizim_haklari (kullanici_id, kalan_hak, son_kullanim) VALUES (?, ?, ?)",
                       (kullanici_id, yeni_hak, bugun))
            db.commit()

        hak_metni = "SINIRSIZ (VIP)" if vip_mi else f"{yeni_hak}/5"
        bekleme = await ctx.send(
            f"🚀 **{ctx.author.name}**, motor ateşlendi (Kalan Hak: **{hak_metni}**). *Çevriliyor...*")
        ingilizce_prompt = await self.prompt_cevir(prompt)

        async def resim_istegi():
            token = os.getenv("REPLICATE_API_TOKEN")
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "User-Agent": "MezarBot/1.0"
            }
            payload = {
                "input": {
                    "prompt": ingilizce_prompt,
                    "num_outputs": 1,
                    "aspect_ratio": "1:1",
                    "output_format": "png"
                }
            }
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.post(
                    "https://api.replicate.com/v1/models/black-forest-labs/flux-schnell/predictions",
                    json=payload
                ) as resp:
                    if resp.status not in (200, 201):
                        err_text = await resp.text()
                        raise ValueError(f"Replicate API hatası ({resp.status}): {err_text}")
                    data = await resp.json()
                    get_url = data.get("urls", {}).get("get")
                    if not get_url:
                        raise ValueError("Replicate get URL dönmedi")

                for _ in range(45):
                    await asyncio.sleep(1)
                    async with session.get(get_url) as resp:
                        if resp.status == 200:
                            poll_data = await resp.json()
                            status = poll_data.get("status")
                            if status == "succeeded":
                                out = poll_data.get("output")
                                if out and isinstance(out, list) and len(out) > 0:
                                    return str(out[0])
                                raise ValueError("Replicate boş çıktı döndü")
                            elif status in ("failed", "canceled"):
                                raise ValueError(poll_data.get("error") or "Çizim işlemi iptal/başarısız oldu")
                raise TimeoutError("Çizim işlemi zaman aşımına uğradı (45 sn)")

        try:
            resim_linki = await resim_istegi()
            embed = discord.Embed(color=0xEB459E, timestamp=datetime.datetime.now(datetime.timezone.utc))
            embed.set_author(name="🖼️ MezarBot Çizim", icon_url=ctx.author.display_avatar.url)
            embed.description = (
                f"> 🇹🇷 {prompt}\n"
                f"> 🇬🇧 *{ingilizce_prompt}*"
            )
            embed.set_image(url=resim_linki)
            embed.set_footer(text=f"MezarBot • Flux Schnell │ Kalan Hak: {hak_metni}")
            await bekleme.delete()
            await ctx.send(embed=embed)
        except Exception as e:
            logger.error(f"Çizim Hatası: {e}")
            if not vip_mi:
                self.ciz_kisisel_sure[kullanici_id] = 0
                c = db.cursor()
                c.execute("UPDATE cizim_haklari SET kalan_hak = kalan_hak + 1 WHERE kullanici_id = ?",
                           (kullanici_id,))
                db.commit()
            try:
                await bekleme.edit(content="❌ Çizim Hatası: API sorunu. Hakkın iade edildi.")
            except Exception:
                pass

    @commands.hybrid_command(name="draw", description="Draw an image with AI")
    @app_commands.describe(prompt="Description of the image")
    async def draw(self, ctx, *, prompt: str):
        """Draw an image with AI. Usage: /draw a cat in space or !draw a cat in space"""
        await self.ciz(ctx, prompt=prompt)

    @commands.hybrid_command(name="sifirla", aliases=["reset"], description="Yapay zekâ sohbet geçmişini sıfırla / Reset AI chat history")
    async def sifirla(self, ctx):
        """AI sohbet geçmişini (bu sunucudaki) sıfırlar."""
        anahtar = (ctx.guild.id if ctx.guild else 0, ctx.author.id)
        self.konusma_gecmisi.pop(anahtar, None)
        self._gecmis_son_aktif.pop(anahtar, None)
        await ctx.send("🧹 Sohbet geçmişin sıfırlandı!", delete_after=5)

    @commands.hybrid_command(description="Yapay zekânın kişiliğini seç")
    async def kisilik(self, ctx, mod: str = None):
        """AI kişilik modunu değiştirir. Kullanım: !kisilik komik"""
        modlar = list(self._kisilik_promptlari.keys())
        if not mod or mod.lower() not in modlar:
            mevcut = self._kisilik.get(ctx.author.id, "normal")
            mod_listesi = " / ".join(f"**{m}**" if m != mevcut else f"~~{m}~~" for m in modlar)
            return await ctx.send(
                f"🎭 Mevcut kişilik: **{mevcut}**\n"
                f"Kullanım: `!kisilik <mod>`\n"
                f"Modlar: {mod_listesi}",
                delete_after=10)
        mod = mod.lower()
        self._kisilik[ctx.author.id] = mod
        # Geçmişi sıfırla (yeni kişilikle temiz başla)
        self.konusma_gecmisi.pop((ctx.guild.id if ctx.guild else 0, ctx.author.id), None)
        emoji_map = {"normal": "😐", "komik": "😂", "akademik": "🎓", "agresif": "😈"}
        await ctx.send(f"{emoji_map.get(mod, '🎭')} AI kişilik modu **{mod}** olarak ayarlandı!", delete_after=7)

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
                    return await message.reply("⏳ Biraz yavaş, 5 saniye bekle.", delete_after=3)
                self._ai_cooldown[message.author.id] = su_an

                async with message.channel.typing():
                    cvp = await self.ai_cevap_uret((message.guild.id, message.author.id), message.author.id, temiz)
                    await message.reply(cvp)


async def setup(bot):
    await bot.add_cog(YapayZeka(bot))
