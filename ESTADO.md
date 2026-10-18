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
| 3 | Ingesta: subir, listar, borrar, semilla | ✅ 17/10 |
| 4 | Grafo LangGraph + pruebas + calibrar umbral | ✅ 17/10 |
| 5 | `/api/chat` + historial | ✅ 17/10 |
| 6 | Frontend | ✅ 17/10 |
| 7 | Despliegue (frontend en la nube + ngrok) | ⏸️ **pendiente**: preparado, faltan las cuentas de Pedro (ver «Faltantes») |
| 8 | README, diagrama, capturas | 🟡 README y capturas para revisión (17/10); falta la sección de despliegue con URLs |

## Cómo está el entorno (17/10/2026)

| Pieza | Estado |
|---|---|
| Ollama | Contenedor **`ollama-gpu`** (no `ollama`), v0.32.15, puerto 11434, CUDA detecta la GTX 1650 (3,2 GB libres de 4 GB) |
| Modelos | **`qwen3.5:2b` (por defecto, paso 4)**, `qwen3.5:4b`, `llama3:latest` y `bge-m3` |
| Postgres | Contenedor `patroclo-postgres`, `pgvector/pgvector:pg16`, extensión `vector` 0.8.7, en `127.0.0.1:5435` |
| API | Contenedor `patroclo-api` en `127.0.0.1:8000`, o `uv run uvicorn app.main:app --reload` desde `backend/` |
| Python | 3.12.13 manejado por uv (`backend/.python-version`) |
| GitHub | https://github.com/PedroRVGE/Patroclo-Local — **público** desde el 17/10 (historial limpiado antes; ver «Limpieza antes de publicar») |

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

---

## Paso 3 — Ingesta de documentos (17/10/2026)

**Qué se hizo**

| Ruta / comando | Qué hace |
|---|---|
| `POST /api/documentos` (multipart: `archivo`, `visibilidad` opcional) | Valida, extrae, fragmenta, vectoriza y guarda. 201 «N fragmentos indexados»; 200 si ese contenido ya estaba |
| `GET /api/documentos` | Lista con título, tipo, fragmentos, visibilidad, quién lo subió y `puede_borrar` |
| `DELETE /api/documentos/{id}` | Borra fila, vectores y archivo. Solo quien lo subió (403 si no) |
| `python -m app.semilla` | Indexa `conocimiento/*.md` (sin el README). Corre al arrancar el contenedor |
| `python -m app.semilla --reindexar` | Recalcula todos los vectores (al cambiar `EMBEDDING_MODEL`) |

El flujo (PDF §2.4), archivo por archivo:

```text
recibir ──▶ validar (extensión, ≤10 MB, contenido) ──▶ sha256 ¿ya existe? ──sí──▶ devolver el existente
                                                              │ no
                                                              ▼
extraer (services/extraccion.py) ──▶ fragmentar (services/fragmentacion.py)
   ──▶ guardar copia en subidas/<uuid>.<ext> ──▶ embeddings bge-m3 + PGVector ──▶ fila `documento` ──▶ confirmar
                          (si algo falla aquí: se borran vectores y archivo, no queda la fila)
```

- **`services/extraccion.py`**: PDF (pypdf, por página), DOCX (python-docx, párrafos y
  tablas), MD (con frontmatter YAML → metadata), TXT y CSV (cada fila «columna: valor»).
  **Valida que el contenido cuadre con la extensión**: PDF empieza por `%PDF-`, DOCX es un ZIP
  con `word/document.xml`, los de texto no tienen bytes nulos. El título sale del
  frontmatter (MD) o de las propiedades del archivo (PDF/DOCX) y si no, del nombre.
- **`services/fragmentacion.py`**: Markdown por encabezados (`MarkdownHeaderTextSplitter`) y
  después 1000/200 por caracteres; lo demás 1000/200 por página. **Cada fragmento empieza
  con «Documento: … | Sección: …»**.
- **`vectorstore/almacen.py`**: `PGVector` (langchain-postgres) sobre el mismo engine de la
  app, con `OllamaEmbeddings(bge-m3)`, metadata en JSONB. **Ids deterministas
  `{documento_id}:{n}`**.
- **`services/ingesta.py`**: `ingerir`, `listar`, `borrar`, `eliminar`, `reindexar`.
- Metadata de cada fragmento: `documento_id`, `nombre` (título), `pagina`, `seccion`,
  `fragmento`, `visibilidad`, `tema`, `productos`.
- Tabla `documento`: id, nombre_original, titulo, tipo, sha256 (único), tamano_bytes,
  nombre_archivo (generado), subido_por (NULL = semilla), subido_en, fragmentos, visibilidad.
- Docker: `conocimiento/` montado en solo lectura y un volumen `patroclo-subidas` para las
  copias. Ollama caído → 503 «El modelo local no está disponible».
- 25 pruebas nuevas (**45 en total**): `test_extraccion.py` y `test_documentos.py`.

**Por qué así**

- **Ids deterministas en vez de `uuid4()` y nada de `pre_delete_collection`:** las dos
  referencias del profesor duplican fragmentos o borran la colección entera en cada
  ingesta. Con `{documento_id}:{n}` borrar un documento es borrar exactamente esos ids, y
  reindexar los reescribe.
