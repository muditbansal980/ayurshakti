# 019 Independent review and final evidence

Request: review the retrieval implementation and the evaluation independently, fix what
is fixable, and leave honest evidence.

## Review output

- `reviews/retrieval-review.md` — 7 findings. The material ones: the 0.7 default filters
  nothing (correct top-1 0.830–0.914 vs wrong 0.802–0.891, measured); transliteration
  fails 4/4; English→Hindi fails 2/2; cold start dominates single CLI invocations.
- `reviews/bilingual-evaluation-review.md` — 6 findings, mainly about interpreting the
  metrics (P@5 ceiling, unjudged-as-wrong bias, tiny Hindi sample, OCR provenance, the
  6-of-8 `difficult` scoring).

## Fixes made during review

- Added the missing `data/evaluation-bilingual.json` mount; the documented evaluation
  command previously failed with `FileNotFoundError`.
- Replaced blocked evaluation cases with corpus-grounded ones after the Hindi ingest
  (the alternative — leaving them blocked — would have hidden the language gap).
- Rebuilt the stale backend image so runtime checks exercised the real code.

## Deliberately not "fixed"

- The 0.7 threshold was left in place and documented rather than retuned. Raising it
  would have silently dropped nothing useful (scores overlap) and any chosen cut would be
  arbitrary on 28 cases. Abstention needs a margin-based design, recorded as next work.
- Transliteration and English→Hindi failures were not patched with a trick: no query
  translation layer was added, because the task forbids inventing capability. They are
  reported.

## Checks actually run

Unit suite (49 tests), live API request, live CLI request, mongosh counts, full bilingual
evaluation, `sakti ingest` idempotency for the 7 pre-existing documents.

## Limitations

Nothing was committed to git; the working tree still holds all changes. Frontend
integration was out of scope and remains untouched.
