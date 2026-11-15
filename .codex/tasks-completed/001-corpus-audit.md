# Corpus inventory and duplicate detection

Status: completed within the scope below.
Recorded: 2026-11-15 (Asia/Kolkata).

## Request

Inspect the supplied PDFs before building RAG.

## Completed work and learning

Added a SHA-256 inventory and PDF extraction audit. The original 12 files contain 8 unique documents. Filenames incorrectly imply separate Acts and Rules in some duplicate pairs.

## Files

backend/src/ip_sakti/ingestion/audit.py; backend/tests/test_audit.py

## Validation

Audit run on all original PDFs; duplicate, malformed-PDF and missing-directory tests pass.

## Limits / next step

A readable PDF is not automatically a current legal source.
