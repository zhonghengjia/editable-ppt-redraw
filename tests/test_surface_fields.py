"""Production field compilation: independent coordinates, supports and bindings."""
import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from PIL import Image
from pptx import Presentation
from test_source_fields import F, P, fixture, manifest, options
from native_components import ManifestComponentBuilder
import native_components as N


def independent_source(color_angle=0,alpha_angle=90):
    pixels=fixture(angle=color_angle)
    pixels[:,:,3]=fixture(angle=alpha_angle,alpha=True)[:,:,3]
    return pixels


class SurfaceMath(unittest.TestCase):
    def test_circle_and_annulus_unobserved_columns_are_not_rank_failures(self):
        yy,xx=np.mgrid[:100,:100];t=np.hypot(xx+.5-50,yy+.5-50)/np.hypot(100,100)*2
        pixels=np.rint(np.stack((.2+.5*t,.8-.5*t,.3+.2*t,np.ones_like(t)),axis=2)*255).astype('uint8')
        for inner in (0,.2):
            support=(t<1/np.sqrt(2))&(t>=inner)
            opt=options('radial');opt['stop_count']=8
            paint,e,preview=F.fit_field(pixels,support,[0,0,100,100],[0,0,100,100],opt)
            self.assertLess(e['max_error'],.008)
            self.assertIn(7,e['unobserved_stop_indices'])
            self.assertEqual(len(paint['stops']),8)
            self.assertTrue((preview[~support]==0).all())

    def test_unsupported_sparse_profile_still_fails(self):
        pixels=fixture();support=np.zeros((40,120),bool);support[20,60]=True
        with self.assertRaisesRegex(ValueError,'insufficient observed'):
            F.fit_field(pixels,support,[0,0,120,40],[0,0,120,40],options(angle=0))

    def test_independent_coordinates_fixed_and_automatic(self):
        for ca,aa in ((0,90),(37,135),(227,315)):
            pixels=independent_source(ca,aa);support=np.ones((40,120),bool)
            for auto in (False,True):
                opt=options();opt.update(semantics='source_rgba',max_error=.025,
                    alpha_profile=dict(model='linear',stop_count=4))
                if not auto:opt.update(angle=ca);opt['alpha_profile']['angle']=aa
                paint,effect,e,preview=F.fit_surface(pixels,support,[0,0,120,40],[0,0,120,40],opt)
                self.assertLess(e['max_error'],.025)
                self.assertTrue(all(s['alpha']==1 for s in paint['stops']))
                self.assertTrue(all(s['color']=='FFFFFF' for s in effect['alpha_mask']['stops']))
                self.assertEqual(preview.shape,pixels.shape)

    def test_transparent_colors_cannot_change_visible_fit(self):
        for angle in (0,37.48,82.3):
            for auto in (False,True):
                pixels=independent_source(angle);t=(np.arange(40)+.5)/40
                pixels[:,:,3]=np.rint(np.interp(t,[0,.33333,.66667,1],[0,0,.5,1])*255)[:,None]
                opt=options();opt.update(semantics='source_rgba',max_error=.025,
                    alpha_profile=dict(model='linear',angle=90,stop_count=4))
                if not auto:opt['angle']=angle
                args=(np.ones((40,120),bool),[0,0,120,40],[0,0,120,40],opt)
                before=F.fit_surface(pixels,*args)
                pixels[pixels[:,:,3]==0,:3]=255-pixels[pixels[:,:,3]==0,:3]
                after=F.fit_surface(pixels,*args)
                self.assertEqual(before[:2],after[:2])

    def test_independent_profiles_do_not_run_a_discarded_joint_fit(self):
        opt=options(angle=0);opt.update(semantics='source_rgba',
            alpha_profile=dict(model='linear',angle=90,stop_count=4))
        with patch.object(F,'_fit_profile',wraps=F._fit_profile) as fit:
            F.fit_surface(independent_source(),np.ones((40,120),bool),[0,0,120,40],[0,0,120,40],opt)
            self.assertEqual(fit.call_count,2)

    def test_auto_stop_budget_handles_non_nested_uniform_grids(self):
        opt=options();opt.update(stop_count=12,semantics='source_rgba',max_error=3/255,
            alpha_profile=dict(model='linear',stop_count=12))
        args=(independent_source(37,135),np.ones((40,120),bool),[0,0,120,40],[0,0,120,40])
        with self.assertRaisesRegex(ValueError,'not representable'):F.fit_surface(*args,opt)
        opt['stop_count']='auto';opt['alpha_profile']['stop_count']='auto'
        with patch.object(F,'_fit_profile',wraps=F._fit_profile) as fit:
            paint,effect,e,_=F.fit_surface(*args,opt)
            self.assertEqual(fit.call_count,2)
        self.assertLess(e['max_error'],3/255)
        self.assertEqual((len(paint['stops']),len(effect['alpha_mask']['stops'])),(4,4))

    def test_auto_profiles_cache_candidates_and_keep_failure_limit(self):
        pixels=independent_source();pixels[10:20,50:70,3]=255
        opt=options(angle=0);opt.update(semantics='source_rgba',stop_count='auto',
            alpha_profile=dict(model='linear',angle=90,stop_count='auto'))
        with patch.object(F,'_fit_profile',wraps=F._fit_profile) as fit:
            with self.assertRaisesRegex(ValueError,'not representable'):
                F.fit_surface(pixels,np.ones((40,120),bool),[0,0,120,40],[0,0,120,40],opt)
            self.assertEqual(fit.call_count,26)

    def test_auto_color_and_alpha_can_use_different_stop_counts(self):
        pixels=fixture(w=160,h=120,angle=0)
        positions=np.rint(np.linspace(0,1,7)*100000)/100000
        coverage=np.interp((np.arange(120)+.5)/120,positions,[0,.08,.12,.52,.58,.96,1])
        pixels[:,:,3]=np.rint(coverage*255)[:,None]
        opt=options(angle=0);opt.update(semantics='source_rgba',stop_count='auto',max_error=3/255,
            alpha_profile=dict(model='linear',angle=90,stop_count='auto'))
        with patch.object(F,'_fit_profile',wraps=F._fit_profile) as fit:
            paint,effect,e,_=F.fit_surface(pixels,np.ones((120,160),bool),[0,0,160,120],[0,0,160,120],opt)
            calls=[(call.kwargs.get('color_weights') is not None,call.args[4]['stop_count']) for call in fit.call_args_list]
        self.assertEqual(len(calls),len(set(calls)))
        self.assertEqual((len(paint['stops']),len(effect['alpha_mask']['stops'])),(4,7))
        self.assertLess(e['max_error'],3/255)

    def test_single_paint_auto_preserves_compatibility_and_validation(self):
        opt=options(angle=37);opt['stop_count']='auto'
        paint,e,_=F.fit_field(fixture(),np.ones((40,120),bool),[0,0,120,40],[0,0,120,40],opt)
        self.assertEqual(len(paint['stops']),4)
        self.assertEqual(e['stop_selection']['selected'],4)
        for value in ('automatic',0,17,True,4.0):
            opt['stop_count']=value
            with self.assertRaises(ValueError):F.validate_options(opt)

    def test_independent_alpha_schema_and_no_silent_discard(self):
        opt=options();opt['alpha_profile']=dict(model='linear',stop_count=4,angle=90)
        with self.assertRaisesRegex(ValueError,'explicit RGBA'):F.validate_options(opt)
        opt['semantics']='source_rgba'
        with self.assertRaisesRegex(ValueError,'fit_surface'):
            F.fit_field(independent_source(),np.ones((40,120),bool),[0,0,120,40],[0,0,120,40],opt)
        opt['alpha_profile']['hidden']='guess'
        with self.assertRaises(ValueError):F.validate_options(opt)

    def test_auto_color_sample_without_visible_information_fails_explicitly(self):
        pixels=np.zeros((500,500,4),dtype='uint8');pixels[0,1]=[100,120,180,1]
        opt=options();opt.update(semantics='source_rgba',
            alpha_profile=dict(model='linear',angle=90,stop_count=4))
        with self.assertRaisesRegex(ValueError,'no observed color information'):
            F.fit_surface(pixels,np.ones((500,500),bool),[0,0,500,500],[0,0,500,500],opt)

    def test_nonseparable_alpha_is_not_smoothed_or_rethresholded(self):
        pixels=independent_source();pixels[10:20,50:70,3]=255
        opt=options(angle=0);opt.update(semantics='source_rgba',
            alpha_profile=dict(model='linear',angle=90,stop_count=4))
        with self.assertRaisesRegex(ValueError,'not representable'):
            F.fit_surface(pixels,np.ones((40,120),bool),[0,0,120,40],[0,0,120,40],opt)


