import copy
from pathlib import Path
import sys
import unittest
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from native_components import component_xml,prepare_component
from native_paint import normalize_compositing,compositing_xml
from spatial_masks import decode_mask_field,fit_axis_mask
NS={'p':'http://schemas.openxmlformats.org/presentationml/2006/main',
    'a':'http://schemas.openxmlformats.org/drawingml/2006/main'}


def component():
    return dict(id='c',output_name='c',viewbox=[0,0,100,100],parts=[dict(id='g',role='group',
        observation='Synthetic overlapped parts',compositing=dict(opacity=.5),children=[
        dict(id='a',role='part',observation='Synthetic red part',d='M0 0 H60 V60 H0 Z',fill='FF0000'),
        dict(id='b',role='part',observation='Synthetic blue part',d='M20 20 H100 V100 H20 Z',fill='0000FF')])])


class NativeCompositingTests(unittest.TestCase):
    def test_no_effects_for_legacy_tree(self):
        f=component();del f['parts'][0]['compositing']
        root,_=component_xml(f,0,0,1,1)
        self.assertFalse(root.findall('.//a:effectDag',NS))
        self.assertEqual(compositing_xml(None),'')

    def test_group_effect_does_not_change_children(self):
        f=component();root,_=component_xml(f,0,0,1,1)
        self.assertEqual(len(root.findall('.//a:alphaModFix',NS)),1)
        self.assertEqual(root.find('p:grpSp/p:grpSpPr/a:effectDag/a:alphaModFix',NS).get('amt'),'50000')
        self.assertEqual([r.get('val') for r in root.findall('.//p:sp/p:spPr/a:solidFill/a:srgbClr/a:alpha',NS)],['100000','100000'])

    def test_nested_scopes_and_zero(self):
        f=component();f['parts'][0]['children'][0]['compositing']={'opacity':0}
        root,_=component_xml(f,0,0,1,1)
        self.assertEqual(sorted(e.get('amt') for e in root.findall('.//a:alphaModFix',NS)),['0','50000'])

    def test_mask_precedes_constant_opacity(self):
        mask=dict(kind='linear',angle=0,stops=[dict(position=0,color='FFFFFF',alpha=0),dict(position=1,color='FFFFFF',alpha=1)])
        f=component();f['parts'][0]['compositing']['alpha_mask']=mask
        root,_=component_xml(f,0,0,1,1)
        dag=root.find('p:grpSp/p:grpSpPr/a:effectDag',NS)
        self.assertEqual([r.tag.rsplit('}',1)[1] for r in dag],['alphaMod','alphaModFix'])
        self.assertIsNotNone(dag.find('a:alphaMod/a:cont/a:fill/a:gradFill',NS))
        self.assertEqual(len(root.findall('.//p:pic',NS)),0)

    def test_unsupported_semantics_rejected(self):
        for value in ({'opacity':float('nan')},{'opacity':True},{'opacity':-1},
                      {'blendmode':'Multiply'},{'isolated':False},{'alpha_mask':{'kind':'group'}},
                      {'alpha_mask':'FFFFFF'},{'alpha_mask':{'kind':'solid','color':'FFFFFF'}},
                      {'alpha_mask':{'kind':'solid','color':'000000','alpha':.5}}):
            with self.subTest(value=value),self.assertRaises(ValueError):normalize_compositing(value)

    def test_source_group_does_not_silently_become_normal(self):
        f=component();f['parts'][0]['blendmode']='Multiply'
        with self.assertRaises(ValueError):prepare_component(f)

    def test_regeneration_keeps_original_contours(self):
        f=component();before=copy.deepcopy(f);one,_=component_xml(f,0,0,1,1)
        f['parts'][0]['compositing']['opacity']=.25
        two,_=component_xml(f,0,0,1,1)
        self.assertEqual([x.xml for x in one.findall('.//a:custGeom',NS)],
                         [x.xml for x in two.findall('.//a:custGeom',NS)])
        self.assertEqual(before['parts'][0]['children'],f['parts'][0]['children'])


