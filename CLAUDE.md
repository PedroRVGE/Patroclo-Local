# Patroclo-Local — el agente experto en lácteos de cabra (trabajo del curso)

**Escrito el 17/10/2026** (§7 actualizado esa noche: la base de conocimiento ya está escrita). Este archivo es para la sesión de Claude Code que construye
Patroclo-Local. Léelo entero antes de escribir código.

> **Fechas que mandan sobre todo lo demás:**
> **domingo 18/10/2026 → se entrega el repositorio.** **Miércoles 21/10/2026 → sustentación
> en vivo (7–10 min).** Si algo no cabe, se recorta alcance — nunca los requisitos mínimos
> del §2.

---

## 1. Qué es esto

Patroclo-Local es el **trabajo final del curso de Implementación** (EIA, semestre 6):
una aplicación web completa —backend, frontend, autenticación, agente LangGraph, modelo
local, base vectorial, carga de documentos, despliegue— **exactamente como la pide
`docs/enunciado-trabajo-agente.pdf` (copia en texto: `docs/enunciado-trabajo-agente.txt`)**. Ese PDF es el enunciado: **léelo primero**.

**El tema:** un agente **experto en productos lácteos de leche de cabra**, el de **Alcanza
S.A.**, que los produce bajo la marca **Del Pastor**. Responde sobre:

- los cuatro quesos que vende la empresa, sus presentaciones y la línea a domicilio,
- la leche de cabra: qué tiene, en qué se diferencia de la de vaca,
- cómo se elabora cada tipo de queso (proceso general),
- el origen y la historia de cada estilo (feta, quesos madurados tipo manchego, queso crema) y por qué cambiaron los nombres,
- con qué platos funciona, recetas y cómo prepararlas, maridajes, conservación.

Todo **solo desde su base de conocimiento** (RAG). Si no está en los documentos, lo dice.

### Cómo encaja con lo demás

| Carpeta | Qué es | Modelo |
|---|---|---|
| **`Patroclo-Local/`** (aquí) | El trabajo del curso. Corre en el PC de Pedro. Cumple el PDF al pie de la letra | **Ollama, local** (obligatorio en el enunciado) |
| `../Patroclo/` | La versión de empresa, que después vivirá dentro del sistema interno de la empresa, con datos reales | API de Anthropic |
| `../PLAN-PATROCLO.md` | El diseño amplio de Patroclo (versión empresa). **Contexto, no requisitos de aquí** | — |
| `../CONTEXTO-PROYECTO.md` | Contexto general de la empresa (privado, fuera del repo). **Aquí solo sirve el §3 (productos)** | — |

**No construyas aquí nada de los sistemas internos de la empresa** ni conexión a sus
bases de datos. Eso es de `../Patroclo/`. Este proyecto no toca datos de la empresa.

Más adelante habrá un **mini-Patroclo de WhatsApp** que hable con clientes usando esta misma
base de conocimiento. **No se construye ahora**: aparece en el README y en la sustentación
como trabajo futuro. Lo único que se deja preparado desde ya es la columna `visibilidad`
(§6).

---

## 2. Requisitos mínimos — sin esto no se aprueba (PDF §6.1)

- [ ] Backend y frontend funcionales
- [ ] Autenticación implementada (registro, inicio de sesión, sesión activa, cerrar sesión; **ningún endpoint sin protección** salvo `/health`, registro e inicio de sesión)
- [ ] Agente construido con **LangChain + LangGraph** (grafo explícito, nada de drag-and-drop)
- [ ] **Modelo local** funcionando (Ollama)
- [ ] Base vectorial integrada y **carga de documentos desde el frontend** operativa
- [ ] Respuestas fundamentadas en el contexto recuperado
- [ ] **Rechazo explícito** cuando no hay información
- [ ] **Despliegue en la nube** y repositorio documentado

Rúbrica (PDF §6.2): Backend/API 15 · LangChain/LangGraph 15 · Arquitectura 10 · Seguridad
10 · RAG 10 · Alucinaciones 10 · Modelo local 8 · Documentación 8 · Carga de documentos 7 ·
Frontend 5 · Despliegue 2.

---

## 3. Los repositorios de referencia

En `referencias/` están los dos repos del profesor (Sebastián Zapata), **sin su `.git`**.
El commit exacto de cada uno está en `referencias/*.commit`. **`referencias/` va en el
`.gitignore`**: es material de consulta, no parte de nuestro repo.

