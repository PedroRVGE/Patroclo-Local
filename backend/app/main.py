"""Punto de entrada de la API de Patroclo-Local.

Ejecutar (desde backend/):  uv run uvicorn app.main:app --reload
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import obtener_configuracion
from app.errores import registrar_manejadores
from controllers import health

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

cfg = obtener_configuracion()

app = FastAPI(
    title="Patroclo-Local",
    description="Agente experto en lácteos de cabra (Del Pastor) — LangGraph + Ollama + pgvector",
    version="0.1.0",
)

# CORS solo para el origen del frontend, nunca '*'. El token viaja en la cabecera
# Authorization (no en cookies), así que no hace falta allow_credentials.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[cfg.origen_frontend],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

registrar_manejadores(app)

app.include_router(health.router)
