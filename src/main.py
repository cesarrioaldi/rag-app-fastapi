# =====================================================
# rag-app-fastapi — main.py
# INI DIA FILE FASTAPI-NYA.
# =====================================================
# Bandingkan dengan chat.py di project aslimu:
#
#   chat.py  : input() dari terminal  -> ask() -> print()
#   main.py  : HTTP POST dari browser -> ask() -> JSON response
#
# FUNGSI ask()-nya SAMA PERSIS. Yang berbeda hanya:
#   - chat.py  memanggil ask() saat kamu menekan Enter
#   - main.py  memanggil ask() saat ada request masuk ke port 8000
#
# Itu inti seluruh pelajaran ini.
#
# Cara menjalankan (jalankan SENDIRI di terminal):
#   cd /Users/macbook/project/kerja/01-portofolio/rag-app-fastapi
#   /Users/macbook/project/kerja/.venv/bin/uvicorn src.main:app --reload
#
# Lalu buka:
#   http://127.0.0.1:8000/docs      <- halaman uji otomatis dari FastAPI
#   http://127.0.0.1:8000/health    <- cek server hidup
#
# Hentikan server: tekan Ctrl+C
# =====================================================

import json
import os
import sys
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

# >>> INI BARIS PALING PENTING DI SELURUH PROJECT <<<
# Kita cuma IMPORT fungsi ask() yang sudah ada. Tidak ada
# logika RAG baru di sini. Semua kerja kerasnya sudah kamu
# tulis di generate.py.
from generate import ask

# Untuk lifespan: kita butuh siapkan_model() dari retrieve.py
# supaya model embedding bisa dimuat saat startup, bukan
# saat request pertama datang.
from retrieve import siapkan_model


# =====================================================
# 1. SKEMA REQUEST & RESPONSE (pakai Pydantic)
# =====================================================
# Pydantic = satpam. Dia memeriksa data yang masuk SEBELUM
# kode kita jalan. Kalau client kirim {"pertanyaan": 123}
# (angka, bukan teks), FastAPI otomatis balas error 422
# dengan pesan jelas — tanpa kita tulis pengecekan manual.
class TanyaRequest(BaseModel):
    pertanyaan: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Pertanyaan yang mau diajukan ke dokumen",
        examples=["bagaimana prosedur audit internal keuangan?"],
    )
    top_k: int = Field(
        3,
        ge=1,
        le=10,
        description="Berapa potongan dokumen yang diambil (1-10)",
    )


class TanyaResponse(BaseModel):
    jawaban: str = Field(..., description="Teks jawaban dari model")
    mode: str = Field(..., description="sapaan | umum | rag")
    sumber: list[str] = Field(default_factory=list, description="File sumber jawaban")
    skor_tertinggi: float = Field(0.0, description="Skor kemiripan tertinggi")


# =====================================================
# 2. APLIKASI (+ lifespan)
# =====================================================
# LIFESPAN = kode yang dijalankan saat server hidup & mati.
#
#   sebelum yield  →  dijalankan SEKALI saat server start
#   setelah yield  →  dijalankan SEKALI saat server dimatikan
#
# Kenapa ini penting? Tanpa lifespan, model embedding baru
# dimuat saat REQUEST PERTAMA datang — jadi pengguna pertama
# menunggu ~14 detik. Dengan lifespan, pemuatan itu terjadi
# saat server start, sebelum ada pengguna. Request pertama
# langsung cepat.
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── FASE STARTUP ────────────────────────────────────
    # Di sini server belum menerima request apa pun.
    # Waktu yang tepat untuk menyiapkan hal-hal yang lambat.
    print("🚀 [startup] Menyiapkan layanan ...")
    siapkan_model()  # muat model embedding sekarang (14 detik ada di sini)
    print("✅ [startup] Semua siap. Server mulai menerima request.")

    yield  # ← SERVER JALAN DI TITIK INI (bisa lama sekali)

    # ── FASE SHUTDOWN ───────────────────────────────────
    # Dijalankan saat Ctrl+C ditekan. Berguna untuk menutup
    # koneksi database, membuang file sementara, dsb.
    print("👋 [shutdown] Server berhenti. Sampai jumpa.")


app = FastAPI(
    title="RagApp-FastAPI",
    description="Latihan: membungkus mesin RAG yang sudah ada jadi layanan HTTP.",
    version="0.1.0",
    lifespan=lifespan,  # ← daftarkan lifespan ke aplikasi
)


# =====================================================
# CORS MIDDLEWARE
# =====================================================
# CORS (Cross-Origin Resource Sharing) memperbolehkan
# frontend di origin lain (misal localhost:3000 atau
# file://) untuk memanggil API kita.
# Tanpa ini, browser akan memblokir request dari frontend
# yang domain-nya beda dengan server API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # izinkan semua origin (untuk development)
    allow_credentials=True,
    allow_methods=["*"],       # izinkan semua method (GET, POST, dll)
    allow_headers=["*"],       # izinkan semua header
)