| Repo | Qué aporta | Qué **no** copiar |
|---|---|---|
| `referencias/agente` (SinRodilla, **Ollama**) | El patrón base: `config.py`, `ingest.py` (loaders → `RecursiveCharacterTextSplitter` 1000/200 → `OllamaEmbeddings` → `PGVector`), `compose.yml` con pgvector + Ollama + **ngrok** para exponer la API, un esqueleto de grafo en `agentgraph.py` y la API FastAPI. `index2.html` son apuntes de clase sobre RAG (MMR, `fetch_k`) | **`agentgraph.py` tiene errores**: usa `Config.OLLAMA_MODEL` y `Config.OLLAMA_BASE_URL`, que no existen; mete `MessagesPlaceholder` dentro de una tupla. `config.py` **imprime la cadena de conexión con la contraseña**. CORS `*` con credenciales. Sesiones en RAM. Cada ingesta **duplica** los fragmentos |
| `referencias/agente20262` (**OpenAI**) | El grafo LangGraph con `ToolNode` + `MemorySaver` y arista condicional; la respuesta con **`pasos`** del agente y `tiempo_ms` (útil para mostrar en el frontend); `config.py` bien hecho con variables de entorno; README con la advertencia de no versionar `.env` | `pre_delete_collection=True` **borra toda la colección en cada ingesta** (incompatible con subir documentos uno a uno). El prompt de sistema tiene una personalidad inapropiada: **no lo reuses**. Python 3.14 (pocas ruedas precompiladas: usa 3.12) |

**Ninguno de los dos tiene:** autenticación, subida de archivos desde el frontend, listar y
borrar documentos, historial persistente, umbral de similitud, nodo evaluador del contexto
ni frontend. **Eso es lo que construimos encima.**

---

## 4. El equipo de Pedro, y qué implica

**Windows · NVIDIA GTX 1650 (4 GB de VRAM) · ~20 GB de RAM.**

- Un modelo de 7–8B (≈4,7 GB) **no cabe** en 4 GB: se reparte con la RAM y va lento. Por
  eso el modelo por defecto es pequeño: **`qwen3.5:2b`** (decidido en el paso 4 midiendo
  con `app.evaluar`; ver la tabla de abajo).
- **Ollama corre en Docker**, en un contenedor aparte llamado **`ollama-gpu`** que Pedro ya tiene
  (volumen `ollama`, puerto 11434). Va **con GPU** (`docker run --gpus=all ...`; Docker
  Desktop en Windows pasa la GPU por WSL2). **No lo metas en el `docker-compose` del
  proyecto ni lo recrees**: ya tiene los modelos descargados. La API llega a él por
  `http://host.docker.internal:11434` cuando corre en Docker, o por `http://localhost:11434`
  cuando corre fuera. Que sea configurable con `OLLAMA_URL`.
- Para ver los modelos: `docker exec ollama-gpu ollama list`. Para ver si un modelo cargó en la
  GPU: `docker exec ollama-gpu ollama ps` (columna PROCESSOR: debe decir `100% GPU`).

**Modelos instalados (17/10/2026):** `qwen3.5:2b` (descargado en el paso 4), `qwen3.5:4b`,
`llama3` y `bge-m3` (descargado en el paso 1). Ninguno de los de chat cabe entero en la GPU
(el 4b queda 48 % en GPU, el 2b 63 %).

| Uso | Por defecto | Alternativa para comparar |
|---|---|---|
| Chat | **`qwen3.5:2b`**: 20/20 casos, ≈14 s por respuesta | `qwen3.5:4b`: 19/20, ≈50 s por respuesta, redacta mejor. `llama3` (8B) no se evaluó: más lento aún |
| Embeddings | `bge-m3` (multilingüe, dimensión 1024) | `nomic-embed-text` (más ligero, pensado para inglés) |

**Ojo con el razonamiento de Qwen:** los Qwen recientes pueden «pensar» antes de responder
(bloques `<think>…</think>`), lo que multiplica el tiempo de respuesta y ensucia la salida de
los nodos de decisión. **Desactívalo** (en `ChatOllama`, el parámetro de razonamiento/`think`
según la versión instalada de `langchain-ollama`) y, por si acaso, limpia cualquier bloque
`<think>` de la salida antes de usarla.

**Memoria de video:** el modelo de chat (~3 GB) y `bge-m3` (~1,2 GB) pueden no caber juntos en
4 GB; Ollama descarga y recarga entre llamadas y eso suma segundos. Mídelo; si molesta, deja
un solo modelo cargado a la vez o anota la limitación.

