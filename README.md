# IP-SAKTI Sahayak — local data pipeline

This project is being built in stages so the data can be inspected and the RAG
steps learned separately. The intended retrieval languages are Hindi and English,
using local open-source embeddings and no paid API.

## Current checkpoint

Implemented:

- Docker Compose configuration for the existing Next.js frontend, Python backend,
  and a local MongoDB deployment that includes the vector-search process.
- Automatic creation of the database collections when the backend starts.
- Persistent MongoDB data, configuration, search storage, and model-cache volumes.
- A PDF audit CLI that detects byte-identical duplicates and low-text pages.
- Backend health endpoints and tests for the audit's failure/duplicate handling.

Also implemented: page-preserving extraction and optional local OCR, section-aware
parent-child chunking, local E5 embeddings, versioned MongoDB ingestion, vector
and keyword retrieval, citations, and a Hindi/English evaluation CLI.

Read [the step-by-step learning guide](docs/learning-guide.md) before ingestion.
Task records are under [.codex](.codex/README.md), with unfinished integration
checks kept separate from completed implementation work.

The frontend is packaged but is not connected to retrieval. The database starts
empty; starting Compose does not silently ingest unreviewed legal documents.
MongoDB end-to-end verification is still in progress.

## Start the local services

1. Install and open [Docker Desktop for Apple silicon](https://docs.docker.com/desktop/setup/install/mac-install/).
   It is free for personal and educational use. Docker Desktop supplies both
   Docker and the `docker compose` command. No Atlas account is required.
2. Run these commands from the directory containing this README:

   ```sh
   docker compose up --build -d
   docker compose ps
   docker compose logs backend
   ```

3. Open the frontend at <http://localhost:3000> and backend readiness at
   <http://localhost:8000/health/ready>.

The first build needs internet access for images, Python packages, npm packages,
and the frontend's existing Google Fonts build step. No model weights download
at backend startup. The embedding setup downloads and caches an open model
once; local inference will not require a paid service.

On a 16 GB Mac, start by assigning roughly 6 GB to Docker and close other heavy
apps during builds. This is a starting allocation, not a measured minimum. Model
inference inside these Linux containers will use CPU. A future native macOS
embedding run can use PyTorch MPS after testing compatibility.

Credentials are **not** stored in this repository. Copy `.env.example` to a
gitignored `.env` and fill in `MONGO_USERNAME` and `MONGO_PASSWORD` before
starting; Compose refuses to start while either is empty. `.env.example`
documents the optional port, database-name and image-name overrides. Set the
credentials before the first database start; changing them later does not change
users already stored in the MongoDB volume.

### Connections

- Backend containers connect to the Docker service hostname `mongodb`.
- MongoDB Compass on your Mac can use this **local-development** connection:

  ```text
  mongodb://<MONGO_USERNAME>:<MONGO_PASSWORD>@localhost:27017/sakti_sahayak?authSource=admin&directConnection=true
  ```

Use the values from your local `.env`.

These development credentials and all published ports are limited to localhost.
They are not appropriate for an internet-facing deployment. You do not need to
prepare an Atlas URL. Backend username/password fields are passed separately to
PyMongo, so punctuation in custom passwords does not need URI escaping there.
Credentials embedded in a Compass URL must be URL encoded.

## Inspect the data before ingestion

With Docker running:

```sh
docker compose exec backend sakti audit
docker compose exec backend sakti status
```

Without Docker, using the existing project virtual environment:

```sh
backend/.venv/bin/python -m pip install -e 'backend[embeddings,test]'
backend/.venv/bin/python -m ip_sakti.cli audit
backend/.venv/bin/python -m unittest discover -s backend/tests -v
```

The audit writes `data/reports/corpus-audit.json`. It preserves every original
PDF and groups duplicates by SHA-256 content hash. A low-text page can be a scan,
an illustration, or a blank page; the flag requests review rather than proving
OCR is necessary. An extracted document is not automatically a verified legal
authority. Source URLs and amendment/version status still need review.

At the first audit there were 12 PDFs and 8 distinct hashes. In particular,
different filenames did not reliably mean different Acts and Rules.

## Folder responsibilities

```text
compose.yaml                  Service networking, volumes and startup order
backend/
  Dockerfile                  Python service image
  pyproject.toml              Python package and dependency declarations
  src/ip_sakti/
    config.py                 Environment configuration
    cli.py                    Command-line entry points
    api/app.py                Health endpoints and startup lifecycle
    ingestion/audit.py        PDF inventory, duplicate and extraction checks
    storage/mongo.py          Database connection and collection initialization
  tests/                      Automated checks
dashboard/                    Existing frontend and its Dockerfile
data/
  raw/                        Original source documents; mounted read-only
  reports/                    Generated audit reports; excluded from Git
```

Chunking, embeddings, retrieval and evaluation have separate package directories. Collection names are `documents`,
`sections`, `chunks`, `ingestion_runs`, and `pipeline_metadata`. They are created
without dropping or replacing existing data.

## Understand the intended data flow

```text
Official source → preserved original → extraction/OCR → source/version review
    → approved chunking → local embeddings → MongoDB vector index

Whole Hindi/English question → query embedding → matching passages → citations
```

An embedding is a numerical representation used to compare meaning. The query
needs an embedding for vector search, but it is not split into corpus chunks.
Retrieval returns evidence; answer generation is a separate later stage.

The proposed lightweight model is
[intfloat/multilingual-e5-small](https://huggingface.co/intfloat/multilingual-e5-small).
It produces 384-dimensional embeddings. Its documented input prefixes and token
limit must be respected by the eventual implementation. Hindi-to-English
cross-language retrieval must be measured on representative questions; language
support alone does not guarantee good legal retrieval.

## Stop and restart

```sh
docker compose stop
docker compose start
```

`docker compose down` removes containers and networking but retains named
volumes. Adding `-v` deletes those volumes, including stored documents and search
data. Do not use it as a routine restart command.

## Validation and deployment limits

Eleven unit tests currently pass. The real multilingual model has been downloaded
and produces 384-dimensional embeddings. Local exact-vector diagnostics are saved
in `data/reports/retrieval-evaluation.json`; they do not verify MongoDB search.
Docker installation and end-to-end container tests are still in progress.

The local frontend build previously failed because Turbopack could not bind a
build-worker port (`Operation not permitted`), including an elevated retry.
Its container build still needs verification.

MongoDB describes
[Atlas Local](https://www.mongodb.com/docs/search/self-managed/current/installation/quick-start/)
as a local development/testing image, not a production deployment. This Compose
setup is a learning and development environment. `backend/requirements.lock`
records resolved native package versions; Linux container resolution and image
digests still need verification before a reproducible production release.

## Run the data pipeline

After the containers are running:

```sh
docker compose exec backend sakti prepare --ocr
docker compose exec backend sakti ingest
docker compose exec backend sakti index-status
docker compose exec backend sakti query 'What designs cannot be registered?' --jurisdiction india --include-unverified
```

`prepare` exits with code 2 if some files fail and still records successful
bundles. Review its manifest before ingestion. `--include-unverified` is for
inspecting the initial corpus; default retrieval excludes unreviewed sources.
These commands return evidence candidates, not generated legal answers.
# ayurshakti
