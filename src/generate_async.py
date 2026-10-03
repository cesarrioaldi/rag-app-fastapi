# =====================================================
# rag-app-fastapi — generate_async.py
# VERSI ASYNC dari generate.py (file asli tidak diubah).
# =====================================================
# Kenapa file ini ada:
#
#   generate.py        → _panggil_ollama() pakai requests (SINKRON)
#                        selama menunggu Ollama, seluruh server berhenti.
#
#   generate_async.py  → _panggil_ollama() pakai httpx (ASYNC)
#                        selama menunggu Ollama, server bisa melayani
#                        request lain.
#
# Perubahan dari generate.py hanya di DUA hal:
#   1. requests → httpx.AsyncClient
#   2. def → async def  (untuk fungsi yang memanggil Ollama)
#
# Semua logika RAG (deteksi sapaan, prompt, ambang skor) TETAP SAMA.
# =====================================================

import os
import sys
from pathlib import Path

import httpx  # ← GANTI dari requests (versi async-nya)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from retrieve import search

# --- Ambang skor ---------------------------------------------------------
AMBANG_SKOR = float(os.getenv("AMBANG_SKOR", "0.35"))

# --- Konfigurasi Ollama ---------------------------------------------------
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:1.5b")

# =====================================================
# 1. DETEKSI SAPAAN  (IDENTIK dengan generate.py)
# =====================================================
SAPAAN_PENUH = [
    "selamat pagi", "selamat siang", "selamat sore", "selamat malam",
    "terima kasih", "makasih", "terimakasih", "apa kabar",
    "kamu bisa apa", "bantuan", "tolong", "hai",
]
SAPAAN_KONTEKSTUAL = ["pagi", "siang", "sore", "malam", "halo", "hai", "assalamualaikum"]


def _deteksi_sapaan(teks: str) -> bool:
    """True kalau input cuma sapaan/obrolan basa-basi."""
    teks = teks.lower().strip()
    for frase in SAPAAN_PENUH:
        if frase in teks:
            return True
    kata = teks.split()
    if len(kata) <= 4:
        for k in SAPAAN_KONTEKSTUAL:
            if k in teks:
                return True
    else:
        if kata and kata[0].strip("?.,!") in SAPAAN_KONTEKSTUAL:
            return True
    return False


# =====================================================
# 2. PEMANGGILAN OLLAMA — VERSI ASYNC (INI BEDANYA)
# =====================================================
# Bandingkan dengan generate.py:
#
#   SINKRON (generate.py):
#       resp = requests.post(url, json=...)   ← server BERHENTI di sini
#
#   ASYNC (file ini):
#       async with httpx.AsyncClient() as client:
#           resp = await client.post(url, json=...)   ← server LANJUT kerja
#
# Kata kunci `await` berarti: "saya menunggu jawaban Ollama, tapi
# sementara itu event loop FastAPI boleh melayani request lain."
async def _panggil_ollama(system: str, prompt: str, suhu: float = 0.3) -> str | None:
    """Kirim prompt ke Ollama secara ASYNC, balas teksnya."""
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "system": system,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": suhu,
                        "num_predict": 400,
                    },
                },
            )
            resp.raise_for_status()
            return resp.json().get("response", "").strip()
    except Exception as e:
        print(f"  ⚠ Gagal hubungi Ollama: {e}")
        return None


# =====================================================
# 3. PENYUSUN PROMPT  (IDENTIK dengan generate.py)
# =====================================================
def _prompt_rag(pertanyaan: str, chunks: list) -> tuple[str, str]:
    """Susun system + prompt untuk mode RAG (anti-halusinasi)."""
    system = (
        "Kamu adalah asisten AI untuk dokumen internal perusahaan. "
        "Jawab dalam Bahasa Indonesia, singkat dan langsung. "
        "Jawab HANYA berdasarkan KONTEKS yang diberikan. "
        "Jangan mengarang atau menebak. "
        "Jika KONTEKS tidak memuat jawaban pertanyaan, jawab tepat: "
        "'Informasi ini tidak tersedia dalam sumber data saya.'"
    )
    bagian = []
    for i, c in enumerate(chunks, start=1):
        bagian.append(f"[{i}] (sumber: {c['source']})\n{c['text']}")
    konteks = "\n\n".join(bagian)
    prompt = (
        "KONTEKS (satu-satunya sumber jawabanmu):\n"
        f"{konteks}\n\n"
        f"PERTANYAAN: {pertanyaan}\n\n"
        "JAWABAN (langsung isi jawabannya, tanpa basa-basi):"
    )
    return system, prompt