- **Idempotencia por sha256 del contenido** (no por nombre): el mismo PDF con otro nombre
  tampoco se duplica.
- **Fragmentar por encabezados + línea de contexto:** la base está escrita en secciones `##`
  cortas (una receta, una pregunta frecuente). Así cada fragmento es una unidad de sentido, y
  el embedding de «1. Corta el queso…» sabe que es de las «Tostadas de ibérico».
- **Extraer con pypdf/python-docx directamente** y no con los loaders de
  langchain-community: se valida el contenido antes de escribir nada en disco, y se controla
  la metadata (frontmatter, título del PDF).
- **Se guarda copia del archivo** (con nombre generado, nunca el del usuario: evita rutas
  como `../../x`): sin ella no se podría reindexar al cambiar de modelo de embeddings.
- **Los documentos de la semilla no se pueden borrar desde la API** (`subido_por` NULL):
  ningún usuario puede dejar al agente sin su base de conocimiento.
- **Visibilidad por defecto `interno`** al subir (lo seguro), salvo que el usuario elija o
  el frontmatter diga otra cosa.
- **Reindexar es un comando, no un endpoint:** recalcula todo (≈1 min) y solo tiene sentido
  al cambiar de modelo; no debe poder dispararlo cualquier usuario.

**Cómo se probó**

- `uv run pytest` → **45 pruebas pasan** (PGVector reemplazado por un almacén falso en
  memoria): indexa y confirma fragmentos, ids y metadata correctos, nombre en disco generado
  (también con `../../etc/malicioso.md`), mismo archivo dos veces no duplica, visibilidad,
  extensión / PDF falso / sin extensión → 400, >10 MB → 413, **Ollama caído → 503 y no
  queda ni fila, ni vectores, ni archivo**, solo el dueño borra, la semilla no se borra.
- **Real (Docker + Postgres + bge-m3):**
  - Semilla: **16 archivos → 131 fragmentos** (125 `publico`, 6 `interno`), vectores de
    1024 dimensiones. El primer archivo tardó 61 s (carga en frío de bge-m3); los demás,
    2–5 s cada uno. Reiniciando el contenedor: «0 indexados ahora, 16 ya estaban».
  - Por la API con curl: sin token 401 → subir el PDF de la demo 201 «5 fragmentos» →
    subirlo otra vez 200 «no se duplicó» → borrarlo 204 → **0 vectores de la guía en la
    base**, de vuelta a 131 → borrar uno de la semilla 403 → PDF falso 400.
  - `--reindexar`: 16 documentos, 131 fragmentos, 57 s.

**Primera mirada a las distancias (material para calibrar el umbral en el paso 4)**

Distancia coseno de `similarity_search_with_score` (menor = más parecido), mejor resultado:

| Pregunta | Distancia | Fragmento |
|---|---|---|
| ¿El queso de cabra tiene lactosa? | 0,199 | La leche de cabra › ¿Tiene lactosa? |
| ¿Por qué el ibérico antes se llamaba Manchego? | 0,276 | Preguntas frecuentes › esa misma pregunta |
| ¿Qué vino va con el queso ibérico? (sin la guía) | **0,426** | Recetas con ibérico › Tostadas… (no habla de vino) |
| ¿Qué vino va con el queso ibérico? (con la guía) | 0,380 | Guía de maridaje, p. 1 |
| receta de sushi | 0,494 | Recetas con feta › Ensalada griega |
| ¿Cuál es la capital de Francia? | 0,632 | Queso crema › Un poco de historia |

**Conclusión:** el umbral separa bien lo ajeno (≥ 0,49) de lo bueno (≤ 0,35), pero **la
pregunta de vinos sin la guía cae en 0,43**: cerca de fragmentos del mismo tema que no la
responden. Un umbral solo no basta para rechazarla: hace falta el **nodo juez**
(`evaluar_contexto`). Es el mejor ejemplo para explicar en la sustentación por qué hay dos
controles y no uno.

**Qué falló y cómo se resolvió**

1. **Una prueba no compilaba:** un literal `b"""…"""` con tildes (los `bytes` solo admiten
   ASCII). Se cambió a `"""…""".encode()`.
2. **El PDF de la demo aparecía como «guia-maridaje-vinos-quesos-de-cabra»** (nombre del
   archivo). Se toma el título de las propiedades del PDF: ahora sale «Guía de maridaje:
   vinos y quesos de cabra».
3. **La consola de Windows (cp1252) no imprime «→» ni «›»** en scripts de prueba: se usa
   `PYTHONIOENCODING=utf-8`. Y **Git Bash reescribe rutas como `/app/subidas`** al pasarlas a
   `docker exec`: se antepone `MSYS_NO_PATHCONV=1`.
4. **Para saber qué excepción atrapar cuando Ollama falla** se probó en vivo: servidor caído →
   `ConnectionError`; modelo no descargado → `ollama.ResponseError`. Las dos se traducen a
   `ModeloNoDisponible` → 503.

**Pendiente (no bloquea):** límite de subidas por usuario; las subidas se procesan de forma
síncrona (un PDF grande deja la petición abierta mientras se calculan los embeddings).

---

## Paso 4 — El agente: grafo LangGraph, umbral y evaluación (17/10/2026)

