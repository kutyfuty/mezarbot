import discord
from discord.ext import commands, tasks
from discord import app_commands
import random
import datetime
import time
import asyncio
import logging
import threading
from database import (db, islem_kaydet, islem_gecmisi_al, basarim_ver,
                      basarimlari_al, basarim_sayisi, BASARIM_LISTESI, vip_kontrol,
                      sunucu_ayar_al, sunucu_ayar_guncelle, yonetici_kontrol,
                      ekonomi_kaydi_olustur, bakiye_al)
from arayuz import Renkler, premium_embed, progress_bar, sayi_formatla, AYIRICI, AYIRICI_INCE, mini_card, bilgi_kutusu
from yapilandirma import PREFIX

logger = logging.getLogger('MezarBot.Ekonomi')

# EKONOMİ SUNUCU BAZLIDIR: bakiye, XP, seviye, günlük ödül, geçmiş, başarımlar ve envanter
# (sunucu_id, kullanici_id) anahtarlıdır. Bellekteki tüm yapılar da aynı anahtarı kullanır.
EKONOMI_DM_MESAJI = ("💰 Ekonomi komutları sadece sunucularda çalışır: bakiye, XP, seviye ve günlük ödül "
                     "her sunucuda ayrıdır. Komutu bir sunucu kanalında kullan.")

# XP spam koruması: {(sunucu_id, kullanici_id): son XP zamanı}
xp_cooldown = {}
XP_COOLDOWN_SURE = 10  # saniye

# Blackjack aktif oyunlar — aynı sunucuda aynı anda iki oyun açılmasın: {(sunucu_id, kullanici_id)}
aktif_oyuncular = set()