class MaskFieldTests(unittest.TestCase):
    def test_decode_alpha_and_neutral_luminosity(self):
        a=np.array([[0,255],[128,64]],np.uint8)
        alpha=decode_mask_field(a,meaning='alpha',color_space='alpha')
        rgb=np.repeat(a[:,:,None],3,axis=2)
        np.testing.assert_allclose(alpha,decode_mask_field(rgb,meaning='luminosity',color_space='DeviceRGB'),rtol=0,atol=1e-15)
        self.assertAlmostEqual(alpha[1,0],128/255)

    def test_pdf_device_rgb_luminosity(self):
        rgb=np.array([[[255,0,0],[0,255,0],[0,0,255],[255,255,255]]],np.uint8)
        np.testing.assert_allclose(decode_mask_field(rgb,meaning='luminosity',color_space='DeviceRGB'),
                                   [[.30,.59,.11,1]],rtol=0,atol=1e-15)

    def test_reject_color_interpretation_and_unknown_transfer(self):
        for pixels,meaning,cs,tr in [(np.zeros((2,2),float),'alpha','alpha','identity'),
            (np.array([[[255,0,0]]],np.uint8),'alpha','DeviceRGB','identity'),
            (np.zeros((2,2),np.uint8),'luminosity','ICC','identity'),
            (np.zeros((2,2),np.uint8),'alpha','alpha','gamma')]:
            with self.assertRaises(ValueError):decode_mask_field(pixels,meaning=meaning,color_space=cs,transfer=tr)

    def test_linear_source_mapping_and_quantization(self):
        a=np.broadcast_to((np.arange(80)+.5)/80,(50,80)).copy()
        result=fit_axis_mask(a,axis='x',field_bbox=[10,20,80,50],owner_bbox=[10,20,80,50],stop_count=4,max_abs_error=.00002)
        self.assertLess(result['evidence']['max_abs_error'],.00002)
        self.assertEqual(result['paint']['angle'],0)
        self.assertEqual(result['evidence']['observed_pixels'],4000)
        self.assertEqual(result['evidence']['final_render'],'NOT_VERIFIED')

    def test_owner_frame_is_not_image_frame(self):
        a=np.broadcast_to((np.arange(100)+.5)/100,(100,100)).copy()
        result=fit_axis_mask(a,axis='x',field_bbox=[0,0,100,100],owner_bbox=[25,0,50,100],stop_count=2,max_abs_error=.00001)
        self.assertAlmostEqual(result['paint']['stops'][0]['alpha'],.25)
        self.assertAlmostEqual(result['paint']['stops'][-1]['alpha'],.75)

    def test_y_field_and_reversed_ramp(self):
        a=np.broadcast_to(1-(np.arange(50)+.5)[:,None]/50,(50,80)).copy()
        result=fit_axis_mask(a,axis='y',field_bbox=[0,0,80,50],owner_bbox=[0,0,80,50],stop_count=2,max_abs_error=.00001)
        self.assertEqual(result['paint']['angle'],90)
        self.assertEqual([s['alpha'] for s in result['paint']['stops']],[1,0])

    def test_nonseparable_mask_rejected_not_flattened(self):
        yy,xx=np.indices((50,50));a=((xx+yy)%2).astype(float)
        with self.assertRaisesRegex(ValueError,'not representable'):
            fit_axis_mask(a,axis='x',field_bbox=[0,0,50,50],owner_bbox=[0,0,50,50],stop_count=8,max_abs_error=.01)

    def test_invalid_domain_and_values(self):
        cases=[(np.ones((4,4)),[0,0,5,4],2), (np.full((4,4),np.nan),[0,0,4,4],2),
               (np.ones((4,4)),[0,0,4,4],8)]
        for a,box,n in cases:
            with self.assertRaises(ValueError):fit_axis_mask(a,axis='x',field_bbox=[0,0,4,4],owner_bbox=box,stop_count=n,max_abs_error=.01)


if __name__=='__main__':unittest.main()
