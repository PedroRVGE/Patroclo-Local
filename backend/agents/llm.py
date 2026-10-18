"""Fábrica del modelo de chat. El resto del agente no sabe qué proveedor hay detrás.

Aquí solo existe Ollama (el enunciado exige un modelo local). `../Patroclo/` puede reusar
el grafo agregando otro proveedor en `crear_llm()`.
"""

import re

from langchain_core.language_models import BaseChatModel
from langchain_ollama import ChatOllama

from app.config import obtener_configuracion

_PENSAMIENTO = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def crear_llm(max_tokens: int) -> BaseChatModel:
    """`max_tokens` corto (≈10) para los nodos de decisión, largo para la respuesta."""
    cfg = obtener_configuracion()
    if cfg.llm_provider != "ollama":
        raise ValueError(f"Proveedor de modelo no soportado aquí: {cfg.llm_provider}")
    return ChatOllama(
        model=cfg.chat_model,
        base_url=cfg.ollama_url,
        # Los Qwen recientes «piensan» antes de responder (<think>…</think>): multiplica el
        # tiempo y ensucia las respuestas de una palabra. Se apaga.
        reasoning=False,
        temperature=cfg.temperatura,
        num_ctx=cfg.num_ctx,
        num_predict=max_tokens,
    )


def limpiar(texto: str) -> str:
    """Quita cualquier bloque <think> que se cuele y los espacios sobrantes."""
    return _PENSAMIENTO.sub("", texto or "").strip()
