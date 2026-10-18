"""Carga la base de conocimiento inicial (conocimiento/*.md) en la base vectorial.

Uso (desde backend/):
    uv run python -m app.semilla              # indexa lo que falte (rápido si ya está todo)
    uv run python -m app.semilla --reindexar  # recalcula TODOS los vectores (p. ej. al
                                              # cambiar EMBEDDING_MODEL)

Es seguro correrlo siempre (el contenedor lo hace al arrancar):
- un archivo que ya está indexado (mismo sha256) no se toca;
- si un archivo de conocimiento/ cambió, se borra la versión vieja y se indexa la nueva;
- `README.md` no se indexa (explica el formato, no es conocimiento).
"""

import argparse
import hashlib
import logging
import sys
import time
from pathlib import Path

from sqlalchemy import select

from app.config import obtener_configuracion
from db.conexion import crear_tablas, nueva_sesion
from db.modelos import Documento
from services import ingesta
from services.modelo_local import ModeloNoDisponible
from vectorstore.almacen import obtener_almacen

log = logging.getLogger("patroclo.semilla")


def sembrar() -> None:
    carpeta = Path(obtener_configuracion().conocimiento_dir)
    archivos = sorted(f for f in carpeta.glob("*.md") if f.name.lower() != "readme.md")
    if not archivos:
        log.warning("No hay archivos .md en %s", carpeta.resolve())
        return

    almacen = obtener_almacen()
    with nueva_sesion() as sesion:
        # Documentos de la semilla que ya están, por nombre de archivo.
        previos = {
            d.nombre_original: d
            for d in sesion.scalars(select(Documento).where(Documento.subido_por.is_(None)))
        }
        nuevos = 0
        for archivo in archivos:
            contenido = archivo.read_bytes()
            previo = previos.get(archivo.name)
            if previo and previo.sha256 != hashlib.sha256(contenido).hexdigest():
                log.info("cambió %s: se reemplaza", archivo.name)
                ingesta.eliminar(sesion, almacen, previo)
            inicio = time.perf_counter()
            resultado = ingesta.ingerir(sesion, almacen, contenido, archivo.name, subido_por=None)
            if resultado.nuevo:
                nuevos += 1
                log.info(
                    "  + %-42s %3d fragmentos  %.1f s",
                    archivo.name, resultado.documento.fragmentos, time.perf_counter() - inicio,
                )
        log.info("Semilla: %d archivos, %d indexados ahora, %d ya estaban.", len(archivos), nuevos, len(archivos) - nuevos)


def reindexar_todo() -> None:
    almacen = obtener_almacen()
    # Borrar la colección entera y recrearla: si cambió el modelo de embeddings, los
    # vectores viejos tienen otra dimensión y no se pueden mezclar con los nuevos.
    almacen.delete_collection()
    almacen.create_collection()
    with nueva_sesion() as sesion:
        documentos = list(sesion.scalars(select(Documento)))
        for doc in documentos:
            doc.fragmentos = 0  # la colección ya está vacía: no hay ids viejos que borrar
            n = ingesta.reindexar(sesion, almacen, doc)
            log.info("  ↻ %-42s %3d fragmentos", doc.titulo, n)
    log.info("Reindexados %d documentos con %s.", len(documentos), obtener_configuracion().embedding_model)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--reindexar", action="store_true", help="recalcula todos los vectores")
    args = parser.parse_args()

    crear_tablas()
    try:
        reindexar_todo() if args.reindexar else sembrar()
    except ModeloNoDisponible:
        log.error("El modelo de embeddings no está disponible (¿Ollama arriba y %s descargado?).",
                  obtener_configuracion().embedding_model)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
