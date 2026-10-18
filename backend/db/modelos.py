"""Tablas propias de Patroclo (las de vectores las crea langchain-postgres).

Los id son UUID y no enteros consecutivos: así un id no revela cuántos usuarios hay ni
permite adivinar el siguiente.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Uuid, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


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


class Documento(Base):
    """Un archivo de la base de conocimiento. Sus fragmentos viven en PGVector.

    El fragmento n de este documento tiene id `{documento.id}:{n}` en PGVector. Con eso
    se pueden borrar sus vectores sin buscarlos por metadata.
    """

    __tablename__ = "documento"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    nombre_original: Mapped[str] = mapped_column(String(255))
    # Lo que se muestra como nombre de la fuente: el `titulo` del frontmatter o el nombre del archivo.
    titulo: Mapped[str] = mapped_column(String(255))
    tipo: Mapped[str] = mapped_column(String(10))  # extensión: pdf, txt, md, docx, csv
    # Huella del contenido: el mismo archivo subido dos veces no se indexa dos veces.
    sha256: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    tamano_bytes: Mapped[int] = mapped_column(Integer)
    # Nombre en disco, generado por el sistema (nunca el que manda el usuario).
    nombre_archivo: Mapped[str] = mapped_column(String(100))
    # NULL = documento de la semilla (conocimiento/): nadie lo puede borrar desde la API.
    subido_por: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("usuario.id", ondelete="SET NULL"), nullable=True
    )
    subido_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    fragmentos: Mapped[int] = mapped_column(Integer, default=0)
    # publico | interno. Para el futuro mini-Patroclo de WhatsApp, que solo podrá
    # recuperar fragmentos `publico` (el filtro lo pondrá el código, no el prompt).
    visibilidad: Mapped[str] = mapped_column(String(10), default="interno")

    autor: Mapped["Usuario | None"] = relationship(lazy="joined")


class TokenRevocado(Base):
    """Lista de JWT cerrados con /salir antes de expirar.

    Un JWT es válido por sí solo hasta su `exp`; para poder «cerrar sesión» de verdad se
    guarda su `jti` aquí. Basta con conservarlo hasta que expire: después ya no sirve.
    """

    __tablename__ = "token_revocado"

    jti: Mapped[str] = mapped_column(String(64), primary_key=True)
    expira_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
