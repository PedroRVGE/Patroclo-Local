"""Pruebas del grafo con un modelo y una base vectorial FALSOS.

Prueban la lógica del grafo (qué camino toma y por qué), no la calidad del modelo. Son
deterministas y tardan milisegundos. La calidad con el modelo real la miden
tests/test_casos_reales.py y `python -m app.evaluar`.
"""

from dataclasses import dataclass, field

from langchain_core.documents import Document
from langchain_core.messages import AIMessage

from agents import prompts
from agents.grafo import construir_grafo
from agents.nodos import NodosPatroclo


class LLMFalso:
    """Responde según qué nodo pregunta (lo reconoce por el texto del prompt)."""

    def __init__(self, clasificacion="PRODUCTO_LACTEO", juez="SI", respuesta="El ibérico es madurado [1].",
                 reescritura="¿Con qué sirvo el queso ibérico?"):
        self.salidas = {"clasificar": clasificacion, "juzgar": juez, "generar": respuesta, "reformular": reescritura}
        self.llamadas: list[str] = []

    def invoke(self, mensajes):
        texto = "\n".join(m.content for m in mensajes)
        if "Categoría:" in texto:
            nodo = "clasificar"
        elif "¿El CONTEXTO trae" in texto:
            nodo = "juzgar"
        elif "usando ÚNICAMENTE el CONTEXTO" in texto:
            nodo = "generar"
        elif "Pregunta reescrita:" in texto:
            nodo = "reformular"
        else:
            raise AssertionError(f"prompt no reconocido: {texto[:80]}")
        self.llamadas.append(nodo)
        return AIMessage(self.salidas[nodo])


@dataclass
class AlmacenFalso:
    distancias: list[float] = field(default_factory=lambda: [0.20, 0.35])
    consultas: list = field(default_factory=list)

    def similarity_search_with_score(self, consulta, k=4, filter=None):
        self.consultas.append({"consulta": consulta, "k": k, "filter": filter})
        return [
            (Document(page_content=f"Documento: Ibérico\n\nTexto {i}", metadata={
                "nombre": "El queso ibérico de cabra", "archivo": "06-queso-iberico-de-cabra.md",
                "documento_id": "d1", "pagina": None, "seccion": f"Sección {i}"}), d)
            for i, d in enumerate(self.distancias[:k], start=1)
        ]


def correr(pregunta="¿Qué es el ibérico?", historial=None, llm=None, almacen=None, umbral=0.5, **kw):
    llm = llm or LLMFalso()
    almacen = almacen if almacen is not None else AlmacenFalso()
    guardados = []
    nodos = NodosPatroclo(llm, llm, almacen, umbral_distancia=umbral, k=4, guardar=guardados.append, **kw)
    estado = construir_grafo(nodos).invoke({"pregunta": pregunta, "historial": historial or []})
    return estado, llm, almacen, guardados


def recorrido(estado):
    return [p["nodo"] for p in estado["pasos"]]


# --- Caminos del grafo ---

def test_respuesta_fundamentada_con_fuentes():
    estado, llm, _, guardados = correr()
    assert estado["rechazada"] is False
    assert estado["respuesta"] == "El ibérico es madurado [1]."
    assert recorrido(estado) == [
        "reformular_pregunta", "clasificar_intencion", "recuperar_contexto",
        "evaluar_contexto", "generar_respuesta", "guardar_historial",
    ]
    fuente = estado["fuentes"][0]
    assert fuente["numero"] == 1
    assert fuente["documento"] == "El queso ibérico de cabra"
    assert fuente["archivo"] == "06-queso-iberico-de-cabra.md"
    assert fuente["similitud"] == 0.8
    assert len(guardados) == 1


def test_saludo_no_busca_en_la_base():
    estado, llm, almacen, _ = correr("Hola, ¿qué tal?", llm=LLMFalso(clasificacion="SALUDO"))
    assert estado["respuesta"] == prompts.MENSAJE_SALUDO
    assert estado["rechazada"] is False
    assert almacen.consultas == []
    assert recorrido(estado) == ["reformular_pregunta", "clasificar_intencion", "responder_saludo", "guardar_historial"]


def test_fuera_de_dominio_se_rechaza_sin_buscar():
    estado, llm, almacen, _ = correr("¿Quién ganó el Mundial?", llm=LLMFalso(clasificacion="FUERA_DE_DOMINIO"))
    assert estado["rechazada"] is True
    assert estado["respuesta"] == prompts.MENSAJE_RECHAZO
    assert almacen.consultas == []


def test_el_mensaje_de_rechazo_contiene_el_literal_del_enunciado():
    assert prompts.MENSAJE_RECHAZO.startswith(
        "No tengo suficiente información en mi base de conocimiento para responder esa pregunta."
    )