Ambos se configuran por variable de entorno (`CHAT_MODEL`, `EMBEDDING_MODEL`). **Cambiar el
modelo de embeddings obliga a volver a indexar** (cambia la dimensión): deja un comando para
eso.

Mide y anota (para el documento técnico, PDF §3.2: «qué limitaciones encontraron»): tiempo
de respuesta, VRAM usada y calidad con 2–3 modelos sobre las mismas preguntas de prueba.

---

## 5. La arquitectura

```text
Navegador ── Frontend React + Vite (desplegado: Vercel / Netlify / Cloudflare Pages)
                │  Authorization: Bearer <JWT>
                ▼
Backend FastAPI  (PC de Pedro, docker compose, expuesto con ngrok o Cloudflare Tunnel)
 ├─ auth        registro, ingreso, yo, salir
 ├─ chat        pregunta → grafo LangGraph → respuesta + fuentes + pasos
 ├─ documentos  subir · listar · borrar   (reindexar: comando `python -m app.semilla --reindexar`)
 ├─ historial   conversaciones y mensajes del usuario
 └─ agente      grafo LangGraph ──▶ Ollama (contenedor `ollama-gpu` con GPU, ya existente)
                     │
                     ▼
PostgreSQL 16 + pgvector (docker)  — vectores, usuarios, documentos, historial
```

**Despliegue** (es requisito mínimo): el frontend va a un hosting estático en la nube; el
backend corre en el PC de Pedro y se publica con **ngrok**, que es el mismo patrón del repo
del profesor (`referencias/agente/compose.yml`). Documenta la URL pública de los dos, las
variables de entorno y los problemas que salgan (PDF §3.5). **El PC tiene que estar prendido
durante la demo**: anótalo como limitación conocida.

### Estructura del repo (PDF Anexo A, ajustada)

