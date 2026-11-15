# Agent assignments
User requested GPT-6 Astra, medium reasoning. Agents not yet spawned.

- Auditor: read-only baseline audit, previous-work-audit report, no source changes.
- Retrieval engineer: retrieval modules, storage/search.py, storage/indexes.py, retrieval-specific tests; implementation waits for critical audit findings.
- Bilingual evaluation engineer: dataset, evaluation module/tests, evaluation records; no core retrieval edits.
- Independent reviewer: review reports only after integration.
- Lead: integration, embedding repairs, CLI/API, runtime tests, source collection, project/task records.
At most three specialist agents run concurrently. Shared-file edits require coordination.
