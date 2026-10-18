"""Pruebas del flujo de autenticación: registro, ingreso, sesión activa y cierre."""

import uuid
from datetime import UTC, datetime, timedelta

import jwt
from sqlalchemy import select

from db.conexion import obtener_sesion
from db.modelos import Usuario
from tests.conftest import cabecera

MENSAJE_GENERICO = "Correo o contraseña incorrectos."


# --- Registro ---

def test_registro_devuelve_token_y_usuario_sin_hash(registrar):
    _, cuerpo = registrar()
    assert cuerpo["token"]
    assert cuerpo["tipo"] == "bearer"
    assert cuerpo["usuario"]["correo"] == "ana@ejemplo.com"
    assert "hash_contrasena" not in cuerpo["usuario"]
    assert "contrasena" not in str(cuerpo)


def test_la_contrasena_se_guarda_como_hash_argon2id(cliente, registrar):
    registrar()
    sesion = next(cliente.app.dependency_overrides[obtener_sesion]())
    usuario = sesion.scalar(select(Usuario))
    assert usuario.hash_contrasena.startswith("$argon2id$")
    assert "queso-de-cabra-1" not in usuario.hash_contrasena


def test_registro_duplicado_ignora_mayusculas(cliente, registrar):
    registrar(correo="ana@ejemplo.com")
    r = cliente.post(
        "/api/auth/registro",
        json={"correo": "  ANA@Ejemplo.com ", "nombre": "Otra", "contrasena": "otra-clave-123"},
    )
    assert r.status_code == 409


def test_registro_valida_campos(cliente):
    casos = [
        {"correo": "no-es-correo", "nombre": "Ana", "contrasena": "queso-de-cabra-1"},
        {"correo": "ana@ejemplo.com", "nombre": "Ana", "contrasena": "corta"},
        {"correo": "ana@ejemplo.com", "nombre": "   ", "contrasena": "queso-de-cabra-1"},
        {"correo": "ana@ejemplo.com", "nombre": "Ana", "contrasena": "x" * 129},
    ]
    for datos in casos:
        assert cliente.post("/api/auth/registro", json=datos).status_code == 422, datos


# --- Ingreso ---

def test_ingreso_correcto(cliente, registrar):
    datos, _ = registrar()
    r = cliente.post("/api/auth/ingresar", json={"correo": "ANA@ejemplo.com", "contrasena": datos["contrasena"]})
    assert r.status_code == 200
    assert r.json()["usuario"]["nombre"] == "Ana"


def test_ingreso_con_contrasena_mala_o_correo_inexistente_da_el_mismo_mensaje(cliente, registrar):
    registrar()
    mala = cliente.post("/api/auth/ingresar", json={"correo": "ana@ejemplo.com", "contrasena": "equivocada"})
    inexistente = cliente.post("/api/auth/ingresar", json={"correo": "nadie@ejemplo.com", "contrasena": "equivocada"})
    assert mala.status_code == inexistente.status_code == 401
    assert mala.json()["detail"] == inexistente.json()["detail"] == MENSAJE_GENERICO


# --- Sesión activa ---

def test_yo_con_token_valido(cliente, registrar):
    _, cuerpo = registrar()
    r = cliente.get("/api/auth/yo", headers=cabecera(cuerpo["token"]))
    assert r.status_code == 200
    assert r.json()["correo"] == "ana@ejemplo.com"


def test_yo_sin_token(cliente):
    r = cliente.get("/api/auth/yo")
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Bearer"


def test_token_alterado_no_sirve(cliente, registrar):
    _, cuerpo = registrar()
    token = cuerpo["token"]
    alterado = token[:-4] + ("AAAA" if not token.endswith("AAAA") else "BBBB")
    assert cliente.get("/api/auth/yo", headers=cabecera(alterado)).status_code == 401


def test_token_firmado_con_otro_secreto_no_sirve(cliente, registrar):
    _, cuerpo = registrar()
    ahora = datetime.now(UTC)
    falso = jwt.encode(
        {"sub": cuerpo["usuario"]["id"], "jti": "x", "iat": ahora, "exp": ahora + timedelta(hours=1)},
        "otro-secreto-que-no-es-el-de-la-api-123456",
        algorithm="HS256",
    )
    assert cliente.get("/api/auth/yo", headers=cabecera(falso)).status_code == 401


def test_token_sin_firma_alg_none_no_sirve(cliente, registrar):
    _, cuerpo = registrar()
    ahora = datetime.now(UTC)
    sin_firma = jwt.encode(
        {"sub": cuerpo["usuario"]["id"], "jti": "x", "iat": ahora, "exp": ahora + timedelta(hours=1)},
        None,
        algorithm="none",
    )
    assert cliente.get("/api/auth/yo", headers=cabecera(sin_firma)).status_code == 401


def test_token_expirado_no_sirve(cliente, registrar):
    import os

    _, cuerpo = registrar()
    hace_rato = datetime.now(UTC) - timedelta(hours=9)
    vencido = jwt.encode(
        {"sub": cuerpo["usuario"]["id"], "jti": "x", "iat": hace_rato, "exp": hace_rato + timedelta(hours=8)},
        os.environ["JWT_SECRETO"],
        algorithm="HS256",
    )
    assert cliente.get("/api/auth/yo", headers=cabecera(vencido)).status_code == 401


def test_token_de_usuario_inexistente_no_sirve(cliente):
    from services.tokens import crear_token

    token, _ = crear_token(uuid.uuid4())
    assert cliente.get("/api/auth/yo", headers=cabecera(token)).status_code == 401


# --- Cerrar sesión ---

def test_salir_revoca_el_token(cliente, registrar):
    datos, cuerpo = registrar()
    token = cuerpo["token"]

    assert cliente.post("/api/auth/salir", headers=cabecera(token)).status_code == 204
    # El mismo token ya no sirve, aunque no haya expirado...
    assert cliente.get("/api/auth/yo", headers=cabecera(token)).status_code == 401
    # ...pero volver a ingresar da uno nuevo que sí sirve.
    nuevo = cliente.post("/api/auth/ingresar", json={"correo": datos["correo"], "contrasena": datos["contrasena"]})
    assert cliente.get("/api/auth/yo", headers=cabecera(nuevo.json()["token"])).status_code == 200


def test_salir_sin_token(cliente):
    assert cliente.post("/api/auth/salir").status_code == 401
