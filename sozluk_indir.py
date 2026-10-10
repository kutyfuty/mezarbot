"""
Türkçe Sözlük İndirici — MezarBot Kelime Oyunu için offline sözlük oluşturur.

Kullanım:
    python sozluk_indir.py

Kaynaklar (sırayla denenir):
    1. GitHub'daki açık kaynak Türkçe kelime listesi
    2. TDK otomatik tamamlama API'si (tüm harfler için taranır)

Sonuç: mezarbot.db → turkce_sozluk tablosuna yüklenir.
"""
import sqlite3
import requests
import time
import string
import sys

from yapilandirma import DB_DOSYA  # bot dizinine göre mutlak yol (çalışma dizininden bağımsız)

# Türkçe alfabe
TURKCE_HARFLER = list("abcçdefgğhıijklmnoöprsştuüvyz")

# Bilinen açık kaynak Türkçe kelime listeleri (GitHub raw URL'leri)
KELIME_LISTESI_KAYNAKLARI = [
    "https://raw.githubusercontent.com/CanNuhlar/Turkce-Kelime-Listesi/master/turkce_kelime_listesi.txt",
    "https://raw.githubusercontent.com/mertemin/turkish-word-list/master/words.txt",
]


def github_dan_indir():
    """GitHub'dan hazır Türkçe kelime listesi indirir."""
    for url in KELIME_LISTESI_KAYNAKLARI:
        try:
            print(f"  Deneniyor: {url[:60]}...")
            r = requests.get(url, timeout=30)
            if r.status_code == 200 and len(r.text) > 1000:
                kelimeler = set()
                for satir in r.text.splitlines():
                    kelime = satir.strip().lower()
                    # Sadece Türkçe karakterlerden oluşan, 2+ harfli kelimeler
                    if len(kelime) >= 2 and kelime.isalpha():
                        kelimeler.add(kelime)
                if len(kelimeler) > 5000:
                    print(f"  ✅ {len(kelimeler)} kelime indirildi!")
                    return kelimeler
                print(f"  ⚠️ Sadece {len(kelimeler)} kelime bulundu, yetersiz.")
        except Exception as e:
            print(f"  ❌ Hata: {e}")
    return set()


def tdk_dan_tara():
    """TDK otomatik tamamlama API'sini kullanarak kelime tarar."""
    print("\n📖 TDK API taranıyor (bu biraz sürebilir)...")
    kelimeler = set()
    session = requests.Session()
    session.headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'

    # Her harf kombinasyonu için TDK autocomplete
    toplam = len(TURKCE_HARFLER) * len(TURKCE_HARFLER)
    sayac = 0

    for h1 in TURKCE_HARFLER:
        for h2 in TURKCE_HARFLER:
            sayac += 1
            prefix = h1 + h2
            try:
                r = session.get(
                    f"https://sozluk.gov.tr/autocomplete.json",
                    params={'ara': prefix},
                    timeout=10
                )
                if r.status_code == 200:
                    data = r.json()
                    if isinstance(data, list):
                        for item in data:
                            madde = item.get('madde', '').strip().lower()
                            if madde and len(madde) >= 2 and ' ' not in madde:
                                kelimeler.add(madde)
            except Exception:
                pass

            # Her 50 istekte durum göster
            if sayac % 50 == 0:
                print(f"  İlerleme: {sayac}/{toplam} ({len(kelimeler)} kelime bulundu)")

            # Rate limiting — TDK'yı yormamak için
            time.sleep(0.15)

    print(f"  ✅ TDK'dan {len(kelimeler)} kelime tarandı!")
    return kelimeler


def veritabanina_yukle(kelimeler):
    """Kelimeleri mezarbot.db → turkce_sozluk tablosuna yükler."""
    db = sqlite3.connect(DB_DOSYA)
    c = db.cursor()

    # Tablo yoksa oluştur
    c.execute("CREATE TABLE IF NOT EXISTS turkce_sozluk (kelime TEXT PRIMARY KEY)")

    # Mevcut kelime sayısı
    c.execute("SELECT COUNT(*) FROM turkce_sozluk")
    mevcut = c.fetchone()[0]
    print(f"\n📊 Mevcut sözlükte {mevcut} kelime var.")

    # Toplu ekleme (INSERT OR IGNORE — var olanları atlar)
    eklenen = 0
    batch = [(k,) for k in kelimeler]
    c.executemany("INSERT OR IGNORE INTO turkce_sozluk (kelime) VALUES (?)", batch)
    eklenen = c.rowcount
    db.commit()

    c.execute("SELECT COUNT(*) FROM turkce_sozluk")
    toplam = c.fetchone()[0]
    db.close()

    print(f"✅ {eklenen} yeni kelime eklendi. Toplam sözlük: {toplam} kelime.")
    return toplam


def main():
    print("=" * 50)
    print("🇹🇷 MezarBot Türkçe Sözlük İndirici")
    print("=" * 50)

    tum_kelimeler = set()

    # 1) GitHub'dan hazır liste
    print("\n📥 GitHub'dan kelime listesi indiriliyor...")
    github_kelimeler = github_dan_indir()
    tum_kelimeler.update(github_kelimeler)

    # 2) TDK API taraması
    if len(tum_kelimeler) < 10000:
        print(f"\n⚠️ GitHub'dan yeterli kelime bulunamadı ({len(tum_kelimeler)}), TDK taranıyor...")
        tdk_kelimeler = tdk_dan_tara()
        tum_kelimeler.update(tdk_kelimeler)
    else:
        print(f"\n✅ GitHub'dan yeterli kelime bulundu, TDK taraması atlanıyor.")
        # Yine de TDK'yı kısa tarayalım (sadece tek harfler)
        print("📖 TDK'dan ek kelimeler çekiliyor (kısa tarama)...")
        session = requests.Session()
        session.headers['User-Agent'] = 'Mozilla/5.0'
        for h in TURKCE_HARFLER:
            try:
                r = session.get(f"https://sozluk.gov.tr/autocomplete.json", params={'ara': h}, timeout=10)
                if r.status_code == 200:
                    data = r.json()
                    if isinstance(data, list):
                        for item in data:
                            madde = item.get('madde', '').strip().lower()
                            if madde and len(madde) >= 2 and ' ' not in madde:
                                tum_kelimeler.add(madde)
            except Exception:
                pass
            time.sleep(0.2)

    if not tum_kelimeler:
        print("\n❌ Hiç kelime bulunamadı! İnternet bağlantısını kontrol et.")
        sys.exit(1)

    print(f"\n📚 Toplam benzersiz kelime: {len(tum_kelimeler)}")

    # DB'ye yükle
    veritabanina_yukle(tum_kelimeler)
    print("\n🎉 Sözlük hazır! Botu yeniden başlattığında otomatik yüklenecek.")


if __name__ == "__main__":
    main()
