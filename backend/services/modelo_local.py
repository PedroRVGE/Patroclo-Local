"""Comprobaciones sobre el servidor de Ollama (el contenedor `ollama-gpu`)."""

import httpx
import ollama

from app.config import obtener_configuracion

# Lo que lanza el cliente de Ollama (y por tanto OllamaEmbeddings/ChatOllama):
#   ConnectionError       → el servidor no responde
#   ollama.ResponseError  → responde pero falla (p. ej. el modelo no está descargado)
ERRORES_OLLAMA = (ConnectionError, ollama.ResponseError, httpx.HTTPError)


class ModeloNoDisponible(Exception):
    """El modelo local no responde. La API lo traduce a 503 con un mensaje claro."""


def modelos_instalados() -> list[str]:
    """Pregunta a Ollama qué modelos tiene descargados (GET /api/tags)."""
    cfg = obtener_configuracion()
    respuesta = httpx.get(f"{cfg.ollama_url}/api/tags", timeout=5)
    respuesta.raise_for_status()
    return [m["name"] for m in respuesta.json().get("models", [])]


def _instalado(modelo: str, instalados: list[str]) -> bool:
    # Ollama nombra 'bge-m3' como 'bge-m3:latest'.
    return modelo in instalados or f"{modelo}:latest" in instalados


def precalentar() -> None:
    """Carga los dos modelos en Ollama (una consulta mínima a cada uno).

    Se llama en segundo plano al arrancar la API: la primera pregunta real no paga los
    ~20 s de carga. Si falla (Ollama apagado), solo se registra.
    """
    import logging
    import time

    from agents.llm import crear_llm
    from vectorstore.almacen import obtener_embeddings

    log = logging.getLogger("patroclo.precalentar")
    inicio = time.perf_counter()
    try:
        obtener_embeddings().embed_query("queso de cabra")
        crear_llm(max_tokens=1).invoke("Hola")
        log.info("modelos cargados en Ollama en %.1f s", time.perf_counter() - inicio)
    except ERRORES_OLLAMA as e:
        log.warning("no se pudieron precalentar los modelos: %s", e)


def verificar_modelo_local() -> dict:
    """Dice si Ollama responde y si los dos modelos configurados están descargados."""
    cfg = obtener_configuracion()
    instalados = modelos_instalados()
    return {
        "chat": {"modelo": cfg.chat_model, "instalado": _instalado(cfg.chat_model, instalados)},
        "embeddings": {
            "modelo": cfg.embedding_model,
            "instalado": _instalado(cfg.embedding_model, instalados),
        },
    }
