# Project state

2026-11-15 — semantic retrieval and bilingual evaluation are implemented and verified
against the live stack. Counts below are runtime-verified, not copied from earlier records.

## Corpus (MongoDB `sakti_sahayak`)

- 8 documents: 7 English, 1 Hindi (OCR'd Designs Act, 2000, 48 parents / 69 children).
- 652 parent sections, 935 child chunks, 935/935 with 384-dim `multilingual-e5-small`
  embeddings at the pinned revision.
- `corpus_vector_v1` reaches `queryable`; retrieval uses real `$vectorSearch`.
- All 8 documents are still `review_status: needs_review`, so default queries return
  nothing unless `include_unverified` is passed.

## Retrieval

- `RetrievalService.retrieve` → `SearchRepository` (eligible documents → ANN → parent
  batch fetch). Cosine scores are recovered from `vectorSearchScore` via `2v-1`.
- Contract checks (model, revision, dimensions, generation, jurisdiction, parent
  linkage, vector validity) raise `RetrievalIntegrityError`; no application-side scan
  fallback exists.
- CLI `sakti query` and `POST /api/v1/search` share the service. API uses a
  non-blocking retrieval lock.

## Evaluation

- 28 cases, 0 blocked: en_en 4, hi_hi 2, hi_en 4, en_hi 2, mixed 4, transliteration 4,
  difficult 8, no-answer 2.
- Executed run: `data/reports/bilingual-evaluation.json`.
- Headline: en_en R@10 1.00 / MRR 0.88; hi_hi 1.00 / 1.00 (2 cases); mixed R@10 1.00 /
  MRR 0.48; hi_en 0.50; en_hi 0.00; transliteration 0.00; difficult R@10 0.83.
- No-answer abstention at 0.7 failed (0/2); score ranges for correct and wrong matches
  overlap (0.830–0.914 vs 0.802–0.891).

## Known limitations

- Transliteration (Latin→Devanagari) retrieval does not work with this model.
- English→Hindi cross-lingual retrieval misses on this lopsided corpus.
- Absolute cosine threshold cannot separate answerable from unanswerable.
- Qrels are provisional, one judged parent per case; unjudged parents count as wrong.
- OCR of the Hindi scan has not been compared page-by-page against images.
- Old-generation children are not cleaned up after re-ingest.
- Two PDFs still need OCR (Patents Rules 2003, Copyright Rules 2013).
- No frontend integration; that remains out of scope per project rules.

## Records

Plans: `plans/03-semantic-retrieval.md`, `plans/04-bilingual-retrieval-evaluation.md`.
Results: `evaluations/retrieval-results.md`, `evaluations/failure-analysis.md`,
`evaluations/dataset.md`. Reviews: `reviews/retrieval-review.md`,
`reviews/bilingual-evaluation-review.md`, `reviews/previous-work-audit.md`.
Final report: `reports/final-report.md`.
