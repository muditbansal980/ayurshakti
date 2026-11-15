"""Read-only report of database, model, and vector index state."""

from datetime import datetime, timezone

from pymongo.errors import OperationFailure, PyMongoError

from ip_sakti.embeddings.local import DIMENSIONS, MODEL, REVISION, cache_path, model_is_cached
from ip_sakti.storage.indexes import VECTOR_INDEX
from ip_sakti.storage.ingest import CONTRACT

COLLECTIONS = ("documents", "sections", "chunks", "ingestion_runs", "pipeline_metadata")


def _iso(value):
    return value.isoformat() if isinstance(value, datetime) else value


def _vector_index(db) -> dict:
    try:
        indexes = list(db.chunks.list_search_indexes(VECTOR_INDEX))
    except (OperationFailure, PyMongoError) as error:
        return {"name": VECTOR_INDEX, "status": "unsupported",
                "detail": f"vector search unavailable: {type(error).__name__}"}
    if not indexes:
        return {"name": VECTOR_INDEX, "status": "missing",
                "detail": "created automatically by sakti ingest"}
    index = indexes[0]
    fields = index.get("latestDefinition", {}).get("fields", [])
    vector = next((field for field in fields if field.get("type") == "vector"
                   and field.get("path") == "embedding"), {})
    return {"name": index.get("name", VECTOR_INDEX),
            "status": index.get("status", "unknown"),
            "queryable": bool(index.get("queryable")),
            "dimensions": vector.get("numDimensions"), "similarity": vector.get("similarity"),
            "path": vector.get("path"),
            "matches_expected": vector.get("numDimensions") == DIMENSIONS
            and vector.get("similarity") == "cosine"}


def pipeline_status(settings, db) -> dict:
    counts = {name: db[name].estimated_document_count() for name in COLLECTIONS}
    chunks = db.chunks
    total_chunks = chunks.count_documents({})
    with_embedding = chunks.count_documents({"embedding": {"$exists": True}})
    contract = db.pipeline_metadata.find_one({"_id": "embedding_contract"}) or {}
    ingestion = db.pipeline_metadata.find_one({"_id": "ingestion"}) or {}
    latest_run = db.ingestion_runs.find_one(sort=[("started_at", -1)])
    cache = cache_path(settings.model_cache_dir)
    active_generations = db.documents.count_documents({"active_generation": {"$exists": True}})
    return {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "database": {
            "name": settings.database,
            "collections": counts,
            "active_documents": active_generations,
            "chunks_with_embeddings": with_embedding,
            "chunks_without_embeddings": total_chunks - with_embedding,
        },
        "model": {
            "name": MODEL,
            "revision": REVISION,
            "dimensions": DIMENSIONS,
            "device": settings.embedding_device,
            "batch_size": settings.embedding_batch_size,
            "cached": model_is_cached(settings.model_cache_dir),
            "cache_dir": str(cache),
        },
        "embedding_contract": {
            "stored": contract or None,
            "matches_expected": bool(contract) and all(
                contract.get(key) == value for key, value in
                CONTRACT.items()
            ),
        },
        "last_ingestion": {key: _iso(value) for key, value in ingestion.items()} or None,
        "latest_run": None if not latest_run else {
            "id": latest_run["_id"], "status": latest_run.get("status"),
            "started_at": _iso(latest_run.get("started_at")),
            "finished_at": _iso(latest_run.get("finished_at")),
            "error": latest_run.get("error"),
        },
        "vector_index": _vector_index(db),
    }
