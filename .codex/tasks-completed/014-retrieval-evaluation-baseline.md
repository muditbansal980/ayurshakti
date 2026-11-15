# Baseline retrieval evaluation (local exact vectors)

Status: completed within the scope below.
Recorded: 2026-11-15 (Asia/Kolkata).

## Request

Run the project's Hindi/English retrieval diagnostics against the freshly
ingested corpus and record final numbers plus known misses (open item in
`tasks-in-progress/008-pipeline-integration.md`).

## What was run

`docker compose run --rm backend sakti evaluate-local`

This is the offline baseline: it embeds every child chunk from the prepared
bundles (cached as `.npy` per generation under `data/processed/`), does exact
cosine ranking in numpy, and compares against `data/evaluation.json`. It does
not touch MongoDB, so it measures the model + chunking, not ANN recall.

## Observed results

Model revision: `614241f622f53c4eeff9890bdc4f31cfecc418b3`, 6 authored cases.

| metric | value |
|---|---|
| hit rate @5 | 0.833 (5/6) |
| MRR @5 | 0.75 |

| language | question intent | expected | rank |
|---|---|---|---|
| en | designs not new/original | Designs Act §4 | 1 |
| hi | designs not new/original | Designs Act §4 | 1 |
| en | absolute grounds, trade mark | Trade Marks Act §9 | 1 |
| hi | absolute grounds, trade mark | Trade Marks Act §9 | **miss** |
| en | GI duration/renewal | GI Act §18 | 2 |
| hi | GI duration/renewal | GI Act §18 | 1 |

## The one miss, precisely

Hindi "व्यापार चिह्न का पंजीकरण अस्वीकार करने के पूर्ण आधार क्या हैं?" returned
the **correct document** at ranks 1–4 (Trade Marks Act §103, §107, §36E, §18) —
only §9 was absent. The score spread across that top-5 was **0.0036**, versus
0.0086–0.0329 for the cases that succeeded: the model placed the whole Trade
Marks Act in the right neighbourhood but could not separate §9 from its
neighbours for this phrasing.

## Why it matters (learning note)

Two different questions get confused here. "Did retrieval find the right law?"
is document-level recall — it passed. "Did it find the right section?" is
passage-level precision — that is where the miss happened. Since the corpus text
is English and only the question is Hindi, E5 has to bridge the language gap and
then discriminate among ~30 sections that all talk about trade marks and
registration. Flat scores are the symptom: when the top-5 are separated by
0.003, the ranking is close to arbitrary, which is also a natural place to put an
abstention margin threshold later.

## Validation actually run

- `sakti evaluate-local` exit 0; report written to
  `data/reports/retrieval-evaluation.json`.
- Numbers above read back from that report file, not from memory.
- Cache shape asserted by the evaluator itself: every generation's `.npy` must be
  `(len(children), 384)` or the run raises.

## Limitations

- Six authored cases is a smoke set; it does not establish legal answer accuracy,
  abstention quality, or MongoDB ANN recall.
- Local exact search is slightly more favourable than the ANN path used in
  production queries.
- The miss is a ranking issue, not a data or embedding defect: the chunk exists,
  is embedded, and is retrievable with other phrasings (see the English case).

## Next step

Consider a hybrid lexical + vector path and a score-margin abstention rule; both
need a larger evaluation set before they can be trusted.
