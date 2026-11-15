from pymongo import MongoClient

from ip_sakti.config import Settings


def create_client(settings: Settings) -> MongoClient:
    options = dict(serverSelectionTimeoutMS=10000, connectTimeoutMS=10000)
    if settings.mongodb_username:
        options.update(
            username=settings.mongodb_username,
            password=settings.mongodb_password,
            authSource="admin",
        )
    return MongoClient(settings.mongodb_uri, **options)


def initialize_database(db) -> None:
    """Idempotent, non-destructive initialization; never overwrites corpus data."""
    existing = set(db.list_collection_names())
    for name in ("documents", "sections", "chunks", "ingestion_runs", "pipeline_metadata"):
        if name not in existing:
            db.create_collection(name)
    db.documents.create_index("sha256", unique=True)
    db.sections.create_index("document_id")
    db.chunks.create_index([("document_id", 1), ("parent_id", 1)])
    db.pipeline_metadata.update_one(
        {"_id": "schema"}, {"$setOnInsert": {"version": 1}}, upsert=True
    )

