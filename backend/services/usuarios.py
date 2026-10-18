"""Registro y verificación de usuarios.

Contraseñas con argon2id (el ganador del Password Hashing Competition; es el modo por
defecto de argon2-cffi). El hash incluye su propia sal y sus parámetros, así que basta
una columna.
"""

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from db.modelos import Usuario

_hasher = PasswordHasher()

# Hash de una contraseña que nadie tiene. Se verifica contra él cuando el correo no
# existe, para que «correo inexistente» y «contraseña mala» tarden lo mismo y no se pueda
# averiguar qué correos están registrados midiendo el tiempo de respuesta.
_HASH_FALSO = _hasher.hash("contrasena-que-nadie-tiene")


class CorreoYaRegistrado(Exception):
    pass


class CredencialesInvalidas(Exception):
    pass


def normalizar_correo(correo: str) -> str:
    return correo.strip().lower()


def registrar(sesion: Session, correo: str, nombre: str, contrasena: str) -> Usuario:
    correo = normalizar_correo(correo)
    if sesion.scalar(select(Usuario.id).where(Usuario.correo == correo)):
        raise CorreoYaRegistrado(correo)

    usuario = Usuario(correo=correo, nombre=nombre.strip(), hash_contrasena=_hasher.hash(contrasena))
    sesion.add(usuario)
    try:
        sesion.commit()
    except IntegrityError:
        # Dos registros simultáneos con el mismo correo: la restricción UNIQUE decide.
        sesion.rollback()
        raise CorreoYaRegistrado(correo) from None
    return usuario


def autenticar(sesion: Session, correo: str, contrasena: str) -> Usuario:
    """Devuelve el usuario si correo y contraseña cuadran; si no, CredencialesInvalidas.

    No distingue entre «no existe» y «contraseña mala»: el mensaje es el mismo.
    """
    usuario = sesion.scalar(select(Usuario).where(Usuario.correo == normalizar_correo(correo)))
    try:
        _hasher.verify(usuario.hash_contrasena if usuario else _HASH_FALSO, contrasena)
    except (VerificationError, InvalidHashError):
        raise CredencialesInvalidas() from None
    if usuario is None:
        raise CredencialesInvalidas()

    # Si algún día se suben los parámetros de argon2, los hashes viejos se actualizan solos.
    if _hasher.check_needs_rehash(usuario.hash_contrasena):
        usuario.hash_contrasena = _hasher.hash(contrasena)
        sesion.commit()
    return usuario
