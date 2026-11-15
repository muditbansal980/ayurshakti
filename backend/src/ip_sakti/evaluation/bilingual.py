"""Corpus-grounded parent-level evaluation. Never writes to MongoDB."""
import argparse
import hashlib
import json
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path

CATEGORIES = ('en_en', 'hi_hi', 'hi_en', 'en_hi', 'mixed', 'transliteration', 'difficult')
METRICS = ('recall_at_5', 'recall_at_10', 'precision_at_5', 'mrr', 'ndcg_at_5')
LANGUAGE_PAIRS = {'en_en': ('en', 'en'), 'hi_hi': ('hi', 'hi'),
                  'hi_en': ('hi', 'en'), 'en_hi': ('en', 'hi')}


def parent_metrics(results, qrels):
    """Sparse judged positives; unjudged parents count as nonrelevant, P@5 divisor=5."""
    grades = {q['parent_id']: q['grade'] for q in qrels if q['grade'] > 0}
    if not grades:
        raise ValueError('Answerable cases require at least one positive parent judgment.')
    ranked = list(dict.fromkeys(r['parent_id'] for r in results))
    relevant = set(grades)
    dcg = sum((2 ** grades.get(p, 0) - 1) / math.log2(i + 2) for i, p in enumerate(ranked[:5]))
    ideal = sum((2 ** g - 1) / math.log2(i + 2) for i, g in enumerate(sorted(grades.values(), reverse=True)[:5]))
    return {
        'recall_at_5': len(set(ranked[:5]) & relevant) / len(relevant),
        'recall_at_10': len(set(ranked[:10]) & relevant) / len(relevant),
        'precision_at_5': len(set(ranked[:5]) & relevant) / 5,
        'mrr': next((1 / i for i, p in enumerate(ranked[:10], 1) if p in relevant), 0.0),
        'ndcg_at_5': dcg / ideal,
    }


def validate_dataset(dataset, db):
    """Reject stale/imaginary IDs or changed contents before reporting any score."""
    seen = set()
    for case in dataset['cases']:
        if case['id'] in seen or case['category'] not in CATEGORIES:
            raise ValueError('Duplicate case ID or unsupported category.')
        seen.add(case['id'])
        if not isinstance(case['query'], str) or not case['query'].strip() or not case.get('label_status'):
            raise ValueError('Missing query or label-review status.')
        expected = case.get('expected_content_languages')
        if not isinstance(expected, list) or not case.get('query_language'):
            raise ValueError('Missing query/content language metadata.')
        if case['category'] in LANGUAGE_PAIRS:
            query_language, content_language = LANGUAGE_PAIRS[case['category']]
            if case['query_language'] != query_language or expected != [content_language]:
                raise ValueError('Language category disagrees with query/content labels.')
        if (case['category'] == 'mixed' and case['query_language'] != 'hi-en'
                or case['category'] == 'transliteration' and case['query_language'] != 'hi-Latn'):
            raise ValueError('Mixed/transliterated query language is mislabeled.')
        if case.get('blocked_reason'):
            continue
        if case.get('no_answer'):
            if case['qrels']:
                raise ValueError('No-answer cases cannot contain positive judgments.')
            continue
        if not case['qrels']:
            raise ValueError('Missing gold parents; mark missing coverage blocked explicitly.')
        parents = set()
        for q in case['qrels']:
            if q['parent_id'] in parents or type(q['grade']) is not int or not 1 <= q['grade'] <= 3:
                raise ValueError('Duplicate parent or invalid relevance grade.')
            parents.add(q['parent_id'])
            doc = db.documents.find_one({'_id': q['document_id']})
            parent = db.sections.find_one({'_id': q['parent_id']})
            if (not doc or not parent or doc.get('active_generation') != q['generation']
                    or parent.get('generation') != q['generation']
                    or parent.get('document_id') != q['document_id']
                    or doc.get('language') != q['language']
                    or q['language'] not in case['expected_content_languages']
                    or not isinstance(parent.get('text'), str)
                    or not q['evidence_excerpt'] or q['evidence_excerpt'] not in parent['text']
                    or parent.get('locator') != q.get('locator')):
                raise ValueError(f"Stale or ungrounded gold judgment: {case['id']}")
            if not q['chunk_ids']:
                raise ValueError('Gold parent requires a supporting child ID.')
            for chunk_id in q['chunk_ids']:
                child = db.chunks.find_one({'_id': chunk_id}, {'parent_id': 1, 'document_id': 1, 'generation': 1})
                if not child or any(child.get(k) != q[k] for k in ('parent_id', 'document_id', 'generation')):
                    raise ValueError(f"Invalid gold child relationship: {case['id']}")


