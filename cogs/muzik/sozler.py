"""
Şarkı sözleri — LRCLIB (https://lrclib.net/api, ücretsiz, anahtarsız).

Senkron (LRC, zaman damgalı) söz varsa çalan konuma göre o anki satır vurgulanır; yoksa düz metin.
Sonuçlar bellekte küçük bir LRU önbellekte tutulur (aynı şarkı için tekrar istek yok).
"""
import asyncio
import logging
import re
from collections import OrderedDict

import aiohttp
from dil import _t

logger = logging.getLogger('MezarBot.Muzik.Sozler')

LRCLIB = "https://lrclib.net/api"
_BASLIKLAR = {'User-Agent': 'MezarBot/2.0 (Discord muzik botu; https://lrclib.net kullanicisi)'}
_ONBELLEK_BOYUTU = 128
_GECICI_HATA = object()

# Başlıktan atılacak kalıplar: (Official Video), [HD], | Lyrics, ft. X, #etiket ...
_PARANTEZ = re.compile(r'[\(\[【](?:[^\)\]】]*?)(?:official|video|audio|lyric|klip|hd|4k|remaster|visualizer|'
                       r'söz|sözleri|music|mv|m/v|clip|live|canlı)[^\)\]】]*[\)\]】]', re.I)
_KALINTI = re.compile(r'\s*(?:\||//|｜).*$')
_FT = re.compile(r'\s+(?:ft\.?|feat\.?|featuring)\s+.*$', re.I)
_ETIKET = re.compile(r'#\S+')
_LRC_SATIR = re.compile(r'\[(\d{1,2}):(\d{2})(?:[.:](\d{1,3}))?\]')


def baslik_temizle(baslik, sanatci=""):
    """'TARKAN - Şımarık (Official Music Video)' → ('TARKAN', 'Şımarık')."""
    b = _ETIKET.sub("", baslik or "")
    b = _PARANTEZ.sub("", b)
    b = _KALINTI.sub("", b)
    b = " ".join(b.split())
    s = (sanatci or "").strip()
    if " - " in b:
        sol, sag = b.split(" - ", 1)
        if not s or s.casefold() in sol.casefold() or sol.casefold() in s.casefold() or len(sol) < 40:
            s, b = sol.strip(), sag.strip()
    b = _FT.sub("", b).strip(" -\"'")
    s = _FT.sub("", s)
    s = re.sub(r'\s*-\s*topic$', '', s, flags=re.I).strip()
    s = re.sub(r'\s*(?:VEVO|Official)$', '', s, flags=re.I).strip()
    return s, b


def lrc_coz(metin):
    """LRC metni → [(saniye, satır)] (sıralı). Birden fazla zaman damgalı satırları da açar."""
    sonuc = []
    for satir in (metin or "").splitlines():
        damgalar = list(_LRC_SATIR.finditer(satir))
        if not damgalar:
            continue
        yazi = _LRC_SATIR.sub("", satir).strip()
        for d in damgalar:
            kesir = d.group(3) or "0"
            sn = int(d.group(1)) * 60 + int(d.group(2)) + int(kesir) / (10 ** len(kesir))
            sonuc.append((sn, yazi))
    sonuc.sort(key=lambda x: x[0])
    return sonuc


def anlik_indeks(senkron, konum):
    """Konumdaki (saniye) satırın indeksi; ilk satırdan önceyse -1."""
    idx = -1
    for i, (t, _) in enumerate(senkron):
        if t <= konum + 0.3:
            idx = i
        else:
            break
    return idx


def canli_pencere(senkron, konum, once=3, sonra=5):
    """Çalan satır kalın olacak şekilde birkaç satırlık pencere metni."""
    i = anlik_indeks(senkron, konum)
    bas = max(0, i - once)
    son = min(len(senkron), max(i, 0) + sonra + 1)
    satirlar = []
    for j in range(bas, son):
        yazi = senkron[j][1] or "♪"
        satirlar.append(f"**▶ {yazi}**" if j == i else f"-# {yazi}" if j < i else yazi)
    if i == -1:
        satirlar.insert(0, _t("*♪ (giriş)*"))
    return "\n".join(satirlar)


