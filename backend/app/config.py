"""Configuración de Patroclo-Local, leída solo de variables de entorno.

Se usa pydantic-settings en vez de os.getenv suelto por tres razones:
  1. Valida tipos al arrancar (un puerto que no es número falla de una vez, no a mitad de una petición).
  2. Los secretos van en SecretStr: si alguien imprime la configuración, sale '**********'.
     (El error de referencias/agente/local_rag/config.py era imprimir la cadena con la contraseña.)
  3. Un solo lugar donde ver todas las variables del proyecto.
"""

from functools import lru_cache
from urllib.parse import quote_plus

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Configuracion(BaseSettings):
    model_config = SettingsConfigDict(
        # Corriendo fuera de Docker desde backend/, el .env está en la raíz del repo.
        # Dentro de Docker no hay archivo: compose pasa las variables con env_file.
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Base de datos (PostgreSQL + pgvector) ---
    postgres_user: str = "patroclo"
    postgres_password: SecretStr
    postgres_db: str = "patroclo"
    pg_host: str = "localhost"
    pg_puerto: int = 5435

    # --- Modelo local (Ollama) ---
    llm_provider: str = "ollama"
    ollama_url: str = "http://localhost:11434"
    chat_model: str = "qwen3.5:2b"  # elegido con app.evaluar: ver ESTADO.md, paso 4
    embedding_model: str = "bge-m3"
    # Mismo num_ctx en todas las llamadas: si cambia entre llamadas, Ollama recarga el modelo.
    num_ctx: int = 4096
    temperatura: float = 0.1
    # Cuánto tiempo deja Ollama el modelo cargado sin uso (su valor por defecto es 5 min;
    # recargar cuesta ~20 s, así que en la demo una pausa larga haría lenta la siguiente pregunta).
    ollama_keep_alive_s: int = 1800
    # Al arrancar la API, carga los dos modelos en segundo plano.
    precalentar_modelos: bool = True

    # --- Agente (RAG) ---
    # Distancia coseno máxima para aceptar un fragmento (menor = más parecido).
    # Calibrada con evaluacion/casos.json: ver ESTADO.md, paso 4.
    umbral_distancia: float = 0.50
    k_fragmentos: int = 4

    # --- Base de conocimiento ---
    coleccion: str = "patroclo_conocimiento"  # colección de PGVector
    conocimiento_dir: str = "../conocimiento"  # semilla (en Docker: /app/conocimiento)
    subidas_dir: str = "subidas"  # copia de cada documento indexado (para reindexar)
    tamano_maximo_mb: int = 10

    # --- Autenticación (JWT propio) ---
    # Sin valor por defecto a propósito: si falta en .env, la API no arranca.
    jwt_secreto: SecretStr = Field(min_length=32)
    jwt_horas: int = 8

    # --- API ---
    origen_frontend: str = "http://localhost:5173"
    # /docs y /openapi.json describen la API entera. Útiles en local; en el despliegue
    # público se apagan (MOSTRAR_DOCS=false).
    mostrar_docs: bool = True

    @property
    def url_base_datos(self) -> str:
        """Cadena de conexión para SQLAlchemy/psycopg. Nunca se registra en el log."""
        usuario = quote_plus(self.postgres_user)
        contrasena = quote_plus(self.postgres_password.get_secret_value())
        return f"postgresql+psycopg://{usuario}:{contrasena}@{self.pg_host}:{self.pg_puerto}/{self.postgres_db}"


@lru_cache
def obtener_configuracion() -> Configuracion:
    """Se lee una vez y se reutiliza (y en las pruebas se puede reemplazar)."""
    return Configuracion()
