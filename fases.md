# Estado de fases del plan multimodal

Este documento resume el estado actual del plan de evolucion a RAG multimodal, con foco en tres preguntas:

- Que se esperaba en cada fase.
- Que ya esta implementado.
- Que sigue pendiente o parcial.

## Estado ejecutivo

- Fases implementadas: 6
- Fases parciales: 1
- Fases pendientes: 2

| Fase | Estado | Resultado actual |
|---|---|---|
| Fase 0 - Spike de compatibilidad | Pendiente | No hay benchmark formal por modalidad y limites |
| Fase 1 - Modelo de datos multimodal | Implementada | `Chunk` y `MediaSegment` soportan metadatos multimodales |
| Fase 2 - Loader por modalidad | Parcial | PDF e imagen operativos; audio/video no implementados |
| Fase 3 - Cliente Gemini multimodal | Implementada | Embeddings de texto, imagen y PDF con manejo robusto |
| Fase 4 - Ingesta hibrida en pipeline | Implementada | Ruteo por modalidad con modos `text/direct/hybrid` |
| Fase 5 - Vector store y retrieval | Implementada | Payload enriquecido y contexto basado en `surrogate_text` |
| Fase 6 - Configuracion `.env` | Implementada | Banderas multimodales controlables por entorno |
| Fase 7 - Validacion funcional | Implementada (nivel smoke test) | Compilacion + pruebas de flujo + fix de coleccion faltante |
| Fase 8 - Documentacion | Implementada | README, docstrings y notas operativas en espanol |

## Detalle por fase

### Fase 0 - Spike de compatibilidad por modalidad

**Para que sirve**
- Confirmar soporte real en el endpoint usado por el proyecto para `texto`, `imagen`, `pdf`, `audio` y `video`.
- Medir limites y estabilidad antes de ampliar arquitectura.

**Estado**
- Pendiente.

**Que falta para cerrarla**
- Matriz de soporte por modalidad.
- Limites por request (tamano, duracion, paginas).
- Latencia media y tasa de fallos/reintentos.
- Consistencia de dimensionalidad.

### Fase 1 - Modelo de datos multimodal

**Para que sirve**
- Guardar informacion recuperable con contexto multimodal, no solo texto plano.

**Estado**
- Implementada.

**Implementado**
- `Chunk` ampliado con `surrogate_text`, paginas, tiempos, `media_mime`, `media_kind`.
- `MediaSegment` como estructura de paso para indexacion multimodal.

### Fase 2 - Loader por modalidad

**Para que sirve**
- Convertir cada tipo de archivo en segmentos adecuados para embeddings y retrieval.

**Estado**
- Parcial.

**Implementado**
- PDF: texto por pagina + sub-PDF por segmento (`RAG_PDF_PAGES_PER_CHUNK`).
- PDF: ajuste adaptativo de paginas por segmento para contenido tabular (`RAG_PDF_ADAPTIVE_PAGES`, `RAG_PDF_PAGES_PER_CHUNK_TABLES`).
- PDF: trazas opcionales de estrategia adaptativa (`RAG_PDF_ADAPTIVE_DEBUG`).
- Imagen: segmento unitario con MIME inferido.

**Pendiente**
- Audio: segmentacion temporal y metadatos de tiempo.
- Video: segmentacion temporal/frame y metadatos de tiempo.

### Fase 3 - Cliente Gemini multimodal

**Para que sirve**
- Unificar llamadas a Gemini para embeddings textuales y multimodales con resiliencia.

**Estado**
- Implementada.

**Implementado**
- Embeddings de texto (`embed_text`, `embed_texts`).
- Embeddings multimodales (`embed_part`, `embed_image_bytes`, `embed_pdf_bytes`).
- Config opcional de dimensionalidad.
- Normalizacion de respuestas y manejo robusto de errores.

### Fase 4 - Ingesta hibrida en pipeline

**Para que sirve**
- Elegir estrategia de indexacion por modalidad sin perder robustez operativa.

**Estado**
- Implementada.

**Implementado**
- Ruteo por modalidad en `_index_file`.
- Modos PDF:
  - `text`: indexacion textual clasica.
  - `direct`: embedding PDF multimodal.
  - `hybrid`: intenta multimodal y cae a texto.
- Imagen con embedding multimodal y `surrogate_text`.
- Si falta la coleccion en Qdrant, se fuerza reindexacion aunque el estado incremental diga omitido.

### Fase 5 - Vector store y retrieval

**Para que sirve**
- Persistir vectores y metadatos para que la respuesta sea mas trazable y util.

**Estado**
- Implementada.

**Implementado**
- Payload enriquecido en `upsert`.
- `search` devuelve `surrogate_text`, paginas, tiempos y tipo de media.
- `collection_exists()` para chequeos defensivos.

### Fase 6 - Configuracion y control por entorno

**Para que sirve**
- Ajustar comportamiento multimodal sin tocar codigo.

**Estado**
- Implementada.

**Implementado**
- Variables nuevas:
  - `RAG_ENABLE_MULTIMODAL`
  - `RAG_PDF_MODE`
  - `RAG_PDF_PAGES_PER_CHUNK`
  - `RAG_MEDIA_FALLBACK_TO_TEXT`
  - `RAG_OUTPUT_DIMENSIONALITY` (opcional)

### Fase 7 - Validacion funcional y robustez

**Para que sirve**
- Confirmar que el flujo principal funciona tras cambios de arquitectura.

**Estado**
- Implementada (nivel smoke test).

**Implementado**
- `compileall` sin errores.
- Flujo `ingest` y `ask` validado.
- Correccion de error `404` cuando no existe la coleccion.
- Mensajes de error en CLI mas precisos (404, 503, 429, configuracion).

**Pendiente de mejora**
- Suite de pruebas repetibles por modalidad y casos limite.

### Fase 8 - Documentacion tecnica y operacional

**Para que sirve**
- Facilitar mantenimiento y operacion diaria del sistema.

**Estado**
- Implementada.

**Implementado**
- README actualizado con modos multimodales.
- Docstrings en espanol orientadas a proposito.
- `AGENTS.md` actualizado con recordatorio operativo.

## Pendiente nuevo: Protocolo de validacion de PDFs

### Objetivo

Definir una prueba corta, repetible y objetiva para validar calidad de respuestas sobre:

- PDF con texto nativo.
- PDF escaneado (imagenes).

### Estado

- Pendiente.

### Alcance propuesto

- Conjunto base:
  - 1 PDF de texto.
  - 1 PDF escaneado.
- Cinco preguntas patron por documento:
  1. Dato puntual.
  2. Resumen breve.
  3. Ubicacion por pagina.
  4. Comparacion entre conceptos.
  5. Dato numerico o fecha.

### Criterios de evaluacion

- Exactitud: responde lo pedido.
- Evidencia: cita fuente/pagina coherente.
- Fidelidad: evita alucinaciones.
- Utilidad: respuesta clara y accionable.

### Entregable esperado

- Matriz de resultados por tipo de PDF.
- Recomendacion operativa de modo PDF (`text`, `direct` o `hybrid`).

## Backlog prioritario recomendado

1. Cerrar Fase 0 con una matriz formal de compatibilidad y limites.
2. Completar audio/video (Fase 2).
3. Implementar el protocolo de validacion de PDFs.
4. Elevar Fase 7 con pruebas repetibles por modalidad.
