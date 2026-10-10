"""
Kuyruk, parça ve saf hesaplar (Discord'dan bağımsız → çevrimdışı test edilebilir).

- Parca: kuyruktaki bir şarkı. Akış URL'si tembel çözülür (çalmadan hemen önce / ön-çözme ile).
- Kuyruk: sunucu başına sıra; ekle / sıradakine ekle / kaldır / taşı / karıştır / temizle + döngü modları.
- sure_coz / hedef_konum: ileri-geri sarma matematiği ("1:30", "+30", "-10").
- oylama_esigi: oylamalı atlama için gereken oy sayısı.
"""
import math
import random
import time
import urllib.parse
from collections import deque
from dataclasses import dataclass, field, replace

# Döngü modları
DONGU_KAPALI, DONGU_SARKI, DONGU_KUYRUK = "kapali", "sarki", "kuyruk"
DONGU_SIRASI = (DONGU_KAPALI, DONGU_SARKI, DONGU_KUYRUK)
DONGU_ETIKET = {DONGU_KAPALI: "Kapalı", DONGU_SARKI: "Şarkı", DONGU_KUYRUK: "Kuyruk"}
DONGU_TAKMA_ADLAR = {
    "kapali": DONGU_KAPALI, "kapalı": DONGU_KAPALI, "kapat": DONGU_KAPALI, "off": DONGU_KAPALI, "yok": DONGU_KAPALI,
    "sarki": DONGU_SARKI, "şarkı": DONGU_SARKI, "tek": DONGU_SARKI, "track": DONGU_SARKI, "song": DONGU_SARKI, "single": DONGU_SARKI,
    "kuyruk": DONGU_KUYRUK, "sira": DONGU_KUYRUK, "sıra": DONGU_KUYRUK, "liste": DONGU_KUYRUK, "queue": DONGU_KUYRUK, "all": DONGU_KUYRUK,
}

VARSAYILAN_KUYRUK_LIMITI = 500   # sunucu başına
GECMIS_LIMITI = 50


@dataclass
class Parca:
    """Kuyruktaki bir parça. `sorgu`: URL ya da yt-dlp arama ifadesi (ör. 'ytsearch1:...')."""
    sorgu: str
    baslik: str = ""
    url: str = ""                 # insanlar için sayfa linki (webpage_url)
    sure: int = 0                 # saniye; 0/None = bilinmiyor / canlı yayın
    kucuk_resim: str = ""
    kaynak: str = ""              # 'youtube', 'soundcloud', 'spotify', 'http' ...
    sanatci: str = ""
    video_id: str = ""            # YouTube video ID (radyo/otomatik oynatma + geçmiş tekrar kontrolü)
    isteyen_id: int = 0
    isteyen_ad: str = ""
    isteyen_avatar: str = ""
    otomatik: bool = False        # otomatik oynatma (radyo) tarafından eklendi
    beklenen_sure: int = 0        # Spotify gibi eşleştirmelerde hedef süre (en yakın YouTube sonucu seçilir)
    arama_metni: str = ""         # kısıtlı/silinmiş video çıkarsa sıradaki arama adayını denemek için
    # ── Çözüm (çalmadan önce doldurulur) ──
    akis_url: str = ""
    akis_basliklari: dict = field(default_factory=dict)
    akis_codec: str = ""
    akis_protokol: str = ""
    canli: bool = False
    cozulme_zamani: float = 0.0

    def gosterim(self, uzunluk=60):
        if self.baslik:
            metin = self.baslik
        elif self.sorgu.startswith(("ytsearch", "scsearch")):
            metin = self.sorgu.split(":", 1)[-1]
        else:
            metin = self.sorgu
        metin = " ".join(str(metin).split())
        return metin if len(metin) <= uzunluk else metin[:uzunluk - 1] + "…"

    def kopya(self):
        """Çözüm bilgisi olmayan temiz kopya (döngü / önceki / kişisel liste için)."""
        return replace(self, akis_url="", akis_basliklari={}, akis_codec="", akis_protokol="", cozulme_zamani=0.0)

    def akis_gecerli_mi(self, simdi=None, pay=None):
        """Çözülmüş akış URL'si hâlâ kullanılabilir mi? YouTube URL'lerindeki `expire` parametresine,
        yoksa çözülme yaşına bakar. `pay`: şarkının kalanı + tampon (saniye)."""
        if not self.akis_url:
            return False
        simdi = simdi or time.time()
        if pay is None:
            pay = (self.sure or 0) + 120
        try:
            sorgu = urllib.parse.parse_qs(urllib.parse.urlparse(self.akis_url).query)
            bitis = int(sorgu.get("expire", [0])[0])
        except (ValueError, TypeError):
            bitis = 0
        if bitis:
            return bitis - simdi > pay
        # expire bilgisi yok (SoundCloud HLS, doğrudan link...): kısa ömürlü say
        return simdi - self.cozulme_zamani < 300

    def veritabani_bicimi(self):
        return {'sorgu': self.url or self.sorgu, 'baslik': self.baslik, 'url': self.url, 'sure': self.sure or None}


