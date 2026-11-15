# Restart the stack and connect to MongoDB

Status: completed within the scope below.
Recorded: 2026-11-15 (Asia/Kolkata).

## Request

Start the containers and connect to the MongoDB database.

## What changed

No source files changed. Docker Desktop was launched (the daemon was not
running), then `docker compose up -d` was run with the existing `.env`.

## Why it matters (learning note)

`docker compose up -d` is idempotent: it recreated nothing because the three
containers and their four named volumes already existed, so it simply started
them again and waited for the `mongodb` healthcheck before touching the backend.
The password never appears in a command line here because `compose.yaml` injects
`MONGO_USERNAME`/`MONGO_PASSWORD` from `.env` into the container environment.

## Validation actually run

- `docker info` succeeded after launching Docker Desktop (daemon ready ~10s).
- `docker compose up -d` exited 0; `mongodb` reached `Healthy`.
- `docker compose ps`: backend `Up (healthy)` on 127.0.0.1:8000, mongodb
  `Up (healthy)` on 127.0.0.1:27017, frontend `Up` on 127.0.0.1:3000.
- `curl http://localhost:8000/health/ready` → `{"status":"ready","database":"sakti_sahayak"}`
  (real round-trip to MongoDB through the backend).
- `mongosh` authenticated against `sakti_sahayak` with
  `db.adminCommand({ping:1}).ok` → `1`.
- Collections present: `chunks`, `documents`, `ingestion_runs`,
  `pipeline_metadata`, `sections`.
- `sakti status` output matches the direct `mongosh` counts.

## Observed state

- All corpus collections are **empty** (0 documents each); `pipeline_metadata`
  holds only the schema marker (1 doc).
- `chunks` has no `vectorSearch` search index yet — `corpus_vector_v1` is created
  by `ensure_indexes()` during `sakti ingest`, so this is expected at this stage.
- Plain index `document_id_1_parent_id_1` exists on `chunks`.

## Limitations

- The collections survived a full Docker restart, but they contained no corpus
  rows, so **corpus persistence is still not proven**; the real test comes after
  the first ingest.
- No ingestion or retrieval has run, so populated vector search remains unverified.

## Next step

`sakti ingest`, then `sakti index-status`, then a `sakti query` — the open items
of `tasks-in-progress/008-pipeline-integration.md`.
