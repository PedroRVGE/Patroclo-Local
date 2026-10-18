"""Corre los casos de evaluacion/casos.json contra el grafo REAL (Ollama + PGVector).

Uso (desde backend/, con Postgres y Ollama arriba):
    uv run python -m app.evaluar                       # modelo de CHAT_MODEL
    uv run python -m app.evaluar --modelo qwen3.5:2b   # comparar otro modelo
    uv run python -m app.evaluar --casos R01 X05       # solo algunos

Imprime una tabla (acierto, tiempo, fuente) y guarda el detalle en
evaluacion/resultados-<modelo>.json. Con eso se calibra UMBRAL_DISTANCIA, se comparan
modelos y se arma la sección de evidencias del documento técnico.

Qué cuenta como acierto: el COMPORTAMIENTO (responder / rechazar / saludar). La fuente
esperada se reporta aparte: la base repite información entre archivos (p. ej. las
preguntas frecuentes), así que una respuesta correcta puede venir de otra fuente válida.
Las ideas de `debe_mencionar` se revisan leyendo las respuestas guardadas.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

from agents import prompts
from app.config import obtener_configuracion
from services.modelo_local import ERRORES_OLLAMA

RAIZ = Path(__file__).resolve().parents[2]
CASOS = RAIZ / "evaluacion" / "casos.json"


def comportamiento(estado: dict) -> str:
    if estado.get("intencion") == "SALUDO":
        return "saludar"
    return "rechazar" if estado.get("rechazada") else "responder"


def correr_caso(grafo, caso: dict) -> dict:
    historial = []
    if "seguimiento" in caso:
        # Primero la pregunta original, para tener historial; se evalúa el seguimiento.
        previo = grafo.invoke({"pregunta": caso["pregunta"], "historial": []})
        historial = [
            {"rol": "usuario", "contenido": caso["pregunta"]},
            {"rol": "asistente", "contenido": previo["respuesta"]},
        ]
    pregunta = caso.get("seguimiento", caso["pregunta"])

    inicio = time.perf_counter()
    estado = grafo.invoke({"pregunta": pregunta, "historial": historial})
    segundos = time.perf_counter() - inicio

    obtuvo = comportamiento(estado)
    archivos = [f.get("archivo") for f in estado.get("fuentes", [])]
    esperada = caso.get("fuente_esperada")
    return {
        "id": caso["id"],
        "pregunta": pregunta,
        "debe": caso["debe"],
        "obtuvo": obtuvo,
        "acierto": obtuvo == caso["debe"],
        "rechazo_literal": (estado.get("respuesta") == prompts.MENSAJE_RECHAZO) if obtuvo == "rechazar" else None,
        "fuente_esperada": esperada,
        "fuente_ok": (esperada in archivos) if esperada and obtuvo == "responder" else None,
        "segundos": round(segundos, 1),
        "pregunta_independiente": estado.get("pregunta_independiente"),
        "respuesta": estado.get("respuesta"),
        "fuentes": archivos,
        "debe_mencionar": caso.get("debe_mencionar"),
        "pasos": estado.get("pasos"),
    }


def main() -> int:
    if os.name == "nt":
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--modelo", help="modelo de chat a evaluar (por defecto CHAT_MODEL)")
    parser.add_argument("--casos", nargs="*", help="ids de los casos a correr (por defecto todos)")
    args = parser.parse_args()

    cfg = obtener_configuracion()
    if args.modelo:
        cfg.chat_model = args.modelo
    from agents.grafo import crear_grafo_real

    grafo = crear_grafo_real()
    casos = json.loads(CASOS.read_text(encoding="utf-8"))["casos"]
    if args.casos:
        casos = [c for c in casos if c["id"] in args.casos]

    print(f"Modelo: {cfg.chat_model} · embeddings: {cfg.embedding_model} · umbral: {cfg.umbral_distancia} · k: {cfg.k_fragmentos}")
    try:
        print("Calentando el modelo (la primera carga no se cuenta)...")
        grafo.invoke({"pregunta": "¿Qué es el queso tipo griego?", "historial": []})

        resultados = []
        print(f"\n{'id':4} {'debe':9} {'obtuvo':9} {'ok':3} {'fuente':7} {'seg':>5}  pregunta")
        for caso in casos:
            r = correr_caso(grafo, caso)
            resultados.append(r)
            fuente = {True: "sí", False: "no", None: ""}[r["fuente_ok"]]
            print(f"{r['id']:4} {r['debe']:9} {r['obtuvo']:9} {'✓' if r['acierto'] else '✗':3} {fuente:7} {r['segundos']:5.1f}  {r['pregunta'][:55]}")
    except ERRORES_OLLAMA as e:
        print(f"\nEl modelo local no está disponible: {e}")
        return 1

    aciertos = sum(r["acierto"] for r in resultados)
    con_fuente = [r for r in resultados if r["fuente_ok"] is not None]
    respondidas = [r["segundos"] for r in resultados if r["obtuvo"] == "responder"]
    print(f"\nAciertos de comportamiento: {aciertos}/{len(resultados)}")
    if con_fuente:
        print(f"Fuente esperada entre las fuentes: {sum(r['fuente_ok'] for r in con_fuente)}/{len(con_fuente)} respondidas")
    print(f"Tiempo medio: {sum(r['segundos'] for r in resultados) / len(resultados):.1f} s"
          + (f" · respondidas: {sum(respondidas) / len(respondidas):.1f} s" if respondidas else ""))

    salida = RAIZ / "evaluacion" / f"resultados-{cfg.chat_model.replace(':', '-').replace('/', '-')}.json"
    salida.write_text(
        json.dumps({"modelo": cfg.chat_model, "umbral": cfg.umbral_distancia, "aciertos": aciertos,
                    "total": len(resultados), "resultados": resultados}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    print(f"Detalle guardado en {salida.relative_to(RAIZ)}")
    return 0 if aciertos == len(resultados) else 2


if __name__ == "__main__":
    sys.exit(main())
