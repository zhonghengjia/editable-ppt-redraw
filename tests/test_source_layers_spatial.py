"""Synthetic spatial-background regressions; no scientific source coordinates."""
import copy
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from raster_components import digest, unmix_background
from source_layers import extract_layer, fit_observed_background, read_layer_bundle, validate_layer_options
from source_objects import extract_source_object


def fixture(root, *, spatial=True):
    h,w=48,64
    yy,xx=np.mgrid[:h,:w]
    alpha=np.clip((19-np.hypot(xx-32,yy-24))/10,0,1)
    foreground=np.array([40,120,175])
    background=np.stack((205+.5*xx+.25*yy,225-.25*xx+.25*yy,240-.25*xx-.5*yy),axis=2)
    if not spatial:background[:]=[235,240,245]
    pixels=np.rint(alpha[:,:,None]*foreground+(1-alpha[:,:,None])*background).astype('uint8')
    source=root/'source.png';Image.fromarray(pixels).save(source)
    annotations=[dict(kind='polygon',label='background',observation='Synthetic opaque background border',points=p)
        for p in ([[0,0],[63,0],[63,3],[0,3]],[[0,44],[63,44],[63,47],[0,47]],
                  [[0,0],[5,0],[5,47],[0,47]],[[59,0],[63,0],[63,47],[59,47]])]
    settings=dict(background_patches=[[0,0,6,6],[58,0,6,6],[0,42,6,6],[58,42,6,6]],
        background_tolerance=1,epsilon=1e-7,solver='direct')
    if spatial:
        settings['background_model']=dict(kind='affine',observation='Synthetic source shows a smooth affine background',max_condition=20)
    else:settings.update(background_patches=[[0,0,6,6]],background_tolerance=0)
    plan=dict(method='closed_form',foreground=[[32,24]],background=[[0,0]],reserved_regions=[],
        annotations=annotations,matting=settings,source_sha256=digest(source.read_bytes()),
        context_bbox=[0,0,w,h],observation='Synthetic soft foreground on observed background')
    return source,alpha,foreground,background,plan


def rgba(outputs):
    return np.asarray(Image.open(io.BytesIO(outputs['rgba'])))


