import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from ip_sakti.embeddings.local import DIMENSIONS, MODEL, REVISION
from ip_sakti.storage.status import pipeline_status


class FakeCollection:
    def __init__(self, documents=0, with_embedding=0):
        self.documents = documents
        self.with_embedding = with_embedding

    def estimated_document_count(self):
        return self.documents

    def count_documents(self, query):
        if "embedding" in json.dumps(query):
            return self.with_embedding
        return self.documents

    def list_search_indexes(self, name=None):
        return [{"name": name, "status": "READY", "queryable": True}]


class FakeDatabase(dict):
    def __init__(self):
        super().__init__({
            "documents": FakeCollection(7),
            "sections": FakeCollection(604),
            "chunks": FakeCollection(866, 866),
        })
        self.metadata = {
            "embedding_contract": {"_id": "embedding_contract", "model": MODEL,
                                   "revision": REVISION, "dimensions": DIMENSIONS,
                                   "normalization": "l2", "prefixes": "e5-query-passage"},
            "ingestion": {"_id": "ingestion", "last_completed_at": datetime.now(timezone.utc),
                          "chunks": 866},
        }

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as error:
            raise AttributeError(name) from error

    def __getitem__(self, name):
        if name == "pipeline_metadata":
            return SimpleNamespace(
                estimated_document_count=lambda: len(self.metadata),
                find_one=lambda query: self.metadata.get(query["_id"]))
        if name == "ingestion_runs":
            return SimpleNamespace(
                estimated_document_count=lambda: 2,
                find_one=lambda **kwargs: {
                    "_id": "run", "status": "completed",
                    "started_at": datetime.now(timezone.utc),
                    "finished_at": datetime.now(timezone.utc)})
        return super().__getitem__(name)


class StatusTests(unittest.TestCase):
    def test_status_does_not_invent_index_definition_or_valid_contract(self):
        settings = SimpleNamespace(database="test", embedding_device="cpu",
                                   embedding_batch_size=16, model_cache_dir=Path("/tmp/none"))
        db = FakeDatabase()
        del db.metadata["embedding_contract"]["normalization"]
        report = pipeline_status(settings, db)
        self.assertFalse(report["embedding_contract"]["matches_expected"])
        self.assertFalse(report["vector_index"]["matches_expected"])
        self.assertIsNone(report["vector_index"]["dimensions"])

    def test_report_is_json_serializable_and_reports_embedding_coverage(self):
        settings = SimpleNamespace(database="sakti_sahayak", embedding_device="cpu",
                                   embedding_batch_size=16, model_cache_dir=Path("/tmp/none"))
        report = pipeline_status(settings, FakeDatabase())

        json.dumps(report)  # datetimes must already be ISO strings
        self.assertEqual(report["database"]["chunks_with_embeddings"], 866)
        self.assertEqual(report["database"]["chunks_without_embeddings"], 0)
        self.assertTrue(report["embedding_contract"]["matches_expected"])
        self.assertTrue(report["vector_index"]["queryable"])
        self.assertEqual(report["model"]["dimensions"], DIMENSIONS)
        self.assertFalse(report["model"]["cached"])


if __name__ == "__main__":
    unittest.main()
