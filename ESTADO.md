# ESTADO — Patroclo-Local

Registro vivo de todo lo que se hace en el proyecto: qué se hizo, por qué así, qué falló y
cómo se resolvió. De aquí sale el apartado «problemas encontrados» del documento técnico
(PDF §5.2.14). **Se actualiza al terminar cada paso del §10 de `CLAUDE.md`.**

**Entrega:** domingo 18/10/2026 · **Sustentación:** miércoles 21/10/2026

## Avance (CLAUDE.md §10)

| # | Paso | Estado |
|---|---|---|
| 1 | Esqueleto: docker-compose, FastAPI con `/health`, `.env.example`, `.gitignore` | ✅ 17/10 |
| 2 | Autenticación completa y probada | ✅ 17/10 |
| 3 | Ingesta: subir, listar, borrar, semilla | ⏳ siguiente |
| 4 | Grafo LangGraph + pruebas + calibrar umbral | — |
| 5 | `/api/chat` + historial | — |
| 6 | Frontend | — |
| 7 | Despliegue (frontend en la nube + ngrok) | — |
| 8 | README, diagrama, capturas | — |

## Cómo está el entorno (17/10/2026)

| Pieza | Estado |
|---|---|
| Ollama | Contenedor **`ollama-gpu`** (no `ollama`), v0.32.15, puerto 11434, CUDA detecta la GTX 1650 (3,2 GB libres de 4 GB) |
| Modelos | `qwen3.5:4b`, `llama3:latest` y **`bge-m3`** (descargado hoy) |
| Postgres | Contenedor `patroclo-postgres`, `pgvector/pgvector:pg16`, extensión `vector` 0.8.7, en `127.0.0.1:5435` |
| API | Contenedor `patroclo-api` en `127.0.0.1:8000`, o `uv run uvicorn app.main:app --reload` desde `backend/` |
| Python | 3.12.13 manejado por uv (`backend/.python-version`) |
| GitHub | https://github.com/PedroRVGE/Patroclo-Local — **privado** por ahora; el PDF exige enlace público: `gh repo edit PedroRVGE/Patroclo-Local --visibility public --accept-visibility-change-consequences` antes del domingo |

---

## Paso 1 — Esqueleto (17/10/2026)

**Qué se hizo**

- `docker-compose.yml` con dos servicios: `postgres` (pgvector pg16, con
  `backend/db/init.sql` que crea la extensión `vector`) y `api` (build de `backend/`).
  **Ollama no está en el compose**: ya corre aparte con GPU y tiene los modelos; la API llega
  a él por `host.docker.internal:11434`.
- Backend FastAPI (Python 3.12 + uv) con la estructura del Anexo A:
  - `app/config.py`: toda la configuración por variables de entorno con **pydantic-settings**.
    La contraseña es `SecretStr`, así que imprimir la configuración nunca la muestra.
  - `app/errores.py`: manejador global; al cliente le llega `{detalle, id_error}`, nunca el
    traceback, que queda en el log con el mismo id.
  - `app/main.py`: CORS **solo** para `ORIGEN_FRONTEND` (nunca `*`), sin cookies.
  - `db/conexion.py`: un engine de SQLAlchemy + psycopg 3 (la misma pila que usa
    langchain-postgres).
  - `services/modelo_local.py`: pregunta a Ollama (`/api/tags`) qué modelos tiene.
  - `controllers/health.py`: `GET /health` revisa la base (y la versión de pgvector) y
    Ollama (y si los dos modelos configurados están descargados). Responde **200** si todo
    está bien y **503** si algo falla, sin filtrar mensajes internos.
  - `tests/test_health.py`: 3 pruebas con la base y Ollama simulados.
- `.env.example` documentado, `.env` local con contraseña aleatoria (no versionado),
  `.gitignore` (`.env`, `referencias/`, `node_modules`, `subidas/`, `.venv`).

**Por qué así**

- **Postgres en el puerto 5435 y solo en 127.0.0.1:** en el PC ya hay otros Postgres en
  5433 y 5434. Publicar solo en localhost evita exponer la base a la red local; hacia
  internet solo saldrá la API (por ngrok, paso 7).
