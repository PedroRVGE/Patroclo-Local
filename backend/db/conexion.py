"""Conexión a PostgreSQL.

Un solo engine de SQLAlchemy para toda la aplicación (maneja el pool de conexiones).
langchain-postgres también usa SQLAlchemy + psycopg 3, así que es la misma pila.
"""

from functools import lru_cache

from sqlalchemy import Engine, create_engine, text

from app.config import obtener_configuracion


@lru_cache
def obtener_engine() -> Engine:
    cfg = obtener_configuracion()
    return create_engine(
        cfg.url_base_datos,
        pool_pre_ping=True,  # descarta conexiones muertas (p. ej. si Postgres se reinició)
        connect_args={"connect_timeout": 5},
    )


def verificar_base_datos() -> dict:
    """Comprueba que la base responde y que la extensión pgvector está instalada."""
    with obtener_engine().connect() as conexion:
        conexion.execute(text("SELECT 1"))
        pgvector = conexion.execute(
            text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        ).scalar()
    return {"pgvector": pgvector}
