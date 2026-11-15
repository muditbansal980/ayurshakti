import json
import math
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from ip_sakti.chunking.parent_child import build_chunks, build_embedding_header, stable_id
from ip_sakti.embeddings.local import (
    DIMENSIONS, MODEL, REVISION, LocalEmbedder, cache_path, model_is_cached,
    validate_vector, validate_vectors,
)
from ip_sakti.storage.ingest import ingest_prepared


class VectorValidationTests(unittest.TestCase):
    def test_rejects_zero_non_unit_and_boolean_vectors(self):
        for vector in ([0.0] * DIMENSIONS, [1.0] * DIMENSIONS,
                       [True] + [0.0] * (DIMENSIONS - 1)):
            with self.subTest(vector=vector[:2]), self.assertRaises(ValueError):
                validate_vector(vector)

    def test_rejects_wrong_dimension(self):
        with self.assertRaisesRegex(ValueError, "dimensions"):
            validate_vector([0.1] * 383)

    def test_rejects_empty_and_non_finite(self):
        with self.assertRaisesRegex(ValueError, "non-empty"):
            validate_vector([])
        for bad in (float("nan"), float("inf"), -float("inf")):
            with self.assertRaisesRegex(ValueError, "non-finite"):
                validate_vector([bad] + [0.0] * (DIMENSIONS - 1))

    def test_rejects_empty_batch(self):
        with self.assertRaisesRegex(ValueError, "no vectors"):
            validate_vectors([])

    def test_accepts_a_valid_normalized_vector(self):
        vector = [1 / math.sqrt(DIMENSIONS)] * DIMENSIONS
        validate_vector(vector)


class FakeArray(list):
    """Stands in for the numpy array sentence-transformers returns."""

    def tolist(self):
        return list(self)


