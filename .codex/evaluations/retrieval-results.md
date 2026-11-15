# Retrieval evaluation results (runtime, 2026-11-15)

All numbers below come from one executed run against the live MongoDB corpus. Nothing
here is estimated.

- Model: `intfloat/multilingual-e5-small`, revision `614241f622f5…` (full revision in
  `embeddings/local.py`), 384 dimensions, CPU, `passage:`/`query:` prefixes.
- Corpus: 8 documents (7 English, 1 Hindi), 652 parents, 935 children, 935 with
  embeddings; `corpus_vector_v1` queryable.
- Ranking: MongoDB `$vectorSearch`, cosine (`2v-1`), top 10 parents after parent dedupe,
  `min_score=-1.0` so no candidate is dropped before scoring.
- Dataset: 28 cases, 0 blocked (`data/evaluation-bilingual.json`).
- Output: `data/reports/bilingual-evaluation.json`.

## Metrics by category

| category | scored | R@5 | R@10 | P@5 | MRR@10 | nDCG@5 | mean total ms |
|---|---|---|---|---|---|---|---|
| en_en | 4 | 1.00 | 1.00 | 0.20 | 0.88 | 0.91 | 1968.9 |
| hi_hi | 2 | 1.00 | 1.00 | 0.20 | 1.00 | 1.00 | 21.6 |
| hi_en | 4 | 0.50 | 0.50 | 0.10 | 0.38 | 0.41 | 33.4 |
| en_hi | 2 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 25.4 |
| mixed | 4 | 0.75 | 1.00 | 0.15 | 0.48 | 0.53 | 26.5 |
| transliteration | 4 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 28.8 |
| difficult | 6 | 0.67 | 0.83 | 0.13 | 0.69 | 0.67 | 29.8 |

Read P@5 only as an artefact of one judged parent per case (ceiling 0.20).

## Abstention probe

| cases | abstained | threshold |
|---|---|---|
| 2 | 0 | 0.7 |

Observed top-1 scores: 0.772 and 0.785 for the two out-of-scope questions. Both were
answered because 0.7 is below every score the model produces on this corpus
(range of wrong-match top-1: 0.802–0.891). The threshold is not a usable confidence
gate; see `reviews/retrieval-review.md` F1.

## Test evidence for the same code

Default suite: 49 tests, 48 pass, 1 opt-in Mongo skip. With
`RUN_MONGO_INTEGRATION=1`: 65 tests, all pass against the live database.

## How to reproduce

```bash
docker compose build backend
docker compose run --rm backend python -m ip_sakti.evaluation.bilingual
```

The dataset is mounted read-only at `/app/data/evaluation-bilingual.json` (added to
`compose.yaml` this session; without it the command fails with `FileNotFoundError`).

## Runtime contract check (same session)

```bash
curl -s localhost:8000/health/ready
# {"status":"ready","database":"sakti_sahayak"}

curl -s -X POST localhost:8000/api/v1/search -H 'content-type: application/json' \
  -d '{"query":"What are the absolute grounds for refusal of a trade mark?","top_k":2,"include_unverified":true,"min_score":-1}'
# search_strategy mongodb_vector_ann; 0.872 The Trade Marks Act, 1999 Section 9
# second result: 0.869 GI Rules 2002 Rule 74 (wrong statute, plausible score)
```

`sakti query … --include-unverified --json` returned the same response shape; per
invocation cost was 8–11 s, dominated by tokenizer + model cold load, not retrieval
(21–35 ms search).
