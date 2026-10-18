"""Paso 2 del flujo de ingesta (PDF §2.4): extraer el texto de un archivo.

Además de extraer, **valida que el contenido corresponda a la extensión**: un .pdf tiene
que empezar por `%PDF-`, un .docx tiene que ser un ZIP con `word/document.xml`, y un
.txt/.md/.csv tiene que ser texto. Así un ejecutable renombrado a .pdf no entra.

No usa los loaders de langchain-community: leyendo los bytes directamente se puede validar
antes de escribir nada en disco, y se controla qué metadata sale (p. ej. el frontmatter).
"""

import csv
import io
import re
import zipfile
from dataclasses import dataclass, field

import yaml
from docx import Document as DocumentoWord
from pypdf import PdfReader
from pypdf.errors import PdfReadError

EXTENSIONES_PERMITIDAS = {"pdf", "txt", "md", "docx", "csv"}

_FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)


class ArchivoInvalido(Exception):
    """El archivo no se puede procesar. El mensaje es apto para mostrarlo al usuario."""


@dataclass
class Pagina:
    texto: str
    numero: int | None = None  # solo los PDF tienen páginas


@dataclass
class Extraido:
    paginas: list[Pagina]
    es_markdown: bool = False
    # Del frontmatter YAML (.md: titulo, tema, productos, visibilidad...) o de las
    # propiedades del archivo (.pdf / .docx: titulo).
    metadatos: dict = field(default_factory=dict)


def validar_extension(extension: str) -> None:
    if extension not in EXTENSIONES_PERMITIDAS:
        raise ArchivoInvalido(
            f"Formato no permitido (.{extension or '?'}). Se aceptan: "
            + ", ".join(f".{e}" for e in sorted(EXTENSIONES_PERMITIDAS))
        )


def extraer(contenido: bytes, extension: str) -> Extraido:
    validar_extension(extension)
    extraido = {
        "pdf": _pdf,
        "docx": _docx,
        "md": _markdown,
        "txt": lambda c: Extraido([Pagina(_texto(c))]),
        "csv": _csv,
    }[extension](contenido)

    if not any(p.texto.strip() for p in extraido.paginas):
        raise ArchivoInvalido("El archivo no tiene texto que se pueda indexar.")
    return extraido


# --- Por formato ---

def _pdf(contenido: bytes) -> Extraido:
    if not contenido.startswith(b"%PDF-"):
        raise ArchivoInvalido("El archivo no es un PDF válido.")
    try:
        lector = PdfReader(io.BytesIO(contenido))
        paginas = [Pagina(p.extract_text() or "", numero=i) for i, p in enumerate(lector.pages, start=1)]
    except (PdfReadError, ValueError, KeyError) as e:
        raise ArchivoInvalido("No se pudo leer el PDF (¿está dañado o protegido?).") from e
    if not any(p.texto.strip() for p in paginas):
        raise ArchivoInvalido("El PDF no tiene texto extraíble (¿es una imagen escaneada?).")
    # El título de las propiedades del PDF, si lo tiene, es mejor nombre de fuente que el archivo.
    titulo = (lector.metadata.title or "").strip() if lector.metadata else ""
    return Extraido(paginas, metadatos={"titulo": titulo} if titulo else {})


def _docx(contenido: bytes) -> Extraido:
    try:
        with zipfile.ZipFile(io.BytesIO(contenido)) as z:
            if "word/document.xml" not in z.namelist():
                raise ArchivoInvalido("El archivo no es un documento de Word (.docx) válido.")
    except zipfile.BadZipFile:
        raise ArchivoInvalido("El archivo no es un documento de Word (.docx) válido.") from None

    doc = DocumentoWord(io.BytesIO(contenido))
    partes = [p.text for p in doc.paragraphs if p.text.strip()]
    for tabla in doc.tables:
        for fila in tabla.rows:
            partes.append(" | ".join(celda.text.strip() for celda in fila.cells))
    titulo = (doc.core_properties.title or "").strip()
    return Extraido([Pagina("\n\n".join(partes))], metadatos={"titulo": titulo} if titulo else {})


def _markdown(contenido: bytes) -> Extraido:
    texto = _texto(contenido)
    metadatos: dict = {}
    coincidencia = _FRONTMATTER.match(texto)
    if coincidencia:
        try:
            metadatos = yaml.safe_load(coincidencia.group(1)) or {}
        except yaml.YAMLError:
            raise ArchivoInvalido("El encabezado YAML (frontmatter) del Markdown está mal formado.") from None
        if not isinstance(metadatos, dict):
            metadatos = {}
        # El frontmatter se quita del texto: va a la metadata, no a los vectores.
        texto = texto[coincidencia.end():]
    return Extraido([Pagina(texto)], es_markdown=True, metadatos=metadatos)


def _csv(contenido: bytes) -> Extraido:
    """Cada fila se vuelve una línea «columna: valor | columna: valor»."""
    texto = _texto(contenido)
    try:
        dialecto = csv.Sniffer().sniff(texto[:4096], delimiters=",;\t|")
    except csv.Error:
        dialecto = csv.excel
    filas = list(csv.reader(io.StringIO(texto), dialecto))
    if len(filas) < 2:
        return Extraido([Pagina(texto)])
    encabezado, *datos = filas
    lineas = [
        " | ".join(f"{col.strip()}: {val.strip()}" for col, val in zip(encabezado, fila) if val.strip())
        for fila in datos
    ]
    return Extraido([Pagina("\n".join(l for l in lineas if l))])


def _texto(contenido: bytes) -> str:
    """Decodifica texto plano; rechaza binarios (bytes nulos)."""
    if b"\x00" in contenido[:8192]:
        raise ArchivoInvalido("El archivo no es de texto.")
    for codificacion in ("utf-8-sig", "cp1252"):
        try:
            return contenido.decode(codificacion)
        except UnicodeDecodeError:
            continue
    raise ArchivoInvalido("No se pudo leer el texto del archivo (codificación desconocida).")
