# Failure analysis (run of 2026-11-15)

Derived from `data/reports/bilingual-evaluation.json` plus the stored parent text. Each
entry states what happened, not just that a metric was low.

## 1. Romanized Hindi fails completely (4/4, recall@10 = 0)

Queries such as `Naya ya maulik nahin hone par design ka panjikaran kyon mana hai?`
retrieve parents from the **Hindi Designs Act** (top-1 0.839), not the expected English
sections 4 / 9 / 18 / 6. The model treats the Latin string as close to Devanagari
semantics but cannot tie it to the right provision, and the corpus now has a tempting
Hindi neighbour for two of the four queries.

Reading: transliteration is a genuine gap for `multilingual-e5-small`. It should be
reported as its own category (it is), and any "Hindi support" claim must exclude it.

## 2. Hindi→English: half the misses are correct answers in Hindi

- `hi_en_design` — top-1 (0.890) is the **Hindi** Designs Act section 4 parent. Right
  answer, wrong language for the `hi_en` label. This is the new Hindi document competing
  with its English twin, not a retrieval error.
- `hi_en_trademark` — top-1 0.825, no Hindi Trade Marks Act exists, so this is a real
  Hindi-query miss on English content.

Implication: once both language versions of a statute exist, `hi_en` cases partly measure
"which language version wins", not language-agnostic retrieval. Future datasets should
make that intent explicit (expected document, not just expected language).

## 3. English→Hindi fails (0/2)

`en_hi_cancel` and `en_hi_novelty` both return English Designs Act sections ahead of the
judged Hindi parents. With one Hindi document among eight, English queries are dominated
by English siblings. Sample size is 2; do not generalise.

## 4. `difficult` misses are topical, not language failures

- `difficult_limited_context` (`How long is GI protection?`) misses GI Act s.18; top-3
  (0.845/0.842/0.840) are other English statute sections.
- `difficult_short` (`GI renewal`) does retrieve s.18 but at rank 7 (MRR 0.14).

Both are short-query ambiguity: two-word queries carry little context and the corpus has
many near-duplicate statutory phrases. A synonym/hybrid layer would be the next
experiment; nothing here justifies disabling ANN.

## 5. Abstention does not work at 0.7

Both out-of-scope questions (0.772, 0.785 top-1) returned 10 results. Across the whole
run, wrong-match top-1 scores reach 0.891 while correct top-1 starts at 0.830, so no
single absolute cut separates them. Consequence: the system currently never says "I do
not know".

## 6. What is deliberately not counted as a failure

- Precision@5 of 0.10–0.20: an artefact of one judged parent per case.
- `scored < cases` in `difficult` (6 of 8): two cases yielded no hits at all under the
  ranking floor and were excluded from the mean, not scored as zero. Reported explicitly
  so the exclusion cannot be mistaken for a pass.
- First-query 1.97 s: lazy model load, not steady-state latency (21–33 ms elsewhere).

## Next experiments, in order of expected value

1. Calibrate abstention on top-1 vs runner-up margin instead of absolute cosine.
2. Add a second Hindi source before making any Hindi-quality claim beyond section-level.
3. Test query expansion for transliteration (map Latin→Devanagari before embedding).
4. Only then consider hybrid lexical fusion, which this corpus's near-duplicate statutory
   language may actually reward.
