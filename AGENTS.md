# AGENTS.md

## Que es este repositorio
- Paquete Python unico con dos superficies que comparten el mismo nucleo RAG (`multirag/*`):
  - Punto de entrada CLI: `main.py` -> `multirag/cli.py:run()`.
  - Punto de entrada API HTTP: `app/main.py` (`uvicorn app.main:app`).
- Los servicios de API son adaptadores del pipeline de la CLI (`app/services/index_service.py` y `app/services/query_service.py` llaman a `multirag.pipeline`).

## Orden de setup para evitar errores falsos
- Arranca Qdrant primero: `docker compose up -d`.
- Instala dependencias: `uv sync`.
- Crea un `.env` en la raiz del repo (el codigo usa `load_dotenv()` desde CWD) y define como minimo `GEMINI_API_KEY`.
- Coloca archivos fuente locales en `doc_raw/` (valor por defecto definido en `multirag/config.py`).

## Comandos de ejecucion (exactos)
- Servidor API en desarrollo: `uv run uvicorn app.main:app --reload`.
- Ingesta CLI: `uv run python main.py ingest`.
- Pregunta unica por CLI (ejecuta ingesta automatica antes): `uv run python main.py ask "..."`.
- Modo interactivo CLI (tambien ejecuta ingesta automatica antes): `uv run python main.py`.
- Limpieza por CLI: `uv run python main.py clean --source "subdir/file.pdf"` o `uv run python main.py clean --all --yes`.

## Comandos de verificacion
- Suite completa: `uv run pytest -q` (actualmente 13 tests).
- Test enfocado: `uv run pytest tests/unit/test_job_service.py -q`.

## Comportamientos clave y gotchas
- El estado incremental del indice vive en `.rag_state/processed.json`; el estado por documento de la API vive en `.rag_state/document_status.json`.
- `.rag_state/test_status_*.json` se usa en tests y esta versionado en git; no lo trates como fuente funcional del producto.
- `JobStore` solo vive en memoria (`app/infrastructure/job_store.py`), por lo que el historial de jobs de la API se reinicia al reiniciar el proceso.
- `POST /api/v1/jobs/index` aplica deduplicacion idempotente: si un documento ya esta en `queued/processing` con un job activo, devuelve `200` reutilizando ese job y no lo re-encola.
- Si un job falla por error global (por ejemplo, Qdrant caido), los documentos de ese job que seguian en `queued/processing` se marcan como `failed` para permitir reintentos limpios.
- Si existe estado `queued/processing` pero el `last_job_id` ya no esta activo (estado stale), el documento vuelve a ser reencolable en la siguiente solicitud de indexacion.
- El endpoint de subida de la API acepta texto/PDF/imagen/docx (`/api/v1/documents/upload`); `.doc` no esta soportado.
- `docker-compose.yml` fija Qdrant server en `v1.13.2` mientras `uv.lock` fija `qdrant-client` en `1.17.1`; pueden aparecer warnings de compatibilidad.
- El README menciona `.env.example`, pero ese archivo no existe en el repo; crea `.env` manualmente.
