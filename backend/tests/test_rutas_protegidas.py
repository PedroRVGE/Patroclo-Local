"""Garantía de seguridad: ninguna ruta queda sin protección (PDF §2.1).

Recorre TODAS las rutas registradas en la app y llama a cada una sin token. Las únicas
que pueden responder algo distinto de 401 son las de la lista PUBLICAS. Si mañana alguien
agrega una ruta y se olvida de `usuario_actual`, esta prueba falla.
"""

import re

from app.main import app

PUBLICAS = {
    ("GET", "/health"),
    ("POST", "/api/auth/registro"),
    ("POST", "/api/auth/ingresar"),
}


def _rutas():
    # Se leen del esquema OpenAPI y no de app.routes: desde FastAPI 0.14x los routers
    # incluidos quedan envueltos en una clase privada y app.routes ya no los lista.
    # Límite conocido: una ruta con include_in_schema=False no aparecería aquí
    # (el proyecto no usa ninguna).
    for ruta, operaciones in app.openapi()["paths"].items():
        for metodo in operaciones:
            yield metodo.upper(), ruta


def test_la_lista_de_publicas_existe_de_verdad():
    assert PUBLICAS <= set(_rutas())


def test_todas_las_demas_rutas_exigen_token(cliente):
    protegidas = [(m, p) for m, p in _rutas() if (m, p) not in PUBLICAS]
    assert protegidas, "debería haber al menos una ruta protegida"
    for metodo, ruta in protegidas:
        # Rellena los parámetros de ruta ({id}) con un valor cualquiera.
        url = re.sub(r"\{[^}]+\}", "00000000-0000-0000-0000-000000000000", ruta)
        r = cliente.request(metodo, url)
        assert r.status_code == 401, f"{metodo} {ruta} respondió {r.status_code} sin token"