- **pydantic-settings en vez de `os.getenv`:** valida tipos al arrancar y protege los
  secretos. Es la corrección directa del error de `referencias/agente/local_rag/config.py`.
- **`/health` con 503:** el frontend (y quien prepare la demo) puede distinguir «la API está
  viva» de «la API está viva pero el modelo o la base no».
- **Imagen Docker no-root** y dependencias en una capa aparte (se cachean mientras no
  cambie `uv.lock`).

**Cómo se probó**

- `uv run pytest` → 3 pruebas pasan.
- `/health` real fuera de Docker y dentro de Docker → `200`, `pgvector 0.8.7`, los dos
  modelos instalados. Desde el contenedor la API alcanza Ollama por `host.docker.internal`.

**Qué falló y cómo se resolvió**

1. **El contenedor de Ollama se llama `ollama-gpu`**, no `ollama` como decía `CLAUDE.md`.
   Se corrigió `CLAUDE.md` §4.
2. **Faltaba `bge-m3`**: `docker exec ollama-gpu ollama pull bge-m3`.
3. **uv no pudo instalar Python 3.12 desde Git Bash:** el enlace
   `cpython-3.12-windows-x86_64-none` quedó como symlink estilo Cygwin y no como junction de
   Windows («Missing expected target directory for Python minor version link»). Se borró ese
   enlace (el Python quedó intacto) y se reinstaló desde PowerShell. **Lección: en Windows,
   los comandos de uv que instalan Python se corren en PowerShell.**
4. **`python` en Git Bash es el alias de la Microsoft Store**, no un Python real. Se usa
   `backend/.venv/Scripts/python.exe` o `uv run python`.

**Medición inicial del modelo (dato para el paso 4 y el documento técnico)**

| Prueba | Resultado |
|---|---|
| `qwen3.5:4b` con `num_ctx=4096` | **3,7 GB → 52 % CPU / 48 % GPU** (no cabe entero en 4 GB de VRAM) |
| Primera llamada (carga en frío) | 104 s (52 s cargando, 52 s procesando el prompt) |
| Llamada en caliente, 64 tokens de salida | 17 s (≈ 4 tokens/s) |
| Respuesta a «¿qué es el feta?» sin RAG | Dice «de oveja (o vaca)», mezcla datos: ejemplo perfecto de por qué hace falta el RAG |

⚠️ **Riesgo para el paso 4:** el grafo hace hasta 4 llamadas al modelo por pregunta
(reformular, clasificar, juez, generar). A esta velocidad son 30–60 s por respuesta. Opciones
a evaluar entonces: salidas de una palabra en los nodos de decisión (pocos tokens), saltarse
`reformular` cuando no hay historial, bajar `num_ctx`, o probar un modelo más pequeño que
quepa entero en la GPU.

---

## Paso 2 — Autenticación (17/10/2026)

**Qué se hizo**

| Ruta | Protegida | Qué hace |
|---|---|---|
| `POST /api/auth/registro` | no | Crea la cuenta (`correo`, `nombre`, `contrasena`) y devuelve el token de una vez (201). Correo repetido → 409 |
| `POST /api/auth/ingresar` | no | Devuelve `{token, tipo, expira_en, usuario}`. Error → 401 «Correo o contraseña incorrectos.» |
| `GET /api/auth/yo` | **sí** | El usuario del token (sin el hash) |
| `POST /api/auth/salir` | **sí** | Revoca el token actual (204) |

- `db/modelos.py`: tablas `usuario` (id UUID, correo único, nombre, `hash_contrasena`,
  creado_en) y `token_revocado` (`jti`, expira_en). Se crean al arrancar la API
  (`crear_tablas()` en el *lifespan*, idempotente).
- `services/usuarios.py`: registro y verificación con **argon2id**.
- `services/tokens.py`: JWT HS256 con `sub`, `jti`, `iat`, `exp` (8 h), firmado con
  `JWT_SECRETO`; revocación guardando el `jti` hasta que expire.
