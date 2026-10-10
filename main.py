"""
MezarBot giriş noktası.

Çalıştırma: venv/bin/python main.py
Tüm yollar bot dizinine göre çözülür (bkz. yapilandirma.py); çalışma dizininden bağımsızdır.
Bu modülü import etmek yan etkisizdir (kilit/log/token kontrolü sadece baslat() içinde).
"""
import asyncio
import difflib
import fcntl
import logging
import logging.handlers
import os
import signal
import ssl
import sys

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from yapilandirma import EK_COGLAR, ENV_DOSYA, GECICI_DIZIN, KILIT_DOSYA, LOG_DOSYA, PREFIX, SAHIP_ID
from database import EkonomiMigrasyonHatasi, veritabanini_kur
from dil import DilAgaci, DilCevirmeni, _t, kancalari_kur

try:
    import certifi
except ImportError:
    certifi = None

logger = logging.getLogger('MezarBot')

# systemd birimi bu kodlarla çıkışta yeniden başlatmaz (RestartPreventExitStatus)
KILIT_CIKIS_KODU = 3           # başka bir örnek zaten çalışıyor
YAPILANDIRMA_CIKIS_KODU = 78   # EX_CONFIG — ör. DISCORD_TOKEN boş

_kilit_dosyasi = None  # süreç boyunca açık kalmalı: flock bu dosya tanıtıcısına bağlı

# Opsiyonel anahtarlar: boşsa ilgili özellik devre dışı kalır, bot çalışmaya devam eder
OPSIYONEL_ANAHTARLAR = (
    ("GROQ_API_KEY", "AI sohbet (@MezarBot) + !ciz prompt çevirisi"),
    ("REPLICATE_API_TOKEN", "!ciz resim çizimi"),
    ("SPOTIFY_CLIENT_ID", "Spotify API (yoksa Spotify linkleri embed sayfasından çözülür)"),
    ("SPOTIFY_CLIENT_SECRET", "Spotify API"),
)


def opsiyonel_anahtarlari_raporla():
    """Hangi opsiyonel özelliklerin açık olduğunu log'a yazar. Anahtar DEĞERLERİNİ asla yazdırmaz."""
    for anahtar, ozellik in OPSIYONEL_ANAHTARLAR:
        if (os.getenv(anahtar) or "").strip():
            logger.info(f"🔑 {anahtar} ayarlı → {ozellik}: aktif")
        else:
            logger.warning(f"🔑 {anahtar} boş → {ozellik}: devre dışı")
    if (os.getenv("HUGGINGFACE_TOKEN") or "").strip():
        logger.info("🔑 HUGGINGFACE_TOKEN ayarlı ama şu an hiçbir özellik kullanmıyor.")


def loglari_kur():
    """Konsol (systemd altında journal'a gider) + boyutu sınırlı dönen log dosyası."""
    bicim = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')
    konsol = logging.StreamHandler()
    dosya = logging.handlers.RotatingFileHandler(
        LOG_DOSYA, maxBytes=5 * 1024 * 1024, backupCount=5, encoding='utf-8')
    for handler in (konsol, dosya):
        handler.setFormatter(bicim)
    logging.basicConfig(level=logging.INFO, handlers=[konsol, dosya])


def tek_ornek_kilidi_al():
    """flock tabanlı tek örnek kilidi (Linux).

    Kilit, dosya tanıtıcısı açık kaldığı sürece tutulur. Süreç ölürse (çökme / kill -9 dahil)
    çekirdek kilidi kendisi bırakır — bayat PID kontrolüne veya dosyayı silmeye gerek yoktur.
    Dosyadaki PID sadece bilgi amaçlıdır."""
    global _kilit_dosyasi
    try:
        dosya = open(KILIT_DOSYA, "a+", encoding="utf-8")
    except OSError as e:
        logger.critical(f"Kilit dosyası açılamadı ({KILIT_DOSYA}): {e}")
        sys.exit(YAPILANDIRMA_CIKIS_KODU)
    try:
        fcntl.flock(dosya.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        dosya.seek(0)
        eski_pid = dosya.read().strip() or "?"
        dosya.close()
        logger.critical(f"HATA: Bot zaten çalışıyor! (PID: {eski_pid}, kilit: {KILIT_DOSYA})")
        sys.exit(KILIT_CIKIS_KODU)
    dosya.seek(0)
    dosya.truncate()
    dosya.write(str(os.getpid()))
    dosya.flush()
    _kilit_dosyasi = dosya


intents = discord.Intents.default()   # guilds, voice_states, reactions, DM'ler dahil; presences YOK
intents.message_content = True        # [PRIVILEGED] prefix komutları, kelime oyunu, AI, oto-mod
intents.members = True                # [PRIVILEGED] hoşgeldin/otorol, get_member, ses kanalı üyeleri

# owner_id: commands.is_owner() ile config.json'daki sahip_id aynı kaynaktan gelsin
# chunk_guilds_at_startup=False: Başlangıçta tüm üyeleri çekip Gateway'i tıkamaz, ihtiyaç anında önbelleğe alır
kancalari_kur()   # buton/menü/modal/olaylar sunucunun dilinde çalışsın
bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None, owner_id=SAHIP_ID,
                   chunk_guilds_at_startup=False, tree_cls=DilAgaci)

