"""The production command supplies advice without requiring the build environment."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from PIL import Image, ImageDraw

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'reconstruction_pipeline.py'


class TextMeasurementCLITests(unittest.TestCase):
    def test_source_bound_advice_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'source.png'
            image = Image.new('RGB', (220, 80), 'white')
            ImageDraw.Draw(image).text((15, 20), 'Cell 24 h', fill='black')
            image.save(source)
            manifest = root / 'manifest.json'
            manifest.write_text(json.dumps(dict(
                source=dict(path=source.name, sha256=hashlib.sha256(source.read_bytes()).hexdigest(), width=220, height=80),
                source_inventory=[dict(id='label', role='text', text='Cell 24 h', bbox=[0,0,220,80])])), encoding='utf-8')
            original = manifest.read_bytes()
            output = root / 'measurements'
            cmd = [sys.executable, '-X', 'utf8', '-B', str(SCRIPT), 'measure-text', str(manifest), str(output), '--item', 'label']
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['status'], 'ADVISORY')
            report_bytes = (output/'measurements.json').read_bytes()
            self.assertEqual(json.loads(report_bytes)['items'][0]['text'], 'Cell 24 h')
            self.assertEqual(manifest.read_bytes(), original)
            repeated = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(repeated.returncode, 1)
            self.assertEqual((output/'measurements.json').read_bytes(), report_bytes)
            image.putpixel((0,0), (255,0,0))
            image.save(source)
            cmd[7] = str(root/'stale')
            stale = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(stale.returncode, 1)
            self.assertIn('hash', json.loads(stale.stderr)['error'])
            self.assertFalse((root/'stale').exists())


if __name__ == '__main__':
    unittest.main()