```text
Patroclo-Local/
├── backend/
│   ├── app/            main.py (FastAPI), config.py, dependencias, errores
│   ├── controllers/    routers: auth, chat, documentos, historial, health
│   ├── services/       lógica: usuarios, ingesta, historial
│   ├── agents/         el grafo: estado, nodos, prompts, construcción
│   ├── vectorstore/    PGVector, embeddings, búsqueda con puntaje
│   ├── db/             modelos y conexión (SQLAlchemy o psycopg)
│   ├── tests/          pruebas del grafo y de la API
│   ├── pyproject.toml  (uv, Python 3.12)
│   └── Dockerfile
├── frontend/           React + Vite + TypeScript
├── conocimiento/       la base de conocimiento inicial — ya escrita (§7)
├── demo-carga/         el PDF que se sube en vivo en la demo — no se indexa (§7)
├── evaluacion/         casos.json: 20 casos de prueba ya escritos (§7, §8)
├── docs/               arquitectura, documento técnico, diapositivas, capturas
├── referencias/        repos del profesor — en .gitignore
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## 6. El backend

**FastAPI + Python 3.12 + uv.** Dependencias base como en las referencias: `langchain`,
`langgraph`, `langchain-ollama`, `langchain-postgres`, `langchain-community`,
`langchain-text-splitters`, `psycopg[binary]`, `pypdf`, `python-dotenv`. Además:
`python-docx` (DOCX), `argon2-cffi` (contraseñas), `pyjwt`, `python-multipart` (subidas).

### Autenticación — implementación propia (el PDF lo permite)

- Tabla `usuario`: correo único, nombre, `hash_contrasena` (**argon2id**), creado_en.
- `POST /api/auth/registro`, `POST /api/auth/ingresar` → **JWT** firmado (HS256, secreto en
  `.env`, expira en 8 h, con `jti`). `GET /api/auth/yo`. `POST /api/auth/salir` → guarda el
  `jti` en una tabla de revocados hasta que expire.
- **Por qué JWT en cabecera y no cookie:** el frontend y el backend quedan en dominios
  distintos (hosting estático + túnel), y las cookies entre sitios se rompen en Safari.
  Un proyecto anterior ya pagó ese error. Queda escrito en el documento técnico.
- Una dependencia `usuario_actual` en **todas** las rutas salvo `/health`, registro e
  ingreso. Mensaje de error de ingreso genérico («correo o contraseña incorrectos»).

### Documentos

- `POST /api/documentos` (multipart): **PDF, TXT, MD, DOCX, CSV**; máximo 10 MB; la
  extensión **y** el contenido deben cuadrar; el nombre en disco lo genera el sistema.
- **Idempotente por sha256**: el mismo archivo dos veces no crea fragmentos duplicados
  (devuelve el existente).
- Flujo del PDF §2.4: recibir → extraer → fragmentar (1000/200) → embeddings → guardar →
  confirmar. Responde con el número de fragmentos.
- Tabla `documento`: id, nombre original, tipo, sha256 único, tamaño, `subido_por`,
  subido_en, fragmentos, `visibilidad` (`publico` | `interno`, por defecto `interno`).
  **`visibilidad` es para el futuro mini-Patroclo de WhatsApp**: él solo podrá recuperar
  fragmentos `publico`, y el filtro lo pondrá el código, no el prompt.
- Cada fragmento en PGVector lleva en su metadata `documento_id`, `nombre`, `pagina` y
  `visibilidad`, para poder **citarlo** y **borrarlo**.
- `GET /api/documentos` lista; `DELETE /api/documentos/{id}` borra el documento **y sus
  vectores** (solo quien lo subió).
- Un script `python -m app.semilla` indexa `conocimiento/` al arrancar (el contenedor lo
  corre antes de uvicorn). Es idempotente: lo que ya está no se toca y un archivo que cambió
  se reemplaza. `--reindexar` recalcula todos los vectores (al cambiar `EMBEDDING_MODEL`).
  Los documentos de la semilla tienen `subido_por` NULL y no se pueden borrar desde la API.

### Historial

Tablas `conversacion` (id, usuario_id, título, creada_en) y `mensaje` (id, conversacion_id,
rol, contenido, fuentes JSON, pasos JSON, rechazada bool, tiempo_ms, creado_en).
`GET /api/conversaciones`, `GET /api/conversaciones/{id}`, `DELETE /api/conversaciones/{id}`.
**Persistente en Postgres**, no en RAM como las referencias. Cada usuario solo ve las suyas.

### Chat

`POST /api/chat` `{ pregunta, conversacion_id? }` →
`{ respuesta, conversacion_id, fuentes: [{documento, pagina, fragmento, similitud}], pasos: [...], rechazada, tiempo_ms }`.
Los `pasos` (idea de `agente20262`) son el recorrido por los nodos del grafo: el frontend los
muestra y sirven para explicar el grafo en la sustentación.

### Lo demás

- Configuración solo por variables de entorno; **nunca imprimir secretos** (el error de
  `referencias/agente/local_rag/config.py`).
- CORS solo para el origen del frontend (`ORIGEN_FRONTEND`), nunca `*`.
- Errores: nunca devolver el traceback; un mensaje claro y un id para buscar en el log.
- Si Ollama no responde: error explícito «el modelo local no está disponible», no un 500
  genérico.

---

## 7. La base de conocimiento inicial (`conocimiento/`) — YA ESTÁ ESCRITA

**La escribió otra sesión de Claude el 17/10/2026**, a partir de `https://delpastor.com/`,
del §3 de `../CONTEXTO-PROYECTO.md` y de fuentes públicas citadas al final de cada archivo.
**No reescribas su contenido.** Si encuentras un error, avísale a Pedro.

**Lee primero `conocimiento/README.md`**: explica el formato y las reglas. Lo esencial:

- **16 archivos Markdown** (`01-…` a `15-…` públicos, `90-operacion-interna.md` interno). El
  `README.md` de la carpeta **no se indexa**.
- Cada archivo empieza con **frontmatter YAML** (`titulo`, `tema`, `productos`,
  `visibilidad`, `fuentes`, `actualizado`). **La ingesta debe parsearlo, copiar `titulo`,
  `tema`, `productos` y `visibilidad` a la metadata de cada fragmento, y quitarlo del texto
  que se vectoriza.** El `titulo` es lo que el frontend muestra como nombre de la fuente.
- Los archivos están escritos con secciones `##` cortas: conviene fragmentar respetando los
  encabezados Markdown (p. ej. `MarkdownHeaderTextSplitter` y después el splitter por
  caracteres) para que cada receta o cada tema quede en un fragmento propio.
- `90-operacion-interna.md` existe para **demostrar el filtro de `visibilidad`**: Patroclo lo
  puede usar; el futuro mini-Patroclo de WhatsApp no.

**Hechos del dominio que el agente debe tener claros** (todos están en la base):