class SurfacePipeline(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.data=manifest(self.root)

    def build(self):
        path=self.root/'manifest.json';path.write_text(json.dumps(self.data))
        P.prepare(path,self.root/'prep')
        review=P.read_json(self.root/'prep/review-template.json')
        for item in review['items']:item.update(accepted=True,note='Synthetic explicit source fixture')
        review_path=self.root/'review.json';review_path.write_text(json.dumps(review))
        return review_path

    def test_saved_native_fill_and_independent_mask(self):
        Image.fromarray(independent_source()).save(self.root/'source.png')
        self.data['source']['sha256']=P.sha(self.root/'source.png')
        opt=self.data['source_inventory'][0]['construction']['field_fit']
        opt.update(angle=0,semantics='source_rgba',alpha_profile=dict(model='linear',angle=90,stop_count=4))
        review=self.build()
        P.build(self.root/'prep',self.root/'out',review=review)
        slide=Presentation(self.root/'out/candidate.pptx').slides[0]
        self.assertEqual(len(slide._element.xpath('.//a:gradFill')),2)
        self.assertEqual(len(slide._element.xpath('.//a:alphaMod')),1)
        self.assertFalse(slide._element.xpath('.//p:pic'))

    def test_estimated_layer_recipe_is_explicit_and_frozen(self):
        runtime=os.environ.get('EDITABLE_PPT_EXTRACT_PYTHON')
        if not runtime:self.skipTest('Separate installed extraction Python not supplied')
        # A real estimator run with complete hard ownership separates bundle
        # plumbing from the inverse problem. No fabricated production receipt.
        data=self.data;plan=dict(method='closed_form',source_sha256=data['source']['sha256'],
            context_bbox=[0,0,120,40],observation='Synthetic observed opaque calibration region',
            foreground=[[60,20]],background=[[0,0]],reserved_regions=[],
            annotations=[dict(kind='polygon',label='foreground',points=[[1,0],[119,0],[119,39],[1,39]],
                              observation='Known calibration foreground')],
            matting=dict(background_patches=[[0,0,1,1]],background_tolerance=0,epsilon=1e-7,solver='direct'))
        plan_path=self.root/'layer-plan.json';plan_path.write_text(json.dumps(plan))
        proc=subprocess.run([runtime,'-X','utf8','-B',str(P.SCRIPTS/'source_objects.py'),
            str(self.root/'source.png'),str(plan_path),str(self.root/'layer')],capture_output=True,text=True,timeout=120)
        self.assertEqual(proc.returncode,0,proc.stderr)
        mask=np.full((40,120),255,dtype='uint8');mask[:,0]=0
        Image.fromarray(mask).save(self.root/'support.png')
        opt=data['source_inventory'][0]['construction']['field_fit']
        opt.update(semantics='estimated_layer',source_layer=dict(path='layer/candidate.json',
            sha256=P.sha(self.root/'layer/candidate.json')))
        opt['support']['sha256']=P.sha(self.root/'support.png')
        review=self.build()
        evidence=P.read_json(self.root/'prep/item-0000/candidate.json')
        self.assertEqual(evidence['input_provenance']['method'],'estimated_source_layer')
        self.assertEqual(evidence['input_provenance']['physical_layer_identity'],'NOT_VERIFIED')
        (self.root/'layer/rgba.png').write_bytes(b'original no longer used')
        P.build(self.root/'prep',self.root/'out',review=review)
        (self.root/'prep/item-0000/layer/alpha.png').write_bytes(b'tamper')
        with self.assertRaisesRegex(ValueError,'bundle bytes changed'):
            P.build(self.root/'prep',self.root/'bad',review=review)
        self.assertFalse((self.root/'bad').exists())

    def test_bulk_preflight_is_linear_and_snapshot_is_owned(self):
        data=copy.deepcopy(self.data);proto=data['native_components'][0];item=data['source_inventory'][0]
        data['native_components']=[];data['source_inventory']=[]
        for i in range(20):
            cid=f'field{i}';c=copy.deepcopy(proto);c.update(id=cid,output_name=cid)
            entry=copy.deepcopy(item);entry['id']=cid
            data['native_components'].append(c);data['source_inventory'].append(entry)
        with patch.object(N,'prepare_component',wraps=N.prepare_component) as counted:
            builder=ManifestComponentBuilder(data,base_dir=self.root)
            data['native_components'][0]['parts'][0]['d']='invalid source mutation'
            deck=Presentation();slide=deck.slides.add_slide(deck.slide_layouts[6])
            for i in range(20):builder.add(slide,f'field{i}',0,0,6,2)
            self.assertEqual(counted.call_count,40)
        self.assertEqual(len(slide.shapes),20)

        (self.root/'source.png').write_bytes(b'changed after preflight')
        with self.assertRaisesRegex(ValueError,'source hash changed'):
            builder.add(slide,'field0',0,0,6,2)
        self.assertEqual(len(slide.shapes),20)

    def test_independent_group_alpha_cannot_attenuate_other_paints(self):
        Image.fromarray(independent_source()).save(self.root/'source.png')
        data=self.data;data['source']['sha256']=P.sha(self.root/'source.png')
        item=data['source_inventory'][0];opt=item['construction']['field_fit']
        opt.update(angle=0,semantics='source_rgba',alpha_profile=dict(model='linear',angle=90,stop_count=4))
        component=data['native_components'][0]
        body=copy.deepcopy(component['parts'][0]);body.update(id='body',fill=dict(kind='group'))
        detail=dict(id='detail',role='independent detail',observation='Opaque source mark',
            d='M28 28 H36 V36 H28 Z',fill='#FF0000')
        for other in (detail,dict(id='other',role='independent group',observation='Separately painted mark',
                                  group_fill='#FF0000',children=[dict(detail,fill=dict(kind='group'))])):
            component['parts']=[dict(id='surface',role='paint owner',observation='Mixed paint descendants',
                group_fill='#FFFFFF',children=[body,other])]
            with self.assertRaisesRegex(ValueError,'must own every painted descendant'):
                F.fit_component(self.root/'source.png',data['source']['sha256'],item,component,base_dir=self.root)

    def test_bulk_source_identity_can_come_from_legacy_contracts(self):
        original=(self.root/'source.png').read_bytes();data=self.data
        source_hash=data['source'].pop('sha256');item=data['source_inventory'][0]
        contracts=dict(regional_fidelity=dict(source_sha256=source_hash,source_size=[120,40],regions=[dict(
            id='field',source_bbox=[0,0,120,40],threshold=.1,max_mismatch_ratio=.1,max_window_ratio=.1,
            window=3,rationale='Synthetic source-bound regression',features=['Source region preserved'])]),
            appearance_fidelity=dict(source_sha256=source_hash,source_size=[120,40],color_space='srgb',
                matte=[255,255,255],items=[dict(id='field',source_bbox=[0,0,120,40],comparison='source_exact',
                requirements=[dict(id='tone',dimension='tone',certainty='observed',
                    observation='Source smooth field',criterion='Retain source variation')])]))
        for key,contract in contracts.items():
            (self.root/'source.png').write_bytes(original)
            test=copy.deepcopy(data);test[key]=contract
            test['source_inventory'][0]['fidelity_sensitive' if key=='regional_fidelity' else 'appearance_sensitive']=True
            builder=ManifestComponentBuilder(test,base_dir=self.root)
            (self.root/'source.png').write_bytes(b'changed after preflight')
            deck=Presentation();slide=deck.slides.add_slide(deck.slide_layouts[6])
            with self.assertRaisesRegex(ValueError,'source hash changed'):
                builder.add(slide,'field',0,0,6,2)
            self.assertFalse(len(slide.shapes))


if __name__=='__main__':unittest.main()
