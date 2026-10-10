"""Sarılmamış, doğal dil gibi görünen metinleri listeler (elle gözden geçirmek için)."""
import ast, re, sys
sys.path.insert(0, "docs")
import dil_sar as ds
ds.GEVSEK = True
for yol in sys.argv[1:]:
    s = ds.Sarici(open(yol, encoding="utf-8").read())
    eski = ds.turkce_mu
    ds.turkce_mu = lambda m: bool(m) and bool(re.search(r"[A-Za-zçğıöşüÇĞİÖŞÜ]{3}", m)) and not re.fullmatch(r"[\w.:/\-%]+", m) \
        and not ds.SQL.search(m)
    for n in ast.walk(s.agac):
        if isinstance(n, (ast.Constant, ast.JoinedStr)) and s.aday_mi(n):
            print(f"{yol}:{n.lineno}: {s.metin(n)[:110]}")
    ds.turkce_mu = eski