**Qué se hizo**

`backend/agents/`, un archivo por responsabilidad:

| Archivo | Qué tiene |
|---|---|
| `estado.py` | `EstadoPatroclo` (TypedDict): pregunta, historial, pregunta_independiente, intencion, fragmentos, contexto_suficiente, respuesta, fuentes, rechazada, **pasos** (con reductor `operator.add`) |
| `prompts.py` | Todos los prompts + los dos mensajes fijos (rechazo literal y saludo) |
| `llm.py` | `crear_llm()` (Ollama, `reasoning=False`) y `limpiar()` (quita `<think>`) |
| `nodos.py` | `NodosPatroclo`: los 8 nodos como métodos; el decorador `@paso` mide cada uno y agrega `{nodo, detalle, ms}` |
| `grafo.py` | `construir_grafo()` con `StateGraph`, las 3 aristas condicionales y `crear_grafo_real()` |

El diagrama, generado desde el código, está en `docs/grafo.md`.

Scripts: `python -m app.calibrar_umbral` (distancias por caso, sin el modelo de chat) y
`python -m app.evaluar [--modelo X]` (los 20 casos contra el grafo real; guarda
`evaluacion/resultados-<modelo>.json`).

**Control de alucinaciones: 7 estrategias** (el PDF pide 2)

| # | Estrategia | Dónde | Quién decide |
|---|---|---|---|
| 1 | Umbral de distancia (0,50) | `recuperar_contexto` | código |
| 2 | LLM juez «¿el contexto trae el dato pedido?» | `evaluar_contexto` | modelo (1 palabra) → código |
| 3 | Prompt: solo el contexto, citar [n], nada propio | `generar_respuesta` | modelo |
| 4 | Rechazo con el mensaje literal | `rechazar` | código (texto fijo) |
| 5 | Fuentes con fragmento y similitud en la respuesta | `generar_respuesta` → UI | código |
| 6 | Clasificador que corta lo fuera de dominio antes de buscar | `clasificar_intencion` | modelo → código |
| 7 | Si el generador escribe `NO_SE`, se rechaza | arista `generar_respuesta → rechazar` | código |

Además: si el clasificador devuelve algo que no está en la lista → `PRODUCTO_LACTEO` (deciden
umbral y juez); si dice `FUERA_DE_DOMINIO` pero la pregunta nombra términos del dominio
(queso, cabra, feta, Del Pastor…) → el código lo corrige a `PRODUCTO_LACTEO`.
**Un fallo del modelo en un nodo de decisión nunca lleva a una respuesta inventada: siempre
cae del lado del rechazo o de una verificación más.**

**Por qué así**

- **Las decisiones (aristas) las toma código** leyendo el estado; el modelo solo llena el
  estado con una palabra. Es la separación del curso: el agente propone, el código controla.
- **Nodos como métodos de una clase que recibe sus dependencias** (modelo, base vectorial,
  función de guardado): las pruebas les pasan versiones falsas y la API las reales.
- **El juez y el generador comparten el mismo mensaje de sistema con el contexto.** Ollama
  reutiliza el prefijo ya procesado (caché KV): medido, 700 tokens de contexto pasan de 6 s
  a 0,5 s en la segunda llamada. El contexto se lee una sola vez por pregunta.
- **`reformular_pregunta` no llama al modelo si no hay historial**; **saludo y rechazo son
  textos fijos**. Una pregunta normal hace 2 llamadas (juez + respuesta) más la
  clasificación de una palabra.
- **El mismo `num_ctx` (4096) en todas las llamadas**: si cambia, Ollama recarga el modelo.
- **Sin checkpointer (`MemorySaver`)** como en `agente20262`: el historial va a Postgres
  (paso 5), que sobrevive a reinicios y lo puede listar el frontend. El grafo recibe el
  historial en el estado.
- **Distancia coseno y no similitud:** `similarity_search_with_score` de PGVector devuelve
  distancia (0 = idéntico). Al frontend se le muestra `similitud = 1 − distancia`.

**Calibración del umbral** (`python -m app.calibrar_umbral`, mejor fragmento por caso)

| Grupo | Distancias |
|---|---|
| Deben responderse (13, con H01 reformulada) | 0,199 – **0,418** (la peor: R02 «presentaciones de feta») |
| Rechazar, del tema pero sin el dato (X03 precio, X04 fundación, X05 vino, X06 receta propia) | 0,329 · 0,399 · 0,431 · 0,453 |
| Rechazar, fuera de dominio (X01 sushi, X02 Mundial) | **0,545** · 0,692 |

**Umbral elegido: 0,50** — 0,08 por encima del peor caso bueno y por debajo de lo ajeno.
**Lo que el umbral no puede hacer:** X03–X06 caen *dentro* (0,33–0,45), mezclados con las
buenas. Ningún umbral los separa sin perder respuestas buenas: los rechaza el juez. Es el
argumento para tener las dos estrategias.

**Sobre `fuente_esperada`:** en R01, R10, R11 y H01 la fuente esperada no sale entre los 4
primeros, pero los fragmentos que salen **sí responden** (p. ej. R01 encuentra la pregunta
frecuente «¿Qué quesos vende Del Pastor?»; R11 la sección «Cómo se hace un queso tipo feta»
de `05-…feta.md`). La base repite información entre archivos. Por eso el acierto se mide
por comportamiento y la fuente se reporta aparte. *Sugerencia para Pedro:* en `casos.json`,
R01 podría aceptar también `15-preguntas-frecuentes.md` y R11 `05-queso-tipo-griego-feta.md`
(no se editó: es material de evaluación ya escrito).