class ModelPinningTests(unittest.TestCase):
    def test_rejects_output_count_mismatch(self):
        embedder = LocalEmbedder()
        embedder.__dict__["tokenizer"] = SimpleNamespace(encode=lambda *a, **kw: [1])
        embedder.__dict__["model"] = SimpleNamespace(
            encode=lambda *a, **kw: FakeArray([[1.0] + [0.0] * 383] * 2))
        with self.assertRaisesRegex(ValueError, "count"):
            embedder.query("one input")

    def test_invalid_inputs_and_batch_override_fail_before_loading(self):
        embedder = LocalEmbedder()
        for texts in ([], "text", [None], [" "]):
            with self.subTest(texts=texts), self.assertRaises(ValueError):
                embedder.encode(texts)
        for batch_size in (0, -1, True, 1.5):
            with self.subTest(batch_size=batch_size), self.assertRaisesRegex(ValueError, "batch size"):
                embedder.encode(["passage: text"], batch_size=batch_size)
        self.assertNotIn("model", embedder.__dict__)

    def test_runtime_model_sequence_limit_is_verified(self):
        import sys
        model = MagicMock()
        model.get_embedding_dimension.return_value = DIMENSIONS
        model.max_seq_length = 128
        module = SimpleNamespace(SentenceTransformer=MagicMock(return_value=model))
        with patch.dict(sys.modules, {"sentence_transformers": module}):
            with self.assertRaisesRegex(ValueError, "sequence limit"):
                LocalEmbedder().model

    def test_constants_are_pinned(self):
        self.assertEqual(MODEL, "intfloat/multilingual-e5-small")
        self.assertEqual(REVISION, "614241f622f53c4eeff9890bdc4f31cfecc418b3")
        self.assertEqual(DIMENSIONS, 384)

    def test_refuses_a_different_model_instead_of_falling_back(self):
        with self.assertRaisesRegex(ValueError, "pinned to"):
            LocalEmbedder(model="sentence-transformers/all-MiniLM-L6-v2")

    def test_refuses_a_different_revision(self):
        with self.assertRaisesRegex(ValueError, "pinned to revision"):
            LocalEmbedder(revision="main")

    def test_query_uses_the_e5_query_prefix(self):
        embedder = LocalEmbedder()
        tokenizer = MagicMock()
        tokenizer.encode.return_value = [1, 2, 3]
        embedder.__dict__["tokenizer"] = tokenizer
        embedder.__dict__["model"] = SimpleNamespace(
            encode=MagicMock(return_value=FakeArray([[0.0] * 383 + [1.0]]))
        )
        embedder.query("धारा 12 क्या है?")
        self.assertEqual(embedder.model.encode.call_args.args[0], ["query: धारा 12 क्या है?"])

    def test_encode_validates_dimension_before_persistence(self):
        embedder = LocalEmbedder()
        tokenizer = MagicMock()
        tokenizer.encode.return_value = [1, 2, 3]
        embedder.__dict__["tokenizer"] = tokenizer
        embedder.__dict__["model"] = SimpleNamespace(
            encode=lambda texts, **kwargs: FakeArray([[0.0] * 10 for _ in texts])
        )
        with self.assertRaisesRegex(ValueError, "dimensions"):
            embedder.encode(["passage: text"])

    def test_cache_helpers_detect_missing_weights(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertFalse(model_is_cached(root))
            self.assertEqual(cache_path(root), root / "hub" / "models--intfloat--multilingual-e5-small")
            snapshot = cache_path(root).glob("snapshots")
            self.assertFalse(any(snapshot))

    def test_cache_requires_pinned_weights_and_tokenizer(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            wrong = cache_path(root) / "snapshots" / "wrong-revision"
            wrong.mkdir(parents=True)
            (wrong / "model.safetensors").write_text("weights")
            self.assertFalse(model_is_cached(root))
            pinned = wrong.parent / REVISION
            pinned.mkdir()
            for filename in ("config.json", "modules.json", "tokenizer_config.json", "tokenizer.json"):
                (pinned / filename).write_text("{}")
            self.assertFalse(model_is_cached(root))
            (pinned / "model.safetensors").write_text("weights")
            self.assertTrue(model_is_cached(root))
            (pinned / "model.safetensors").unlink()
            (pinned / "model.safetensors").symlink_to(pinned / "missing")
            self.assertFalse(model_is_cached(root))


class ChunkEmbeddingContractTests(unittest.TestCase):
    def test_embedding_text_carries_title_and_locator(self):
        header = build_embedding_header(
            {"title": "The Trade Marks Act, 1999"}, {"locator": "Section 12"}
        )
        self.assertEqual(header, "passage: The Trade Marks Act, 1999 | Section 12\n")

    def test_hindi_and_english_chunks_both_get_the_passage_prefix(self):
        class Tokenizer:
            def encode(self, text, add_special_tokens=True, **kwargs):
                return list(range(len(text)))

            def __call__(self, text, **kwargs):
                return {"offset_mapping": [(i, i + 1) for i in range(len(text))]}

        pages = [{"page": 1, "text": "1. अंग्रेज़ी text.—धारा लागू है।"}]
        document = {"sha256": "sha", "title": "नमूना अधिनियम"}
        _, children = build_chunks(document, pages, [{
            "locator": "Section 1", "start": 0, "end": len(pages[0]["text"]),
            "text": pages[0]["text"], "pages": [1],
        }], Tokenizer(), target_tokens=160)
        self.assertTrue(children)
        for child in children:
            self.assertTrue(child["embedding_text"].startswith("passage: नमूना अधिनियम | Section 1\n"))


def _bundle(children=2):
    bundle = {
        "pipeline_version": "section-parent-child-v1",
        "target_tokens": 384,
        "document": {"sha256": "sha", "title": "परीक्षण Act", "jurisdiction": "india",
                     "review_status": "needs_review", "local_file": "act.pdf"},
        "parents": [{"_id": "p", "locator": "Section 1", "text": "text", "pages": [1]}],
        "children": [{"_id": f"c{i}", "parent_id": "p", "embedding_text": "passage: x",
                      "text": "x", "locator": "Section 1", "pages": [1], "token_count": 3}
                     for i in range(children)],
        "warnings": [],
    }
    generation = stable_id(json.dumps(bundle, sort_keys=True, ensure_ascii=False))
    bundle["generation"] = generation
    return bundle, generation


CONTRACT = {"_id": "embedding_contract", "model": MODEL, "revision": REVISION,
            "dimensions": DIMENSIONS, "normalization": "l2", "prefixes": "e5-query-passage"}


class PersistenceTests(unittest.TestCase):
    def _run(self, db, embedder, bundle, generation, batch_size=16):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "bundle.json").write_text(json.dumps(bundle))
            (root / "manifest.json").write_text(json.dumps(
                {"prepared": [{"bundle": "bundle.json", "generation": generation}]}))
            with patch("ip_sakti.storage.ingest.initialize_database"), \
                 patch("ip_sakti.storage.ingest.ensure_indexes"), \
                 patch("ip_sakti.storage.ingest.wait_for_vector_index"):
                return ingest_prepared(
                    SimpleNamespace(processed_dir=root, embedding_batch_size=batch_size),
                    db, embedder)

    def test_every_chunk_is_persisted_with_embedding_provenance(self):
        bundle, generation = _bundle()
        db = MagicMock()
        db.documents.find_one.return_value = None
        db.pipeline_metadata.find_one.side_effect = lambda query: CONTRACT if query["_id"] == "embedding_contract" else None
        db.chunks.count_documents.return_value = 2
        db.chunks.bulk_write.side_effect = lambda operations, ordered: [SimpleNamespace(upserted_count=len(operations))]
        embedder = MagicMock()
        embedder.encode.return_value = [[1.0] + [0.0] * (DIMENSIONS - 1)] * 2

        result = self._run(db, embedder, bundle, generation)

        self.assertEqual(result["vector_index"], "queryable")
        chunk = db.chunks.bulk_write.call_args.args[0][0]._doc["$set"]
        self.assertEqual(chunk["embedding_model"], MODEL)
        self.assertEqual(chunk["embedding_revision"], REVISION)
        self.assertEqual(chunk["embedding_dimensions"], DIMENSIONS)
        self.assertEqual(len(chunk["embedding"]), DIMENSIONS)
        self.assertEqual(chunk["section_id"], chunk["parent_id"])
        self.assertEqual(chunk["metadata"]["pipeline_version"], "section-parent-child-v1")
        self.assertIn("created_at", db.chunks.bulk_write.call_args.args[0][0]._doc["$setOnInsert"])
        self.assertIn("updated_at", chunk)
        self.assertEqual(db.ingestion_runs.update_one.call_args_list[-1].args[1]["$set"]["status"], "completed")
        self.assertEqual(embedder.encode.call_count, 1)  # 2 children, one batch

    def test_unchanged_generation_is_not_embedded_or_rewritten(self):
        bundle, generation = _bundle()
        db = MagicMock()
        db.documents.find_one.return_value = {"active_generation": generation}
        db.pipeline_metadata.find_one.side_effect = lambda query: CONTRACT if query["_id"] == "embedding_contract" else None
        embedder = MagicMock()

        result = self._run(db, embedder, bundle, generation)

        embedder.encode.assert_not_called()
        db.chunks.bulk_write.assert_not_called()
        self.assertEqual(result["results"][0]["status"], "unchanged")

    def test_missing_embeddings_do_not_activate_the_generation(self):
        bundle, generation = _bundle()
        db = MagicMock()
        db.documents.find_one.return_value = None
        db.pipeline_metadata.find_one.side_effect = lambda query: CONTRACT if query["_id"] == "embedding_contract" else None
        db.chunks.count_documents.return_value = 0  # nothing persisted
        embedder = MagicMock()
        embedder.encode.return_value = [[1.0] + [0.0] * (DIMENSIONS - 1)] * 2

        with self.assertRaisesRegex(ValueError, "have embeddings"):
            self._run(db, embedder, bundle, generation)
        db.documents.replace_one.assert_not_called()

    def test_partial_failure_marks_the_run_partially_completed(self):
        first, first_generation = _bundle(children=1)
        second, second_generation = _bundle(children=1)
        second["document"] = {**second["document"], "sha256": "sha2"}
        second["generation"] = stable_id(json.dumps({k: v for k, v in second.items() if k != "generation"},
                                                    sort_keys=True, ensure_ascii=False))
        second_generation = second["generation"]
        db = MagicMock()
        db.documents.find_one.return_value = None
        db.pipeline_metadata.find_one.side_effect = lambda query: CONTRACT if query["_id"] == "embedding_contract" else None
        db.chunks.count_documents.return_value = 1
        embedder = MagicMock()
        embedder.encode.side_effect = [[[1.0] + [0.0] * (DIMENSIONS - 1)], RuntimeError("disk full")]

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "a.json").write_text(json.dumps(first))
            (root / "b.json").write_text(json.dumps(second))
            (root / "manifest.json").write_text(json.dumps({"prepared": [
                {"bundle": "a.json", "generation": first_generation},
                {"bundle": "b.json", "generation": second_generation},
            ]}))
            with patch("ip_sakti.storage.ingest.initialize_database"), \
                 patch("ip_sakti.storage.ingest.ensure_indexes"), \
                 patch("ip_sakti.storage.ingest.wait_for_vector_index"):
                with self.assertRaisesRegex(RuntimeError, "disk full"):
                    ingest_prepared(SimpleNamespace(processed_dir=root, embedding_batch_size=16), db, embedder)

        statuses = [call.args[1]["$set"]["status"] for call in db.ingestion_runs.update_one.call_args_list]
        self.assertEqual(statuses[-1], "partially_completed")


if __name__ == "__main__":
    unittest.main()
