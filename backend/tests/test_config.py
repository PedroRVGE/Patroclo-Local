"""Pruebas de la configuración que afecta la seguridad."""

import pytest

from app.config import Configuracion


def _cfg(**kw) -> Configuracion:
    return Configuracion(postgres_password="x", jwt_secreto="s" * 40, _env_file=None, **kw)


def test_varios_origenes_separados_por_comas():
    cfg = _cfg(origen_frontend="http://localhost:5173, https://patroclo-local.vercel.app/")
    assert cfg.origenes_frontend == ["http://localhost:5173", "https://patroclo-local.vercel.app"]


def test_cors_nunca_acepta_comodin():
    with pytest.raises(ValueError, match="no puede ser"):
        _ = _cfg(origen_frontend="*").origenes_frontend


def test_secreto_jwt_corto_no_arranca():
    with pytest.raises(ValueError):
        Configuracion(postgres_password="x", jwt_secreto="corto", _env_file=None)


def test_no_arranca_con_los_valores_de_ejemplo_de_env_example():
    from pathlib import Path

    ejemplo = (Path(__file__).resolve().parents[2] / ".env.example").read_text(encoding="utf-8")
    valores = dict(l.split("=", 1) for l in ejemplo.splitlines() if "=" in l and not l.startswith("#"))
    with pytest.raises(ValueError, match="valor de ejemplo"):
        Configuracion(postgres_password=valores["POSTGRES_PASSWORD"], jwt_secreto="s" * 40, _env_file=None)
    with pytest.raises(ValueError, match="valor de ejemplo"):
        Configuracion(postgres_password="x", jwt_secreto=valores["JWT_SECRETO"], _env_file=None)


def test_los_secretos_no_salen_al_imprimir_la_configuracion():
    cfg = Configuracion(postgres_password="clave-de-la-base", jwt_secreto="secreto-jwt-" * 4, _env_file=None)
    impreso = f"{cfg!r} {cfg} {cfg.model_dump()}"
    assert "clave-de-la-base" not in impreso
    assert "secreto-jwt-" not in impreso
    assert "clave-de-la-base" in cfg.url_base_datos  # se usa, pero no se imprime
