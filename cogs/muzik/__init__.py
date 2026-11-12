"""
MezarBot Premium Müzik (paket).

  kuyruk.py      → Parca / Kuyruk / döngü / sarma ve oylama matematiği (saf, test edilebilir)
  filtreler.py   → FFmpeg -af filtre zincirleri
  kaynaklar.py   → yt-dlp (YouTube / YT Music / SoundCloud / doğrudan link), Spotify, otomatik oynatma
  sozler.py      → LRCLIB şarkı sözleri (senkron + düz)
  oynatici.py    → sunucu başına oynatıcı (FFmpeg kaynağı, konum takibi, yeniden bağlanma, ön çözme)
  panel.py       → kalıcı kontrol paneli + sayfalı görünümler
  guncelleyici.py→ yt-dlp otomatik güncelleme
  cog.py         → Muzik cog'u (komutlar, dinleyiciler, bakım döngüleri)

Veritabanı: muzik_veritabani.py (kök dizin) — kendi tabloları, database.db bağlantısı.
main.py `from cogs.muzik import kalici_durumu_yukle` kullanır (AGENTS.md) — burada yeniden dışa aktarılır.
"""
from yapilandirma import MEMBER_PROFILI
from .cog import Muzik, js_ortamlarini_denetle, kalici_durumu_yukle
from .kaynaklar import ydl_opts, ydl_playlist_opts

__all__ = ["Muzik", "kalici_durumu_yukle", "js_ortamlarini_denetle", "ydl_opts", "ydl_playlist_opts", "setup"]

_KOMUT_INGILIZCE = {
    "oynat": ("play", "Plays a song or playlist (YouTube, Spotify, SoundCloud, direct link)"),
    "siradaki": ("playnext", "Adds a song to the top of the queue"),
    "atla": ("skip", "Skips the current song or jumps to a position"),
    "oylaatla": ("voteskip", "Votes to skip the current song"),
    "onceki": ("previous", "Plays the previous song in history"),
    "duraklat": ("pause", "Pauses playback"),
    "devam": ("resume", "Resumes playback"),
    "durdur": ("stop", "Stops playback and clears the queue"),
    "sar": ("seek", "Seeks to a timestamp in the song"),
    "ileri": ("forward", "Fast forwards by a duration"),
    "geri": ("rewind", "Rewinds by a duration"),
    "kuyruk": ("queue", "Shows the current song queue"),
    "kaldir": ("remove", "Removes a song from the queue"),
    "tasi": ("move", "Moves a song to another position in the queue"),
    "karistir": ("shuffle", "Shuffles the queue"),
    "temizle": ("clear", "Clears the queue"),
    "dongu": ("loop", "Changes the loop mode (off, song, queue)"),
    "ses": ("volume", "Sets the playback volume (0-150)"),
    "simdi": ("nowplaying", "Shows the currently playing song"),
    "muzikgecmis": ("history", "Shows playback history"),
    "sozler": ("lyrics", "Shows lyrics of the current song"),
    "ayril": ("disconnect", "Disconnects the bot from the voice channel"),
    "katil": ("join", "Connects the bot to your voice channel"),
    "istekkanali": ("requestchannel", "Sets up a dedicated music request channel"),
    "istekkanalitemizle": ("removerequestchannel", "Removes the dedicated request channel"),
    "panel": ("musicpanel", "Opens the persistent music control panel"),
    "calmalistesi": ("playlist", "Manages saved custom playlists"),
    "filtre": ("filter", "Applies audio effects (bass, 8d, nightcore, etc.)"),
    "ytdlpguncelle": ("updateytdlp", "Checks and updates yt-dlp binary"),
}


def _ingilizce_yap(cog):
    for cmd in cog.get_commands():
        if cmd.name in _KOMUT_INGILIZCE:
            en_name, en_desc = _KOMUT_INGILIZCE[cmd.name]
            eski_ad = cmd.name
            # yeni ad takma adlar arasından çıkarılır, eski ad takma adlara eklenir
            yeni_aliases = [a for a in cmd.aliases if a != en_name]
            if eski_ad not in yeni_aliases:
                yeni_aliases.append(eski_ad)
            cmd.aliases = list(dict.fromkeys(yeni_aliases))
            cmd.name = en_name
            cmd.description = en_desc
            if hasattr(cmd, 'app_command') and cmd.app_command:
                cmd.app_command.name = en_name
                cmd.app_command.description = en_desc


async def setup(bot):
    cog = Muzik(bot)
    if MEMBER_PROFILI:
        _ingilizce_yap(cog)
    await bot.add_cog(cog)
