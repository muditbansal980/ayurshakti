# Build and understand the corpus pipeline

Read this alongside the code. Run commands from the repository root. The
frontend is intentionally not connected to the retrieval CLI.

## 1. Preserve originals and identify duplicates

Code: `backend/src/ip_sakti/ingestion/audit.py`.

```sh
backend/.venv/bin/python -m ip_sakti.cli audit
```

A SHA-256 hash identifies the exact bytes of a PDF. Two differently named files
with the same hash are one document, not two pieces of evidence. Original PDFs
stay in `data/raw`; derived files go elsewhere.

`data/catalog.json` maps each hash to its title, document type, jurisdiction,
language, source URL and version/review status. A filename is not proof of the
document's legal identity. Unknown URLs are stored as null rather than invented.

## 2. Extract text and preserve page numbers

Code: `ingestion/extract.py`.

The extractor retains a text record for each PDF page. It removes the known
IndiaCode watermark and page numbering while preserving legal punctuation,
brackets and amendment notes. Image-only pages require OCR review. The Docker
image includes Poppler and Tesseract with English and Hindi language packs.

`--ocr` performs local OCR. It is slower and does not guarantee correct legal
text: compare dates, amounts, section numbers and negations against the image.
Blank/illustrated covers can also need manual review. A document with an
unprocessed image page is reported as failed rather than silently indexed with
missing content. Successful documents can still proceed independently.

## 3. Detect legal sections as parents

Code: `ingestion/sections.py`.

The parser recognizes numbered sections, rules and explicit articles, including
Hindi heading labels. It skips front matter and the table of contents. A
section may continue across several PDF pages; page boundaries do not force a
new parent. Provisos, explanations and footnotes remain in the containing text.

Legal PDF extraction is imperfect. The parser is heuristic, not a verified legal
parser. It handles the supplied English statutory layouts; other layouts need
evaluation. Unrecognized documents fall back to explicitly labelled PDF pages
and remain unverified. Schedules are retained but table/column relationships
require visual review. Preambles/front matter are retained in page extraction,
but excluded from the section retrieval index when operative sections exist.

## 4. Make token-bounded children inside each parent

Code: `chunking/parent_child.py`.

Default target: **384 tokens including the title and locator prefix**. Overlap:
**32 tokens**, within the same parent. These are initial parameters, not proven
optimal values. The splitter prefers sentence/clause boundaries where feasible,
and uses token offsets for long passages. Every final input is counted again.

```text
Original PDF → Section 18 (parent, complete source text)
                   ├── child 1 + page/character offsets
                   └── child 2 + page/character offsets
```

Short sections may be a single child. Long sections produce several. Children
never cross their parent boundary. Each child stores its parent's ID and its
exact substring offsets, so we can check that the evidence was not rewritten.

```sh
backend/.venv/bin/python -m ip_sakti.cli prepare
```

Inspect `data/processed/manifest.json`, then open a listed bundle. Compare
`parents`, `children`, `pages`, `locator`, `start`, `end`, and `token_count`.
An exit code of 2 means some documents need attention; successful bundles are
still recorded in the manifest. Ingestion only uses that manifest, not stray
old files left in the directory.

## 5. Embed children locally

Code: `embeddings/local.py`.

The pinned `intfloat/multilingual-e5-small` revision produces 384 numbers per
passage. Similar meaning should produce nearby vectors. Model input is:

```text
passage: Document title | Section 18
The exact child text ...
```

