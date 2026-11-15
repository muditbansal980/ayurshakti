# Move database credentials to .env and purge them from Git history

Status: completed within the scope below.
Recorded: 2026-11-15 (Asia/Kolkata).

## Request

Stop hardcoding the database credentials in `compose.yaml`, read them from a
`.env` file instead, remove the committed secret from GitHub, and push.

## What changed and why

Compose files are ordinary text; a fallback like `${MONGO_PASSWORD:-<value>}`
publishes the password in the repository and in every clone. Moving the value to
a gitignored `.env` keeps the compose file shareable while each machine supplies
its own secret.

- `compose.yaml`: `MONGO_USERNAME` and `MONGO_PASSWORD` now use the
  `${VAR:?message}` form, so Compose stops with an explanatory error instead of
  silently falling back. Ports, database name and image name keep their defaults.
- `backend/src/ip_sakti/config.py`: removed the hardcoded password fallback;
  `MONGODB_PASSWORD`/`MONGODB_USERNAME` are read from the environment (Docker
  injects them from `.env`; native runs use `backend/.env`).
- `.env.example` and `backend/.env.example`: credential values blanked.
- `README.md`: Compass example now shows placeholders and points to `.env`.
- `.env` (new, gitignored, mode 600): holds the real local values.

History was rewritten with `git filter-branch --tree-filter` to replace the
literal in all four commits (`8de62c6`, `952b9ba`, `cfc1332`, `0c8208f`), then
pushed with `--force-with-lease`. New history: `24b2784`, `e02c58f`, `ff3c894`,
`d6dfa38`.

## Validation actually run

- `git grep 'sakti-local-dev'` over tracked files → no matches.
- `docker compose config --quiet` → passes; with `MONGO_PASSWORD=` forced empty
  it fails with "required variable MONGO_PASSWORD is missing a value", proving
  the guard works.
- `docker compose up -d` → all three containers still running; backend
  `/health/ready` returns HTTP 200 `{"status":"ready"}`.
- `backend/.venv/bin/python -m unittest discover -s tests` → 12 tests, 11 run,
  1 skipped, OK.
- `git log -S'sakti-local-dev' origin/main` after fetching → no commits.
- `git diff pre-secret-purge-backup main` → empty, so the rewrite changed only
  the secret literal, not project content.
- `git ls-remote origin main` → `d6dfa38`, matching the local tip.

## Limitations

- The previous value was already public on GitHub for a period. It is a
  localhost-only development password, not a live service credential, but anyone
  who cloned the old history still has it. Because the existing MongoDB volume
  was initialised with it, it was deliberately kept as the `.env` value; rotate
  by removing the `mongo_data` volume and setting a new password.
- Rewriting history changes commit hashes: other clones need `git fetch` +
  `git reset --hard origin/main`. The old objects may remain reachable through
  GitHub caches for a while; GitHub support can force a purge if required.
- A local tag `pre-secret-purge-backup` still points at the pre-rewrite tip for
  recovery. Delete it with `git tag -d pre-secret-purge-backup` once satisfied.
- The `.env` file is not backed up anywhere; losing it means recreating the
  credentials.

## Next step

Ingest the corpus (`sakti ingest`) and verify retrieval against real MongoDB
vector indexes — the core remaining item in task 008.
