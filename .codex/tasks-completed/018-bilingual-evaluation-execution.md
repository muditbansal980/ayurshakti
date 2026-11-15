# 018 Bilingual evaluation built and executed

Request: measure English, Hindi, cross-lingual, mixed-language and transliteration
retrieval on the real corpus, with transliteration as its own category and no fabricated
gold IDs.

## Work done

1. Found `hi_hi` and `en_hi` blocked because the corpus held no Hindi content, although an
   official Hindi Designs Act scan existed in `data/raw/official/`.
2. OCR'd it locally (`tesseract eng+hin` in the backend image), prepared 48 parents /
   69 children, ingested 69 embedded chunks. OCR quality on sampled pages was clean
   Devanagari with intact section headings.
3. Replaced the two blocked placeholders with four grounded cases
   (`hi_hi_design_novelty`, `hi_hi_cancel`, `en_hi_cancel`, `en_hi_novelty`), taking
   parent/child/generation from MongoDB and using a literal slice of the stored parent
   text as `evidence_excerpt`. Result: 28 cases, 0 blocked.
4. Mounted the dataset into the backend container and executed the harness.

## Results (real run)

`data/reports/bilingual-evaluation.json`; tables in `evaluations/retrieval-results.md`.

| category | scored | R@5 | R@10 | MRR | nDCG@5 |
|---|---|---|---|---|---|
| en_en | 4 | 1.00 | 1.00 | 0.88 | 0.91 |
| hi_hi | 2 | 1.00 | 1.00 | 1.00 | 1.00 |
| hi_en | 4 | 0.50 | 0.50 | 0.38 | 0.41 |
| en_hi | 2 | 0.00 | 0.00 | 0.00 | 0.00 |
| mixed | 4 | 0.75 | 1.00 | 0.48 | 0.53 |
| transliteration | 4 | 0.00 | 0.00 | 0.00 | 0.00 |
| difficult | 6 | 0.67 | 0.83 | 0.69 | 0.67 |

No-answer abstention: 0/2 at threshold 0.7.

## Limitations

- Two Hindi cases per category, one Hindi document: evidence, not a general claim.
- `hi_en` design misses are correct answers in the *other* language version; the category
  measures language preference as much as retrieval.
- Labels remain provisional (`needs_review`); OCR not compared page-by-page.
- Precision@5 ≤ 0.20 by construction (one judged parent per case).
- Two `difficult` cases produced no hits and are excluded from that category mean
  (reported as `scored: 6` of 8).

Next: 019.
