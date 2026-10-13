import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('classification_worker', Path(__file__).resolve().parents[2] / 'scripts/kaleu-worker.py')
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)


class WorkerTests(unittest.TestCase):
    def test_schema_output_and_minimal_inputs(self):
        job = {'items': [{'fingerprint': 'a'*64, 'description': 'Reembolso de compra', 'allowed_categories': ['Reembolsos']}]}
        def run(command, **kwargs):
            self.assertIn('--output-schema', command)
            self.assertEqual(command[command.index('--sandbox')+1], 'read-only')
            schema = json.loads(Path(command[command.index('--output-schema')+1]).read_text())
            self.assertFalse(schema['additionalProperties'])
            self.assertNotIn('PERSONALBUDGET_KALEU_TOKEN', kwargs['env'])
            answer = {'decisions': [{'fingerprint': 'a'*64, 'category': 'Reembolsos', 'confidence': .95, 'reason': 'Reembolso explícito'}]}
            Path(command[command.index('--output-last-message')+1]).write_text(json.dumps(answer))
            return type('Result', (), {'returncode': 0})()
        with patch.object(worker.client, 'config', return_value={'codex': 'codex', 'codex_home': '/tmp/test-home'}), patch.object(worker.subprocess, 'run', side_effect=run):
            self.assertEqual(worker.execute_classification(job)[0]['category'], 'Reembolsos')

    def test_failure_is_reported_without_fabricated_result(self):
        with patch.object(worker.client, 'request', side_effect=[{'job': {'id':'batch', 'lease':'secret'}}, {'ok':True}]) as request, patch.object(worker, 'execute_classification', side_effect=RuntimeError('failure')):
            self.assertTrue(worker.process_classification())
            completion = request.call_args.args[2]
            self.assertTrue(completion['failed'])
            self.assertEqual(completion['decisions'], [])
