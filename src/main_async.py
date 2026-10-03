# =====================================================
# rag-app-fastapi — main_async.py
# VERSI ASYNC dari main.py (file asli tidak diubah).
# =====================================================
# Bandingkan dengan main.py:
#
#   main.py        →  from generate import ask
#                     def tanya(req):  hasil = ask(...)
#
#   main_async.py  →  from generate_async import ask_async
#                     async def tanya(req):  hasil = await ask_async(...)
#
# Bedanya: `async def` + `await`. Dua kata itu yang membuat
# server bisa melayani request lain sementara menunggu Ollama.
#
# Cara menjalankan (jalankan SENDIRI di terminal):
#   cd /Users/macbook/project/kerja/01-portofolio/rag-app-fastapi
#   /Users/macbook/project/kerja/.venv/bin/uvicorn src.main_async:app --port 8001
#
# Kenapa port 8001? Supaya kamu bisa menjalankan main.py (8000)
# dan main_async.py (8001) BERDAMPINGAN, lalu membandingkan
# perilakunya pada dua terminal berbeda. Itu inti latihannya.
# =====================================================

import sys
from contextlib import asynccontextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from fastapi import FastAPI
from pydantic import BaseModel, Field

# ← bedanya di sini: impor versi async-nya
from generate_async import ask_async
from retrieve import siapkan_model


# =====================================================
# 1. SKEMA REQUEST & RESPONSE (sama seperti main.py)
# =====================================================
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
# 2. APLIKASI (+ lifespan, sama seperti main.py)
# =====================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 [startup] Menyiapkan layanan (versi ASYNC) ...")
    siapkan_model()
    print("✅ [startup] Semua siap. Server ASYNC mulai menerima request.")

    yield

    print("👋 [shutdown] Server ASYNC berhenti.")


app = FastAPI(
    title="RagApp-FastAPI (ASYNC)",
    description="Versi async: server tidak berhenti saat menunggu Ollama.",
    version="0.2.0",
    lifespan=lifespan,
)


# =====================================================
# 3. ENDPOINT
# =====================================================
@app.get("/health")
def health():
    """Cek server hidup."""
    return {"status": "ok", "layanan": "RagApp-FastAPI (ASYNC)"}


# ← PERHATIKAN: `async def` dan `await`.
# Dua kata inilah seluruh perbedaan versi ini.
@app.post("/ask", response_model=TanyaResponse)
async def tanya(req: TanyaRequest):
    """Terima pertanyaan lewat HTTP, balas JSON — tanpa memblokir server."""
    # `await` artinya: tunggu ask_async selesai, TAPI serahkan
    # kendali ke FastAPI dulu supaya dia bisa melayani request lain.
    hasil = await ask_async(req.pertanyaan, top_k=req.top_k)
    return hasil
