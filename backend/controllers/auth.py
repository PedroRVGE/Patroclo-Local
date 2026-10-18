"""Rutas de autenticación: registro, ingreso, yo, salir.

El controlador solo traduce HTTP ↔ servicios: valida la entrada (pydantic), llama a
services/usuarios y services/tokens, y convierte sus excepciones en códigos HTTP.
"""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, field_validator

from app.dependencias import SesionActiva, SesionBD, UsuarioActual, sesion_actual
from services import tokens, usuarios

router = APIRouter(prefix="/api/auth", tags=["autenticación"])


# --- Esquemas de entrada y salida ---

class DatosRegistro(BaseModel):
    correo: EmailStr
    nombre: str = Field(min_length=1, max_length=100)
    # Máximo 128: argon2 aguanta más, pero así nadie manda 10 MB para gastar CPU.
    contrasena: str = Field(min_length=8, max_length=128)

    @field_validator("nombre")
    @classmethod
    def nombre_no_vacio(cls, valor: str) -> str:
        if not valor.strip():
            raise ValueError("El nombre no puede estar vacío.")
        return valor.strip()


class DatosIngreso(BaseModel):
    correo: EmailStr
    contrasena: str = Field(min_length=1, max_length=128)


class UsuarioPublico(BaseModel):
    """Lo que el frontend puede saber de un usuario. Nunca el hash."""

    id: uuid.UUID
    correo: str
    nombre: str
    creado_en: datetime | None = None

    model_config = {"from_attributes": True}


class RespuestaSesion(BaseModel):
    token: str
    tipo: str = "bearer"
    expira_en: datetime
    usuario: UsuarioPublico


def _sesion_para(usuario) -> RespuestaSesion:
    token, expira = tokens.crear_token(usuario.id)
    return RespuestaSesion(token=token, expira_en=expira, usuario=UsuarioPublico.model_validate(usuario))


# --- Rutas públicas ---

@router.post("/registro", status_code=status.HTTP_201_CREATED)
def registro(datos: DatosRegistro, sesion: SesionBD) -> RespuestaSesion:
    """Crea la cuenta y deja la sesión iniciada (devuelve el token de una vez)."""
    try:
        usuario = usuarios.registrar(sesion, datos.correo, datos.nombre, datos.contrasena)
    except usuarios.CorreoYaRegistrado:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe una cuenta con ese correo.") from None
    sesion.refresh(usuario)  # trae creado_en, que lo pone la base
    return _sesion_para(usuario)


@router.post("/ingresar")
def ingresar(datos: DatosIngreso, sesion: SesionBD) -> RespuestaSesion:
    try:
        usuario = usuarios.autenticar(sesion, datos.correo, datos.contrasena)
    except usuarios.CredencialesInvalidas:
        # Mensaje genérico: no revela si el correo existe.
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Correo o contraseña incorrectos.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    return _sesion_para(usuario)


# --- Rutas protegidas ---

@router.get("/yo")
def yo(usuario: UsuarioActual) -> UsuarioPublico:
    return UsuarioPublico.model_validate(usuario)


@router.post("/salir", status_code=status.HTTP_204_NO_CONTENT)
def salir(activa: Annotated[SesionActiva, Depends(sesion_actual)], sesion: SesionBD) -> None:
    """Revoca el token actual: a partir de aquí deja de servir aunque no haya expirado."""
    tokens.revocar(sesion, activa.jti, activa.exp)
