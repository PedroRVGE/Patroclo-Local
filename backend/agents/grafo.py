"""Construcción del grafo de LangGraph: los nodos y las aristas (quién sigue a quién).

    START
      ▼
    reformular_pregunta
      ▼
    clasificar_intencion ──SALUDO──────────▶ responder_saludo ──┐
      │ ──FUERA_DE_DOMINIO────────────────▶ rechazar ──────────┤
      ▼ PRODUCTO_LACTEO                         ▲               │
    recuperar_contexto                          │               │
      ▼                                         │               │
    evaluar_contexto ──insuficiente─────────────┤               │
      ▼ suficiente                              │               │
    generar_respuesta ──NO_SE───────────────────┘               │
      ▼ respondió                                               │
    guardar_historial ◀─────────────────────────────────────────┘
      ▼
    END

Las decisiones (aristas condicionales) las toma CÓDIGO leyendo el estado; el modelo
solo llena el estado (intención, veredicto del juez, respuesta).
"""

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from agents.estado import EstadoPatroclo
from agents.nodos import NodosPatroclo


def ruta_por_intencion(estado: EstadoPatroclo) -> str:
    return {"SALUDO": "responder_saludo", "FUERA_DE_DOMINIO": "rechazar"}.get(
        estado.get("intencion"), "recuperar_contexto"
    )


def ruta_por_contexto(estado: EstadoPatroclo) -> str:
    return "generar_respuesta" if estado.get("contexto_suficiente") else "rechazar"


def ruta_por_respuesta(estado: EstadoPatroclo) -> str:
    return "rechazar" if estado.get("rechazada") else "guardar_historial"


def construir_grafo(nodos: NodosPatroclo) -> CompiledStateGraph:
    g = StateGraph(EstadoPatroclo)

    g.add_node("reformular_pregunta", nodos.reformular_pregunta)
    g.add_node("clasificar_intencion", nodos.clasificar_intencion)
    g.add_node("recuperar_contexto", nodos.recuperar_contexto)
    g.add_node("evaluar_contexto", nodos.evaluar_contexto)
    g.add_node("generar_respuesta", nodos.generar_respuesta)
    g.add_node("rechazar", nodos.rechazar)
    g.add_node("responder_saludo", nodos.responder_saludo)
    g.add_node("guardar_historial", nodos.guardar_historial)

    g.add_edge(START, "reformular_pregunta")
    g.add_edge("reformular_pregunta", "clasificar_intencion")
    g.add_conditional_edges(
        "clasificar_intencion",
        ruta_por_intencion,
        ["responder_saludo", "rechazar", "recuperar_contexto"],
    )
    g.add_edge("recuperar_contexto", "evaluar_contexto")
    g.add_conditional_edges("evaluar_contexto", ruta_por_contexto, ["generar_respuesta", "rechazar"])
    g.add_conditional_edges("generar_respuesta", ruta_por_respuesta, ["rechazar", "guardar_historial"])
    g.add_edge("rechazar", "guardar_historial")
    g.add_edge("responder_saludo", "guardar_historial")
    g.add_edge("guardar_historial", END)

    return g.compile()


def crear_grafo_real(guardar=None, solo_publico: bool = False) -> CompiledStateGraph:
    """El grafo con Ollama y PGVector de verdad (lo usan la API y app.evaluar)."""
    from agents.llm import crear_llm
    from app.config import obtener_configuracion
    from vectorstore.almacen import obtener_almacen

    cfg = obtener_configuracion()
    nodos = NodosPatroclo(
        llm_decision=crear_llm(max_tokens=12),
        llm_respuesta=crear_llm(max_tokens=400),
        almacen=obtener_almacen(),
        umbral_distancia=cfg.umbral_distancia,
        k=cfg.k_fragmentos,
        guardar=guardar,
        solo_publico=solo_publico,
    )
    return construir_grafo(nodos)