**Comparación de modelos** (`python -m app.evaluar --modelo …`, mismos 20 casos, mismos
prompts finales, umbral 0,50, k=4; detalle en `evaluacion/resultados-*.json`)

| | `qwen3.5:2b` | `qwen3.5:4b` |
|---|---|---|
| Comportamiento correcto | **20/20** | 19/20 (rechaza R11 «¿cómo se hace un feta?»: su juez es más estricto) |
| Rechazos correctos (X01–X06) | 6/6 | 6/6 |
| Fuente esperada entre las fuentes | 10/13 | 10/12 |
| Tiempo medio por respuesta | **14 s** | 50 s |
| En la GPU | 63 % | 48 % |
| Velocidad de generación | 13–17 tokens/s | ≈5 tokens/s |
| Calidad leída a mano | Correcta y citada; a veces agrega una inferencia propia (R06: «el caproico contribuye al color blanco», que no dice la base) y es menos completa (R09 sin «utensilios limpios») | Más precisa y completa (R03, R06, R09 impecables) |

**Decisión: `qwen3.5:2b` por defecto.** Mismo o mejor comportamiento, 3,5× más rápido (en
una demo de 7–10 min, 50 s por pregunta son demasiados) y sus fallos son del lado seguro.
*Trade-off aceptado:* redacta peor que el 4b y a veces agrega una inferencia pequeña. Para
volver al 4b basta `CHAT_MODEL=qwen3.5:4b` en `.env`. En `CLAUDE.md` §4 se actualizó el
modelo por defecto.

**Cómo se probó**

- `uv run pytest` → **62 pruebas pasan** (16 nuevas del grafo, con modelo y base falsos):
  cada camino (respuesta, saludo, fuera de dominio), umbral (descarta lejanos y no llama al
  juez), juez NO → rechazo sin generar, `NO_SE` → rechazo, clasificador confundido →
  no inventa, corrección por términos del dominio, `<think>` limpiado, «Sí.» con tilde,
  reformulación solo con historial y fallback si sale vacía, filtro `solo_publico`, pasos
  con detalle y ms.
- `uv run pytest -m integracion` → los 20 casos de `casos.json` contra Postgres + Ollama
  reales (comportamiento y mensaje literal; la fuente esperada solo avisa).
- `python -m app.evaluar` con los dos modelos (tablas de arriba).

**Qué falló y cómo se resolvió** (iteraciones con `app.evaluar` y `qwen3.5:2b`)

| Iteración | Resultado | Problema encontrado | Cambio |
|---|---|---|---|
| 1 | 14/20 (rechazos 6/6) | El clasificador mandó a FUERA_DE_DOMINIO «¿dónde pastorean las cabras de Del Pastor?» y «¿por qué el ibérico se llamaba Manchego?» | Ejemplos en el prompt + **corrección por código**: si nombra términos del dominio, no puede ser FUERA_DE_DOMINIO |
| 1 | | El juez rechazó R02, R10, R11 teniendo el dato: sus reglas del «NO» pesaban demasiado para un 2B | Juez redactado en positivo («SI si con el contexto se puede responder…»), la estrictez solo para el dato concreto que falta |
| 1 | | H01: la pregunta reescrita salió cortada («…para servir con él») | El reformulador usaba el modelo de decisión, limitado a 12 tokens: ahora usa el de respuesta |
| 2 | 19/20 | Leyendo las respuestas: H01 reescrita cambió la pregunta («¿qué *quesos* acompañan al ibérico?»); R06 agregó una causa inventada | Ejemplo de reescritura en el prompt (con otro queso, para no ajustar al caso) y regla «ni causas o conclusiones tuyas» |
| 2 | | R11 «¿cómo se hace un feta?» rechazada: el juez lo confundía con la regla de «fórmula exacta» (pensada para X06) | La regla dice ahora «fórmula de producción propia de la empresa»; un proceso general sí es respuesta |
| 3 | **20/20** | R06 aún agrega la frase del caproico | Limitación conocida del modelo de 2B; queda anotada |

Otros problemas:

1. **El 4b no cabe en la GPU** (3,4 GB de pesos, 3,2 GB libres): bajar `num_ctx` de 4096 a
   3072 no cambió nada (sigue 48 % GPU). La generación, no la lectura del prompt, es el
   cuello de botella: 200 tokens = 42 s.
2. **Se probó mover bge-m3 a la CPU** (`num_gpu=0`) para liberar la GPU: la pregunta se
   vectoriza en 0,2 s en CPU, pero el 2b siguió en 63 % GPU y la ingesta se volvía 5× más
   lenta (10 fragmentos en 19 s). **Descartado.**
3. **La fuente esperada no aparece en 3 de las respondidas** aunque la respuesta es correcta:
   la base repite información (ver arriba). Se reporta aparte en vez de contarla como fallo.