# --- Control de alucinaciones ---

def test_umbral_descarta_fragmentos_lejanos_y_no_llama_al_juez():
    estado, llm, _, _ = correr(almacen=AlmacenFalso(distancias=[0.62, 0.70]))
    assert estado["fragmentos"] == []
    assert estado["rechazada"] is True
    assert estado["respuesta"] == prompts.MENSAJE_RECHAZO
    assert "juzgar" not in llm.llamadas and "generar" not in llm.llamadas


def test_umbral_deja_solo_los_fragmentos_cercanos():
    estado, _, _, _ = correr(almacen=AlmacenFalso(distancias=[0.30, 0.45, 0.55]), umbral=0.5)
    assert [round(f["distancia"], 2) for f in estado["fragmentos"]] == [0.30, 0.45]
    assert len(estado["fuentes"]) == 2


def test_juez_dice_no_entonces_rechaza_sin_generar():
    estado, llm, _, _ = correr("¿Qué vino va con el ibérico?", llm=LLMFalso(juez="NO"))
    assert estado["rechazada"] is True
    assert estado["respuesta"] == prompts.MENSAJE_RECHAZO
    assert "generar" not in llm.llamadas
    assert estado["fuentes"] == []


def test_generador_dice_no_se_entonces_rechaza():
    estado, _, _, _ = correr(llm=LLMFalso(respuesta="NO_SE"))
    assert estado["rechazada"] is True
    assert estado["respuesta"] == prompts.MENSAJE_RECHAZO
    assert recorrido(estado)[-2:] == ["rechazar", "guardar_historial"]


def test_clasificador_confundido_no_produce_respuesta_inventada():
    # Salida inesperada → se trata como PRODUCTO_LACTEO y deciden umbral y juez.
    estado, _, _, _ = correr(llm=LLMFalso(clasificacion="Creo que es sobre comida", juez="NO"))
    assert estado["intencion"] == "PRODUCTO_LACTEO"
    assert estado["rechazada"] is True


def test_fuera_de_dominio_con_terminos_del_dominio_lo_corrige_el_codigo():
    # El modelo dice FUERA_DE_DOMINIO, pero la pregunta habla de cabras: se busca igual.
    estado, _, almacen, _ = correr("¿Dónde pastorean las cabras de Del Pastor?",
                                   llm=LLMFalso(clasificacion="FUERA_DE_DOMINIO"))
    assert estado["intencion"] == "PRODUCTO_LACTEO"
    assert almacen.consultas, "debió buscar en la base"
    assert estado["rechazada"] is False


def test_se_limpia_el_razonamiento_think():
    estado, _, _, _ = correr("Hola", llm=LLMFalso(clasificacion="<think>el usuario saluda</think>\nSALUDO"))
    assert estado["intencion"] == "SALUDO"


def test_juez_acepta_si_con_tilde():
    estado, _, _, _ = correr(llm=LLMFalso(juez="Sí."))
    assert estado["contexto_suficiente"] is True


# --- Historial y filtros ---

def test_sin_historial_no_se_llama_al_reformulador():
    estado, llm, _, _ = correr("¿Qué es el ibérico?")
    assert "reformular" not in llm.llamadas
    assert estado["pregunta_independiente"] == "¿Qué es el ibérico?"


def test_con_historial_se_busca_con_la_pregunta_reescrita():
    historial = [
        {"rol": "usuario", "contenido": "¿Qué es el queso ibérico?"},
        {"rol": "asistente", "contenido": "Es el queso madurado de Del Pastor."},
    ]
    estado, llm, almacen, _ = correr("¿Y con qué lo sirvo?", historial=historial)
    assert "reformular" in llm.llamadas
    assert almacen.consultas[0]["consulta"] == "¿Con qué sirvo el queso ibérico?"


def test_reescritura_vacia_usa_la_pregunta_original():
    historial = [{"rol": "usuario", "contenido": "hola"}]
    estado, _, _, _ = correr("¿Qué es el feta?", historial=historial, llm=LLMFalso(reescritura=""))
    assert estado["pregunta_independiente"] == "¿Qué es el feta?"


def test_solo_publico_filtra_en_la_consulta():
    _, _, almacen, _ = correr(solo_publico=True)
    assert almacen.consultas[0]["filter"] == {"visibilidad": {"$eq": "publico"}}


def test_cada_paso_tiene_detalle_y_tiempo():
    estado, _, _, _ = correr()
    for p in estado["pasos"]:
        assert set(p) == {"nodo", "detalle", "ms"}
        assert isinstance(p["ms"], int)
