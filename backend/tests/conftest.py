"""Configuración común de las pruebas.

Las pruebas de la API usan SQLite en memoria en lugar de Postgres: son rápidas y no
necesitan Docker. Las tablas de usuario y token solo usan tipos genéricos, así que se
comportan igual. (Las pruebas de vectores, más adelante, sí necesitarán Postgres.)
"""

import os

# Antes de importar la app: valores de prueba que mandan sobre el .env real.
os.environ["POSTGRES_PASSWORD"] = "prueba"
os.environ["JWT_SECRETO"] = "secreto-de-pruebas-con-mas-de-32-caracteres"
os.environ["JWT_HORAS"] = "8"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import obtener_configuracion
from app.main import app
from db.conexion import obtener_sesion
from db.modelos import Base
from vectorstore.almacen import obtener_almacen


class AlmacenFalso:
    """Reemplaza a PGVector en las pruebas: guarda los fragmentos en un diccionario.

    `falla_con` simula que Ollama no responde al calcular los embeddings.
    """

    def __init__(self):
        self.fragmentos: dict = {}
        self.falla_con: Exception | None = None

    def add_documents(self, documents, ids):
        if self.falla_con:
            raise self.falla_con
        self.fragmentos.update(zip(ids, documents))
        return ids

    def delete(self, ids):
        for i in ids:
            self.fragmentos.pop(i, None)


@pytest.fixture
def almacen():
    return AlmacenFalso()


@pytest.fixture
def cliente(almacen, tmp_path, monkeypatch):
    # StaticPool: una sola conexión compartida, si no cada conexión vería su propia
    # base en memoria vacía.
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    fabrica = sessionmaker(bind=engine, expire_on_commit=False)

    def sesion_de_prueba():
        with fabrica() as sesion:
            yield sesion

    # Los archivos subidos van a una carpeta temporal de la prueba.
    monkeypatch.setattr(obtener_configuracion(), "subidas_dir", str(tmp_path / "subidas"))
    app.dependency_overrides[obtener_sesion] = sesion_de_prueba
    app.dependency_overrides[obtener_almacen] = lambda: almacen
    # Sin `with`: no corre el lifespan, así que no intenta conectarse a Postgres.
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()
    engine.dispose()


@pytest.fixture
def registrar(cliente):
    """Registra un usuario y devuelve (datos, respuesta JSON)."""

    def _registrar(correo="ana@ejemplo.com", nombre="Ana", contrasena="queso-de-cabra-1"):
        datos = {"correo": correo, "nombre": nombre, "contrasena": contrasena}
        r = cliente.post("/api/auth/registro", json=datos)
        assert r.status_code == 201, r.text
        return datos, r.json()

    return _registrar


def cabecera(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
