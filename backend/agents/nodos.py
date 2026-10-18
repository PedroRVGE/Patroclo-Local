"""Los nodos del grafo. Cada uno es una función pequeña: recibe el estado y devuelve solo
lo que cambia.

Los nodos son métodos de `NodosPatroclo` para recibir sus dependencias (modelo, base
vectorial, función de guardado) desde afuera. En las pruebas se le pasan versiones falsas;
en la API, las reales.
"""

import functools
import logging
import re
import time
from collections.abc import Callable

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.vectorstores import VectorStore

from agents import prompts
from agents.estado import EstadoPatroclo, Fragmento
from agents.llm import limpiar

log = logging.getLogger(__name__)

INTENCIONES = ("SALUDO", "PRODUCTO_LACTEO", "FUERA_DE_DOMINIO")
MAX_HISTORIAL = 6  # mensajes anteriores que se le muestran al reformulador

# Si la pregunta nombra algo del dominio, el código no deja que el clasificador la mande a
# FUERA_DE_DOMINIO: en ese caso deciden el umbral y el juez, que miran la base de verdad.
# (Un modelo de 2B clasificó «¿dónde pastorean las cabras de Del Pastor?» como fuera de dominio.)
TERMINOS_DEL_DOMINIO = re.compile(
    r"\b(quesos?|cabras?|caprin\w*|leches?|l[áa]cte\w*|feta|ib[ée]rico|manchego|griego|crema|"
    r"yogur\w*|mantequilla|helados?|salmuera|cuajo|maridaj\w*|del pastor|alcanza)\b",
    re.IGNORECASE,
)


def paso(nombre: str):
    """Decorador: mide el nodo y agrega {nodo, detalle, ms} a `pasos`.

    El nodo puede devolver una clave `detalle` (texto corto para el frontend); el
    decorador la saca del resultado y la pone en el paso.
    """

    def decorador(funcion):
        @functools.wraps(funcion)
        def envoltura(self, estado: EstadoPatroclo) -> dict:
            inicio = time.perf_counter()
            resultado = funcion(self, estado)
            ms = round((time.perf_counter() - inicio) * 1000)
            detalle = resultado.pop("detalle", "")
            log.info("nodo %-22s %6d ms  %s", nombre, ms, detalle)
            return {**resultado, "pasos": [{"nodo": nombre, "detalle": detalle, "ms": ms}]}

        return envoltura

    return decorador


