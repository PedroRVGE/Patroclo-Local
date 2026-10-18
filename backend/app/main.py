"""Punto de entrada de la API de Patroclo-Local.

Ejecutar (desde backend/):  uv run uvicorn app.main:app --reload
"""

import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import obtener_configuracion
from app.errores import registrar_manejadores
from controllers import auth, chat, documentos, health, historial
from db.conexion import crear_tablas
from services.modelo_local import precalentar

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("patroclo")

cfg = obtener_configuracion()


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    # Si la base no está arriba, la API arranca igual: /health lo reporta y las rutas
    # que la necesitan responden 503 en vez de que el proceso muera.
    try:
        crear_tablas()
    except Exception:
        log.exception("No se pudieron crear las tablas al arrancar (¿Postgres está arriba?)")
    if cfg.precalentar_modelos:
        # En un hilo aparte: la API empieza a atender de una vez mientras los modelos cargan.
        threading.Thread(target=precalentar, name="precalentar", daemon=True).start()
    yield


app = FastAPI(
    title="Patroclo-Local",
    description="Agente experto en lácteos de cabra (Del Pastor) — LangGraph + Ollama + pgvector",
    version="0.1.0",
    lifespan=ciclo_de_vida,
    docs_url="/docs" if cfg.mostrar_docs else None,
    redoc_url=None,
    openapi_url="/openapi.json" if cfg.mostrar_docs else None,
)

# CORS solo para el origen del frontend, nunca '*'. El token viaja en la cabecera
# Authorization (no en cookies), así que no hace falta allow_credentials.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[cfg.origen_frontend],
    allow_methods=["GET", "POST", "DELETE"],
    # ngrok-skip-browser-warning: la manda el frontend para saltar el aviso de ngrok (paso 7).
    allow_headers=["Authorization", "Content-Type", "ngrok-skip-browser-warning"],
)

registrar_manejadores(app)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(documentos.router)
app.include_router(chat.router)
app.include_router(historial.router)
