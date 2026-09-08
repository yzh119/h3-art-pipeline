"""Check paid-task recovery without network access or account credits."""
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import gen_mesh


class MeshResumeTests(unittest.TestCase):
    def test_resume_restores_parameters_without_post(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);image=root/'image.png';image.write_bytes(b'source');out=root/'mesh'
            record={'task_id':'existing-task','source_sha256':hashlib.sha256(image.read_bytes()).hexdigest(),'parameters':{'ai_model':'meshy-7','should_remesh':False}}
            out.with_suffix('.pending.json').write_text(json.dumps(record))
            task={'model_urls':{'glb':'https://example.invalid/model'},'consumed_credits':30}
            with patch.dict('os.environ',{'MESHY_API_KEY':'test-only'}),patch.object(gen_mesh,'request',side_effect=AssertionError('Unexpected paid request')),patch.object(gen_mesh,'poll',return_value=task) as poll,patch.object(gen_mesh.urllib.request,'urlopen',return_value=io.BytesIO(b'model')):
                self.assertEqual(gen_mesh.main([str(image),'--out',str(out),'--resume']),0)
            poll.assert_called_once_with('existing-task','test-only')
            self.assertEqual(json.loads(out.with_suffix('.json').read_text())['parameters'],record['parameters'])
            self.assertEqual(out.with_suffix('.glb').read_bytes(),b'model')

    def test_pending_task_rejects_second_submission(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);image=root/'image.png';image.write_bytes(b'source');out=root/'mesh';out.with_suffix('.pending.json').write_text('{}')
            with patch.dict('os.environ',{'MESHY_API_KEY':'test-only'}),patch.object(gen_mesh,'request',side_effect=AssertionError('Unexpected paid request')):
                with self.assertRaises(SystemExit) as error:gen_mesh.main([str(image),'--out',str(out)])
                self.assertEqual(error.exception.code,2)

    def test_changed_resume_image_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);image=root/'image.png';image.write_bytes(b'changed');out=root/'mesh'
            out.with_suffix('.pending.json').write_text(json.dumps({'task_id':'existing','source_sha256':'old','parameters':{}}))
            with patch.dict('os.environ',{'MESHY_API_KEY':'test-only'}),patch.object(gen_mesh,'poll',side_effect=AssertionError('Unexpected poll')):
                with self.assertRaises(SystemExit) as error:gen_mesh.main([str(image),'--out',str(out),'--resume'])
                self.assertEqual(error.exception.code,2)

if __name__=='__main__':unittest.main()
