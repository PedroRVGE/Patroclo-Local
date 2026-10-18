"""Calibración de UMBRAL_DISTANCIA con los casos de evaluacion/casos.json.

Uso (desde backend/, con Postgres y Ollama arriba):
    uv run python -m app.calibrar_umbral

Para cada caso busca los 4 fragmentos más cercanos y muestra la distancia coseno del mejor
(menor = más parecido) y si la fuente esperada aparece. No usa el modelo de chat: solo
embeddings, así que tarda segundos.

Cómo leer la salida: los casos «responder» deberían quedar por debajo del umbral y los
«rechazar» fuera de dominio por encima. Los «rechazar» que caen por debajo (preguntas del
tema que la base no responde) no los puede atajar el umbral: para eso está el nodo juez.
"""

import json
import os
import sys
from pathlib import Path

from vectorstore.almacen import obtener_almacen

CASOS = Path(__file__).resolve().parents[2] / "evaluacion" / "casos.json"


def main() -> int:
    if os.name == "nt":
        sys.stdout.reconfigure(encoding="utf-8")
    casos = json.loads(CASOS.read_text(encoding="utf-8"))["casos"]
    almacen = obtener_almacen()
    filas = []
    for caso in casos:
        if caso["debe"] == "saludar":
            continue
        # El seguimiento depende del historial; aquí se calibra con la pregunta ya reformulada.
        pregunta = "¿Con qué sirvo el queso ibérico?" if "seguimiento" in caso else caso["pregunta"]
        resultados = almacen.similarity_search_with_score(pregunta, k=4)
        mejor = resultados[0][1] if resultados else 9.0
        archivos = [doc.metadata.get("archivo") for doc, _ in resultados]
        esperada = caso.get("fuente_esperada")
        posicion = archivos.index(esperada) + 1 if esperada in archivos else None
        filas.append((mejor, caso["id"], caso["debe"], posicion, pregunta, resultados[0][0].metadata["nombre"]))

    filas.sort()
    print(f"{'dist':>6}  {'id':4} {'debe':9} {'fuente':6}  pregunta  →  mejor fragmento")
    for dist, cid, debe, pos, pregunta, nombre in filas:
        marca = ("—" if debe == "responder" else "") if pos is None else f"top{pos}"
        print(f"{dist:6.3f}  {cid:4} {debe:9} {marca:6}  {pregunta[:50]:50} → {nombre[:40]}")

    responder = [d for d, _, debe, *_ in filas if debe == "responder"]
    rechazar = [d for d, _, debe, *_ in filas if debe == "rechazar"]
    print(f"\nresponder: peor (máxima) distancia = {max(responder):.3f}")
    print(f"rechazar:  distancias = {', '.join(f'{d:.3f}' for d in sorted(rechazar))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
