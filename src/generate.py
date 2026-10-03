# =====================================================
# rag-app-fastapi — generate.py
# Otak chat: putuskan mode jawaban & panggil model qwen
# =====================================================
# DISALIN dari rag-app/src/generate.py, TIDAK diubah logikanya.
#
# Poin penting untuk pelajaran hari ini:
#   ask() di bawah ini adalah FUNGSI PYTHON BIASA.
#   Dia tidak tahu apa-apa soal HTTP, FastAPI, atau JSON.
#   Dia menerima string, mengembalikan dict.
#
#   main.py nanti cuma membungkus fungsi ini supaya bisa
#   dipanggil lewat http://localhost:8000/ask
#
#   Itulah seluruh "pekerjaan" FastAPI di project ini.
# =====================================================

import os
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from retrieve import search

# --- Ambang skor: di atas ini = dianggap pertanyaan soal dokumen ---------
AMBANG_SKOR = float(os.getenv("AMBANG_SKOR"))

# --- Konfigurasi Ollama (model chat lokal) --------------------------------
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL")

# =====================================================
# 1. DETEKSI SAPAAN
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
# 2. PEMANGGILAN OLLAMA
# =====================================================
def _panggil_ollama(system: str, prompt: str, suhu: float = 0.3) -> str | None:
    """Kirim prompt ke Ollama, balas teksnya (None kalau gagal)."""
    try:
        resp = requests.post(
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
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json().get("response", "").strip()
    except Exception as e:
        print(f"  ⚠ Gagal hubungi Ollama: {e}")
        return None


# =====================================================
# 3. PENYUSUN PROMPT
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
# 4. PINTU GERBANG UTAMA — ask()
# =====================================================
# >>> FUNGSI INI YANG AKAN DIBUNGKUS OLEH FASTAPI <<<
def ask(pertanyaan: str, top_k: int = 3) -> dict:
    """Jawab pertanyaan: RAG kalau nyambung, umum kalau tidak.

    Hasil: {"jawaban": str, "mode": "sapaan"|"umum"|"rag",
            "sumber": [nama file], "skor_tertinggi": float}
    """
    # --- Lapis 1: sapaan ---
    if _deteksi_sapaan(pertanyaan):
        system = (
            "Kamu adalah asisten AI yang ramah dan membantu, khususnya "
            "untuk dokumen internal perusahaan (SOP, kebijakan, prosedur). "
            "Jawab dalam Bahasa Indonesia secara natural dan hangat. "
            "Kamu TIDAK punya akses ke dokumen apa pun saat ini."
        )
        jawaban = _panggil_ollama(system, pertanyaan, suhu=0.7)
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

    # --- Lapis 2: cari chunk paling mirip ---
    chunks = search(pertanyaan, top_k=top_k)
    skor_tertinggi = chunks[0]["skor"] if chunks else 0.0

    # --- Lapis 3: putuskan mode ---
    if chunks and skor_tertinggi >= AMBANG_SKOR:
        system, prompt = _prompt_rag(pertanyaan, chunks)
        jawaban = _panggil_ollama(system, prompt, suhu=0.3)
        sumber = sorted({c["source"] for c in chunks if c["source"]})
        mode = "rag"
    else:
        system, prompt = _prompt_umum(pertanyaan)
        jawaban = _panggil_ollama(system, prompt, suhu=0.7)
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
def main():
    if len(sys.argv) < 2:
        print('Cara pakai: python src/generate.py "pertanyaan kamu"')
        sys.exit(1)
    pertanyaan = " ".join(sys.argv[1:])
    hasil = ask(pertanyaan)
    print(f"\n[{hasil['mode']}] {hasil['jawaban']}")
    if hasil["sumber"]:
        print("📎 Sumber:", ", ".join(hasil["sumber"]))


if __name__ == "__main__":
    main()
