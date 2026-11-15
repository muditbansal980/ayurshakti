# 017 CLI/API integration and runtime verification

Request: make the retrieval service reachable from the CLI and HTTP API and prove it in
Docker.

## What changed

- `compose.yaml` gained a read-only mount for `data/evaluation-bilingual.json`; without it
  the evaluation command fails inside the container.
- Backend image rebuilt so the container runs the working-tree code (the old image lacked
  the new CLI flags and the search router).

## Checks actually run

1. `docker compose build backend` → built.
2. `docker compose up -d backend`; `curl /health/ready` →
   `{"status":"ready","database":"sakti_sahayak"}`.
3. `POST /api/v1/search` with `include_unverified: true` →
   `mongodb_vector_ann`, top hit Trade Marks Act s.9 at 0.872 (second hit was a wrong
   statute at 0.869, consistent with the score-compression finding).
4. `sakti query "…"` in Hindi with `--include-unverified --json` → same response shape,
   `candidate_limit: 100`, `search_strategy: mongodb_vector_ann`.
5. `sakti ingest` after OCR → existing 7 documents reported `unchanged`, Hindi document
   `ingested` with 69 chunks; index `queryable`.

## Limitations

- No filtered (`--language` / `--kind`) request was run end to end.
- Concurrent-request 503 behaviour untested.
- Cold start: a single CLI query costs 8–11 s (tokenizer + model load). The API pays it
  once; steady-state retrieval is 21–35 ms.

Next: 018.