4. **`fuente_esperada` es un nombre de archivo y la metadata solo tenía el título:** se agregó
   `archivo` a la metadata de cada fragmento y se reindexó (57 s).
5. **Los scripts de evaluación corren desde el host** (`uv run`), no dentro del contenedor:
   `evaluacion/` no está montada en Docker (no hace falta en producción).

**Pendiente para el paso 5:** `guardar_historial` ya existe en el grafo pero recibe la
función de guardado desde afuera; la API la conectará con las tablas `conversacion` y
`mensaje`. Las respuestas del modelo 2b tardan ≈14 s: el frontend necesita el indicador
de «pensando».

---

## Paso 5 — `/api/chat` e historial persistente (17/10/2026)

**Qué se hizo**

| Ruta | Qué hace |
|---|---|
| `POST /api/chat` `{pregunta, conversacion_id?}` | Pasa la pregunta por el grafo. Responde `{respuesta, conversacion_id, fuentes[], pasos[], rechazada, tiempo_ms, con_historial}`. Sin `conversacion_id` abre una conversación nueva |
| `GET /api/conversaciones` | Las del usuario, la más reciente primero, con número de mensajes |
| `GET /api/conversaciones/{id}` | Todos los mensajes, con las fuentes y los pasos de cada respuesta |
| `DELETE /api/conversaciones/{id}` | Borra la conversación y sus mensajes (cascada) |

- Tablas `conversacion` (id, usuario_id, titulo, creada_en, actualizada_en) y `mensaje`
  (id, conversacion_id, rol, contenido, fuentes JSONB, pasos JSONB, rechazada, tiempo_ms,
  creado_en).
- `services/historial.py` (crear, obtener, últimos 6 mensajes para el grafo, guardar la
  interacción, listar, borrar) y `services/chat.py` (`responder()`: conversación →
  historial → grafo → respuesta).
- **El grafo se compila una sola vez** (`obtener_grafo()` con `lru_cache`). Lo que cambia por
  petición —cómo guardar en la sesión de base de datos de ESA petición— le llega al nodo
  `guardar_historial` por `config["configurable"]["guardar"]`, el mecanismo de LangGraph
  para pasar dependencias por ejecución.
- **Precalentamiento:** al arrancar, la API carga los dos modelos en un hilo aparte, y
  `keep_alive` de 30 min (antes, el de Ollama: 5 min).
- 10 pruebas nuevas en `test_chat.py` (**72 en total**).

**Por qué así**

- **Historial en Postgres, no en RAM ni en `MemorySaver`:** sobrevive a reinicios, se puede
  listar y borrar desde el frontend, y cada respuesta guardada conserva sus fuentes y
  pasos (al reabrir una conversación se ve todo igual).
- **Conversación ajena = 404, no 403:** no revela que existe.
- **Si el modelo falla, nada queda a medias:** la conversación nueva se crea con `flush()`
  (tiene id pero no está confirmada) y se confirma junto con los mensajes en
  `guardar_historial`. Si Ollama cae a mitad del grafo → `rollback()` y 503.
- **`creado_en` de los mensajes con la hora de Python, no `now()` de Postgres:** `now()`
  es la hora de *inicio de la transacción*, y la pregunta y la respuesta se guardan en la
  misma transacción: quedarían con la misma hora y su orden sería ambiguo.
- **Título = primera pregunta recortada a 80 caracteres:** sin otra llamada al modelo.
- **Solo los últimos 6 mensajes van al grafo:** con `num_ctx` 4096 y un modelo pequeño, más
  historial ocupa contexto y confunde al reformulador.

**Cómo se probó**

- `uv run pytest` → **72 pruebas pasan**. Las de chat usan el grafo real con el modelo y la
  base falsos: abre conversación y responde con fuentes, la interacción queda guardada
  (con fuentes, pasos y tiempo), el seguimiento usa el historial (el reformulador se llama
  solo la segunda vez), los rechazos también se guardan, **modelo caído → 503 y no queda
  ninguna conversación**, la conversación de otro da 404 en las tres rutas, borrar,
  conversación inexistente, validación (vacía, >1000 caracteres) y título recortado.
- La prueba que recorre todas las rutas ahora cubre también `/api/chat` y
  `/api/conversaciones` (401 sin token).
- **De punta a punta (Docker + Postgres + Ollama, `qwen3.5:2b`):**

| Pregunta | Resultado | Tiempo |
|---|---|---|
| ¿Qué es el queso ibérico de Del Pastor? (primera, modelos fríos) | Responde, 4 fuentes | 32 s (15 s cargando qwen, 6 s cargando bge-m3) |
| ¿Y con qué lo sirvo? (misma conversación) | Reformula con el historial y responde: tablas, tostadas con bocadillo, rallado sobre pasta | 12 s |
| ¿Qué vino va bien con el queso ibérico? | **Rechazo literal** (el juez dice NO) | 5 s |
| ¿El queso de cabra tiene lactosa? (primera tras reiniciar, **con precalentamiento**) | Responde y cita | **10,5 s** |

  Recorrido típico de una respuesta: clasificar 1,8 s → recuperar 0,15 s → juez 3 s →
  generar 6 s.

**Qué falló y cómo se resolvió**

