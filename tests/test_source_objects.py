import copy
import io
import importlib.util
import json
import os
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from source_objects import extract_source_object, _annotations
from raster_components import digest


class SourceObjects(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'source.png'
        im = Image.new('RGB', (180, 120), 'white')
        d = ImageDraw.Draw(im)
        d.ellipse((20, 25, 125, 95), fill=(30, 100, 170))
        d.ellipse((50, 50, 70, 70), fill='white')  # true hole
        d.line((110, 42, 142, 18), fill=(30, 100, 170), width=2)
        d.rectangle((150, 80, 162, 87), fill=(30, 100, 170))  # disconnected glyph/confounder
        im.save(self.path)
        self.plan = dict(source_sha256=digest(self.path.read_bytes()), context_bbox=[5, 5, 170, 105],
                         foreground=[[90, 55]], background=[], method='selector',
                         reserved_regions=[[148, 78, 20, 14]], observation='Synthetic branched ring and separate same-color glyph',
                         selector=dict(rgb=[[0, 80], [70, 130], [130, 210]], differences=[], observation='Blue object support'))

    def test_bounds_follow_full_object_not_a_seed_crop(self):
        data, report = extract_source_object(self.path, self.plan)
        x, y, w, h = report['source_bbox']
        self.assertLessEqual(x, 20)
        self.assertGreaterEqual(x+w, 143)
        self.assertLessEqual(y, 18)
        self.assertEqual(report['issues'], [])
        out = np.array(Image.open(io.BytesIO(data['rgba'])))
        src = np.array(Image.open(self.path))[y:y+h, x:x+w]
        visible = out[:, :, 3] > 0
        np.testing.assert_array_equal(out[:, :, :3][visible], src[visible])
        self.assertEqual(out[60-y, 60-x, 3], 0)
        self.assertEqual(report['status'], 'CANDIDATE')

    def test_touching_context_reported_not_silently_trimmed(self):
        p = copy.deepcopy(self.plan)
        p['context_bbox'] = [50, 5, 125, 105]
        _, r = extract_source_object(self.path, p)
        self.assertTrue(any('context edge' in x for x in r['issues']))

    def test_reserved_content_is_not_erased(self):
        p = copy.deepcopy(self.plan)
        p['reserved_regions'] = [[85, 50, 12, 12]]
        data, r = extract_source_object(self.path, p)
        self.assertGreater(r['reserved_overlaps'][0]['foreground_pixels'], 0)
        mask = np.array(Image.open(io.BytesIO(data['context_mask'])))
        self.assertEqual(mask[55-5, 90-5], 255)

    def test_each_disconnected_part_requires_seed(self):
        p = copy.deepcopy(self.plan)
        p['foreground'].append([155, 83])
        _, r = extract_source_object(self.path, p)
        self.assertEqual(len(r['selected_regions']), 2)
        self.assertTrue(r['reserved_overlaps'])

    def test_hash_seed_conflict_and_bounds(self):
        for change in ({'source_sha256': '0'*64}, {'foreground': [[1, 1]]},
                       {'foreground': [[90, 55]], 'background': [[90, 55]]},
                       {'context_bbox': [-1, 0, 90, 90]}, {'foreground': [[10, 10]]},
                       {'background': [[91, 55]]}, {'reserved_regions': [[170, 100, 30, 30]]}):
            p = dict(self.plan, **change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                extract_source_object(self.path, p)

    def test_existing_alpha_not_overwritten(self):
        im = Image.open(self.path).convert('RGBA')
        im.putpixel((60, 60), (255, 255, 255, 0))
        im.save(self.path)
        self.plan['source_sha256'] = digest(self.path.read_bytes())
        with self.assertRaisesRegex(ValueError, 'preserve existing alpha'):
            extract_source_object(self.path, self.plan)

    def test_no_model_or_dependency_fallback(self):
        p = copy.deepcopy(self.plan)
        p['method'] = 'grabcut'
        p.pop('selector')
        p['background'] = [[6, 6]]
        with patch.dict(sys.modules, {'cv2': None}), self.assertRaisesRegex(RuntimeError, 'no automatic'):
            extract_source_object(self.path, p)


class SourceAnnotations(unittest.TestCase):
    def mark(self, label='foreground', **kw):
        return dict(kind='stroke', label=label, width=1, points=[[12, 13], [24, 13]],
                    observation='Synthetic observed thin line', **kw)

    def test_source_origin_and_disconnected_hard_marks(self):
        a = self.mark()
        b = dict(a, points=[[12, 24], [24, 24]])
        labels = _annotations([a, b], (10, 10, 20, 20), [(2, 2)], [(0, 0)])
        self.assertTrue((labels[3, 2:15] == 1).all())
        self.assertTrue((labels[14, 2:15] == 1).all())
        self.assertEqual(labels[8, 8], 255)
        self.assertEqual(labels[0, 0], 0)

    def test_four_classes_and_consistent_hard_priority(self):
        probable = self.mark('probable_foreground')
        hard = dict(probable, label='foreground', points=[[18, 13]])
        region = dict(kind='polygon', label='probable_background',
            points=[[12, 19], [24, 19], [24, 25], [12, 25]], observation='Visible background')
        first = _annotations([probable, hard, region], (10, 10, 20, 20), [], [])
        second = _annotations([region, hard, probable], (10, 10, 20, 20), [], [])
        np.testing.assert_array_equal(first, second)
        self.assertEqual(first[3, 8], 1)
        self.assertEqual(first[3, 2], 3)
        self.assertEqual(first[12, 8], 2)

    def test_conflicting_neighbor_not_resolved_by_order(self):
        fg = self.mark()
        bg = dict(fg, label='background')
        for marks in ([fg, bg], [bg, fg]):
            with self.assertRaisesRegex(ValueError, 'conflicting'):
                _annotations(marks, (10, 10, 20, 20), [], [])
        with self.assertRaisesRegex(ValueError, 'conflicting'):
            _annotations([fg], (10, 10, 20, 20), [], [(2, 3)])

    def test_invalid_or_clipped_annotations_fail(self):
        for change in (dict(width=2), dict(width=True), dict(points=[[9, 13]]),
                       dict(points=[[10, 10]], width=3), dict(label='erase'),
                       dict(observation=''), dict(extra=True), dict(kind='box'),
                       dict(points=[])):
            with self.subTest(change=change), self.assertRaises(ValueError):
                _annotations([dict(self.mark(), **change)], (10, 10, 20, 20), [], [])
        for points in ([[12, 12]], [[12, 12], [12, 12], [12, 12]]):
            with self.assertRaises(ValueError):
                _annotations([dict(kind='polygon', label='foreground', points=points,
                    observation='Degenerate polygon')], (10, 10, 20, 20), [], [])

    def test_real_grabcut_retains_marked_pale_line_and_excludes_neighbor(self):
        runtime = os.environ.get('EDITABLE_PPT_EXTRACT_PYTHON')
        if not runtime and importlib.util.find_spec('cv2') is None:
            self.skipTest('Optional installed OpenCV runtime not supplied')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'source.png'
            im = Image.new('RGB', (100, 70), '#EDF2F8')
            draw = ImageDraw.Draw(im)
            draw.ellipse((15, 10, 55, 45), fill='#407CAA')
            draw.line((12, 57, 78, 57), fill='#DBE0E6', width=1)
            draw.rectangle((70, 20, 84, 36), fill='#407CAA')
            im.save(source)
            plan = dict(source_sha256=digest(source.read_bytes()), context_bbox=[0, 0, 100, 70],
                foreground=[[30, 25]], background=[[2, 2]], method='grabcut', reserved_regions=[],
                observation='Blue body plus a disconnected pale line; same-color neighbor is separate',
                annotations=[dict(kind='stroke', label='foreground', points=[[12, 57], [78, 57]], width=1,
                                  observation='Pale one-pixel line visible across original source'),
                             dict(kind='polygon', label='background', points=[[69, 19], [85, 19], [85, 37], [69, 37]],
                                  observation='Separate blue neighbor, not part of this object')])
            (root / 'plan.json').write_text(json.dumps(plan))
            before = source.read_bytes()
            result = subprocess.run([runtime or sys.executable, '-X', 'utf8', '-B',
                str(Path(__file__).resolve().parents[1] / 'scripts/source_objects.py'),
                str(source), str(root / 'plan.json'), str(root / 'out')], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            mask = np.asarray(Image.open(root / 'out/context_mask.png'))
            self.assertTrue((mask[57, 12:79] == 255).all())
            self.assertFalse(mask[19:38, 69:86].any())
            report = json.loads((root / 'out/candidate.json').read_text())
            self.assertGreaterEqual(report['hard_foreground_pixels'], 68)
            self.assertEqual(report['annotation_count'], 2)
            self.assertEqual(report['status'], 'CANDIDATE')
            self.assertFalse(report['hidden_content_generated'])
            x, y, w, h = report['source_bbox']
            rgba = np.asarray(Image.open(root / 'out/rgba.png'))
            np.testing.assert_array_equal(rgba[:, :, :3], np.asarray(im)[y:y+h, x:x+w])
            self.assertEqual(before, source.read_bytes())
            self.assertTrue((root / 'out/annotations.png').exists())
            initial = np.asarray(Image.open(root / 'out/initial_labels.png'))
            self.assertTrue((initial[57, 12:79] == 1).all())
            self.assertTrue((initial[20:37, 70:85] == 0).all())


if __name__ == '__main__':
    unittest.main()
