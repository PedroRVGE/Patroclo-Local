"""Emisión, verificación y revocación de los JWT de sesión.

Contenido del token: `sub` (id del usuario), `jti` (id único del token, para poder
revocarlo), `iat` (emitido) y `exp` (expira). Firmado con HS256 y el secreto de .env.
"""

import uuid
from datetime import UTC, datetime, timedelta

import jwt
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.config import obtener_configuracion
from db.modelos import TokenRevocado

_ALGORITMO = "HS256"


class TokenInvalido(Exception):
    pass


def crear_token(usuario_id: uuid.UUID) -> tuple[str, datetime]:
    cfg = obtener_configuracion()
    ahora = datetime.now(UTC)
    expira = ahora + timedelta(hours=cfg.jwt_horas)
    datos = {"sub": str(usuario_id), "jti": uuid.uuid4().hex, "iat": ahora, "exp": expira}
    token = jwt.encode(datos, cfg.jwt_secreto.get_secret_value(), algorithm=_ALGORITMO)
    return token, expira


def decodificar(token: str) -> dict:
    """Verifica firma y expiración. Lanza TokenInvalido con cualquier problema."""
    cfg = obtener_configuracion()
    try:
        return jwt.decode(
            token,
            cfg.jwt_secreto.get_secret_value(),
            # Lista explícita: impide el ataque de cambiar el algoritmo a «none».
            algorithms=[_ALGORITMO],
            options={"require": ["sub", "jti", "exp", "iat"]},
        )
    except jwt.PyJWTError:
        raise TokenInvalido() from None


def esta_revocado(sesion: Session, jti: str) -> bool:
    return sesion.get(TokenRevocado, jti) is not None


def revocar(sesion: Session, jti: str, exp: int) -> None:
    """Guarda el jti hasta que el token expire y, de paso, limpia los ya vencidos."""
    ahora = datetime.now(UTC)
    sesion.execute(delete(TokenRevocado).where(TokenRevocado.expira_en < ahora))
    if not esta_revocado(sesion, jti):
        sesion.add(TokenRevocado(jti=jti, expira_en=datetime.fromtimestamp(exp, UTC)))
    sesion.commit()
