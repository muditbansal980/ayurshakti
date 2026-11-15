# Generate and persist embeddings during ingestion

Status: completed within the scope below.
Recorded: 2026-11-15 (Asia/Kolkata).

## Request

Audit the ingestion pipeline and make sure every child chunk gets a local
384-dimensional embedding stored in `sakti_sahayak.chunks`, without paid APIs
and without replacing the selected model.

## What the audit found

The pipeline already embedded and persisted — `sakti ingest` was simply never
run, so the collections were empty. The real defects were in the surrounding
contract:

1. `ingest.py` and `search.py` read the loaded revision from
   `embedder.model[0].auto_model.config._commit_hash`, a private API that returns
   `None` for local/offline loads. A `None` revision would have been written into
   `pipeline_metadata`, silently disabling model-version validation.
2. Stored chunk documents lacked `section_id`, `embedding_model`,
   `embedding_revision`, `embedding_dimensions`, `metadata`, `created_at` and
   `updated_at`.
3. Nothing validated embedding dimension, finiteness, or empty output before a
   write; a broken vector could reach MongoDB.
4. The batch size was hardcoded in two places and was not configurable.
5. `sakti status` reported only collection counts, and `sakti download-model`
   did not verify dimensions or report the cache location.
6. A not-yet-queryable search index was treated as a failed ingestion run, even
   though the vectors were already durable.
7. `Settings.embedding_model` was ignored, leaving room for a silent model swap.

## What changed

- `embeddings/local.py`: pinned constants exposed (`MODEL`, `REVISION`, `DIMENSIONS`),
  `PASSAGE_PREFIX`/`QUERY_PREFIX`, `validate_vector`/`validate_vectors`
  (non-empty, exactly 384, all finite), configurable `batch_size`, revision
  verification only when the loader reports a commit hash, and an explicit error
  when a different model/revision is requested — no fallback.
- `storage/ingest.py`: uses the pinned revision as the contract, adds the missing
  chunk fields, switches chunk writes to `UpdateOne` upserts with
  `$setOnInsert: created_at` and `$set: updated_at`, verifies the persisted
  embedding count equals the bundle's child count before activating a generation,
  records `partially_completed` when some documents succeeded, and no longer fails
  a run solely because the search index is still building.
- `storage/status.py` (new): connection/database, model name/revision/dimensions/
  cache status, counts with and without embeddings, stored contract vs expected,
  last ingestion, latest run, and vector index state. Datetimes are ISO strings.
- `cli.py`: `download-model` warms the model, validates 384 dimensions, reports the
  cache path, and exits non-zero on failure; `status` uses the new report;
  `ingest --batch-size` overrides `EMBEDDING_BATCH_SIZE`.
- `config.py`: adds `embedding_revision`, `embedding_batch_size`, `model_cache_dir`.
- `retrieval/search.py`: validates the contract against pinned constants.
- `backend/Dockerfile`: dependencies install in their own layer before `COPY src`,
  so a code change no longer reinstalls torch; model weights are still not baked
  into the image.
- Tests: `tests/test_embeddings.py` (validation, pinning, prefixes, persistence
  fields, idempotency, partial failure), `tests/test_status.py` (JSON-serializable
  report), and updated `test_storage_retrieval.py` / `test_mongo_integration.py`
  for the new contract.

## Why it matters (learning note)

Chunking is deterministic text splitting; embedding is the model. They are joined
only by the tokenizer (384-token budget measured in E5 tokens) and by
`embedding_text`, which the model consumes verbatim. The `generation` id is what
makes re-ingestion safe: chunks are keyed by generation, and a document's
`active_generation` pointer only moves after every child of that generation is
confirmed to have an embedding.

## Validation actually run

- `python -m compileall backend/src backend/tests` → OK.
- `docker compose run --rm ... python -m unittest discover -s tests` →
  **29 tests, OK (1 skipped: the opt-in Mongo test)**.
- `RUN_MONGO_INTEGRATION=1` copy of the same command →
  real `$vectorSearch` + filter + parent citation + keyword fusion test **OK**.
- `docker compose build backend` after the Dockerfile change → image built.
- `sakti download-model` → exit 0, `dimensions: 384`,
  cache `/app/model-cache/hub/models--intfloat--multilingual-e5-small`
  (471 MB on the `model_cache` volume).
- `sakti status` → 866/866 chunks embedded, `cached: true`,
  contract `matches_expected: true`, index `READY`.

## Limitations

- Old generations are retained by design; re-preparing a changed document leaves
  the previous generation's chunks in `chunks` (unsearchable, since every query
  filters on active generations) until an explicit cleanup.
- Every ingested document is still `review_status: needs_review`, so default
  `sakti query` returns nothing until sources are verified or
  `--include-unverified` is passed.
- OCR for image-only PDFs and the remaining source-collection checks are out of
  scope here (see `tasks-in-progress/008-pipeline-integration.md`).

## Next step

Ingest and verify against MongoDB — recorded in
`tasks-completed/013-verify-embeddings-in-mongodb.md`.
