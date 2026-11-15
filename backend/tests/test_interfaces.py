import io
import unittest
from contextlib import redirect_stdout, redirect_stderr
from threading import Lock
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pymongo.errors import OperationFailure

from ip_sakti.api.search import router
from ip_sakti.cli import main


class SearchAPITests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(router)
        app.state.retrieval = MagicMock()
        app.state.retrieval.retrieve.return_value = {"results": [], "note": "test"}
        app.state.retrieval_lock = Lock()
        self.app = app
        self.client = TestClient(app)

    def test_passes_filters_and_reuses_service(self):
        response = self.client.post('/api/v1/search', json={
            'query': 'डिजाइन पंजीकरण', 'top_k': 3, 'min_score': 0.8,
            'filters': {'language': 'hi'}, 'include_unverified': True})
        self.assertEqual(response.status_code, 200)
        self.app.state.retrieval.retrieve.assert_called_once_with(
            'डिजाइन पंजीकरण', top_k=3, min_score=0.8,
            filters={'language': 'hi'}, include_unverified=True)

    def test_invalid_requests_do_not_call_retrieval(self):
        for payload in ({'query': ''}, {'query': 'q', 'top_k': True},
                        {'query': 'q', 'top_k': 21}, {'query': 'q', 'extra': 1},
                        {'query': 'q', 'filters': {'unknown': 'x'}},
                        {'query': 'q', 'filters': {'language': 'fr'}}):
            with self.subTest(payload=payload):
                self.assertEqual(self.client.post('/api/v1/search', json=payload).status_code, 422)
        self.app.state.retrieval.retrieve.assert_not_called()

    def test_operational_errors_redact_details_and_release_lock(self):
        for error in (OperationFailure('secret connection detail'), RuntimeError('private path')):
            self.app.state.retrieval.retrieve.side_effect = error
            response = self.client.post('/api/v1/search', json={'query': 'q'})
            self.assertEqual(response.status_code, 503)
            self.assertNotIn(str(error), response.text)
            self.assertFalse(self.app.state.retrieval_lock.locked())
        self.app.state.retrieval.retrieve.side_effect = ValueError('Question exceeds token limit')
        self.assertEqual(self.client.post('/api/v1/search', json={'query': 'q'}).status_code, 422)

    def test_busy_request_does_not_unlock_other_request(self):
        self.app.state.retrieval_lock.acquire()
        response = self.client.post('/api/v1/search', json={'query': 'q'})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.headers['Retry-After'], '1')
        self.assertTrue(self.app.state.retrieval_lock.locked())
        self.app.state.retrieval_lock.release()


class CLITests(unittest.TestCase):
    def test_query_json_and_human_output(self):
        result = {'results': [], 'reason': 'No eligible sources', 'note': 'Scores are cosine'}
        for json_output in (False, True):
            output = io.StringIO()
            with patch('ip_sakti.cli.Settings.from_env', return_value=SimpleNamespace(
                    embedding_device='cpu', embedding_model='intfloat/multilingual-e5-small',
                    embedding_revision='614241f622f53c4eeff9890bdc4f31cfecc418b3',
                    embedding_batch_size=16, database='test')), \
                 patch('ip_sakti.cli.create_client'), \
                 patch('ip_sakti.retrieval.search.RetrievalService') as service, redirect_stdout(output):
                service.return_value.retrieve.return_value = result
                argv = ['query', 'नमस्ते', '--language', 'hi'] + (['--json'] if json_output else [])
                self.assertEqual(main(argv), 0)
                self.assertIn('No eligible sources', output.getvalue())
                self.assertEqual(service.return_value.retrieve.call_args.kwargs['filters'], {'language': 'hi'})
                if json_output:
                    import json
                    self.assertEqual(json.loads(output.getvalue()), result)

    def test_invalid_environment_exits_cleanly(self):
        output = io.StringIO()
        with patch('ip_sakti.cli.Settings.from_env', side_effect=ValueError('invalid batch size')), redirect_stderr(output):
            self.assertEqual(main(['status']), 1)
        self.assertIn('invalid batch size', output.getvalue())


if __name__ == '__main__':
    unittest.main()
