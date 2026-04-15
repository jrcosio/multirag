# MEJORAS_RAG

## Objetivo

Evolucionar el RAG multimodal actual para que:

- [ ] ayude a investigar, no solo a responder preguntas puntuales
- [ ] comprenda mejor el global del corpus documental
- [ ] conecte evidencia entre documentos
- [ ] entregue respuestas mas auditables y utiles para analisis

## Principios de ejecucion

- [ ] medir antes de cambiar
- [ ] mejorar retrieval antes de depender de prompts complejos
- [ ] separar modo rapido (`lookup`) y modo investigacion (`research`)
- [ ] mantener la arquitectura simple (Qdrant + Gemini + Python)

## Fases (con check de avance)

### Fase 0 - Baseline y evaluacion

**Objetivo:** tener una linea base objetiva para comparar mejoras.

- [ ] crear dataset de evaluacion (factual, comparativa, multi-fragmento, global)
- [ ] registrar por consulta: pregunta, chunks recuperados, scores, respuesta final
- [ ] definir metricas minimas: calidad de evidencia, calidad de respuesta, cobertura de fuentes, latencia
- [ ] crear un flujo reproducible de evaluacion antes/despues

**Criterio de salida**

- [ ] baseline documentado y repetible

---

### Fase 1 - Mejorar chunking y metadata

**Objetivo:** pasar de chunks lineales fragiles a unidades mas semanticas.

- [ ] cambiar chunking por estructura (secciones/parrafos/bloques)
- [ ] enriquecer metadatos por chunk (seccion, orden, tipo de bloque, pagina)
- [ ] introducir jerarquia logica (`leaf chunk` y `parent block`)
- [ ] mejorar `surrogate_text` para multimodalidad

**Criterio de salida**

- [ ] mejora en recuperacion factual y menos fragmentos descontextualizados

---

### Fase 2 - Retrieval en dos etapas (candidatos + reranking)

**Objetivo:** no depender de un unico `top-k` vectorial.

- [ ] recuperar candidatos amplios (`candidate_k`)
- [ ] rerankear con Gemini para obtener `final_k`
- [ ] deduplicar resultados casi iguales
- [ ] favorecer cobertura de varias fuentes/documentos

**Criterio de salida**

- [ ] chunks finales mas relevantes en consultas ambiguas o comparativas

---

### Fase 3 - Context expansion y evidence pack

**Objetivo:** responder con contexto completo, no con trozos sueltos.

- [ ] expandir cada chunk final con vecinos (anterior/siguiente/padre)
- [ ] agrupar evidencia por documento antes de generar respuesta
- [ ] construir `context pack` ordenado y sin duplicados
- [ ] limitar por presupuesto de tokens y diversidad

**Criterio de salida**

- [ ] mejores respuestas en preguntas de argumentacion y sintesis

---

### Fase 4 - Modo `research`

**Objetivo:** consultas complejas con pipeline multi-paso.

- [ ] añadir selector de modo en query (`lookup`/`research`)
- [ ] clasificar intencion de consulta
- [ ] descomponer en subpreguntas
- [ ] ejecutar retrieval por subpregunta
- [ ] fusionar evidencia y sintetizar respuesta estructurada
- [ ] exigir soporte en fuentes por afirmaciones importantes

**Criterio de salida**

- [ ] mejora clara en preguntas tipo "que dice el corpus sobre..."

---

### Fase 5 - Capa global del corpus

**Objetivo:** entender el conjunto documental como unidad, no solo chunks.

- [ ] generar durante ingesta resumen por documento/seccion
- [ ] extraer temas y keywords por documento
- [ ] indexar vistas globales separadas de chunks finos
- [ ] retrieval en dos niveles: documento/tema -> chunk/evidencia

**Criterio de salida**

- [ ] mejora en respuestas panoramicas y comparativas multi-documento

---

### Fase 6 - Respuesta auditable para analisis

**Objetivo:** hacer la salida mas util para investigar.

