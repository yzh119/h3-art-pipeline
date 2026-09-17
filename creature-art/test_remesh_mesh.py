"""Prevent duplicate paid submissions when recovering a remesh download."""
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import remesh_mesh


class RemeshRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.meta = self.root / 'source.json'
        self.meta.write_text(json.dumps({'task_id': 'source'}))
        self.out = self.root / 'remeshed'
        self.args = ['--input-meta', str(self.meta), '--out', str(self.out)]
        self.record = {'task_id': 'existing', 'parameters': {'input_task_id': 'source',
                       'target_formats': ['glb'], 'topology': 'triangle', 'target_polycount': 100000}}
        self.out.with_suffix('.pending.json').write_text(json.dumps(self.record))
        self.env = patch.dict('os.environ', {'MESHY_API_KEY': 'test-only'})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_resume_does_not_post_and_restores_parameters(self):
        task = {'status': 'SUCCEEDED', 'model_urls': {'glb': 'https://example.invalid/model'}}
        with patch.object(remesh_mesh.gen_mesh, 'request', side_effect=AssertionError('Paid request')), \
             patch.object(remesh_mesh.gen_mesh, 'poll', return_value=task) as poll, \
             patch.object(remesh_mesh.urllib.request, 'urlopen', return_value=io.BytesIO(b'mesh')):
            self.assertEqual(remesh_mesh.main(self.args + ['--resume']), 0)
        poll.assert_called_once_with('existing', 'test-only')
        result = json.loads(self.out.with_suffix('.json').read_text())
        self.assertEqual(result['parameters'], self.record['parameters'])
        self.assertEqual(self.out.with_suffix('.glb').read_bytes(), b'mesh')

    def test_pending_rejects_duplicate_submission(self):
        with patch.object(remesh_mesh.gen_mesh, 'request', side_effect=AssertionError('Paid request')):
            with self.assertRaises(SystemExit):
                remesh_mesh.main(self.args)

    def test_changed_source_rejects_resume(self):
        self.meta.write_text(json.dumps({'task_id': 'different'}))
        with patch.object(remesh_mesh.gen_mesh, 'poll', side_effect=AssertionError('Wrong task')):
            with self.assertRaises(SystemExit):
                remesh_mesh.main(self.args + ['--resume'])


if __name__ == '__main__':
    unittest.main()
