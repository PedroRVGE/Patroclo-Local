"""Tablas propias de Patroclo (las de vectores las crea langchain-postgres).

Los id son UUID y no enteros consecutivos: así un id no revela cuántos usuarios hay ni
permite adivinar el siguiente.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Uuid, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Usuario(Base):
    __tablename__ = "usuario"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    correo: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    nombre: Mapped[str] = mapped_column(String(100))
    # Hash argon2id completo (incluye algoritmo, parámetros y sal). Nunca la contraseña.
    hash_contrasena: Mapped[str] = mapped_column(String(255))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TokenRevocado(Base):
    """Lista de JWT cerrados con /salir antes de expirar.

    Un JWT es válido por sí solo hasta su `exp`; para poder «cerrar sesión» de verdad se
    guarda su `jti` aquí. Basta con conservarlo hasta que expire: después ya no sirve.
    """

    __tablename__ = "token_revocado"

    jti: Mapped[str] = mapped_column(String(64), primary_key=True)
    expira_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
