"""Stage complete immutable generations, then atomically switch the active pointer."""

import json
from datetime import datetime, timezone
from uuid import uuid4

from pymongo import ReplaceOne

from ip_sakti.chunking.parent_child import stable_id
from ip_sakti.embeddings.local import MODEL, DIMENSIONS
from ip_sakti.storage.indexes import ensure_indexes, wait_for_vector_index
from ip_sakti.storage.mongo import initialize_database


def ingest_prepared(settings, db, embedder) -> dict:
    manifest = json.loads((settings.processed_dir / "manifest.json").read_text())
    if not manifest["prepared"]:
        raise ValueError("No prepared documents. Run sakti prepare first.")
    initialize_database(db)
    ensure_indexes(db)
    # Loading once also records the actual downloaded model revision.
    revision = embedder.model[0].auto_model.config._commit_hash
    contract = {"model": MODEL, "revision": revision, "dimensions": DIMENSIONS,
                "normalization": "l2", "prefixes": "e5-query-passage"}
    db.pipeline_metadata.update_one({"_id": "embedding_contract"}, {"$setOnInsert": contract}, upsert=True)
    stored = db.pipeline_metadata.find_one({"_id": "embedding_contract"})
    if any(stored.get(key) != value for key, value in contract.items()):
        raise ValueError("Model revision differs from the stored corpus. Reindex into a new database.")
    run_id = str(uuid4())
    db.ingestion_runs.insert_one({"_id": run_id, "started_at": datetime.now(timezone.utc), "status": "running"})
    results = []
    try:
        for entry in manifest["prepared"]:
            bundle_path = settings.processed_dir / entry["bundle"]
            if bundle_path.parent.resolve() != settings.processed_dir.resolve():
                raise ValueError("Invalid bundle path in manifest.")
            bundle = json.loads(bundle_path.read_text())
            generation = bundle.pop("generation")
            if generation != entry["generation"] or generation != stable_id(json.dumps(bundle, sort_keys=True, ensure_ascii=False)):
                raise ValueError("Prepared bundle changed since preparation. Rerun sakti prepare.")
            metadata = bundle["document"]
            current = db.documents.find_one({"_id": metadata["sha256"]})
            if current and current.get("active_generation") == generation:
                results.append({"document": metadata["title"], "status": "unchanged"})
                continue
            parent_ids = {parent["_id"]: stable_id(generation, parent["_id"]) for parent in bundle["parents"]}
            for parent in bundle["parents"]:
                item = {**parent, "_id": parent_ids[parent["_id"]], "generation": generation}
                db.sections.replace_one({"_id": item["_id"]}, item, upsert=True)
            children = bundle["children"]
            for start in range(0, len(children), 16):
                batch = children[start:start + 16]
                vectors = embedder.encode([child["embedding_text"] for child in batch])
                operations = []
                for child, vector in zip(batch, vectors, strict=True):
                    item = {**child, "_id": stable_id(generation, child["_id"]),
                            "parent_id": parent_ids[child["parent_id"]], "generation": generation,
                            "embedding": vector, "title": metadata["title"],
                            "jurisdiction": metadata["jurisdiction"], "review_status": metadata["review_status"]}
                    operations.append(ReplaceOne({"_id": item["_id"]}, item, upsert=True))
                db.chunks.bulk_write(operations, ordered=False)
            if db.chunks.count_documents({"generation": generation}) != len(children):
                raise ValueError("Incomplete generation; active document was not changed.")
            db.documents.replace_one({"_id": metadata["sha256"]}, {
                **metadata, "_id": metadata["sha256"], "active_generation": generation,
                "parent_count": len(bundle["parents"]), "child_count": len(children),
                "warnings": bundle["warnings"], "indexed_at": datetime.now(timezone.utc),
            }, upsert=True)
            results.append({"document": metadata["title"], "status": "ingested", "children": len(children)})
        wait_for_vector_index(db)
        db.ingestion_runs.update_one({"_id": run_id}, {"$set": {"status": "complete", "finished_at": datetime.now(timezone.utc), "results": results}})
        return {"run_id": run_id, "results": results, "note": "Search indexing is asynchronous; newly written passages may take time to appear."}
    except Exception:
        db.ingestion_runs.update_one({"_id": run_id}, {"$set": {"status": "failed", "finished_at": datetime.now(timezone.utc)}})
        raise

