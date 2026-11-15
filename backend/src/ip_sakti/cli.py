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
    commands.add_parser("download-model", help="Download/cache the free multilingual embedding model")
    fetch = commands.add_parser("fetch-sources", help="Download the explicit official-source list and register provenance")
    fetch.add_argument("--sources", type=Path, default=Path("data/sources.json"))
    commands.add_parser("ingest", help="Embed prepared children and activate complete MongoDB generations")
    commands.add_parser("index-status", help="Wait for the MongoDB vector index to become queryable")
    evaluate = commands.add_parser("evaluate-local", help="Run an exact-vector diagnostic without MongoDB")
    evaluate.add_argument("--cases", type=Path, default=Path("data/evaluation.json"))
    query = commands.add_parser("query", help="Retrieve source passages and their parent sections")
    query.add_argument("question")
    query.add_argument("--jurisdiction", choices=["india", "international"], required=True)
    query.add_argument("--top-k", type=int, default=5)
    query.add_argument("--include-unverified", action="store_true")
    query.add_argument("--vector-only", action="store_true")
    args = parser.parse_args(argv)
    settings = Settings.from_env()
    try:
        if args.command == "fetch-sources":
            from ip_sakti.ingestion.acquire import fetch_sources
            report = fetch_sources(settings, args.sources)
            from ip_sakti.ingestion.prepare import write_json
            write_json(settings.reports_dir / "source-fetch.json", report)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 2 if report["failed"] else 0
        if args.command in ("prepare", "download-model", "ingest", "query", "evaluate-local"):
            from ip_sakti.embeddings.local import LocalEmbedder
            embedder = LocalEmbedder(settings.embedding_device)
        if args.command == "evaluate-local":
            from ip_sakti.evaluation.local import evaluate_local
            print(json.dumps(evaluate_local(settings, embedder, args.cases), ensure_ascii=False, indent=2))
            return 0
        if args.command == "download-model":
            print(json.dumps({"model": settings.embedding_model, "dimensions": len(embedder.query("test"))}))
            return 0
        if args.command == "prepare":
            from ip_sakti.ingestion.prepare import prepare_corpus
            report = prepare_corpus(settings, embedder.tokenizer, ocr=args.ocr, target_tokens=args.target_tokens)
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
            elif args.command == "ingest":
                from ip_sakti.storage.ingest import ingest_prepared
                print(json.dumps(ingest_prepared(settings, db, embedder), ensure_ascii=False, indent=2))
            elif args.command == "index-status":
                from ip_sakti.storage.indexes import wait_for_vector_index
                wait_for_vector_index(db)
                print("Vector index is queryable.")
            elif args.command == "query":
                from ip_sakti.retrieval.search import search
                print(json.dumps(search(db, embedder, args.question, jurisdiction=args.jurisdiction,
                                        top_k=args.top_k, include_unverified=args.include_unverified,
                                        hybrid=not args.vector_only), ensure_ascii=False, indent=2))
            else:
                print(json.dumps({
                    "database": settings.database,
                    "collections": {
                        name: db[name].estimated_document_count()
                        for name in sorted(db.list_collection_names())
                    },
                }, indent=2))
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


if __name__ == "__main__":
    raise SystemExit(main())

