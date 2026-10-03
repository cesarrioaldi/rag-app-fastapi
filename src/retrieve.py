# =====================================================
# rag-app-fastapi — retrieve.py
# Pencarian chunk paling mirip dengan pertanyaan.
# =====================================================
# INI DISALIN dari rag-app/src/retrieve.py dengan SATU perubahan:
# nama database default jadi "ragapp_fastapi".
#
# Perhatikan: bagian "SELECT ... ORDER BY <=>" DI BAWAH SAMA PERSIS
# dengan project aslimu. Ini buktinya — FastAPI nanti tidak
# mengubah cara ambil data sama sekali. Yang berubah cuma
# siapa yang memanggil fungsi ini (terminal vs HTTP).
# =====================================================

import json
import os
import sys
from pathlib import Path

# --- Path akar proyek ---------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

# --- Baca konfigurasi dari .env -----------------------------------------
from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

# --- Konfigurasi database -----------------------------------------------
import psycopg2

DB_CONFIG = {
    "dbname": os.getenv("DB_NAME"),      # wajib di .env
    "user": os.getenv("DB_USER"),        # wajib di .env
    "password": os.getenv("DB_PASSWORD"),# wajib di .env (kosongkan kalau no-password)
    "host": os.getenv("DB_HOST"),        # wajib di .env
    "port": os.getenv("DB_PORT"),        # wajib di .env
}

# --- Model embedding (dimuat sekali) --------------------------------------
from sentence_transformers import SentenceTransformer

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL")  # wajib di .env
_model_embed = None


def dapatkan_model_embed():
    """Ambil model embedding (muat sekali, bukan tiap pertanyaan)."""
    global _model_embed
    if _model_embed is None:
        print("⏳ Memuat model embedding ...")
        _model_embed = SentenceTransformer(EMBEDDING_MODEL)
    return _model_embed


# =====================================================
# DIPAKAI OLEH lifespan DI main.py
# =====================================================
# Fungsi ini ada supaya model bisa dipaksa dimuat LEBIH AWAL —
# saat server start — bukan menunggu request pertama datang.
#
# Isinya cuma memanggil dapatkan_model_embed() yang sudah ada.
# Jadi logika pemuatannya tetap SATU tempat, tidak diduplikasi.
def siapkan_model():
    """Paksa muat model embedding sekarang juga.

    Dipanggil sekali oleh lifespan di main.py saat server menyala.
    Sesudah ini, semua request langsung dapat model yang sudah siap
    di memori — tidak ada lagi jeda 14 detik di request pertama.
    """
    return dapatkan_model_embed()


def search(pertanyaan: str, top_k: int = 3) -> list:
    """Cari chunk paling mirip dengan pertanyaan.

    Hasil: [{"chunk_id":..., "text":..., "source":..., "skor":...}]
    """
    # 1. Ubah pertanyaan jadi vektor (384 angka)
    model = dapatkan_model_embed()
    vektor_pertanyaan = model.encode([pertanyaan], normalize_embeddings=True)[0]

    # 2. Cari chunk terdekat — SQL ini IDENTIK dengan project aslimu
    sql = """
        SELECT id, text, source, metadata,
               1 - (embedding <=> %s::vector) AS skor
        FROM documents
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """
    vektor_str = json.dumps(vektor_pertanyaan.tolist())

    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute(sql, (vektor_str, vektor_str, top_k))
    hasil = []
    for id_, teks, sumber, metadata, skor in cur.fetchall():
        chunk_id = metadata.get("chunk_id") if metadata else None
        hasil.append(
            {
                "chunk_id": chunk_id,
                "text": teks,
                "source": sumber,
                "skor": float(skor),
            }
        )
    cur.close()
    conn.close()
    return hasil


# =====================================================
# JALUR PERINTAH — test retrieval (masih bisa dipakai seperti dulu)
# =====================================================
def main():
    if len(sys.argv) < 2:
        print('Cara pakai: python src/retrieve.py "pertanyaan kamu"')
        sys.exit(1)
    pertanyaan = " ".join(sys.argv[1:])

    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("SELECT source, COUNT(*) FROM documents GROUP BY source")
    total = cur.fetchall()
    cur.close()
    conn.close()
    if total:
        for sumber, n in total:
            print(f"📚 DB: {n} chunk dari '{sumber}'")
    else:
        print("⚠ Database KOSONG — salin data dari ragapp dulu.")

    print(f"\n🔍 Pertanyaan: {pertanyaan}\n")
    hasil = search(pertanyaan)
    if not hasil:
        print("(tidak ada hasil)")
        return
    for i, r in enumerate(hasil, start=1):
        print(f"[{i}] skor {r['skor']:.3f} | {r['source']} | chunk {r['chunk_id']}")
        print(f"    {r['text'][:200]}...")


if __name__ == "__main__":
    main()
