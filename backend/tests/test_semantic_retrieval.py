"""Semantic orchestration contracts; live Mongo coverage is separate."""
import unittest
from unittest.mock import MagicMock

from ip_sakti.embeddings.local import DIMENSIONS, MODEL, QUERY_PREFIX, REVISION
from ip_sakti.retrieval.search import RetrievalIntegrityError, RetrievalService, mongo_cosine_score, search
from ip_sakti.storage.ingest import CONTRACT


VECTOR = [1.0] + [0.0] * (DIMENSIONS - 1)


def fixture():
    db, embedder = MagicMock(), MagicMock()
    embedder.count.return_value = 12
    embedder.query.return_value = VECTOR
    db.documents.find.return_value.max_time_ms.return_value = [
        {"_id": "d", "active_generation": "g", "jurisdiction": "india", "review_status": "verified", "kind": "act", "language": "en"}]
    db.pipeline_metadata.find_one.return_value = dict(CONTRACT)
    db.chunks.list_search_indexes.return_value = [{"queryable": True, "latestDefinition": {"fields": [
        {"type": "vector", "path": "embedding", "numDimensions": DIMENSIONS, "similarity": "cosine"},
        {"type": "filter", "path": "generation"}, {"type": "filter", "path": "jurisdiction"}]}}]
    db.chunks.aggregate.return_value = [hit("c", "p", .95)]
    db.sections.find.return_value.max_time_ms.return_value = [parent("p"), parent("p2")]
    return db, embedder, RetrievalService(db, embedder)


def hit(identity, parent_id, score):
    return {"_id": identity, "document_id": "d", "parent_id": parent_id, "generation": "g", "jurisdiction": "india", "embedding": VECTOR, "embedding_model": MODEL, "embedding_revision": REVISION, "embedding_dimensions": DIMENSIONS, "vector_score": score, "text": "passage", "pages": [1]}


def parent(identity):
    return {"_id": identity, "document_id": "d", "generation": "g", "text": "Full section", "pages": [1, 2], "locator": "Section 1"}


