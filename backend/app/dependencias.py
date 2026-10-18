"""Dependencias de autenticación que usan los controladores.

Toda ruta que no sea /health, registro o ingreso declara `usuario_actual` (o
`sesion_actual`). La prueba tests/test_rutas_protegidas.py recorre todas las rutas de la
app y falla si alguna nueva se olvidó de hacerlo.
"""

import uuid
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from db.conexion import obtener_sesion
from db.modelos import Usuario
from services import tokens

# auto_error=False para responder nosotros con 401 (FastAPI por defecto da 403).
_bearer = HTTPBearer(auto_error=False, description="Token JWT obtenido en /api/auth/ingresar")

SesionBD = Annotated[Session, Depends(obtener_sesion)]


def _no_autorizado(detalle: str = "Sesión inválida o expirada. Vuelve a ingresar.") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detalle,
        headers={"WWW-Authenticate": "Bearer"},
    )


@dataclass
class SesionActiva:
    usuario: Usuario
    jti: str
    exp: int


def sesion_actual(
    sesion: SesionBD,
    credenciales: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> SesionActiva:
    """Valida el JWT de la cabecera Authorization: Bearer <token>."""
    if credenciales is None:
        raise _no_autorizado("Falta el token de sesión.")
    try:
        datos = tokens.decodificar(credenciales.credentials)
        usuario_id = uuid.UUID(datos["sub"])
    except (tokens.TokenInvalido, ValueError):
        raise _no_autorizado() from None

    if tokens.esta_revocado(sesion, datos["jti"]):
        raise _no_autorizado()
    usuario = sesion.get(Usuario, usuario_id)
    if usuario is None:  # el usuario fue borrado después de emitir el token
        raise _no_autorizado()
    return SesionActiva(usuario=usuario, jti=datos["jti"], exp=datos["exp"])


def usuario_actual(activa: Annotated[SesionActiva, Depends(sesion_actual)]) -> Usuario:
    return activa.usuario


UsuarioActual = Annotated[Usuario, Depends(usuario_actual)]
