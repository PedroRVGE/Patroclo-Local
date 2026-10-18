"""Manejo de errores no previstos.

Nunca se devuelve el traceback al cliente. Se registra completo en el log con un id
corto, y al cliente solo le llega ese id para poder buscar el error después.
"""

import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from services.modelo_local import ModeloNoDisponible

log = logging.getLogger("patroclo.errores")


def registrar_manejadores(app: FastAPI) -> None:
    @app.exception_handler(OperationalError)
    async def base_no_disponible(request: Request, exc: OperationalError) -> JSONResponse:
        id_error = uuid.uuid4().hex[:12]
        log.error("error %s: base de datos no disponible en %s %s", id_error, request.method, request.url.path)
        return JSONResponse(
            status_code=503,
            content={"detalle": "La base de datos no está disponible.", "id_error": id_error},
        )

    @app.exception_handler(ModeloNoDisponible)
    async def modelo_no_disponible(request: Request, exc: ModeloNoDisponible) -> JSONResponse:
        id_error = uuid.uuid4().hex[:12]
        log.error("error %s: modelo local no disponible en %s %s (%s)", id_error, request.method, request.url.path, exc)
        return JSONResponse(
            status_code=503,
            content={"detalle": "El modelo local no está disponible. Intenta de nuevo en un momento.", "id_error": id_error},
        )

    @app.exception_handler(Exception)
    async def error_no_previsto(request: Request, exc: Exception) -> JSONResponse:
        id_error = uuid.uuid4().hex[:12]
        log.exception("error %s en %s %s", id_error, request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detalle": "Ocurrió un error interno.", "id_error": id_error},
        )
