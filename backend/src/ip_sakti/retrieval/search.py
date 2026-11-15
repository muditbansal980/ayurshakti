"""Whole-query local E5 retrieval with cosine scores and distinct parent context."""

import math
import time
import warnings

from ip_sakti.embeddings.local import DIMENSIONS, MAX_TOKENS, MODEL, QUERY_PREFIX, REVISION, validate_vector
from ip_sakti.storage.search import RetrievalIntegrityError, SearchRepository

SUPPORTED_FILTERS = {"jurisdiction", "document_id", "kind", "language"}


def fuse_rankings(rankings: list[list[dict]], limit: int) -> list[dict]:
    """Legacy RRF utility; semantic retrieval deliberately does not use RRF scores."""
    scores, records = {}, {}
    for ranking in rankings:
        for rank, record in enumerate(ranking, 1):
            key = record["_id"]
            records[key] = record
            scores[key] = scores.get(key, 0) + 1 / (60 + rank)
    return [{**records[key], "retrieval_score": score}
            for key, score in sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:limit]]


def mongo_cosine_score(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
        raise RetrievalIntegrityError("Malformed MongoDB vector similarity score.")
    return 2 * value - 1


def validate_request(query, top_k, min_score, filters, include_unverified):
    if not isinstance(query, str) or not query.strip():
        raise ValueError("Provide a nonempty question.")
    if len(query) > 20000:
        raise ValueError("Question is too long; maximum 20000 characters and 512 model tokens.")
    if isinstance(top_k, bool) or not isinstance(top_k, int) or not 1 <= top_k <= 20:
        raise ValueError("top-k must be an integer between 1 and 20.")
    if isinstance(min_score, bool) or not isinstance(min_score, (int, float)) or not math.isfinite(min_score) or not -1 <= min_score <= 1:
        raise ValueError("Minimum cosine score must be a finite number between -1 and 1.")
    if not isinstance(include_unverified, bool):
        raise ValueError("include_unverified must be boolean.")
    if filters is None:
        filters = {}
    if not isinstance(filters, dict) or any(key not in SUPPORTED_FILTERS for key in filters):
        raise ValueError("Supported filters: document_id, kind, language, jurisdiction.")
    if any(not isinstance(value, str) or not value.strip() for value in filters.values()):
        raise ValueError("Filter values must be nonempty strings.")
    if "jurisdiction" in filters and filters["jurisdiction"] not in ("india", "international"):
        raise ValueError("Choose one jurisdiction: india or international.")
    if "language" in filters and filters["language"] not in ("hi", "en"):
        raise ValueError("Choose one content language: hi or en.")
    return query.strip(), dict(filters)


class RetrievalService:
    def __init__(self, db, embedder):
        self.repository = SearchRepository(db)
        self.embedder = embedder

    def retrieve(self, query, *, top_k=5, min_score=0.7, filters=None, include_unverified=False):
        started = time.perf_counter()
        query, filters = validate_request(query, top_k, min_score, filters, include_unverified)
        tokenization_started = time.perf_counter()
        try:
            token_count = self.embedder.count(QUERY_PREFIX + query)
        except Exception as error:
            raise RuntimeError("Local query tokenizer is unavailable.") from error
        if token_count > MAX_TOKENS:
            raise ValueError("Embedding input exceeds 512 tokens; refusing silent truncation.")
        validation_ms = (time.perf_counter() - tokenization_started) * 1000
        embedding_ms = 0.0
        # Bounded ANN oversampling reduces duplicate-parent loss, but cannot promise
        # globally exact ranking or top_k distinct parents. Never silently scan/fallback.
        limit = max(100, top_k * 20)
        response = {"question": query, "jurisdiction": filters.get("jurisdiction"), "filters": filters,
                    "min_score": min_score, "results": [], "candidate_limit": limit,
                    "candidate_limit_reached": False, "search_strategy": "mongodb_vector_ann",
                    "note": "Scores are cosine similarity, not confidence. The default 0.7 threshold is an uncalibrated heuristic. ANN candidates are bounded; fewer than top-k distinct parents may be returned."}
        search_started = time.perf_counter()
        documents = self.repository.eligible_documents(filters, include_unverified)
        if not documents:
            response["reason"] = "No eligible sources. Review corpus metadata, or use --include-unverified for development inspection."
        else:
            self.repository.check_contract_and_index()
            embedding_started = time.perf_counter()
            try:
                vector = self.embedder.query(query)  # One complete query; no chunking.
            except Exception as error:
                raise RuntimeError("Local query embedding failed; check model files and configuration.") from error
            try:
                validate_vector(vector)
            except ValueError as error:
                raise RetrievalIntegrityError("Query embedder returned an invalid vector.") from error
            embedding_ms += (time.perf_counter() - embedding_started) * 1000
            candidates = self.repository.candidates(vector, documents, filters, limit)
            response["candidate_limit_reached"] = len(candidates) >= limit
            hits = []
            for child in candidates:
                if not isinstance(child.get("document_id"), str):
                    raise RetrievalIntegrityError("Malformed passage document ID; corpus needs repair.")
                document = documents.get(child.get("document_id"))
                # Defend against malformed/foreign records sharing a generation.
                if not document or child.get("generation") != document["active_generation"]:
                    continue
                if child.get("jurisdiction") != document.get("jurisdiction"):
                    continue
                if any(not isinstance(child.get(key), str) or not child[key] for key in ("_id", "parent_id", "text")):
                    raise RetrievalIntegrityError("Malformed retrieved passage; corpus needs repair.")
                if any(child.get(key) != value for key, value in {
                    "embedding_model": MODEL, "embedding_revision": REVISION,
                    "embedding_dimensions": DIMENSIONS,
                }.items()):
                    raise RetrievalIntegrityError("Stored passage embedding contract is incompatible; corpus needs repair.")
                if "section_id" in child and child["section_id"] != child["parent_id"]:
                    raise RetrievalIntegrityError("Stored passage has conflicting parent relationships; corpus needs repair.")
                try:
                    validate_vector(child.get("embedding"))
                except ValueError as error:
                    raise RetrievalIntegrityError("Malformed stored embedding; corpus needs repair.") from error
                score = mongo_cosine_score(child.get("vector_score"))
                if score >= min_score:
                    hits.append({**child, "score": score})
            hits.sort(key=lambda child: (-child["score"], child["_id"]))
            selected, seen = [], set()
            for child in hits:
                if child["parent_id"] not in seen:
                    selected.append(child)
                    seen.add(child["parent_id"])
                if len(selected) >= top_k:
                    break
            parents = self.repository.parents(selected)
            for child in selected:
                parent = parents.get(child["parent_id"])
                if not parent or parent.get("generation") != child["generation"] or parent.get("document_id") != child["document_id"] or not isinstance(parent.get("text"), str) or not parent["text"]:
                    raise RetrievalIntegrityError("Missing or incompatible parent for a retrieved passage; corpus needs repair.")
                document = documents[child["document_id"]]
                citation = {key: document[key] for key in ("title", "source_url", "local_file", "sha256", "jurisdiction", "version_label", "review_status") if key in document}
                citation.update({key: value for key, value in {
                    "provision": parent.get("locator"), "pdf_pages": child.get("pages"),
                    "parent_pdf_pages": parent.get("pages")}.items() if value is not None})
                response["results"].append({
                    "chunk_id": child["_id"], "document_id": child["document_id"], "parent_id": child["parent_id"],
                    "score": child["score"], "retrieval_score": child["score"],
                    "text": child["text"], "matched_passage": child["text"], "parent_text": parent["text"],
                    "metadata": {key: document[key] for key in ("kind", "language", "jurisdiction", "review_status") if key in document},
                    "citation": citation,
                })
        total_ms = (time.perf_counter() - started) * 1000
        response["timings"] = {"embedding_ms": embedding_ms, "validation_ms": validation_ms, "search_ms": (time.perf_counter() - search_started) * 1000 - embedding_ms, "total_ms": total_ms}
        return response


def search(db, embedder, question, *, jurisdiction=None, top_k=5, include_unverified=False,
           hybrid=False, min_score=0.7, filters=None):
    """Compatibility entry point; all returned scores now have cosine semantics."""
    if hybrid:
        warnings.warn("hybrid=True is deprecated; semantic cosine retrieval is used.", DeprecationWarning, stacklevel=2)
    if filters is not None and not isinstance(filters, dict):
        raise ValueError("Filters must be a mapping.")
    selected = dict(filters or {})
    if jurisdiction is not None:
        if "jurisdiction" in selected and selected["jurisdiction"] != jurisdiction:
            raise ValueError("Conflicting jurisdiction filters.")
        selected["jurisdiction"] = jurisdiction
    return RetrievalService(db, embedder).retrieve(question, top_k=top_k, min_score=min_score,
                                                 filters=selected, include_unverified=include_unverified)
