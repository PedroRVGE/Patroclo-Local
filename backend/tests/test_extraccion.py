"""Pruebas de extracción y fragmentación (sin base de datos ni Ollama)."""

import io
from pathlib import Path

import pytest
from docx import Document as DocumentoWord

from services.extraccion import ArchivoInvalido, extraer
from services.fragmentacion import TAMANO_FRAGMENTO, fragmentar

RAIZ = Path(__file__).resolve().parents[2]
CONOCIMIENTO = RAIZ / "conocimiento"
PDF_DEMO = RAIZ / "demo-carga" / "guia-maridaje-vinos-quesos-de-cabra.pdf"

MD = """---
titulo: Receta de prueba
tema: receta
productos: [iberico]
visibilidad: publico
---

# Recetas de prueba

## Tostadas

Pan, queso ibérico y bocadillo.

## Ensalada

Rúgula, pera y láminas de ibérico.
"""


# --- Markdown y frontmatter ---

def test_frontmatter_va_a_metadata_y_sale_del_texto():
    e = extraer(MD.encode(), "md")
    assert e.metadatos["titulo"] == "Receta de prueba"
    assert e.metadatos["visibilidad"] == "publico"
    assert e.metadatos["productos"] == ["iberico"]
    assert "titulo:" not in e.paginas[0].texto
    assert not e.paginas[0].texto.lstrip().startswith("---")


def test_markdown_se_fragmenta_por_secciones_con_contexto():
    e = extraer(MD.encode(), "md")
    frags = fragmentar(e, "Receta de prueba", {"documento_id": "x"})
    secciones = [f.metadata["seccion"] for f in frags]
    assert "Tostadas" in secciones and "Ensalada" in secciones
    tostadas = next(f for f in frags if f.metadata["seccion"] == "Tostadas")
    assert tostadas.page_content.startswith("Documento: Receta de prueba | Sección: Tostadas")
    assert "Ensalada" not in tostadas.page_content  # cada receta en su fragmento
    assert all(f.metadata["documento_id"] == "x" for f in frags)
    assert [f.metadata["fragmento"] for f in frags] == list(range(len(frags)))


def test_toda_la_base_de_conocimiento_se_fragmenta_bien():
    archivos = [f for f in CONOCIMIENTO.glob("*.md") if f.name != "README.md"]
    assert len(archivos) == 16
    for archivo in archivos:
        e = extraer(archivo.read_bytes(), "md")
        assert e.metadatos.get("titulo"), archivo.name
        assert e.metadatos.get("visibilidad") in {"publico", "interno"}, archivo.name
        frags = fragmentar(e, e.metadatos["titulo"], {})
        assert frags, archivo.name
        # 1000 del splitter + la línea de contexto
        assert all(len(f.page_content) <= TAMANO_FRAGMENTO + 200 for f in frags), archivo.name
    interno = extraer((CONOCIMIENTO / "90-operacion-interna.md").read_bytes(), "md")
    assert interno.metadatos["visibilidad"] == "interno"


# --- PDF ---

def test_pdf_real_se_extrae_por_paginas():
    e = extraer(PDF_DEMO.read_bytes(), "pdf")
    assert len(e.paginas) >= 1
    assert "vino" in " ".join(p.texto for p in e.paginas).lower()
    assert e.metadatos["titulo"] == "Guía de maridaje: vinos y quesos de cabra"  # de las propiedades del PDF
    frags = fragmentar(e, "Guía", {})
    assert all(f.metadata["pagina"] >= 1 for f in frags)


def test_pdf_falso_se_rechaza():
    with pytest.raises(ArchivoInvalido, match="no es un PDF"):
        extraer(b"MZ\x90\x00 esto es un ejecutable renombrado", "pdf")


# --- DOCX ---

def _docx(*parrafos: str) -> bytes:
    doc = DocumentoWord()
    for p in parrafos:
        doc.add_paragraph(p)
    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


def test_docx_se_extrae():
    e = extraer(_docx("El queso crema de cabra viene en tarrina.", "Se unta en pan."), "docx")
    assert "tarrina" in e.paginas[0].texto


def test_docx_falso_se_rechaza():
    with pytest.raises(ArchivoInvalido, match="Word"):
        extraer(b"no soy un zip", "docx")


# --- CSV y texto ---

def test_csv_cada_fila_con_sus_columnas():
    e = extraer("queso;presentacion\nibérico;110 g\ncrema;tarrina 120 g\n".encode(), "csv")
    assert "queso: ibérico | presentacion: 110 g" in e.paginas[0].texto


def test_binario_con_extension_de_texto_se_rechaza():
    with pytest.raises(ArchivoInvalido, match="no es de texto"):
        extraer(b"\x00\x01\x02binario", "txt")


def test_texto_en_cp1252_se_lee():
    assert "lácteos" in extraer("lácteos de cabra".encode("cp1252"), "txt").paginas[0].texto


def test_archivo_vacio_se_rechaza():
    with pytest.raises(ArchivoInvalido, match="no tiene texto"):
        extraer(b"   \n  ", "txt")


def test_extension_no_permitida():
    with pytest.raises(ArchivoInvalido, match="Formato no permitido"):
        extraer(b"algo", "exe")
