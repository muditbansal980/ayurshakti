# Local multilingual embedding model

Status: completed within the scope below.
Recorded: 2026-11-15 (Asia/Kolkata).

## Request

Use Hindi and English with open-source embeddings and zero paid API cost.

## Completed work and learning

Installed multilingual-e5-small, pinned its downloaded revision, added E5 query/passage prefixes, normalization and rejection of overlong inputs.

## Files

backend/src/ip_sakti/embeddings/local.py; backend/pyproject.toml; backend/requirements.lock

## Validation

Downloaded weights and produced real 384-dimensional embeddings locally. Six-question initial diagnostic retrieved the expected provision in the top five for five cases.

## Limits / next step

Small diagnostic is not legal-accuracy validation. Native MPS was unavailable; tested inference uses CPU.
