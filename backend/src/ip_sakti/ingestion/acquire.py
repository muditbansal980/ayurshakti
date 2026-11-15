"""Download only the explicit public source list; preserve provenance and originals."""

import hashlib
import json
import ssl
from datetime import datetime, timezone
from io import BytesIO
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from pypdf import PdfReader
import truststore

from ip_sakti.ingestion.prepare import write_json


def fetch_sources(settings, source_list) -> dict:
    catalog = json.loads(settings.catalog_path.read_text())
    by_hash = {d["sha256"]: d for d in catalog["documents"]}
    results = []
    failed = []
    for source in json.loads(source_list.read_text())["sources"]:
        try:
            url = source["url"]
            if urlparse(url).scheme != "https":
                raise ValueError("Sources must use HTTPS.")
            request = Request(url, headers={"User-Agent": "IP-SAKTI-Corpus/0.1 (educational research)"})
            # Use OS certificate trust (including managed-network roots), never
            # disable TLS verification to work around a proxy certificate.
            with urlopen(request, timeout=60, context=truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)) as response:
                body = response.read(25 * 1024 * 1024 + 1)
                resolved_url = response.url
            if len(body) > 25 * 1024 * 1024 or not body.startswith(b"%PDF-"):
                raise ValueError(f"Expected a PDF under 25 MiB from {url}")
            reader = PdfReader(BytesIO(body))
            if not len(reader.pages):
                raise ValueError("Downloaded PDF has no pages.")
            digest = hashlib.sha256(body).hexdigest()
            destination = settings.corpus_dir / "official" / f"{digest}.pdf"
            destination.parent.mkdir(parents=True, exist_ok=True)
            if not destination.exists():
                temporary = destination.with_suffix(".part")
                temporary.write_bytes(body)
                temporary.replace(destination)
            if digest not in by_hash:
                by_hash[digest] = {
                    "sha256": digest, "title": source["title"], "kind": source["kind"],
                    "jurisdiction": source["jurisdiction"], "language": source["language"],
                    "source_url": url, "resolved_url": resolved_url,
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                    "review_status": "needs_review", "version_label": source["version_label"],
                }
            # Persist after each source so a later download failure loses no provenance.
            write_json(settings.catalog_path, {"documents": list(by_hash.values())})
            results.append({"title": source["title"], "file": str(destination), "sha256": digest})
        except (OSError, ValueError) as error:
            failed.append({"title": source["title"], "url": source["url"], "reason": str(error)})
    return {"downloaded": results, "failed": failed}
