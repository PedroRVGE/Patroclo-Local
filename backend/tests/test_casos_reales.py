"""Los 20 casos de evaluacion/casos.json contra el modelo y la base REALES.

No corren con un `pytest` normal (tardan minutos y necesitan Postgres + Ollama arriba con
la semilla indexada y SIN la guía de vinos cargada). Se corren así, desde backend/:

    uv run pytest -m integracion

Comprueban, por caso: que respondió / rechazó / saludó según `debe`, y que los rechazos
usan el mensaje literal. La fuente esperada se avisa pero no hace fallar la prueba: la
base repite información entre archivos y una respuesta correcta puede citar otra fuente
válida (ver ESTADO.md, paso 4).
"""

import json
import warnings
from pathlib import Path

import pytest

pytestmark = pytest.mark.integracion

CASOS = json.loads((Path(__file__).resolve().parents[2] / "evaluacion" / "casos.json").read_text(encoding="utf-8"))["casos"]


@pytest.fixture(scope="module")
def grafo():
    import os

    # Con las credenciales del .env real (conftest.py pone unas de prueba).
    os.environ.pop("POSTGRES_PASSWORD", None)
    from app.config import obtener_configuracion
    from db.conexion import obtener_engine
    from vectorstore.almacen import obtener_almacen, obtener_embeddings

    for funcion in (obtener_configuracion, obtener_engine, obtener_almacen, obtener_embeddings):
        funcion.cache_clear()
    from agents.grafo import crear_grafo_real

    return crear_grafo_real()


@pytest.mark.parametrize("caso", CASOS, ids=[c["id"] for c in CASOS])
def test_caso(grafo, caso):
    from agents import prompts
    from app.evaluar import correr_caso

    r = correr_caso(grafo, caso)
    assert r["obtuvo"] == caso["debe"], f"{caso['id']}: se esperaba {caso['debe']}, obtuvo {r['obtuvo']}. Pasos: {r['pasos']}"
    if caso["debe"] == "rechazar":
        assert r["respuesta"] == prompts.MENSAJE_RECHAZO
    if r["fuente_ok"] is False:
        warnings.warn(f"{caso['id']}: la fuente esperada {caso['fuente_esperada']} no está entre {r['fuentes']}")
