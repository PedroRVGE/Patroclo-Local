"""Pruebas de /api/documentos con PGVector reemplazado por un almacén falso."""

import uuid
from pathlib import Path

from app.config import obtener_configuracion
from db.conexion import obtener_sesion
from db.modelos import Documento
from tests.conftest import cabecera

MD = """---
titulo: Quesos de prueba
visibilidad: publico
---

## El ibérico

Es el queso madurado.

## El crema

Es el untable.
""".encode()


def _subir(cliente, token, contenido=MD, nombre="quesos.md", **form):
    return cliente.post(
        "/api/documentos",
        headers=cabecera(token),
        files={"archivo": (nombre, contenido, "application/octet-stream")},
        data=form,
    )


def _sesion(cliente):
    return next(cliente.app.dependency_overrides[obtener_sesion]())


def test_subir_indexa_y_confirma_fragmentos(cliente, registrar, almacen):
    _, ana = registrar()
    r = _subir(cliente, ana["token"])
    assert r.status_code == 201, r.text
    cuerpo = r.json()
    assert cuerpo["nuevo"] is True
    doc = cuerpo["documento"]
    assert doc["titulo"] == "Quesos de prueba"  # del frontmatter
    assert doc["visibilidad"] == "publico"  # del frontmatter
    assert doc["fragmentos"] == 2 == len(almacen.fragmentos)
    assert doc["puede_borrar"] is True
    assert "2 fragmentos" in cuerpo["mensaje"]

    # Los ids en el almacén son «documento_id:n» y la metadata permite citar y filtrar.
    assert set(almacen.fragmentos) == {f"{doc['id']}:0", f"{doc['id']}:1"}
    meta = almacen.fragmentos[f"{doc['id']}:0"].metadata
    assert meta["documento_id"] == doc["id"]
    assert meta["nombre"] == "Quesos de prueba"
    assert meta["visibilidad"] == "publico"


def test_el_archivo_se_guarda_con_nombre_del_sistema(cliente, registrar):
    _, ana = registrar()
    doc_id = _subir(cliente, ana["token"], nombre="../../etc/malicioso.md").json()["documento"]["id"]
    doc = _sesion(cliente).get(Documento, uuid.UUID(doc_id))
    assert doc.nombre_original == "malicioso.md"  # sin la ruta
    assert doc.nombre_archivo == f"{uuid.UUID(doc_id).hex}.md"
    assert (Path(obtener_configuracion().subidas_dir) / doc.nombre_archivo).exists()


def test_mismo_archivo_dos_veces_no_duplica(cliente, registrar, almacen):
    _, ana = registrar()
    _, beto = registrar(correo="beto@ejemplo.com", nombre="Beto")
    primero = _subir(cliente, ana["token"]).json()
    segundo = _subir(cliente, beto["token"], nombre="otro-nombre.md")
    assert segundo.status_code == 200
    assert segundo.json()["nuevo"] is False
    assert segundo.json()["documento"]["id"] == primero["documento"]["id"]
    assert len(almacen.fragmentos) == 2
    assert len(cliente.get("/api/documentos", headers=cabecera(ana["token"])).json()) == 1


def test_visibilidad_por_defecto_es_interno(cliente, registrar):
    _, ana = registrar()
    r = _subir(cliente, ana["token"], contenido=b"El feta en bloque viene al vacio.", nombre="nota.txt")
    assert r.json()["documento"]["visibilidad"] == "interno"


def test_visibilidad_elegida_al_subir_manda(cliente, registrar):
    _, ana = registrar()
    r = _subir(cliente, ana["token"], contenido=b"Texto publico.", nombre="nota.txt", visibilidad="publico")
    assert r.json()["documento"]["visibilidad"] == "publico"
    assert _subir(cliente, ana["token"], contenido=b"x y z", nombre="b.txt", visibilidad="secreto").status_code == 422


def test_validaciones_de_archivo(cliente, registrar):
    _, ana = registrar()
    assert _subir(cliente, ana["token"], b"MZ...", "virus.exe").status_code == 400
    assert _subir(cliente, ana["token"], b"no es pdf", "falso.pdf").status_code == 400
    assert _subir(cliente, ana["token"], b"sin extension", "archivo").status_code == 400


def test_archivo_de_mas_de_10_mb(cliente, registrar):
    _, ana = registrar()
    grande = b"a" * (10 * 1024 * 1024 + 1)
    r = _subir(cliente, ana["token"], grande, "grande.txt")
    assert r.status_code == 413


def test_si_ollama_falla_no_queda_nada(cliente, registrar, almacen):
    _, ana = registrar()
    almacen.falla_con = ConnectionError("Failed to connect to Ollama")
    r = _subir(cliente, ana["token"])
    assert r.status_code == 503
    assert "modelo local no está disponible" in r.json()["detalle"]
    assert almacen.fragmentos == {}
    assert cliente.get("/api/documentos", headers=cabecera(ana["token"])).json() == []
    assert list(Path(obtener_configuracion().subidas_dir).glob("*")) == []


def test_listar_dice_quien_puede_borrar(cliente, registrar):
    _, ana = registrar()
    _, beto = registrar(correo="beto@ejemplo.com", nombre="Beto")
    _subir(cliente, ana["token"])
    lista = cliente.get("/api/documentos", headers=cabecera(beto["token"])).json()
    assert lista[0]["subido_por"] == "Ana"
    assert lista[0]["puede_borrar"] is False


def test_borrar_quita_documento_vectores_y_archivo(cliente, registrar, almacen):
    _, ana = registrar()
    doc_id = _subir(cliente, ana["token"]).json()["documento"]["id"]
    nombre_archivo = f"{uuid.UUID(doc_id).hex}.md"

    r = cliente.delete(f"/api/documentos/{doc_id}", headers=cabecera(ana["token"]))
    assert r.status_code == 204
    assert almacen.fragmentos == {}
    assert cliente.get("/api/documentos", headers=cabecera(ana["token"])).json() == []
    assert not (Path(obtener_configuracion().subidas_dir) / nombre_archivo).exists()


def test_solo_quien_subio_puede_borrar(cliente, registrar, almacen):
    _, ana = registrar()
    _, beto = registrar(correo="beto@ejemplo.com", nombre="Beto")
    doc_id = _subir(cliente, ana["token"]).json()["documento"]["id"]
    assert cliente.delete(f"/api/documentos/{doc_id}", headers=cabecera(beto["token"])).status_code == 403
    assert len(almacen.fragmentos) == 2


def test_documentos_de_la_semilla_no_se_pueden_borrar(cliente, registrar, almacen):
    from services import ingesta

    _, ana = registrar()
    semilla = ingesta.ingerir(_sesion(cliente), almacen, MD, "01-semilla.md", subido_por=None)
    r = cliente.delete(f"/api/documentos/{semilla.documento.id}", headers=cabecera(ana["token"]))
    assert r.status_code == 403
    lista = cliente.get("/api/documentos", headers=cabecera(ana["token"])).json()
    assert lista[0]["subido_por"] == "Base inicial"


def test_borrar_inexistente(cliente, registrar):
    _, ana = registrar()
    r = cliente.delete(f"/api/documentos/{uuid.uuid4()}", headers=cabecera(ana["token"]))
    assert r.status_code == 404