# Kart Mantığı
KARTLAR = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
DEGERLER = {'2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9, '10': 10, 'J': 10, 'Q': 10, 'K': 10, 'A': 11}

# Kriptografik güvenli rastgelelik (kumar oyunları için)
_secure_random = random.SystemRandom()


def _bakiye_rezerve_et(sunucu_id, kullanici_id, miktar):
    """Bahsi BU sunucunun bakiyesinden atomik olarak düşer (emanet/escrow). Bakiye yetmezse hiçbir şey
    değişmez, False döner. Commit çağıran tarafa aittir."""
    c = db.cursor()
    c.execute("UPDATE ekonomi SET bakiye = bakiye - ? WHERE sunucu_id = ? AND kullanici_id = ? AND bakiye >= ?",
              (miktar, sunucu_id, kullanici_id, miktar))
    return c.rowcount > 0


def _bakiye_ekle(sunucu_id, kullanici_id, miktar):
    """BU sunucudaki bakiyeye atomik ekleme (iade / ödeme). Commit çağıran tarafa aittir."""
    c = db.cursor()
    c.execute("UPDATE ekonomi SET bakiye = bakiye + ? WHERE sunucu_id = ? AND kullanici_id = ?",
              (miktar, sunucu_id, kullanici_id))


def _duello_iade(sunucu_id, davet_eden_id, hedef_id, miktar):
    """Düello iptal / zaman aşımı / beraberlik: iki tarafın emanetteki bahsini (aynı sunucuda) iade eder."""
    _bakiye_ekle(sunucu_id, davet_eden_id, miktar)
    _bakiye_ekle(sunucu_id, hedef_id, miktar)
    db.commit()


def _duello_ode(sunucu_id, kazanan_id, miktar):
    """Düello sonucu: iki bahis de kabul anında emanete alındı — kazanana potun tamamı (2x) BU sunucuda ödenir."""
    _bakiye_ekle(sunucu_id, kazanan_id, miktar * 2)
    db.commit()

def el_degeri(el):
    deger = sum(DEGERLER[kart] for kart in el)
    aslar = el.count('A')
    while deger > 21 and aslar:
        deger -= 10
        aslar -= 1
    return deger

class BlackjackView(discord.ui.View):
    def __init__(self, ctx, miktar):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.sunucu_id = ctx.guild.id  # bahis bu sunucunun ekonomisinde emanette
        self.miktar = miktar
        self.desta = KARTLAR * 4
        _secure_random.shuffle(self.desta)
        self.oyuncu_eli = [self.desta.pop(), self.desta.pop()]
        self.kasa_eli = [self.desta.pop(), self.desta.pop()]
        self.oyun_bitti = False

    def embed_olustur(self, gizli=True):
        oyuncu_skor = el_degeri(self.oyuncu_eli)
        kasa_skor = el_degeri(self.kasa_eli)

        embed = discord.Embed(color=Renkler.EKONOMI, timestamp=datetime.datetime.now(datetime.timezone.utc))
        embed.set_author(name="🃏 Blackjack", icon_url=self.ctx.author.display_avatar.url)

        kasa_kartlari = f"`{self.kasa_eli[0]}`  `?`" if gizli else "  ".join(f"`{k}`" for k in self.kasa_eli)
        kasa_skor_str = "?" if gizli else str(kasa_skor)

        embed.description = (
            f"**Bahis:** `{sayi_formatla(self.miktar)}` Coin\n"
            f"{AYIRICI_INCE}\n"
            f"🏠 **Kasa** ─ Skor: `{kasa_skor_str}`\n"
            f"> {kasa_kartlari}\n\n"
            f"👤 **{self.ctx.author.display_name}** ─ Skor: `{oyuncu_skor}`\n"
            f"> {'  '.join(f'`{k}`' for k in self.oyuncu_eli)}"
        )

        if self.oyun_bitti:
            embed.set_footer(text="MezarBot • Oyun sona erdi")
        else:
            embed.set_footer(text="MezarBot • Vur veya Kal")

        return embed

    @discord.ui.button(label="Vur", style=discord.ButtonStyle.green, emoji="➕")
    async def vur(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("❌ Bu senin oyunun değil!", ephemeral=True)

        if not self.desta:
            self.desta = KARTLAR * 4
            _secure_random.shuffle(self.desta)
        self.oyuncu_eli.append(self.desta.pop())
        if el_degeri(self.oyuncu_eli) > 21:
            self.oyun_bitti = True
            await self.final(interaction, "Kasa kazandı! (21'i geçtin)")
        else:
            await interaction.response.edit_message(embed=self.embed_olustur(), view=self)

    @discord.ui.button(label="Kal", style=discord.ButtonStyle.red, emoji="✋")
    async def kal(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("❌ Bu senin oyunun değil!", ephemeral=True)

        self.oyun_bitti = True

        while el_degeri(self.kasa_eli) < 17:
            if not self.desta:
                self.desta = KARTLAR * 4
                _secure_random.shuffle(self.desta)
            self.kasa_eli.append(self.desta.pop())

        oyuncu_skor = el_degeri(self.oyuncu_eli)
        kasa_skor = el_degeri(self.kasa_eli)

        if kasa_skor > 21:
            await self.final(interaction, "Kazandın! (Kasa battı)")
        elif oyuncu_skor > kasa_skor:
            await self.final(interaction, "Kazandın! (Kasa'dan daha yakınsın)")
        elif oyuncu_skor < kasa_skor:
            await self.final(interaction, "Kasa kazandı! (Kasa daha yakın)")
        else:
            await self.final(interaction, "Berabere! (Paran iade edildi)")

    async def final(self, interaction, mesaj):
        # Bahis zaten oyun başında (bu sunucuda) düşüldü: kazanınca +2x, berabere +1x, kaybedince 0
        sid, uid = self.sunucu_id, self.ctx.author.id
        if "Kazandın" in mesaj:
            _bakiye_ekle(sid, uid, self.miktar * 2)
            color = Renkler.BASARI
            islem_kaydet(sid, uid, 'blackjack', self.miktar, 'Blackjack kazancı')
        elif "Berabere" in mesaj:
            _bakiye_ekle(sid, uid, self.miktar)
            color = Renkler.BILGI
            islem_kaydet(sid, uid, 'blackjack', 0, 'Blackjack berabere')
        else:
            color = Renkler.HATA
            islem_kaydet(sid, uid, 'blackjack', -self.miktar, 'Blackjack kaybı')
        db.commit()

        # Güncel bakiyeyi oku
        yeni_bakiye = bakiye_al(sid, uid) or 0

        embed = self.embed_olustur(gizli=False)
        embed.color = color
        embed.set_author(name=f"🃏 Blackjack ─ {mesaj}", icon_url=self.ctx.author.display_avatar.url)
        embed.description += f"\n{AYIRICI_INCE}\n> 💰 **Bakiye:** `{sayi_formatla(yeni_bakiye)}` Coin"

        # Oyuncuyu aktif listesinden çıkar
        aktif_oyuncular.discard((sid, uid))

        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()

    async def on_timeout(self):
        """Zaman aşımında oyuncuyu listeden çıkar (bahis zaten düşüldü)."""
        aktif_oyuncular.discard((self.sunucu_id, self.ctx.author.id))
        if not self.oyun_bitti:
            self.oyun_bitti = True
            yeni_bakiye = bakiye_al(self.sunucu_id, self.ctx.author.id) or 0
            embed = self.embed_olustur(gizli=False)
            embed.color = Renkler.HATA
            embed.set_author(name="🃏 Blackjack ─ Süre Doldu! (Kasa kazandı)", icon_url=self.ctx.author.display_avatar.url)
            embed.description += f"\n{AYIRICI_INCE}\n> 💰 **Bakiye:** `{sayi_formatla(yeni_bakiye)}` Coin"
            try:
                # View'ın bağlı olduğu mesajı bul ve güncelle
                if hasattr(self, 'message') and self.message:
                    await self.message.edit(embed=embed, view=None)
            except (discord.NotFound, discord.HTTPException):
                pass


# Düello Sistemleri
class DuelloDavetView(discord.ui.View):
    def __init__(self, davet_eden, hedef, miktar):
        super().__init__(timeout=60)
        self.davet_eden = davet_eden
        self.hedef = hedef
        self.miktar = miktar
        self.deger = None

    @discord.ui.button(label="Kabul Et", style=discord.ButtonStyle.success, emoji="⚔️")
    async def kabul(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.hedef.id:
            return await interaction.response.send_message("Bu davet senin icin degil!", ephemeral=True)
        await interaction.response.defer()
        self.deger = True
        self.stop()

    @discord.ui.button(label="Reddet", style=discord.ButtonStyle.danger, emoji="🛡️")
    async def reddet(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.hedef.id:
            return await interaction.response.send_message("Bu davet senin icin degil!", ephemeral=True)
        await interaction.response.defer()
        self.deger = False
        self.stop()

class DuelloOyunSecimView(discord.ui.View):
    def __init__(self, davet_eden, hedef, miktar):
        super().__init__(timeout=60)
        self.davet_eden = davet_eden
        self.hedef = hedef
        self.miktar = miktar
        self.secim = None

    @discord.ui.button(label="Zar Atma", style=discord.ButtonStyle.secondary, emoji="🎲")
    async def zar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.davet_eden.id:
            return await interaction.response.send_message("Sadece davet sahibi oyun secebilir!", ephemeral=True)
        await interaction.response.defer()
        self.secim = "zar"
        self.stop()

    @discord.ui.button(label="Taş Kağıt Makas", style=discord.ButtonStyle.secondary, emoji="✂️")
    async def tkm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.davet_eden.id:
            return await interaction.response.send_message("Sadece davet sahibi oyun secebilir!", ephemeral=True)
        await interaction.response.defer()
        self.secim = "tkm"
        self.stop()

class DuelloZarView(discord.ui.View):
    def __init__(self, sunucu_id, davet_eden, hedef, miktar, mesaj_ref=None):
        super().__init__(timeout=60)
        self.sunucu_id = sunucu_id  # iki bahis de bu sunucunun ekonomisinde emanette
        self.davet_eden = davet_eden
        self.hedef = hedef
        self.miktar = miktar
        self.zarlar = {davet_eden.id: None, hedef.id: None}
        self.mesaj_ref = mesaj_ref  # düzenlemek için mesaj referansı
        self.sonuclandi = False

    async def on_timeout(self):
        if self.sonuclandi:
            return
        self.sonuclandi = True
        _duello_iade(self.sunucu_id, self.davet_eden.id, self.hedef.id, self.miktar)
        if self.mesaj_ref:
            embed = premium_embed("⏰ Düello - Süre Doldu!", "Zar atılmadığı için düello iptal edildi. Paralar iade edildi.", renk=Renkler.UYARI)
            try:
                await self.mesaj_ref.edit(embed=embed, view=None)
            except (discord.NotFound, discord.HTTPException):
                pass

    @discord.ui.button(label="Zar At", style=discord.ButtonStyle.primary, emoji="🎲")
    async def zar_at(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in self.zarlar:
            return await interaction.response.send_message("❌ Sen bu düellonun bir parçası değilsin!", ephemeral=True)

        if self.zarlar[interaction.user.id] is not None:
            return await interaction.response.send_message("❌ Zaten zar attın!", ephemeral=True)

        self.zarlar[interaction.user.id] = _secure_random.randint(1, 100)

        if all(z is not None for z in self.zarlar.values()):
            await self.sonuclandir(interaction)
        else:
            await interaction.response.send_message(f"🎲 Zarını attın: **{self.zarlar[interaction.user.id]}**! Diğer oyuncu bekleniyor...", ephemeral=True)
            embed = interaction.message.embeds[0]
            embed.description = f"{AYIRICI}\n🎲 {interaction.user.mention} zarını attı! Diğer oyuncu bekleniyor...\n{AYIRICI}"
            await interaction.message.edit(embed=embed)

    async def sonuclandir(self, interaction):
        self.sonuclandi = True
        p1_val = self.zarlar[self.davet_eden.id]
        p2_val = self.zarlar[self.hedef.id]

        if p1_val > p2_val:
            kazanan, kaybeden = self.davet_eden, self.hedef
        elif p2_val > p1_val:
            kazanan, kaybeden = self.hedef, self.davet_eden
        else:
            self.stop()
            _duello_iade(self.sunucu_id, self.davet_eden.id, self.hedef.id, self.miktar)
            embed = discord.Embed(color=Renkler.BILGI, description=f"### 🤝 Berabere!\nİkiniz de **{p1_val}** attınız! Paralar iade edildi.", timestamp=datetime.datetime.now(datetime.timezone.utc))
            embed.set_author(name="🎲 Düello ─ Zar Atma")
            embed.set_footer(text="MezarBot • Düello")
            return await interaction.response.edit_message(embed=embed, view=None)

        # Bahisler emanette: kazanana pot (2x) atomik olarak ödenir
        _duello_ode(self.sunucu_id, kazanan.id, self.miktar)

        embed = discord.Embed(color=Renkler.BASARI, timestamp=datetime.datetime.now(datetime.timezone.utc))
        embed.set_author(name="⚔️ Düello Sonucu ─ Zar Atma")
        embed.description = (
            f"### 🏆 {kazanan.mention} KAZANDI!\n\n"
            f"{bilgi_kutusu(('🎲', self.davet_eden.name, f'`{p1_val}`'), ('🎲', self.hedef.name, f'`{p2_val}`'), ('💰', 'Ödül', f'`{sayi_formatla(self.miktar * 2)}` Coin'))}"
        )
        embed.set_footer(text="MezarBot • Düello")
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()

class DuelloTKMView(discord.ui.View):
    def __init__(self, sunucu_id, davet_eden, hedef, miktar, mesaj_ref=None):
        super().__init__(timeout=60)
        self.sunucu_id = sunucu_id  # iki bahis de bu sunucunun ekonomisinde emanette
        self.davet_eden = davet_eden
        self.hedef = hedef
        self.miktar = miktar
        self.secimler = {davet_eden.id: None, hedef.id: None}
        self.mesaj_ref = mesaj_ref
        self.sonuclandi = False

    async def on_timeout(self):
        if self.sonuclandi:
            return
        self.sonuclandi = True
        _duello_iade(self.sunucu_id, self.davet_eden.id, self.hedef.id, self.miktar)
        if self.mesaj_ref:
            embed = premium_embed("⏰ Düello - Süre Doldu!", "Seçim yapılmadığı için düello iptal edildi. Paralar iade edildi.", renk=Renkler.UYARI)
            try:
                await self.mesaj_ref.edit(embed=embed, view=None)
            except (discord.NotFound, discord.HTTPException):
                pass

    @discord.ui.button(label="Taş", style=discord.ButtonStyle.secondary, emoji="🪨")
    async def tas(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.hamle(interaction, "taş")

    @discord.ui.button(label="Kağıt", style=discord.ButtonStyle.secondary, emoji="📄")
    async def kagit(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.hamle(interaction, "kağıt")

    @discord.ui.button(label="Makas", style=discord.ButtonStyle.secondary, emoji="✂️")
    async def makas(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.hamle(interaction, "makas")

    async def hamle(self, interaction, secim):
        if interaction.user.id not in self.secimler:
            return await interaction.response.send_message("❌ Sen bu düellonun bir parçası değilsin!", ephemeral=True)
        if self.secimler[interaction.user.id] is not None:
            return await interaction.response.send_message("❌ Zaten seçim yaptın!", ephemeral=True)

        self.secimler[interaction.user.id] = secim

        if all(s is not None for s in self.secimler.values()):
            await self.sonuclandir(interaction)
        else:
            await interaction.response.send_message(f"✅ Seçimin: **{secim.capitalize()}**! Rakip bekleniyor...", ephemeral=True)
            embed = interaction.message.embeds[0]
            embed.description = f"{AYIRICI}\n✂️ {interaction.user.mention} seçimini yaptı! Rakip bekleniyor...\n{AYIRICI}"
            await interaction.message.edit(embed=embed)

    async def sonuclandir(self, interaction):
        self.sonuclandi = True
        p1_s = self.secimler[self.davet_eden.id]
        p2_s = self.secimler[self.hedef.id]

        kazanan = None
        if p1_s == p2_s:
            pass
        elif (p1_s == "taş" and p2_s == "makas") or (p1_s == "kağıt" and p2_s == "taş") or (p1_s == "makas" and p2_s == "kağıt"):
            kazanan = self.davet_eden
        else:
            kazanan = self.hedef

        if kazanan is None:
            self.stop()
            _duello_iade(self.sunucu_id, self.davet_eden.id, self.hedef.id, self.miktar)
            embed = discord.Embed(color=Renkler.BILGI, description=f"### 🤝 Berabere!\nİkiniz de **{p1_s.capitalize()}** seçtiniz! Paralar iade edildi.", timestamp=datetime.datetime.now(datetime.timezone.utc))
            embed.set_author(name="✂️ Düello ─ Taş Kağıt Makas")
            embed.set_footer(text="MezarBot • Düello")
            return await interaction.response.edit_message(embed=embed, view=None)

        # Bahisler emanette: kazanana pot (2x) atomik olarak ödenir
        _duello_ode(self.sunucu_id, kazanan.id, self.miktar)

        embed = discord.Embed(color=Renkler.BASARI, timestamp=datetime.datetime.now(datetime.timezone.utc))
        embed.set_author(name="⚔️ Düello Sonucu ─ Taş Kağıt Makas")
        embed.description = (
            f"### 🏆 {kazanan.mention} KAZANDI!\n\n"
            f"{bilgi_kutusu(('✂️', self.davet_eden.name, f'`{p1_s.capitalize()}`'), ('✂️', self.hedef.name, f'`{p2_s.capitalize()}`'), ('💰', 'Ödül', f'`{sayi_formatla(self.miktar * 2)}` Coin'))}"
        )
        embed.set_footer(text="MezarBot • Düello")
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()


class Ekonomi(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Batch XP sistemi: bellekte biriktir, periyodik olarak DB'ye yaz
        self._xp_buffer = {}  # {(sunucu_id, kullanici_id): {'xp': int, 'seviye': int, 'yeni': bool}}
        self._xp_lock = threading.Lock()  # XP buffer thread safety
        self._xp_flush.start()
        self.xp_temizle.start()

    async def cog_check(self, ctx):
        """Ekonomi sunucu bazlıdır: DM'de hiçbir ekonomi komutu çalışmaz (hangi sunucunun bakiyesi?).
        Mesajı main.on_command_error (NoPrivateMessage) gösterir."""
        if ctx.guild is None:
            raise commands.NoPrivateMessage(EKONOMI_DM_MESAJI)
        return True

    def cog_unload(self):
        self._xp_flush.cancel()
        self.xp_temizle.cancel()
        # Son kalan XP'leri yaz
        self._flush_xp_to_db()

    @tasks.loop(minutes=30)
    async def xp_temizle(self):
        """Eski XP cooldown verilerini temizler — bellek sızıntısını önler."""
        su_an = time.time()
        temizlenecek = [anahtar for anahtar, t in xp_cooldown.items() if su_an - t > 300]
        for anahtar in temizlenecek:
            del xp_cooldown[anahtar]

    @tasks.loop(seconds=30)
    async def _xp_flush(self):
        """Biriken XP güncellemelerini toplu olarak DB'ye yazar."""
        self._flush_xp_to_db()

    def _flush_xp_to_db(self):
        """XP buffer'ını DB'ye yazar. bakiye asla üzerine yazılmaz (diğer komutlar atomik günceller)."""
        with self._xp_lock:
            if not self._xp_buffer:
                return
            c = db.cursor()
            for (sunucu_id, kullanici_id), veri in self._xp_buffer.items():
                if veri.get('yeni'):
                    ekonomi_kaydi_olustur(sunucu_id, kullanici_id, xp=veri['xp'], seviye=veri['seviye'])
                c.execute(
                    "UPDATE ekonomi SET xp = ?, seviye = ? WHERE sunucu_id = ? AND kullanici_id = ?",
                    (veri['xp'], veri['seviye'], sunucu_id, kullanici_id))
            db.commit()
            self._xp_buffer.clear()

    def _siralama_getir(self, sunucu_id, kullanici_id):
        """Kullanıcının BU sunucudaki zenginlik sırasını SQL ile verimli şekilde döner."""
        c = db.cursor()
        c.execute(
            "SELECT COUNT(*) + 1 FROM ekonomi WHERE sunucu_id = ? AND bakiye > "
            "(SELECT COALESCE(bakiye, 0) FROM ekonomi WHERE sunucu_id = ? AND kullanici_id = ?)",
            (sunucu_id, sunucu_id, kullanici_id))
        sonuc = c.fetchone()
        return f"`#{sonuc[0]}`" if sonuc else "`—`"

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild or not message.content or message.content.startswith(PREFIX):
            return
        # XP/seviye sistemi sunucu başına opt-in (!xpayarla ac). Kapalı sunucularda ve DM'de XP verilmez.
        # (Ör. seviye sistemini başka bir botun yönettiği sunucularda kapalı bırakılır.) Cache'den okunur.
        ayar = sunucu_ayar_al(message.guild.id)
        if not (ayar and ayar.get('xp_aktif')):
            return

        sunucu_id = message.guild.id
        kullanici_id = message.author.id
        anahtar = (sunucu_id, kullanici_id)  # XP / seviye sunucu bazlı
        su_an = time.time()

        # XP spam koruması (sunucu başına)
        son_xp = xp_cooldown.get(anahtar, 0)
        if su_an - son_xp < XP_COOLDOWN_SURE:
            return
        xp_cooldown[anahtar] = su_an

        kazanilan_xp = random.randint(5, 15)

        # Buffer'da varsa oradan oku (sadece xp/seviye), yoksa DB'den oku
        with self._xp_lock:
            yeni = False
            if anahtar in self._xp_buffer:
                veri = self._xp_buffer[anahtar]
                xp, seviye = veri['xp'], veri['seviye']
                # DB'de henüz satırı olmayan kullanıcı: flush'ta INSERT yapılsın diye bayrak korunur
                yeni = veri.get('yeni', False)
            else:
                c = db.cursor()
                c.execute("SELECT xp, seviye FROM ekonomi WHERE sunucu_id = ? AND kullanici_id = ?",
                          (sunucu_id, kullanici_id))
                kayit = c.fetchone()
                if kayit:
                    xp, seviye = kayit[0] or 0, kayit[1] or 1
                else:
                    # Bu sunucuda yeni kullanıcı
                    self._xp_buffer[anahtar] = {
                        'xp': kazanilan_xp, 'seviye': 1, 'yeni': True
                    }
                    return

        yeni_xp = xp + kazanilan_xp
        gerekli_xp = seviye * 100

        if yeni_xp >= gerekli_xp:
            seviye += 1
            yeni_xp = 0
            # Seviye atlama bonusu — atomik DB güncelleme (buffer'a bakiye yazmıyoruz), bu sunucunun bakiyesine
            if yeni:
                # Satır henüz flush edilmediyse bonus kaybolmasın: önce satırı oluştur
                ekonomi_kaydi_olustur(sunucu_id, kullanici_id)
            _bakiye_ekle(sunucu_id, kullanici_id, 50)
            db.commit()
            islem_kaydet(sunucu_id, kullanici_id, 'seviye_bonus', 50, f'Seviye {seviye} bonusu')
            try:
                embed = discord.Embed(color=Renkler.EKONOMI, timestamp=datetime.datetime.now(datetime.timezone.utc))
                embed.set_author(name="⬆️ SEVİYE ATLADI!", icon_url=message.author.display_avatar.url)
                embed.description = (
                    f"🎉 {message.author.mention} **Seviye {seviye}**'e ulaştı!\n\n"
                    f"{bilgi_kutusu(('🏆', 'Seviye', f'`{seviye}`'), ('💰', 'Bonus', '`+50` Coin'))}"
                )
                embed.set_footer(text="MezarBot • Ekonomi")
                await message.channel.send(embed=embed, delete_after=10)
            except Exception as e:
                logger.warning(f"Seviye atlama bildirimi gönderilemedi (kullanıcı={kullanici_id}): {e}")

            # Başarım kontrolleri
            if seviye >= 10:
                if basarim_ver(sunucu_id, kullanici_id, 'seviye_10'):
                    await self._basarim_bildir(message.channel, message.author, 'seviye_10')
            if seviye >= 25:
                if basarim_ver(sunucu_id, kullanici_id, 'seviye_25'):
                    await self._basarim_bildir(message.channel, message.author, 'seviye_25')

        with self._xp_lock:
            self._xp_buffer[anahtar] = {
                'xp': yeni_xp, 'seviye': seviye, 'yeni': yeni
            }

    @commands.hybrid_command(description="Profil kartı: seviye, XP ve bakiye")
    async def profil(self, ctx, uye: discord.Member = None):
        """Bu sunucudaki profil bilgilerini gösterir. Kullanım: !profil veya !profil @kişi"""
        hedef = uye or ctx.author
        sunucu_id = ctx.guild.id
        # Önce buffer'ı flush et
        self._flush_xp_to_db()
        c = db.cursor()
        c.execute("SELECT xp, seviye, bakiye, streak FROM ekonomi WHERE sunucu_id = ? AND kullanici_id = ?",
                  (sunucu_id, hedef.id))
        kayit = c.fetchone()
        if kayit:
            xp, seviye, bakiye = kayit[0] or 0, kayit[1] or 1, kayit[2] or 0
            streak = kayit[3] or 0
            gerekli_xp = seviye * 100
            bar = progress_bar(xp, gerekli_xp, 12)

            yuzde = int((xp/gerekli_xp)*100) if gerekli_xp > 0 else 0
            basarim_count = basarim_sayisi(sunucu_id, hedef.id)

            embed = discord.Embed(color=Renkler.BILGI, timestamp=datetime.datetime.now(datetime.timezone.utc))
            embed.set_author(name=f"{hedef.display_name}", icon_url=hedef.display_avatar.url)
            embed.set_thumbnail(url=hedef.display_avatar.url)
            embed.description = f"{AYIRICI}\n✨ `{bar}` **{yuzde}%** ─ `{xp}/{gerekli_xp}` XP\n{AYIRICI}"

            embed.add_field(name="", value=mini_card("Seviye", f"`{seviye}`", "🏆"), inline=True)
            embed.add_field(name="", value=mini_card("Bakiye", f"`{sayi_formatla(bakiye)}` Coin", "💰"), inline=True)
            embed.add_field(name="", value=mini_card("Sıralama", self._siralama_getir(sunucu_id, hedef.id), "📊"), inline=True)

            # Streak ve Başarımlar
            if streak > 0 or basarim_count > 0:
                extra = []
                if streak > 0:
                    extra.append(f"🔥 **Streak:** `{streak}` gün")
                if basarim_count > 0:
                    extra.append(f"🏅 **Başarımlar:** `{basarim_count}/{len(BASARIM_LISTESI)}`")
                embed.add_field(name="", value=" ∙ ".join(extra), inline=False)

            # Rozetleri göster
            c.execute("""SELECT d.emoji, d.isim FROM envanter e
                         JOIN dukkan_urunler d ON e.urun_id = d.id
                         WHERE e.sunucu_id = ? AND e.kullanici_id = ? AND d.tip = 'rozet'
                         ORDER BY d.fiyat DESC""", (sunucu_id, hedef.id))
            rozetler = c.fetchall()
            if rozetler:
                rozet_str = " ".join(f"{r[0]}" for r in rozetler)
                embed.add_field(name=f"🏅 Rozetler ({len(rozetler)})", value=rozet_str, inline=False)

            embed.set_footer(text=f"MezarBot • Profil • {ctx.guild.name}")
            await ctx.send(embed=embed)
        else:
            await ctx.send("❌ Bu kullanıcının bu sunucuda profili yok!", delete_after=5)

    @commands.hybrid_command(description="Bakiyeni göster")
    async def bakiye(self, ctx, uye: discord.Member = None):
        """Bu sunucudaki bakiyeyi gösterir. Kullanım: !bakiye veya !bakiye @kişi"""
        hedef = uye or ctx.author
        self._flush_xp_to_db()
        miktar = bakiye_al(ctx.guild.id, hedef.id)
        if miktar is not None:
            embed = discord.Embed(
                description=f"💰 ┃ **{hedef.display_name}** ── `{sayi_formatla(miktar)}` Coin",
                color=Renkler.EKONOMI
            )
            await ctx.send(embed=embed)
        else:
            await ctx.send("❌ Bu sunucuda profil bulunamadı!", delete_after=5)

    @commands.hybrid_command(description="Günlük ödülünü al")
    async def gunluk(self, ctx):
        """Bu sunucudaki günlük maaşını al. Ardışık giriş = artan bonus! (günde bir, her sunucuda ayrı)"""
        bugun = datetime.date.today().isoformat()
        dun = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
        sunucu_id = ctx.guild.id
        kullanici_id = ctx.author.id
        c = db.cursor()
        c.execute("SELECT bakiye, son_gunluk, streak, son_gunluk_tarih FROM ekonomi WHERE sunucu_id = ? AND kullanici_id = ?",
                  (sunucu_id, kullanici_id))
        kayit = c.fetchone()
        if kayit:
            son_gunluk = kayit[1] or ''
            eski_streak = kayit[2] or 0
            son_tarih = kayit[3] or ''

            if son_gunluk == bugun:
                return await ctx.send("❌ Bugünkü maaşını zaten almışsın! Yarın tekrar gel.", delete_after=7)

            # Streak hesapla
            if son_tarih == dun:
                yeni_streak = eski_streak + 1
            else:
                yeni_streak = 1

            # Bonus hesapla: 100 + (streak * 10), max 500
            bonus = min(100 + (yeni_streak * 10), 500)

            c.execute("UPDATE ekonomi SET bakiye = bakiye + ?, son_gunluk = ?, streak = ?, son_gunluk_tarih = ? "
                      "WHERE sunucu_id = ? AND kullanici_id = ? AND COALESCE(son_gunluk, '') != ?",
                      (bonus, bugun, yeni_streak, bugun, sunucu_id, kullanici_id, bugun))
            if c.rowcount == 0:
                return await ctx.send("❌ Bugünkü maaşını zaten almışsın! Yarın tekrar gel.", delete_after=7)
            db.commit()
            islem_kaydet(sunucu_id, kullanici_id, 'gunluk', bonus, f'Günlük maaş (streak {yeni_streak})')

            yeni_bakiye = bakiye_al(sunucu_id, kullanici_id) or 0

            embed = discord.Embed(color=Renkler.BASARI, timestamp=datetime.datetime.now(datetime.timezone.utc))
            embed.set_author(name="💰 Günlük Maaş", icon_url=ctx.author.display_avatar.url)

            streak_str = f"🔥 **{yeni_streak} gün** üst üste!" if yeni_streak > 1 else ""
            embed.description = (
                f"**+{sayi_formatla(bonus)} Coin** hesabına eklendi!\n"
                f"{streak_str}\n\n"
                f"{bilgi_kutusu(('💰', 'Bakiye', f'`{sayi_formatla(yeni_bakiye)}` Coin'), ('🔥', 'Streak', f'`{yeni_streak}` gün'), ('⏰', 'Sonraki', '**Yarın**'))}"
            )
            embed.set_footer(text="MezarBot • Ekonomi")
            await ctx.send(embed=embed, delete_after=15)

            # Başarım kontrolleri
            if yeni_streak >= 5:
                if basarim_ver(sunucu_id, kullanici_id, 'streak_5'):
                    await self._basarim_bildir(ctx.channel, ctx.author, 'streak_5')
            if yeni_streak >= 30:
                if basarim_ver(sunucu_id, kullanici_id, 'streak_30'):
                    await self._basarim_bildir(ctx.channel, ctx.author, 'streak_30')
        else:
            # OR IGNORE: aynı anda iki !gunluk gelirse ikincisi satırı ikinci kez oluşturamaz / para basamaz
            c.execute(
                "INSERT OR IGNORE INTO ekonomi (sunucu_id, kullanici_id, xp, seviye, bakiye, son_gunluk, streak, son_gunluk_tarih) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (sunucu_id, kullanici_id, 0, 1, 100, bugun, 1, bugun))
            if c.rowcount == 0:
                return await ctx.send("❌ Bugünkü maaşını zaten almışsın! Yarın tekrar gel.", delete_after=7)
            db.commit()
            islem_kaydet(sunucu_id, kullanici_id, 'gunluk', 100, 'İlk günlük maaş')
            await ctx.send("✅ Bu sunucudaki profilin oluşturuldu ve ilk maaşın verildi! 💰 100 Coin", delete_after=10)

    @commands.hybrid_command(description="Yazı tura at (yazı/tura + miktar)")
    async def yazitura(self, ctx, secim: str, miktar: int):
        """Yazı tura oyna. Kullanım: !yazitura yazı 100"""
        secim = secim.lower()
        if secim not in ["yazı", "yazi", "tura"]:
            return await ctx.send("❌ Geçerli bir seçim yap: `yazı` veya `tura`", delete_after=5)

        if miktar < 10:
            return await ctx.send("❌ Minimum bahis **10 Coin**!", delete_after=5)

        sunucu_id, kullanici_id = ctx.guild.id, ctx.author.id
        mevcut = bakiye_al(sunucu_id, kullanici_id)
        if mevcut is None:
            return await ctx.send("❌ Bu sunucuda profilin yok! Önce `!gunluk` kullan.", delete_after=7)
        if mevcut < miktar:
            return await ctx.send(f"❌ Paran yetersiz! Bakiyen: **{sayi_formatla(mevcut)} Coin**", delete_after=7)

        tahmin = "yazı" if secim in ["yazı", "yazi"] else "tura"
        bilgisayar_secimi = _secure_random.choice(["yazı", "tura"])

        kazandin = (tahmin == bilgisayar_secimi)

        # Kumar limit kontrolü
        if await self._kumar_limit_kontrol(ctx, miktar):
            return

        # Atomik: bahis önce koşullu düşülür (bakiye bu arada azaldıysa işlem yapılmaz),
        # kazanınca pot (2x) eklenir. Net sonuç eskisiyle aynı (+miktar / -miktar), yarış durumu yok.
        if not _bakiye_rezerve_et(sunucu_id, kullanici_id, miktar):
            return await ctx.send("❌ Yeterli bakiyen yok!", delete_after=5)
        if kazandin:
            _bakiye_ekle(sunucu_id, kullanici_id, miktar * 2)
            islem_kaydet(sunucu_id, kullanici_id, 'yazitura', miktar, 'Yazı tura kazancı')
            self._kumar_kazanma_kaydet(sunucu_id, kullanici_id)
        else:
            islem_kaydet(sunucu_id, kullanici_id, 'yazitura', -miktar, 'Yazı tura kaybı')
            self._kumar_kayip_kaydet(sunucu_id, kullanici_id, miktar)
        db.commit()

        # Başarım: İlk kumar
        if basarim_ver(sunucu_id, kullanici_id, 'ilk_kumar'):
            await self._basarim_bildir(ctx.channel, ctx.author, 'ilk_kumar')
        # Başarım: Büyük kazanç
        if kazandin and miktar >= 5000:
            if basarim_ver(sunucu_id, kullanici_id, 'buyuk_kazanc'):
                await self._basarim_bildir(ctx.channel, ctx.author, 'buyuk_kazanc')

        # Güncel bakiyeyi oku
        yeni_bakiye = bakiye_al(sunucu_id, kullanici_id) or 0

        # Başarım: Zengin
        if yeni_bakiye >= 10000:
            if basarim_ver(sunucu_id, kullanici_id, 'zengin'):
                await self._basarim_bildir(ctx.channel, ctx.author, 'zengin')

        renk = Renkler.BASARI if kazandin else Renkler.HATA
        baslik = "KAZANDIN! 🎉" if kazandin else "KAYBETTİN 💀"
        isaret = "+" if kazandin else "-"

        embed = discord.Embed(color=renk, timestamp=datetime.datetime.now(datetime.timezone.utc))
        embed.set_author(name="🪙 Yazı Tura", icon_url=ctx.author.display_avatar.url)
        embed.description = (
            f"### {baslik}\n"
            f"Sonuç: **{bilgisayar_secimi.upper()}** geldi!\n\n"
            f"{bilgi_kutusu(('🎯', 'Tahmin', f'**{tahmin.capitalize()}**'), ('💵', 'Bahis', f'`{isaret}{sayi_formatla(miktar)}` Coin'), ('💰', 'Bakiye', f'`{sayi_formatla(yeni_bakiye)}` Coin'))}"
        )
        embed.set_footer(text="MezarBot • Kumar")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="paraekle", description="[Bot Sahibi] Kendi bakiyene coin ekler")
    @app_commands.describe(miktar="Eklenecek coin miktarı")
    @commands.guild_only()
    @commands.is_owner()
    async def paraekle(self, ctx, miktar: int):
        """[OWNER ONLY] Bu sunucudaki kendi bakiyene para ekler."""
        if miktar <= 0:
            return await ctx.send("❌ Miktar pozitif olmalı!", ephemeral=True)
        sunucu_id, kullanici_id = ctx.guild.id, ctx.author.id
        # Satır yoksa oluştur, sonra atomik ekle (sadece bu sunucunun ekonomisi)
        ekonomi_kaydi_olustur(sunucu_id, kullanici_id)
        _bakiye_ekle(sunucu_id, kullanici_id, miktar)
        db.commit()
        islem_kaydet(sunucu_id, kullanici_id, 'paraekle', miktar, 'Sahip: para ekleme')

        yeni_bakiye = bakiye_al(sunucu_id, kullanici_id) or 0
        await ctx.send(f"✅ Bu sunucudaki hesabına **{sayi_formatla(miktar)}** Coin eklendi! Yeni bakiye: **{sayi_formatla(yeni_bakiye)}**")

    @commands.hybrid_command(description="Bu sunucunun zenginlik sıralaması")
    async def siralama(self, ctx):
        """Bu sunucunun en zengin 10 kullanıcısını gösterir."""
        # Önce buffer'ı flush et
        self._flush_xp_to_db()
        c = db.cursor()
        c.execute("SELECT kullanici_id, bakiye, seviye FROM ekonomi WHERE sunucu_id = ? ORDER BY bakiye DESC LIMIT 10",
                  (ctx.guild.id,))
        kayitlar = c.fetchall()
        if not kayitlar:
            return await ctx.send("❌ Bu sunucuda henüz kayıtlı kullanıcı yok.", delete_after=5)
        c.execute("SELECT COUNT(*) FROM ekonomi WHERE sunucu_id = ?", (ctx.guild.id,))
        toplam_oyuncu = c.fetchone()[0]

        madalyalar = ["🥇", "🥈", "🥉"]

        # Önce sunucu üyesi (sunucudaki görünen ad), sonra kullanıcı cache'i, en son API
        async def kullanici_bilgi_al(kayit):
            uye = ctx.guild.get_member(kayit[0])
            if uye:
                return uye.display_name
            kullanici = self.bot.get_user(kayit[0])
            if kullanici:
                return kullanici.display_name
            try:
                kullanici = await self.bot.fetch_user(kayit[0])
                return kullanici.display_name
            except Exception:
                return f"Bilinmeyen ({kayit[0]})"

        isimler = await asyncio.gather(*[kullanici_bilgi_al(k) for k in kayitlar])

        satirlar = []
        for i, (kayit, isim) in enumerate(zip(kayitlar, isimler)):
            medal = madalyalar[i] if i < 3 else f"`#{i+1}`"
            satirlar.append(f"{medal} **{isim}**\n> 💰 `{sayi_formatla(kayit[1])}` Coin ─ Sv. `{kayit[2]}`")

        embed = discord.Embed(color=Renkler.EKONOMI, timestamp=datetime.datetime.now(datetime.timezone.utc))
        embed.set_author(name=f"🏆 Zenginlik Sıralaması ─ {ctx.guild.name}")
        embed.description = f"{AYIRICI}\n" + "\n".join(satirlar) + f"\n{AYIRICI}"
        embed.set_footer(text=f"MezarBot • Bu sunucuda toplam {toplam_oyuncu} oyuncu")
        await ctx.send(embed=embed)

    @commands.hybrid_command(description="Başka bir üyeye para gönder")
    async def transfer(self, ctx, alici: discord.Member, miktar: int):
        """Başka bir kullanıcıya para gönder. Kullanım: !transfer @kişi 100"""
        if alici.bot:
            return await ctx.send("❌ Botlara para gönderemezsin!", delete_after=5)
        if alici.id == ctx.author.id:
            return await ctx.send("❌ Kendine para gönderemezsin!", delete_after=5)
        if miktar <= 0:
            return await ctx.send("❌ Geçerli bir miktar gir.", delete_after=5)

        # Transfer sadece BU sunucunun ekonomisinde: gönderenin bu sunucudaki bakiyesinden alıcının
        # bu sunucudaki bakiyesine (alıcı discord.Member dönüştürücüsüyle bu sunucunun üyesidir)
        sunucu_id = ctx.guild.id
        gonderen = bakiye_al(sunucu_id, ctx.author.id)
        if gonderen is None or gonderen < miktar:
            return await ctx.send("❌ Yeterli bakiyen yok!", delete_after=5)

        if bakiye_al(sunucu_id, alici.id) is None:
            return await ctx.send("❌ Alıcının bu sunucuda profili yok!", delete_after=5)

        # Atomik transfer — bakiye negatife düşmesin
        c = db.cursor()
        c.execute("UPDATE ekonomi SET bakiye = bakiye - ?, transfer_sayisi = COALESCE(transfer_sayisi, 0) + 1 "
                  "WHERE sunucu_id = ? AND kullanici_id = ? AND bakiye >= ?",
                  (miktar, sunucu_id, ctx.author.id, miktar))
        if c.rowcount == 0:
            return await ctx.send("❌ Yeterli bakiyen yok!", delete_after=5)
        _bakiye_ekle(sunucu_id, alici.id, miktar)
        db.commit()

        islem_kaydet(sunucu_id, ctx.author.id, 'transfer', -miktar, f'{alici.display_name} kişisine transfer')
        islem_kaydet(sunucu_id, alici.id, 'transfer', miktar, f'{ctx.author.display_name} kişisinden transfer')

        # Başarım: Sosyal (10+ farklı kişiye transfer)
        c.execute("SELECT transfer_sayisi FROM ekonomi WHERE sunucu_id = ? AND kullanici_id = ?", (sunucu_id, ctx.author.id))
        ts = c.fetchone()
        if ts and (ts[0] or 0) >= 10:
            if basarim_ver(sunucu_id, ctx.author.id, 'sosyal'):
                await self._basarim_bildir(ctx.channel, ctx.author, 'sosyal')

        embed = discord.Embed(color=Renkler.BASARI, timestamp=datetime.datetime.now(datetime.timezone.utc))
        embed.set_author(name="💸 Transfer Başarılı", icon_url=ctx.author.display_avatar.url)
        embed.description = (
            f"{bilgi_kutusu(('📤', 'Gönderen', ctx.author.mention), ('📥', 'Alan', alici.mention), ('💰', 'Miktar', f'`{sayi_formatla(miktar)}` Coin'))}"
        )
        embed.set_footer(text="MezarBot • Ekonomi")
        await ctx.send(embed=embed)

    @commands.hybrid_command(description="Bahisli blackjack oyna")
    async def blackjack(self, ctx, miktar: int):
        """Blackjack oyna. Kullanım: !blackjack 100"""
        if miktar < 10:
            return await ctx.send("❌ Minimum bahis **10 Coin**!", delete_after=5)

        sunucu_id, kullanici_id = ctx.guild.id, ctx.author.id
        anahtar = (sunucu_id, kullanici_id)
        # Aynı sunucuda aynı anda birden fazla oyun açmasını engelle
        if anahtar in aktif_oyuncular:
            return await ctx.send("❌ Zaten aktif bir oyunun var! Önce onu bitir.", delete_after=5)

        bakiye = bakiye_al(sunucu_id, kullanici_id)
        if bakiye is None:
            return await ctx.send("❌ Bu sunucuda profilin yok! Önce `!gunluk` kullan.", delete_after=7)
        if bakiye < miktar:
            return await ctx.send(f"❌ Paran yetersiz! Bakiyen: **{sayi_formatla(bakiye)} Coin**", delete_after=7)

        # Bahsi oyun başında bu sunucunun bakiyesinden düş (atomik emanet)
        if not _bakiye_rezerve_et(sunucu_id, kullanici_id, miktar):
            return await ctx.send("❌ Yeterli bakiyen yok!", delete_after=5)
        db.commit()

        aktif_oyuncular.add(anahtar)
        try:
            view = BlackjackView(ctx, miktar)
            embed = view.embed_olustur()
            view.message = await ctx.send(embed=embed, view=view)
        except Exception:
            aktif_oyuncular.discard(anahtar)
            # Bahsi iade et
            _bakiye_ekle(sunucu_id, kullanici_id, miktar)
            db.commit()
            raise

    @commands.hybrid_command(description="Bir üyeyi bahisli düelloya davet et")
    async def duello(self, ctx, hedef: discord.Member, miktar: int):
        """Bir üyeye düello teklif eder. Kullanım: !duello @kişi 100"""
        if hedef.bot or hedef.id == ctx.author.id:
            return await ctx.send("❌ Kendine veya botlara düello teklif edemezsin!", delete_after=5)

        if miktar < 10:
            return await ctx.send("❌ Minimum bahis **10 Coin**!", delete_after=5)

        # Düello tamamen BU sunucunun ekonomisinde: iki bakiye ve emanet aynı sunucu_id ile
        sunucu_id = ctx.guild.id
        p1_bakiye = bakiye_al(sunucu_id, ctx.author.id) or 0
        p2_bakiye = bakiye_al(sunucu_id, hedef.id) or 0

        if p1_bakiye < miktar:
            return await ctx.send(f"❌ Paran yetersiz! Bakiyen: **{sayi_formatla(p1_bakiye)} Coin**")
        if p2_bakiye < miktar:
            return await ctx.send(f"❌ Rakibinin parası yetersiz! Bakiyesi: **{sayi_formatla(p2_bakiye)} Coin**")

        davet_view = DuelloDavetView(ctx.author, hedef, miktar)
        embed = discord.Embed(color=Renkler.BILGI, timestamp=datetime.datetime.now(datetime.timezone.utc))
        embed.set_author(name="⚔️ Düello Daveti", icon_url=ctx.author.display_avatar.url)
        embed.description = (
            f"{ctx.author.mention} ─ {hedef.mention}\n\n"
            f"{bilgi_kutusu(('💰', 'Bahis', f'`{sayi_formatla(miktar)}` Coin'))}\n\n"
            f"Rakip, düelloyu kabul ediyor musun?"
        )
        embed.set_footer(text="MezarBot • 60 saniye süreniz var")
        msg = await ctx.send(content=hedef.mention, embed=embed, view=davet_view)

        await davet_view.wait()

        if davet_view.deger is None:
            await msg.edit(content="❌ Süre doldu, davet zaman aşımına uğradı.", view=None)
        elif davet_view.deger is False:
            await msg.edit(content=f"❌ {hedef.mention} düello teklifini reddetti.", view=None)
        else:
            # Emanet (escrow): kabul anında iki tarafın bahsi de atomik olarak düşülür.
            # Böylece oyun sırasında bakiyeyi transfer ile boşaltıp "yoktan para" kazanma açığı kapanır.
            if not _bakiye_rezerve_et(sunucu_id, ctx.author.id, miktar):
                return await msg.edit(content=f"❌ {ctx.author.mention} bakiyesi artık yetersiz, düello iptal edildi.", view=None)
            if not _bakiye_rezerve_et(sunucu_id, hedef.id, miktar):
                _bakiye_ekle(sunucu_id, ctx.author.id, miktar)
                db.commit()
                return await msg.edit(content=f"❌ {hedef.mention} bakiyesi artık yetersiz, düello iptal edildi.", view=None)
            db.commit()

            # Oyun view'ı gönderilene kadar iade sorumluluğu bu komutta; sonrasında view'da (sonuç/zaman aşımı)
            oyun_basladi = False
            try:
                secim_view = DuelloOyunSecimView(ctx.author, hedef, miktar)
                embed = discord.Embed(color=Renkler.BILGI, timestamp=datetime.datetime.now(datetime.timezone.utc))
                embed.set_author(name="🎮 Oyun Seçimi")
                embed.description = f"✅ {hedef.mention} kabul etti!\n\n{ctx.author.mention}, oynamak istediğin oyunu seç:"
                embed.set_footer(text="MezarBot • Düello")
                await msg.edit(content=ctx.author.mention, embed=embed, view=secim_view)

                await secim_view.wait()

                if secim_view.secim == "zar":
                    zar_view = DuelloZarView(sunucu_id, ctx.author, hedef, miktar, mesaj_ref=msg)
                    embed = discord.Embed(color=Renkler.BILGI, timestamp=datetime.datetime.now(datetime.timezone.utc))
                    embed.set_author(name="🎲 Düello ─ Zar Atma")
                    embed.description = f"**Bahis:** `{sayi_formatla(miktar)}` Coin\n\nİki taraf da butonla zar atsın, yüksek gelen kazanır!"
                    embed.set_footer(text="MezarBot • Düello")
                    await msg.edit(content=None, embed=embed, view=zar_view)
                    oyun_basladi = True
                elif secim_view.secim == "tkm":
                    tkm_view = DuelloTKMView(sunucu_id, ctx.author, hedef, miktar, mesaj_ref=msg)
                    embed = discord.Embed(color=Renkler.BILGI, timestamp=datetime.datetime.now(datetime.timezone.utc))
                    embed.set_author(name="✂️ Düello ─ Taş Kağıt Makas")
                    embed.description = f"**Bahis:** `{sayi_formatla(miktar)}` Coin\n\nGizli seçimlerinizi yapın!"
                    embed.set_footer(text="MezarBot • Düello")
                    await msg.edit(content=None, embed=embed, view=tkm_view)
                    oyun_basladi = True
                else:
                    await msg.edit(content="❌ Oyun seçimi yapılmadığı için düello iptal edildi. Paralar iade edildi.", view=None)
            finally:
                if not oyun_basladi:
                    _duello_iade(sunucu_id, ctx.author.id, hedef.id, miktar)


    @commands.hybrid_command(description="Bu sunucuda XP sistemini aç/kapat")
    @app_commands.default_permissions(manage_guild=True)
    @commands.guild_only()
    @commands.check(yonetici_kontrol)
    async def xpayarla(self, ctx, durum: str = None):
        """[Yönetici] Bu sunucuda mesajlardan XP/seviye kazanımını açar/kapatır. Kullanım: !xpayarla ac | !xpayarla kapat"""
        ayar = sunucu_ayar_al(ctx.guild.id) or {}
        mevcut = bool(ayar.get('xp_aktif'))
        if durum is None:
            yeni = not mevcut
        else:
            yeni = durum.lower() in ('aç', 'ac', 'on', 'aktif', 'evet', 'true', '1', 'open')
        sunucu_ayar_guncelle(ctx.guild.id, xp_aktif=1 if yeni else 0)
        if yeni:
            await ctx.send(embed=premium_embed("⬆️ XP Sistemi: AÇIK", "Üyeler mesaj attıkça XP kazanır, seviye atlayınca **50 Coin** bonus alır.", renk=Renkler.BASARI))
        else:
            await ctx.send(embed=premium_embed("⏸️ XP Sistemi: KAPALI", "Bu sunucuda mesajlardan XP verilmez. Diğer ekonomi komutları çalışmaya devam eder.", renk=Renkler.NOTR))

    # ── Başarım Sistemi ─────────────────────────────

    async def _basarim_bildir(self, kanal, uye, basarim_id):
        """Başarım kazanıldığında bildirim gönderir."""
        bilgi = BASARIM_LISTESI.get(basarim_id)
        if not bilgi:
            return
        try:
            embed = discord.Embed(color=0xFFD700, timestamp=datetime.datetime.now(datetime.timezone.utc))
            embed.set_author(name="🏅 Başarım Kazanıldı!", icon_url=uye.display_avatar.url)
            embed.description = (
                f"{bilgi['emoji']} **{bilgi['isim']}**\n"
                f"> {bilgi['aciklama']}\n\n"
                f"Tebrikler {uye.mention}!"
            )
            embed.set_footer(text="MezarBot • Başarımlar")
            await kanal.send(embed=embed, delete_after=15)
        except Exception as e:
            logger.warning(f"Başarım bildirimi gönderilemedi: {e}")

    async def _kumar_limit_kontrol(self, ctx, miktar):
        """Kumar limiti kontrolü (günlük kayıp sayacı sunucu bazlı). Aşılmışsa mesaj gönderir ve True döner."""
        bugun = datetime.date.today().isoformat()
        sunucu_id, kullanici_id = ctx.guild.id, ctx.author.id
        c = db.cursor()
        c.execute("SELECT gunluk_kayip, gunluk_kayip_tarih FROM ekonomi WHERE sunucu_id = ? AND kullanici_id = ?",
                  (sunucu_id, kullanici_id))
        kayit = c.fetchone()
        if not kayit:
            return False

        gunluk_kayip = kayit[0] or 0
        kayip_tarih = kayit[1] or ''

        # Gün değiştiyse sıfırla
        if kayip_tarih != bugun:
            c.execute("UPDATE ekonomi SET gunluk_kayip = 0, gunluk_kayip_tarih = ? WHERE sunucu_id = ? AND kullanici_id = ?",
                      (bugun, sunucu_id, kullanici_id))
            db.commit()
            gunluk_kayip = 0

        is_vip = vip_kontrol(ctx.author)
        limit = 15000 if is_vip else 5000

        if gunluk_kayip + miktar > limit:
            kalan = max(0, limit - gunluk_kayip)
            await ctx.send(
                f"❌ Günlük kumar kayıp limitine ulaştın! "
                f"(Limit: **{sayi_formatla(limit)}** Coin, Kalan: **{sayi_formatla(kalan)}** Coin)",
                delete_after=7)
            return True
        return False

    def _kumar_kayip_kaydet(self, sunucu_id, kullanici_id, miktar):
        """Kumar kaybını (bu sunucudaki) günlük sayaca ekler."""
        bugun = datetime.date.today().isoformat()
        c = db.cursor()
        c.execute("UPDATE ekonomi SET gunluk_kayip = COALESCE(gunluk_kayip, 0) + ?, gunluk_kayip_tarih = ? "
                  "WHERE sunucu_id = ? AND kullanici_id = ?",
                  (miktar, bugun, sunucu_id, kullanici_id))
        db.commit()

    def _kumar_kazanma_kaydet(self, sunucu_id, kullanici_id):
        """Kumar kazanma sayısını (bu sunucuda) artırır."""
        c = db.cursor()
        c.execute("UPDATE ekonomi SET kumar_kazanma = COALESCE(kumar_kazanma, 0) + 1 WHERE sunucu_id = ? AND kullanici_id = ?",
                  (sunucu_id, kullanici_id))
        db.commit()

    @commands.hybrid_command(description="Son para hareketlerin")
    async def gecmis(self, ctx, uye: discord.Member = None):
        """Bu sunucudaki son 10 işlemi gösterir. Kullanım: !gecmis veya !gecmis @kişi"""
        hedef = uye or ctx.author
        islemler = islem_gecmisi_al(ctx.guild.id, hedef.id, 10)
        if not islemler:
            return await ctx.send("📋 İşlem geçmişi boş.", delete_after=7)

        tip_emojileri = {
            'gunluk': '📅', 'yazitura': '🪙', 'blackjack': '🃏',
            'duello': '⚔️', 'transfer': '💸', 'seviye_bonus': '⬆️',
            'satin_alma': '🛒', 'kelime_oyunu': '📝', 'paraekle': '🛠️',
        }

        satirlar = []
        for tip, miktar, aciklama, tarih in islemler:
            emoji = tip_emojileri.get(tip, '💰')
            isaret = '+' if miktar > 0 else ''
            tarih_str = tarih[:16] if tarih else '?'
            aciklama_str = f" — {aciklama}" if aciklama else ''
            satirlar.append(f"> {emoji} `{isaret}{sayi_formatla(miktar)}` Coin{aciklama_str}\n> ─ *{tarih_str}*")

        embed = discord.Embed(color=Renkler.BILGI, timestamp=datetime.datetime.now(datetime.timezone.utc))
        embed.set_author(name=f"📋 {hedef.display_name} — İşlem Geçmişi", icon_url=hedef.display_avatar.url)
        embed.description = f"{AYIRICI}\n" + "\n\n".join(satirlar) + f"\n{AYIRICI}"
        embed.set_footer(text="MezarBot • Son 10 işlem")
        await ctx.send(embed=embed)

    @commands.hybrid_command(description="Başarımların", aliases=["achievements"])
    async def basarimlar(self, ctx, uye: discord.Member = None):
        """Bu sunucudaki başarımları gösterir. Kullanım: !basarimlar veya !basarimlar @kişi"""
        hedef = uye or ctx.author
        kazanilan = basarimlari_al(ctx.guild.id, hedef.id)
        kazanilan_ids = {row[0] for row in kazanilan}

        satirlar = []
        for basarim_id, bilgi in BASARIM_LISTESI.items():
            if basarim_id in kazanilan_ids:
                satirlar.append(f"> {bilgi['emoji']} ~~**{bilgi['isim']}**~~ ✅ — {bilgi['aciklama']}")
            else:
                satirlar.append(f"> 🔒 **{bilgi['isim']}** — {bilgi['aciklama']}")

        embed = discord.Embed(color=0xFFD700, timestamp=datetime.datetime.now(datetime.timezone.utc))
        embed.set_author(name=f"🏅 {hedef.display_name} — Başarımlar ({len(kazanilan)}/{len(BASARIM_LISTESI)})",
                        icon_url=hedef.display_avatar.url)
        embed.description = f"{AYIRICI}\n" + "\n".join(satirlar) + f"\n{AYIRICI}"
        embed.set_footer(text="MezarBot • Başarım Sistemi")
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Ekonomi(bot))
