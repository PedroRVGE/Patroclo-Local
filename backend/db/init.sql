-- Se ejecuta una sola vez, cuando el volumen de Postgres está vacío.
-- Las tablas las crea el backend; aquí solo se habilita pgvector.
CREATE EXTENSION IF NOT EXISTS vector;
