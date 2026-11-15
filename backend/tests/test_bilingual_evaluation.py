import math
import copy
import unittest

from ip_sakti.evaluation.bilingual import evaluate, parent_metrics, validate_dataset


class MetricsTests(unittest.TestCase):
    def test_parent_dedup_and_fixed_precision_denominator(self):
        hits = [{'parent_id': p} for p in ['a', 'a', 'x', 'b']]
        metrics = parent_metrics(hits, [{'parent_id': 'a', 'grade': 3}, {'parent_id': 'b', 'grade': 1}])
        self.assertEqual(metrics['recall_at_5'], 1)
        self.assertEqual(metrics['precision_at_5'], 0.4)
        self.assertEqual(metrics['mrr'], 1)
        self.assertAlmostEqual(metrics['ndcg_at_5'], (7 + 1 / math.log2(4)) / (7 + 1 / math.log2(3)))

    def test_cutoffs_and_missing_relevant(self):
        hits = [{'parent_id': str(i)} for i in range(10)]
        m = parent_metrics(hits, [{'parent_id': '5', 'grade': 2}, {'parent_id': 'absent', 'grade': 1}])
        self.assertEqual(m['recall_at_5'], 0)
        self.assertEqual(m['recall_at_10'], 0.5)
        self.assertEqual(m['mrr'], 1 / 6)
        self.assertEqual(m['ndcg_at_5'], 0)

    def test_empty_results_and_no_gold(self):
        self.assertTrue(all(v == 0 for v in parent_metrics([], [{'parent_id': 'a', 'grade': 1}]).values()))
        with self.assertRaises(ValueError):
            parent_metrics([], [])

    def test_noanswer_and_missing_languages_do_not_inflate_metrics(self):
        class Service:
            def retrieve(self, query, **kwargs):
                self.threshold = kwargs['min_score']
                return {'results': [], 'timings': {'embedding_ms': 1, 'search_ms': 2, 'total_ms': 3}}
        service = Service()
        dataset = {'cases': [
            {'id': 'n', 'query': 'weather', 'category': 'difficult', 'label_status': 'provisional', 'no_answer': True, 'qrels': []},
            {'id': 'h', 'query': 'hi', 'category': 'hi_hi', 'label_status': 'blocked', 'blocked_reason': 'missing source', 'qrels': []}]}
        result = evaluate(dataset, service)
        self.assertEqual(service.threshold, 0.7)
        self.assertIsNone(result['categories']['hi_hi']['metrics'])
        self.assertEqual(result['categories']['hi_hi']['blocked'], 1)
        self.assertEqual(result['categories']['difficult']['scored'], 0)
        self.assertEqual(result['no_answer']['abstained'], 1)

    def test_stale_gold_is_rejected(self):
        class Collection:
            def find_one(self, *args): return None
        class DB:
            documents = sections = Collection()
        case = {'id': 'x', 'query': 'q', 'category': 'en_en', 'label_status': 'provisional',
                'query_language': 'en', 'expected_content_languages': ['en'],
                'qrels': [{'parent_id': 'p', 'document_id': 'd', 'grade': 3}]}
        with self.assertRaisesRegex(ValueError, 'Stale'):
            validate_dataset({'cases': [case]}, DB())

    def test_source_relationship_and_language_labels_are_checked(self):
        class Collection:
            def __init__(self, record): self.record = record
            def find_one(self, *args): return self.record
        class DB:
            documents = Collection({'active_generation': 'g', 'language': 'hi'})
            sections = Collection({'document_id': 'd', 'generation': 'g', 'locator': 'Section 4', 'text': 'नई या मूल डिजाइन नहीं है'})
            chunks = Collection({'parent_id': 'p', 'document_id': 'd', 'generation': 'g'})
        case = {'id': 'x', 'query': 'Which designs are prohibited?', 'category': 'en_hi',
                'label_status': 'provisional', 'query_language': 'en', 'expected_content_languages': ['hi'],
                'qrels': [{'parent_id': 'p', 'document_id': 'd', 'generation': 'g', 'grade': 3,
                           'language': 'hi', 'locator': 'Section 4', 'evidence_excerpt': 'नई या मूल', 'chunk_ids': ['c']}]}
        validate_dataset({'cases': [case]}, DB())
        for field, value in [('generation', 'stale'), ('locator', 'Section 5'),
                             ('evidence_excerpt', 'invented'), ('language', 'en')]:
            with self.subTest(field=field):
                invalid = copy.deepcopy(case)
                invalid['qrels'][0][field] = value
                with self.assertRaisesRegex(ValueError, 'Stale'):
                    validate_dataset({'cases': [invalid]}, DB())
        db = DB()
        db.chunks = Collection({'parent_id': 'other', 'document_id': 'd', 'generation': 'g'})
        with self.assertRaisesRegex(ValueError, 'relationship'):
            validate_dataset({'cases': [case]}, db)
        case['expected_content_languages'] = ['en']
        with self.assertRaisesRegex(ValueError, 'Language category'):
            validate_dataset({'cases': [case]}, DB())

    def test_invalid_abstention_threshold_rejected(self):
        for threshold in (float('nan'), float('inf'), True, 1.1, -1.1):
            with self.subTest(threshold=threshold), self.assertRaises(ValueError):
                evaluate({'cases': []}, None, no_answer_threshold=threshold)

    def test_category_scores_and_latency_stay_separate(self):
        class Service:
            def retrieve(self, query, **kwargs):
                self.filters = kwargs['filters']
                parent = 'gold' if query == 'hindi' else 'wrong'
                return {'results': [{'parent_id': parent, 'document_id': 'd', 'chunk_id': 'c', 'score': 0.8}],
                        'timings': {'embedding_ms': 2, 'validation_ms': 10, 'search_ms': 3, 'total_ms': 15}}
        service = Service()
        cases = [{'id': category, 'query': query, 'category': category, 'label_status': 'provisional',
                  'qrels': [{'parent_id': 'gold', 'document_id': 'd', 'grade': 3}]}
                 for category, query in [('hi_en', 'hindi'), ('transliteration', 'romanized')]]
        result = evaluate({'cases': cases}, service)
        self.assertEqual(result['categories']['hi_en']['metrics']['recall_at_5'], 1)
        self.assertEqual(result['categories']['transliteration']['metrics']['recall_at_5'], 0)
        self.assertEqual(result['categories']['hi_en']['mean_timings_ms']['validation_ms'], 10)
        self.assertEqual(result['results'][1]['missing_gold_parents_at_10'], ['gold'])
        self.assertEqual(service.filters, {'jurisdiction': 'india'})


if __name__ == '__main__':
    unittest.main()