# =====================================================
# 3. ENDPOINT
# =====================================================
# @app.get / @app.post disebut DECORATOR. Fungsinya mendaftarkan
# fungsi Python biasa sebagai "pintu" yang bisa diketik di browser.
#
#   @app.post("/ask")  ->  POST http://127.0.0.1:8000/ask
#
# Tanpa decorator ini, fungsi tanya() di bawah tidak akan
# pernah dipanggil lewat HTTP — dia cuma fungsi Python biasa.

@app.get("/health")
def health():
    """Cek server hidup. Endpoint paling sederhana — tidak ada input."""
    return {"status": "ok", "layanan": "RagApp-FastAPI"}


@app.post("/ask", response_model=TanyaResponse)
def tanya(req: TanyaRequest):
    """Terima pertanyaan lewat HTTP, balas JSON.

    PERHATIKAN: isi fungsi ini hanya SATU BARIS panggilan ask().
    Semua logika RAG (deteksi sapaan, retrieve, pilih mode,
    panggil Ollama) tetap tinggal di generate.py.

    FastAPI tidak mengambil alih pekerjaan itu. Dia cuma
    menyediakan pintunya.
    """
    # req.pertanyaan sudah DIJAMIN ada & berupa teks oleh Pydantic.
    # Kita tinggal teruskan ke fungsi yang sudah kamu tulis.
    hasil = ask(req.pertanyaan, top_k=req.top_k)

    # FastAPI otomatis mengubah dict ini jadi JSON:
    # {"jawaban": "...", "mode": "rag", "sumber": [...], "skor_tertinggi": 0.52}
    return hasil


# =====================================================
# 4. ENDPOINT /ingest — Upload PDF & masukkan ke DB
# =====================================================
# Endpoint ini menerima file PDF, memecahnya jadi chunk,
# membuat embedding, lalu menyimpan ke PostgreSQL.
# Ini melengkapi alur: upload PDF -> tanya -> dapat jawaban.

@app.post("/ingest")
async def ingest_pdf(file: UploadFile = File(...)):
    """Upload file PDF, pecah jadi chunk, simpan ke database.

    Proses:
    1. Terima file PDF dari client
    2. Ekstrak teks dari setiap halaman (pakai PyMuPDF/fitz)
    3. Pecah jadi chunk per paragraf
    4. Buat embedding untuk setiap chunk
    5. Simpan ke tabel documents di PostgreSQL
    """
    # --- Validasi: pastikan file berupa PDF ---
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="File harus berformat PDF (.pdf)"
        )

    # --- Simpan file sementara ---
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        # --- Ekstrak teks dari PDF pakai PyMuPDF ---
        import fitz  # PyMuPDF

        doc = fitz.open(tmp_path)
        chunks = []
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text("text").strip()
            if not text:
                continue
            # Pecah per paragraf (baris kosong jadi pemisah)
            paragraf_list = [p.strip() for p in text.split("\n\n") if p.strip()]
            for i, paragraf in enumerate(paragraf_list):
                if len(paragraf) > 20:  # skip paragraf terlalu pendek
                    chunks.append({
                        "text": paragraf,
                        "source": file.filename,
                        "metadata": {
                            "page": page_num + 1,
                            "chunk_id": f"p{page_num+1}_c{i+1}",
                        },
                    })
        doc.close()

        if not chunks:
            raise HTTPException(
                status_code=400,
                detail="Tidak ada teks yang bisa diekstrak dari PDF ini."
            )

        # --- Buat embedding & simpan ke database ---
        from retrieve import dapatkan_model_embed, DB_CONFIG
        import psycopg2

        model = dapatkan_model_embed()
        texts_to_embed = [c["text"] for c in chunks]
        embeddings = model.encode(texts_to_embed, normalize_embeddings=True)

        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()

        inserted = 0
        for chunk, emb in zip(chunks, embeddings):
            emb_str = json.dumps(emb.tolist())
            cur.execute(
                """
                INSERT INTO documents (text, source, metadata, embedding)
                VALUES (%s, %s, %s, %s::vector)
                """,
                (chunk["text"], chunk["source"], json.dumps(chunk["metadata"]), emb_str),
            )
            inserted += 1

        conn.commit()
        cur.close()
        conn.close()

        return {
            "status": "ok",
            "file": file.filename,
            "chunks_ditambahkan": inserted,
            "pesan": f"Berhasil memproses {inserted} chunk dari '{file.filename}'.",
        }

    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="PyMuPDF (fitz) belum terinstall. Jalankan: pip install PyMuPDF"
        )
    except HTTPException:
        raise  # lempar ulang HTTPException apa adanya
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Gagal memproses PDF: {str(e)}"
        )
    finally:
        # --- Hapus file sementara ---
        os.unlink(tmp_path)


# =====================================================
# 5. SERVE FRONTEND (opsional)
# =====================================================
# Jika folder frontend/ ada, kita serve index.html-nya
# supaya user bisa langsung buka http://localhost:8000

@app.get("/", include_in_schema=False)
def serve_frontend():
    """Serve halaman chat frontend jika tersedia."""
    frontend_path = ROOT / "frontend" / "index.html"
    if frontend_path.exists():
        return FileResponse(frontend_path, media_type="text/html")
    return JSONResponse(
        {"pesan": "Frontend tidak ditemukan. Buka /docs untuk uji API."},
        status_code=200,
    )