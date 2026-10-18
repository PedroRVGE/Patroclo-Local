"""Pruebas de /health sin depender de Postgres ni de Ollama (se simulan)."""

import pytest
from fastapi.testclient import TestClient

from controllers import health


@pytest.fixture
def cliente(monkeypatch):
    monkeypatch.setenv("POSTGRES_PASSWORD", "prueba")
    from app.main import app

    return TestClient(app, raise_server_exceptions=False)


def _modelos(chat=True, embeddings=True):
    return {
        "chat": {"modelo": "qwen3.5:4b", "instalado": chat},
        "embeddings": {"modelo": "bge-m3", "instalado": embeddings},
    }


def test_todo_ok(cliente, monkeypatch):
    monkeypatch.setattr(health, "verificar_base_datos", lambda: {"pgvector": "0.8.0"})
    monkeypatch.setattr(health, "verificar_modelo_local", lambda: _modelos())
    r = cliente.get("/health")
    assert r.status_code == 200
    assert r.json()["estado"] == "ok"


def test_base_caida_devuelve_503_sin_detalles(cliente, monkeypatch):
    def falla():
        raise RuntimeError("password authentication failed for user patroclo")

    monkeypatch.setattr(health, "verificar_base_datos", falla)
    monkeypatch.setattr(health, "verificar_modelo_local", lambda: _modelos())
    r = cliente.get("/health")
    assert r.status_code == 503
    assert r.json()["base_datos"] == {"estado": "error"}
    assert "password" not in r.text  # el error interno no se filtra


def test_falta_modelo_de_embeddings(cliente, monkeypatch):
    monkeypatch.setattr(health, "verificar_base_datos", lambda: {"pgvector": "0.8.0"})
    monkeypatch.setattr(health, "verificar_modelo_local", lambda: _modelos(embeddings=False))
    r = cliente.get("/health")
    assert r.status_code == 503
    assert r.json()["modelo_local"]["estado"] == "incompleto"
