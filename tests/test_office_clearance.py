"""Synthetic evidence tests; these do not claim an actual Office render."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

from PIL import Image
from pptx import Presentation
from pptx.util import Inches

S=Path(__file__).resolve().parents[1]/'scripts';sys.path.insert(0,str(S))
import text_clearance as mod


class OfficeClearance(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.deck=self.root/'case.pptx';p=Presentation();p.slide_width=Inches(10);p.slide_height=Inches(5)
        s=p.slides.add_slide(p.slide_layouts[6])
        for name,x in [('A',1),('B',2)]:
            t=s.shapes.add_textbox(Inches(x),Inches(1),Inches(2),Inches(1));t.name=name;t.text=name
        p.save(self.deck)
        render=self.root/'slide.png';Image.new('RGB',(200,100),'white').save(render)
        self.data={'schema_version':1,'status':'PASS','source_unchanged':True,'artifact_sha256':hashlib.sha256(self.deck.read_bytes()).hexdigest(),
            'renderer':'Microsoft PowerPoint synthetic unit-test stub','slide_width_pt':720,'slide_height_pt':360,
            'slides':[{'index':1,'render_path':'slide.png','render_sha256':hashlib.sha256(render.read_bytes()).hexdigest(),
                'text_bounds':[{'name':n,'text':n,'box_pt':[x*7.2,72,8*7.2,72],'rotation':0} for n,x in [('A',10),('B',31)]]}]}
        self.evidence=self.root/'office-evidence.json';self.save()
        self.manifest={'canvas':{'width':100,'height':50},'text_clearance':{'label_names':['A','B'],'obstacle_names':[],'min_gap_px':0}}
    def tearDown(self):self.tmp.cleanup()
    def save(self):self.evidence.write_text(json.dumps(self.data),encoding='utf-8')
    def run_audit(self):return mod.audit(self.deck,self.manifest,self.evidence)
    def test_text_only_slide_is_checked(self):
        r=mod.audit(self.deck,self.manifest);self.assertEqual(r['label_count'],2);self.assertEqual(len(r['collisions']),1)
    def test_layout_only_remains_failure(self):
        r=self.run_audit();self.assertFalse(r['valid']);self.assertEqual(r['collisions'][0]['diagnostic'],'layout_box_only')
        self.assertEqual(r['collisions'][0]['slide'],1)
    def test_actual_bounds_overlap(self):
        self.data['slides'][0]['text_bounds'][1]['box_pt'][0]=14*7.2;self.save()
        self.assertEqual(self.run_audit()['collisions'][0]['diagnostic'],'actual_text_bounds_overlap')
        self.assertEqual(self.run_audit()['collisions'][0]['candidate_sources'],['xml_frame','office_text_bounds'])
        self.assertEqual(len(self.run_audit()['collisions']),1)
    def separate_frames(self):
        p=Presentation(self.deck);p.slides[0].shapes[1].left=Inches(4);p.save(self.deck)
        self.data['artifact_sha256']=hashlib.sha256(self.deck.read_bytes()).hexdigest()
    def test_overflow_adds_new_candidate_without_frame_intersection(self):
        self.separate_frames()
        self.data['slides'][0]['text_bounds'][0]['box_pt']=[72,72,250,72]
        self.data['slides'][0]['text_bounds'][1]['box_pt']=[288,72,30,72];self.save()
        self.assertEqual(mod.audit(self.deck,self.manifest)['collisions'],[])
        report=self.run_audit();self.assertFalse(report['valid']);self.assertEqual(len(report['collisions']),1)
        self.assertEqual(report['collisions'][0]['candidate_sources'],['office_text_bounds'])
    def test_disjoint_frames_and_actual_bounds_are_safe(self):
        self.separate_frames();self.save()
        report=self.run_audit();self.assertTrue(report['valid']);self.assertFalse(report['unverified'])
    def test_missing_actual_bounds_without_frame_candidates_is_unverified(self):
        self.separate_frames();self.data['slides'][0]['text_bounds'].pop();self.save()
        report=self.run_audit();self.assertFalse(report['collisions']);self.assertTrue(report['unverified'])
    def test_identical_actual_coordinates_on_different_slides_do_not_collide(self):
        p=Presentation(self.deck);second=p.slides.add_slide(p.slide_layouts[6])
        element=p.slides[0].shapes[1]._element;element.getparent().remove(element);second.shapes._spTree.append(element)
        p.save(self.deck);self.data['artifact_sha256']=hashlib.sha256(self.deck.read_bytes()).hexdigest()
        first=self.data['slides'][0];other=dict(first,index=2,text_bounds=[first['text_bounds'][1]])
        first['text_bounds']=first['text_bounds'][:1];other['text_bounds'][0]['box_pt']=list(first['text_bounds'][0]['box_pt'])
        self.data['slides'].append(other);self.save()
        report=self.run_audit();self.assertFalse(report['collisions']);self.assertFalse(report['unverified'])
    def test_text_path_overflow_adds_new_candidate(self):
        p=Presentation(self.deck)
        builder=p.slides[0].shapes.build_freeform(300,60,scale=12700)
        builder.add_line_segments([(301,160)],close=False)
        builder.convert_to_shape().name='path';p.save(self.deck)
        self.data['artifact_sha256']=hashlib.sha256(self.deck.read_bytes()).hexdigest()
        self.data['slides'][0]['text_bounds'][0]['box_pt']=[72,72,360,72];self.save()
        self.manifest['text_clearance'].update(label_names=['A'],obstacle_names=['path'])
        self.assertFalse(mod.audit(self.deck,self.manifest)['collisions'])
        report=self.run_audit();self.assertEqual(len(report['collisions']),1)
        self.assertEqual(report['collisions'][0]['candidate_sources'],['office_text_bounds'])
    def test_overflow_preview_covers_actual_and_both_frame_extents(self):
        self.separate_frames()
        self.data['slides'][0]['text_bounds'][0]['box_pt']=[72,72,400,72]
        self.data['slides'][0]['text_bounds'][1]['box_pt']=[288,72,30,72];self.save()
        out=self.root/'overflow.html';mod.write_review(self.run_audit(),self.deck,self.manifest,self.evidence,out)
        import re
        view=re.search(r'viewBox="([^"]+)"',out.read_text()).group(1)
        left,top,width,height=map(float,view.split())
        self.assertLessEqual(left,10);self.assertGreaterEqual(left+width,472/7.2)
        self.assertIn('office_text_bounds',out.read_text())
    def test_stale_artifact(self):
        self.data['artifact_sha256']='0'*64;self.save();r=self.run_audit()
        self.assertEqual(r['office_evidence']['status'],'NOT_VERIFIED');self.assertTrue(r['unverified'])
        self.assertEqual(r['collisions'][0]['diagnostic'],'office_bounds_unavailable')
    def test_stale_render(self):
        self.data['slides'][0]['render_sha256']='0'*64;self.save();self.assertTrue(self.run_audit()['unverified'])
    def test_failed_office_evidence_not_promoted(self):
        self.data['status']='FAIL';self.save();self.assertTrue(self.run_audit()['unverified'])
    def test_wrong_dimensions(self):
        self.data['slide_width_pt']=800;self.save();self.assertTrue(self.run_audit()['unverified'])
    def test_office16_quantization_requires_exact_predicted_grid(self):
        p=Presentation(self.deck);p.slide_height=int(866.16*12700);p.save(self.deck)
        self.data.update(renderer='Microsoft PowerPoint 16.0',slide_height_pt=866.125,
            artifact_sha256=hashlib.sha256(self.deck.read_bytes()).hexdigest())
        render=self.root/'slide.png';Image.new('RGB',(720,866),'white').save(render)
        self.data['slides'][0]['render_sha256']=hashlib.sha256(render.read_bytes()).hexdigest();self.save()
        self.assertEqual(self.run_audit()['office_evidence']['status'],'BOUND')
        self.data['slide_height_pt']=866.13;self.save()
        self.assertEqual(self.run_audit()['office_evidence']['status'],'NOT_VERIFIED')
    def test_rotated_ancestor_not_certified(self):
        self.data['slides'][0]['text_bounds'][0]['ancestor_rotated']=True;self.save()
        self.assertEqual(self.run_audit()['collisions'][0]['diagnostic'],'office_bounds_unavailable')
    def test_unselected_duplicate_text_does_not_block_diagnostics(self):
        entry={'name':'unselected','text':'Other','box_pt':[300,150,100,50],'rotation':0}
        self.data['slides'][0]['text_bounds'].extend([entry,entry]);self.save()
        self.assertEqual(self.run_audit()['office_evidence']['status'],'BOUND')
    def test_unselected_table_limit_is_disclosed_without_blocking_labels(self):
        self.separate_frames();self.data['slides'][0]['unverified']=['Other table: table-cell text bounds are not supported'];self.save()
        report=self.run_audit();self.assertFalse(report['unverified']);self.assertTrue(report['valid'])
        self.assertTrue(report['office_evidence']['unselected_limitations'])
    def test_rotation_not_certified(self):
        self.data['slides'][0]['text_bounds'][0]['rotation']=45;self.save();r=self.run_audit()
        self.assertEqual(r['collisions'][0]['diagnostic'],'office_bounds_unavailable');self.assertTrue(r['unverified'])
    def test_duplicate_measurement(self):
        self.data['slides'][0]['text_bounds'].append(self.data['slides'][0]['text_bounds'][0]);self.save()
        self.assertEqual(self.run_audit()['office_evidence']['status'],'NOT_VERIFIED')
    def test_wrong_text_not_used(self):
        self.data['slides'][0]['text_bounds'][0]['text']='changed';self.save()
        self.assertEqual(self.run_audit()['collisions'][0]['diagnostic'],'office_bounds_unavailable')
    def test_preview_create_only(self):
        r=self.run_audit();out=self.root/'review.html';mod.write_review(r,self.deck,self.manifest,self.evidence,out)
        self.assertIn('layout_box_only',out.read_text());self.assertIn('data:image/png;base64,',out.read_text())
        with self.assertRaises(ValueError):mod.write_review(r,self.deck,self.manifest,self.evidence,out)
    def test_stale_layout_not_sent_to_grammar(self):
        spec=importlib.util.spec_from_file_location('runner',S/'run-quality-checks.py');runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
        manifest=self.root/'manifest.json';manifest.write_text(json.dumps(dict(self.manifest,diagram_grammar={})))
        layout=self.root/'stale.layout.json';layout.write_text(json.dumps({'artifact_sha256':'0'*64,'elements':[]}))
        checks={c['check']:c for c in runner.run_checks(self.deck,manifest,layout)['checks']}
        self.assertEqual(checks['layout_provenance']['status'],'NOT_VERIFIED')
        self.assertEqual(checks['diagram_grammar']['status'],'NOT_VERIFIED')


if __name__=='__main__':unittest.main()
