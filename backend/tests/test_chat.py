"""Pruebas de /api/chat y /api/conversaciones.

Usan el grafo de verdad con el modelo y la base vectorial falsos de test_grafo.py: se
prueba todo el camino API → grafo → guardar en la base, sin Ollama.
"""

import uuid

import pytest
from langchain_core.messages import AIMessage

from agents import prompts
from agents.grafo import construir_grafo
from agents.nodos import NodosPatroclo
from app.main import app
from services.chat import obtener_grafo
from tests.conftest import cabecera
from tests.test_grafo import AlmacenFalso, LLMFalso


class LLMCaido:
    def invoke(self, mensajes):
        raise ConnectionError("Failed to connect to Ollama")


@pytest.fixture
def llm():
    return LLMFalso()


@pytest.fixture
def grafo(cliente, llm):
    """Se instala después de `cliente` para que no lo borre su limpieza."""
    nodos = NodosPatroclo(llm, llm, AlmacenFalso(), umbral_distancia=0.5)
    app.dependency_overrides[obtener_grafo] = lambda: construir_grafo(nodos)
    return llm


def _preguntar(cliente, token, pregunta, conversacion_id=None):
    cuerpo = {"pregunta": pregunta}
    if conversacion_id:
        cuerpo["conversacion_id"] = conversacion_id
    return cliente.post("/api/chat", headers=cabecera(token), json=cuerpo)


def test_pregunta_nueva_abre_conversacion_y_responde_con_fuentes(cliente, registrar, grafo):
    _, ana = registrar()
    r = _preguntar(cliente, ana["token"], "¿Qué es el queso ibérico?")
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["respuesta"] == "El ibérico es madurado [1]."
    assert cuerpo["rechazada"] is False
    assert cuerpo["fuentes"][0]["documento"] == "El queso ibérico de cabra"
    assert cuerpo["fuentes"][0]["fragmento"]
    assert [p["nodo"] for p in cuerpo["pasos"]][-1] == "guardar_historial"
    assert cuerpo["tiempo_ms"] >= 0
    assert cuerpo["con_historial"] is False
    uuid.UUID(cuerpo["conversacion_id"])


def test_la_interaccion_queda_guardada(cliente, registrar, grafo):
    _, ana = registrar()
    conv = _preguntar(cliente, ana["token"], "¿Qué es el queso ibérico?").json()["conversacion_id"]

    lista = cliente.get("/api/conversaciones", headers=cabecera(ana["token"])).json()
    assert len(lista) == 1
    assert lista[0]["titulo"] == "¿Qué es el queso ibérico?"
    assert lista[0]["mensajes"] == 2

    detalle = cliente.get(f"/api/conversaciones/{conv}", headers=cabecera(ana["token"])).json()
    usuario, asistente = detalle["mensajes"]
    assert (usuario["rol"], usuario["contenido"]) == ("usuario", "¿Qué es el queso ibérico?")
    assert asistente["rol"] == "asistente"
    assert asistente["fuentes"][0]["archivo"] == "06-queso-iberico-de-cabra.md"
    assert asistente["pasos"][-1]["nodo"] == "guardar_historial"
    assert asistente["tiempo_ms"] is not None


def test_el_seguimiento_usa_el_historial(cliente, registrar, grafo):
    _, ana = registrar()
    conv = _preguntar(cliente, ana["token"], "¿Qué es el queso ibérico?").json()["conversacion_id"]
    assert "reformular" not in grafo.llamadas  # la primera no tiene historial

    r = _preguntar(cliente, ana["token"], "¿Y con qué lo sirvo?", conv).json()
    assert r["con_historial"] is True
    assert r["conversacion_id"] == conv
    assert "reformular" in grafo.llamadas
    assert cliente.get("/api/conversaciones", headers=cabecera(ana["token"])).json()[0]["mensajes"] == 4


def test_rechazo_tambien_se_guarda(cliente, registrar):
    _, ana = registrar()
    nodos = NodosPatroclo(LLMFalso(clasificacion="FUERA_DE_DOMINIO"), LLMFalso(), AlmacenFalso(), 0.5)
    app.dependency_overrides[obtener_grafo] = lambda: construir_grafo(nodos)

    r = _preguntar(cliente, ana["token"], "¿Quién ganó el Mundial?").json()
    assert r["rechazada"] is True
    assert r["respuesta"] == prompts.MENSAJE_RECHAZO
    detalle = cliente.get(f"/api/conversaciones/{r['conversacion_id']}", headers=cabecera(ana["token"])).json()
    assert detalle["mensajes"][1]["rechazada"] is True


def test_modelo_caido_da_503_y_no_guarda_nada(cliente, registrar):
    _, ana = registrar()
    nodos = NodosPatroclo(LLMCaido(), LLMCaido(), AlmacenFalso(), 0.5)
    app.dependency_overrides[obtener_grafo] = lambda: construir_grafo(nodos)

    r = _preguntar(cliente, ana["token"], "¿Qué es el queso ibérico?")
    assert r.status_code == 503
    assert "modelo local no está disponible" in r.json()["detalle"]
    assert cliente.get("/api/conversaciones", headers=cabecera(ana["token"])).json() == []


def test_no_se_puede_usar_ni_ver_la_conversacion_de_otro(cliente, registrar, grafo):
    _, ana = registrar()
    _, beto = registrar(correo="beto@ejemplo.com", nombre="Beto")
    conv = _preguntar(cliente, ana["token"], "¿Qué es el queso ibérico?").json()["conversacion_id"]

    assert _preguntar(cliente, beto["token"], "¿Y con qué lo sirvo?", conv).status_code == 404
    assert cliente.get(f"/api/conversaciones/{conv}", headers=cabecera(beto["token"])).status_code == 404
    assert cliente.delete(f"/api/conversaciones/{conv}", headers=cabecera(beto["token"])).status_code == 404
    assert cliente.get("/api/conversaciones", headers=cabecera(beto["token"])).json() == []


def test_borrar_conversacion_con_sus_mensajes(cliente, registrar, grafo):
    _, ana = registrar()
    conv = _preguntar(cliente, ana["token"], "¿Qué es el queso ibérico?").json()["conversacion_id"]
    assert cliente.delete(f"/api/conversaciones/{conv}", headers=cabecera(ana["token"])).status_code == 204
    assert cliente.get("/api/conversaciones", headers=cabecera(ana["token"])).json() == []
    assert cliente.get(f"/api/conversaciones/{conv}", headers=cabecera(ana["token"])).status_code == 404


def test_conversacion_inexistente(cliente, registrar, grafo):
    _, ana = registrar()
    assert _preguntar(cliente, ana["token"], "hola", str(uuid.uuid4())).status_code == 404


def test_validacion_de_la_pregunta(cliente, registrar, grafo):
    _, ana = registrar()
    assert _preguntar(cliente, ana["token"], "   ").status_code == 422
    assert _preguntar(cliente, ana["token"], "x" * 1001).status_code == 422
    assert cliente.post("/api/chat", headers=cabecera(ana["token"]), json={}).status_code == 422


def test_titulo_largo_se_recorta(cliente, registrar, grafo):
    _, ana = registrar()
    _preguntar(cliente, ana["token"], "¿Qué es el queso ibérico " + "y " * 60 + "?")
    titulo = cliente.get("/api/conversaciones", headers=cabecera(ana["token"])).json()[0]["titulo"]
    assert len(titulo) <= 80 and titulo.endswith("…")