def _prompt_umum(pertanyaan: str) -> tuple[str, str]:
    """Susun system + prompt untuk mode umum."""
    system = (
        "Kamu adalah asisten AI yang ramah dan membantu. "
        "Jawab dalam Bahasa Indonesia, natural dan informatif. "
        "Kamu TIDAK punya akses ke dokumen perusahaan mana pun; "
        "jawab dari pengetahuan umummu sendiri."
    )
    return system, pertanyaan


# =====================================================
# 4. PINTU GERBANG UTAMA — ask_async()
# =====================================================
# Perhatikan: search() di dalam sini MASIH SINKRON.
# Itu tidak masalah — mencari 12 chunk di database lokal
# hanya butuh milidetik, bukan detik seperti Ollama.
# Kita tidak perlu meng-async-kan yang tidak lambat.
async def ask_async(pertanyaan: str, top_k: int = 3) -> dict:
    """Versi ASYNC dari ask(). Logika sama, hanya bisa di-await."""
    # --- Lapis 1: sapaan ---
    if _deteksi_sapaan(pertanyaan):
        system = (
            "Kamu adalah asisten AI yang ramah dan membantu, khususnya "
            "untuk dokumen internal perusahaan (SOP, kebijakan, prosedur). "
            "Jawab dalam Bahasa Indonesia secara natural dan hangat. "
            "Kamu TIDAK punya akses ke dokumen apa pun saat ini."
        )
        jawaban = await _panggil_ollama(system, pertanyaan, suhu=0.7)
        if jawaban is None:
            jawaban = (
                "Kendala teknis menghubungi model bahasa (Ollama). "
                "Pastikan Ollama jalan:  curl http://localhost:11434/api/tags"
            )
        return {
            "jawaban": jawaban,
            "mode": "sapaan",
            "sumber": [],
            "skor_tertinggi": 0.0,
        }

    # --- Lapis 2: cari chunk (sinkron, tidak masalah — cepat) ---
    chunks = search(pertanyaan, top_k=top_k)
    skor_tertinggi = chunks[0]["skor"] if chunks else 0.0

    # --- Lapis 3: putuskan mode ---
    if chunks and skor_tertinggi >= AMBANG_SKOR:
        system, prompt = _prompt_rag(pertanyaan, chunks)
        jawaban = await _panggil_ollama(system, prompt, suhu=0.3)
        sumber = sorted({c["source"] for c in chunks if c["source"]})
        mode = "rag"
    else:
        system, prompt = _prompt_umum(pertanyaan)
        jawaban = await _panggil_ollama(system, prompt, suhu=0.7)
        sumber = []
        mode = "umum"

    if jawaban is None:
        jawaban = (
            "Kendala teknis menghubungi model bahasa (Ollama). "
            "Pastikan Ollama jalan:  curl http://localhost:11434/api/tags"
        )

    return {
        "jawaban": jawaban,
        "mode": mode,
        "sumber": sumber,
        "skor_tertinggi": skor_tertinggi,
    }


# =====================================================
# JALUR PERINTAH — test satu pertanyaan dari terminal
# =====================================================
# Karena ask_async() adalah async, terminal perlu asyncio.run()
# untuk menjalankannya. Ini seperti "membuka event loop sendiri"
# karena kita tidak sedang di dalam server FastAPI.
def main():
    import asyncio

    if len(sys.argv) < 2:
        print('Cara pakai: python src/generate_async.py "pertanyaan kamu"')
        sys.exit(1)
    pertanyaan = " ".join(sys.argv[1:])
    hasil = asyncio.run(ask_async(pertanyaan))
    print(f"\n[{hasil['mode']}] {hasil['jawaban']}")
    if hasil["sumber"]:
        print("📎 Sumber:", ", ".join(hasil["sumber"]))


if __name__ == "__main__":
    main()
