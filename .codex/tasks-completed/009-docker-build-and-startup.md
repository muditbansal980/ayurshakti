# Docker image build and stack startup

Status: completed within the scope below.
Recorded: 2026-11-15 (Asia/Kolkata).

## Request

Build the images with `docker compose up --build -d` and check whether the build
and startup succeeded.

## What changed

No source files changed. This task produced build artifacts and runtime state:
three images, four named volumes, one network and three running containers.

Images built:

- `ip-sakti-sahayak-backend:latest` (10 GB — torch and its CUDA wheels dominate)
- `ip-sakti-sahayak-frontend:latest` (414 MB)
- `mongodb/mongodb-atlas-local:8.0` (2.01 GB, pulled)

Volumes created: `ip-sakti-sahayak_mongo_data`, `_mongo_config`, `_mongo_search`,
`_model_cache`.

## Why it matters (learning note)

`up --build` is the step that turns the Compose file into running processes:
Compose builds each service's image from its Dockerfile, creates the shared
network and volumes, starts MongoDB first, waits for its healthcheck, then starts
the backend. The backend's `depends_on: condition: service_healthy` is why the
database is available before the app starts asking it for data.

## Validation actually run

- `docker compose up --build -d` exited 0 (log: `/tmp/compose-up.log`).
- `docker compose ps`: backend `Up (healthy)`, mongodb `Up (healthy)`,
  frontend `Up` — ports 8000, 27017 and 3000 bound to 127.0.0.1.
- `curl http://localhost:8000/health/ready` → HTTP 200
  `{"status":"ready","database":"sakti_sahayak"}` (real database round-trip).
- `curl http://localhost:3000/` → HTTP 200.
- Collections auto-created in `sakti_sahayak`: `chunks`, `ingestion_runs`,
  `documents`, `sections`, `pipeline_metadata`.
- Vector-search smoke test: created a 384-dimension `vectorSearch` index on
  `chunks.embedding`, observed `status: READY, queryable: true`, then dropped it.
  This proves the Atlas Local search process (the Java `mongot` process) is live.
- `pgrep` is absent from the MongoDB image, so process checks must read
  `/proc/*/comm` instead; that is a tooling detail, not a health failure.

## Limitations

- The stack is running but the database is **empty**: no corpus has been
  ingested yet, so retrieval against real vector indexes is still unverified.
- The backend image is 10 GB because `torch` pulls CUDA wheels that a CPU-only
  container does not need; a CPU-only index would shrink it substantially.
- Frontend container serves the UI but is deliberately not wired to retrieval.

## Next step

`docker compose exec backend sakti ingest`, then `sakti index-status`, then
`sakti query` — the remaining core items of task 008.
