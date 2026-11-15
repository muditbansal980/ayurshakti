import time

from pymongo.operations import SearchIndexModel

from ip_sakti.embeddings.local import DIMENSIONS

VECTOR_INDEX = "corpus_vector_v1"


def ensure_indexes(db) -> None:
    definition = {"fields": [
        {"type": "vector", "path": "embedding", "numDimensions": DIMENSIONS, "similarity": "cosine"},
        {"type": "filter", "path": "generation"},
        {"type": "filter", "path": "jurisdiction"},
        {"type": "filter", "path": "review_status"},
    ]}
    existing = list(db.chunks.list_search_indexes(VECTOR_INDEX))
    if not existing:
        db.chunks.create_search_index(SearchIndexModel(name=VECTOR_INDEX, type="vectorSearch", definition=definition))
    elif existing[0].get("latestDefinition") != definition:
        raise ValueError("Existing vector index has a different definition; migrate explicitly instead of overwriting it.")
    # Native MongoDB keyword search is useful for exact legal terminology. With
    # language=none it does not apply an English stemmer to Hindi text.
    db.chunks.create_index([("text", "text"), ("title", "text"), ("locator", "text")],
                           name="corpus_keywords_v1", default_language="none")


def wait_for_vector_index(db, timeout: int = 120) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        indexes = list(db.chunks.list_search_indexes(VECTOR_INDEX))
        if indexes and indexes[0].get("queryable") is True and indexes[0].get("status") in (None, "READY"):
            return
        if indexes and indexes[0].get("status") == "FAILED":
            raise ValueError("MongoDB vector index failed. Inspect the database logs.")
        time.sleep(2)
    raise ValueError("Vector index is not queryable yet. Wait, then rerun sakti index-status.")



def require_vector_index(db) -> None:
    """Readiness is checked at request time; retrieval never creates indexes."""
    indexes = list(db.chunks.list_search_indexes(VECTOR_INDEX))
    if not indexes or indexes[0].get("queryable") is not True or indexes[0].get("status") not in (None, "READY"):
        raise RuntimeError("MongoDB vector index is not queryable. Run sakti create-index and check index-status.")
    fields = indexes[0].get("latestDefinition", {}).get("fields", [])
    vector = [field for field in fields if field.get("path") == "embedding"]
    expected = {"type": "vector", "path": "embedding", "numDimensions": DIMENSIONS, "similarity": "cosine"}
    filters = {field.get("path") for field in fields if field.get("type") == "filter"}
    if vector != [expected] or not {"generation", "jurisdiction"}.issubset(filters):
        raise RuntimeError("MongoDB vector index is incompatible; expected cosine, 384 dimensions and generation/jurisdiction filters.")
