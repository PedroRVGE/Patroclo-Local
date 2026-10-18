"""Una pregunta al agente, de punta a punta.

    conversación (nueva o existente, del usuario) → historial → grafo → guardar → respuesta

El grafo se compila una sola vez. Lo que cambia por petición (cómo guardar en ESTA sesión
de base de datos) se le pasa en `config["configurable"]`, que LangGraph entrega a los
nodos que lo piden.
"""

import time
import uuid
from functools import lru_cache

from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.orm import Session

from db.modelos import Usuario
from services import historial
from services.modelo_local import ERRORES_OLLAMA, ModeloNoDisponible


@lru_cache
def obtener_grafo() -> CompiledStateGraph:
    """El grafo real (Ollama + PGVector), compilado una vez para toda la app."""
    from agents.grafo import crear_grafo_real

    return crear_grafo_real()


def responder(
    sesion: Session,
    grafo: CompiledStateGraph,
    usuario: Usuario,
    pregunta: str,
    conversacion_id: uuid.UUID | None = None,
) -> dict:
    inicio = time.perf_counter()

    if conversacion_id:
        conversacion = historial.obtener(sesion, conversacion_id, usuario)
        previos = historial.historial_para_el_grafo(sesion, conversacion)
    else:
        conversacion = historial.crear(sesion, usuario, pregunta)
        previos = []

    def guardar(estado: dict) -> None:
        # Lo llama el nodo guardar_historial, al final del grafo.
        tiempo_ms = round((time.perf_counter() - inicio) * 1000)
        historial.guardar_interaccion(sesion, conversacion, pregunta, estado, tiempo_ms)

    try:
        estado = grafo.invoke(
            {
                "pregunta": pregunta,
                "historial": previos,
                "usuario_id": str(usuario.id),
                "conversacion_id": str(conversacion.id),
            },
            config={"configurable": {"guardar": guardar}},
        )
    except ERRORES_OLLAMA as e:
        # Ni la conversación nueva ni la pregunta quedan guardadas a medias.
        sesion.rollback()
        raise ModeloNoDisponible(str(e)) from e
    except Exception:
        sesion.rollback()
        raise

    return {
        "respuesta": estado["respuesta"],
        "conversacion_id": conversacion.id,
        "fuentes": estado.get("fuentes") or [],
        "pasos": estado.get("pasos") or [],
        "rechazada": bool(estado.get("rechazada")),
        "tiempo_ms": round((time.perf_counter() - inicio) * 1000),
        "con_historial": bool(previos),
    }