# Yüklenecek Vagonlar
vagonlar = [
    'cogs.yonetim', 'cogs.yapayzeka', 'cogs.muzik', 'cogs.yardim',
    'cogs.konusma', 'cogs.ses_aktivite', 'cogs.durum_rotator',
    'cogs.ozel_oda', 'cogs.sunucu_onay', 'cogs.ceviri'
]
vagonlar += [c for c in EK_COGLAR if c not in vagonlar]   # config.json → ek_coglar (kuruluma özel)


@bot.event
async def on_ready():
    # İlk bağlantıda slash sync yap, reconnect'lerde tekrarlama
    if not getattr(bot, '_hazir', False):
        bot._hazir = True

        # 1. Global senkronizasyon (Discord geneli arka plan)
        try:
            senkron = await bot.tree.sync()
            logger.info(f"{len(senkron)} slash komutu global olarak senkronize edildi.")
        except Exception as e:
            logger.error(f"Slash sync hatasi: {e}")

        # 2. Sunucuya özel kopyaları temizle: global + sunucu kopyası birlikte olunca Discord her komutu
        #    İKİ KEZ gösterir. (Eskiden burada copy_global_to ile her sunucuya kopyalanıyordu.)
        for g in bot.guilds:
            try:
                bot.tree.clear_commands(guild=g)
                await bot.tree.sync(guild=g)
            except Exception as e:
                logger.warning(f"{g.name} ({g.id}) sunucu komutları temizlenemedi: {e}")

        from cogs.muzik import kalici_durumu_yukle
        await kalici_durumu_yukle(bot)

    logger.info(f'{bot.user.name} hazir! {len(bot.guilds)} sunucu | {sum(g.member_count or 0 for g in bot.guilds)} kullanici')


@bot.event
async def on_command_error(ctx, error):
    # Cooldown hatası
    if isinstance(error, commands.CommandOnCooldown):
        kalan_sure = int(error.retry_after)
        uyari_mesaji = await ctx.send(_t("⏳ **Yavaşla!** Sistemi soğutuyoruz. Yeni bir işlem yapmak için **{kalan_sure} saniye** daha beklemelisin.", kalan_sure=kalan_sure))
        await asyncio.sleep(7)
        try:
            await uyari_mesaji.delete()
        except discord.NotFound:
            pass
    # Komut bulunamadı
    elif isinstance(error, commands.CommandNotFound):
        t = difflib.get_close_matches(ctx.invoked_with, [c.name for c in bot.commands], n=1, cutoff=0.5)
        if t:
            await ctx.send(_t("Bunu mu demek istedin? 👉 **{PREFIX}{t}**", PREFIX=PREFIX, t=t[0]), delete_after=5)
    # Eksik argüman
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(_t("⚠️ Eksik parametre: `{name}`. Kullanım için `{PREFIX}yardim` yaz.", name=error.param.name, PREFIX=PREFIX), delete_after=7)
    # Yetki hatası
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send(_t("🚫 Bu komutu kullanmak için yetkin yok!"), delete_after=5)
    # DM'de sunucu komutu
    elif isinstance(error, commands.NoPrivateMessage):
        # Özel (Türkçe) mesajla fırlatıldıysa onu göster (ör. ekonomi: "sunucu bazlıdır"),
        # discord.py'nin İngilizce varsayılan mesajı yerine genel Türkçe mesaj.
        mesaj = str(error)
        if not mesaj or mesaj == str(commands.NoPrivateMessage()):
            mesaj = _t("❌ Bu komut sadece sunucularda kullanılabilir.")
        await ctx.send(mesaj, delete_after=10)
    # Sahip komutu
    elif isinstance(error, commands.NotOwner):
        await ctx.send(_t("🚫 Bu komut sadece bot sahibine özel."), delete_after=5)
    # Check hatası (yönetici / VIP kontrolü vb.)
    elif isinstance(error, commands.CheckFailure):
        await ctx.send(_t("🚫 Bu komut için yetkin yok! (Sunucu yöneticisi — *Yönetici* / *Sunucuyu Yönet* yetkisi — gerekir)"), delete_after=5)
    # Diğer hatalar
    else:
        logger.error(f"Komut Hatası ({ctx.command}): {error}", exc_info=True)
        try:
            await ctx.send(_t("⚠️ Beklenmedik bir hata oluştu. Lütfen tekrar dene."), delete_after=7)
        except (aiohttp.ClientConnectorCertificateError, aiohttp.ClientConnectorError):
            logger.warning(f"Hata mesajı gönderilemedi (ağ/SSL sorunu): {ctx.command}")


