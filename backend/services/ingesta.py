"""Ingesta de documentos: el flujo completo del PDF §2.4.

    recibir → validar → ¿ya existe? (sha256) → extraer → fragmentar
            → embeddings + guardar en PGVector → guardar archivo y fila → confirmar

Reglas:
- **Idempotente:** el mismo archivo (mismo sha256) dos veces devuelve el documento que ya
  existe, sin crear fragmentos nuevos.
- **Todo o nada:** si fallan los embeddings (Ollama caído) o la base, no queda ni la fila,
  ni el archivo en disco, ni vectores sueltos.
- **Solo quien subió un documento lo puede borrar.** Los de la semilla (subido_por NULL) no
  se pueden borrar desde la API.
"""

import hashlib
import logging
import uuid
from dataclasses import dataclass
from pathlib import Path

from langchain_core.vectorstores import VectorStore
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import obtener_configuracion
from db.modelos import Documento, Usuario
from services import extraccion, fragmentacion
from services.extraccion import ArchivoInvalido
from services.modelo_local import ERRORES_OLLAMA, ModeloNoDisponible
from vectorstore.almacen import ids_de_fragmentos

log = logging.getLogger(__name__)

VISIBILIDADES = {"publico", "interno"}


class ArchivoMuyGrande(Exception):
    pass


class DocumentoNoEncontrado(Exception):
    pass


class SinPermiso(Exception):
    pass


@dataclass
class ResultadoIngesta:
    documento: Documento
    nuevo: bool  # False = ya existía (mismo contenido) y no se volvió a indexar


def _dir_subidas() -> Path:
    ruta = Path(obtener_configuracion().subidas_dir)
    ruta.mkdir(parents=True, exist_ok=True)
    return ruta


def extension_de(nombre: str) -> str:
    return Path(nombre).suffix.lower().lstrip(".")


def _fragmentos_de(documento: Documento, extraido: extraccion.Extraido):
    """Fragmenta y pone en cada fragmento la metadata para citarlo, filtrarlo y borrarlo."""
    meta = extraido.metadatos
    metadata_base = {
        "documento_id": str(documento.id),
        "nombre": documento.titulo,
        "archivo": documento.nombre_original,
        "visibilidad": documento.visibilidad,
        "tema": meta.get("tema"),
        "productos": meta.get("productos") or [],
    }
    return fragmentacion.fragmentar(extraido, documento.titulo, metadata_base)


def _indexar(almacen: VectorStore, documento: Documento, fragmentos) -> list[str]:
    ids = ids_de_fragmentos(documento.id, len(fragmentos))
    try:
        # PGVector calcula TODOS los embeddings antes de insertar: si Ollama falla a la
        # mitad, no queda nada insertado.
        almacen.add_documents(fragmentos, ids=ids)
    except ERRORES_OLLAMA as e:
        raise ModeloNoDisponible(str(e)) from e
    return ids


