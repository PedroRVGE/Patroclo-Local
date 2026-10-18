"""Comprobaciones sobre el servidor de Ollama (el contenedor `ollama-gpu`)."""

import httpx

from app.config import obtener_configuracion


def modelos_instalados() -> list[str]:
    """Pregunta a Ollama qué modelos tiene descargados (GET /api/tags)."""
    cfg = obtener_configuracion()
    respuesta = httpx.get(f"{cfg.ollama_url}/api/tags", timeout=5)
    respuesta.raise_for_status()
    return [m["name"] for m in respuesta.json().get("models", [])]


def _instalado(modelo: str, instalados: list[str]) -> bool:
    # Ollama nombra 'bge-m3' como 'bge-m3:latest'.
    return modelo in instalados or f"{modelo}:latest" in instalados


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
