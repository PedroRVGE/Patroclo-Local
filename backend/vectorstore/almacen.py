"""Base vectorial: PGVector (pgvector en el mismo Postgres) + embeddings de Ollama.

Por qué pgvector y no ChromaDB/FAISS: ya hay un Postgres para usuarios, documentos e
historial. Con pgvector todo vive en una sola base, con un solo respaldo, y el borrado de
un documento y de sus vectores ocurre en el mismo lugar.

PGVector guarda los fragmentos en dos tablas propias:
  langchain_pg_collection  (una fila por colección)
  langchain_pg_embedding   (una fila por fragmento: id, texto, vector, metadata JSONB)
"""

from functools import lru_cache

from langchain_ollama import OllamaEmbeddings
from langchain_postgres.vectorstores import PGVector

from app.config import obtener_configuracion
from db.conexion import obtener_engine


@lru_cache
def obtener_embeddings() -> OllamaEmbeddings:
    cfg = obtener_configuracion()
    return OllamaEmbeddings(model=cfg.embedding_model, base_url=cfg.ollama_url, keep_alive=cfg.ollama_keep_alive_s)


@lru_cache
def obtener_almacen() -> PGVector:
    """Una instancia para toda la app. Al crearla, PGVector crea sus tablas si faltan."""
    cfg = obtener_configuracion()
    return PGVector(
        embeddings=obtener_embeddings(),
        connection=obtener_engine(),  # reutiliza el pool de conexiones de la app
        collection_name=cfg.coleccion,
        use_jsonb=True,  # metadata en JSONB: permite filtrar (p. ej. visibilidad = publico)
        create_extension=False,  # la crea backend/db/init.sql
    )


def ids_de_fragmentos(documento_id, cantidad: int) -> list[str]:
    """Ids deterministas: el fragmento n del documento X es «X:n».

    Así, borrar un documento es borrar exactamente esos ids, y reindexarlo los reescribe
    en vez de duplicarlos (el error de referencias/agente, donde cada ingesta duplicaba).
    """
    return [f"{documento_id}:{n}" for n in range(cantidad)]
