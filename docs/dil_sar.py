"""
Tek seferlik/yardımcı araç: bir .py dosyasındaki kullanıcıya görünen Türkçe metinleri dil._t(...) ile sarar.
f-string → _t("şablon {ad}", ad=ifade). Dışarıda kalanlar: log/print, SQL, docstring, karşılaştırma, sözlük
anahtarı, dekoratör, modül/sınıf düzeyi sabitler, custom_id ve kanal/rol ADLARI. Sonuç elle gözden geçirilmelidir.

    venv/bin/python docs/dil_sar.py cogs/ornek.py [--yaz]
"""
import ast
import re
import sys

TR_HARF = re.compile(r"[çğıöşüÇĞİÖŞÜâîû]")
TR_KELIME = re.compile(r"\b(ve|bir|bu|için|yok|var|ile|olarak|değil|kanal|şarkı|oda|kuyruk|sunucu|komut|kullan|ayar|"
                       r"liste|üye|ses|yetki|hata|sadece|lütfen|tamam|kapat|aç|ekle|sil|seç)\w*", re.I)
SQL = re.compile(r"^\s*(SELECT|INSERT|UPDATE|DELETE|CREATE|ALTER|PRAGMA|DROP|WITH)\b", re.I)
HARIC_CAGRILAR = {"debug", "info", "warning", "error", "exception", "critical", "log", "print", "compile", "match",
                  "search", "sub", "fullmatch", "findall", "split", "execute", "executemany", "executescript",
                  "startswith", "endswith", "replace", "strip", "lstrip", "rstrip", "get", "getenv", "join", "format",
                  "getattr", "setattr", "hasattr", "ceviri", "Choice", "describe", "command", "hybrid_command",
                  "Group", "choices", "rename", "create_text_channel", "create_voice_channel", "create_category",
                  "create_role", "create_category_channel", "encode", "decode", "index", "count", "lower", "upper",
                  "casefold", "zfill", "ljust", "rjust", "center", "partition", "rpartition"}
HARIC_ANAHTARLAR = {"custom_id", "reason_key", "name_key", "category", "overwrites", "emoji", "url", "icon_url",
                    "style", "color", "colour"}
AD_ANAHTARLARI_KANAL = {"name"}   # utils.get(..., name=...) / kanal düzenleme adları
KANAL_CAGRILARI = {"get", "find", "create_text_channel", "create_voice_channel", "create_category", "create_role",
                   "edit", "clone"}


GEVSEK = False
TR_SOZLUK = re.compile(r"\b(saniye|dakika|saat|parca|kapali|acik|sira|siradaki|sonraki|onceki|kanal|liste|listesi|"
                       r"komut|kullanici|uye|yetki|rol|mesaj|sebep|sure|limit|kisi|kisiler|sayfa|toplam|tum|hepsi|yeni|eski|"
                       r"bilgi|durum|ayarlar|ayarla|kaydedildi|silindi|eklendi|kaldirildi|basarili|basarisiz|bulunamadi|"
                       r"gecersiz|zaten|simdi|tekrar|dene|bekle|olmali|gerekli|devre|disi|aktif|pasif|otomatik|"
                       r"evet|hayir|iptal|onay|dil|sunucu|oda|odasi|sahibi|davet|ad|adi|yasak|at|gizli|gorunur|"
                       r"muzik|sarki|calma|cal|oynat|durdur|devam|atla|karistir|dongu|ses|seviye|kayit|gecmis|sozler)\b", re.I)


def turkce_mu(s):
    if not s or len(s.strip()) < 2 or SQL.search(s):
        return False
    if GEVSEK and not re.fullmatch(r"[\w.:/\-]+", s) and TR_SOZLUK.search(s):
        return True
    if re.fullmatch(r"[\w.:/\-]+", s) and not TR_HARF.search(s):
        return False   # tanımlayıcı / yol / anahtar
    return bool(TR_HARF.search(s) or TR_KELIME.search(s))


def cagri_adi(call):
    f = call.func
    return f.attr if isinstance(f, ast.Attribute) else (f.id if isinstance(f, ast.Name) else "")