def evaluate(dataset, service, *, no_answer_threshold=0.7):
    if (isinstance(no_answer_threshold, bool) or not isinstance(no_answer_threshold, (int, float))
            or not math.isfinite(no_answer_threshold) or not -1 <= no_answer_threshold <= 1):
        raise ValueError('No-answer threshold must be a finite cosine score in [-1, 1].')
    results = []
    for case in dataset['cases']:
        row = {'id': case['id'], 'query': case['query'], 'category': case['category'],
               'label_status': case['label_status'], 'difficulty': case.get('difficulty'),
               'query_language': case.get('query_language'),
               'expected_content_languages': case.get('expected_content_languages')}
        if case.get('blocked_reason'):
            results.append({**row, 'status': 'blocked', 'reason': case['blocked_reason']})
            continue
        no_answer = case.get('no_answer', False)
        response = service.retrieve(case['query'], top_k=10,
                                    min_score=no_answer_threshold if no_answer else -1.0,
                                    filters={'jurisdiction': case.get('jurisdiction', 'india')},
                                    include_unverified=True)
        hits = response['results']
        row.update(status='evaluated', no_answer=no_answer, timings=response['timings'],
                   candidate_limit_reached=response.get('candidate_limit_reached'),
                   hits=[{k: h[k] for k in ('parent_id', 'document_id', 'chunk_id', 'score')} for h in hits])
        if no_answer:
            row.update(abstained=not hits, threshold=no_answer_threshold)
        else:
            row['metrics'] = parent_metrics(hits, case['qrels'])
            row['gold_parents'] = [{'parent_id': q['parent_id'], 'document_id': q['document_id'],
                                   'grade': q['grade']} for q in case['qrels']]
            relevant_docs = {q['document_id'] for q in case['qrels']}
            row['relevant_documents_retrieved'] = len(relevant_docs & {h['document_id'] for h in hits})
            row['missing_gold_parents_at_10'] = sorted({q['parent_id'] for q in case['qrels']} - {h['parent_id'] for h in hits})
        results.append(row)
    categories = {}
    for category in CATEGORIES:
        rows = [r for r in results if r['category'] == category]
        scored = [r for r in rows if 'metrics' in r]
        categories[category] = {'cases': len(rows), 'scored': len(scored),
                                'blocked': sum(r['status'] == 'blocked' for r in rows),
                                'metrics': {m: statistics.mean(r['metrics'][m] for r in scored) for m in METRICS} if scored else None,
                                'mean_timings_ms': {k: statistics.mean(r['timings'].get(k, 0) for r in scored) for k in ('validation_ms', 'embedding_ms', 'search_ms', 'total_ms')} if scored else None}
    negatives = [r for r in results if r.get('no_answer')]
    return {'created_at': datetime.now(timezone.utc).isoformat(), 'categories': categories,
            'mode': 'mongodb_semantic_retrieval', 'ranking_min_score': -1.0,
            'retrieval_filters': 'Indian corpus across all languages; expected content language is a judgment, not a search filter.',
            'mrr_cutoff': 10, 'label_status': 'authored_provisional_manual_review_needed',
            'limitations': 'Sparse provisional qrels, not exhaustive judgments. Unjudged parents count as nonrelevant. MRR truncated at 10. First query includes lazy model-load cost; no warmup. No-answer threshold is heuristic, not calibrated.',
            'no_answer': {'cases': len(negatives), 'abstained': sum(r['abstained'] for r in negatives), 'threshold': no_answer_threshold},
            'results': results}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, default=Path('data/evaluation-bilingual.json'))
    parser.add_argument('--output', type=Path, default=Path('data/reports/bilingual-evaluation.json'))
    parser.add_argument('--no-answer-threshold', type=float, default=0.7)
    args = parser.parse_args(argv)
    from ip_sakti.config import Settings
    from ip_sakti.embeddings.local import LocalEmbedder, MODEL, REVISION
    from ip_sakti.storage.mongo import create_client
    from ip_sakti.retrieval.search import RetrievalService
    settings = Settings.from_env()
    dataset_bytes = args.dataset.read_bytes()
    dataset = json.loads(dataset_bytes)
    with create_client(settings) as client:
        db = client[settings.database]
        validate_dataset(dataset, db)
        embedder = LocalEmbedder(device=settings.embedding_device, batch_size=settings.embedding_batch_size)
        report = evaluate(dataset, RetrievalService(db, embedder), no_answer_threshold=args.no_answer_threshold)
        report.update(model=MODEL, model_revision=REVISION, dataset=str(args.dataset),
                      dataset_sha256=hashlib.sha256(dataset_bytes).hexdigest())
        report['corpus_snapshot'] = sorted([
            {'document_id': d['_id'], 'generation': d['active_generation'], 'language': d.get('language')}
            for d in db.documents.find({'active_generation': {'$exists': True}},
                                       {'active_generation': 1, 'language': 1})
        ], key=lambda d: d['document_id'])
        report['corpus_languages'] = list(db.documents.aggregate([{'$match': {'active_generation': {'$exists': True}}}, {'$group': {'_id': '$language', 'documents': {'$sum': 1}}}]))
    from ip_sakti.ingestion.prepare import write_json
    write_json(args.output, report)
    print(json.dumps({'output': str(args.output), 'categories': report['categories'], 'no_answer': report['no_answer']}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
