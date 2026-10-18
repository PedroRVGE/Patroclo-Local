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
| 5 | `/api/chat` + historial | ⏳ siguiente |
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
