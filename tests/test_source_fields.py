"""Independent continuous-field fixtures, pipeline binding and native readback."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from PIL import Image
from pptx import Presentation
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import source_fields as F
import reconstruction_pipeline as P


def options(model='linear',**kwargs):
    return dict(part_id='surface',support=dict(path='support.png',sha256='a'*64),
        model=model,semantics='visible_composite',stop_count=4,max_error=.015,**kwargs)


def fixture(w=120,h=40,angle=37,radial=False,alpha=False):
    yy,xx=np.mgrid[:h,:w]; xx=xx+.5; yy=yy+.5
    if radial: t=np.sqrt((xx-w/2)**2+(yy-h/2)**2)/np.sqrt(w*w+h*h)*2
    else:
        a=np.deg2rad(angle); c,s=np.cos(a),np.sin(a)
        lo=min(0,w*c)+min(0,h*s); hi=max(0,w*c)+max(0,h*s)
        t=(xx*c+yy*s-lo)/(hi-lo)
    # Quantized native positions, independently interpolated RGB and alpha.
    positions=[0,.33333,.66667,1]
    stops=np.array([[.15,.3,.7],[.3,.55,.85],[.7,.65,.35],[.95,.8,.1]])
    rgb=np.stack([np.interp(t,positions,stops[:,i]) for i in range(3)],axis=-1)
    coverage=np.interp(t,positions,[0,.4,.75,1]) if alpha else np.ones_like(t)
    return np.rint(np.dstack((rgb,coverage))*255).astype('uint8')


class FieldMath(unittest.TestCase):
    def test_non_square_diagonal_and_reverse(self):
        for angle in (37,135,227,315):
            with self.subTest(angle=angle):
                p=fixture(angle=angle); paint,e,_=F.fit_field(p,np.ones((40,120),bool),[0,0,120,40],[0,0,120,40],options(angle=angle))
                self.assertEqual(paint['kind'],'linear');self.assertEqual(len(paint['stops']),4)
                self.assertLess(e['max_error'],.009)

    def test_automatic_direction_is_aspect_correct(self):
        p=fixture(angle=37)
        paint,e,_=F.fit_field(p,np.ones((40,120),bool),[0,0,120,40],[0,0,120,40],options())
        self.assertLess(abs(paint['angle']-37),1)
        self.assertLess(e['max_error'],.012)

    def test_rgba_forward_and_zero_alpha_rgb(self):
        p=fixture(alpha=True,angle=0); p[:,:2,3]=0
        opt=options(angle=0);opt['semantics']='source_rgba';opt['max_error']=.04
        a,e,_=F.fit_field(p,np.ones((40,120),bool),[0,0,120,40],[0,0,120,40],opt)
        p[:,:2,:3]=255-p[:,:2,:3]
        b,_,_=F.fit_field(p,np.ones((40,120),bool),[0,0,120,40],[0,0,120,40],opt)
        self.assertEqual(a,b)
        self.assertLess(e['max_alpha_error'],.04)
        self.assertTrue(any(0<s['alpha']<1 for s in a['stops']))

    def test_centered_circle_in_non_square_domain(self):
        p=fixture(radial=True)
        paint,e,_=F.fit_field(p,np.ones((40,120),bool),[0,0,120,40],[0,0,120,40],options('radial'))
        self.assertEqual(paint['focus'],[.5,.5]);self.assertLess(e['max_error'],.009)

    def test_radial_source_radius_and_constant_rim(self):
        yy,xx=np.mgrid[:40,:120];t=np.clip(np.hypot(xx+.5-60,yy+.5-20)/24,0,1)
        colors=np.array([[30,60,130],[60,100,170],[110,140,200],[170,200,220]])
        p=np.zeros((40,120,4),dtype='uint8');p[:,:,3]=255
        for i in range(3):p[:,:,i]=np.rint(np.interp(t,[0,.33333,.66667,1],colors[:,i]))
        paint,e,_=F.fit_field(p,np.ones((40,120),bool),[0,0,120,40],[0,0,120,40],options('radial',radius=24))
        self.assertEqual(len(paint['stops']),5)
        self.assertEqual(paint['stops'][-1]['color'],paint['stops'][-2]['color'])
        self.assertLess(e['max_error'],.009)

    def test_offset_owner_with_holes_uses_geometry_domain(self):
        p=np.zeros((80,160,4),dtype='uint8');p[20:60,20:140]=fixture(angle=37)
        support=np.zeros((80,160),bool);support[20:60,20:140]=True;support[30:40,60:75]=False
        paint,e,preview=F.fit_field(p,support,[50,70,160,80],[70,90,120,40],options(angle=37))
        self.assertLess(e['max_error'],.01)
        self.assertTrue((preview[~support]==0).all())
        self.assertEqual(e['owner_bbox'],[70,90,120,40])

    def test_solid(self):
        p=np.full((20,20,4),[53,100,170,255],dtype='uint8')
        paint,e,_=F.fit_field(p,np.ones((20,20),bool),[0,0,20,20],[0,0,20,20],options('solid'))
        self.assertEqual(paint,dict(kind='solid',color='3564AA',alpha=1))
        self.assertEqual(e['max_error'],0)

    def test_hard_boundary_is_not_smoothed_to_pass(self):
        p=np.zeros((40,120,4),dtype='uint8');p[:,:,3]=255;p[:,60:,:3]=255
        with self.assertRaisesRegex(ValueError,'not representable'):
            F.fit_field(p,np.ones((40,120),bool),[0,0,120,40],[0,0,120,40],options(angle=0))

    def test_options_and_input_boundaries(self):
        p=fixture();support=np.ones((40,120),bool)
        for key,value in [('stop_count',2),('model','mesh'),('max_error',.9),('semantics','recover_hidden')]:
            opt=options();opt[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):
                F.fit_field(p,support,[0,0,120,40],[0,0,120,40],opt)
        p[:,:,3]=128
        with self.assertRaisesRegex(ValueError,'opaque'):
            F.fit_field(p,support,[0,0,120,40],[0,0,120,40],options())
        with self.assertRaisesRegex(ValueError,'complete native owner'):
            F.fit_field(p,support,[0,0,120,40],[-1,0,121,40],options())


def manifest(root):
    source=root/'source.png';Image.fromarray(fixture()).save(source)
    Image.new('L',(120,40),255).save(root/'support.png')
    opt=options(angle=37);opt['support']['sha256']=P.sha(root/'support.png')
    return dict(schema_version=1,mode='faithful',execution_profile='standard',
        source=dict(path='source.png',width=120,height=40,sha256=P.sha(source)),canvas=dict(width=120,height=40),
        targets=[dict(format='pptx',path='candidate.pptx')],construction=dict(version=3,slide_width_inches=6),
        modules=[dict(id='panel',type='illustration',bbox=[0,0,120,40],reading_order=1)],connections=[],uncertainties=[],
        source_inventory=[dict(id='field',module='panel',role='shape',bbox=[0,0,120,40],representation='native_composite',
            construction=dict(kind='native_component',observation='Synthetic source smooth field',field_fit=opt))],
        native_components=[dict(id='field',output_name='field',viewbox=[0,0,120,40],parts=[
            dict(id='surface',role='surface',observation='Synthetic original rectangle',d='M0 0 L120 0 L120 40 L0 40 Z',fill=None)])])


class FieldPipeline(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.data=manifest(self.root)
        self.path=self.root/'manifest.json'

    def prepare(self):
        self.path.write_text(json.dumps(self.data),encoding='utf8')
        P.prepare(self.path,self.root/'prep')
        review=P.read_json(self.root/'prep/review-template.json')
        for item in review['items']: item.update(accepted=True,note='Synthetic fixed geometry and source color fixture')
        path=self.root/'review.json';path.write_text(json.dumps(review));return path

    def test_actual_pipeline_continuous_fill_without_tracer(self):
        before=copy.deepcopy(self.data['native_components']);review=self.prepare()
        self.assertEqual(self.data['native_components'],before)
        (self.root/'source.png').write_bytes(b'not reused after prepare')
        with patch('component_fidelity.trace_component',side_effect=AssertionError('must not quantize')):
            P.build(self.root/'prep',self.root/'build',review=review)
        deck=Presentation(self.root/'build/candidate.pptx');slide=deck.slides[0]
        self.assertEqual(len(slide._element.xpath('.//a:gradFill')),1)
        self.assertEqual(len(slide._element.xpath('.//a:gs')),4)
        self.assertEqual(len(slide._element.xpath('.//p:sp')),1)
        self.assertFalse(slide._element.xpath('.//p:pic'))
        resolved=P.read_json(self.root/'build/resolved-manifest.json')
        self.assertEqual(resolved['native_components'][0]['parts'][0]['d'],before[0]['parts'][0]['d'])
        self.assertEqual(resolved['native_components'][0]['parts'][0]['fill']['kind'],'linear')

    def test_review_and_support_are_required(self):
        self.prepare()
        with self.assertRaisesRegex(ValueError,'inspect extracted'):
            P.build(self.root/'prep',self.root/'bad')
        (self.root/'prep/item-0000/support.png').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'hash changed'):
            P.build(self.root/'prep',self.root/'bad',review=self.root/'review.json')
        self.assertFalse((self.root/'bad').exists())

    def test_fit_tampering_even_with_rebound_review_is_rejected(self):
        review=self.prepare();candidate=self.root/'prep/item-0000/candidate.json'
        evidence=P.read_json(candidate);evidence['component']['parts'][0]['fill']['stops'][0]['color']='FFFFFF'
        candidate.write_text(json.dumps(evidence))
        rec=P.read_json(self.root/'prep/prepared.json');rec['items'][0]['candidate']['sha256']=P.sha(candidate)
        (self.root/'prep/prepared.json').write_text(json.dumps(rec))
        rev=P.read_json(review);rev['prepared_sha256']=P.sha(self.root/'prep/prepared.json');rev['items'][0]['candidate_sha256']=P.sha(candidate)
        review.write_text(json.dumps(rev))
        with self.assertRaisesRegex(ValueError,'differs from frozen'):
            P.build(self.root/'prep',self.root/'bad',review=review)
        self.assertFalse((self.root/'bad').exists())

    def test_version_and_route_binding(self):
        for version in (1,2):
            self.data['construction']['version']=version
            self.assertTrue(P.validate_contract(self.data))
        self.data['construction']['version']=3
        self.assertEqual(P.validate_contract(self.data),[])

    def test_missing_candidate_rejected_before_approval_or_output(self):
        self.prepare()
        path=self.root/'prep/prepared.json';rec=P.read_json(path)
        del rec['items'][0]['candidate'];path.write_text(json.dumps(rec))
        with self.assertRaisesRegex(ValueError,'candidates are incomplete'):
            P.build(self.root/'prep',self.root/'bad')
        self.assertFalse((self.root/'bad').exists())

    def test_rebound_support_must_match_original_recipe(self):
        self.prepare()
        data=P.read_json(self.root/'prep/input-manifest.json');item=data['source_inventory'][0]
        path=self.root/'prep/item-0000/support.png'
        mask=np.full((40,120),255,dtype='uint8');mask[10:20,30:40]=0;Image.fromarray(mask).save(path)
        support=dict(path='item-0000/support.png',sha256=P.sha(path))
        with self.assertRaisesRegex(ValueError,'support differs from frozen recipe'):
            P._field_candidate(self.root/'prep/source.png',data,item,support,self.root/'prep')

    def test_group_fit_and_inheriting_compositing(self):
        component=self.data['native_components'][0];leaf=component['parts'][0]
        leaf.update(id='leaf',fill=dict(kind='group'))
        component['parts']=[dict(id='surface',role='surface',observation='Observed single field owner',
                                 group_fill='FFFFFF',children=[leaf])]
        item=self.data['source_inventory'][0]
        args=(self.root/'source.png',self.data['source']['sha256'],item,component)
        evidence,_=F.fit_component(*args,base_dir=self.root)
        self.assertEqual(evidence['component']['parts'][0]['group_fill']['kind'],'linear')
        self.assertEqual(evidence['component']['parts'][0]['children'][0]['d'],leaf['d'])
        leaf['compositing']=dict(opacity=.5)
        with self.assertRaisesRegex(ValueError,'consumer already has compositing'):
            F.fit_component(*args,base_dir=self.root)
        del leaf['compositing']
        component['parts'][0]['children']=[dict(id='inner',role='group',observation='Inherited alpha',
                                               compositing=dict(opacity=.5),children=[leaf])]
        with self.assertRaisesRegex(ValueError,'consumer already has compositing'):
            F.fit_component(*args,base_dir=self.root)

    def test_qualified_source_reader_is_reused(self):
        source=self.root/'source.png'
        for tag in ('icc','orientation','palette'):
            with self.subTest(tag=tag):
                image=Image.fromarray(fixture());kwargs={}
                if tag=='icc':kwargs['icc_profile']=b'unqualified-profile'
                elif tag=='orientation':
                    exif=Image.Exif();exif[274]=6;kwargs['exif']=exif
                else:image=image.convert('P')
                image.save(source,**kwargs)
                with self.assertRaisesRegex(ValueError,'qualify ICC|requires RGB'):
                    F.fit_component(source,P.sha(source),self.data['source_inventory'][0],
                                    self.data['native_components'][0],base_dir=self.root)

    def test_failed_fit_has_no_successful_preparation(self):
        p=fixture();p[:,60:,:3]=0;Image.fromarray(p).save(self.root/'source.png')
        self.data['source']['sha256']=P.sha(self.root/'source.png')
        with self.assertRaisesRegex(ValueError,'not representable'): self.prepare()
        self.assertFalse((self.root/'prep/prepared.json').exists())
        self.assertTrue((self.root/'prep/failure.json').exists())


if __name__=='__main__': unittest.main()
