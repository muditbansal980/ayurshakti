import unittest

from ip_sakti.chunking.parent_child import build_chunks
from ip_sakti.ingestion.sections import parse_sections
from ip_sakti.retrieval.search import fuse_rankings


class CharacterTokenizer:
    """A deliberately small test tokenizer to stress boundaries, not model quality."""
    def encode(self, text, add_special_tokens=True, **kwargs):
        return list(range(len(text) + (2 if add_special_tokens else 0)))

    def __call__(self, text, **kwargs):
        return {"offset_mapping": [(i, i + 1) for i in range(len(text))]}


class SectionTests(unittest.TestCase):
    def test_contents_cross_references_footnotes_and_exceptions(self):
        pages = [
            {"page": 1, "text": "LIST OF AMENDING ACTS\n1. The Amending Act.\nARRANGEMENT OF SECTIONS\n1. Short title.\n2. Definitions.\nTHE SCHEDULE."},
            {"page": 2, "text": "CHAPTER I\n1. Short title.—(1) This Act may be called Test.\n2. Definitions.—In this Act,\n(a) a reference to\nsection 49;\n1. Subs. by Act 1 of 2000.\nProvided that an exception applies."},
            {"page": 3, "text": "Explanation.—This exception continues on a new page.\n3. Duties.—A duty applies.\nTHE SCHEDULE\n1. Table row\n2. Another row"},
        ]
        text, sections, warnings = parse_sections(pages)
        self.assertEqual([s["locator"] for s in sections], ["Section 1", "Section 2", "Section 3", "THE SCHEDULE"])
        self.assertEqual(sections[1]["pages"], [2, 3])
        self.assertIn("Provided that", sections[1]["text"])
        self.assertIn("Explanation", sections[1]["text"])
        for section in sections:
            self.assertEqual(section["text"], text[section["start"]:section["end"]])
        self.assertTrue(any("Schedule/table" in warning for warning in warnings))

    def test_hindi_and_explicit_treaty_articles(self):
        for text, kind, expected in [
            ("धारा १\nयह नियम है।\nधारा २\nयह अपवाद है।", "act", ["Section १", "Section २"]),
            ("Article 1\nDefinitions\nA definition.\nArticle 2\nObjectives", "treaty", ["Article 1", "Article 2"]),
        ]:
            _, sections, _ = parse_sections([{"page": 1, "text": text}], kind)
            self.assertEqual([s["locator"] for s in sections], expected)

    def test_child_limits_page_provenance_overlap_and_reproducibility(self):
        pages = [{"page": 1, "text": "1. Duties.—(1) " + "Duty applies. " * 40},
                 {"page": 2, "text": "Provided that an exception applies. " * 20 + "\n2. End.—Final provision."}]
        text, sections, _ = parse_sections(pages)
        doc = {"sha256": "abc", "title": "Test Act"}
        parents, children = build_chunks(doc, pages, sections, CharacterTokenizer(), target_tokens=160, overlap_tokens=16)
        self.assertGreater(len(children), 2)
        self.assertEqual((parents, children), build_chunks(doc, pages, sections, CharacterTokenizer(), target_tokens=160, overlap_tokens=16))
        by_id = {p["_id"]: p for p in parents}
        covered = set()
        for child in children:
            self.assertLessEqual(child["token_count"], 160)
            self.assertEqual(child["text"], text[child["start"]:child["end"]])
            self.assertTrue(child["pages"])
            self.assertTrue(by_id[child["parent_id"]]["start"] <= child["start"] < child["end"] <= by_id[child["parent_id"]]["end"])
            covered.update(range(child["start"], child["end"]))
        for parent in parents:
            self.assertTrue(all(i in covered for i in range(parent["start"], parent["end"]) if not text[i].isspace()))

    def test_rank_fusion_rewards_agreement_without_score_scale_assumptions(self):
        results = fuse_rankings([[{"_id": "a"}, {"_id": "b"}], [{"_id": "b"}, {"_id": "c"}]], 3)
        self.assertEqual(results[0]["_id"], "b")


if __name__ == "__main__":
    unittest.main()
