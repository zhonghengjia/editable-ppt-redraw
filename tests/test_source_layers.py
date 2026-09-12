"""Source-layer capability regressions, not claims about a biological figure."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import numpy as np
from PIL import Image
from pptx import Presentation

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import reconstruction_pipeline as P
from raster_components import unmix_background
from source_layers import validate_layer_options
from test_reconstruction_pipeline import example_manifest, NODE


def fixture(root):
    h,w=60,80
    yy,xx=np.mgrid[:h,:w]
    alpha=np.clip((26-np.hypot(xx-40,yy-30))/14,0,1)
    fore=np.array([40,130,200]); back=np.array([240,244,250])
    pixels=np.rint(alpha[:,:,None]*fore+(1-alpha[:,:,None])*back).astype('uint8')
    source=root/'source.png'; Image.fromarray(pixels).save(source)
    def poly(points): return dict(kind='polygon',label='background',points=points,observation='Synthetic observed background')
    extract=dict(method='closed_form',foreground=[[40,30]],background=[[0,0]],reserved_regions=[],
        annotations=[poly([[0,0],[79,0],[79,3],[0,3]]),poly([[0,56],[79,56],[79,59],[0,59]]),
                     poly([[0,0],[10,0],[10,59],[0,59]]),poly([[70,0],[79,0],[79,59],[70,59]])],
        matting=dict(background_patches=[[0,0,8,8]],background_tolerance=0,epsilon=1e-7,max_iterations=3000))
    plan=dict(extract,source_sha256=P.sha(source),context_bbox=[0,0,w,h],observation='Synthetic soft blue disk')
    return source,alpha,fore,back,plan


class LayerMath(unittest.TestCase):
    def test_shared_inverse_on_multiple_backgrounds_and_zero_alpha(self):
        a=np.array([[0,.01,.25,.7,1.]])
        fore=np.broadcast_to([60,125,180],a.shape+(3,))
        for back in ([0,0,0],[255,255,255],[237,241,248]):
            c=np.rint(a[:,:,None]*fore+(1-a[:,:,None])*back)
            out,report=unmix_background(c,a,back)
            self.assertTrue((out[0,0]==0).all())
            self.assertLessEqual(report['visible_roundtrip_max_channel_error'],.500001)
            np.testing.assert_allclose(out[0,2:],fore[0,2:],atol=2)

    def test_inverse_rejects_incompatible_or_nonfinite_inputs(self):
        for a in (np.array([[.1]]),np.array([[float('nan')]]),np.array([[-1.]])):
            with self.assertRaises(ValueError): unmix_background(np.zeros((1,1,3)),a,[255,255,255])

    def test_layer_schema_requires_explicit_solver_and_scope(self):
        with tempfile.TemporaryDirectory() as temp:
            _,_,_,_,plan=fixture(Path(temp))
            validate_layer_options(plan)
            for mutation in ({'epsilon':0},{'max_iterations':0},{'background_patches':[]}):
                bad=copy.deepcopy(plan); bad['matting'].update(mutation)
                with self.assertRaises(ValueError):validate_layer_options(bad)
            plan['occlusions']=[dict(id='bad',kind='anatomy',authorization='test',marks=[])]
            with self.assertRaises(ValueError):validate_layer_options(plan)


class LayerProduction(unittest.TestCase):
    def setUp(self):
        self.runtime=os.environ.get('EDITABLE_PPT_EXTRACT_PYTHON')
        if not self.runtime and importlib.util.find_spec('scipy') is None:
            self.skipTest('Optional SciPy extraction runtime not supplied')
        self.runtime=self.runtime or sys.executable
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.source,self.alpha,self.fore,self.back,self.plan=fixture(self.root)

    def extract(self,plan=None,name='out',expect_success=True):
        path=self.root/(name+'.json');path.write_text(json.dumps(plan or self.plan))
        result=subprocess.run([self.runtime,'-X','utf8','-B',str(P.SCRIPTS/'source_objects.py'),
            str(self.source),str(path),str(self.root/name)],capture_output=True,text=True,timeout=120)
        if expect_success:self.assertEqual(result.returncode,0,result.stderr)
        else:self.assertNotEqual(result.returncode,0)
        return self.root/name

    def run_math(self, code):
        result=subprocess.run([self.runtime,'-X','utf8','-B','-c',
            'import sys;sys.path.insert(0,'+repr(str(P.SCRIPTS))+');import numpy as np;from source_layers import *;\n'+code],
            capture_output=True,text=True,timeout=120)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_biharmonic_reproduces_linear_field_and_preserves_boundary(self):
        self.run_math('''
y,x=np.mgrid[:20,:24]
rgb=np.stack((30+2*x+3*y,180-x-y,50+4*x),axis=2).astype('uint8')
mask=np.zeros((20,24),bool);mask[6:14,8:16]=True
damaged=rgb.copy();damaged[mask]=0
out,report=interpolate_smooth_field(damaged,mask)
assert np.abs(out.astype(int)-rgb).max()<=1
assert np.array_equal(out[~mask],damaged[~mask])
assert report['inferred_pixels']==64
for invalid in (mask.astype('uint8'),np.ones((20,24),bool)):
    try:interpolate_smooth_field(rgb,invalid)
    except ValueError:pass
    else:raise AssertionError('invalid/boundary mask accepted')
''')

    def test_direct_and_cg_consistency_and_solver_boundaries(self):
        self.run_math('''
y,x=np.mgrid[:10,:12];rgb=np.stack((30+3*x,100+2*y,180+0*x),axis=2).astype('uint8')
labels=np.full((10,12),255);labels[:,0]=0;labels[:,-1]=1
a,ra=closed_form_alpha(rgb,labels,epsilon=1e-7,solver='direct')
b,rb=closed_form_alpha(rgb,labels,epsilon=1e-7,max_iterations=1000)
assert np.max(np.abs(a-b))<1e-4
assert np.all(a[:,0]==0) and np.all(a[:,-1]==1)
labels[:,:6]=0;labels[:,6:]=1
c,rc=closed_form_alpha(rgb,labels,epsilon=1e-7,solver='direct')
assert rc['unknown_pixels']==0 and set(ra)==set(rc)
for r,l,opts in ((rgb,np.zeros_like(labels),{}),(rgb[:3],labels,{}),
 (rgb.astype(float)*np.nan,labels,{}),(rgb,labels,{'solver':'invalid'}),
 (rgb,labels,{'epsilon':0})):
    settings=dict(epsilon=1e-7,solver='direct');settings.update(opts)
    try:closed_form_alpha(r,l,**settings)
    except ValueError:pass
    else:raise AssertionError('invalid solver input accepted')
''')

    def test_joint_occlusion_order_and_reservations(self):
        pixels=np.asarray(Image.open(self.source)).copy();pixels[26:30,53:56]=0;pixels[34:38,54:57]=0
        Image.fromarray(pixels).save(self.source);self.plan['source_sha256']=P.sha(self.source)
        self.plan['reserved_regions']=[[53,26,4,12]]
        self.plan['occlusions']=[dict(id=str(i),kind='smooth_field',authorization='Synthetic smooth-field test',
            marks=[dict(kind='polygon',label='occluder',observation='Synthetic overprint',points=pts)])
            for i,pts in enumerate(([[53,26],[55,26],[55,29],[53,29]],[[54,34],[56,34],[56,37],[54,37]]))]
        first=self.extract(name='first')
        self.plan['occlusions'].reverse();second=self.extract(name='second')
        for key in ('reconstructed_color','alpha','rgba'):
            self.assertEqual(P.sha(first/(key+'.png')),P.sha(second/(key+'.png')))
        self.assertTrue(P.read_json(first/'candidate.json')['reserved_overlaps'])

    def test_nonconstant_matte_rejected_without_candidate(self):
        self.plan['matting']['background_patches']=[[0,0,8,8],[38,28,4,4]]
        out=self.extract(expect_success=False)
        self.assertFalse(out.exists())

    def test_receipt_and_alpha_coherence_binding(self):
        from source_layers import read_layer_bundle
        out=self.extract();receipt=out/'candidate.json'
        binding=dict(path=str(receipt),sha256=P.sha(receipt))
        read_layer_bundle(binding,P.sha(self.source),[0,0,80,60])
        evidence=P.read_json(receipt);evidence['plan']['observation']='changed'
        receipt.write_text(json.dumps(evidence));binding['sha256']=P.sha(receipt)
        with self.assertRaisesRegex(ValueError,'recipe'):
            read_layer_bundle(binding,P.sha(self.source),[0,0,80,60])

    def test_soft_coverage_and_clean_foreground(self):
        before=P.sha(self.source); out=self.extract()
        rgba=np.asarray(Image.open(out/'rgba.png'))
        recovered=rgba[:,:,3]/255
        self.assertLess(np.mean(np.abs(recovered-self.alpha)),.025)
        band=(self.alpha>.15)&(self.alpha<.85)
        self.assertLess(np.mean(np.abs(rgba[:,:,:3][band]-self.fore)),8)
        self.assertTrue((rgba[:,:,:3][rgba[:,:,3]==0]==0).all())
        self.assertGreater(np.unique(rgba[:,:,3]).size,30)
        self.assertEqual(P.sha(self.source),before)
        self.assertFalse(P.read_json(out/'candidate.json')['hidden_content_generated'])

    def test_smooth_occlusion_has_no_glyph_hole_and_keeps_other_rgb(self):
        pixels=np.asarray(Image.open(self.source)).copy(); pixels[26:34,55:58]=0
        Image.fromarray(pixels).save(self.source); self.plan['source_sha256']=P.sha(self.source)
        self.plan['occlusions']=[dict(id='letter',kind='smooth_field',authorization='Synthetic low-frequency color-field test',
            marks=[dict(kind='polygon',label='occluder',observation='Synthetic black overprint only',
                        points=[[55,26],[57,26],[57,33],[55,33]])])]
        out=self.extract()
        mask=np.asarray(Image.open(out/'occlusion_mask.png'))>0
        repaired=np.asarray(Image.open(out/'reconstructed_color.png'))
        np.testing.assert_array_equal(repaired[~mask],pixels[~mask])
        self.assertGreater(np.asarray(Image.open(out/'alpha.png'))[mask].min(),0)
        self.assertTrue(P.read_json(out/'candidate.json')['hidden_content_generated'])

    def test_nonconvergence_fails_without_output(self):
        self.plan['matting']['max_iterations']=1
        out=self.extract(expect_success=False)
        self.assertFalse(out.exists())

    def test_pipeline_binds_rgba_and_emits_native_alpha(self):
        manifest=example_manifest(self.source)
        manifest['source'].update(width=80,height=60)
        manifest['canvas'].update(width=80,height=60)
        manifest['modules'][0]['bbox']=[0,0,80,60]
        manifest['construction']['version']=2
        manifest['source_inventory']=manifest['source_inventory'][::2]
        body,background=manifest['source_inventory']
        body['bbox']=background['bbox']=[0,0,80,60]
        extract={k:v for k,v in self.plan.items() if k not in ('source_sha256','context_bbox','observation')}
        body['construction'].update(extract=extract,trace=dict(colors=32,representation='palette_edges',
            max_native_paths=100,max_native_commands=20000))
        background['construction']['options']['fill']='F0F4FA'
        path=self.root/'manifest.json';path.write_text(json.dumps(manifest))
        prep=self.root/'prep';P.prepare(path,prep,node=NODE,extract_python=self.runtime)
        review=P.read_json(prep/'review-template.json')
        review['items'][0].update(accepted=True,note='Synthetic known-alpha regression support')
        rev=self.root/'review.json';rev.write_text(json.dumps(review))
        P.build(prep,self.root/'build',review=rev,node=NODE)
        slide=Presentation(self.root/'build/candidate.pptx').slides[0]
        self.assertFalse(slide._element.xpath('.//p:pic'))
        alphas=[int(x) for x in slide._element.xpath('.//a:alpha/@val')]
        self.assertTrue(any(0<v<100000 for v in alphas))
        (prep/'item-0000/rgba.png').write_bytes(b'tampered')
        with self.assertRaisesRegex(ValueError,'bytes changed'):
            P.build(prep,self.root/'bad',review=rev,node=NODE)
        manifest['construction']['version']=1
        self.assertTrue(P.validate_contract(manifest))
