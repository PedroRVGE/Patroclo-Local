"""Paso 3 del flujo de ingesta: dividir el texto en fragmentos (chunks).

- **Markdown:** primero por encabezados (`#`, `##`, `###`) con MarkdownHeaderTextSplitter,
  para que cada receta o cada tema quede en su propio fragmento; después, si una sección
  pasa de 1000 caracteres, por caracteres (1000 con 200 de solapamiento).
- **Lo demás:** por caracteres, página por página (así cada fragmento sabe su página).

Cada fragmento empieza con una línea de contexto «Documento | Sección». Un fragmento que
dice solo «1. Corta el queso en cubos...» no sabe de qué receta es; con la línea de
contexto, el embedding (y el modelo, al leerlo) sí lo saben.
"""

from langchain_core.documents import Document
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

from services.extraccion import Extraido

TAMANO_FRAGMENTO = 1000
SOLAPAMIENTO = 200

_por_caracteres = RecursiveCharacterTextSplitter(chunk_size=TAMANO_FRAGMENTO, chunk_overlap=SOLAPAMIENTO)
_por_encabezados = MarkdownHeaderTextSplitter(
    headers_to_split_on=[("#", "h1"), ("##", "h2"), ("###", "h3")],
    strip_headers=False,  # el encabezado se queda en el texto: aporta significado
)


def fragmentar(extraido: Extraido, titulo: str, metadata_base: dict) -> list[Document]:
    """Devuelve los fragmentos listos para vectorizar, con su metadata.

    `metadata_base` (documento_id, nombre, visibilidad, tema, productos...) se copia en
    todos los fragmentos; aquí se añaden `pagina`, `seccion` y `fragmento` (posición).
    """
    if extraido.es_markdown:
        secciones = _por_encabezados.split_text(extraido.paginas[0].texto)
        piezas = []
        for seccion in secciones:
            # El h1 suele ser el título del documento: la sección útil es h2 › h3.
            ruta = " › ".join(seccion.metadata[h] for h in ("h2", "h3") if h in seccion.metadata)
            for trozo in _por_caracteres.split_text(seccion.page_content):
                piezas.append((trozo, None, ruta or None))
    else:
        piezas = [
            (trozo, pagina.numero, None)
            for pagina in extraido.paginas
            for trozo in _por_caracteres.split_text(pagina.texto)
        ]

    fragmentos = []
    for texto, pagina, seccion in piezas:
        if not texto.strip():
            continue
        contexto = f"Documento: {titulo}" + (f" | Sección: {seccion}" if seccion else "")
        fragmentos.append(
            Document(
                page_content=f"{contexto}\n\n{texto.strip()}",
                metadata={**metadata_base, "pagina": pagina, "seccion": seccion, "fragmento": len(fragmentos)},
            )
        )
    return fragmentos