def sayfalara_bol(metin, limit=1800):
    """Uzun metni satır sınırlarından bölerek ≤limit karakterlik sayfalara ayırır."""
    sayfalar, mevcut = [], ""
    for satir in (metin or "").splitlines():
        while len(satir) > limit:
            if mevcut:
                sayfalar.append(mevcut)
                mevcut = ""
            sayfalar.append(satir[:limit])
            satir = satir[limit:]
        if len(mevcut) + len(satir) + 1 > limit:
            sayfalar.append(mevcut)
            mevcut = satir
        else:
            mevcut = f"{mevcut}\n{satir}" if mevcut else satir
    if mevcut.strip():
        sayfalar.append(mevcut)
    return sayfalar or [_t("*(boş)*")]


class SozIstemcisi:
    def __init__(self):
        self._oturum = None
        self._onbellek = OrderedDict()

    async def _http(self):
        if self._oturum is None or self._oturum.closed:
            self._oturum = aiohttp.ClientSession(headers=_BASLIKLAR, timeout=aiohttp.ClientTimeout(total=12))
        return self._oturum

    async def kapat(self):
        if self._oturum and not self._oturum.closed:
            await self._oturum.close()

    async def _getir(self, yol, params):
        oturum = await self._http()
        """→ JSON, 404'te None, geçici hatada (5xx/zaman aşımı, bir kez yeniden denenir) _GECICI_HATA."""
        for deneme in range(2):
            if deneme:
                await asyncio.sleep(1)
            try:
                async with oturum.get(f"{LRCLIB}/{yol}", params=params) as yanit:
                    if yanit.status == 404:
                        return None
                    if yanit.status == 200:
                        return await yanit.json(content_type=None)
                    logger.warning(f"LRCLIB HTTP {yanit.status} ({yol})")
                    if yanit.status < 500 and yanit.status != 429:
                        return None
            except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as e:
                logger.warning(f"LRCLIB isteği başarısız ({yol}): {e}")
        return _GECICI_HATA

    async def bul(self, baslik, sanatci="", sure=0, serbest_sorgu=None):
        """→ dict(sanatci, baslik, album, sure, senkron=[(sn, satır)], duz=str, enstrumantal=bool) ya da None."""
        if serbest_sorgu:
            s, b = baslik_temizle(serbest_sorgu)
        else:
            s, b = baslik_temizle(baslik, sanatci)
        anahtar = (s.casefold(), b.casefold(), int(sure or 0) // 3)
        if anahtar in self._onbellek:
            self._onbellek.move_to_end(anahtar)
            return self._onbellek[anahtar]

        hata = False

        async def getir(yol, params):
            nonlocal hata
            veri = await self._getir(yol, params)
            if veri is _GECICI_HATA:
                hata = True
                return None
            return veri

        kayit = None
        if s and b and sure and not serbest_sorgu:
            kayit = await getir("get", {"artist_name": s, "track_name": b, "duration": int(sure)})
        if not kayit and b:
            params = {"track_name": b}
            if s:
                params["artist_name"] = s
            kayit = self._en_iyi(await getir("search", params), sure)
        if not kayit:
            kayit = self._en_iyi(await getir("search", {"q": f"{s} {b}".strip()}), sure)
        sonuc = self._bicimle(kayit) if kayit else None
        if sonuc is None and hata:
            return None   # LRCLIB geçici hatası: "bulunamadı" önbelleğe yazılmaz, sonraki istek yeniden dener
        self._onbellek[anahtar] = sonuc
        while len(self._onbellek) > _ONBELLEK_BOYUTU:
            self._onbellek.popitem(last=False)
        return sonuc

    @staticmethod
    def _en_iyi(liste, sure):
        if not isinstance(liste, list):
            return None
        adaylar = [k for k in liste if k.get('syncedLyrics') or k.get('plainLyrics') or k.get('instrumental')]
        if not adaylar:
            return None

        def puan(k):
            fark = abs((k.get('duration') or 0) - sure) if sure else 0
            return (0 if k.get('syncedLyrics') else 1) + (fark / 4 if fark <= 20 else 50)
        return min(adaylar, key=puan)

    @staticmethod
    def _bicimle(k):
        return {
            'sanatci': k.get('artistName') or "",
            'baslik': k.get('trackName') or "",
            'album': k.get('albumName') or "",
            'sure': k.get('duration') or 0,
            'senkron': lrc_coz(k.get('syncedLyrics') or ""),
            'duz': (k.get('plainLyrics') or "").strip(),
            'enstrumantal': bool(k.get('instrumental')),
        }
