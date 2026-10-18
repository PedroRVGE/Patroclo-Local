"""POST /api/chat — una pregunta al agente. Protegida."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel, Field, field_validator

from app.dependencias import SesionBD, UsuarioActual
from services import chat, historial

router = APIRouter(prefix="/api/chat", tags=["chat"])

Grafo = Annotated[CompiledStateGraph, Depends(chat.obtener_grafo)]


class Pregunta(BaseModel):
    pregunta: str = Field(min_length=1, max_length=1000)
    conversacion_id: uuid.UUID | None = None  # sin él, se abre una conversación nueva

    @field_validator("pregunta")
    @classmethod
    def no_vacia(cls, valor: str) -> str:
        if not valor.strip():
            raise ValueError("La pregunta no puede estar vacía.")
        return valor.strip()


class Fuente(BaseModel):
    numero: int
    documento: str | None
    archivo: str | None = None
    documento_id: str | None = None
    pagina: int | None = None
    seccion: str | None = None
    fragmento: str
    similitud: float


class Paso(BaseModel):
    nodo: str
    detalle: str
    ms: int


class RespuestaChat(BaseModel):
    respuesta: str
    conversacion_id: uuid.UUID
    fuentes: list[Fuente]
    pasos: list[Paso]
    rechazada: bool
    tiempo_ms: int
    con_historial: bool


@router.post("")
def preguntar(datos: Pregunta, usuario: UsuarioActual, sesion: SesionBD, grafo: Grafo) -> RespuestaChat:
    """Pasa la pregunta por el grafo y devuelve respuesta, fuentes y el recorrido.

    Si el modelo local no responde → 503 «El modelo local no está disponible».
    """
    try:
        return RespuestaChat(**chat.responder(sesion, grafo, usuario, datos.pregunta, datos.conversacion_id))
    except historial.ConversacionNoEncontrada:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "La conversación no existe.") from None
