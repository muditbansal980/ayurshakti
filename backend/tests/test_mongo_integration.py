"""Opt-in checks against real MongoDB Search, using an isolated temporary database."""

import os
import time
import unittest
from uuid import uuid4

from ip_sakti.config import Settings
from ip_sakti.embeddings.local import DIMENSIONS, MODEL, REVISION
from ip_sakti.retrieval.search import search
from ip_sakti.storage.indexes import ensure_indexes, wait_for_vector_index
from ip_sakti.storage.mongo import create_client, initialize_database
from ip_sakti.storage.ingest import CONTRACT
from ip_sakti.storage.search import RetrievalIntegrityError


class FixtureEmbedder:
    def count(self, text):
        return 10

    def query(self, question):
        return [1.0] + [0.0] * (DIMENSIONS - 1)


@unittest.skipUnless(os.getenv("RUN_MONGO_INTEGRATION") == "1", "Requires a running MongoDB Search deployment")
class MongoIntegrationTests(unittest.TestCase):
    def test_real_vector_filter_parent_citation_and_failure_handling(self):
        with create_client(Settings.from_env()) as client:
            db = client["sakti_test_" + uuid4().hex]
            try:
                initialize_database(db)
                initialize_database(db)
                ensure_indexes(db)
                db.pipeline_metadata.insert_one({"_id": "embedding_contract", **CONTRACT})
                db.documents.insert_one({"_id": "d", "sha256": "sha", "active_generation": "active", "jurisdiction": "india", "review_status": "verified", "title": "Test Act", "local_file": "test.pdf"})
                db.sections.insert_one({"_id": "parent", "document_id": "d", "generation": "active", "locator": "Section 1", "text": "Registration requires approval. An exception applies.", "pages": [1, 2]})
                for identity, generation, jurisdiction in [("valid", "active", "india"), ("stale", "old", "india"), ("foreign", "active", "international")]:
                    db.chunks.insert_one({"_id": identity, "document_id": "d", "parent_id": "parent", "generation": generation, "jurisdiction": jurisdiction, "review_status": "verified", "embedding": [1.0] + [0.0] * (DIMENSIONS - 1), "embedding_model": MODEL, "embedding_revision": REVISION, "embedding_dimensions": DIMENSIONS, "text": "Registration requires approval.", "title": "Test Act", "locator": "Section 1", "pages": [1]})
                wait_for_vector_index(db)
                # Queryable does not mean all recently inserted documents have
                # reached the asynchronous search index. Poll with a deadline.
                deadline = time.monotonic() + 90
                while time.monotonic() < deadline:
                    result = search(db, FixtureEmbedder(), "registration approval", jurisdiction="india", hybrid=False)
                    if result["results"]:
                        break
                    time.sleep(2)
                self.assertEqual(len(result["results"]), 1)
                self.assertAlmostEqual(result["results"][0]["score"], 1.0, places=5)
                self.assertEqual(result["results"][0]["chunk_id"], "valid")
                self.assertEqual(result["results"][0]["citation"]["provision"], "Section 1")
                self.assertIn("exception", result["results"][0]["parent_text"])
                hybrid = search(db, FixtureEmbedder(), "registration approval", jurisdiction="india")
                self.assertEqual(len(hybrid["results"]), 1)
                # Foreign-only query has no eligible document, even though a
                # matching foreign child was deliberately inserted above.
                self.assertEqual(search(db, FixtureEmbedder(), "registration", jurisdiction="international")["results"], [])
                self.assertEqual(search(db, FixtureEmbedder(), "registration", filters={"document_id": "missing"})["results"], [])
                self.assertNotIn("source_url", result["results"][0]["citation"])
                db.sections.delete_one({"_id": "parent"})
                with self.assertRaises(RetrievalIntegrityError):
                    search(db, FixtureEmbedder(), "registration", jurisdiction="india")
            finally:
                client.drop_database(db.name)


if __name__ == "__main__":
    unittest.main()