class KuyrukDolu(Exception):
    pass


class Kuyruk:
    """Sunucu başına şarkı sırası. Tüm işlemler O(n) liste işlemleri; n ≤ limit (500)."""

    def __init__(self, limit=VARSAYILAN_KUYRUK_LIMITI):
        self.limit = limit
        self._parcalar = []

    # ── Okuma ──
    def __len__(self):
        return len(self._parcalar)

    def __iter__(self):
        return iter(list(self._parcalar))

    def __getitem__(self, i):
        return self._parcalar[i]

    def bos_mu(self):
        return not self._parcalar

    def bos_yer(self):
        return max(0, self.limit - len(self._parcalar))

    def ilk(self):
        return self._parcalar[0] if self._parcalar else None

    def toplam_sure(self):
        return sum(p.sure or 0 for p in self._parcalar)

    # ── Yazma ──
    def ekle(self, parca):
        if len(self._parcalar) >= self.limit:
            raise KuyrukDolu(self.limit)
        self._parcalar.append(parca)
        return len(self._parcalar)

    def toplu_ekle(self, parcalar):
        """Limite kadar ekler; eklenen sayıyı döner."""
        eklenecek = list(parcalar)[:self.bos_yer()]
        self._parcalar.extend(eklenecek)
        return len(eklenecek)

    def basa_ekle(self, parca, zorla=False):
        """Sıradaki olarak ekler. zorla=True: limit dolu olsa bile (önceki / döngü için)."""
        if not zorla and len(self._parcalar) >= self.limit:
            raise KuyrukDolu(self.limit)
        self._parcalar.insert(0, parca)
        return 1

    def al(self):
        """Sıradakini çıkarıp döner (yoksa None)."""
        return self._parcalar.pop(0) if self._parcalar else None

    def kaldir(self, sira_no):
        """1 tabanlı sıra numarasındaki parçayı çıkarır. Geçersizse IndexError."""
        if not 1 <= sira_no <= len(self._parcalar):
            raise IndexError(sira_no)
        return self._parcalar.pop(sira_no - 1)

    def tasi(self, kimden, kime):
        """1 tabanlı: `kimden` numaralı parçayı `kime` konumuna taşır. Taşınan parçayı döner."""
        n = len(self._parcalar)
        if not (1 <= kimden <= n and 1 <= kime <= n):
            raise IndexError((kimden, kime))
        parca = self._parcalar.pop(kimden - 1)
        self._parcalar.insert(kime - 1, parca)
        return parca

    def atla_konuma(self, sira_no):
        """1 tabanlı: sira_no'dan önceki parçaları atar, sira_no'yu sıradaki yapar. Atılanları döner."""
        if not 1 <= sira_no <= len(self._parcalar):
            raise IndexError(sira_no)
        atilanlar = self._parcalar[:sira_no - 1]
        del self._parcalar[:sira_no - 1]
        return atilanlar

    def karistir(self, rastgele=None):
        (rastgele or random).shuffle(self._parcalar)

    def temizle(self):
        n = len(self._parcalar)
        self._parcalar.clear()
        return n

    def kullanicinin_parcalarini_kaldir(self, kullanici_id):
        once = len(self._parcalar)
        self._parcalar = [p for p in self._parcalar if p.isteyen_id != kullanici_id]
        return once - len(self._parcalar)

    def otomatikleri_kaldir(self):
        once = len(self._parcalar)
        self._parcalar = [p for p in self._parcalar if not p.otomatik]
        return once - len(self._parcalar)

    # ── Döngü ──
    def sonraki(self, biten, dongu, atlandi=False):
        """Biten parçaya ve döngü moduna göre sıradaki parçayı belirler (kuyruğu günceller).
        - şarkı döngüsü: atlanmadıysa AYNI parça nesnesi tekrar (çözülmüş akış URL'si geçerliyse yeniden kullanılır)
        - kuyruk döngüsü: biten parça sona eklenir (atlansa da — listeden düşmesin)
        """
        if biten is not None:
            if dongu == DONGU_SARKI and not atlandi:
                return biten
            if dongu == DONGU_KUYRUK and not biten.otomatik:
                self._parcalar.append(biten.kopya())
        return self.al()


