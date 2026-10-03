# =====================================================
# rag-app-fastapi — salin_data.py
# Menyalin 12 chunk dari database "ragapp" -> "ragapp_fastapi"
# =====================================================
# Ini AMAN: hanya MEMBACA dari ragapp, hanya MENULIS ke
# ragapp_fastapi. Database aslimu tidak diubah sedikit pun.
#
# Cara pakai (jalankan SENDIRI di terminal):
#   cd /Users/macbook/project/kerja/rag-app-fastapi
#   /Users/macbook/project/kerja/.venv/bin/python salin_data.py
# =====================================================

import os
import sys
from pathlib import Path

import psycopg2
from psycopg2.extras import Json

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

ASAL = {                      # database lama (HANYA DIBACA)
    "dbname": "ragapp",
    "user": os.getenv("DB_USER", "macbook"),
    "password": os.getenv("DB_PASSWORD", ""),
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
}
TUJUAN = {                    # database baru (DITULIS)
    "dbname": os.getenv("DB_NAME", "ragapp_fastapi"),
    "user": os.getenv("DB_USER", "macbook"),
    "password": os.getenv("DB_PASSWORD", ""),
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
}


def main():
    print(f"📖 Membaca dari : {ASAL['dbname']}")
    print(f"📝 Menulis ke   : {TUJUAN['dbname']}\n")

    # --- 1. Baca semua chunk dari database lama ---
    src = psycopg2.connect(**ASAL)
    cur = src.cursor()
    cur.execute("SELECT text, source, metadata, embedding FROM documents ORDER BY id")
    baris = cur.fetchall()
    cur.close()
    src.close()
    print(f"✅ Terbaca: {len(baris)} chunk")

    if not baris:
        print("⚠ Database ragapp kosong. Tidak ada yang disalin.")
        return

    # --- 2. Kosongkan tabel tujuan (biar tidak dobel kalau dijalankan 2x) ---
    dst = psycopg2.connect(**TUJUAN)
    dcur = dst.cursor()
    dcur.execute("TRUNCATE documents RESTART IDENTITY")
    print("🧹 Tabel tujuan dibersihkan")

    # --- 3. Salin barisnya ---
    for teks, sumber, metadata, embedding in baris:
        dcur.execute(
            """INSERT INTO documents (text, source, metadata, embedding)
               VALUES (%s, %s, %s, %s)""",
            (teks, sumber, Json(metadata) if metadata else None, embedding),
        )
    dst.commit()

    # --- 4. Verifikasi ---
    dcur.execute("SELECT COUNT(*) FROM documents")
    jumlah = dcur.fetchone()[0]
    dcur.close()
    dst.close()

    print(f"\n🎉 Selesai. Database '{TUJUAN['dbname']}' sekarang berisi {jumlah} chunk.")
    print("   Cek dengan:")
    print(f"   psql -d {TUJUAN['dbname']} -c \"SELECT count(*) FROM documents;\"")


if __name__ == "__main__":
    main()
