"""Exact local vector baseline to test model/chunks independently of MongoDB."""

import json

from ip_sakti.embeddings.local import REVISION
from ip_sakti.ingestion.prepare import write_json


def evaluate_local(settings, embedder, cases_path) -> dict:
    import numpy as np

    manifest = json.loads((settings.processed_dir / "manifest.json").read_text())
    children = []
    for entry in manifest["prepared"]:
        bundle = json.loads((settings.processed_dir / entry["bundle"]).read_text())
        cache = settings.processed_dir / (entry["generation"] + ".npy")
        if cache.exists():
            vectors = np.load(cache, allow_pickle=False)
        else:
            vectors = np.asarray(embedder.encode([c["embedding_text"] for c in bundle["children"]]), dtype=np.float32)
            np.save(cache, vectors)
        if vectors.shape != (len(bundle["children"]), 384):
            raise ValueError("Invalid evaluation cache shape; remove the affected .npy file and rerun.")
        children.extend((c, bundle["document"], vector) for c, vector in zip(bundle["children"], vectors, strict=True))
    if not children:
        raise ValueError("Prepare corpus before running evaluation.")
    matrix = np.stack([row[2] for row in children])
    cases = json.loads(cases_path.read_text())["cases"]
    if not cases:
        raise ValueError("Evaluation case list must not be empty.")
    results = []
    for case in cases:
        scores = matrix @ np.asarray(embedder.query(case["question"]))
        seen, top = set(), []
        for i in np.argsort(-scores):
            child, document, _ = children[int(i)]
            key = (document["sha256"], child["parent_id"])
            if key in seen or document["jurisdiction"] != case["jurisdiction"]:
                continue
            seen.add(key)
            top.append({"title": document["title"], "locator": child["locator"], "score": float(scores[i])})
            if len(top) == 5:
                break
        rank = next((i for i, hit in enumerate(top, 1) if case["expected_title"] == hit["title"] and case["expected_locator"] == hit["locator"]), None)
        results.append({**case, "rank": rank, "top_5": top})
    report = {"mode": "local_exact_vectors_not_mongodb", "model_revision": REVISION,
              "cases": len(results), "hit_rate_at_5": sum(r["rank"] is not None for r in results) / len(results),
              "mrr_at_5": sum(1 / r["rank"] if r["rank"] else 0 for r in results) / len(results),
              "results": results, "limitation": "Small authored smoke set; does not establish legal answer accuracy, abstention quality, or MongoDB ANN recall."}
    write_json(settings.reports_dir / "retrieval-evaluation.json", report)
    return report
