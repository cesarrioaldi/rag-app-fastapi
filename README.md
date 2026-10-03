# rag-app-fastapi

Project **latihan** untuk belajar FastAPI. Punya database sendiri
(`ragapp_fastapi`) dan kode sendiri — berdiri sendiri, tanpa bergantung
project lain.

## Kenapa project terpisah?

Supaya kamu bisa bereksperimen bebas. Kalau ada yang salah, hapus saja
folder ini — tidak ada yang lain yang kena.

## Apa yang dipelajari?

Membungkus mesin RAG yang **sudah kamu punya** menjadi layanan HTTP.

```
chat.py   :  input() dari terminal  ->  ask()  ->  print()      (cara lama)
main.py   :  POST dari browser      ->  ask()  ->  JSON balik   (cara baru)
             └── FUNGSI ask()-nya SAMA PERSIS ──┘
```

FastAPI **tidak** menggantikan retrieve.py atau generate.py.
Dia hanya pintu masuk supaya aplikasi lain (React, app HP, Postman)
bisa memanggil fungsi Python-mu tanpa perlu install Python.

---

## Langkah menjalankan

Jalankan perintah di bawah **satu per satu** di terminalmu.
Pastikan venv bersama diaktifkan dulu di setiap jendela terminal baru.

### Langkah 0 — Aktifkan venv

```bash
source /Users/macbook/project/kerja/.venv/bin/activate
```

### Langkah 1 — Install fastapi & uvicorn

```bash
cd /Users/macbook/project/kerja/01-portofolio/rag-app-fastapi
pip install fastapi "uvicorn[standard]" pydantic
```

Cek berhasil:

```bash
python -c "import fastapi, uvicorn; print('fastapi', fastapi.__version__)"
```

### Langkah 2 — Buat file .env

```bash
cp .env.example .env
```

Isinya sudah benar (DB_NAME=ragapp_fastapi). Tidak perlu diubah.

### Langkah 3 — Buat database baru

```bash
createdb ragapp_fastapi
psql -d ragapp_fastapi -f schema.sql
```

### Langkah 4 — Isi database

Database `ragapp_fastapi` punya isinya sendiri (diisi manual, bukan
hasil salinan). Proyek ini tidak menyimpan file PDF/teks apa pun di
folder-nya; datanya hidup di PostgreSQL.

Cara mengisi (manual):

```bash
psql -d ragapp_fastapi
```

lalu `INSERT` baris-baris `documents` milikmu (kolom: `text`, `source`, `embedding`).

Belum ada data? Tidak apa-apa untuk latihan. `retrieve.py` akan bilang
"Database KOSONG". Fitur upload PDF lewat HTTP (`/ingest`) masih rencana —
lihat bagian akhir README.

### Langkah 5 — Test retrieve.py masih jalan

```bash
python src/retrieve.py "bagaimana prosedur audit internal?"
```

Ini membuktikan: pindah database tidak mengubah cara kerja retrieval.

### Langkah 6 — Test generate.py masih jalan

```bash
python src/generate.py "bagaimana prosedur audit internal?"
```

Pastikan Ollama hidup dulu. Kalau belum: `ollama serve`

### Langkah 7 — INI YANG BARU: jalankan FastAPI

```bash
uvicorn src.main:app --reload
```

Yang muncul di terminal:

```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Application startup complete.
```

**Server ini sekarang hidup.** Jangan tutup terminal ini.
Buka terminal **baru** untuk perintah berikutnya.

### Langkah 8 — Panggil lewat HTTP

Buka di browser:

- http://127.0.0.1:8000/docs — halaman uji otomatis (coba tombol "Try it out")
- http://127.0.0.1:8000/health — cek server hidup

Atau dari terminal baru:

```bash
curl http://127.0.0.1:8000/health

curl -X POST http://127.0.0.1:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"pertanyaan": "bagaimana prosedur audit internal keuangan?"}'
```

### Langkah 9 — Hentikan server

Kembali ke terminal yang menjalankan uvicorn, tekan **Ctrl+C**.

---

## Apa yang harus kamu perhatikan saat belajar

Bandingkan tiga hal ini, dan tanyakan ke dirimu sendiri:

1. **SQL di retrieve.py** — apakah berubah? (Jawaban: tidak, sama persis)
2. **Isi ask() di generate.py** — apakah berubah? (Jawaban: tidak, sama persis)
3. **Bagaimana kamu memanggilnya** — apakah berubah? (Jawaban: ya, dari `input()` jadi HTTP)

Kalau ketiganya kamu pahami, kamu sudah paham apa itu FastAPI.

## Struktur file

```
rag-app-fastapi/
├── .env.example        # template konfigurasi
├── requirements.txt    # daftar dependency
├── schema.sql          # struktur tabel (hanya untuk ragapp_fastapi)
├── README.md           # file ini
└── src/
    ├── retrieve.py     # mesin retrieval (SQL + embedding)
    ├── generate.py     # penyusun jawaban
    └── main.py         # BARU — ini file FastAPI-nya
```

## Rencana sesi berikutnya

Sesi ini baru `/health` dan `/ask`. Berikutnya bisa ditambah satu per satu:

- `/stats` — berapa chunk di database
- `/ingest` — upload PDF lewat HTTP (pakai pdf_pipeline.py)
- `frontend/index.html` — halaman chat sederhana di browser
- Docker — bungkus supaya bisa dijalankan di server lain
