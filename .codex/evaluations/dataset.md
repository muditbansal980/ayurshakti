# Bilingual retrieval evaluation dataset

Status: executed 2026-11-15 — 28 cases, 0 blocked. English and Hindi gold authored; runtime results in `retrieval-results.md`.

`data/evaluation-bilingual.json` records persisted parent IDs (the metric unit), child IDs, source document SHA-256, immutable generation, language, locator, relevance grade and an exact excerpt. `evaluation/bilingual.py` validates these against active MongoDB records before scoring. Originals and old evaluation remain unchanged.

Inventory at first authoring: seven prepared documents, 866 children, all English. At execution: eight documents (7 en, 1 hi — the OCR'd Hindi Designs Act, 2000), 652 parents, 935 children. Hindi-content success is now measured against real Devanagari parents, never inferred from Hindi queries over English sources.

Four English topics: Designs Act section 4; Trade Marks Act section 9; GI Act section 18; Biological Diversity Act section 6. Four query variants per topic cover English, Hindi, mixed language and Romanized Hindi. Six additional answerable cases test short, long, spelling, synonym, limited-context and specialist terminology. Two out-of-scope probes evaluate threshold abstention separately. The two blocked placeholders (`hi_hi_pending`, `en_hi_pending`) were replaced on 2026-11-15 by four cases grounded in the ingested Hindi Designs Act (sections 4 and 19). `hi_hi` and `en_hi` now have 2 scored cases each — evidence, but not enough to generalise.

All judgments are authored provisional positives and explicitly require human review. They are grounded in source text but are not an exhaustive relevance assessment or legal validation. Precision treats unjudged results as nonrelevant; with one judged parent, P@5 cannot exceed 0.2. Grades range 1–3; current direct-answer parents receive grade 3. Do not interpret this small set as general production quality.

Ranking evaluates top 10 parents with min_score=-1. Recall@5/@10, fixed-denominator Precision@5, MRR truncated at 10 and graded nDCG@5 are reported for each category. Duplicate parent hits count once. Missing categories have null metrics. Out-of-scope probes use the separate uncalibrated default 0.7 cosine threshold and never enter relevance averages.

Actual service timings separate embedding, search and total milliseconds. No warmup is performed: first-query lazy model load is included and must not be mistaken for steady-state query latency. No database writes occur in evaluation.

Run: `docker compose run --rm backend python -m ip_sakti.evaluation.bilingual`. The dataset file is mounted read-only into the backend container; without that mount the command fails with `FileNotFoundError`.

Checks run: `test_bilingual_evaluation.py` passes as part of the 49-test suite; `validate_dataset` accepted all 28 cases against the live corpus and rejected the earlier blocked entries (no gold IDs). Runtime results are recorded in `retrieval-results.md`.