- Del Pastor vende **cuatro quesos de cabra**: **queso tipo griego (antes feta)** —frasco de
  200 g en salmuera—, **queso feta en bloque** —500 g al vacío, para cocinas profesionales—,
  **queso ibérico de cabra (antes Manchego)** —110 g y 500 g al vacío— y **queso crema de
  cabra** —tarrina de 120 g—. Además, una línea a domicilio: leche, yogur, mantequilla, helados
  y pastelería de cabra.
- **«Manchego» y «Feta» son denominaciones de origen protegidas** (de oveja de La Mancha y
  de Grecia). Por eso los nombres «antes Manchego» y «antes feta».
- **Nada de precios, NIT, PLU ni clientes** en la base. Para precios y pedidos, el agente
  remite al WhatsApp **+57 300 998 5423** o a **comercial@delpastor.com** (eso sí está en la base).
- **Lo que no se sabe no está** (año de fundación, fundadores, nombre de la finca) y el
  agente debe decir que no lo sabe.

### `demo-carga/` — NO se indexa en la semilla

Tiene `guia-maridaje-vinos-quesos-de-cabra.pdf`, que se **sube en vivo desde el frontend**
en la sustentación. La semilla no tiene nada de vinos a propósito: antes de subirlo,
«¿qué vino va con el ibérico?» se rechaza; después, se responde citando la guía. Ver
`demo-carga/README.md`.

### `evaluacion/casos.json` — los casos de prueba

**20 casos ya escritos** contra esta base: 12 que deben responderse (con la fuente esperada
y las ideas que deben aparecer), 6 que deben rechazarse (incluye precio, fundación de la
marca, receta propia y el de vinos antes de la carga), un saludo y un seguimiento que
necesita historial. **Úsalos** para las pruebas del grafo, para calibrar el umbral y para
comparar modelos (§4, §8).

## 8. El agente — el grafo de LangGraph

Sigue el flujo del PDF §3.1 y el Anexo B, con nodos explícitos (cada uno es una función
pequeña que recibe el estado y devuelve un diccionario parcial):

```text
START
  ▼
reformular_pregunta      con historial → pregunta independiente (si no hay historial, pasa igual)
  ▼
clasificar_intencion     SALUDO | PRODUCTO_LACTEO | FUERA_DE_DOMINIO   (salida estructurada)
  ├─ SALUDO ────────────▶ responder_saludo ──────────────┐
  ├─ FUERA_DE_DOMINIO ──▶ rechazar ──────────────────────┤
  ▼ PRODUCTO_LACTEO                                      │
recuperar_contexto       similarity_search_with_score, k=4, se descarta lo que no pase el UMBRAL
  ▼                                                      │
evaluar_contexto         ¿hay fragmentos? + LLM juez: «¿este contexto responde la pregunta?» (sí/no)
  ├─ insuficiente ──────▶ rechazar ──────────────────────┤
  ▼ suficiente                                           │
generar_respuesta        solo con el contexto, citando [1], [2]…                │
  ▼                                                      │
guardar_historial ◀──────────────────────────────────────┘
  ▼
END
```

**Estado** (`TypedDict`): `pregunta`, `historial`, `pregunta_independiente`, `intencion`,
`fragmentos` (texto + metadata + similitud), `contexto_suficiente`, `respuesta`, `fuentes`,
`rechazada`, `pasos`, `usuario_id`, `conversacion_id`.

**El mensaje de rechazo es literal** (PDF §3.1), y se le suma la sugerencia:

> No tengo suficiente información en mi base de conocimiento para responder esa pregunta.
> Si tienes un documento sobre el tema, puedes cargarlo en la sección Documentos.

### Control de alucinaciones (PDF §3.4 pide dos; se implementan seis)

| # | Estrategia | Dónde |
|---|---|---|
| 1 | Umbral mínimo de similitud | `recuperar_contexto` |
| 2 | Nodo dedicado a validar si el contexto alcanza (LLM juez) | `evaluar_contexto` |
| 3 | Prompt que obliga a responder solo con lo recuperado | `generar_respuesta` |
| 4 | Rechazo explícito con el mensaje literal | `rechazar` |
| 5 | Fuentes y fragmentos visibles en el frontend | respuesta + UI |
| 6 | Clasificador de intención que corta lo fuera de dominio antes de buscar | `clasificar_intencion` |

**Ojo con el umbral:** `PGVector.similarity_search_with_score` devuelve **distancia coseno**
(menor = más parecido), no similitud. Calibra el umbral con preguntas reales — buenas y
ajenas — y deja el valor en `.env` (`UMBRAL_DISTANCIA`). Anota cómo lo calibraste: es
material del documento técnico.

