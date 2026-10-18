# Base de conocimiento de Patroclo — LEER ANTES DE INDEXAR

**Este README no se indexa.** Todo lo demás de esta carpeta sí.

Escrita el 17/10/2026 a partir de `https://delpastor.com/` (leída ese día), de
`../../CONTEXTO-PROYECTO.md` (§3, los productos) y de fuentes públicas citadas en cada archivo.

## Formato de cada archivo

Markdown con frontmatter YAML:

```yaml
---
titulo: Título legible (se muestra como nombre de la fuente)
tema: marca | catalogo | leche | elaboracion | origen | receta | maridaje | conservacion | faq | operacion
productos: [tipo-griego, feta-bloque, iberico, crema, linea-domicilio]   # los que trata
visibilidad: publico | interno
fuentes:
  - descripción — URL
actualizado: 2026-10-17
---
```

**La ingesta debe leer el frontmatter y copiarlo a la metadata de cada fragmento**
(`titulo`, `tema`, `productos`, `visibilidad`) y **quitarlo del texto** que se vectoriza.
Las secciones `## Fuentes` al final de cada archivo sí se vectorizan: así el agente puede citarlas.

## Qué hay

| Archivo | Tema | Visibilidad |
|---|---|---|
| `01-del-pastor-la-marca.md` | Quién es Del Pastor, dónde están las cabras, valores, cómo comprar | publico |
| `02-catalogo-del-pastor.md` | Los cuatro quesos, sus presentaciones y la línea a domicilio | publico |
| `03-leche-de-cabra.md` | Composición, sabor, lactosa, alergias, mitos | publico |
| `04-cabras-en-colombia.md` | Caprinocultura colombiana, razas, regiones | publico |
| `05-queso-tipo-griego-feta.md` | Origen, historia, protección del nombre, elaboración, usos | publico |
| `06-queso-iberico-de-cabra.md` | El madurado, el Manchego y por qué cambió el nombre | publico |
| `07-queso-crema-de-cabra.md` | El untable: qué es, cómo se hace, usos | publico |
| `08-como-se-hace-el-queso-de-cabra.md` | Proceso general, las tres familias de queso | publico |
| `09-recetas-tipo-griego-y-feta.md` | Recetas con el tipo griego y el feta en bloque | publico |
| `10-recetas-iberico.md` | Recetas con el ibérico | publico |
| `11-recetas-queso-crema.md` | Recetas dulces y saladas con el queso crema | publico |
| `12-acompanamientos-y-tablas.md` | Con qué combina cada queso y cómo armar una tabla (sin vinos) | publico |
| `13-conservacion-y-seguridad.md` | Cómo guardar cada queso, salmuera, grupos de riesgo | publico |
| `14-otros-productos-de-cabra.md` | Leche, yogur, mantequilla, helados, pastelería | publico |
| `15-preguntas-frecuentes.md` | Preguntas de clientes, con respuesta corta | publico |
| `90-operacion-interna.md` | Guía interna de atención (ejemplo para demostrar el filtro de visibilidad) | **interno** |

## Reglas que se respetaron (y que el agente debe respetar)

- **Nada de precios, NIT, PLU, condiciones comerciales ni nombres de clientes.** Precios y
  pedidos: siempre al WhatsApp o al correo de la empresa.
- **Nada inventado sobre la marca.** Lo de Del Pastor sale de su web o de `CONTEXTO-PROYECTO.md`.
  Lo que no se sabe (año de fundación, fundadores, nombre de la finca) **no está**, y el agente
  debe decir que no lo sabe.
- **Ninguna receta de producción propia.** `08` describe el proceso general de cada tipo de queso,
  no la fórmula de la empresa.
- **Las recetas de cocina (09–11) son de referencia**, escritas para esta base a partir de
  preparaciones tradicionales. No son recetas oficiales de Del Pastor.
- **Lo que es afirmación y no hecho comprobado se dice así** (p. ej. la beta-caseína A2).

## Lo que NO está a propósito

**Maridajes con vino y cerveza.** Viven en `../demo-carga/` para subirlos en vivo en la
sustentación: antes de cargarlos, Patroclo debe rechazar «¿qué vino va con el ibérico?»;
después, responderla con la fuente nueva.