@unittest.skipUnless(importlib.util.find_spec('scipy'), 'Run in the qualified SciPy extraction interpreter')
class SpatialBackground(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.source,self.alpha,self.fore,self.back,self.plan=fixture(self.root)

    def test_spatial_gradient_soft_edge_and_foreground_decontamination(self):
        before=self.source.read_bytes()
        outputs,evidence=extract_source_object(self.source,self.plan)
        out=rgba(outputs);a=out[:,:,3]/255
        self.assertLess(np.mean(np.abs(a-self.alpha)),.035)
        band=(self.alpha>.2)&(self.alpha<.85)
        self.assertLess(np.mean(np.abs(out[:,:,:3][band].astype(float)-self.fore)),10)
        self.assertTrue((out[:,:,:3][out[:,:,3]==0]==0).all())
        self.assertGreater(np.unique(out[:,:,3]).size,30)
        self.assertEqual(self.source.read_bytes(),before)
        self.assertFalse(evidence['hidden_content_generated'])
        self.assertEqual(evidence['background_model']['extrapolated_pixels'],0)
        self.assertEqual(evidence['background_model']['patch_center_rank'],3)
        self.assertEqual(len(evidence['background_model']['heldout_patch_max_errors']),4)
        self.assertLessEqual(evidence['background_model']['maximum_observed_error'],1)
        self.assertIsNone(evidence['background_rgb'])
        trimap=np.asarray(Image.open(io.BytesIO(outputs['trimap'])))
        self.assertTrue((out[:,:,3][trimap==0]==0).all())
        self.assertTrue((out[:,:,3][trimap==255]==255).all())
        self.assertEqual(evidence['uncertainty']['alpha_unknown_pixels'],int((trimap==128).sum()))
        self.assertEqual(set(outputs),{'context_mask','alpha','rgba','trimap','occlusion_mask',
            'coverage_adjustment','reconstructed_color'})

    def test_constant_path_keeps_existing_contract_and_known_ground_truth(self):
        source,alpha,fore,_,plan=fixture(self.root,spatial=False)
        outputs,evidence=extract_layer(source,plan)
        out=rgba(outputs)
        self.assertNotIn('background_model',evidence)
        self.assertEqual(evidence['background_rgb'],[235,240,245])
        self.assertEqual(evidence['background_sample_max_deviation'],0)
        self.assertLess(np.mean(np.abs(out[:,:,3]/255-alpha)),.025)
        band=(alpha>.2)&(alpha<.85)
        self.assertLess(np.mean(np.abs(out[:,:,:3][band].astype(float)-fore)),8)

    def test_spatial_background_is_opt_in(self):
        del self.plan['matting']['background_model']
        with self.assertRaisesRegex(ValueError,'constant matte'):
            extract_layer(self.source,self.plan)

    def test_known_spatial_background_inverse_and_zero_alpha(self):
        a=np.array([[0,.1,.4,.9,1.]])
        b=np.array([[[220,230,240],[205,220,235],[190,210,230],[175,200,225],[160,190,220]]])
        f=np.broadcast_to([40,110,180],b.shape)
        c=np.rint(a[:,:,None]*f+(1-a[:,:,None])*b)
        out,report=unmix_background(c,a,b)
        np.testing.assert_array_equal(out[0,0],[0,0,0])
        np.testing.assert_allclose(out[0,2:],f[0,2:],atol=2)
        self.assertLessEqual(report['visible_roundtrip_max_channel_error'],.500001)
        bad=b.astype(float);bad[0,2,0]=np.nan
        with self.assertRaises(ValueError):unmix_background(c,a,bad)

    def test_exact_affine_zero_tolerance_and_range_boundary(self):
        yy,xx=np.mgrid[:48,:64]
        pixels=np.stack((xx+2*yy,100+xx,200-yy),axis=2).astype('uint8')
        image=Image.fromarray(pixels)
        labels=np.zeros((48,64),dtype='uint8')
        settings=copy.deepcopy(self.plan['matting']);settings['background_tolerance']=0
        field,report=fit_observed_background(image,(0,0,64,48),settings,labels)
        np.testing.assert_allclose(field,pixels,atol=1e-10)
        self.assertLess(report['numeric_roundoff_tolerance'],1e-8)
        self.assertEqual(report['background_tolerance'],0)

    def test_original_source_patches_can_enclose_an_offset_context(self):
        yy,xx=np.mgrid[:24,:28]
        pixels=np.stack((50+xx+yy,160-xx,210-yy),axis=2).astype('uint8')
        settings=copy.deepcopy(self.plan['matting'])
        settings.update(background_patches=[[0,0,3,3],[25,0,3,3],[0,21,3,3],[25,21,3,3]],
            background_tolerance=0)
        labels=np.zeros((16,18),dtype='uint8')
        field,report=fit_observed_background(Image.fromarray(pixels),(5,4,18,16),settings,labels)
        np.testing.assert_allclose(field,pixels[4:20,5:23],atol=1e-10)
        self.assertEqual(report['field_size'],[18,16])
        self.assertEqual(report['extrapolated_pixels'],0)

    def test_independent_patch_order_does_not_change_pixels(self):
        first,_=extract_layer(self.source,self.plan)
        self.plan['matting']['background_patches'].reverse()
        second,_=extract_layer(self.source,self.plan)
        for key in first:self.assertEqual(first[key],second[key],key)

    def test_hard_thin_branch_and_disconnected_fragment_survive(self):
        pixels=np.asarray(Image.open(self.source)).copy()
        pixels[24,50:58]=self.fore;pixels[8,50]=self.fore
        Image.fromarray(pixels).save(self.source)
        self.plan['source_sha256']=digest(self.source.read_bytes())
        self.plan['foreground'].append([50,8])
        self.plan['annotations'].append(dict(kind='stroke',label='foreground',width=1,
            points=[[50,24],[57,24]],observation='Synthetic visible one-pixel branch'))
        outputs,_=extract_layer(self.source,self.plan)
        out=rgba(outputs)
        self.assertTrue((out[24,50:58,3]==255).all())
        self.assertEqual(out[8,50,3],255)
        np.testing.assert_array_equal(out[24,50:58,:3],np.broadcast_to(self.fore,(8,3)))

    def test_invalid_and_misspelled_models_rejected(self):
        for mutation in ({'kind':'quadratic'},{'observation':''},{'max_condition':float('nan')},
                         {'max_condition':True},{'extrapolate':True}):
            bad=copy.deepcopy(self.plan);bad['matting']['background_model'].update(mutation)
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):validate_layer_options(bad)
        for value in (None,[],{}):
            bad=copy.deepcopy(self.plan);bad['matting']['background_model']=value
            with self.assertRaises(ValueError):validate_layer_options(bad)
        bad=copy.deepcopy(self.plan);bad['matting']['background_patches']=bad['matting']['background_patches'][:3]
        with self.assertRaisesRegex(ValueError,'four independent'):validate_layer_options(bad)

    def test_ill_conditioned_and_collinear_patch_centers_rejected(self):
        for boxes in ([[0,0,2,2],[10,0,2,2],[20,0,2,2],[30,0,2,2]],
                      [[0,0,2,2],[20,0,2,2],[40,0,2,2],[60,1,2,2]]):
            bad=copy.deepcopy(self.plan);bad['matting']['background_patches']=boxes
            with self.assertRaisesRegex(ValueError,'rank deficient|condition limit'):
                extract_layer(self.source,bad)

    def test_no_extrapolation_beyond_observed_patch_hull(self):
        bad=copy.deepcopy(self.plan)
        bad['matting']['background_patches']=[[1,1,4,4],[59,1,4,4],[1,43,4,4],[59,43,4,4]]
        with self.assertRaisesRegex(ValueError,'outside observed patch hull'):
            extract_layer(self.source,bad)

    def test_contradictory_samples_and_hard_witnesses_rejected(self):
        # A new corner color can be explained poorly by an affine field and is
        # caught by independent held-out evidence, rather than deleted as an outlier.
        pixels=np.asarray(Image.open(self.source)).copy();pixels[:6,:6]=[10,20,30]
        Image.fromarray(pixels).save(self.source);self.plan['source_sha256']=digest(self.source.read_bytes())
        with self.assertRaisesRegex(ValueError,'fit/held-out tolerance'):
            extract_layer(self.source,self.plan)
        self.source,_,_,_,self.plan=fixture(self.root)
        self.plan['background'].append([32,30])
        with self.assertRaisesRegex(ValueError,'hard background witnesses'):
            extract_layer(self.source,self.plan)

    def test_overlapping_foreground_reserved_and_occlusion_samples_rejected(self):
        bad=copy.deepcopy(self.plan);bad['matting']['background_patches'][1]=[1,1,6,6]
        with self.assertRaisesRegex(ValueError,'disjoint'):extract_layer(self.source,bad)
        bad=copy.deepcopy(self.plan);bad['foreground'].append([2,2])
        # Remove border annotations so the independent patch conflict is reached.
        bad['annotations']=[]
        with self.assertRaisesRegex(ValueError,'foreground ownership'):extract_layer(self.source,bad)
        bad=copy.deepcopy(self.plan);bad['reserved_regions']=[[1,1,2,2]]
        with self.assertRaisesRegex(ValueError,'reserved'):extract_layer(self.source,bad)
        image=Image.open(self.source);labels=np.full((48,64),255);labels[0,0]=0;labels[24,32]=1
        excluded=np.zeros((48,64),bool);excluded[2,2]=True
        with self.assertRaisesRegex(ValueError,'occlusion'):
            fit_observed_background(image,(0,0,64,48),self.plan['matting'],labels,excluded=excluded)

    def test_stale_source_hash_and_receipt_model_mismatch_rejected(self):
        bad=copy.deepcopy(self.plan);bad['source_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'hash mismatch'):extract_layer(self.source,bad)
        outputs,evidence=extract_layer(self.source,self.plan)
        out=self.root/'bundle';out.mkdir()
        for key,value in outputs.items():(out/(key+'.png')).write_bytes(value)
        receipt=out/'candidate.json';receipt.write_text(json.dumps(evidence),encoding='utf8')
        binding=dict(path=str(receipt),sha256=digest(receipt.read_bytes()))
        read_layer_bundle(binding,self.plan['source_sha256'],self.plan['context_bbox'])
        evidence['background_model']['kind']='constant'
        receipt.write_text(json.dumps(evidence),encoding='utf8');binding['sha256']=digest(receipt.read_bytes())
        with self.assertRaisesRegex(ValueError,'background model/recipe mismatch'):
            read_layer_bundle(binding,self.plan['source_sha256'],self.plan['context_bbox'])


if __name__=='__main__':unittest.main()
