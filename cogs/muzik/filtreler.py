"""
Ses filtreleri → FFmpeg -af zinciri.

Filtre değişince akış MEVCUT KONUMDAN yeniden başlatılır (oynatici.Oynatici.yeniden_baslat).
Hız/perde değiştiren filtrelerde (nightcore, vaporwave, hız) şarkı içindeki konum
`hiz_carpani()` ile hesaplanır: 1 sn çıktı = hiz_carpani sn şarkı.

Her zincir tests/muzik_test.py'de gerçek bir akışın 5 sn'si üzerinde ffmpeg ile doğrulanır (çıkış kodu 0).
"""
from dataclasses import dataclass, field

ORNEKLEME = 48000

# Bas güçlendirme seviyeleri: (etiket, kazanç dB)
BAS_SEVIYELERI = {0: ("Kapalı", 0), 1: ("Hafif", 4), 2: ("Orta", 8), 3: ("Güçlü", 12), 4: ("Aşırı", 18)}

PERDE_EFEKTLERI = {
    # ad: (etiket, oran) — asetrate ile hız+perde birlikte değişir
    "nightcore": ("Nightcore", 1.25),
    "vaporwave": ("Vaporwave", 0.80),
}

HIZ_MIN, HIZ_MAX = 0.5, 2.0

NORMALIZASYON_ZINCIRI = f"loudnorm=I=-14:TP=-1.5:LRA=11,aresample={ORNEKLEME}"


@dataclass
class FiltreDurumu:
    bas: int = 0                 # 0-4
    perde: str = ""              # '' | 'nightcore' | 'vaporwave'
    sekiz_d: bool = False
    karaoke: bool = False
    hiz: float = 1.0             # atempo (perdeyi değiştirmeden hız)
    normalizasyon: bool = False
    _ek: dict = field(default_factory=dict, repr=False)

    def aktif_mi(self):
        """Ses normalizasyonu hariç herhangi bir efekt açık mı?"""
        return bool(self.bas or self.perde or self.sekiz_d or self.karaoke or abs(self.hiz - 1.0) > 1e-3)

    def islem_gerekli_mi(self):
        """FFmpeg'de -af gerekiyor mu? (değilse Opus doğrudan aktarım mümkün)"""
        return self.aktif_mi() or self.normalizasyon

    def hiz_carpani(self):
        oran = PERDE_EFEKTLERI[self.perde][1] if self.perde in PERDE_EFEKTLERI else 1.0
        return oran * self.hiz

    def sifirla(self, normalizasyon_koru=True):
        norm = self.normalizasyon if normalizasyon_koru else False
        self.bas, self.perde, self.sekiz_d, self.karaoke, self.hiz = 0, "", False, False, 1.0
        self.normalizasyon = norm

    def af_zinciri(self):
        """FFmpeg -af değeri (gerek yoksa boş dize). Sıra: vokal çıkarma → perde → bas → hız → 8D → normalizasyon."""
        z = []
        if self.karaoke:
            # Merkezdeki (mono) içeriği — genelde vokal — bastırır, yanları korur
            z.append("stereotools=mlev=0.015625")
        if self.perde in PERDE_EFEKTLERI:
            oran = PERDE_EFEKTLERI[self.perde][1]
            z.append(f"aresample={ORNEKLEME},asetrate={int(ORNEKLEME * oran)},aresample={ORNEKLEME}")
            if self.perde == "vaporwave":
                z.append("aecho=0.8:0.85:60:0.25")
        if self.bas in BAS_SEVIYELERI and self.bas > 0:
            kazanc = BAS_SEVIYELERI[self.bas][1]
            z.append(f"bass=g={kazanc}:f=110:w=0.6")
        if abs(self.hiz - 1.0) > 1e-3:
            z.append(f"atempo={self.hiz:.3f}")
        if self.sekiz_d:
            z.append("apulsator=hz=0.125:amount=0.85")
        if self.bas >= 3 or self.perde:
            # Bas / perde sonrası kırpılmayı (clipping) önle
            z.append("alimiter=limit=0.95:level=disabled")
        if self.normalizasyon:
            z.append(NORMALIZASYON_ZINCIRI)
        return ",".join(z)

    def ozet(self):
        """Panelde gösterilecek kısa liste."""
        parcalar = []
        if self.bas:
            parcalar.append(f"🔈 Bas: {BAS_SEVIYELERI[self.bas][0]}")
        if self.perde in PERDE_EFEKTLERI:
            parcalar.append(f"🌙 {PERDE_EFEKTLERI[self.perde][0]}")
        if self.sekiz_d:
            parcalar.append("🎧 8D")
        if self.karaoke:
            parcalar.append("🎤 Karaoke")
        if abs(self.hiz - 1.0) > 1e-3:
            parcalar.append(f"⏩ {self.hiz:g}x")
        if self.normalizasyon:
            parcalar.append("📶 Normalizasyon")
        return parcalar


