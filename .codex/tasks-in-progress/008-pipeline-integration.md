# Complete pipeline validation

Status: in progress.

- ~~Install/start Docker Desktop and validate Compose, persistence and MongoDB search.~~
  Done 2026-11-15: all three images built, all containers healthy, backend
  `/health/ready` returns 200, collections auto-created, and a live vectorSearch
  index reached READY (see `tasks-completed/009-docker-build-and-startup.md`).
  The stack was restarted and the database reconnected on 2026-11-15 (see
  `tasks-completed/011-restart-stack-and-connect-db.md`); collections survived
  the restart. Corpus-row persistence is now proven: 7 documents, 604 sections
  and 866 embedded chunks survived the ingest and a second idempotent run
  (`tasks-completed/013-verify-embeddings-in-mongodb.md`).
- Re-prepare the corpus after final section-parser corrections.
- ~~Re-run Hindi/English diagnostics and record final counts and known misses.~~
  Done 2026-11-15: hit@5 0.833, MRR@5 0.75 over 6 cases; one Hindi miss where
  the right statute ranked 1-4 but the wrong sections did
  (`tasks-completed/014-retrieval-evaluation-baseline.md`).
- ~~Ingest into MongoDB and test retrieval against real vector indexes.~~
  Done 2026-11-15: 866/866 chunks embedded at 384 dimensions, `corpus_vector_v1`
  READY, English and Hindi queries returned parent sections with citations.
  Remaining gap: all sources are still `review_status: needs_review`, so default
  queries return nothing until sources are reviewed and marked verified.
- Process image-only PDFs with local OCR or document precise blockers.
  Partly done 2026-11-15: the Hindi Designs Act, 2000 scan was OCR'd with local
  `tesseract eng+hin`, prepared (48 parents / 69 children) and ingested as the first
  Hindi document. Still blocked: The Patents Rules, 2003 and Copyright Rules 1, 2013
  (both reported "page 1 needs OCR review").
- Finish official-source collection checks; the FSSAI URL returned 404.
- Update README and task records with observed outcomes.

Do not mark this task complete merely because the implementation files exist.
