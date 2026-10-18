"""El estado del grafo: el «expediente» que pasa de nodo en nodo.

Cada nodo recibe el estado completo y devuelve SOLO las claves que cambia; LangGraph las
mezcla. La excepción es `pasos`: tiene un reductor (`operator.add`), así que cada nodo
devuelve su propio paso y LangGraph los va concatenando en vez de reemplazarlos.
"""

import operator
from typing import Annotated, Literal, TypedDict

Intencion = Literal["SALUDO", "PRODUCTO_LACTEO", "FUERA_DE_DOMINIO"]


class Fragmento(TypedDict):
    texto: str
    metadata: dict  # documento_id, nombre, archivo, pagina, seccion, visibilidad...
    distancia: float  # coseno: 0 = idéntico


class Mensaje(TypedDict):
    rol: Literal["usuario", "asistente"]
    contenido: str


class Paso(TypedDict):
    nodo: str
    detalle: str
    ms: int


class EstadoPatroclo(TypedDict, total=False):
    # Entrada
    pregunta: str
    historial: list[Mensaje]  # mensajes anteriores de la conversación (los carga la API)
    usuario_id: str | None
    conversacion_id: str | None
    # Lo que van llenando los nodos
    pregunta_independiente: str  # la pregunta reescrita para entenderse sin el historial
    intencion: Intencion
    fragmentos: list[Fragmento]  # los que pasaron el umbral
    contexto_suficiente: bool
    # Salida
    respuesta: str
    fuentes: list[dict]
    rechazada: bool
    pasos: Annotated[list[Paso], operator.add]
