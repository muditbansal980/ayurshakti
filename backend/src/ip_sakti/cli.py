"""Run corpus operations explicitly, independently of the frontend."""

import argparse
import json
import sys
from pathlib import Path

from pymongo.errors import PyMongoError

from ip_sakti.config import Settings
from ip_sakti.storage.mongo import create_client, initialize_database


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sakti", description="IP-SAKTI data tools")
    commands = parser.add_subparsers(dest="command", required=True)
    audit = commands.add_parser("audit", help="Check PDF duplicates and extraction quality; no chunking")
    audit.add_argument("--corpus", type=Path)
    audit.add_argument("--output", type=Path)
    commands.add_parser("init-db", help="Create the local database and collections idempotently")
    commands.add_parser("status", help="Show collection counts without reading document contents")
    prepare = commands.add_parser("prepare", help="Extract PDFs and create inspectable parent/child bundles")
    prepare.add_argument("--ocr", action="store_true", help="Run local eng+hin OCR for image-only pages")
    prepare.add_argument("--target-tokens", type=int, default=384)
    prepare.add_argument("--document-id", help="Prepare only this catalog SHA-256, preserving other manifest entries")
    commands.add_parser("download-model", help="Download/cache the free multilingual embedding model")
    fetch = commands.add_parser("fetch-sources", help="Download the explicit official-source list and register provenance")
    fetch.add_argument("--sources", type=Path, default=Path("data/sources.json"))
    ingest = commands.add_parser("ingest", help="Embed prepared children and activate complete MongoDB generations")
    ingest.add_argument("--batch-size", type=int, default=None, help="Children embedded per model call (default 16)")
    commands.add_parser("index-status", help="Wait for the MongoDB vector index to become queryable")
    evaluate = commands.add_parser("evaluate-local", help="Run an exact-vector diagnostic without MongoDB")
    evaluate.add_argument("--cases", type=Path, default=Path("data/evaluation.json"))
    query = commands.add_parser("query", help="Retrieve source passages and their parent sections")
    query.add_argument("question")
    query.add_argument("--jurisdiction", choices=["india", "international"])
    query.add_argument("--top-k", type=int, default=5)
    query.add_argument("--min-score", type=float, default=0.7, help="Minimum cosine similarity (-1 to 1); heuristic, not confidence")
    query.add_argument("--document-id")
    query.add_argument("--kind")
    query.add_argument("--language", choices=["hi", "en"])
    query.add_argument("--json", action="store_true", help="Print the full structured response")
    query.add_argument("--include-unverified", action="store_true")
    query.add_argument("--vector-only", action="store_true", help="Compatibility flag; semantic vector search is now the default")
    args = parser.parse_args(argv)
    try:
        settings = Settings.from_env()
        if args.command == "fetch-sources":
            from ip_sakti.ingestion.acquire import fetch_sources
            report = fetch_sources(settings, args.sources)
            from ip_sakti.ingestion.prepare import write_json
            write_json(settings.reports_dir / "source-fetch.json", report)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 2 if report["failed"] else 0
        if args.command in ("prepare", "download-model", "ingest", "query", "evaluate-local"):
            from ip_sakti.embeddings.local import LocalEmbedder
            embedder = LocalEmbedder(settings.embedding_device, settings.embedding_model,
                                     settings.embedding_revision, settings.embedding_batch_size)
        if args.command == "evaluate-local":
            from ip_sakti.evaluation.local import evaluate_local
            print(json.dumps(evaluate_local(settings, embedder, args.cases), ensure_ascii=False, indent=2))
            return 0
        if args.command == "download-model":
            from ip_sakti.embeddings.local import DIMENSIONS, cache_path
            try:
                # Forces the tokenizer download, the weight download, and a real forward pass.
                vector = embedder.query("model warm-up")
                embedder.encode(["passage: model warm-up"])
            except Exception as error:  # network, disk, or incompatible weights
                print(f"Model download failed for {settings.embedding_model}: "
                      f"{type(error).__name__}: {error}", file=sys.stderr)
                return 1
            if len(vector) != DIMENSIONS:
                print(f"Expected {DIMENSIONS} dimensions, model produced {len(vector)}.",
                      file=sys.stderr)
                return 1
            print(json.dumps({
                "model": settings.embedding_model,
                "revision": settings.embedding_revision,
                "dimensions": len(vector),
                "device": settings.embedding_device,
                "cache_dir": str(cache_path(settings.model_cache_dir)),
                "status": "ready",
            }, indent=2))
            return 0
        if args.command == "prepare":
            from ip_sakti.ingestion.prepare import prepare_corpus
            report = prepare_corpus(settings, embedder.tokenizer, ocr=args.ocr,
                                    target_tokens=args.target_tokens, document_id=args.document_id)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 2 if report["failed"] else 0
        if args.command == "audit":
            from ip_sakti.ingestion.audit import audit_corpus

            result = audit_corpus(args.corpus or settings.corpus_dir)
            output = args.output or settings.reports_dir / "corpus-audit.json"
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(json.dumps({
                "report": str(output),
                "files": result["file_count"],
                "unique": result["unique_document_count"],
                "duplicates": result["duplicate_file_count"],
            }, ensure_ascii=False, indent=2))
            return 0
        with create_client(settings) as client:
            client.admin.command("ping")
            db = client[settings.database]
            if args.command == "init-db":
                initialize_database(db)
                print(f"Initialized {settings.database}; existing documents preserved.")
            elif args.command == "status":
                from ip_sakti.storage.status import pipeline_status
                print(json.dumps(pipeline_status(settings, db), ensure_ascii=False, indent=2))
            elif args.command == "ingest":
                from dataclasses import replace
                from ip_sakti.storage.ingest import ingest_prepared
                if args.batch_size is not None:
                    if args.batch_size < 1:
                        raise ValueError("Batch size must be a positive integer.")
                    settings = replace(settings, embedding_batch_size=args.batch_size)
                    embedder.batch_size = args.batch_size
                print(json.dumps(ingest_prepared(settings, db, embedder), ensure_ascii=False, indent=2))
            elif args.command == "index-status":
                from ip_sakti.storage.indexes import wait_for_vector_index
                wait_for_vector_index(db)
                print("Vector index is queryable.")
            elif args.command == "query":
                from ip_sakti.retrieval.search import RetrievalService
                filters = {key: value for key, value in {
                    "jurisdiction": args.jurisdiction, "document_id": args.document_id,
                    "kind": args.kind, "language": args.language,
                }.items() if value is not None}
                result = RetrievalService(db, embedder).retrieve(
                    args.question, top_k=args.top_k, min_score=args.min_score,
                    filters=filters, include_unverified=args.include_unverified)
                if args.json:
                    print(json.dumps(result, ensure_ascii=False, indent=2))
                else:
                    print(format_search_results(result))

        return 0
    except PyMongoError:
        print("MongoDB operation failed. Check Docker health and local credentials. Connection secrets are omitted.", file=sys.stderr)
        return 1
    except ImportError:
        print("Install local model dependencies: pip install -e 'backend[embeddings]'", file=sys.stderr)
        return 1
    except (ValueError, OSError) as error:
        print(str(error), file=sys.stderr)
        return 1
    except RuntimeError:
        print("Retrieval/model operation failed. Check the pinned local model, corpus integrity and vector index readiness.", file=sys.stderr)
        return 1


def format_search_results(response: dict) -> str:
    lines = []
    for rank, result in enumerate(response["results"], 1):
        citation = result["citation"]
        lines.append(f"{rank}. {citation.get('title', 'Untitled')} — {citation.get('provision', 'Unknown section')} "
                     f"(cosine {result['score']:.4f})")
        lines.append(f"   Chunk: {result['chunk_id']} | Document: {result['document_id']}")
        lines.append(f"   PDF pages: {citation.get('pdf_pages', [])} | Review: {citation.get('review_status', 'unknown')}")
        lines.append(f"   Source: {citation.get('source_url') or citation.get('local_file') or 'Not recorded'}")
        lines.append(result["matched_passage"])
        lines.append("")
    if not lines:
        lines.append(response.get("reason", "No passages met the filters and similarity threshold."))
    lines.append(response.get("note", "Scores measure similarity, not answer correctness. Review source currency."))
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())

