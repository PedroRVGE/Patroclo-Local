"""Conversaciones y mensajes, persistentes en Postgres.

Las referencias guardaban el historial en RAM (se perdía al reiniciar y no se podía
listar). Aquí cada conversación es una fila y cada mensaje otra.

Regla de acceso: cada usuario solo ve las suyas. Pedir una ajena responde lo mismo que
pedir una que no existe (404), para no revelar que existe.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db.modelos import Conversacion, Mensaje, Usuario

MENSAJES_DE_CONTEXTO = 6  # los últimos que se le pasan al grafo como historial


class ConversacionNoEncontrada(Exception):
    pass


def crear(sesion: Session, usuario: Usuario, primera_pregunta: str) -> Conversacion:
    titulo = " ".join(primera_pregunta.split())
    conversacion = Conversacion(
        usuario_id=usuario.id,
        titulo=titulo if len(titulo) <= 80 else titulo[:79].rstrip() + "…",
    )
    sesion.add(conversacion)
    sesion.flush()  # asigna el id sin confirmar todavía (se confirma al guardar los mensajes)
    return conversacion


def obtener(sesion: Session, conversacion_id: uuid.UUID, usuario: Usuario) -> Conversacion:
    conversacion = sesion.get(Conversacion, conversacion_id)
    if conversacion is None or conversacion.usuario_id != usuario.id:
        raise ConversacionNoEncontrada()
    return conversacion


def historial_para_el_grafo(sesion: Session, conversacion: Conversacion) -> list[dict]:
    """Los últimos mensajes, en orden, con la forma que espera el estado del grafo."""
    ultimos = sesion.scalars(
        select(Mensaje)
        .where(Mensaje.conversacion_id == conversacion.id)
        .order_by(Mensaje.creado_en.desc())
        .limit(MENSAJES_DE_CONTEXTO)
    ).all()
    return [{"rol": m.rol, "contenido": m.contenido} for m in reversed(ultimos)]


def guardar_interaccion(
    sesion: Session, conversacion: Conversacion, pregunta: str, estado: dict, tiempo_ms: int
) -> Mensaje:
    """Guarda la pregunta y la respuesta (con fuentes, pasos y si fue rechazada)."""
    sesion.add(Mensaje(conversacion_id=conversacion.id, rol="usuario", contenido=pregunta))
    respuesta = Mensaje(
        conversacion_id=conversacion.id,
        rol="asistente",
        contenido=estado.get("respuesta", ""),
        fuentes=estado.get("fuentes") or [],
        pasos=estado.get("pasos") or [],
        rechazada=bool(estado.get("rechazada")),
        tiempo_ms=tiempo_ms,
    )
    sesion.add(respuesta)
    conversacion.actualizada_en = datetime.now(UTC)
    sesion.commit()
    return respuesta


def listar(sesion: Session, usuario: Usuario) -> list[tuple[Conversacion, int]]:
    """Conversaciones del usuario con su número de mensajes, la más reciente primero."""
    cantidad = (
        select(Mensaje.conversacion_id, func.count().label("n")).group_by(Mensaje.conversacion_id).subquery()
    )
    filas = sesion.execute(
        select(Conversacion, func.coalesce(cantidad.c.n, 0))
        .outerjoin(cantidad, cantidad.c.conversacion_id == Conversacion.id)
        .where(Conversacion.usuario_id == usuario.id)
        .order_by(Conversacion.actualizada_en.desc())
    ).all()
    return [(c, n) for c, n in filas]


def borrar(sesion: Session, conversacion_id: uuid.UUID, usuario: Usuario) -> None:
    sesion.delete(obtener(sesion, conversacion_id, usuario))  # los mensajes caen en cascada
    sesion.commit()
