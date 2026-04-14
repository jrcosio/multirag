from __future__ import annotations

import argparse
import sys

from multirag.config import load_settings
from multirag.gemini_client import GeminiClient
from multirag.pipeline import answer_question, ingest_documents
from multirag.state import ProcessedState
from multirag.ui import CliUI, UIOptions
from multirag.vector_store import VectorStore


def run() -> None:
    """Gestiona la experiencia de linea de comandos para ingesta y preguntas."""

    parser = argparse.ArgumentParser(description="RAG multimodal en terminal")
    parser.add_argument("--no-color", action="store_true", help="Desactiva colores en la salida")
    parser.add_argument("--no-progress", action="store_true", help="Desactiva barras de progreso")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("ingest", help="Procesa archivos nuevos de doc_raw")

    ask_parser = subparsers.add_parser("ask", help="Hace una pregunta al RAG")
    ask_parser.add_argument("question", nargs="+", help="Pregunta para el RAG")

    clean_parser = subparsers.add_parser("clean", help="Limpia datos vectoriales y estado incremental")
    clean_target = clean_parser.add_mutually_exclusive_group(required=True)
    clean_target.add_argument("--source", help="Ruta relativa del archivo en doc_raw a eliminar")
    clean_target.add_argument("--all", action="store_true", help="Elimina toda la coleccion vectorial")
    clean_parser.add_argument("--yes", action="store_true", help="Confirma acciones destructivas sin preguntar")

    args = parser.parse_args()
    ui = CliUI(UIOptions(use_color=not args.no_color, use_progress=not args.no_progress))

    settings = load_settings()
    store = VectorStore(url=settings.qdrant_url, collection_name=settings.qdrant_collection)
    state = ProcessedState(settings.state_dir / "processed.json")

    if args.command == "clean":
        _run_clean(ui, store, state, settings, source=args.source, clean_all=args.all, yes=args.yes)
        return

    gemini = GeminiClient(
        api_key=settings.gemini_api_key,
        embedding_model=settings.embedding_model,
        llm_model=settings.llm_model,
        output_dimensionality=settings.output_dimensionality,
        max_retries=settings.api_max_retries,
        base_delay_ms=settings.api_base_delay_ms,
        max_delay_ms=settings.api_max_delay_ms,
        jitter_ms=settings.api_jitter_ms,
    )

    if args.command == "ingest":
        ui.title("Ingesta")
        stats = ingest_documents(
            settings,
            gemini,
            store,
            use_progress=ui.options.use_progress,
            on_event=lambda event, path: _on_ingest_event(ui, event, path),
        )
        _print_ingest_stats(ui, stats)
        return

    if args.command == "ask":
        ui.title("Ingesta Incremental")
        stats = ingest_documents(
            settings,
            gemini,
            store,
            use_progress=ui.options.use_progress,
            on_event=lambda event, path: _on_ingest_event(ui, event, path),
        )
        _print_ingest_stats(ui, stats)

        question = " ".join(args.question)
        ui.title("Consulta")
        try:
            result = answer_question(
                settings,
                gemini,
                store,
                question=question,
                on_stage=lambda stage: _on_ask_stage(ui, stage),
            )
        except Exception as exc:  # noqa: BLE001
            ui.error(f"No se pudo completar la consulta: {exc}")
            ui.warn(_friendly_error_hint(exc))
            return
        print("\nRespuesta:\n")
        print(_safe_console_text(result["answer"]))
        print("\nFuentes:")
        for i, match in enumerate(result["matches"], start=1):
            details = []
            page_start = match.get("page_start")
            page_end = match.get("page_end")
            if page_start:
                details.append(f"p={page_start}-{page_end or page_start}")
            start_sec = match.get("start_sec")
            end_sec = match.get("end_sec")
            if start_sec is not None:
                end_label = end_sec if end_sec is not None else start_sec
                details.append(f"t={start_sec:.1f}-{end_label:.1f}s")
            detail_str = f" | {' '.join(details)}" if details else ""
            print(
                f"{i}. {match['source_path']} | modalidad={match['modality']} "
                f"| chunk={match['chunk_index']}{detail_str} | score={ui.score(match['score'])}"
            )
        return

    _interactive_loop(settings, gemini, store, ui)


def _interactive_loop(settings, gemini, store, ui: CliUI) -> None:
    """Mantiene una sesion de preguntas repetidas reutilizando el indice cargado."""

    ui.title("Ingesta Incremental")
    stats = ingest_documents(
        settings,
        gemini,
        store,
        use_progress=ui.options.use_progress,
        on_event=lambda event, path: _on_ingest_event(ui, event, path),
    )
    _print_ingest_stats(ui, stats)

    ui.info("Modo interactivo. Escribe tu pregunta o 'exit' para salir.")
    while True:
        question = input("\n> ").strip()
        if question.lower() in {"exit", "quit", "salir"}:
            ui.ok("Hasta luego.")
            return
        if not question:
            continue

        try:
            result = answer_question(
                settings,
                gemini,
                store,
                question=question,
                on_stage=lambda stage: _on_ask_stage(ui, stage),
            )
        except Exception as exc:  # noqa: BLE001
            ui.error(f"No se pudo completar la consulta: {exc}")
            ui.warn(_friendly_error_hint(exc))
            continue
        print("\nRespuesta:\n")
        print(_safe_console_text(result["answer"]))


