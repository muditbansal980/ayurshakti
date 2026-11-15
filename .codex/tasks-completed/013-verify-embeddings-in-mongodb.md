# Ingest the corpus and verify embeddings in MongoDB

Status: completed within the scope below.
Recorded: 2026-11-15 (Asia/Kolkata).

## Request

Run the full pipeline end to end and prove, with MongoDB queries, that every
expected chunk has a persisted 384-dimensional embedding and that a rerun does
not duplicate anything.

## What was run (in order)

1. `docker compose build backend` (new cache-friendly Dockerfile).
2. `docker compose up -d backend`.
3. `docker compose run --rm backend sakti download-model`.
4. `docker compose run --rm backend sakti ingest`.
5. Verification `mongosh` queries.
6. `sakti query` (one English, one Hindi question).
7. `sakti ingest` again, to test idempotency.
8. `sakti status`.
9. `RUN_MONGO_INTEGRATION=1` integration test.

## Observed results

Ingestion run 1 (`status: completed`, `vector_index: queryable`):

| document | sections | chunks |
|---|---|---|
| Biological Diversity Act, 2002 (and 6 more documents) | 604 total | 866 total |

MongoDB verification:

```
total chunks         : 866
with embeddings      : 866
without embeddings   : 0
documents            : 7
sections             : 604
expected children sum: 866      (sum of active documents' child_count)
min/max dims         : 384 / 384
max |norm-1|         : 1.16e-7
models               : ["intfloat/multilingual-e5-small"]
revisions            : ["614241f622f53c4eeff9890bdc4f31cfecc418b3"]
declared dims        : [384]
null/empty embeddings: 0
index                : corpus_vector_v1, status READY, queryable true
contract             : model + revision + 384 + l2 + e5-query-passage
```

Identity checks: `distinct("_id").length === 866`, all 866 chunks carry
`section_id`, and 0 chunks are missing `created_at`/`updated_at`.

Retrieval (unreviewed sources included, because all documents are still
`needs_review`):

- EN "grounds for refusal of registration of a trade mark?" → Trade Marks Act,
  **Section 11** (relative grounds) then **Section 9** (absolute grounds), with
  PDF pages 13–15 attached as citations.
- HI "डिज़ाइन पंजीकरण के लिए क्या शर्तें हैं?" → Designs Act 2000, **Section 19**.
  A Hindi question matching English statute text confirms the multilingual model
  is working, not just keyword overlap.

Idempotency: the second `sakti ingest` reported `"status": "unchanged"` for all
7 documents; `chunks` stayed at 866, `sections` at 604, `documents` at 7, with a
second `ingestion_runs` record. No duplicates, no re-embedding.

## Why it matters (learning note)

`sakti status` distinguishes "chunks exist" from "chunks have embeddings", which
is the exact failure this task was about. The `chunks_without_embeddings: 0`
line is the acceptance criterion; before the run it was 0-of-0, after it is
866-of-866.

## Limitations

- Cell values in the table above come from the actual tree output; the per-document
  breakdown was printed by `sakti ingest` and is summarised here (7 documents,
  including a 4-chunk WIPO GRATK Final Act and the 229-chunk Trade Marks Act).
- `max |norm-1| = 1.16e-7` is float32 storage rounding, not a normalization bug.
- The search index is asynchronous; `index-status` reports readiness, and
  newly written passages may take a moment to become searchable.
- No answer generation or frontend wiring is included.

## Next step

Mark sources as verified after review, then rerun `sakti evaluate-local` and
`sakti query` without `--include-unverified` (tracked in
`tasks-in-progress/008-pipeline-integration.md`).