1. **La primera pregunta tardaba 32 s** y Ollama descarga los modelos tras 5 min sin uso
   (en la demo, cualquier pausa haría lenta la siguiente pregunta). Se agregó
   `OLLAMA_KEEP_ALIVE_S=1800` a los dos modelos y el precalentamiento al arrancar (20 s, en
   segundo plano). La primera pregunta bajó a 10,5 s.
2. **`OllamaEmbeddings.keep_alive` solo acepta segundos (int)**, mientras que `ChatOllama`
   acepta también `"30m"`. Se usa un entero en los dos.
3. **El decorador `@paso` tapaba el parámetro `config`:** LangGraph decide si le pasa
   `config` a un nodo mirando su firma. Con `functools.wraps` la firma visible es la del
   nodo original, y la envoltura reenvía `**kwargs`.
4. **Probar con `curl` desde Git Bash daba 400** «error parsing the body»: la terminal le
   pasa las tildes en cp1252, no en UTF-8. No es un error de la API; se prueba con el JSON
   escrito en un archivo UTF-8 (`--data-binary @archivo`).

**Limitación conocida (para la sustentación):** el 2b a veces mezcla datos de fragmentos
cercanos. En «¿Qué es el queso ibérico de Del Pastor?» dijo que el ibérico «es una
Denominación de Origen Protegida» (la DOP es el Manchego). Las fuentes visibles permiten
detectarlo, y con `qwen3.5:4b` no pasa (50 s por respuesta). **Preguntas que el 2b responde
bien para la demo:** lactosa (R05), cabras y regiones (R07), pedido (R12), receta con queso
crema (R08), mantequilla blanca (R06), y el seguimiento «¿y con qué lo sirvo?».

---

## Paso 6 — Frontend (17/10/2026)

**Qué se hizo** — `frontend/`: React 19 + Vite 8 + TypeScript 5.9 + React Router 7. Sin
librerías de componentes: CSS propio con la identidad de quesería (crema, verde oliva,
terracota). Arranca con `npm run dev --prefix frontend` (o `preview_start` con
`.claude/launch.json`); la URL del backend sale de `VITE_API_URL`.

| Archivo | Qué hace |
|---|---|
| `src/api/cliente.ts` | Único lugar que conoce la URL; pone `Authorization: Bearer`; traduce errores (red caída, 401, 422 de pydantic, 503 del modelo) a mensajes en español |
| `src/api/tipos.ts` | Tipos espejo de las respuestas del backend |
| `src/sesion/Sesion.tsx` | Sesión: token en memoria + `sessionStorage`; al abrir la página valida el token con `/yo`; un 401 en cualquier llamada cierra la sesión |
| `src/App.tsx` | Rutas; `RutaProtegida` manda a `/ingresar` sin sesión (y vuelve a donde iba) |
| `src/paginas/Ingreso.tsx` | Ingresar / Crear cuenta, con validación (correo, nombre, 8–128 caracteres, confirmación) |
| `src/paginas/Chat.tsx` | Historial a la izquierda, mensajes, sugerencias, indicador «pensando… N s», Enter envía |
| `src/componentes/MensajeAsistente.tsx` | Respuesta + **Fuentes** desplegables (documento, sección/página, similitud %, fragmento) + **Recorrido por el grafo** (cada nodo con su detalle y tiempo) |
| `src/componentes/TextoRespuesta.tsx` | Markdown mínimo (negrita, listas) y citas `[n]` como botones que abren y resaltan la fuente |
| `src/paginas/Documentos.tsx` | Arrastrar y soltar, visibilidad, estado de la subida, lista con fragmentos, borrar (solo los propios) |
| `src/componentes/AvisoServicio.tsx` | Consulta `/health` cada 30 s y avisa si no hay backend, modelo o base |

**Por qué así**

- **`sessionStorage` y no `localStorage`:** la sesión dura lo que la pestaña; el token no
  queda guardado indefinidamente en el equipo. Al recargar, el token guardado se valida con
  `/yo` antes de confiar en él.
- **La respuesta del modelo nunca se inyecta como HTML** (`dangerouslySetInnerHTML`): un
  renderizador propio arma elementos de React. Si un documento cargado trae `<script>`, se
  ve como texto. Las citas a fuentes que no existen (`[7]` con 4 fuentes) se muestran como
  texto, sin vínculo inventado.
- **Validación en el navegador y otra vez en el backend:** la del navegador es para dar
  mensajes inmediatos; la que manda es la del servidor.
- **Rechazo distinto a la vista** (borde terracota y etiqueta «Sin información
  suficiente») y **recorrido del grafo visible**: en la sustentación se ve, pregunta por
  pregunta, qué nodo decidió qué (ej.: «4 de 4 pasan el umbral… juez: NO → rechazar»).
- **Cabecera `ngrok-skip-browser-warning`** en todas las llamadas: ngrok gratuito muestra una
  página de aviso a los navegadores, que rompería las llamadas a la API (paso 7). Se agregó a
  `allow_headers` del CORS del backend.
- **Sin librería de componentes:** menos dependencias y menos que explicar; el CSS son ~300
  líneas con variables de color.

**Cómo se probó** (navegador integrado contra el backend real en Docker con `qwen3.5:2b`)

