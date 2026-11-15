from ip_sakti.embeddings.local import MODEL
from ip_sakti.storage.indexes import VECTOR_INDEX


def fuse_rankings(rankings: list[list[dict]], limit: int) -> list[dict]:
    scores, records = {}, {}
    for ranking in rankings:
        for rank, record in enumerate(ranking, 1):
            key = record["_id"]
            records[key] = record
            scores[key] = scores.get(key, 0) + 1 / (60 + rank)
    return [{**records[key], "retrieval_score": score}
            for key, score in sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:limit]]


def search(db, embedder, question: str, *, jurisdiction: str, top_k: int = 5,
           include_unverified: bool = False, hybrid: bool = True) -> dict:
    if not question.strip() or not 1 <= top_k <= 20:
        raise ValueError("Provide a nonempty question and top-k between 1 and 20.")
    if jurisdiction not in ("india", "international"):
        raise ValueError("Choose one jurisdiction: india or international.")
    selection = {"jurisdiction": jurisdiction, "active_generation": {"$exists": True}}
    if not include_unverified:
        selection["review_status"] = "verified"
    documents = {d["_id"]: d for d in db.documents.find(selection)}
    if not documents:
        return {"results": [], "reason": "No eligible sources. Review corpus metadata, or use --include-unverified for development inspection."}
    contract = db.pipeline_metadata.find_one({"_id": "embedding_contract"})
    revision = embedder.model[0].auto_model.config._commit_hash
    if not contract or contract.get("model") != MODEL or contract.get("revision") != revision:
        raise ValueError("Query model does not match the stored embedding contract.")
    vector = embedder.query(question)  # Exactly one embedding; never query chunking.
    filters = {"generation": {"$in": [d["active_generation"] for d in documents.values()]},
               "jurisdiction": jurisdiction}
    limit = min(top_k * 8, 160)
    dense = list(db.chunks.aggregate([
        {"$vectorSearch": {"index": VECTOR_INDEX, "path": "embedding", "queryVector": vector,
                           "filter": filters, "numCandidates": limit * 20, "limit": limit}},
        {"$project": {"embedding": 0, "embedding_text": 0}},
    ]))
    rankings = [dense]
    if hybrid:
        lexical = list(db.chunks.find({**filters, "$text": {"$search": question, "$language": "none"}},
                                      {"embedding": 0, "embedding_text": 0, "keyword_score": {"$meta": "textScore"}})
                       .sort([("keyword_score", {"$meta": "textScore"})]).limit(limit))
        rankings.append(lexical)
    hits = fuse_rankings(rankings, limit * 2)
    results, seen = [], set()
    for child in hits:
        if child["parent_id"] in seen:
            continue
        parent = db.sections.find_one({"_id": child["parent_id"], "generation": child["generation"]})
        if not parent:
            raise ValueError("Missing parent for a retrieved passage; corpus needs repair.")
        seen.add(child["parent_id"])
        document = documents[child["document_id"]]
        results.append({
            "retrieval_score": child["retrieval_score"],
            "matched_passage": child["text"], "parent_text": parent["text"],
            "citation": {"title": document["title"], "provision": parent["locator"],
                         "pdf_pages": child["pages"], "parent_pdf_pages": parent["pages"],
                         "source_url": document.get("source_url"), "local_file": document["local_file"],
                         "sha256": document["sha256"], "jurisdiction": jurisdiction,
                         "version_label": document.get("version_label"),
                         "review_status": document["review_status"]},
        })
        if len(results) == top_k:
            break
    return {"question": question, "jurisdiction": jurisdiction, "results": results,
            "note": "Ranking scores are not legal confidence. Results are evidence candidates, not generated advice; review source currency and relevance."}
