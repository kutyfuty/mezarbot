import discord
from discord.ext import commands, tasks
from discord import app_commands
import aiohttp
import ssl
import datetime
import logging
from database import db, yonetici_kontrol, sunucu_ayar_al, sunucu_ayar_guncelle
from arayuz import Renkler, AYIRICI, bilgi_kutusu

logger = logging.getLogger('MezarBot.OyunIndirimleri')

# Epic Games REST API (static backend — GraphQL endpoint kaldırıldı)
EPIC_FREE_URL = "https://store-site-backend-static-ipv4.ak.epicgames.com/freeGamesPromotions"
EPIC_FREE_PARAMS = {"locale": "tr", "country": "TR", "allowCountries": "TR"}

CHEAPSHARK_API = "https://www.cheapshark.com/api/1.0/deals"
CHEAPSHARK_GAMES_API = "https://www.cheapshark.com/api/1.0/games"

# Bilinen mağaza ID → isim + emoji
MAGAZA_MAP = {
    "1": ("Steam", "🟦"),
    "2": ("GamersGate", "🎮"),
    "3": ("GreenManGaming", "🟩"),
    "7": ("GOG", "🟣"),
    "8": ("Origin", "🟠"),
    "11": ("Humble Bundle", "📦"),
    "13": ("Uplay", "⬜"),
    "15": ("Fanatical", "🔴"),
    "21": ("WinGameStore", "🪟"),
    "23": ("GameBillet", "🎫"),
    "24": ("Voidu", "🔵"),
    "25": ("Epic Games", "⬛"),
    "27": ("Gamesplanet", "🌍"),
    "28": ("Gamesload", "📥"),
    "29": ("2Game", "2️⃣"),
    "30": ("IndieGala", "🎪"),
    "31": ("Blizzard", "❄️"),
    "33": ("DLGamer", "📀"),
    "34": ("Noctre", "🌙"),
    "35": ("DreamGame", "💭"),
}

# Platform renkleri
EPIC_RENK = 0x2F2D2E
STEAM_RENK = 0x1B2838


