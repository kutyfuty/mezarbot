"""dil_en.py'yi yeniden yazar: mevcut EN + yeni çeviriler (anahtar listesi JSON + {id: çeviri} dosyaları). Anahtarlar dosya sırasında."""
import json, sys, importlib.util, os, re
kok = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, kok)
from dil_en import EN
anahtarlar = json.load(open(sys.argv[1], encoding="utf-8"))
yeni = {}
for yol in sys.argv[2:]:
    spec = importlib.util.spec_from_file_location("t", yol); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    yeni.update(m.T)
birlesik = dict(EN)
eksik = []
for i, k, yer in anahtarlar:
    if i in yeni:
        birlesik[k] = yeni[i]
    elif k not in birlesik:
        eksik.append((i, k))
def kaynak(k):
    for i, kk, yer in anahtarlar:
        if kk == k:
            return yer.split(":")[0]
    return "?"
gruplar = {}
for k, v in birlesik.items():
    gruplar.setdefault(kaynak(k) if kaynak(k) != "?" else "diğer", []).append((k, v))
satirlar = ['"""İngilizce çeviriler — anahtar: koddaki _t(...) şablonu (Türkçe, birebir). tests/dil_test.py eksikleri bulur.',
            'Yeni metin eklerken: kodda _t("…") kullan, buraya karşılığını ekle (yer tutucular {ad} aynı kalmalı)."""', "", "EN = {"]
for g in sorted(gruplar, key=lambda x: (x.startswith("/"), x)):
    satirlar.append(f"    # ── {g} ──")
    for k, v in gruplar[g]:
        satirlar.append(f"    {json.dumps(k, ensure_ascii=False)}:\n        {json.dumps(v, ensure_ascii=False)},")
satirlar.append("}")
open(os.path.join(kok, "dil_en.py"), "w", encoding="utf-8").write("\n".join(satirlar) + "\n")
print(f"{len(birlesik)} çeviri yazıldı; eksik {len(eksik)}: {eksik[:5]}")
