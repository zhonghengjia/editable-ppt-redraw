"""Exercise the production correction route and independently inspect saved text."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

from PIL import Image
from pptx import Presentation

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import reconstruction_pipeline as pipeline
from office_evidence import text_layout


class TextRevision(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.manifest = self.root/'source.json'
        self.revised = self.root/'revised.json'
        self.plan = self.root/'changes.json'
        source = self.root/'reference.png'
        Image.new('RGB', (800, 400), 'white').save(source)
        items = [
            dict(id='title', role='text', module='main', text='Exact title', bbox=[20,20,500,80],
                 representation='native_primitive', construction=dict(kind='text', observation='Source text',
                    frame_bbox=[20,20,70,45], options=dict(font_size_px=32, font='Arial'))),
            dict(id='body', role='text', module='main', text='Footnote', bbox=[20,140,500,40],
                 representation='native_primitive', construction=dict(kind='text', observation='Source note',
                    options=dict(font_size_px=16))),
        ]
        self.data = dict(schema_version=1, mode='faithful', execution_profile='standard',
            source=dict(path=source.name, sha256=pipeline.sha(source), width=800, height=400),
            canvas=dict(width=800,height=400), targets=[dict(format='pptx',path='output.pptx')],
            modules=[dict(id='main',type='illustration',bbox=[0,0,800,400],reading_order=1)],
            connections=[], uncertainties=[], construction=dict(version=1,slide_width_inches=8),
            source_inventory=items)
        pipeline.write_json(self.manifest, self.data)

    def write_plan(self, item, sha=None):
        self.plan.write_text(json.dumps(dict(manifest_sha256=sha or pipeline.sha(self.manifest), items=[item])),
                             encoding='utf-8')

    def test_revision_rebuilds_native_objects_while_preserving_source_observation(self):
        title = self.data['source_inventory'][0]
        self.write_plan(dict(id='title',reason='Widen frame around complete source title',
                             frame_bbox=[20,20,500,80],font_size_px=28))
        before = self.manifest.read_bytes()
        self.assertEqual(pipeline.revise_text(self.manifest,self.plan,self.revised), ['title'])
        self.assertEqual(before, self.manifest.read_bytes())
        expected = copy.deepcopy(self.data)
        recipe = expected['source_inventory'][0]['construction']
        recipe['frame_bbox'] = [20,20,500,80]
        recipe['options']['font_size_px'] = 28
        self.assertEqual(pipeline.read_json(self.revised), expected)
        pipeline.prepare(self.revised,self.root/'prepared')
        pipeline.build(self.root/'prepared',self.root/'build')
        shapes = Presentation(self.root/'build'/'output.pptx').slides[0].shapes
        self.assertEqual([shape.name for shape in shapes], ['title', 'body'])
        self.assertEqual(shapes[0].text, title['text'])
        self.assertAlmostEqual(shapes[0].width.inches, 5)
        self.assertAlmostEqual(shapes[0].text_frame.paragraphs[0].font.size.pt, 20.16, places=2)
        self.assertAlmostEqual(shapes[1].text_frame.paragraphs[0].font.size.pt, 11.52, places=2)
        with self.assertRaises(FileExistsError):
            pipeline.revise_text(self.manifest,self.plan,self.revised)

    def test_invalid_or_stale_changes_never_write_revision(self):
        for overrides in ({'text':'Bad'}, {'frame_bbox':[20,20,900,80]},
                          {'font_size_px':True}, {'font_size_px':32}, {'id':'missing'}):
            with self.subTest(overrides=overrides):
                self.write_plan(dict(id='title',reason='Current observed issue') | overrides)
                with self.assertRaises(ValueError):
                    pipeline.revise_text(self.manifest,self.plan,self.revised)
                self.assertFalse(self.revised.exists())
        self.write_plan(dict(id='title', reason='Widen', frame_bbox=[20,20,500,80]), sha='0'*64)
        with self.assertRaisesRegex(ValueError, 'different manifest hash'):
            pipeline.revise_text(self.manifest,self.plan,self.revised)
        self.assertFalse(self.revised.exists())

    def test_layout_distinguishes_hard_breaks_and_overflow_from_wrapping(self):
        selected = [dict(id='label',output_id='3',text='A\nB')]
        frame = dict(name='label',shape_id=3,box_pt=[10,10,100,30],rotation=0)
        bounds = dict(frame,text='A\rB',line_count=3,box_pt=[10,9,95,33])
        snap = dict(status='BOUND',slides=[dict(index=1,shapes=[frame],text_bounds=[bounds])])
        issues = text_layout(snap, selected)['issues']
        self.assertEqual([v['kind'] for v in issues],
                         ['rendered_line_count_mismatch','text_outside_frame'])
        bounds.update(line_count=2,box_pt=[10,10,90,30])
        self.assertTrue(text_layout(snap, selected)['valid'])
        bounds.pop('line_count')
        self.assertIn('line count',text_layout(snap, selected)['unverified'][0])
        bounds.update(line_count=2,shape_id=4)
        self.assertIn('ID/name',text_layout(snap, selected)['unverified'][0])


if __name__ == '__main__':
    unittest.main()
