"""MongoDB-only access for semantic retrieval; never fall back to a corpus scan."""

from ip_sakti.storage.indexes import VECTOR_INDEX, require_vector_index
from ip_sakti.storage.ingest import CONTRACT


class RetrievalIntegrityError(RuntimeError):
    """Stored corpus data cannot safely be used for retrieval."""


class SearchRepository:
    def __init__(self, db):
        self.db = db

    def eligible_documents(self, filters, include_unverified):
        selection = {"active_generation": {"$type": "string", "$ne": ""}}
        selection.update({"_id" if key == "document_id" else key: value
                          for key, value in filters.items()})
        if not include_unverified:
            selection["review_status"] = "verified"
        return {row["_id"]: row for row in self.db.documents.find(selection).max_time_ms(10000)}

    def check_contract_and_index(self):
        stored = self.db.pipeline_metadata.find_one({"_id": "embedding_contract"}) or {}
        if any(stored.get(key) != value for key, value in CONTRACT.items()):
            raise RetrievalIntegrityError("Query model does not match the stored embedding contract; re-embed the corpus.")
        require_vector_index(self.db)

    def candidates(self, vector, documents, filters, limit):
        selection = {"generation": {"$in": sorted({d["active_generation"] for d in documents.values()})}}
        if "jurisdiction" in filters:
            selection["jurisdiction"] = filters["jurisdiction"]
        return list(self.db.chunks.aggregate([
            {"$vectorSearch": {"index": VECTOR_INDEX, "path": "embedding", "queryVector": vector,
                               "filter": selection, "numCandidates": min(limit * 20, 10000), "limit": limit}},
            {"$set": {"vector_score": {"$meta": "vectorSearchScore"}}},
            {"$project": {"embedding_text": 0}},
        ], maxTimeMS=10000))

    def parents(self, hits):
        if not hits:
            return {}
        return {row["_id"]: row for row in self.db.sections.find(
            {"_id": {"$in": sorted({hit["parent_id"] for hit in hits})}}
        ).max_time_ms(10000)}