- [ ] formato de salida estructurado (`respuesta`, `hallazgos`, `evidencia`, `incertidumbres`)
- [ ] agrupar fuentes por documento
- [ ] enriquecer endpoint debug con trazabilidad de retrieval

**Criterio de salida**

- [ ] usuario puede auditar facilmente como y por que se respondio

---

### Fase 7 - Retrieval hibrido (posterior)

**Objetivo:** mejorar consultas con terminos exactos (siglas, codigos, nombres).

- [ ] evaluar fusion semantica + lexical
- [ ] medir impacto en consultas tecnicas exactas

**Criterio de salida**

- [ ] mejora en queries de coincidencia literal sin degradar semantica

---

### Fase 8 - Entidades/relaciones ligeras (opcional)

**Objetivo:** reforzar preguntas relacionales entre documentos.

- [ ] extraer entidades (personas, orgs, conceptos, fechas)
- [ ] conectar documentos por entidades comunes
- [ ] usarlo para expansion y filtros de consulta

**Criterio de salida**

- [ ] mejor desempeño en preguntas de relacion y patron transversal

## Prioridad real (alineada a tu objetivo)

Primero ejecutar:

- [ ] Fase 0
- [ ] Fase 1
- [ ] Fase 2
- [ ] Fase 3
- [ ] Fase 4
- [ ] Fase 5

Despues evaluar si compensa abordar:

- [ ] Fase 6
- [ ] Fase 7
- [ ] Fase 8

## Implementacion tecnica por archivos (siguiente paso recomendado)

### 1) `multirag/chunking.py`

- [ ] incorporar chunking estructural (no solo split por caracteres)
- [ ] emitir informacion de seccion/parent para contexto

### 2) `multirag/types.py`

- [ ] extender `Chunk` con metadata de estructura documental
- [ ] anadir campos para relaciones padre/hijo o vecinos

### 3) `multirag/vector_store.py`

- [ ] soportar retrieval en dos etapas (`candidate_k` y `final_k` via servicio)
- [ ] permitir estrategias de deduplicacion/diversidad
- [ ] preparar filtros por metadata cuando aplique

### 4) `multirag/pipeline.py`

- [ ] separar `answer_question_lookup()` y `answer_question_research()`
- [ ] agregar expansion de contexto y fusion por documento
- [ ] construir `context_pack` antes de llamar al generador

### 5) `multirag/gemini_client.py`

- [ ] anadir utilidades de reranking sobre candidatos
- [ ] anadir utilidades para descomposicion en subpreguntas
- [ ] anadir utilidades para resumen global por documento

### 6) `app/schemas/query.py`

- [ ] anadir campo opcional `mode` con valores `lookup`/`research`
- [ ] mantener compatibilidad hacia atras (default `lookup`)

### 7) `app/services/query_service.py`

- [ ] enrutar segun `mode`
- [ ] controlar parametros de `candidate_k`, `final_k` y presupuesto de contexto

### 8) `app/api/v1/endpoints/query.py`

- [ ] exponer `mode` y nuevos campos debug sin romper contrato actual
- [ ] publicar variante debug con trazas de etapas (retrieval, rerank, expansion)

## Checklist de control por sprint

### Sprint A (fundacion)

- [ ] Fase 0 completa
- [ ] primer corte de Fase 1

### Sprint B (calidad retrieval)

- [ ] Fase 2 completa
- [ ] primera version de Fase 3

### Sprint C (investigacion)

- [ ] Fase 4 MVP
- [ ] Fase 5 MVP

### Sprint D (madurez)

- [ ] Fase 6
- [ ] decidir si ejecutar Fase 7/8 segun metricas

## Definicion de exito global

Se considera logrado cuando:

- [ ] responde mejor preguntas globales del corpus
- [ ] mejora comparativas entre varios documentos
- [ ] mejora cobertura y trazabilidad de evidencia
- [ ] mantiene latencia razonable por modo (`lookup` rapido, `research` mas profundo)