# Komut / menü seçenekleri: anahtar → (etiket, emoji, açıklama)
# Sahibin isteği (2026-09-13): bassboost / nightcore / 8D vb. efektler kullanıcıya SUNULMAZ — "normal" ses.
# Efekt mantığı (FiltreDurumu, secenek_uygula) testler ve geriye uyumluluk için duruyor.
FILTRE_SECENEKLERI = {
    "kapat":        ("Efektleri kapat", "🚫", "Filtresiz, saf ses"),
    "normalizasyon": ("Ses dengeleme", "📶", "Şarkılar arası ses farkını eşitler"),
}


def secenek_uygula(durum, anahtar, deger=None):
    """Menü/komut seçeneğini FiltreDurumu'na uygular (aç/kapa mantığıyla). Açıklama metni döner.
    Geçersiz anahtar → ValueError."""
    if anahtar == "kapat":
        durum.sifirla(normalizasyon_koru=True)
        return "Tüm efektler kapatıldı."
    if anahtar.startswith("bas") and anahtar[3:].isdigit():
        seviye = int(anahtar[3:])
        if seviye not in BAS_SEVIYELERI:
            raise ValueError(anahtar)
        durum.bas = 0 if durum.bas == seviye else seviye
        return f"Bassboost: {BAS_SEVIYELERI[durum.bas][0]}"
    if anahtar in PERDE_EFEKTLERI:
        durum.perde = "" if durum.perde == anahtar else anahtar
        return f"{PERDE_EFEKTLERI[anahtar][0]}: {'açık' if durum.perde else 'kapalı'}"
    if anahtar == "8d":
        durum.sekiz_d = not durum.sekiz_d
        return f"8D: {'açık' if durum.sekiz_d else 'kapalı'}"
    if anahtar == "karaoke":
        durum.karaoke = not durum.karaoke
        return f"Karaoke: {'açık' if durum.karaoke else 'kapalı'}"
    if anahtar in ("hizlandir", "yavaslat", "hiz"):
        if deger is None:
            hedef = 1.25 if anahtar == "hizlandir" else 0.8 if anahtar == "yavaslat" else 1.0
            deger = 1.0 if abs(durum.hiz - hedef) < 1e-3 else hedef
        deger = round(min(HIZ_MAX, max(HIZ_MIN, float(deger))), 2)
        durum.hiz = deger
        return f"Hız: {deger:g}x"
    if anahtar == "normalizasyon":
        durum.normalizasyon = not durum.normalizasyon
        return f"Normalizasyon: {'açık' if durum.normalizasyon else 'kapalı'}"
    raise ValueError(anahtar)


def tum_test_zincirleri():
    """Test için: her filtre tek başına + birkaç kombinasyon → [(ad, af_zinciri)]."""
    sonuc = []
    for anahtar in FILTRE_SECENEKLERI:
        if anahtar == "kapat":
            continue
        d = FiltreDurumu()
        secenek_uygula(d, anahtar)
        sonuc.append((anahtar, d.af_zinciri()))
    d = FiltreDurumu(bas=3, perde="nightcore", sekiz_d=True, normalizasyon=True)
    sonuc.append(("kombinasyon:bas3+nightcore+8d+norm", d.af_zinciri()))
    d = FiltreDurumu(karaoke=True, hiz=1.5, perde="vaporwave")
    sonuc.append(("kombinasyon:karaoke+vaporwave+1.5x", d.af_zinciri()))
    return sonuc