class NodosPatroclo:
    def __init__(
        self,
        llm_decision: BaseChatModel,
        llm_respuesta: BaseChatModel,
        almacen: VectorStore,
        umbral_distancia: float,
        k: int = 4,
        guardar: Callable[[EstadoPatroclo], None] | None = None,
        solo_publico: bool = False,
    ):
        self.llm_decision = llm_decision
        self.llm_respuesta = llm_respuesta
        self.almacen = almacen
        self.umbral = umbral_distancia
        self.k = k
        self.guardar = guardar
        # Para el futuro mini-Patroclo de WhatsApp: solo fragmentos `publico`.
        # El filtro lo aplica la consulta a la base, no el prompt.
        self.solo_publico = solo_publico

    def _preguntar(self, llm: BaseChatModel, mensajes) -> str:
        return limpiar(llm.invoke(mensajes).content)

    # ------------------------------------------------------------------ 1
    @paso("reformular_pregunta")
    def reformular_pregunta(self, estado: EstadoPatroclo) -> dict:
        pregunta = estado["pregunta"].strip()
        historial = (estado.get("historial") or [])[-MAX_HISTORIAL:]
        if not historial:
            # Sin historial no hay nada que resolver: no se gasta una llamada al modelo.
            return {"pregunta_independiente": pregunta, "detalle": "sin historial: se usa tal cual"}

        texto_historial = "\n".join(
            f"{'Usuario' if m['rol'] == 'usuario' else 'Patroclo'}: {m['contenido'][:400]}" for m in historial
        )
        # Con el modelo de respuesta (no el de decisión, limitado a ~12 tokens): una pregunta
        # reescrita puede ser más larga que una palabra.
        reescrita = self._preguntar(
            self.llm_respuesta,
            [HumanMessage(prompts.REFORMULAR.format(historial=texto_historial, pregunta=pregunta))],
        ).splitlines()
        reescrita = reescrita[0].strip().strip('"«»') if reescrita else ""
        # Si el modelo devuelve algo vacío o desproporcionado, se usa la original.
        if not reescrita or len(reescrita) > 3 * len(pregunta) + 80:
            reescrita = pregunta
        return {"pregunta_independiente": reescrita, "detalle": f"«{reescrita}»"}

    # ------------------------------------------------------------------ 2
    @paso("clasificar_intencion")
    def clasificar_intencion(self, estado: EstadoPatroclo) -> dict:
        salida = self._preguntar(
            self.llm_decision,
            [HumanMessage(prompts.CLASIFICAR.format(pregunta=estado["pregunta_independiente"]))],
        )
        normalizada = salida.upper().replace(" ", "_").replace("Á", "A")
        intencion = next((i for i in INTENCIONES if i in normalizada), None)
        if intencion is None:
            # Respuesta inesperada: se asume del dominio y deciden el umbral y el juez.
            # Un fallo del clasificador nunca puede producir una respuesta inventada.
            return {"intencion": "PRODUCTO_LACTEO", "detalle": f"salida no reconocida («{salida[:30]}») → PRODUCTO_LACTEO"}
        if intencion == "FUERA_DE_DOMINIO" and TERMINOS_DEL_DOMINIO.search(estado["pregunta_independiente"]):
            return {"intencion": "PRODUCTO_LACTEO", "detalle": "modelo: FUERA_DE_DOMINIO, pero nombra términos del dominio → PRODUCTO_LACTEO"}
        return {"intencion": intencion, "detalle": intencion}

    # ------------------------------------------------------------------ 3
    @paso("recuperar_contexto")
    def recuperar_contexto(self, estado: EstadoPatroclo) -> dict:
        filtro = {"visibilidad": {"$eq": "publico"}} if self.solo_publico else None
        resultados = self.almacen.similarity_search_with_score(
            estado["pregunta_independiente"], k=self.k, filter=filtro
        )
        fragmentos: list[Fragmento] = [
            {"texto": doc.page_content, "metadata": doc.metadata, "distancia": float(dist)}
            for doc, dist in resultados
            if dist <= self.umbral  # estrategia 1: umbral mínimo de similitud
        ]
        distancias = ", ".join(f"{d:.2f}" for _, d in resultados) or "ninguno"
        return {
            "fragmentos": fragmentos,
            "detalle": f"{len(fragmentos)} de {len(resultados)} pasan el umbral {self.umbral:.2f} (distancias: {distancias})",
        }

    # ------------------------------------------------------------------ 4
    @paso("evaluar_contexto")
    def evaluar_contexto(self, estado: EstadoPatroclo) -> dict:
        fragmentos = estado.get("fragmentos") or []
        if not fragmentos:
            return {"contexto_suficiente": False, "detalle": "no hay fragmentos: insuficiente"}

        # Estrategia 2: un LLM juez decide si el contexto responde la pregunta.
        veredicto = self._preguntar(
            self.llm_decision, self._mensajes_con_contexto(fragmentos, prompts.JUZGAR, estado)
        )
        suficiente = veredicto.upper().lstrip("¡¿ ").startswith(("SI", "SÍ"))
        return {
            "contexto_suficiente": suficiente,
            "detalle": f"juez: «{veredicto[:20]}» → {'suficiente' if suficiente else 'insuficiente'}",
        }

    # ------------------------------------------------------------------ 5
    @paso("generar_respuesta")
    def generar_respuesta(self, estado: EstadoPatroclo) -> dict:
        fragmentos = estado["fragmentos"]
        # Estrategia 3: el prompt obliga a responder solo con el contexto y citar [n].
        respuesta = self._preguntar(
            self.llm_respuesta, self._mensajes_con_contexto(fragmentos, prompts.GENERAR, estado)
        )
        if not respuesta or "NO_SE" in respuesta.upper().replace("Ó", "O"):
            # El generador mismo dice que no puede: se rechaza (no se muestra su texto).
            return {"rechazada": True, "detalle": "el generador respondió NO_SE → rechazar"}
        return {
            "respuesta": respuesta,
            "fuentes": self._fuentes(fragmentos),
            "rechazada": False,
            "detalle": f"{len(respuesta)} caracteres, {len(fragmentos)} fuentes",
        }

    # ------------------------------------------------------------------ fines
    @paso("rechazar")
    def rechazar(self, estado: EstadoPatroclo) -> dict:
        # Estrategia 4: rechazo explícito con el mensaje literal del enunciado.
        return {"respuesta": prompts.MENSAJE_RECHAZO, "fuentes": [], "rechazada": True, "detalle": "mensaje literal"}

    @paso("responder_saludo")
    def responder_saludo(self, estado: EstadoPatroclo) -> dict:
        return {"respuesta": prompts.MENSAJE_SALUDO, "fuentes": [], "rechazada": False, "detalle": "mensaje fijo"}

    @paso("guardar_historial")
    def guardar_historial(self, estado: EstadoPatroclo) -> dict:
        if self.guardar is None:
            return {"detalle": "sin almacenamiento (modo evaluación)"}
        self.guardar(estado)
        return {"detalle": "guardado"}

    # ------------------------------------------------------------------ ayudas
    def _mensajes_con_contexto(self, fragmentos: list[Fragmento], plantilla: str, estado: EstadoPatroclo):
        contexto = "\n\n".join(f"[{i}] {f['texto']}" for i, f in enumerate(fragmentos, start=1))
        return [
            SystemMessage(prompts.SISTEMA_CON_CONTEXTO.format(contexto=contexto)),
            HumanMessage(plantilla.format(pregunta=estado["pregunta_independiente"])),
        ]

    @staticmethod
    def _fuentes(fragmentos: list[Fragmento]) -> list[dict]:
        # Estrategia 5: las fuentes y los fragmentos usados se devuelven para mostrarlos.
        return [
            {
                "numero": i,
                "documento": f["metadata"].get("nombre"),
                "archivo": f["metadata"].get("archivo"),
                "documento_id": f["metadata"].get("documento_id"),
                "pagina": f["metadata"].get("pagina"),
                "seccion": f["metadata"].get("seccion"),
                "fragmento": f["texto"],
                "similitud": round(1 - f["distancia"], 3),
            }
            for i, f in enumerate(fragmentos, start=1)
        ]
