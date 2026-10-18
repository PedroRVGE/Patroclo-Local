"""Pruebas de la sincronización de la semilla (`python -m app.semilla`).

Se comprueba la parte que no depende del modelo: que un archivo que desaparece de
conocimiento/ salga de la base con sus vectores, y que lo que subió un usuario desde el
frontend no se toque nunca.
"""

import uuid

from app.semilla import olvidar_borrados
from db.conexion import obtener_sesion
from db.modelos import Documento
from services import ingesta

MD = """---
titulo: Documento de prueba
visibilidad: publico
---

## Una sección

Texto cualquiera para que haya al menos un fragmento.
""".encode()


def _sesion(cliente):
    return next(cliente.app.dependency_overrides[obtener_sesion]())


def _archivos_en_vectores(almacen) -> set[str]:
    return {f.metadata["archivo"] for f in almacen.fragmentos.values()}


def test_archivo_borrado_de_la_carpeta_sale_de_la_base(cliente, almacen):
    sesion = _sesion(cliente)
    ingesta.ingerir(sesion, almacen, MD, "01-se-queda.md", subido_por=None)
    ingesta.ingerir(sesion, almacen, MD + b"\nOtro texto.\n", "02-se-va.md", subido_por=None)
    sesion.commit()
    assert _archivos_en_vectores(almacen) == {"01-se-queda.md", "02-se-va.md"}

    borrados = olvidar_borrados(sesion, almacen, {"01-se-queda.md"})
    sesion.commit()

    assert borrados == ["02-se-va.md"]
    assert [d.nombre_original for d in sesion.query(Documento).all()] == ["01-se-queda.md"]
    assert _archivos_en_vectores(almacen) == {"01-se-queda.md"}


def test_no_borra_lo_que_subio_un_usuario(cliente, almacen):
    sesion = _sesion(cliente)
    ingesta.ingerir(sesion, almacen, MD, "mio.md", subido_por=uuid.uuid4())
    sesion.commit()

    borrados = olvidar_borrados(sesion, almacen, set())  # como si la carpeta estuviera vacía
    sesion.commit()

    assert borrados == []
    assert [d.nombre_original for d in sesion.query(Documento).all()] == ["mio.md"]
    assert _archivos_en_vectores(almacen) == {"mio.md"}


def test_sin_cambios_no_borra_nada(cliente, almacen):
    sesion = _sesion(cliente)
    ingesta.ingerir(sesion, almacen, MD, "01-igual.md", subido_por=None)
    sesion.commit()

    assert olvidar_borrados(sesion, almacen, {"01-igual.md"}) == []
    assert sesion.query(Documento).count() == 1
