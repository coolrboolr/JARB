import os
import sys
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("OPENAI_KEY", "test-key")

from api import app, handle_unexpected_error  # noqa: E402


class ApiRoutesTests(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_create_tool_missing_fields(self):
        response = self.client.post('/api/create_tool', json={})
        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertFalse(payload["success"])
        self.assertEqual(payload["error"]["code"], "BAD_REQUEST")

    def test_create_tool_success(self):
        with patch('api.jarb_core.create_tool') as mock_create:
            response = self.client.post('/api/create_tool', json={
                'name': 'foo',
                'description': 'does things'
            })
        self.assertEqual(response.status_code, 201)
        payload = response.get_json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["data"], {"message": "Tool created"})
        mock_create.assert_called_once_with('foo', 'does things')

    def test_use_tool_success(self):
        with patch('api.jarb_core.use_tool') as mock_use:
            mock_use.return_value = 'ok'
            response = self.client.post('/api/use_tool', json={
                'tool_name': 'foo',
                'params': {'x': 1}
            })
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["data"], {'result': 'ok'})
        mock_use.assert_called_once_with('foo', x=1)

    def test_use_tool_not_found(self):
        with patch('api.jarb_core.use_tool') as mock_use:
            mock_use.side_effect = FileNotFoundError()
            response = self.client.post('/api/use_tool', json={'tool_name': 'missing'})
        self.assertEqual(response.status_code, 404)
        payload = response.get_json()
        self.assertFalse(payload["success"])
        self.assertEqual(payload["error"]["code"], 'NOT_FOUND')

    def test_list_tools_success(self):
        with patch('api.jarb_core.list_tools') as mock_list:
            mock_list.return_value = ['a', 'b']
            response = self.client.get('/api/list_tools')
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["data"], {'tools': ['a', 'b']})

    def test_list_tools_failure(self):
        with patch('api.jarb_core.list_tools') as mock_list:
            mock_list.side_effect = RuntimeError('boom')
            response = self.client.get('/api/list_tools')
        self.assertEqual(response.status_code, 500)
        payload = response.get_json()
        self.assertEqual(payload["error"]["code"], 'LIST_FAILED')

    def test_tool_parameters_success(self):
        description = {
            'name': 'foo',
            'docstring': 'Foo doc',
            'parameters': [{
                'name': 'x',
                'kind': 'POSITIONAL_OR_KEYWORD',
                'default': None,
                'required': True,
                'annotation': {'type': 'int', 'raw': 'int'},
            }],
            'return_annotation': None,
        }
        with patch('api.jarb_core.describe_tool') as mock_describe:
            mock_describe.return_value = description
            response = self.client.get('/api/tool_parameters/foo')
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["data"], {
            'name': description['name'],
            'parameters': description['parameters'],
            'docstring': description['docstring'],
            'return_annotation': description['return_annotation'],
        })
        first_param = payload["data"]["parameters"][0]
        self.assertIn('required', first_param)
        self.assertIn('annotation', first_param)
        self.assertIn('type', first_param['annotation'])

    def test_tool_parameters_not_found(self):
        with patch('api.jarb_core.describe_tool') as mock_describe:
            mock_describe.side_effect = FileNotFoundError()
            response = self.client.get('/api/tool_parameters/foo')
        self.assertEqual(response.status_code, 404)
        payload = response.get_json()
        self.assertEqual(payload["error"]["code"], 'NOT_FOUND')

    def test_tools_catalog_success(self):
        catalog = [{
            'name': 'sample',
            'docstring': 'Sample tool',
            'parameters': [{
                'name': 'count',
                'kind': 'POSITIONAL_OR_KEYWORD',
                'default': None,
                'required': True,
                'annotation': {'type': 'int', 'raw': 'int'},
            }],
            'return_annotation': None,
        }]
        with patch('api.jarb_core.get_tool_catalog') as mock_catalog:
            mock_catalog.return_value = catalog
            response = self.client.get('/api/tools')
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["data"], {'tools': catalog})
        first_tool = payload["data"]["tools"][0]
        first_param = first_tool['parameters'][0]
        self.assertIn('required', first_param)
        self.assertIn('annotation', first_param)
        self.assertEqual(first_param['annotation']['type'], 'int')

    def test_tools_catalog_failure(self):
        with patch('api.jarb_core.get_tool_catalog') as mock_catalog:
            mock_catalog.side_effect = Exception('boom')
            response = self.client.get('/api/tools')
        self.assertEqual(response.status_code, 500)
        payload = response.get_json()
        self.assertEqual(payload["error"]["code"], 'CATALOG_FAILED')

    def test_tool_runs_success(self):
        runs = [{
            'run_id': 'abc',
            'tool_name': 'foo',
            'status': 'success',
            'duration_ms': 10,
            'finished_at': '2025-11-13T00:00:00Z',
            'started_at': '2025-11-13T00:00:00Z',
            'error': None,
            'params': {'a': 1},
            'result_summary': 'ok',
        }]
        with patch('api.jarb_core.get_tool_runs') as mock_runs:
            mock_runs.return_value = runs
            response = self.client.get('/api/tool_runs/foo?limit=5')
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["data"], {'runs': runs})
        mock_runs.assert_called_once_with('foo', limit=5)

    def test_tool_runs_not_found(self):
        with patch('api.jarb_core.get_tool_runs') as mock_runs:
            mock_runs.side_effect = FileNotFoundError()
            response = self.client.get('/api/tool_runs/missing')
        self.assertEqual(response.status_code, 404)
        payload = response.get_json()
        self.assertEqual(payload["error"]["code"], 'NOT_FOUND')

    def test_tool_runs_failure(self):
        with patch('api.jarb_core.get_tool_runs') as mock_runs:
            mock_runs.side_effect = Exception('boom')
            response = self.client.get('/api/tool_runs/foo')
        self.assertEqual(response.status_code, 500)
        payload = response.get_json()
        self.assertEqual(payload["error"]["code"], 'RUNS_FAILED')

    def test_create_flow_success(self):
        with patch('api.jarb_core.create_flow') as mock_create_flow:
            response = self.client.post('/api/create_flow', json={'flow': {'name': 'demo', 'steps': [{'tool': 'foo'}]}})
        self.assertEqual(response.status_code, 201)
        payload = response.get_json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["data"], {"message": "Flow created"})
        mock_create_flow.assert_called_once()

    def test_create_flow_validation_error(self):
        response = self.client.post('/api/create_flow', json={'flow': 'nope'})
        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertEqual(payload["error"]["code"], 'BAD_REQUEST')

    def test_run_flow_success(self):
        with patch('api.jarb_core.run_flow') as mock_run:
            mock_run.return_value = {'ok': True}
            response = self.client.post('/api/run_flow', json={'flow_name': 'demo', 'inputs': {'x': 1}})
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["data"], {'result': {'ok': True}})
        mock_run.assert_called_once_with('demo', {'x': 1})

    def test_run_flow_not_found(self):
        with patch('api.jarb_core.run_flow') as mock_run:
            mock_run.side_effect = FileNotFoundError()
            response = self.client.post('/api/run_flow', json={'flow_name': 'missing', 'inputs': {}})
        self.assertEqual(response.status_code, 404)
        payload = response.get_json()
        self.assertEqual(payload["error"]["code"], 'NOT_FOUND')

    def test_run_flow_bad_inputs(self):
        response = self.client.post('/api/run_flow', json={'flow_name': 'demo', 'inputs': 'oops'})
        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertEqual(payload["error"]["code"], 'BAD_REQUEST')

    def test_flows_catalog_success(self):
        with patch('api.jarb_core.list_flows') as mock_list:
            mock_list.return_value = ['one']
            response = self.client.get('/api/flows')
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["data"], {'flows': ['one']})

    def test_flow_detail_success(self):
        flow = {'name': 'demo', 'steps': []}
        with patch('api.jarb_core.describe_flow') as mock_describe:
            mock_describe.return_value = flow
            response = self.client.get('/api/flow/demo')
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["data"], {'flow': flow})

    def test_flow_detail_not_found(self):
        with patch('api.jarb_core.describe_flow') as mock_describe:
            mock_describe.side_effect = FileNotFoundError()
            response = self.client.get('/api/flow/missing')
        self.assertEqual(response.status_code, 404)
        payload = response.get_json()
        self.assertEqual(payload["error"]["code"], 'NOT_FOUND')

    def test_flow_runs_success(self):
        runs = [{'flow_run_id': '1', 'status': 'success'}]
        with patch('api.jarb_core.get_flow_runs') as mock_runs:
            mock_runs.return_value = runs
            response = self.client.get('/api/flow_runs/demo?limit=2')
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["data"], {'runs': runs})
        mock_runs.assert_called_once_with('demo', limit=2)

    def test_flow_runs_not_found(self):
        with patch('api.jarb_core.get_flow_runs') as mock_runs:
            mock_runs.side_effect = FileNotFoundError()
            response = self.client.get('/api/flow_runs/missing')
        self.assertEqual(response.status_code, 404)
        payload = response.get_json()
        self.assertEqual(payload["error"]["code"], 'NOT_FOUND')

    def test_global_error_handler(self):
        with app.test_request_context('/api/create_tool'):
            response, status = handle_unexpected_error(RuntimeError('explode'))
        self.assertEqual(status, 500)
        payload = response.get_json()
        self.assertFalse(payload["success"])
        self.assertEqual(payload["error"], {
            'code': 'INTERNAL_ERROR',
            'message': 'An unexpected error occurred.',
        })


if __name__ == '__main__':
    unittest.main()
