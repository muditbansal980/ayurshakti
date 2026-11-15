import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from ip_sakti.chunking.parent_child import stable_id
from ip_sakti.embeddings.local import LocalEmbedder, MODEL
from ip_sakti.retrieval.search import search
from ip_sakti.storage.ingest import ingest_prepared


def fake_embedder():
    embedder = MagicMock()
    embedder.model = [SimpleNamespace(auto_model=SimpleNamespace(config=SimpleNamespace(_commit_hash="revision")))]
    return embedder


class StorageTests(unittest.TestCase):
    def test_failed_embedding_never_activates_a_partial_generation(self):
        bundle = {"document": {"sha256": "sha", "title": "Act", "jurisdiction": "india", "review_status": "needs_review"},
                  "parents": [{"_id": "p"}], "children": [{"_id": str(i), "parent_id": "p", "embedding_text": "passage: text"} for i in range(17)], "warnings": []}
        generation = stable_id(json.dumps(bundle, sort_keys=True, ensure_ascii=False))
        bundle["generation"] = generation
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "bundle.json").write_text(json.dumps(bundle))
            (root / "manifest.json").write_text(json.dumps({"prepared": [{"bundle": "bundle.json", "generation": generation}]}))
            db = MagicMock()
            db.documents.find_one.return_value = {"active_generation": "previous-good"}
            db.pipeline_metadata.find_one.return_value = {"model": MODEL, "revision": "revision", "dimensions": 384, "normalization": "l2", "prefixes": "e5-query-passage"}
            embedder = fake_embedder()
            embedder.encode.side_effect = [[[0.0] * 384 for _ in range(16)], RuntimeError("simulated model failure")]
            with patch("ip_sakti.storage.ingest.initialize_database"), patch("ip_sakti.storage.ingest.ensure_indexes"):
                with self.assertRaisesRegex(RuntimeError, "simulated"):
                    ingest_prepared(SimpleNamespace(processed_dir=root), db, embedder)
            db.documents.replace_one.assert_not_called()
            self.assertEqual(db.ingestion_runs.update_one.call_args.args[1]["$set"]["status"], "failed")

    def test_tampered_bundle_is_rejected_before_document_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "bundle.json").write_text(json.dumps({"generation": "bad", "document": {}}))
            (root / "manifest.json").write_text(json.dumps({"prepared": [{"bundle": "bundle.json", "generation": "bad"}]}))
            db = MagicMock()
            db.pipeline_metadata.find_one.return_value = {"model": MODEL, "revision": "revision", "dimensions": 384, "normalization": "l2", "prefixes": "e5-query-passage"}
            with patch("ip_sakti.storage.ingest.initialize_database"), patch("ip_sakti.storage.ingest.ensure_indexes"):
                with self.assertRaisesRegex(ValueError, "changed"):
                    ingest_prepared(SimpleNamespace(processed_dir=root), db, fake_embedder())
            db.documents.replace_one.assert_not_called()


class RetrievalTests(unittest.TestCase):
    def test_one_whole_query_jurisdiction_and_active_generation_filters(self):
        db = MagicMock()
        db.documents.find.return_value = [{"_id": "d", "sha256": "sha", "active_generation": "good", "title": "Act", "local_file": "act.pdf", "review_status": "verified"}]
        db.pipeline_metadata.find_one.return_value = {"model": MODEL, "revision": "revision"}
        db.chunks.aggregate.return_value = [{"_id": "c", "document_id": "d", "parent_id": "p", "generation": "good", "text": "Clause", "pages": [2]}]
        db.sections.find_one.return_value = {"text": "Clause and exception", "locator": "Section 1", "pages": [2, 3]}
        embedder = fake_embedder()
        embedder.query.return_value = [0.0] * 384
        result = search(db, embedder, "पंजीकरण के नियम क्या हैं?", jurisdiction="india", hybrid=False)
        embedder.query.assert_called_once_with("पंजीकरण के नियम क्या हैं?")
        self.assertEqual(db.documents.find.call_args.args[0]["review_status"], "verified")
        filters = db.chunks.aggregate.call_args.args[0][0]["$vectorSearch"]["filter"]
        self.assertEqual(filters, {"generation": {"$in": ["good"]}, "jurisdiction": "india"})
        self.assertEqual(result["results"][0]["parent_text"], "Clause and exception")
        self.assertEqual(result["results"][0]["citation"]["parent_pdf_pages"], [2, 3])

    def test_no_verified_sources_does_not_search_unreviewed_documents(self):
        db = MagicMock()
        db.documents.find.return_value = []
        result = search(db, fake_embedder(), "Question", jurisdiction="india")
        self.assertEqual(result["results"], [])
        db.chunks.aggregate.assert_not_called()

    def test_long_query_is_rejected_before_model_loading(self):
        embedder = LocalEmbedder()
        tokenizer = MagicMock()
        tokenizer.encode.return_value = [1] * 513
        embedder.__dict__["tokenizer"] = tokenizer
        with self.assertRaisesRegex(ValueError, "truncation"):
            embedder.query("Long question")
        self.assertNotIn("model", embedder.__dict__)


if __name__ == "__main__":
    unittest.main()
