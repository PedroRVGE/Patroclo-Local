"""GET /health — único endpoint público junto con registro e ingreso.

Sirve para saber, antes de la demo, si la API, la base y el modelo local están vivos.
No devuelve mensajes de error internos (podrían filtrar rutas o credenciales): solo
'ok' / 'error' por componente. El detalle queda en el log.
"""

import logging

from fastapi import APIRouter, Response, status

from db.conexion import verificar_base_datos
from services.modelo_local import verificar_modelo_local

log = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


@router.get("/health")
def health(response: Response) -> dict:
    componentes: dict = {}

    try:
        componentes["base_datos"] = {"estado": "ok", **verificar_base_datos()}
    except Exception:
        log.exception("health: la base de datos no responde")
        componentes["base_datos"] = {"estado": "error"}

    try:
        modelos = verificar_modelo_local()
        completo = modelos["chat"]["instalado"] and modelos["embeddings"]["instalado"]
        componentes["modelo_local"] = {"estado": "ok" if completo else "incompleto", **modelos}
    except Exception:
        log.exception("health: Ollama no responde")
        componentes["modelo_local"] = {"estado": "error"}

    sano = all(c["estado"] == "ok" for c in componentes.values())
    if not sano:
        # 503 para que un monitor (o el frontend) distinga "vivo" de "vivo pero cojo".
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"estado": "ok" if sano else "degradado", **componentes}
