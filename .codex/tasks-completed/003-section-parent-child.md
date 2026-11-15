# Section-aware parent-child implementation

Status: completed within the scope below.
Recorded: 2026-11-15 (Asia/Kolkata).

## Request

Use section-aware parent-child chunking after explaining alternatives.

## Completed work and learning

Added page-preserving extraction, optional local OCR, section detection, TOC/reference handling, exact text offsets, and token-bounded child splitting. Children stay within parents.

## Files

backend/src/ip_sakti/ingestion/extract.py; backend/src/ip_sakti/ingestion/sections.py; backend/src/ip_sakti/chunking/parent_child.py

## Validation

Tests cover cross-page exceptions, contents, footnotes, Hindi headings, deterministic IDs and child-token limits. Prepared real PDF bundles.

## Limits / next step

Parsing is heuristic. Image-only PDFs and table layouts need OCR or visual review. Latest corpus validation is tracked in the active task.
