# MultiRAG (Terminal)

RAG multimodal en terminal usando:

- Vector DB: Qdrant en Docker
- Embeddings: `gemini-embedding-2-preview`
- LLM de respuesta: `gemini-3.1-flash-lite-preview`

Procesa automaticamente ficheros en `doc_raw`.
Si ya fueron procesados (mismo hash), se omiten.

## 1) Levantar Qdrant

```bash
docker compose up -d
```

## 2) Configurar entorno

```bash
copy .env.example .env
```

Edita `.env` y coloca tu `GEMINI_API_KEY`.

## 3) Instalar dependencias

```bash
uv sync
```

## 4) Ejecutar API FastAPI

```bash
uv run uvicorn app.main:app --reload
```

Documentacion interactiva:

- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

Endpoints principales:

- `POST /api/v1/documents/upload` para subir documentos soportados
- `POST /api/v1/jobs/index` para crear job asincrono de indexacion
- `GET /api/v1/jobs/{job_id}` para monitorear progreso
- `POST /api/v1/query` para inferencia
- `DELETE /api/v1/documents/{document_id}` para borrar un documento concreto
- `DELETE /api/v1/documents?confirm=true` para borrar todo

Estado por documento en `GET /api/v1/documents`:

- `not_started`: aun no se inicio indexacion del hash actual.
- `queued`: documento encolado en un job.
- `processing`: documento en procesamiento activo.
- `processed`: indexacion completada para el hash actual.
- `failed`: fallo en la ultima indexacion del documento.

## 5) Cargar documentos

Coloca archivos en `doc_raw/`.

Formatos soportados:

- Texto: `.txt`, `.md`, `.json`, `.csv`, `.html`, `.xml`, `.py`
- Word: `.docx` (`.doc` no soportado)
- PDF: `.pdf`
- Imagen: `.png`, `.jpg`, `.jpeg`, `.webp`, `.bmp`

Comportamiento de ingesta:

- Texto: indexacion textual por chunks.
- PDF: configurable (`text`, `direct`, `hybrid`).
- Imagen: embedding multimodal directo; ademas se genera descripcion para contexto de respuesta.

Variables multimodales en `.env`:

```bash
RAG_ENABLE_MULTIMODAL=true
RAG_PDF_MODE=hybrid
RAG_PDF_PAGES_PER_CHUNK=1
RAG_PDF_ADAPTIVE_PAGES=true
RAG_PDF_PAGES_PER_CHUNK_TABLES=3
RAG_PDF_ADAPTIVE_DEBUG=false
RAG_MEDIA_FALLBACK_TO_TEXT=true
# RAG_OUTPUT_DIMENSIONALITY=1024
```

Modos PDF:

- `text`: extrae texto del PDF y lo indexa como texto.
- `direct`: intenta embedding multimodal del PDF por grupos de paginas.
- `hybrid`: intenta `direct` y si falla usa fallback textual.

Ajuste adaptativo de paginas PDF:

- Si `RAG_PDF_ADAPTIVE_PAGES=true`, el sistema detecta patrones de tablas en el PDF.
- Cuando detecta contenido tabular, usa `RAG_PDF_PAGES_PER_CHUNK_TABLES` (por defecto 3).
- Si no detecta tablas, usa `RAG_PDF_PAGES_PER_CHUNK` (por defecto 1).
- Si `RAG_PDF_ADAPTIVE_DEBUG=true`, imprime en la ingesta la estrategia elegida y su motivo.

## 6) Ingesta manual

```bash
uv run python main.py ingest
```

## 7) Preguntar al RAG

```bash
uv run python main.py ask "Que informacion hay sobre el documento X?"
```

El comando `ask` ejecuta primero la ingesta incremental automaticamente.

## 8) Modo interactivo

```bash
uv run python main.py
```

## 9) Limpieza de base vectorial

Puedes limpiar datos indexados de dos formas:

- Limpiar una sola fuente (ruta relativa dentro de `doc_raw`):

```bash
uv run python main.py clean --source "subcarpeta/archivo.pdf"
```

- Limpiar toda la coleccion vectorial:

```bash
uv run python main.py clean --all
```

Para evitar confirmacion interactiva:

```bash
uv run python main.py clean --all --yes
```

Comportamiento importante:

- `clean --source` elimina vectores de esa fuente y su entrada en `.rag_state/processed.json`.
- `clean --all` elimina toda la coleccion de Qdrant y reinicia `.rag_state/processed.json`.

## 10) Salida visual (colores y progreso)

Por defecto, la CLI usa una salida visual sobria:

- Colores para estado (`INFO`, `OK`, `WARN`, `ERROR`)
- Barras de progreso al hacer embeddings en la ingesta

Puedes desactivarlo:

```bash
uv run python main.py --no-color ingest
uv run python main.py --no-progress ask "Tu pregunta"
uv run python main.py --no-color --no-progress ask "Tu pregunta"
```

`--no-progress` es util para logs limpios en CI.

## 11) Modo resiliente ante 503

La ingesta funciona en modo resiliente:

- Reintentos automaticos con backoff exponencial + jitter
- Embeddings en lote para reducir numero de llamadas
- Si un archivo falla temporalmente, se reporta y se continua con el siguiente

Variables recomendadas en `.env`:

```bash
RAG_EMBED_BATCH_SIZE=16
GEMINI_API_MAX_RETRIES=6
GEMINI_API_BASE_DELAY_MS=500
GEMINI_API_MAX_DELAY_MS=10000
GEMINI_API_JITTER_MS=250
```

Si sigues viendo `503 UNAVAILABLE`, prueba:

- Subir `RAG_CHUNK_SIZE` (menos chunks)
- Bajar `RAG_CHUNK_OVERLAP`
- Reintentar tras unos segundos

## 12) Como funciona el control incremental

- Se guarda estado en `.rag_state/processed.json`
- Se calcula hash SHA-256 por archivo
- Si hash no cambia, el archivo se omite
- Si cambia, se reindexa ese archivo
