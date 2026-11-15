# Phase 4: bilingual evaluation
Status: corpus investigation pending.

Objective: reproducible graded corpus-grounded retrieval evaluation for English, Hindi, cross-lingual, mixed and transliterated queries, plus difficult/no-answer cases.
Dependencies: Phase 3 service contract; real source contents and stable parent/document/child IDs. Existing corpus appears English-only; verify rather than assume Hindi coverage.
Tasks: inspect language distribution; identify/collect official Hindi source if necessary with provenance; ground labels; implement Recall@5/@10, Precision@5, MRR and nDCG@5; run real retrieval with timings; diagnose failures; independent review.
Ownership: bilingual engineer owns data/evaluation-bilingual.json, evaluation/bilingual.py, evaluation tests and .codex/evaluations; lead owns any acquisition/ingestion changes and runtime integration; reviewer owns bilingual-evaluation-review.
Acceptance: each required category evaluated where real content exists, absent coverage explicitly blocked rather than fabricated; machine-readable IDs and grades; separately reported category metrics and latency; provisional author labels marked human-review-needed; reproducible execution.
Commands: backend/.venv/bin/python -m unittest discover -s backend/tests -v; evaluation module command agreed with engineer and recorded verbatim after execution.
Risks: source language/encoding, sparse gold labels, missing current laws, transliteration quality, evaluation labels are not legal validation.
Definition of done: real database evaluation executed, category results/failures saved, tests pass and independent review completed. Missing language corpus is not a passing scenario.
