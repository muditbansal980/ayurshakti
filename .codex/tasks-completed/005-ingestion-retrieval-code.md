# MongoDB ingestion and retrieval implementation

Status: completed within the scope below.
Recorded: 2026-11-15 (Asia/Kolkata).

## Request

Store corpus vectors and offer a standalone retrieval CLI without frontend integration.

## Completed work and learning

Added immutable generations, active-version filtering, vector and keyword indexes, rank fusion, parent expansion and citations. Queries are embedded once, never chunked.

## Files

backend/src/ip_sakti/storage/ingest.py; backend/src/ip_sakti/storage/indexes.py; backend/src/ip_sakti/retrieval/search.py

## Validation

Tests verify failure does not activate partial generations, bundle tampering is rejected, jurisdictions and active versions are filtered, and unverified material is excluded by default.

## Limits / next step

MongoDB end-to-end verification remains an active work item; this record covers implementation and unit checks only.
