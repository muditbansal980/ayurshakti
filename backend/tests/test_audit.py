import tempfile
import unittest
from pathlib import Path

from pypdf import PdfWriter

from ip_sakti.ingestion.audit import audit_corpus


class CorpusAuditTests(unittest.TestCase):
    def test_duplicates_blank_pages_and_corrupt_files_are_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            writer = PdfWriter()
            writer.add_blank_page(width=200, height=200)
            with (root / "act.pdf").open("wb") as target:
                writer.write(target)
            (root / "misnamed-rules.pdf").write_bytes((root / "act.pdf").read_bytes())
            (root / "broken.pdf").write_bytes(b"broken")
            report = audit_corpus(root)
            self.assertEqual(report["file_count"], 3)
            self.assertEqual(report["unique_document_count"], 2)
            self.assertEqual(report["duplicate_file_count"], 1)
            successful = next(d for d in report["documents"] if d["extraction_status"] != "failed")
            self.assertEqual(successful["low_text_pages"], [1])
            self.assertIsNone(successful["source_url"])
            self.assertEqual(len(list(root.iterdir())), 3)
            self.assertTrue(any(d["extraction_status"] == "failed" for d in report["documents"]))

    def test_missing_corpus_does_not_report_a_successful_empty_run(self):
        with self.assertRaises(ValueError):
            audit_corpus(Path("/path/that/does/not/exist"))


if __name__ == "__main__":
    unittest.main()
