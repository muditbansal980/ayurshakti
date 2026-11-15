"""E5 uses different prefixes for queries and corpus passages, in both languages."""

import math
from functools import cached_property
from pathlib import Path

MODEL = "intfloat/multilingual-e5-small"
REVISION = "614241f622f53c4eeff9890bdc4f31cfecc418b3"
DIMENSIONS = 384
MAX_TOKENS = 512
BATCH_SIZE = 16

PASSAGE_PREFIX = "passage: "
QUERY_PREFIX = "query: "


def validate_vector(vector: list[float], dimensions: int = DIMENSIONS) -> None:
    """Reject vectors MongoDB could store but never search meaningfully."""
    if not isinstance(vector, list) or not vector:
        raise ValueError("Embedding must be a non-empty list of floats.")
    if len(vector) != dimensions:
        raise ValueError(
            f"Embedding has {len(vector)} dimensions; the index expects {dimensions}."
        )
    for value in vector:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError("Embedding contains a non-finite value (NaN or infinity).")
    norm = math.sqrt(math.fsum(value * value for value in vector))
    if not math.isclose(norm, 1.0, rel_tol=1e-4, abs_tol=1e-4):
        raise ValueError("Embedding must be L2-normalized (unit norm).")


def validate_vectors(vectors: list[list[float]], dimensions: int = DIMENSIONS) -> None:
    if not vectors:
        raise ValueError("The embedder returned no vectors for a non-empty batch.")
    for vector in vectors:
        validate_vector(vector, dimensions)


def cache_path(model_cache_dir: Path, model: str = MODEL) -> Path:
    """Where Hugging Face keeps the downloaded snapshot for this model."""
    return Path(model_cache_dir) / "hub" / ("models--" + model.replace("/", "--"))


def model_is_cached(model_cache_dir: Path, model: str = MODEL) -> bool:
    """Check the pinned snapshot's weights and tokenizer, not arbitrary revisions.

    This is a file-presence check; an offline forward pass proves loadability.
    is_file also rejects broken Hugging Face cache symlinks.
    """
    snapshot = cache_path(model_cache_dir, model) / "snapshots" / REVISION
    required = ("config.json", "modules.json", "tokenizer_config.json", "tokenizer.json")
    weights = any((snapshot / name).is_file() and (snapshot / name).stat().st_size > 0
                  for name in ("model.safetensors", "pytorch_model.bin"))
    return weights and all((snapshot / name).is_file() and (snapshot / name).stat().st_size > 0
                           for name in required)


class LocalEmbedder:
    def __init__(self, device: str = "cpu", model: str = MODEL, revision: str = REVISION,
                 batch_size: int = BATCH_SIZE):
        if device != "cpu":
            raise ValueError("This deployment uses local CPU inference; device must be cpu.")
        if isinstance(batch_size, bool) or not isinstance(batch_size, int) or batch_size < 1:
            raise ValueError("Embedding batch size must be a positive integer.")
        if model != MODEL:
            raise ValueError(
                f"This corpus is pinned to {MODEL}. Changing the model requires an explicit "
                "re-embedding run; there is no silent fallback."
            )
        if revision != REVISION:
            raise ValueError(f"This corpus is pinned to revision {REVISION}.")
        self.device = device
        self.model_name = model
        self.revision = revision
        self.batch_size = batch_size

    @cached_property
    def tokenizer(self):
        from transformers import AutoTokenizer
        return AutoTokenizer.from_pretrained(self.model_name, revision=self.revision,
                                             use_fast=True, trust_remote_code=False)

    @cached_property
    def model(self):
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer(self.model_name, revision=self.revision,
                                    device=self.device, trust_remote_code=False)
        # sentence-transformers renamed this method; support both without warning.
        dimension = (model.get_embedding_dimension() if hasattr(model, "get_embedding_dimension")
                     else model.get_sentence_embedding_dimension())
        if dimension != DIMENSIONS:
            raise ValueError("Embedding dimension does not match the MongoDB index.")
        if model.max_seq_length != MAX_TOKENS:
            raise ValueError("Loaded model sequence limit does not match the 512-token contract.")
        # Older/offline loads may not report a commit hash; the pinned revision above
        # is then the source of truth. Never record an unverifiable value as the contract.
        loaded = getattr(getattr(model[0], "auto_model", None), "config", None)
        commit = getattr(loaded, "_commit_hash", None) if loaded is not None else None
        if commit and commit != self.revision:
            raise ValueError(
                f"Loaded weights are revision {commit}, but the corpus requires {self.revision}."
            )
        return model

    def count(self, text: str) -> int:
        return len(self.tokenizer.encode(text, add_special_tokens=True, truncation=False))

    def encode(self, texts: list[str], batch_size: int | None = None) -> list[list[float]]:
        if not isinstance(texts, list) or not texts or any(
                not isinstance(text, str) or not text.strip() for text in texts):
            raise ValueError("Embedding inputs must be a non-empty list of non-empty strings.")
        effective_batch_size = self.batch_size if batch_size is None else batch_size
        if isinstance(effective_batch_size, bool) or not isinstance(effective_batch_size, int) or effective_batch_size < 1:
            raise ValueError("Embedding batch size must be a positive integer.")
        if any(self.count(text) > MAX_TOKENS for text in texts):
            raise ValueError("Embedding input exceeds 512 tokens; refusing silent truncation.")
        vectors = self.model.encode(
            texts,
            batch_size=effective_batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
            convert_to_numpy=True,
        ).tolist()
        if len(vectors) != len(texts):
            raise ValueError("Embedding output count does not match the input count.")
        validate_vectors(vectors)
        return vectors

    def query(self, question: str) -> list[float]:
        if not isinstance(question, str) or not question.strip():
            raise ValueError("Question must not be empty.")
        return self.encode([QUERY_PREFIX + question.strip()])[0]
