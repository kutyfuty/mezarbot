"""
ESKİ tek seferlik migrasyon betiği (itiraf_kanal_id sütunu).
Artık gerekli değil: database.veritabanini_kur() bu sütunu ve diğer tüm migrasyonları
bot başlarken otomatik (idempotent) ekler. Sadece geriye dönük uyumluluk için duruyor.
"""
import os
import sqlite3

from yapilandirma import DB_DOSYA

db_path = DB_DOSYA
if not os.path.exists(db_path):
    print(f"HATA: {db_path} bulunamadı.")
else:
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Sütunun varlığını kontrol et
        cursor.execute("PRAGMA table_info(sunucu_ayarlar)")
        columns = [column[1] for column in cursor.fetchall()]

        if "itiraf_kanal_id" not in columns:
            print("itiraf_kanal_id sutunu ekleniyor...")
            cursor.execute("ALTER TABLE sunucu_ayarlar ADD COLUMN itiraf_kanal_id INTEGER")
            conn.commit()
            print("OK. Sutun basariyla eklendi.")
        else:
            print("itiraf_kanal_id sutunu zaten mevcut.")

        conn.close()
    except sqlite3.Error as e:
        print(f"HATA: {e}")
