"""Sincroniza la base de conocimiento (conocimiento/*.md) con la base vectorial.

Uso (desde backend/):
    uv run python -m app.semilla              # deja la base igual a la carpeta
    uv run python -m app.semilla --reindexar  # recalcula TODOS los vectores (p. ej. al
                                              # cambiar EMBEDDING_MODEL)

Un solo comando deja todo al día; es seguro correrlo siempre (el contenedor lo hace al
arrancar):
- un archivo que ya está indexado (mismo sha256) no se toca;
- un archivo nuevo se indexa;
- si un archivo de conocimiento/ cambió, se borra la versión vieja y se indexa la nueva;
- si un archivo **ya no está** en la carpeta, su documento y sus vectores se borran;
- `README.md` no se indexa (explica el formato, no es conocimiento).

Lo que se subió desde el frontend (`subido_por` no nulo) nunca se toca aquí: esos
documentos se borran desde la pantalla Documentos.
"""

import argparse
import hashlib
import logging
import sys
import time
from pathlib import Path

from sqlalchemy import func, select

from app.config import obtener_configuracion
from db.conexion import crear_tablas, nueva_sesion
from db.modelos import Documento
from services import ingesta
from services.modelo_local import ModeloNoDisponible
from vectorstore.almacen import obtener_almacen

log = logging.getLogger("patroclo.semilla")


def olvidar_borrados(sesion, almacen, nombres: set[str]) -> list[str]:
    """Borra los documentos de la semilla cuyo .md ya no está en la carpeta.

    Solo toca los de la semilla (`subido_por` nulo): lo que subió un usuario desde el
    frontend se borra desde ahí. Devuelve los nombres borrados.
    """
    borrados = []
    previos = list(sesion.scalars(select(Documento).where(Documento.subido_por.is_(None))))
    for doc in previos:
        if doc.nombre_original not in nombres:
            ingesta.eliminar(sesion, almacen, doc)
            borrados.append(doc.nombre_original)
    return borrados


def sembrar() -> None:
    carpeta = Path(obtener_configuracion().conocimiento_dir)
    archivos = sorted(f for f in carpeta.glob("*.md") if f.name.lower() != "readme.md")
    if not archivos:
        # Carpeta vacía o mal montada: no se borra nada, que sería destruir la base por
        # un error de configuración.
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
        borrados = olvidar_borrados(sesion, almacen, {a.name for a in archivos})
        for nombre in borrados:
            log.info("  - %-42s ya no está en la carpeta: borrado", nombre)
        sesion.commit()
        total = sesion.scalar(select(func.count()).select_from(Documento))
        fragmentos = sesion.scalar(select(func.coalesce(func.sum(Documento.fragmentos), 0)))
        log.info(
            "Semilla: %d archivos, %d indexados ahora, %d ya estaban, %d borrados.",
            len(archivos), nuevos, len(archivos) - nuevos, len(borrados),
        )
        log.info("Base de conocimiento: %d documentos, %d fragmentos.", total, fragmentos)


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