| Prueba | Resultado |
|---|---|
| Abrir `/` sin sesión | Redirige a `/ingresar` |
| Crear cuenta con correo inválido, sin nombre, contraseña corta y sin confirmar | Los 4 mensajes de validación, sin llamar al backend |
| Ingresar con contraseña equivocada | «Correo o contraseña incorrectos.» (el mensaje genérico del backend) |
| Ingresar bien | Chat con las conversaciones anteriores en el historial |
| Sugerencia «¿Qué quesos vende Del Pastor?» | Indicador «pensando… N s», respuesta con 4 citas y 4 fuentes; la URL pasa a `/chat/<id>` |
| Clic en la cita `2` | Abre las fuentes y resalta la 2 |
| «¿Qué vino va bien con el queso ibérico?» | Rechazo con estilo propio; el recorrido muestra «4 de 4 pasan el umbral (0,43–0,44) → juez: NO → rechazar» |
| Subir un `.md` de prueba | «Documento procesado: 1 fragmento…»; 17 documentos / 132 fragmentos; solo él tiene «Borrar» |
| Preguntar por el dato que solo está en ese documento | Responde «viene en presentación de 50 g [1]» citándolo (5,6 s) |
| Borrarlo | «se borró de la base de conocimiento»; 16 / 131 y **0 vectores suyos en Postgres** |
| Cerrar sesión | `/salir` → 204 (token revocado), `sessionStorage` vacío, `/documentos` redirige a `/ingresar`, y tras ingresar vuelve a `/documentos` |
| Celular (375×812) | Encabezado y navegación adaptados; historial como panel con botón; tabla con desplazamiento propio |

**Qué falló y cómo se resolvió**

1. **«Chat» no se marcaba como activo con una conversación abierta** (`/chat/<id>`): el
   `NavLink` solo coincidía con `/` exacto. Ahora está activo en `/` y `/chat/*`.
2. **En el celular el botón «Cerrar historial» tapaba «+ Nueva conversación»**, y la «×»
   de borrar conversaciones solo aparecía con el puntero encima (no existe en una pantalla
   táctil). Espacio arriba del panel y «×» siempre visible en pantallas pequeñas.
3. **«1 fragmentos indexados»:** el backend ahora dice «1 fragmento indexado».
4. **La lista de documentos mostraba la semilla al revés** (90-… primero) porque ordenaba
   por fecha de subida. Ahora: subidos por usuarios primero (el más reciente arriba) y la
   semilla en el orden de sus archivos.
5. **El navegador integrado no puede elegir archivos del disco:** la subida se probó creando
   el archivo en memoria con JavaScript y pasándoselo al `<input type="file">` de la página;
   desde ahí el flujo es el real. **La demo con el PDF de `demo-carga/` hay que hacerla a
   mano** (arrastrarlo a la pantalla Documentos).
6. **TypeScript 7 (el compilador nativo nuevo) es la última versión en npm:** se fijó
   `typescript ~5.9`, más probada con Vite y los tipos de React. Y `FormEvent` está obsoleto
   en los tipos de React 19: se usa `SyntheticEvent`.

---

## Paso 7 — Despliegue: PREPARADO, PENDIENTE (17/10/2026)

**Ya está hecho**

- `docker-compose.yml`: servicio `ngrok` (imagen `ngrok/ngrok:3`) detrás del perfil
  **`publico`**. `docker compose up` no expone nada; para publicar hay que pedirlo:
  `docker compose --profile publico up -d`. Usa un **dominio fijo** (`NGROK_DOMAIN`) para
  que la URL del backend no cambie al reiniciar. El panel de ngrok queda solo en
  `http://127.0.0.1:4040`.
- `ORIGEN_FRONTEND` acepta varios orígenes separados por comas (local + nube); `*` se
  rechaza al arrancar. Pruebas en `tests/test_config.py`.
- `frontend/vercel.json`: todas las rutas sirven `index.html` (si no, recargar
  `/chat/<id>` daría 404) y cabeceras de seguridad (`nosniff`, `DENY` en iframes).
- El frontend ya manda `ngrok-skip-browser-warning` y el CORS del backend la acepta.
- `.env` tiene las líneas `NGROK_AUTHTOKEN=` y `NGROK_DOMAIN=` vacías, listas para llenar.

### ⏳ Faltantes

**Los hace Pedro (son sus cuentas y sus secretos; Claude no los maneja):**