@bot.tree.error
async def on_tree_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    """Slash komutları için genel hata yakalayıcı."""
    if isinstance(error, app_commands.CommandOnCooldown):
        kalan = int(error.retry_after)
        mesaj = _t("⏳ Yavaşla! Bu komut soğuma süresinde. **{kalan} saniye** sonra tekrar deneyebilirsin.", kalan=kalan)
    elif isinstance(error, app_commands.MissingPermissions):
        mesaj = _t("🚫 Bu komutu kullanmak için gerekli Discord yetkisine sahip değilsin.")
    elif isinstance(error, app_commands.BotMissingPermissions):
        mesaj = _t("🚫 Bot bu komutu çalıştırmak için gerekli sunucu yetkilerine sahip değil.")
    elif isinstance(error, app_commands.CheckFailure):
        mesaj = _t("🚫 Bu komutu kullanmak için yetkin yok (Yönetici yetkisi gereklidir).")
    elif isinstance(error, app_commands.NoPrivateMessage):
        mesaj = _t("❌ Bu komut sadece sunucularda kullanılabilir.")
    else:
        cmd_name = interaction.command.name if interaction.command else "Bilinmeyen"
        logger.error(f"Slash Komut Hatası ({cmd_name}): {error}", exc_info=True)
        mesaj = _t("⚠️ İşlem sırasında beklenmedik bir hata oluştu. Lütfen tekrar dene.")

    try:
        if interaction.response.is_done():
            await interaction.followup.send(mesaj, ephemeral=True)
        else:
            await interaction.response.send_message(mesaj, ephemeral=True)
    except Exception as e:
        logger.warning(f"Slash hata yanıtı iletilemedi: {e}")


async def _kapat(sinyal):
    """SIGTERM/SIGINT: botu düzgün kapat. Bot.close() cog'ları kaldırır → ekonomi XP buffer'ı DB'ye yazılır."""
    logger.info(f"{sinyal.name} alındı, bot kapatılıyor...")
    await bot.close()


async def main(token):
    # ── Discord.py SSL Connector ──
    # Cloudflare HTTP/2 connection coalescing bazen hostname mismatch'e yol açıyor.
    # force_close=True: bağlantı havuzu tekrar kullanımını kapatır, her istek temiz bağlantı açar.
    _ssl_ctx = ssl.create_default_context()   # sistem CA deposu
    if certifi:
        _ssl_ctx.load_verify_locations(certifi.where())
    bot.http.connector = aiohttp.TCPConnector(
        ssl=_ssl_ctx, force_close=True, enable_cleanup_closed=True
    )
    logger.info("🔒 SSL connector (force_close) yapılandırıldı.")

    loop = asyncio.get_running_loop()
    for sinyal in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sinyal, lambda s=sinyal: asyncio.create_task(_kapat(s)))

    async with bot:
        await bot.tree.set_translator(DilCevirmeni())   # slash açıklamaları İngilizce istemcilerde İngilizce
        for vagon in vagonlar:
            try:
                await bot.load_extension(vagon)
                logger.info(f"📦 Yüklendi: {vagon}")
            except Exception as e:
                logger.error(f"❌ Hata: {vagon} yüklenemedi. Sebep: {e}", exc_info=True)
        await bot.start(token)


def baslat():
    loglari_kur()
    tek_ornek_kilidi_al()

    token = (os.getenv("DISCORD_TOKEN") or "").strip()
    if not token:
        logger.critical(f"HATA: DISCORD_TOKEN boş! Bot token'ını {ENV_DOSYA} dosyasına yaz.")
        sys.exit(YAPILANDIRMA_CIKIS_KODU)
    opsiyonel_anahtarlari_raporla()

    os.makedirs(GECICI_DIZIN, exist_ok=True)
    # Şema + migrasyonlar + cache: cog'lar yüklenmeden ve Discord'a bağlanmadan önce hazır olsun
    try:
        veritabanini_kur()
    except EkonomiMigrasyonHatasi as e:
        # Migrasyon geri alındı, DB değişmedi. Yeniden başlatma aynı hatayı verir (78 → systemd tekrar denemez).
        logger.critical(f"HATA: Ekonomi migrasyonu yapılamadı, bot başlatılmıyor: {e}")
        sys.exit(YAPILANDIRMA_CIKIS_KODU)
    asyncio.run(main(token))
    # Müzik: yt-dlp güncellendiyse bot.cikis_kodu = 75 → systemd (Restart=on-failure) yeni sürümle yeniden başlatır
    cikis_kodu = getattr(bot, 'cikis_kodu', 0)
    if cikis_kodu:
        sys.exit(cikis_kodu)


if __name__ == "__main__":
    baslat()
