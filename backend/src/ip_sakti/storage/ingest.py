"""Stage complete immutable generations, then atomically switch the active pointer."""

import json
import logging
from datetime import datetime, timezone
from uuid import uuid4

from pymongo import UpdateOne

from ip_sakti.chunking.parent_child import PIPELINE_VERSION, stable_id
from ip_sakti.embeddings.local import DIMENSIONS, MODEL, REVISION, validate_vectors
from ip_sakti.storage.indexes import ensure_indexes, wait_for_vector_index
from ip_sakti.storage.mongo import initialize_database

log = logging.getLogger(__name__)

CONTRACT = {
    "model": MODEL,
    "revision": REVISION,
    "dimensions": DIMENSIONS,
    "normalization": "l2",
    "prefixes": "e5-query-passage",
}


def _verify_contract(db) -> None:
    """Refuse to mix vectors from different models, revisions, or dimensions."""
    db.pipeline_metadata.update_one(
        {"_id": "embedding_contract"}, {"$setOnInsert": CONTRACT}, upsert=True
    )
    stored = db.pipeline_metadata.find_one({"_id": "embedding_contract"}) or {}
    mismatched = {
        key: (stored.get(key), value)
        for key, value in CONTRACT.items()
        if stored.get(key) != value
    }
    if mismatched:
        details = ", ".join(f"{key}: stored={old!r} required={new!r}"
                            for key, (old, new) in mismatched.items())
        raise ValueError(
            f"Stored embedding contract is incompatible ({details}). "
            "Re-embed explicitly into a fresh database instead of mixing vectors."
        )


def _chunk_document(child: dict, *, generation: str, parent_id: str, vector: list[float],
                    metadata: dict, pipeline_version: str, target_tokens: int) -> dict:
    return {
        **child,
        "_id": stable_id(generation, child["_id"]),
        "section_id": parent_id,      # schema name for the parent section
        "parent_id": parent_id,       # kept: retrieval and citations read this field
        "generation": generation,
        "embedding": vector,
        "embedding_model": MODEL,
        "embedding_revision": REVISION,
        "embedding_dimensions": DIMENSIONS,
        "metadata": {"pipeline_version": pipeline_version, "target_tokens": target_tokens},
        "title": metadata["title"],
        "jurisdiction": metadata["jurisdiction"],
        "review_status": metadata["review_status"],
    }


def ingest_prepared(settings, db, embedder) -> dict:
    manifest = json.loads((settings.processed_dir / "manifest.json").read_text())
    if not manifest["prepared"]:
        raise ValueError("No prepared documents. Run sakti prepare first.")
    initialize_database(db)
    ensure_indexes(db)
    _verify_contract(db)

    batch_size = getattr(settings, "embedding_batch_size", 16)
    run_id = str(uuid4())
    db.ingestion_runs.insert_one({
        "_id": run_id, "started_at": datetime.now(timezone.utc), "status": "processing",
        "model": MODEL, "revision": REVISION,
    })
    results: list[dict] = []
    index_state = "queryable"
    try:
        for entry in manifest["prepared"]:
            bundle_path = settings.processed_dir / entry["bundle"]
            if bundle_path.parent.resolve() != settings.processed_dir.resolve():
                raise ValueError("Invalid bundle path in manifest.")
            bundle = json.loads(bundle_path.read_text())
            generation = bundle.pop("generation")
            if generation != entry["generation"] or generation != stable_id(
                json.dumps(bundle, sort_keys=True, ensure_ascii=False)
            ):
                raise ValueError("Prepared bundle changed since preparation. Rerun sakti prepare.")

            metadata = bundle["document"]
            pipeline_version = bundle.get("pipeline_version", PIPELINE_VERSION)
            target_tokens = bundle.get("target_tokens", 384)
            current = db.documents.find_one({"_id": metadata["sha256"]})
            if current and current.get("active_generation") == generation:
                results.append({"document": metadata["title"], "status": "unchanged"})
                log.info("Unchanged, skipped: %s", metadata["title"])
                continue

            parent_ids = {parent["_id"]: stable_id(generation, parent["_id"])
                          for parent in bundle["parents"]}
            for parent in bundle["parents"]:
                item = {**parent, "_id": parent_ids[parent["_id"]], "generation": generation}
                db.sections.replace_one({"_id": item["_id"]}, item, upsert=True)

            children = bundle["children"]
            embedded = 0
            for start in range(0, len(children), batch_size):
                batch = children[start:start + batch_size]
                vectors = embedder.encode([child["embedding_text"] for child in batch])
                validate_vectors(vectors)
                now = datetime.now(timezone.utc)
                operations = [
                    UpdateOne(
                        {"_id": stable_id(generation, child["_id"])},
                        {"$set": {**_chunk_document(child, generation=generation,
                                                    parent_id=parent_ids[child["parent_id"]],
                                                    vector=vector, metadata=metadata,
                                                    pipeline_version=pipeline_version,
                                                    target_tokens=target_tokens),
                                  "updated_at": now},
                         "$setOnInsert": {"created_at": now}},
                        upsert=True,
                    )
                    for child, vector in zip(batch, vectors, strict=True)
                ]
                db.chunks.bulk_write(operations, ordered=False)
                embedded += len(batch)

            stored = db.chunks.count_documents({"generation": generation,
                                                "embedding": {"$exists": True}})
            if stored != len(children):
                raise ValueError(
                    f"Only {stored} of {len(children)} chunks have embeddings; "
                    "the active document was not changed."
                )
            db.documents.replace_one({"_id": metadata["sha256"]}, {
                **metadata, "_id": metadata["sha256"], "active_generation": generation,
                "parent_count": len(bundle["parents"]), "child_count": len(children),
                "warnings": bundle["warnings"], "indexed_at": datetime.now(timezone.utc),
            }, upsert=True)
            results.append({"document": metadata["title"], "status": "ingested",
                            "sections": len(bundle["parents"]), "chunks": len(children),
                            "embedded": embedded})
            log.info("Ingested %s (%d chunks)", metadata["title"], embedded)

        try:
            wait_for_vector_index(db)
        except ValueError as warning:
            # Vectors are already durable; index readiness is not data loss.
            index_state = "not_queryable"
            log.warning("Vector index not ready: %s", warning)
    except Exception as error:
        status = "partially_completed" if results else "failed"
        db.ingestion_runs.update_one({"_id": run_id}, {"$set": {
            "status": status, "finished_at": datetime.now(timezone.utc),
            "results": results, "error": f"{type(error).__name__}: {error}",
        }})
        raise

    now = datetime.now(timezone.utc)
    db.ingestion_runs.update_one({"_id": run_id}, {"$set": {
        "status": "completed", "finished_at": now, "results": results,
        "vector_index": index_state,
    }})
    db.pipeline_metadata.update_one({"_id": "ingestion"}, {"$set": {
        "schema_version": 1, "last_completed_at": now, "last_run_id": run_id,
        "chunking": PIPELINE_VERSION,
        "documents": db.documents.count_documents({"active_generation": {"$exists": True}}),
        "chunks": db.chunks.count_documents({"embedding": {"$exists": True}}),
    }}, upsert=True)
    return {"run_id": run_id, "results": results, "vector_index": index_state,
            "note": "Search indexing is asynchronous; newly written passages may take time to appear."}
