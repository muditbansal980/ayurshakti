"""Inspect originals without modifying them or creating retrieval chunks."""

import hashlib
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from pypdf import PdfReader


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def audit_corpus(root: Path) -> dict:
    if not root.is_dir():
        raise ValueError(f"Corpus directory does not exist: {root}")
    groups = defaultdict(list)
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix.lower() == ".pdf":
            groups[sha256_file(path)].append(path)

    documents = []
    for digest, paths in groups.items():
        item = {
            "sha256": digest,
            "files": [str(path.relative_to(root)) for path in paths],
            "duplicate_count": len(paths) - 1,
            "source_url": None,
            "provenance_status": "needs_review",
        }
        try:
            reader = PdfReader(str(paths[0]))
            lengths = []
            first_text = ""
            for page in reader.pages:
                text = (page.extract_text() or "").strip()
                lengths.append(len(text))
                if not first_text and len(text) >= 40:
                    first_text = text[:500]
            item.update(
                pages=len(lengths),
                low_text_pages=[i + 1 for i, size in enumerate(lengths) if size < 40],
                total_extracted_characters=sum(lengths),
                first_text_sample=first_text,
                extraction_status="needs_ocr_review" if any(n < 40 for n in lengths) else "text_available",
            )
        except Exception as error:
            # A malformed file must not hide the other files in the audit.
            item.update(extraction_status="failed", error_type=type(error).__name__)
        documents.append(item)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "corpus_root": str(root.resolve()),
        "file_count": sum(len(paths) for paths in groups.values()),
        "unique_document_count": len(groups),
        "duplicate_file_count": sum(len(paths) - 1 for paths in groups.values()),
        "note": "Low-text pages may be scans, illustrations or blank pages; review before OCR. Filenames do not establish legal identity or currency.",
        "documents": documents,
    }

