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
        if indexes and indexes[0].get("queryable"):
            return
        if indexes and indexes[0].get("status") == "FAILED":
            raise ValueError("MongoDB vector index failed. Inspect the database logs.")
        time.sleep(2)
    raise ValueError("Vector index is not queryable yet. Wait, then rerun sakti index-status.")

