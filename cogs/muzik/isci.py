#!/usr/bin/env python3
"""
Müzik işçi süreci — yt-dlp çıkarma + Spotify çözümleme BOTTAN AYRI BİR SÜREÇTE çalışır.

Neden: yt-dlp (ve büyük JSON ayrıştırma) Python'da CPU yoğun; bot sürecinde thread'de çalışınca
GIL'i tutar ve discord.py'nin 20 ms'lik ses thread'ini geciktirir → "ızlanma/takılma".
Bu süreç kendi GIL'ine sahip; bot sadece küçük, kırpılmış JSON sonuçları alır.

Protokol (satır başına bir JSON):
    stdin  ← {"id": 1, "islem": "cikar", "arg": {...}}
    stdout → {"id": 1, "ok": true, "sonuc": {...}}  |  {"id": 1, "ok": false, "hata": "...", "tur": "...", "http_status": 403}
stdin kapanınca süreç biter. Bu dosya paket içinden import EDİLMEZ (veritabanı vb. yüklenmez);
kaynaklar.IsciHavuzu tarafından `python isci.py` olarak başlatılır.
"""
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

_TARAYICI_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36'


def _protokol_akisi():
    """Gerçek stdout'u protokole ayırır; fd 1'i stderr'e yönlendirir (kütüphaneler print etse de protokol bozulmaz)."""
    fd = os.dup(1)
    os.dup2(2, 1)
    sys.stdout = sys.stderr
    return os.fdopen(fd, "w", encoding="utf-8", buffering=1)


class _SessizLogger:
    """yt-dlp mesajlarını yut (hatalar zaten exception olarak dönüyor)."""

    def debug(self, mesaj):
        pass

    def info(self, mesaj):
        pass

    def warning(self, mesaj):
        pass

    def error(self, mesaj):
        pass


_TAM_ANAHTARLAR = ("url", "http_headers", "acodec", "protocol", "is_live", "duration", "title", "webpage_url",
                   "id", "thumbnail", "artist", "channel", "uploader", "extractor_key", "extractor", "format_id")
_FLAT_ANAHTARLAR = ("id", "url", "webpage_url", "title", "duration", "ie_key", "channel", "uploader", "artist",
                    "extractor_key")


def _kirp_tam(bilgi):
    if bilgi and bilgi.get("entries"):
        bilgi = next((e for e in bilgi["entries"] if e), None)
    if not bilgi:
        return None
    return {k: bilgi.get(k) for k in _TAM_ANAHTARLAR}


def _kirp_flat(bilgi):
    if not bilgi:
        return None
    ogeler = []
    for e in bilgi.get("entries") or []:
        if not e:
            continue
        d = {k: e.get(k) for k in _FLAT_ANAHTARLAR}
        kucukler = e.get("thumbnails") or []
        d["thumbnail"] = e.get("thumbnail") or (kucukler[-1].get("url") if kucukler else None)
        ogeler.append(d)
    return {"title": bilgi.get("title"), "playlist_count": bilgi.get("playlist_count"), "entries": ogeler}


def cikar(secenekler, hedef, mod="tam"):
    import yt_dlp
    secenekler = dict(secenekler)
    secenekler["logger"] = _SessizLogger()
    with yt_dlp.YoutubeDL(secenekler) as ydl:
        bilgi = ydl.extract_info(hedef, download=False)
    return _kirp_flat(bilgi) if mod == "flat" else _kirp_tam(bilgi)


def spotify_embed(tur, sp_id):
    """open.spotify.com/embed sayfasındaki __NEXT_DATA__ → kırpılmış entity."""
    url = f"https://open.spotify.com/embed/{tur}/{sp_id}"
    html, son_hata = None, None
    for deneme in range(3):
        try:
            istek = urllib.request.Request(url, headers={"User-Agent": _TARAYICI_UA, "Accept-Language": "tr,en;q=0.8"})
            with urllib.request.urlopen(istek, timeout=15) as yanit:
                html = yanit.read().decode("utf-8", "replace")
            break
        except urllib.error.HTTPError as e:
            son_hata = e
            if e.code < 500:
                break
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            son_hata = e
        time.sleep(1 + deneme)
    if html is None:
        raise RuntimeError(f"Spotify embed sayfası alınamadı: {son_hata}")
    eslesme = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.S)
    if not eslesme:
        raise RuntimeError("Spotify embed: __NEXT_DATA__ yok (sayfa yapısı değişmiş olabilir)")
    try:
        varlik = json.loads(eslesme.group(1))["props"]["pageProps"]["state"]["data"]["entity"]
    except (KeyError, TypeError) as e:
        raise RuntimeError(f"Spotify embed: beklenmeyen yapı ({e!r}) — bu link türü desteklenmiyor olabilir")
    return {
        "type": varlik.get("type"), "name": varlik.get("name"), "title": varlik.get("title"), "id": varlik.get("id"),
        "duration": varlik.get("duration"),
        "artists": [{"name": a.get("name")} for a in varlik.get("artists") or [] if isinstance(a, dict)],
        "trackList": [{"title": t.get("title"), "subtitle": t.get("subtitle"), "duration": t.get("duration"),
                       "uri": t.get("uri")} for t in varlik.get("trackList") or [] if isinstance(t, dict)],
    }