- `app/dependencias.py`: `usuario_actual` / `sesion_actual`, que leen
  `Authorization: Bearer <token>`, verifican firma, expiración y revocación, y cargan el
  usuario. Cualquier fallo → 401 con `WWW-Authenticate: Bearer`.
- `app/errores.py`: si Postgres no responde → 503 «La base de datos no está disponible».
- `MOSTRAR_DOCS`: apaga `/docs` y `/openapi.json` en el despliegue público.
- 17 pruebas nuevas (20 en total): `tests/test_auth.py` y `tests/test_rutas_protegidas.py`.

**Por qué así**

- **JWT en cabecera y no cookie:** frontend y backend quedan en dominios distintos (hosting
  estático + túnel) y las cookies entre sitios se rompen en Safari.
- **Revocación con lista de `jti`:** un JWT vale por sí solo hasta su `exp`, así que «cerrar
  sesión» borrando el token solo en el navegador no lo invalida si alguien lo copió. Basta
  con guardar el `jti` hasta que expire; cada `/salir` limpia los ya vencidos.
- **Mismo mensaje y mismo tiempo para «correo inexistente» y «contraseña mala»:** cuando el
  correo no existe se verifica igual contra un hash falso, para que no se pueda averiguar
  qué correos están registrados midiendo el tiempo de respuesta.
- **`algorithms=["HS256"]` explícito** al verificar: bloquea el ataque `alg: none`, que
  tiene su propia prueba.
- **Contraseña de 8 a 128 caracteres:** el máximo evita que alguien mande textos enormes
  para gastar CPU en argon2.
- **ids UUID:** no revelan cuántos usuarios hay ni dejan adivinar el siguiente.
- **Las tablas se crean con `create_all` y no con Alembic (migraciones):** con 3 días de
  plazo y un esquema nuevo no hace falta migrar nada. *Trade-off:* si una tabla cambia, hay
  que borrarla o alterarla a mano. Para `../Patroclo/` (producción) sí harían falta
  migraciones.
- **El registro dice «ya existe una cuenta con ese correo»:** eso deja averiguar si un
  correo está registrado. Se acepta porque sin eso el usuario no entiende por qué falla;
  el ingreso, que es lo que se ataca por fuerza bruta, sí es genérico.

**Cómo se probó**

- `uv run pytest` → **20 pruebas pasan**: registro, validaciones (correo, nombre vacío,
  contraseña corta o larga), hash argon2id en la base, duplicado sin distinguir mayúsculas,
  mensaje genérico, token alterado, firmado con otro secreto, `alg: none`, expirado, de un
  usuario inexistente, y salir → el mismo token deja de servir.
- **`test_rutas_protegidas.py` recorre todas las rutas** de la app y exige 401 sin token,
  salvo `/health`, registro e ingreso. Se comprobó que sirve: agregando a propósito una
  ruta sin protección, la prueba falla («GET /api/olvidada respondió 200 sin token»).
- Contra el **Postgres real** (API en Docker, con curl): 201 → 409 → 401 → 200 → `/yo`
  200 → `/salir` 204 → `/yo` 401. En la base: el hash empieza por `$argon2id$` y queda 1
  fila en `token_revocado`. Quedó creado un usuario de prueba
  (`demo.patroclo@ejemplo.com`) en la base local.

**Qué falló y cómo se resolvió**

1. **La prueba de rutas protegidas no encontraba ninguna ruta.** Desde FastAPI 0.14x,
   `app.routes` ya no lista las rutas de los routers incluidos (quedan envueltas en una
   clase privada, `_IncludedRouter`). Se cambió para leerlas del esquema OpenAPI
   (`app.openapi()["paths"]`), que es la API pública. Límite: una ruta con
   `include_in_schema=False` no aparecería (no se usa ninguna).
2. **`email-validator` rechaza dominios reservados** como `.test`: la primera prueba con
   curl dio 422. No es un error del código; se probó con un dominio normal.

**Pendiente (no bloquea):** límite de intentos en `/ingresar` contra fuerza bruta. Por
ahora argon2 hace cada intento caro (~50–100 ms); se anota como mejora.