Questions use `query: `, including Hindi questions. The prefixes are required by
the [E5 model's retrieval recipe](https://huggingface.co/intfloat/multilingual-e5-small).
Vectors are L2-normalized. Inputs longer than 512 tokens are rejected before the
model can silently truncate them. **A query is embedded once and never chunked.**

```sh
backend/.venv/bin/python -m ip_sakti.cli download-model
```

The first run downloads free weights. Native commands cache them under
`.cache/huggingface`; Docker uses its `model_cache` volume. After caching, you
can set `HF_HUB_OFFLINE=1`. Native and Docker caches are separate by default.
CPU inference is the supported default; the tested environment did not expose
MPS even though the physical computer has Apple silicon.

## 6. Ingest into MongoDB without publishing partial documents

Code: `storage/ingest.py`, `storage/indexes.py`.

The storage layers are:

| Collection | Contents |
|---|---|
| `documents` | Original hash, provenance, review status, active generation |
| `sections` | Complete parent sections |
| `chunks` | Child text, offsets, parent ID, embedding |
| `ingestion_runs` | Run status and document results |
| `pipeline_metadata` | Schema and embedding-model contract |

An ingestion generation describes one exact combination of source metadata,
extraction and chunking output. A run writes parents and children first. Only
after all children are present does it switch the document's active-generation
pointer. Query filters use active generations, so failed partial writes cannot
replace a good document. Re-ingesting an unchanged generation skips embedding.
Old generations are retained; no automatic history deletion occurs.

Removing a file from disk does **not** retire its already ingested database
document. Version retirement and garbage collection require an explicit later
administrative operation. For now, use a new database for independent corpus
experiments rather than assuming file deletion removes searchable material.

```sh
docker compose up --build -d
docker compose exec backend sakti prepare --ocr
docker compose exec backend sakti ingest
docker compose exec backend sakti index-status
docker compose exec backend sakti status
```

MongoDB creates the vector index during ingestion. Its dimensions must match the
model. A model-revision mismatch is rejected instead of mixing incompatible
vectors. Indexing is asynchronous: a queryable index can still be catching up
with recently inserted data. This is why end-to-end testing must use MongoDB,
not just the local embedding diagnostic.

## 7. Retrieve a whole question and expand its parents

Code: `retrieval/search.py`.

```sh
docker compose exec backend sakti query \
  'What designs cannot be registered?' \
  --jurisdiction india --include-unverified

docker compose exec backend sakti query \
  'भौगोलिक संकेत के पंजीकरण की अवधि क्या है?' \
  --jurisdiction india --include-unverified
```

The development flag is necessary for the initial corpus because its legal
currency has not been verified. Without it, only catalog entries reviewed as
`verified` and re-prepared/re-ingested are eligible. Merely downloading a file
from an official website does not prove it is the current applicable law.

Retrieval combines MongoDB vector search with its native text index (language
`none`, avoiding English stemming of Hindi). Reciprocal rank fusion combines
rank positions without pretending the two score scales are comparable. Keyword
search does not translate Hindi into English; cross-language matching comes from
the embedding model. `--vector-only` helps compare the two retrieval modes.

Results contain the matching child, the complete parent, document title,
provision, PDF page numbers, source URL when known, hash and review status. India
and international queries are filtered separately. Scores measure ranking, not
legal confidence. This CLI produces evidence candidates, not answers, and has
no calibrated out-of-scope abstention or legal-advice engine. Very long parent
sections are returned intact; a future generator must budget their context.

## 8. Measure retrieval before improving it

Code: `evaluation/local.py`; cases: `data/evaluation.json`.

```sh
backend/.venv/bin/python -m ip_sakti.cli evaluate-local
backend/.venv/bin/python -m unittest discover -s backend/tests -v
```

The local diagnostic compares normalized vectors directly, independently of
MongoDB. It caches vectors per prepared generation and reports hit rate and mean
reciprocal rank at five **distinct parents**. This is useful for checking whether
the model/chunks can find a provision, but it does not test MongoDB's approximate
search, hybrid fusion, answer accuracy or legal correctness. Six authored
questions are a smoke test, not a benchmark. Add expert-reviewed questions,
paraphrases, exception cases, out-of-scope queries and jurisdiction-conflict cases
before claiming production quality.

## 9. Collect additional authoritative sources

```sh
backend/.venv/bin/python -m ip_sakti.cli fetch-sources
```

This host-side command reads `data/sources.json`, downloads only those listed
PDFs, validates basic PDF readability, preserves their hashes and records URLs,
resolved URLs and download times in the catalog. It reports failures separately
in `data/reports/source-fetch.json`. Docker mounts original PDFs read-only, so
source acquisition is deliberately run on the host before preparation.

The currently collected WIPO document is the conference **Final Act**, not the
full treaty. The FSSAI notification URL returned 404 during collection. These
are explicit coverage gaps. Additional priorities are the Patents Act, verified
current patent/biodiversity rules, Drugs and Cosmetics legislation, Ayurveda
Aahara regulations, the full GRATK text, CBD/Nagoya and TRIPS. Do not label this
corpus complete or current until those sources and their versions are checked.
