# 015 Master audit with live evidence

Request: audit the existing implementation instead of trusting earlier records, then
report real counts and defects.

Scope: read the code, then verify every headline claim against the running stack.

## What was found

- Earlier records claimed 7 documents / 866 chunks. Those numbers were correct at the
  time but stale after this session's Hindi ingest; current verified numbers are
  8 documents / 652 parents / 935 children / 935 embedded.
- `reviews/previous-work-audit.md` (written in the prior session) lists the code-level
  defects that were already repaired: private hub API usage, missing chunk fields,
  `ReplaceOne` losing `created_at`, hardcoded batch size, placeholder `status` and
  `download-model`, index build misdetection, ignored `settings.embedding_model`.
- New code present but never executed: `storage/search.py`, `api/search.py`, rewritten
  `retrieval/search.py`, `evaluation/bilingual.py`, `data/evaluation-bilingual.json`.
  Its tests had never been run; the image was stale and lacked the new CLI flags.

## Checks actually run

- `docker compose run --rm … python -m unittest discover -s tests` → 49 tests, 48 pass,
  1 opt-in Mongo test skipped. With `RUN_MONGO_INTEGRATION=1`: 65 tests, all pass
  (live `$vectorSearch`).
- mongosh counts and language breakdown against `sakti_sahayak`.
- `sakti prepare --ocr --document-id …` failed first on the stale image
  (`unrecognized arguments`), proving the image/working-tree mismatch; rebuilt after.

## Changed files

None for the audit itself. Evidence recorded in `reviews/retrieval-review.md` and
`evaluations/retrieval-results.md`.

## Limitations

The previous session's claim that 29 tests passed could not be reproduced (it was true
then; the suite has since grown). No frontend state was audited.

Next: 016.
