-- =====================================================
-- rag-app-fastapi — schema.sql
-- Database LATIHAN untuk belajar FastAPI.
-- =====================================================
-- PENTING: file ini HANYA menyentuh database "ragapp_fastapi".
-- Tidak ada DROP DATABASE di sini.
--
-- Cara pakai (jalankan SENDIRI di terminal):
--   createdb ragapp_fastapi
--   psql -d ragapp_fastapi -f schema.sql
-- =====================================================

-- Ekstensi pgvector (untuk kolom embedding)
CREATE EXTENSION IF NOT EXISTS vector;

-- Tabel dokumen.
CREATE TABLE IF NOT EXISTS documents (
    id         SERIAL PRIMARY KEY,
    text       TEXT NOT NULL,
    source     TEXT,
    metadata   JSONB,
    embedding  vector(384)          -- MiniLM-L6-v2 = 384 dimensi
);

-- Index untuk pencarian tetangga terdekat (cosine).
-- Tanpa ini, pencarian tetap jalan tapi lambat saat data besar.
CREATE INDEX IF NOT EXISTS documents_embedding_idx
    ON documents USING hnsw (embedding vector_cosine_ops);

-- Verifikasi
SELECT 'schema siap' AS status, COUNT(*) AS jumlah_chunk FROM documents;