**Con un modelo de 3B:** temperatura baja (0–0,2), `num_ctx` de 4096 para que quepan los
fragmentos, y salidas estructuradas cortas (una palabra) en los nodos de decisión. Si el
modelo devuelve algo que no está en la lista de intenciones, el código lo trata como
`PRODUCTO_LACTEO` y deja que decidan el umbral y el juez: **un fallo del clasificador nunca
debe producir una respuesta inventada**.

**Proveedor del modelo detrás de una función** (`crear_llm()`), con `LLM_PROVIDER=ollama`
por defecto. Así `../Patroclo/` puede reusar el grafo cambiando el proveedor. **Aquí no se
usa ningún modelo comercial**: el enunciado prohíbe depender de uno.

### Pruebas del grafo (`backend/tests/`)

Las pruebas leen **`evaluacion/casos.json`** (§7) y comprueban, para cada caso: si respondió,
rechazó o saludó según `debe`; que en las respondidas aparezca `fuente_esperada` entre las
fuentes; y que las rechazadas usen el mensaje literal. Deja además un script
`python -m app.evaluar` que corra todos los casos contra el modelo configurado e imprima una
tabla (acierto, tiempo, fuente): con él se calibra `UMBRAL_DISTANCIA` y se comparan modelos,
y su salida va al documento técnico.

---

## 9. El frontend

**React + Vite + TypeScript.** Pantallas:

1. **Ingresar / Registrarse.** Validación de formularios y errores claros.
2. **Chat** (tipo chatbot): lista de conversaciones a la izquierda; mensajes; cada respuesta
   muestra sus **fuentes** (desplegables, con el fragmento) y sus **pasos** por el grafo;
   las respuestas rechazadas se distinguen visualmente; indicador de «pensando» (el modelo
   local tarda).
3. **Documentos:** subir (arrastrar y soltar), ver estado y número de fragmentos, listar,
   borrar.
4. **Cerrar sesión** siempre visible.

Rutas protegidas: sin token válido → al ingreso. Token en memoria + `sessionStorage`.
Mensaje visible si el backend o el modelo no están disponibles (PDF §2.3).

**Identidad visual:** cálida, de quesería artesanal (crema, verde oliva, terracota), no el
azul genérico de los dashboards. Nombre visible: **Patroclo** — subtítulo «experto en
lácteos de cabra · Del Pastor».

---

## 10. El orden de trabajo (pensado para el plazo)

Cada paso termina con **un commit con mensaje significativo** (el PDF lo evalúa). Nada de un
commit gigante al final.

1. Esqueleto: `docker-compose` (Postgres+pgvector), backend FastAPI con `/health`,
   `.env.example`, `.gitignore` (con `referencias/`, `.env`, `node_modules`, subidas).
2. Autenticación completa y probada.
3. Ingesta: subir, listar, borrar, semilla desde `conocimiento/`.
4. El grafo con sus nodos + las pruebas del §8. **Aquí se calibra el umbral.**
5. `/api/chat` + historial.
6. Frontend: ingreso → chat → documentos.
7. Despliegue: frontend en la nube + backend por ngrok. Probarlo desde el celular.
8. README completo (cómo correr local y cómo desplegar), diagrama de arquitectura, capturas.

**Si el tiempo no alcanza, se recorta en este orden:** CSV y DOCX → borrar conversaciones →
comparación de modelos → pasos en la interfaz. **Nunca** se recorta: autenticación, rechazo,
fuentes, carga de documentos ni despliegue.

---

## 11. Cómo trabajar con Pedro

Las reglas de `../../CLAUDE.md` (el programa de agentes) siguen valiendo, ajustadas al
plazo: **primero se construye y después se explica**, pero **cada componente se explica**.
En la sustentación Pedro tiene que recorrer el código y explicar el grafo (PDF §5.3); si no
puede explicar algo que escribiste, no está terminado.

Al terminar cada paso del §10, documéntalo en **`ESTADO.md`** (raíz del repo; Pedro pidió
que todo quede ahí, y reemplaza a la antigua `docs/bitacora.md`): qué se hizo, por qué así,
qué falló y cómo se resolvió, y actualiza la tabla de avance. De ahí sale el apartado «problemas encontrados»
del documento técnico (PDF §5.2.14).

- Nombres del dominio en español (`documento`, `fragmento`, `conversacion`), igual que en
  los demás proyectos de la empresa.
- Secretos solo en `.env`; `.env` nunca se versiona.
- Si una decisión cambia algo de este archivo, **corrige este archivo**.