def _print_ingest_stats(ui: CliUI, stats: dict[str, object]) -> None:
    """Resume el resultado de ingesta para diagnostico rapido del usuario."""

    ui.ok(
        "Ingesta -> "
        f"total={stats['total_files']} "
        f"procesados={stats['processed_files']} "
        f"omitidos={stats['skipped_files']} "
        f"fallidos={stats.get('failed_count', 0)} "
        f"chunks={stats['indexed_chunks']}"
    )
    failed_files = stats.get("failed_files") or []
    failed_reasons = stats.get("failed_reasons") or {}
    for path in failed_files:
        reason = failed_reasons.get(path)
        if reason:
            ui.warn(f"No se pudo procesar (se omite por ahora): {path} -> {reason}")
            continue
        ui.warn(f"No se pudo procesar (se omite por ahora): {path}")


def _on_ingest_event(ui: CliUI, event: str, path: str) -> None:
    """Traduce eventos internos de ingesta a mensajes de consola legibles."""

    if ui.options.use_progress:
        return
    if event == "file_processed":
        ui.ok(f"Procesado: {path}")
    elif event == "file_skipped":
        ui.info(f"Omitido: {path}")
    elif event == "file_empty":
        ui.warn(f"Sin contenido util: {path}")
    elif event == "file_failed":
        ui.warn(f"Fallo temporal, se continua con el siguiente: {path}")
    elif event == "image_describing":
        ui.info(f"Describiendo imagen: {path}")
    elif event == "pdf_chunking_strategy":
        ui.info(f"Estrategia PDF: {path}")


def _on_ask_stage(ui: CliUI, stage: str) -> None:
    """Muestra el avance de una consulta para que el flujo sea transparente."""

    labels = {
        "embedding_question": "Generando embedding de la pregunta...",
        "search_qdrant": "Buscando contexto en Qdrant...",
        "generating_answer": "Generando respuesta con Gemini...",
    }
    ui.info(labels.get(stage, stage))


def _safe_console_text(text: str) -> str:
    """Adapta texto a la codificacion de consola para evitar errores de impresion."""

    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    return text.encode(encoding, errors="replace").decode(encoding, errors="replace")


def _friendly_error_hint(exc: Exception) -> str:
    """Devuelve una recomendacion segun el tipo de fallo detectado en consulta."""

    message = str(exc).lower()
    if "collection" in message and "doesn't exist" in message:
        return "No existe la coleccion en Qdrant. Ejecuta 'ingest' o vuelve a lanzar 'ask' para recrearla."
    if "404" in message and "not found" in message:
        return "Se recibio 404 desde Qdrant. Verifica QDRANT_COLLECTION y que el contenedor este activo."
    if "503" in message or "unavailable" in message:
        return "Parece un fallo temporal de servicio (503). Reintenta en unos segundos."
    if "429" in message or "quota" in message or "rate limit" in message:
        return "Se alcanzo un limite de cuota/rate. Espera un momento y vuelve a intentar."
    return "Revisa configuracion de Gemini/Qdrant y vuelve a intentar la consulta."


def _run_clean(
    ui: CliUI,
    store: VectorStore,
    state: ProcessedState,
    settings,
    source: str | None,
    clean_all: bool,
    yes: bool,
) -> None:
    """Ejecuta limpieza selectiva o total de vectores y estado incremental."""

    ui.title("Limpieza")
    if clean_all:
        if not yes:
            prompt = (
                f"Esta accion borrara toda la coleccion '{settings.qdrant_collection}' "
                "y reiniciara .rag_state/processed.json. Continuar? [y/N]: "
            )
            answer = input(prompt).strip().lower()
            if answer not in {"y", "yes", "s", "si"}:
                ui.warn("Operacion cancelada por el usuario.")
                return

        deleted = store.delete_collection()
        state.clear()
        if deleted:
            ui.ok(f"Coleccion eliminada: {settings.qdrant_collection}")
        else:
            ui.info(f"La coleccion no existia: {settings.qdrant_collection}")
        ui.ok("Estado incremental reiniciado: .rag_state/processed.json")
        return

    assert source is not None
    normalized_source = _normalize_source_path(source, settings.doc_raw_dir)
    if store.collection_exists():
        store.remove_source(normalized_source)
        ui.ok(f"Vectores eliminados para: {normalized_source}")
    else:
        ui.info("La coleccion de Qdrant no existe; no habia vectores que eliminar.")

    removed = state.unmark_processed(normalized_source)
    if removed:
        ui.ok(f"Estado incremental eliminado para: {normalized_source}")
    else:
        ui.info(f"No habia estado incremental para: {normalized_source}")


def _normalize_source_path(source: str, doc_raw_dir) -> str:
    """Normaliza rutas de entrada para que coincidan con source_path almacenado."""

    cleaned = source.strip().replace("\\", "/")
    if not cleaned:
        return cleaned

    try:
        from pathlib import Path

        src_path = Path(cleaned)
        if src_path.is_absolute():
            rel = src_path.resolve().relative_to(doc_raw_dir.resolve())
            return str(rel).replace("\\", "/")
    except Exception:  # noqa: BLE001
        pass

    return cleaned.lstrip("./")
