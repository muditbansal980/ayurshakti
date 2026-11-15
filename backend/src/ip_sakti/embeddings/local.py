"""E5 uses different prefixes for queries and corpus passages, in both languages."""

from functools import cached_property

MODEL = "intfloat/multilingual-e5-small"
REVISION = "614241f622f53c4eeff9890bdc4f31cfecc418b3"
DIMENSIONS = 384
MAX_TOKENS = 512


class LocalEmbedder:
    def __init__(self, device: str = "cpu"):
        self.device = device

    @cached_property
    def tokenizer(self):
        from transformers import AutoTokenizer
        return AutoTokenizer.from_pretrained(MODEL, revision=REVISION, use_fast=True, trust_remote_code=False)

    @cached_property
    def model(self):
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer(MODEL, revision=REVISION, device=self.device, trust_remote_code=False)
        if model.get_sentence_embedding_dimension() != DIMENSIONS:
            raise ValueError("Embedding dimension does not match the MongoDB index.")
        return model

    def count(self, text: str) -> int:
        return len(self.tokenizer.encode(text, add_special_tokens=True, truncation=False))

    def encode(self, texts: list[str]) -> list[list[float]]:
        if any(self.count(text) > MAX_TOKENS for text in texts):
            raise ValueError("Embedding input exceeds 512 tokens; refusing silent truncation.")
        return self.model.encode(texts, batch_size=16, normalize_embeddings=True,
                                 show_progress_bar=False, convert_to_numpy=True).tolist()

    def query(self, question: str) -> list[float]:
        if not question.strip():
            raise ValueError("Question must not be empty.")
        return self.encode(["query: " + question.strip()])[0]

