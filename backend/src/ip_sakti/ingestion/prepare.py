import json
from datetime import datetime, timezone
from pathlib import Path

from ip_sakti.chunking.parent_child import PIPELINE_VERSION, build_chunks, stable_id
from ip_sakti.embeddings.local import MODEL, REVISION
from ip_sakti.ingestion.audit import sha256_file
from ip_sakti.ingestion.extract import extract_pdf
from ip_sakti.ingestion.sections import parse_sections


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def prepare_corpus(settings, tokenizer, *, ocr=False, target_tokens=384) -> dict:
    catalog = json.loads(settings.catalog_path.read_text(encoding="utf-8"))
    entries = {entry["sha256"]: entry for entry in catalog["documents"]}
    report = {"created_at": datetime.now(timezone.utc).isoformat(), "prepared": [], "skipped_duplicates": [], "failed": []}
    seen = set()
    for path in sorted(settings.corpus_dir.rglob("*.pdf")):
        digest = sha256_file(path)
        relative = str(path.relative_to(settings.corpus_dir))
        if digest in seen:
            report["skipped_duplicates"].append(relative)
            continue
        seen.add(digest)
        try:
            if digest not in entries:
                raise ValueError("Missing content hash in data/catalog.json; register source metadata first.")
            metadata = {**entries[digest], "local_file": relative}
            if metadata["jurisdiction"] not in ("india", "international"):
                raise ValueError("Jurisdiction must be india or international.")
            pages = extract_pdf(path, ocr=ocr)
            _, sections, warnings = parse_sections(pages, metadata["kind"])
            if any(p["method"].startswith("tesseract") for p in pages):
                warnings.append("OCR text requires manual comparison against original page images.")
            if warnings:
                metadata["review_status"] = "needs_review"
            parents, children = build_chunks(metadata, pages, sections, tokenizer, target_tokens=target_tokens)
            if not children:
                raise ValueError("No searchable children were produced.")
            bundle = {"pipeline_version": PIPELINE_VERSION, "model": MODEL, "model_revision": REVISION, "target_tokens": target_tokens,
                      "document": metadata, "pages": pages, "parents": parents,
                      "children": children, "warnings": warnings}
            generation = stable_id(json.dumps(bundle, sort_keys=True, ensure_ascii=False))
            bundle["generation"] = generation
            output = settings.processed_dir / f"{digest}.json"
            write_json(output, bundle)
            report["prepared"].append({"file": relative, "bundle": output.name,
                                       "generation": generation, "parents": len(parents),
                                       "children": len(children), "warnings": warnings})
        except (ValueError, OSError, KeyError) as error:
            report["failed"].append({"file": relative, "reason": str(error)})
    write_json(settings.processed_dir / "manifest.json", report)
    return report