def dongu_sonraki_mod(mod):
    i = DONGU_SIRASI.index(mod) if mod in DONGU_SIRASI else 0
    return DONGU_SIRASI[(i + 1) % len(DONGU_SIRASI)]


class Gecmis:
    """Son çalınan parçalar (önceki şarkı + geçmiş komutu + otomatik oynatmada tekrar engeli)."""

    def __init__(self, limit=GECMIS_LIMITI):
        self._d = deque(maxlen=limit)

    def ekle(self, parca):
        if parca is not None:
            self._d.append(parca.kopya())

    def geri_al(self):
        return self._d.pop() if self._d else None

    def son(self, n=10):
        return list(self._d)[-n:][::-1]   # en yeni önce

    def video_idleri(self):
        return {p.video_id for p in self._d if p.video_id}

    def basliklar(self):
        return {normallestir(p.baslik) for p in self._d if p.baslik}

    def __len__(self):
        return len(self._d)


def normallestir(metin):
    return " ".join(str(metin or "").casefold().split())


# ══════════════════════════════════════════════
#  SARMA (SEEK) MATEMATİĞİ
# ══════════════════════════════════════════════

def sure_coz(metin):
    """'90' | '1:30' | '1:02:03' | '+30' | '-10' | '1m30s' → (saniye, isaret) ; isaret: 0 mutlak, +1 ileri, -1 geri.
    Geçersizse (None, None)."""
    metin = str(metin or "").strip().lower().replace(" ", "")
    if not metin:
        return None, None
    isaret = 0
    if metin[0] in "+-":
        isaret = 1 if metin[0] == "+" else -1
        metin = metin[1:]
    if not metin:
        return None, None
    try:
        if ":" in metin:
            parcalar = [int(p) for p in metin.split(":")]
            if len(parcalar) > 3 or any(p < 0 for p in parcalar) or any(p >= 60 for p in parcalar[1:]):
                return None, None
            saniye = 0
            for p in parcalar:
                saniye = saniye * 60 + p
        elif any(b in metin for b in "hms"):
            saniye, sayi = 0, ""
            carpan = {"h": 3600, "m": 60, "s": 1}
            for ch in metin:
                if ch.isdigit():
                    sayi += ch
                elif ch in carpan and sayi:
                    saniye += int(sayi) * carpan[ch]
                    sayi = ""
                else:
                    return None, None
            if sayi:
                saniye += int(sayi)
        else:
            saniye = int(metin)
    except ValueError:
        return None, None
    if saniye < 0:
        return None, None
    return saniye, isaret


def hedef_konum(mevcut, saniye, isaret, toplam):
    """Sarma hedefini hesaplar ve [0, toplam-1] aralığına sıkıştırır (toplam bilinmiyorsa üst sınır yok)."""
    if isaret == 1:
        hedef = mevcut + saniye
    elif isaret == -1:
        hedef = mevcut - saniye
    else:
        hedef = saniye
    hedef = max(0.0, float(hedef))
    if toplam and toplam > 0:
        hedef = min(hedef, max(0.0, toplam - 1))
    return hedef


def sure_metni(saniye):
    """185 → '3:05', 3725 → '1:02:05'; None/0 bilinmiyorsa '—'."""
    if saniye is None:
        return "—"
    saniye = max(0, int(saniye))
    s, kalan = divmod(saniye, 3600)
    d, sn = divmod(kalan, 60)
    return f"{s}:{d:02d}:{sn:02d}" if s else f"{d}:{sn:02d}"


# ══════════════════════════════════════════════
#  OYLAMALI ATLAMA
# ══════════════════════════════════════════════

def oylama_esigi(dinleyici_sayisi, oran):
    """Gereken oy: ceil(dinleyici × oran), en az 1, en fazla dinleyici sayısı. Oran [0.1, 1.0] aralığına sıkıştırılır."""
    oran = min(1.0, max(0.1, float(oran or 0.5)))
    n = max(0, int(dinleyici_sayisi))
    if n == 0:
        return 1
    return max(1, min(n, math.ceil(n * oran - 1e-9)))


def ilerleme_cubugu(gecen, toplam, uzunluk=16):
    """▬▬▬▬🔘────── tarzı çubuk (toplam bilinmiyorsa canlı yayın çubuğu)."""
    if not toplam or toplam <= 0:
        return "▬" * (uzunluk // 2) + "🔴" + "▬" * (uzunluk - uzunluk // 2 - 1)
    oran = max(0.0, min(1.0, (gecen or 0) / toplam))
    konum = min(uzunluk - 1, int(oran * uzunluk))
    return "▬" * konum + "🔘" + "─" * (uzunluk - konum - 1)
