# Phase 3: semantic retrieval
Status: audit in progress, implementation gated on critical audit findings.

Objective: reusable local E5 semantic retrieval through MongoDB Vector Search, CLI and existing FastAPI app. No frontend wiring or answer generation.
Dependencies: existing pinned multilingual E5 embeddings, section-aware parent/child bundles, Atlas Local, persistent model cache.
Tasks: independent baseline audit; repair critical defects; repository/service with cosine scores, thresholds, filters and batched parents; CLI/API integration; actual Mongo tests; independent review.
Ownership: auditor owns previous-work-audit; retrieval engineer owns retrieval/*, storage/search.py, storage/indexes.py and retrieval-specific tests; lead owns embeddings fixes, CLI, API, Docker and integration; reviewer owns review reports.
Acceptance: exact model contract, validated whole query, finite normalized vectors, actual ready vector index, active generation filters, deterministic parent deduplication, source IDs/citations, meaningful threshold, no N+1; JSON/human CLI and POST /api/v1/search verified.
Commands: backend/.venv/bin/python -m unittest discover -s backend/tests -v; RUN_MONGO_INTEGRATION=1 backend/.venv/bin/python -m unittest discover -s backend/tests -p test_mongo_integration.py -v; docker compose config --quiet; docker compose ps; CLI/API smoke commands recorded when executed.
Risks: old uncommitted work must be preserved; async vector indexing; all existing sources need currency review; memory on 16 GB host; malformed legacy records.
Definition of done: audited and repaired, real integration and regression checks pass, independent review findings resolved, evidence and remaining limitations recorded.
