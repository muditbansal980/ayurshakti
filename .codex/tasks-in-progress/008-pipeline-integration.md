# Complete pipeline validation

Status: in progress.

- ~~Install/start Docker Desktop and validate Compose, persistence and MongoDB search.~~
  Done 2026-11-15: all three images built, all containers healthy, backend
  `/health/ready` returns 200, collections auto-created, and a live vectorSearch
  index reached READY (see `tasks-completed/009-docker-build-and-startup.md`).
  Persistence across a restart is still unverified.
- Re-prepare the corpus after final section-parser corrections.
- Re-run Hindi/English diagnostics and record final counts and known misses.
- Ingest into MongoDB and test retrieval against real vector indexes.
- Process image-only PDFs with local OCR or document precise blockers.
- Finish official-source collection checks; the FSSAI URL returned 404.
- Update README and task records with observed outcomes.

Do not mark this task complete merely because the implementation files exist.
