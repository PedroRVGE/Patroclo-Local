"""Historial de conversaciones del usuario. Protegidas; cada usuario solo ve las suyas."""

import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.dependencias import SesionBD, UsuarioActual
from controllers.chat import Fuente, Paso
from services import historial

router = APIRouter(prefix="/api/conversaciones", tags=["historial"])


class ResumenConversacion(BaseModel):
    id: uuid.UUID
    titulo: str
    creada_en: datetime | None
    actualizada_en: datetime | None
    mensajes: int


class MensajePublico(BaseModel):
    id: uuid.UUID
    rol: str
    contenido: str
    fuentes: list[Fuente] = []
    pasos: list[Paso] = []
    rechazada: bool
    tiempo_ms: int | None
    creado_en: datetime | None

    model_config = {"from_attributes": True}


class ConversacionCompleta(BaseModel):
    id: uuid.UUID
    titulo: str
    creada_en: datetime | None
    mensajes: list[MensajePublico]


def _no_encontrada() -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, "La conversación no existe.")


@router.get("")
def listar(usuario: UsuarioActual, sesion: SesionBD) -> list[ResumenConversacion]:
    return [
        ResumenConversacion(id=c.id, titulo=c.titulo, creada_en=c.creada_en, actualizada_en=c.actualizada_en, mensajes=n)
        for c, n in historial.listar(sesion, usuario)
    ]


@router.get("/{conversacion_id}")
def ver(conversacion_id: uuid.UUID, usuario: UsuarioActual, sesion: SesionBD) -> ConversacionCompleta:
    try:
        c = historial.obtener(sesion, conversacion_id, usuario)
    except historial.ConversacionNoEncontrada:
        raise _no_encontrada() from None
    return ConversacionCompleta(
        id=c.id,
        titulo=c.titulo,
        creada_en=c.creada_en,
        mensajes=[
            MensajePublico(
                id=m.id, rol=m.rol, contenido=m.contenido, fuentes=m.fuentes or [], pasos=m.pasos or [],
                rechazada=m.rechazada, tiempo_ms=m.tiempo_ms, creado_en=m.creado_en,
            )
            for m in c.mensajes
        ],
    )


@router.delete("/{conversacion_id}", status_code=status.HTTP_204_NO_CONTENT)
def borrar(conversacion_id: uuid.UUID, usuario: UsuarioActual, sesion: SesionBD) -> None:
    try:
        historial.borrar(sesion, conversacion_id, usuario)
    except historial.ConversacionNoEncontrada:
        raise _no_encontrada() from None
