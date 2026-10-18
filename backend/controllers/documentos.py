"""Rutas de documentos: subir, listar y borrar. Todas protegidas."""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from langchain_core.vectorstores import VectorStore
from pydantic import BaseModel

from app.config import obtener_configuracion
from app.dependencias import SesionBD, UsuarioActual
from db.modelos import Documento, Usuario
from services import ingesta
from services.extraccion import ArchivoInvalido
from vectorstore.almacen import obtener_almacen

router = APIRouter(prefix="/api/documentos", tags=["documentos"])

Almacen = Annotated[VectorStore, Depends(obtener_almacen)]


class DocumentoPublico(BaseModel):
    id: uuid.UUID
    titulo: str
    nombre_original: str
    tipo: str
    tamano_bytes: int
    fragmentos: int
    visibilidad: str
    subido_en: datetime | None
    subido_por: str  # nombre de quien lo subió, o «Base inicial» para la semilla
    puede_borrar: bool


class RespuestaSubida(BaseModel):
    documento: DocumentoPublico
    nuevo: bool
    mensaje: str


def _publico(doc: Documento, usuario: Usuario) -> DocumentoPublico:
    return DocumentoPublico(
        id=doc.id,
        titulo=doc.titulo,
        nombre_original=doc.nombre_original,
        tipo=doc.tipo,
        tamano_bytes=doc.tamano_bytes,
        fragmentos=doc.fragmentos,
        visibilidad=doc.visibilidad,
        subido_en=doc.subido_en,
        subido_por=doc.autor.nombre if doc.autor else "Base inicial",
        puede_borrar=doc.subido_por == usuario.id,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
def subir(
    usuario: UsuarioActual,
    sesion: SesionBD,
    almacen: Almacen,
    response: Response,
    archivo: Annotated[UploadFile, File(description="PDF, TXT, MD, DOCX o CSV, máximo 10 MB")],
    visibilidad: Annotated[Literal["publico", "interno"] | None, Form()] = None,
) -> RespuestaSubida:
    """Recibe un archivo, lo procesa y lo indexa. Responde con el número de fragmentos.

    201 si se indexó; 200 si ese mismo contenido ya estaba (no se duplica).
    """
    limite = obtener_configuracion().tamano_maximo_mb * 1024 * 1024
    # Se lee un byte de más: si llega, el archivo pasa del límite (sin leerlo entero).
    contenido = archivo.file.read(limite + 1)
    try:
        resultado = ingesta.ingerir(sesion, almacen, contenido, archivo.filename or "", usuario.id, visibilidad)
    except ingesta.ArchivoMuyGrande:
        raise HTTPException(
            status.HTTP_413_CONTENT_TOO_LARGE,
            f"El archivo pasa del máximo de {obtener_configuracion().tamano_maximo_mb} MB.",
        ) from None
    except ArchivoInvalido as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from None

    doc = resultado.documento
    if resultado.nuevo:
        mensaje = (
            "Documento procesado: 1 fragmento indexado."
            if doc.fragmentos == 1
            else f"Documento procesado: {doc.fragmentos} fragmentos indexados."
        )
    else:
        response.status_code = status.HTTP_200_OK
        mensaje = f"Ese contenido ya estaba en la base («{doc.titulo}»). No se duplicó."
    return RespuestaSubida(documento=_publico(doc, usuario), nuevo=resultado.nuevo, mensaje=mensaje)


@router.get("")
def listar(usuario: UsuarioActual, sesion: SesionBD) -> list[DocumentoPublico]:
    return [_publico(d, usuario) for d in ingesta.listar(sesion)]


@router.delete("/{documento_id}", status_code=status.HTTP_204_NO_CONTENT)
def borrar(documento_id: uuid.UUID, usuario: UsuarioActual, sesion: SesionBD, almacen: Almacen) -> None:
    """Borra el documento y todos sus vectores. Solo quien lo subió."""
    try:
        ingesta.borrar(sesion, almacen, documento_id, usuario)
    except ingesta.DocumentoNoEncontrado:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El documento no existe.") from None
    except ingesta.SinPermiso:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Solo quien subió el documento puede borrarlo.") from None