def ingerir(
    sesion: Session,
    almacen: VectorStore,
    contenido: bytes,
    nombre_original: str,
    subido_por: uuid.UUID | None,
    visibilidad: str | None = None,
) -> ResultadoIngesta:
    cfg = obtener_configuracion()

    # 1. Validar lo barato primero (antes de leer el contenido).
    nombre_original = Path(nombre_original or "").name[:255]  # sin rutas («../../x»)
    if not nombre_original:
        raise ArchivoInvalido("El archivo no tiene nombre.")
    tipo = extension_de(nombre_original)
    extraccion.validar_extension(tipo)
    if len(contenido) > cfg.tamano_maximo_mb * 1024 * 1024:
        raise ArchivoMuyGrande()
    if visibilidad is not None and visibilidad not in VISIBILIDADES:
        raise ArchivoInvalido("La visibilidad debe ser «publico» o «interno».")

    # 2. ¿Ya existe? (idempotencia por contenido)
    sha256 = hashlib.sha256(contenido).hexdigest()
    existente = sesion.scalar(select(Documento).where(Documento.sha256 == sha256))
    if existente:
        return ResultadoIngesta(existente, nuevo=False)

    # 3. Extraer y fragmentar (valida que el contenido cuadre con la extensión).
    documento = Documento(
        id=uuid.uuid4(),
        nombre_original=nombre_original,
        titulo=Path(nombre_original).stem,
        tipo=tipo,
        sha256=sha256,
        tamano_bytes=len(contenido),
        nombre_archivo="",
        subido_por=subido_por,
        visibilidad=visibilidad or "interno",
    )
    extraido = extraccion.extraer(contenido, tipo)
    # El frontmatter (Markdown) puede traer título y visibilidad.
    if extraido.metadatos.get("titulo"):
        documento.titulo = str(extraido.metadatos["titulo"])[:255]
    if visibilidad is None and extraido.metadatos.get("visibilidad") in VISIBILIDADES:
        documento.visibilidad = extraido.metadatos["visibilidad"]
    fragmentos = _fragmentos_de(documento, extraido)
    if not fragmentos:
        raise ArchivoInvalido("El archivo no tiene texto que se pueda indexar.")

    # 4. Guardar copia en disco con un nombre generado por el sistema.
    documento.nombre_archivo = f"{documento.id.hex}.{tipo}"
    ruta = _dir_subidas() / documento.nombre_archivo
    ruta.write_bytes(contenido)

    # 5. Embeddings + vectores, y después la fila. Si algo falla, se deshace todo.
    ids: list[str] = []
    try:
        ids = _indexar(almacen, documento, fragmentos)
        documento.fragmentos = len(fragmentos)
        sesion.add(documento)
        sesion.commit()
    except IntegrityError:
        # Otro usuario subió el mismo archivo al mismo tiempo: gana el primero.
        sesion.rollback()
        _deshacer(almacen, ids, ruta)
        return ResultadoIngesta(sesion.scalar(select(Documento).where(Documento.sha256 == sha256)), nuevo=False)
    except Exception:
        sesion.rollback()
        _deshacer(almacen, ids, ruta)
        raise

    log.info("documento indexado: %s (%s fragmentos)", documento.titulo, documento.fragmentos)
    return ResultadoIngesta(documento, nuevo=True)


def _deshacer(almacen: VectorStore, ids: list[str], ruta: Path) -> None:
    if ids:
        try:
            almacen.delete(ids=ids)
        except Exception:
            log.exception("no se pudieron borrar %s vectores al deshacer una ingesta", len(ids))
    ruta.unlink(missing_ok=True)


def listar(sesion: Session) -> list[Documento]:
    """Primero los subidos por usuarios (el más reciente arriba); después la semilla, en el
    orden de sus archivos (01-…, 02-…, 90-…)."""
    documentos = list(sesion.scalars(select(Documento)))
    subidos = sorted((d for d in documentos if d.subido_por), key=lambda d: d.subido_en, reverse=True)
    semilla = sorted((d for d in documentos if not d.subido_por), key=lambda d: d.nombre_original)
    return subidos + semilla


def borrar(sesion: Session, almacen: VectorStore, documento_id: uuid.UUID, usuario: Usuario) -> None:
    documento = sesion.get(Documento, documento_id)
    if documento is None:
        raise DocumentoNoEncontrado()
    if documento.subido_por != usuario.id:
        raise SinPermiso()
    eliminar(sesion, almacen, documento)


def eliminar(sesion: Session, almacen: VectorStore, documento: Documento) -> None:
    """Borra vectores, fila y archivo, sin revisar permisos (lo usan borrar y la semilla)."""
    if documento.fragmentos:
        almacen.delete(ids=ids_de_fragmentos(documento.id, documento.fragmentos))
    sesion.delete(documento)
    sesion.commit()
    (_dir_subidas() / documento.nombre_archivo).unlink(missing_ok=True)
    log.info("documento borrado: %s", documento.titulo)


def reindexar(sesion: Session, almacen: VectorStore, documento: Documento) -> int:
    """Vuelve a calcular los vectores de un documento desde su copia en disco.

    Se usa al cambiar EMBEDDING_MODEL (cambia la dimensión de los vectores) o al cambiar
    la forma de fragmentar.
    """
    contenido = (_dir_subidas() / documento.nombre_archivo).read_bytes()
    fragmentos = _fragmentos_de(documento, extraccion.extraer(contenido, documento.tipo))
    if documento.fragmentos:
        almacen.delete(ids=ids_de_fragmentos(documento.id, documento.fragmentos))
    _indexar(almacen, documento, fragmentos)
    documento.fragmentos = len(fragmentos)
    sesion.commit()
    return len(fragmentos)
