"""Conexión a PostgreSQL.

Un solo engine de SQLAlchemy para toda la aplicación (maneja el pool de conexiones).
langchain-postgres también usa SQLAlchemy + psycopg 3, así que es la misma pila.
"""

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import obtener_configuracion


@lru_cache
def obtener_engine() -> Engine:
    cfg = obtener_configuracion()
    return create_engine(
        cfg.url_base_datos,
        pool_pre_ping=True,  # descarta conexiones muertas (p. ej. si Postgres se reinició)
        connect_args={"connect_timeout": 5},
    )


@lru_cache
def _fabrica_sesiones() -> sessionmaker[Session]:
    return sessionmaker(bind=obtener_engine(), expire_on_commit=False)


def nueva_sesion() -> Session:
    """Sesión para scripts fuera de una petición (semilla, evaluación). Usar con `with`."""
    return _fabrica_sesiones()()


def obtener_sesion() -> Iterator[Session]:
    """Dependencia de FastAPI: una sesión por petición, cerrada siempre al final."""
    with nueva_sesion() as sesion:
        yield sesion


def crear_tablas() -> None:
    """Crea las tablas que falten (idempotente). Se llama al arrancar la API."""
    from db.modelos import Base

    Base.metadata.create_all(obtener_engine())


def verificar_base_datos() -> dict:
    """Comprueba que la base responde y que la extensión pgvector está instalada."""
    with obtener_engine().connect() as conexion:
        conexion.execute(text("SELECT 1"))
        pgvector = conexion.execute(
            text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        ).scalar()
    return {"pgvector": pgvector}
