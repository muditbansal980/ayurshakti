# Independent review: bilingual evaluation

Date: 2026-11-15. Scope: `data/evaluation-bilingual.json`, `evaluation/bilingual.py`,
`data/reports/bilingual-evaluation.json`.

## Verdict

The harness is trustworthy for what it measures. It validates every gold ID against the
live database (document, parent, child, generation, language, and an exact excerpt
substring) and refuses stale labels, so the 28-case run cannot silently drift from the
corpus. What it measures is narrow: one judged parent per case, provisional labels, and
a metric set that penalises unjudged relevant parents.

## Dataset composition after this session

| category | cases | notes |
|---|---|---|
| en_en | 4 | English query, English source |
| hi_hi | 2 | Hindi query, Hindi source (new, was blocked) |
| hi_en | 4 | Hindi query, English source |
| en_hi | 2 | English query, Hindi source (new, was blocked) |
| mixed | 4 | mixed-language query |
| transliteration | 4 | Romanized Hindi queries |
| difficult | 8 | short/long/spelling/synonym/specialist/limited-context; 2 had no gold text at run time |
| no-answer | 2 | scored separately, never averaged in |

The two previous `*_pending` blocked cases were replaced by four grounded cases from the
OCR'd Hindi Designs Act: sections 4 (prohibition of registration) and 19 (cancellation).
`evidence_excerpt` values are literal slices of the stored parent text.

## Findings

### E1 — Precision@5 is near its ceiling by construction (interpretation risk)

With one judged parent per case, P@5 cannot exceed 0.20. The reported 0.10–0.20 values
say nothing about precision; they only reflect the judgement sparsity. Do not quote
them as quality. Recall@5/@10, MRR and nDCG@5 are the meaningful numbers here.

### E2 — Unjudged parents count as non-relevant (conservative bias)

`parent_metrics` treats anything not in `qrels` as wrong. Several misses seen in the run
(for example a Trade Marks section adjacent to the judged one, and GI Rules Rule 74)
are plausible partial answers. Real recall is therefore a lower bound.

### E3 — `hi_hi` and `en_hi` currently rest on 2 cases each, one document

Both Hindi categories are powered by a single OCR'd statute, and only two sections of it
are judged. 100% recall on `hi_hi` means "two queries found two sections", not "Hindi
retrieval works". `en_hi` at 0/2 has the same sample-size caveat in the opposite
direction. Both are still far better evidence than the earlier blocked placeholders.

### E4 — OCR provenance is unresolved for the Hindi source

The Hindi PDF is reported as a gazette scan whose text comes from `tesseract eng+hin`.
Extraction quality on the sampled pages was clean, but no page-by-page comparison
against the images was done. If OCR mangled a section heading, a judged parent could be
subtly wrong. `review_status` remains `needs_review`.

### E5 — `difficult` category has 8 cases but only 6 scored

Two cases had no retrieved candidate at or above the ranking floor used for scoring
(`min_score=-1.0`), i.e. they produced no hits at all, and are excluded from the
category mean rather than counted as zeros. The report exposes `scored` vs `cases`, but
a reader skimming metrics would overstate coverage. Fix belongs in reporting clarity,
not scoring.

### E6 — No warmup; first-query load included (documented)

`en_en` mean total latency is 1.97 s because the first query loads the model. All other
categories are 21–33 ms. The report's `limitations` field states this; keep it when
quoting numbers.

## Checks run

- Unit suite: 49 tests, 48 pass, 1 skip (includes `test_bilingual_evaluation.py`).
- `validate_dataset` accepted all 28 cases against live Mongo; it raised correctly on
  the previous blocked entries (no gold) before they were replaced.
- Full run: `python -m ip_sakti.evaluation.bilingual` in the backend container, output
  `data/reports/bilingual-evaluation.json`.
