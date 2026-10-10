"""
MezarBot Arayüz Yardımcıları
Modern ve premium görünümlü embed'ler için ortak fonksiyonlar.
"""
import discord
import datetime
import shutil
from dil import _t


# ── Paylaşılan Sabitler ──
# Linux: PATH'teki ffmpeg (systemd birimindeki PATH dahil); bulunamazsa sistem paketinin yolu
FFMPEG_YOLU = shutil.which("ffmpeg") or "/usr/bin/ffmpeg"

DURUM_TIPLERI = {
    "oynuyor": discord.ActivityType.playing,
    "dinliyor": discord.ActivityType.listening,
    "izliyor": discord.ActivityType.watching,
    "yarismada": discord.ActivityType.competing
}


# ── Renk Paleti (Discord 2025 Uyumlu) ──
class Renkler:
    BASARI = 0x57F287       # Yeşil
    HATA = 0xED4245         # Kırmızı
    UYARI = 0xFEE75C        # Sarı
    BILGI = 0x5865F2        # Discord Blurple
    PREMIUM = 0xEB459E      # Fuşya
    MUZIK = 0x1DB954        # Spotify yeşili
    EKONOMI = 0xF1C40F      # Altın
    MODERASYON = HATA       # Bilerek HATA ile aynı kırmızı (tek kaynaktan türetilir)
    NOTR = 0x2B2D31         # Koyu gri
    DISCORD = 0x5865F2      # Blurple


# ── Dekoratif Elemanlar ──
AYIRICI = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
AYIRICI_INCE = "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈"
AYIRICI_NOKTA = "· · · · · · · · · · · · · · · · · · · · · ·"


# ── Müzik Platform Bilgileri (renk + ikon + ad) ──
# Renk: Discord embed'de canlı görünsün diye platformun marka rengi
MUZIK_PLATFORM_BILGI = {
    'youtube:music': {'ikon': '🎵', 'isim': 'YouTube Music', 'renk': 0xFF0000},
    'youtube':       {'ikon': '🔴', 'isim': 'YouTube',       'renk': 0xFF0000},
    'soundcloud':    {'ikon': '🟠', 'isim': 'SoundCloud',    'renk': 0xFF7700},
    'bandcamp':      {'ikon': '🔵', 'isim': 'Bandcamp',      'renk': 0x1DA0C3},
    'twitch':        {'ikon': '🟣', 'isim': 'Twitch',        'renk': 0x9146FF},
    'spotify':       {'ikon': '🟢', 'isim': 'Spotify',       'renk': 0x1DB954},
    'apple':         {'ikon': '🍎', 'isim': 'Apple Music',   'renk': 0xFA243C},
}

def platform_bilgi(extractor):
    """Platform extractor adına göre {ikon, isim, renk} döner. Bilinmiyorsa varsayılan."""
    if not extractor:
        return {'ikon': '🎶', 'isim': _t("Müzik"), 'renk': 0x1DB954}
    e = extractor.lower()
    for key, val in MUZIK_PLATFORM_BILGI.items():
        if key in e:
            return val
    return {'ikon': '🎶', 'isim': extractor.capitalize(), 'renk': 0x1DB954}


def progress_bar_premium(deger, maksimum, uzunluk=15):
    """Spotify benzeri modern progress bar.

    Örnek: ▰▰▰▰▰▰▰▰●▱▱▱▱▱▱
    Dolu kısım kalın blok, cursor noktası, kalan ince blok."""
    if maksimum <= 0 or deger is None:
        return "▱" * uzunluk
    oran = max(0.0, min(deger / maksimum, 1.0))
    dolu = int(oran * uzunluk)
    if dolu >= uzunluk:
        return "▰" * uzunluk
    return "▰" * dolu + "●" + "▱" * (uzunluk - dolu - 1)


def alan_satiri(emoji, etiket, deger):
    """Inline field için tek satırlık modern format.
    Örnek: ⏱ Süre / 4:15"""
    return f"{emoji}  **{etiket}**\n`{deger}`"
BOSLUK = "\u200b"


def premium_embed(baslik, aciklama=None, renk=Renkler.BILGI, thumbnail_url=None, ikon=None):
    """Premium görünümlü embed oluşturur."""
    embed = discord.Embed(
        title=baslik,
        description=aciklama,
        color=renk,
        timestamp=datetime.datetime.now(datetime.timezone.utc)
    )
    if thumbnail_url:
        embed.set_thumbnail(url=thumbnail_url)
    embed.set_footer(text="MezarBot", icon_url=ikon)
    return embed


def progress_bar(deger, maksimum, uzunluk=12):
    """Modern progress bar."""
    if maksimum <= 0:
        return "░" * uzunluk
    oran = min(deger / maksimum, 1.0)
    dolu = int(oran * uzunluk)
    return "█" * dolu + "░" * (uzunluk - dolu)


def sure_formatla(saniye):
    """Saniyeyi güzel formata çevirir."""
    if saniye is None:
        return "—"
    dakika = int(saniye // 60)
    sn = int(saniye % 60)
    if dakika >= 60:
        saat = dakika // 60
        dakika = dakika % 60
        return f"`{saat}:{dakika:02d}:{sn:02d}`"
    return f"`{dakika}:{sn:02d}`"


def sayi_formatla(sayi):
    """Sayıyı binlik ayracıyla formatlar."""
    return f"{sayi:,}".replace(",", ".")


def sure_insana_cevir(saniye):
    """Saniyeyi okunabilir Türkçe formata çevirir."""
    saniye = int(saniye)
    if saniye < 60:
        return _t("{saniye} saniye", saniye=saniye)
    elif saniye < 3600:
        return _t("{d0} dakika", d0=saniye // 60)
    elif saniye < 86400:
        return _t("{d0} saat", d0=saniye // 3600)
    else:
        return _t("{d0} gün", d0=saniye // 86400)


def mini_card(baslik, deger, emoji=""):
    """Modern bilgi kartı."""
    return f"{emoji} **{baslik}**\n> {deger}"


def bilgi_kutusu(*satirlar):
    """Tree-style bilgi kutusu.
    Her satır (emoji, etiket, deger) tuple'ı.

    Çıktı:
    ╭ 🎯 Tahmin ── Yazı
    ├ 💵 Bahis ─── 500 Coin
    ╰ 💰 Bakiye ── 1.500 Coin
    """
    if not satirlar:
        return ""
    sonuc = []
    for i, (emoji, etiket, deger) in enumerate(satirlar):
        if len(satirlar) == 1:
            prefix = "◈"
        elif i == 0:
            prefix = "╭"
        elif i == len(satirlar) - 1:
            prefix = "╰"
        else:
            prefix = "├"
        sonuc.append(f"> {prefix} {emoji} **{etiket}** ── {deger}")
    return "\n".join(sonuc)


def hata_embed(mesaj, ipucu=None):
    """Modern hata embed'i."""
    embed = discord.Embed(
        description=f"**❌ ┃ {mesaj}**",
        color=Renkler.HATA
    )
    if ipucu:
        embed.set_footer(text=f"💡 {ipucu}")
    return embed


def basari_embed(mesaj):
    """Modern başarı embed'i."""
    return discord.Embed(
        description=f"**✅ ┃ {mesaj}**",
        color=Renkler.BASARI
    )