_spotify_istemci = None


def spotify_api(tur, sp_id, limit=500):
    """Spotify Web API (client credentials; anahtarlar ortam değişkenlerinden). → {"baslik", "parcalar": [...]}"""
    global _spotify_istemci
    if _spotify_istemci is None:
        import spotipy
        from spotipy.cache_handler import MemoryCacheHandler
        from spotipy.oauth2 import SpotifyClientCredentials
        _spotify_istemci = spotipy.Spotify(
            auth_manager=SpotifyClientCredentials(client_id=os.environ.get("SPOTIFY_CLIENT_ID", "").strip(),
                                                  client_secret=os.environ.get("SPOTIFY_CLIENT_SECRET", "").strip(),
                                                  cache_handler=MemoryCacheHandler()),
            requests_timeout=10, retries=0)
    sp = _spotify_istemci

    def kirp(t):
        return {"name": t.get("name"), "id": t.get("id"), "duration_ms": t.get("duration_ms"),
                "artists": [a.get("name") for a in t.get("artists") or [] if a.get("name")]}
    if tur == "track":
        t = sp.track(sp_id)
        return {"baslik": t.get("name"), "parcalar": [kirp(t)]}
    if tur == "album":
        veri = sp.album(sp_id)
        sayfa = veri.get("tracks") or {}
        ogeler = list(sayfa.get("items") or [])
        while sayfa.get("next") and len(ogeler) < limit:
            sayfa = sp.next(sayfa) or {}
            ogeler.extend(sayfa.get("items") or [])
        return {"baslik": veri.get("name"), "parcalar": [kirp(t) for t in ogeler[:limit] if t]}
    veri = sp.playlist(sp_id)
    sayfa = veri.get("tracks") or veri.get("items") or {}
    ogeler = [i.get("track") or i.get("item") for i in sayfa.get("items") or []]
    while sayfa.get("next") and len(ogeler) < limit:
        sayfa = sp.next(sayfa) or {}
        ogeler.extend(i.get("track") or i.get("item") for i in sayfa.get("items") or [])
    return {"baslik": veri.get("name"), "parcalar": [kirp(t) for t in ogeler[:limit] if t and t.get("name")]}


def ping():
    import yt_dlp.version
    return {"pid": os.getpid(), "yt_dlp": yt_dlp.version.__version__}


ISLEMLER = {"cikar": cikar, "spotify_embed": spotify_embed, "spotify_api": spotify_api, "ping": ping}


def main():
    cikis = _protokol_akisi()
    yazma_kilidi = threading.Lock()
    havuz = ThreadPoolExecutor(max_workers=int(os.environ.get("MUZIK_ISCI_IS_PARCACIGI", "2")))
    import yt_dlp  # noqa: F401 — ısınma: ilk istek beklemesin

    def yaz(yanit):
        satir = json.dumps(yanit, ensure_ascii=False, default=str)
        with yazma_kilidi:
            cikis.write(satir + "\n")
            cikis.flush()

    def calistir(istek):
        try:
            sonuc = ISLEMLER[istek["islem"]](**istek.get("arg", {}))
            yaz({"id": istek["id"], "ok": True, "sonuc": sonuc})
        except BaseException as e:  # işçi asla çökmemeli; hata bota metin olarak döner
            yaz({"id": istek.get("id"), "ok": False, "hata": str(e)[:2000], "tur": type(e).__name__,
                 "http_status": getattr(e, "http_status", None)})

    for satir in sys.stdin:
        satir = satir.strip()
        if not satir:
            continue
        try:
            istek = json.loads(satir)
        except json.JSONDecodeError:
            continue
        havuz.submit(calistir, istek)
    havuz.shutdown(wait=False, cancel_futures=True)


if __name__ == "__main__":
    main()