class Sarici:
    def __init__(self, kaynak):
        self.kaynak = kaynak
        self.satirlar = [x + "\n" for x in kaynak.split("\n")]   # splitlines \u2028 vb.'de de böler, ast bölmez
        self.agac = ast.parse(kaynak)
        self.ebeveyn = {}
        for n in ast.walk(self.agac):
            for c in ast.iter_child_nodes(n):
                self.ebeveyn[c] = n
        self.ofset = [0]
        for s in self.satirlar:
            self.ofset.append(self.ofset[-1] + len(s))
        self.anahtarlar = []

    def poz(self, satir, sutun):
        # ast sütunları UTF-8 bayt ofseti
        bayt = self.satirlar[satir - 1].encode("utf-8")[:sutun]
        return self.ofset[satir - 1] + len(bayt.decode("utf-8"))

    def metin(self, n):
        return self.kaynak[self.poz(n.lineno, n.col_offset):self.poz(n.end_lineno, n.end_col_offset)]

    def docstring_mi(self, n):
        e = self.ebeveyn.get(n)
        if isinstance(e, ast.Expr):
            ust = self.ebeveyn.get(e)
            return isinstance(ust, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)) and ust.body[0] is e
        return False

    def _kardes_cevrili(self, n):
        """n bir koşullu ifadenin (a if k else b / a or b) kolu ve öbür kol _t(...) ise True."""
        e = self.ebeveyn.get(n)
        if isinstance(e, ast.IfExp) and n in (e.body, e.orelse):
            diger = e.orelse if n is e.body else e.body
        elif isinstance(e, ast.BoolOp) and isinstance(e.op, ast.Or):
            digerleri = [v for v in e.values if v is not n]
            return any(isinstance(v, ast.Call) and cagri_adi(v) == "_t" for v in digerleri)
        else:
            return False
        return isinstance(diger, ast.Call) and cagri_adi(diger) == "_t"

    ZORLA = set()

    def aday_mi(self, n):
        if getattr(n, "lineno", None) in self.ZORLA and isinstance(n, (ast.Constant, ast.JoinedStr)):
            eski = globals()["turkce_mu"]
            globals()["turkce_mu"] = lambda m: bool(m) and bool(re.search(r"[A-Za-zçğıöşüÇĞİÖŞÜ]{2}", m))
            try:
                return self._aday_mi(n)
            finally:
                globals()["turkce_mu"] = eski
        return self._aday_mi(n)

    def _aday_mi(self, n):
        if isinstance(n, ast.Constant):
            if not isinstance(n.value, str):
                return False
            if not turkce_mu(n.value) and not (GEVSEK and re.search(r"[A-Za-zçğıöşüÇĞİÖŞÜ]{2}", n.value)
                                               and self._kardes_cevrili(n)):
                return False
        elif isinstance(n, ast.JoinedStr):
            sabit = "".join(v.value for v in n.values if isinstance(v, ast.Constant))
            if not turkce_mu(sabit) and not (GEVSEK and re.search(r"[A-Za-zçğıöşüÇĞİÖŞÜ]{2}", sabit)
                                             and self._kardes_cevrili(n)):
                return False
            if any(isinstance(v, ast.FormattedValue) and v.format_spec is not None and
                   any(isinstance(x, ast.FormattedValue) for x in v.format_spec.values) for v in n.values):
                return False
        else:
            return False
        if self.docstring_mi(n):
            return False
        # f-string içindeki sabit parça değil
        e = self.ebeveyn.get(n)
        if isinstance(e, ast.JoinedStr) or isinstance(e, ast.FormattedValue) and e.format_spec is n:
            return False
        # ata zinciri
        cocuk, ata = n, e
        fonksiyon_icinde = False
        while ata is not None:
            if isinstance(ata, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                if cocuk in getattr(ata, "decorator_list", []) or (hasattr(ata, "args") and cocuk is ata.args):
                    return False
                fonksiyon_icinde = True
                break
            if isinstance(ata, ast.ClassDef) and cocuk in ata.decorator_list:
                return False
            if isinstance(ata, ast.arguments):
                return False
            if isinstance(ata, ast.Compare):
                return False
            if "--hatalar" not in sys.argv and isinstance(ata, ast.Raise) and isinstance(ata.exc, ast.Call) and cagri_adi(ata.exc) in (
                    "ValueError", "TypeError", "RuntimeError", "KeyError", "AssertionError", "EkonomiMigrasyonHatasi"):
                return False
            if isinstance(ata, ast.Dict) and cocuk in ata.keys:
                return False
            if isinstance(ata, ast.Subscript) and cocuk is ata.slice:
                return False
            if isinstance(ata, ast.keyword) and ata.arg in HARIC_ANAHTARLAR:
                return False
            if isinstance(ata, ast.Call) and cagri_adi(ata) == "_t" and not isinstance(cocuk, ast.keyword):
                return False   # zaten şablon
            if isinstance(ata, ast.Call):
                ad = cagri_adi(ata)
                if cocuk is ata.func:
                    return False
                if ad in HARIC_CAGRILAR and not (ad == "get" and self._kanal_get_degil(ata, cocuk)):
                    return False
                if ad in KANAL_CAGRILARI and isinstance(cocuk, ast.keyword) and cocuk.arg in AD_ANAHTARLARI_KANAL:
                    return False
            if isinstance(ata, ast.FormattedValue):
                pass
            cocuk, ata = ata, self.ebeveyn.get(ata)
        return fonksiyon_icinde

    @staticmethod
    def _kanal_get_degil(call, cocuk):
        return False

    def adaylar(self, kok):
        return [n for n in ast.walk(kok) if n is not kok and self.aday_mi(n)] if kok is not None else []

    def yeniden_yaz(self, kok):
        """kok düğümünün kaynağını, içindeki aday metinler sarılmış olarak döner."""
        if isinstance(kok, ast.Module):
            bas, son = 0, len(self.kaynak)
        else:
            bas = self.poz(kok.lineno, kok.col_offset)
            son = self.poz(kok.end_lineno, kok.end_col_offset)
        if self.aday_mi(kok) and kok is not self._kok_haric:
            return self.sar(kok)
        degisimler = []
        for c in self._dogrudan_adaylar(kok):
            degisimler.append((self.poz(c.lineno, c.col_offset), self.poz(c.end_lineno, c.end_col_offset), self.sar(c)))
        parca = self.kaynak[bas:son]
        for b, s, yeni in sorted(degisimler, reverse=True):
            parca = parca[:b - bas] + yeni + parca[s - bas:]
        return parca

    _kok_haric = None

    def _dogrudan_adaylar(self, kok):
        """kok altındaki, başka bir aday tarafından kapsanmayan aday düğümler."""
        sonuc = []

        def gez(n):
            for c in ast.iter_child_nodes(n):
                if self.aday_mi(c):
                    sonuc.append(c)
                else:
                    gez(c)
        gez(kok)
        return sonuc

    def sar(self, n):
        girinti = " " * 4
        if isinstance(n, ast.Constant):
            sablon, degerler = n.value, []
        else:
            sablon, degerler, kullanilan = "", [], {}
            for i, v in enumerate(n.values):
                if isinstance(v, ast.Constant):
                    sablon += v.value.replace("{", "{{").replace("}", "}}")
                    continue
                ifade = self.yeniden_yaz(v.value)
                ad = self._ad(v.value, i)
                if ad in kullanilan and kullanilan[ad] != ifade:
                    k = 2
                    while f"{ad}{k}" in kullanilan and kullanilan[f"{ad}{k}"] != ifade:
                        k += 1
                    ad = f"{ad}{k}"
                kullanilan[ad] = ifade
                donusum = {-1: "", 115: "!s", 114: "!r", 97: "!a"}[v.conversion]
                bicim = ""
                if v.format_spec is not None:
                    bicim = ":" + "".join(x.value for x in v.format_spec.values)
                sablon += "{" + ad + donusum + bicim + "}"
            degerler = list(kullanilan.items())
        self.anahtarlar.append(sablon)
        parcalar = [x + "\n" for x in sablon.split("\n")[:-1]] + ([sablon.split("\n")[-1]] if sablon.split("\n")[-1] else [])
        if len(parcalar) > 2 and len(sablon) > 90:
            ayirici = "\n" + " " * (self._sutun(n) + 3)
            literal = ayirici.join('"' + self._kacis(p) + '"' for p in parcalar)
        else:
            literal = '"' + self._kacis(sablon) + '"'
        arg = "".join(f", {a}={e}" for a, e in degerler)
        return f"_t({literal}{arg})"

    @staticmethod
    def _kacis(s):
        return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\t", "\\t")

    def _sutun(self, n):
        satir = self.satirlar[n.lineno - 1]
        return len(satir.encode("utf-8")[:n.col_offset].decode("utf-8"))

    @staticmethod
    def _ad(ifade, i):
        while isinstance(ifade, ast.Call):
            ifade = ifade.func
        if isinstance(ifade, ast.Name):
            ad = ifade.id
        elif isinstance(ifade, ast.Attribute):
            ad = ifade.attr
        elif isinstance(ifade, ast.Subscript):
            return Sarici._ad(ifade.value, i)
        else:
            ad = f"d{i}"
        ad = re.sub(r"\W", "", ad).lstrip("_") or f"d{i}"
        return ad if ad.isidentifier() and ad not in ("self", "cls") else f"d{i}"

    def calistir(self):
        govde = self.yeniden_yaz(self.agac)
        return govde


def main():
    global GEVSEK
    GEVSEK = "--gevsek" in sys.argv
    yol = sys.argv[1]
    kaynak = open(yol, encoding="utf-8").read()
    s = Sarici(kaynak)
    for a in sys.argv:
        if a.startswith("--satir="):
            Sarici.ZORLA = {int(x) for x in a[8:].split(",")}
    s._kok_haric = s.agac
    yeni = s.yeniden_yaz(s.agac)
    # modül başı: kaynak[0:bas] yeniden_yaz'ın dışında kalmasın (Module'un lineno'su yok)
    if yeni != kaynak and "from dil import _t" not in yeni:
        satirlar = yeni.split("\n")
        son_import = max(i for i, l in enumerate(satirlar) if re.match(r"^(import |from \S+ import )", l))
        while satirlar[son_import].rstrip().endswith(("(", ",")) or (satirlar[son_import].count("(") > satirlar[son_import].count(")")):
            son_import += 1
            while not satirlar[son_import].rstrip().endswith(")"):
                son_import += 1
            break
        satirlar.insert(son_import + 1, "from dil import _t")
        yeni = "\n".join(satirlar)
    ast.parse(yeni)
    print(f"{len(s.anahtarlar)} metin sarıldı", file=sys.stderr)
    if "--yaz" in sys.argv:
        open(yol, "w", encoding="utf-8").write(yeni)
    else:
        sys.stdout.write(yeni)


if __name__ == "__main__":
    main()