class OyunIndirimleri(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.session = None
        self.kontrol_dongusu.start()

    async def cog_unload(self):
        self.kontrol_dongusu.cancel()
        if self.session and not self.session.closed:
            await self.session.close()

    async def _session_al(self):
        if self.session is None or self.session.closed:
            # certifi CA bundle ile güvenli SSL context
            ssl_ctx = ssl.create_default_context()
            try:
                import certifi
                ssl_ctx.load_verify_locations(certifi.where())
            except ImportError:
                pass
            connector = aiohttp.TCPConnector(ssl=ssl_ctx)
            self.session = aiohttp.ClientSession(connector=connector)
        return self.session

    # ══════════════════════════════════════════════
    #  KANAL AYARI
    # ══════════════════════════════════════════════

    @commands.hybrid_command(description="Oyun fırsatları kanalını ayarla")
    @app_commands.default_permissions(manage_guild=True)
    @commands.guild_only()
    @commands.check(yonetici_kontrol)
    async def oyunayarla(self, ctx, kanal: discord.TextChannel = None):
        """Oyun fırsatlarının gönderileceği kanalı ayarlar."""
        kanal = kanal or ctx.channel
        sunucu_ayar_guncelle(ctx.guild.id, oyun_kanal_id=kanal.id)

        embed = discord.Embed(color=Renkler.BASARI, timestamp=datetime.datetime.now())
        embed.set_author(name="✅ Oyun Fırsatları Kanalı Ayarlandı")
        embed.description = (
            f"{AYIRICI}\n"
            f"{bilgi_kutusu(('📢', 'Kanal', kanal.mention), ('🎮', 'İçerik', 'Epic bedava oyunlar + Steam indirimleri'), ('⏰', 'Kontrol', 'Her 30 dakikada bir'))}"
        )
        embed.set_footer(text="MezarBot • Oyun Fırsatları")
        await ctx.send(embed=embed)

    @commands.hybrid_command(description="Oyun fırsatı bildirimlerini kapat")
    @app_commands.default_permissions(manage_guild=True)
    @commands.guild_only()
    @commands.check(yonetici_kontrol)
    async def oyunkapat(self, ctx):
        """Oyun fırsatları bildirimlerini kapatır."""
        sunucu_ayar_guncelle(ctx.guild.id, oyun_kanal_id=0)

        embed = discord.Embed(color=Renkler.HATA, timestamp=datetime.datetime.now())
        embed.set_author(name="🔕 Oyun Fırsatları Kapatıldı")
        embed.description = f"{AYIRICI}\nArtık bu sunucuya oyun fırsatı gönderilmeyecek."
        embed.set_footer(text="MezarBot • Oyun Fırsatları")
        await ctx.send(embed=embed)

    @commands.hybrid_command(description="Bir oyunun fiyatını ve indirimlerini ara")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def oyunara(self, ctx, *, oyun_adi: str):
        """Bir oyunun tüm platformlardaki indirimlerini arar. Kullanım: !oyunara GTA V"""
        if len(oyun_adi) < 2:
            return await ctx.send("❌ En az 2 karakter gir.", delete_after=5)
        if len(oyun_adi) > 100:
            return await ctx.send("❌ Oyun adı çok uzun!", delete_after=5)

        bekleme = await ctx.send(f"🔍 **{oyun_adi}** aranıyor...")

        sonuclar = await self._oyun_ara(oyun_adi)

        try:
            await bekleme.delete()
        except discord.NotFound:
            pass

        if not sonuclar:
            return await ctx.send(f"❌ **{oyun_adi}** için indirim bulunamadı.", delete_after=7)

        embed = self._arama_embed_olustur(oyun_adi, sonuclar)
        await ctx.send(embed=embed)

    @commands.hybrid_command(description="Epic Games'teki bedava oyunlar")
    async def epicbedava(self, ctx):
        """Şu anki Epic Games bedava oyunlarını gösterir."""
        bekleme = await ctx.send("🔍 Epic Games bedava oyunlar kontrol ediliyor...")
        oyunlar = await self._epic_bedava_oyunlar_al()

        try:
            await bekleme.delete()
        except discord.NotFound:
            pass

        if not oyunlar:
            return await ctx.send("❌ Şu an Epic Games'te bedava oyun bulunamadı.", delete_after=7)
        for embed in self._epic_embedler_olustur(oyunlar):
            await ctx.send(embed=embed)

    @commands.hybrid_command(description="Steam'deki güncel fırsatlar")
    async def steamfirsatlari(self, ctx):
        """En iyi Steam indirimlerini gösterir."""
        bekleme = await ctx.send("🔍 Steam fırsatları kontrol ediliyor...")
        firsatlar = await self._steam_firsatlar_al()

        try:
            await bekleme.delete()
        except discord.NotFound:
            pass

        if not firsatlar:
            return await ctx.send("❌ Steam fırsatları alınamadı.", delete_after=7)
        embed = self._steam_embed_olustur(firsatlar)
        await ctx.send(embed=embed)

    # ══════════════════════════════════════════════
    #  EPIC GAMES BEDAVA OYUNLAR (GraphQL API)
    # ══════════════════════════════════════════════

    async def _epic_bedava_oyunlar_al(self):
        """Epic Games Store REST API'den bedava oyunları çeker."""
        try:
            session = await self._session_al()

            async with session.get(EPIC_FREE_URL, params=EPIC_FREE_PARAMS, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                if resp.status != 200:
                    logger.error(f"Epic Free Games API hata: {resp.status}")
                    return []
                data = await resp.json()

            oyunlar = []
            elements = data.get("data", {}).get("Catalog", {}).get("searchStore", {}).get("elements", [])

            for oyun in elements:
                promotions = oyun.get("promotions")
                if not promotions:
                    continue

                aktif_teklifler = promotions.get("promotionalOffers", [])
                yaklasan_teklifler = promotions.get("upcomingPromotionalOffers", [])

                durum = None
                baslangic = None
                bitis = None

                for grup in aktif_teklifler:
                    for teklif in grup.get("promotionalOffers", []):
                        if teklif.get("discountSetting", {}).get("discountPercentage") == 0:
                            durum = "aktif"
                            baslangic = teklif.get("startDate", "")
                            bitis = teklif.get("endDate", "")
                            break

                if not durum:
                    for grup in yaklasan_teklifler:
                        for teklif in grup.get("promotionalOffers", []):
                            if teklif.get("discountSetting", {}).get("discountPercentage") == 0:
                                durum = "yaklasan"
                                baslangic = teklif.get("startDate", "")
                                bitis = teklif.get("endDate", "")
                                break

                if not durum:
                    continue

                baslik = oyun.get("title", "Bilinmeyen")
                aciklama = oyun.get("description", "")
                orijinal_fiyat = "Bedava"

                fiyat_bilgisi = oyun.get("price", {}).get("totalPrice", {})
                if fiyat_bilgisi:
                    orijinal = fiyat_bilgisi.get("originalPrice", 0)
                    if orijinal > 0:
                        orijinal_fiyat = f"{orijinal / 100:.2f} TL"

                # Kapak resmi
                resim_url = None
                for img in oyun.get("keyImages", []):
                    if img.get("type") in ("OfferImageWide", "DieselStoreFrontWide", "Thumbnail"):
                        resim_url = img.get("url")
                        break
                if not resim_url:
                    images = oyun.get("keyImages", [])
                    if images:
                        resim_url = images[0].get("url")

                # Epic Store linki
                slug = None
                for mapping in oyun.get("catalogNs", {}).get("mappings", []):
                    slug = mapping.get("pageSlug")
                    if slug:
                        break
                if not slug:
                    slug = oyun.get("productSlug") or oyun.get("urlSlug", "")

                link = f"https://store.epicgames.com/tr/p/{slug}" if slug else "https://store.epicgames.com/tr/free-games"

                oyunlar.append({
                    "baslik": baslik,
                    "aciklama": aciklama[:200] + "..." if len(aciklama) > 200 else aciklama,
                    "orijinal_fiyat": orijinal_fiyat,
                    "resim": resim_url,
                    "link": link,
                    "durum": durum,
                    "baslangic": baslangic,
                    "bitis": bitis,
                    "id": oyun.get("id", baslik),
                })

            return oyunlar

        except Exception as e:
            logger.error(f"Epic Games API hatası: {e}")
            return []

    def _epic_embedler_olustur(self, oyunlar):
        """Epic bedava oyunlar için embed listesi döner."""
        embedler = []
        for oyun in oyunlar:
            if oyun["durum"] == "aktif":
                renk = 0x00D166
                durum_text = "🟢 ŞU AN BEDAVA"
            else:
                renk = 0xFEE75C
                durum_text = "🟡 YAKINDA BEDAVA"

            embed = discord.Embed(color=renk, timestamp=datetime.datetime.now())
            embed.set_author(name=f"🎮 Epic Games — {durum_text}")

            # Tarih formatla
            bitis_str = ""
            if oyun["bitis"]:
                try:
                    bitis_dt = datetime.datetime.fromisoformat(oyun["bitis"].replace("Z", "+00:00"))
                    bitis_str = bitis_dt.strftime("%d %b %Y, %H:%M")
                except (ValueError, TypeError):
                    bitis_str = ""

            kutu_satirlari = [('🎯', 'Oyun', f"**{oyun['baslik']}**")]
            if oyun["orijinal_fiyat"] != "Bedava":
                kutu_satirlari.append(('💰', 'Normal Fiyat', f"~~{oyun['orijinal_fiyat']}~~ → **BEDAVA**"))
            else:
                kutu_satirlari.append(('💰', 'Fiyat', '**BEDAVA**'))
            if bitis_str:
                etiket = "Bitiş" if oyun["durum"] == "aktif" else "Başlangıç"
                kutu_satirlari.append(('📅', etiket, bitis_str))

            embed.description = (
                f"{AYIRICI}\n"
                f"{bilgi_kutusu(*kutu_satirlari)}\n\n"
            )
            if oyun["aciklama"]:
                embed.description += f"> *{oyun['aciklama']}*\n\n"

            embed.description += f"[🔗 Epic Store'da Aç]({oyun['link']})"

            if oyun["resim"]:
                embed.set_image(url=oyun["resim"])

            embed.set_footer(text="MezarBot • Epic Games Free Games")
            embedler.append(embed)

        return embedler

    # ══════════════════════════════════════════════
    #  STEAM İNDİRİMLERİ (CheapShark API)
    # ══════════════════════════════════════════════

    async def _steam_firsatlar_al(self):
        """CheapShark API ile en iyi Steam indirimlerini çeker."""
        try:
            session = await self._session_al()
            params = {
                "storeID": "1",  # Steam
                "sortBy": "Deal Rating",
                "pageSize": "8",
                "onSale": "1",
            }
            async with session.get(CHEAPSHARK_API, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    logger.error(f"CheapShark API hata: {resp.status}")
                    return []
                data = await resp.json()

            firsatlar = []
            for deal in data:
                indirim = round(float(deal.get("savings", 0)))
                if indirim < 50:
                    continue

                normal_fiyat = deal.get("normalPrice", "?")
                indirimli_fiyat = deal.get("salePrice", "?")
                baslik = deal.get("title", "Bilinmeyen")
                deal_id = deal.get("dealID", "")
                thumb = deal.get("thumb", "")
                steam_id = deal.get("steamAppID", "")

                link = f"https://store.steampowered.com/app/{steam_id}" if steam_id else f"https://www.cheapshark.com/redirect?dealID={deal_id}"

                firsatlar.append({
                    "baslik": baslik,
                    "normal_fiyat": normal_fiyat,
                    "indirimli_fiyat": indirimli_fiyat,
                    "indirim": indirim,
                    "link": link,
                    "thumb": thumb,
                    "deal_id": deal_id,
                    "steam_id": steam_id,
                })

            return firsatlar[:8]

        except Exception as e:
            logger.error(f"CheapShark API hatası: {e}")
            return []

    def _steam_embed_olustur(self, firsatlar):
        """Steam indirim embed'i oluşturur."""
        embed = discord.Embed(color=STEAM_RENK, timestamp=datetime.datetime.now())
        embed.set_author(name="🎮 Steam — En İyi Fırsatlar")

        satirlar = [f"{AYIRICI}\n"]
        for i, f in enumerate(firsatlar, 1):
            indirim_bar = f"**-{f['indirim']}%**"
            satirlar.append(
                f"> **{i}.** [{f['baslik']}]({f['link']})\n"
                f">    {indirim_bar} ── ~~${f['normal_fiyat']}~~ → **${f['indirimli_fiyat']}**\n"
            )

        embed.description = "\n".join(satirlar)
        embed.set_footer(text="MezarBot • CheapShark API • Fiyatlar USD cinsindendir")

        if firsatlar and firsatlar[0]["thumb"]:
            embed.set_thumbnail(url=firsatlar[0]["thumb"])

        return embed

    # ══════════════════════════════════════════════
    #  OYUN ARAMA (CheapShark Games API)
    # ══════════════════════════════════════════════

    async def _oyun_ara(self, oyun_adi):
        """CheapShark Games API ile oyun arar ve en iyi fırsatları döner."""
        try:
            session = await self._session_al()

            # 1) Oyun ara
            params = {"title": oyun_adi, "limit": "5", "exact": "0"}
            async with session.get(CHEAPSHARK_GAMES_API, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    return []
                oyunlar = await resp.json()

            if not oyunlar:
                return []

            sonuclar = []
            for oyun in oyunlar[:5]:
                game_id = oyun.get("gameID")
                baslik = oyun.get("external", "Bilinmeyen")
                en_ucuz = oyun.get("cheapest", "?")
                thumb = oyun.get("thumb", "")

                # 2) Oyunun detaylarını al (tüm mağazalardaki fırsatlar)
                detail_params = {"id": game_id}
                async with session.get(CHEAPSHARK_GAMES_API, params=detail_params, timeout=aiohttp.ClientTimeout(total=15)) as resp2:
                    if resp2.status != 200:
                        continue
                    detay = await resp2.json()

                firsatlar = []
                for deal in detay.get("deals", [])[:6]:
                    store_id = deal.get("storeID", "")
                    magaza_adi, magaza_emoji = MAGAZA_MAP.get(store_id, (f"Mağaza #{store_id}", "🏪"))
                    fiyat = deal.get("price", "?")
                    perakende = deal.get("retailPrice", "?")
                    indirim_yuzdesi = deal.get("savings", "0")
                    deal_id = deal.get("dealID", "")

                    try:
                        indirim = round(float(indirim_yuzdesi))
                    except (ValueError, TypeError):
                        indirim = 0

                    if indirim < 1:
                        continue

                    link = f"https://www.cheapshark.com/redirect?dealID={deal_id}"

                    firsatlar.append({
                        "magaza": magaza_adi,
                        "emoji": magaza_emoji,
                        "fiyat": fiyat,
                        "perakende": perakende,
                        "indirim": indirim,
                        "link": link,
                    })

                if firsatlar:
                    sonuclar.append({
                        "baslik": baslik,
                        "en_ucuz": en_ucuz,
                        "thumb": thumb,
                        "firsatlar": firsatlar,
                    })

            return sonuclar

        except Exception as e:
            logger.error(f"Oyun arama hatası: {e}")
            return []

    def _arama_embed_olustur(self, aranan, sonuclar):
        """Oyun arama sonuçları embed'i."""
        embed = discord.Embed(color=0x5865F2, timestamp=datetime.datetime.now())
        embed.set_author(name=f"🔍 Arama Sonuçları — \"{aranan}\"")

        aciklama_satirlari = [f"{AYIRICI}\n"]

        for oyun in sonuclar[:3]:
            aciklama_satirlari.append(f"### 🎮 {oyun['baslik']}")
            aciklama_satirlari.append(f"> 💵 En ucuz: **${oyun['en_ucuz']}**\n")

            for f in oyun["firsatlar"][:5]:
                aciklama_satirlari.append(
                    f"> {f['emoji']} [{f['magaza']}]({f['link']}) ── "
                    f"**-{f['indirim']}%** ~~${f['perakende']}~~ → **${f['fiyat']}**"
                )
            aciklama_satirlari.append("")

        embed.description = "\n".join(aciklama_satirlari)

        if sonuclar and sonuclar[0]["thumb"]:
            embed.set_thumbnail(url=sonuclar[0]["thumb"])

        embed.set_footer(text="MezarBot • CheapShark API • Fiyatlar USD cinsindendir")
        return embed

    # ══════════════════════════════════════════════
    #  OTOMATİK KONTROL DÖNGÜSÜ
    # ══════════════════════════════════════════════

    @tasks.loop(minutes=30)
    async def kontrol_dongusu(self):
        """Her 30 dakikada bir Epic bedava oyunlari ve Steam firsatlarini kontrol eder."""

        # Oyun kanalı ayarlanmış sunucuları bul
        kanallar = []
        for guild in self.bot.guilds:
            ayar = sunucu_ayar_al(guild.id)
            if ayar and ayar.get("oyun_kanal_id"):
                kanal = guild.get_channel(ayar["oyun_kanal_id"])
                if kanal:
                    kanallar.append(kanal)

        if not kanallar:
            return

        c = db.cursor()

        # ── Epic Games Bedava Oyunlar ──
        try:
            oyunlar = await self._epic_bedava_oyunlar_al()
            for oyun in oyunlar:
                if oyun["durum"] != "aktif":
                    continue

                firsat_id = f"epic_{oyun['id']}"
                c.execute("SELECT id FROM gonderilen_firsatlar WHERE id = ?", (firsat_id,))
                if c.fetchone():
                    continue

                embedler = self._epic_embedler_olustur([oyun])
                for kanal in kanallar:
                    try:
                        for embed in embedler:
                            await kanal.send(embed=embed)
                    except (discord.Forbidden, discord.HTTPException) as e:
                        logger.warning(f"Epic embed gönderilemedi ({kanal.guild.name}): {e}")

                c.execute("INSERT OR IGNORE INTO gonderilen_firsatlar (id, tip, tarih) VALUES (?, ?, ?)",
                          (firsat_id, "epic", datetime.datetime.now().isoformat()))
                db.commit()

        except Exception as e:
            logger.error(f"Epic kontrol hatası: {e}")

        # ── Steam Fırsatları (günde 2 kez: 12:xx ve 20:xx arası) ──
        try:
            su_an = datetime.datetime.now()
            # 30dk loop olduğu için her saatte en az 1 kez geçer; sadece saat kontrol et
            if su_an.hour not in (12, 20):
                return

            steam_tarih_id = f"steam_{su_an.strftime('%Y-%m-%d_%H')}"
            c.execute("SELECT id FROM gonderilen_firsatlar WHERE id = ?", (steam_tarih_id,))
            if c.fetchone():
                return

            firsatlar = await self._steam_firsatlar_al()
            if not firsatlar:
                return

            embed = self._steam_embed_olustur(firsatlar)
            for kanal in kanallar:
                try:
                    await kanal.send(embed=embed)
                except (discord.Forbidden, discord.HTTPException) as e:
                    logger.warning(f"Steam embed gönderilemedi ({kanal.guild.name}): {e}")

            c.execute("INSERT OR IGNORE INTO gonderilen_firsatlar (id, tip, tarih) VALUES (?, ?, ?)",
                      (steam_tarih_id, "steam", su_an.isoformat()))
            db.commit()

            # Eski kayıtları temizle (7 günden eski)
            yedi_gun_once = (su_an - datetime.timedelta(days=7)).isoformat()
            c.execute("DELETE FROM gonderilen_firsatlar WHERE tarih < ?", (yedi_gun_once,))
            db.commit()

        except Exception as e:
            logger.error(f"Steam kontrol hatası: {e}")

    @kontrol_dongusu.before_loop
    async def kontrol_bekle(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(OyunIndirimleri(bot))