class SemanticRetrievalTests(unittest.TestCase):
    def test_scores_order_threshold_and_distinct_parents(self):
        db, embedder, service = fixture()
        db.chunks.aggregate.return_value = [hit("z", "p", .95), hit("a", "p", .95), hit("b", "p2", .90), hit("low", "p3", .7)]
        result = service.retrieve("  प्रश्न  ", top_k=2, min_score=.8)
        self.assertEqual([x["chunk_id"] for x in result["results"]], ["a", "b"])
        self.assertAlmostEqual(result["results"][0]["score"], .9)
        embedder.query.assert_called_once_with("प्रश्न")
        embedder.count.assert_called_once_with(QUERY_PREFIX + "प्रश्न")
        db.sections.find.assert_called_once()
        db.sections.find_one.assert_not_called()
        self.assertNotIn("embedding", result["results"][0])
        self.assertNotIn("source_url", result["results"][0]["citation"])
        self.assertGreaterEqual(result["timings"]["total_ms"], result["timings"]["embedding_ms"])

    def test_filters_resolve_before_vector_query(self):
        db, _, service = fixture()
        filters = {"document_id": "d", "kind": "act", "language": "en", "jurisdiction": "india"}
        service.retrieve("rules", filters=filters)
        selection = db.documents.find.call_args.args[0]
        self.assertEqual(selection["_id"], "d")
        self.assertEqual(selection["language"], "en")
        self.assertEqual(selection["kind"], "act")
        self.assertEqual(selection["review_status"], "verified")
        stage = db.chunks.aggregate.call_args.args[0][0]["$vectorSearch"]
        self.assertEqual(stage["filter"], {"generation": {"$in": ["g"]}, "jurisdiction": "india"})
        self.assertLessEqual(stage["numCandidates"], 10000)

    def test_invalid_requests(self):
        for kwargs in ({"query": None}, {"query": 1}, {"query": " "}, {"top_k": True}, {"top_k": 0}, {"top_k": 21}, {"min_score": float("nan")}, {"min_score": True}, {"min_score": 1.1}, {"filters": {"section": "x"}}, {"filters": {"language": {"$ne": "en"}}}, {"filters": {"jurisdiction": "x"}}, {"include_unverified": 1}, {"query": "x" * 20001}):
            with self.subTest(kwargs=kwargs):
                db, embedder, service = fixture()
                with self.assertRaises(ValueError):
                    service.retrieve(**{"query": "rules", **kwargs})
                db.chunks.aggregate.assert_not_called()
                embedder.query.assert_not_called()

    def test_token_overflow_even_with_empty_database(self):
        db, embedder, service = fixture()
        embedder.count.return_value = 513
        db.documents.find.return_value.max_time_ms.return_value = []
        with self.assertRaisesRegex(ValueError, "truncation"):
            service.retrieve("long")
        embedder.query.assert_not_called()

    def test_language_filter_uses_supported_corpus_codes(self):
        for language in ("Hindi", "EN", "hi ", "fr"):
            db, embedder, service = fixture()
            with self.assertRaisesRegex(ValueError, "content language"):
                service.retrieve("rules", filters={"language": language})
            db.documents.find.assert_not_called()
            embedder.query.assert_not_called()

    def test_empty_eligible_and_zero_results(self):
        db, embedder, service = fixture()
        db.documents.find.return_value.max_time_ms.return_value = []
        self.assertEqual(service.retrieve("rules")["results"], [])
        embedder.query.assert_not_called()
        db.chunks.aggregate.assert_not_called()
        db, _, service = fixture()
        db.chunks.aggregate.return_value = []
        self.assertEqual(service.retrieve("rules")["results"], [])
        db.sections.find.assert_not_called()

    def test_bad_contract_or_index_is_operational_error(self):
        for key in CONTRACT:
            db, _, service = fixture()
            db.pipeline_metadata.find_one.return_value.pop(key)
            with self.assertRaises(RetrievalIntegrityError):
                service.retrieve("rules")
        for state in ([], [{"queryable": False}], [{"queryable": True, "latestDefinition": {}}]):
            db, _, service = fixture()
            db.chunks.list_search_indexes.return_value = state
            with self.assertRaises(RuntimeError):
                service.retrieve("rules")
            db.chunks.aggregate.assert_not_called()

    def test_invalid_stored_and_query_embeddings(self):
        for vector in (None, [], [1.0], [0.] * DIMENSIONS, [float("nan")] * DIMENSIONS, [True] + [0.] * (DIMENSIONS - 1)):
            db, _, service = fixture()
            db.chunks.aggregate.return_value[0]["embedding"] = vector
            with self.assertRaises(RetrievalIntegrityError):
                service.retrieve("rules")
            db, embedder, service = fixture()
            embedder.query.return_value = vector
            with self.assertRaises(RetrievalIntegrityError):
                service.retrieve("rules")

    def test_per_passage_contract_must_match_global_contract(self):
        for field, bad_value in (("embedding_model", "other-model"), ("embedding_revision", "other-revision"),
                                 ("embedding_dimensions", 768)):
            for missing in (False, True):
                with self.subTest(field=field, missing=missing):
                    db, _, service = fixture()
                    if missing:
                        db.chunks.aggregate.return_value[0].pop(field)
                    else:
                        db.chunks.aggregate.return_value[0][field] = bad_value
                    with self.assertRaisesRegex(RetrievalIntegrityError, "passage embedding contract"):
                        service.retrieve("rules")

    def test_malformed_relationships_have_integrity_errors(self):
        for update in ({"document_id": []}, {"document_id": None}, {"parent_id": []},
                       {"section_id": "different-parent"}):
            db, _, service = fixture()
            db.chunks.aggregate.return_value[0].update(update)
            with self.assertRaises(RetrievalIntegrityError):
                service.retrieve("rules")

    def test_pending_index_update_is_not_ready(self):
        for status in ("BUILDING", "PENDING", "FAILED"):
            db, _, service = fixture()
            db.chunks.list_search_indexes.return_value[0]["status"] = status
            with self.assertRaisesRegex(RuntimeError, "not queryable"):
                service.retrieve("rules")
            db.chunks.aggregate.assert_not_called()

    def test_ineligible_hits_are_excluded(self):
        for update in ({"document_id": "other"}, {"generation": "old"}, {"jurisdiction": "international"}):
            db, _, service = fixture()
            db.chunks.aggregate.return_value[0].update(update)
            self.assertEqual(service.retrieve("rules")["results"], [])

    def test_missing_or_incompatible_parent_is_error(self):
        for rows in ([], [{**parent("p"), "generation": "old"}], [{**parent("p"), "document_id": "other"}]):
            db, _, service = fixture()
            db.sections.find.return_value.max_time_ms.return_value = rows
            with self.assertRaises(RetrievalIntegrityError):
                service.retrieve("rules")

    def test_local_model_failure_is_operational(self):
        for method in ("count", "query"):
            db, embedder, service = fixture()
            getattr(embedder, method).side_effect = ValueError("bad local model")
            with self.assertRaises(RuntimeError):
                service.retrieve("rules")
            db.chunks.aggregate.assert_not_called()

    def test_scores_and_legacy_wrapper(self):
        self.assertEqual([mongo_cosine_score(x) for x in (0, .5, 1)], [-1, 0, 1])
        for score in (None, True, float("inf"), -.1, 1.1):
            with self.assertRaises(RetrievalIntegrityError):
                mongo_cosine_score(score)
        db, embedder, _ = fixture()
        with self.assertWarns(DeprecationWarning):
            result = search(db, embedder, "rules", jurisdiction="india", hybrid=True)
        self.assertEqual(result["results"][0]["parent_id"], "p")
        self.assertAlmostEqual(result["results"][0]["retrieval_score"], .9)

    def test_candidate_bound_is_reported(self):
        db, _, service = fixture()
        db.chunks.aggregate.return_value = [hit(str(i), "p", .9) for i in range(100)]
        result = service.retrieve("rules", top_k=1)
        self.assertTrue(result["candidate_limit_reached"])
        self.assertEqual(result["candidate_limit"], 100)
        self.assertEqual(len(result["results"]), 1)


if __name__ == "__main__":
    unittest.main()