- [ ] Cuenta gratuita en ngrok → copiar el **authtoken**
      (https://dashboard.ngrok.com/get-started/your-authtoken) a `NGROK_AUTHTOKEN` en `.env`.
- [ ] Reclamar el **dominio fijo gratuito** (https://dashboard.ngrok.com/domains) y ponerlo
      en `NGROK_DOMAIN` (sin `https://`).
- [ ] Cuenta gratuita en Vercel (con GitHub) y `npx vercel login` en una terminal.
- [ ] Hacer **público** el repositorio antes del domingo (el PDF pide enlace público):
      `gh repo edit PedroRVGE/Patroclo-Local --visibility public --accept-visibility-change-consequences`

**Después, con lo anterior listo:**

- [ ] `docker compose --profile publico up -d` y comprobar `https://<NGROK_DOMAIN>/health`.
- [ ] `npx vercel deploy --prod` desde `frontend/` con `VITE_API_URL=https://<NGROK_DOMAIN>`.
- [ ] Agregar la URL de Vercel a `ORIGEN_FRONTEND` y poner `MOSTRAR_DOCS=false`; reiniciar
      la API.
- [ ] Probar el flujo completo desde la URL de Vercel, **también desde el celular**.
- [ ] Anotar aquí y en el README las dos URLs públicas, las variables usadas y los problemas
      que salgan (PDF §3.5).

**Riesgos conocidos del despliegue (para el documento técnico):**

- **El PC de Pedro tiene que estar prendido** (con Docker y `ollama-gpu`) durante la demo.
- **Mientras ngrok esté arriba, cualquiera con la URL puede registrarse** y usar la GPU o
  subir documentos (el PDF exige registro abierto). Mitigación: ngrok solo durante pruebas y
  la sustentación (`docker compose stop ngrok` para apagarlo).
- ngrok gratuito muestra una página de aviso a los navegadores; la cabecera
  `ngrok-skip-browser-warning` la evita en las llamadas del frontend, pero abrir la URL de la
  API directamente en el navegador sí la muestra.

---

## Preparación para revisión de compañeros (17/10/2026)

- **`README.md`** completo para que otra persona entienda y corra el proyecto: qué cumple del
  enunciado, arquitectura (Mermaid), el grafo y los 7 controles, tecnologías, cómo correrlo
  en otro PC (incluido cómo levantar Ollama si no lo tienen), pruebas y evaluación,
  estructura, API, despliegue pendiente, limitaciones y una **guía de revisión** de 20–30 min.
- **`docs/capturas/`**: 5 capturas de la prueba del paso 6 (ingreso, respuesta con fuentes,
  rechazo con recorrido, documentos, celular).
- **Problema encontrado al escribir el README:** el valor de ejemplo de `JWT_SECRETO` en
  `.env.example` medía más de 32 caracteres, así que **quien copiara el archivo sin cambiarlo
  arrancaba la API con un secreto publicado en GitHub**. Ahora la configuración rechaza
  cualquier `POSTGRES_PASSWORD` o `JWT_SECRETO` que empiece por `<CAMBIAR` (prueba en
  `test_config.py`, que lee el `.env.example` real). **77 pruebas.**

---

## Limpieza antes de publicar el repositorio (17/10/2026)

Antes de hacer público el repositorio se auditó **todo el historial** (no solo los archivos
actuales), porque al publicarlo cualquiera puede ver cualquier commit viejo.

**Lo que se buscó y no apareció:** `.env` nunca se versionó; la contraseña de la base y el
secreto JWT reales no están en ningún commit; no hay tokens (GitHub, ngrok, claves de API),
rutas del PC ni la contraseña de la cuenta de prueba; `referencias/` nunca se subió.
**Publicar el código no expone el computador:** solo ngrok lo haría, y está detrás del
perfil `publico`; los puertos de la base y la API escuchan solo en `127.0.0.1`.

**Lo que se limpió (decisión de Pedro):**

- `conocimiento/90-operacion-interna.md` se reemplazó por una **guía interna de atención
  genérica**, marcada como documento de ejemplo. Sigue sirviendo para demostrar el filtro de
  visibilidad: el Patroclo interno la recupera (distancia 0,24 para «¿qué hago si un cliente
  reclama?») y con el filtro `solo_publico` no aparece.
- Se quitaron las menciones al sistema interno de la empresa y a su dominio en `CLAUDE.md` y
  en las fuentes de `conocimiento/`.
- La captura `docs/capturas/04-documentos.jpg` se volvió a tomar (mostraba el título viejo).
- En `evaluacion/resultados-qwen3.5-4b.json`, la respuesta de R12 citaba la versión vieja
  del documento interno: esa frase quedó **tachada con una nota visible** («Texto retirado al
  publicar el repositorio…»). No se reescribió la respuesta para no falsear el resultado; el
  conteo (19/20) no cambia.

**Cómo se reescribió el historial:**

1. Respaldo completo de la historia original en un `git bundle` (fuera del repositorio, en
   la carpeta temporal de la sesión).
2. `git-filter-repo` sobre un clon: las mismas reglas de reemplazo en **todas las versiones
   de todos los archivos**, y el `90` viejo y la captura vieja borrados de todo el historial;
   después, un commit que agrega las versiones limpias. El contenido final quedó idéntico al
   del repositorio de trabajo.
3. **Problema:** `git-filter-repo` aplica primero las reglas literales y después las de
   expresiones regulares, así que la regla general dejó variantes que las específicas ya no
   reconocían (en versiones viejas de `CLAUDE.md` y de las fuentes). Se encontró con una
   búsqueda en cada versión de cada archivo y se corrigió con una segunda pasada.
4. Verificación: 0 coincidencias de los términos retirados en las 12 versiones del
   historial y 0 objetos sueltos.
5. **El repositorio viejo de GitHub no se reescribió encima** (GitHub conserva un tiempo los
   commits viejos y se pueden abrir por su identificador): se renombró a
   `Patroclo-Local-respaldo-privado` (sigue **privado**) y se creó `Patroclo-Local` nuevo con
   el historial limpio. Pedro puede borrar el viejo desde GitHub cuando quiera.

Los identificadores de los commits cambiaron; por eso este archivo ya no cita commits por
su identificador.
