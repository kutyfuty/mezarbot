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
from .cog import Muzik, js_ortamlarini_denetle, kalici_durumu_yukle
from .kaynaklar import ydl_opts, ydl_playlist_opts

__all__ = ["Muzik", "kalici_durumu_yukle", "js_ortamlarini_denetle", "ydl_opts", "ydl_playlist_opts", "setup"]


async def setup(bot):
    await bot.add_cog(Muzik(bot))
