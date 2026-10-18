# El grafo de Patroclo (LangGraph)

Generado desde el código con `construir_grafo(...).get_graph().draw_mermaid()`
(`backend/agents/grafo.py`). Las flechas punteadas son aristas condicionales: las decide
código que lee el estado, no el modelo.

```mermaid
---
config:
  flowchart:
    curve: linear
---
graph TD;
	__start__([<p>__start__</p>]):::first
	reformular_pregunta(reformular_pregunta)
	clasificar_intencion(clasificar_intencion)
	recuperar_contexto(recuperar_contexto)
	evaluar_contexto(evaluar_contexto)
	generar_respuesta(generar_respuesta)
	rechazar(rechazar)
	responder_saludo(responder_saludo)
	guardar_historial(guardar_historial)
	__end__([<p>__end__</p>]):::last
	__start__ --> reformular_pregunta;
	clasificar_intencion -.-> rechazar;
	clasificar_intencion -.-> recuperar_contexto;
	clasificar_intencion -.-> responder_saludo;
	evaluar_contexto -.-> generar_respuesta;
	evaluar_contexto -.-> rechazar;
	generar_respuesta -.-> guardar_historial;
	generar_respuesta -.-> rechazar;
	rechazar --> guardar_historial;
	recuperar_contexto --> evaluar_contexto;
	reformular_pregunta --> clasificar_intencion;
	responder_saludo --> guardar_historial;
	guardar_historial --> __end__;
	classDef default fill:#f2f0ff,line-height:1.2
	classDef first fill-opacity:0
	classDef last fill:#bfb6fc
```

| Nodo | Usa el modelo | Qué hace |
|---|---|---|
| reformular_pregunta | solo si hay historial | Reescribe la pregunta para que se entienda sola |
| clasificar_intencion | sí (1 palabra) | SALUDO / PRODUCTO_LACTEO / FUERA_DE_DOMINIO; el código corrige si nombra términos del dominio |
| recuperar_contexto | no (embeddings) | k=4 fragmentos de PGVector; descarta los de distancia > UMBRAL_DISTANCIA |
| evaluar_contexto | sí (1 palabra) | Juez: ¿el contexto trae el dato pedido? Sin fragmentos → insuficiente sin llamar al modelo |
| generar_respuesta | sí | Responde solo con el contexto, citando [n]; si escribe NO_SE se rechaza |
| rechazar | no | Mensaje literal del enunciado + sugerencia de cargar documentos |
| responder_saludo | no | Mensaje fijo de presentación |
| guardar_historial | no | Guarda pregunta, respuesta, fuentes y pasos (paso 5) |
