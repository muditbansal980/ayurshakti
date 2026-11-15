# Project collaboration

- Explain implementation stages in plain language: the user is learning RAG.
- Keep corpus ingestion/retrieval separate from frontend integration unless the
  user explicitly expands the scope.
- Use Hindi/English local open-source embeddings and avoid paid services.
- Break each user task into small work items. Keep one Markdown record per
  completed item in `.codex/tasks-completed/`, following `.codex/README.md`.
  Keep unfinished items in `.codex/tasks-in-progress/` with accurate status.
- Record what changed, why, relevant files, checks actually run, and limitations.
  Never mark runtime verification complete merely because code was written.
- Preserve originals in `data/raw/`, source provenance, and version history.
- Follow `dashboard/AGENTS.md` when editing frontend files.
