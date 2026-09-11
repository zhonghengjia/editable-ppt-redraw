"""Observed color ownership survives before the existing native tracing stage."""
import json,os,sys,tempfile,unittest
from pathlib import Path
import numpy as np
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import component_fidelity as C
import native_vectors as V

class SourceAppearanceTests(unittest.TestCase):
    def fixture(self):
        a=np.zeros((16,16,4),dtype=np.uint8)
        a[:]=[210,180,220,255]
        a[3:12,3:12]=[170,120,190,255]
        a[6:8,3:12]=[120,70,150,100]
        mask=np.ones((16,16),dtype=bool);mask[0,:]=False;mask[8,8]=False
        return Image.fromarray(a),mask

    def test_color_alpha_and_fine_line_unchanged(self):
        image,mask=self.fixture();result=np.array(C.retain_source_paint(image,mask))
        np.testing.assert_array_equal(result[mask],np.array(image)[mask])
        self.assertEqual(len(np.unique(result[mask],axis=0)),3)

    def test_hole_and_exterior_are_not_filled(self):
        image,mask=self.fixture();result=np.array(C.retain_source_paint(image,mask))
        self.assertTrue(np.all(result[~mask]==0))

    def test_no_soft_alpha_threshold(self):
        image,mask=self.fixture();a=np.array(image);a[5,5,3]=1
        self.assertEqual(np.array(C.retain_source_paint(Image.fromarray(a),mask))[5,5,3],1)

    def test_invalid_ownership_arrays(self):
        image,mask=self.fixture()
        for bad in (mask.astype(np.uint8),np.ones((5,5),bool),np.zeros_like(mask)):
            with self.assertRaises(ValueError):C.retain_source_paint(image,bad)

    def spec(self,path):return dict(path=str(path),sha256=C.digest(path),observation='Synthetic visible owner with one genuine hole')

    def test_mask_hash_is_checked(self):
        with tempfile.TemporaryDirectory() as f:
            p=Path(f)/'m.png';Image.new('L',(16,16),255).save(p)
            spec=self.spec(p);spec['sha256']='0'*64
            with self.assertRaisesRegex(ValueError,'hash'):C.supplied_support(self.fixture()[0],spec)

    def test_binary_shape_and_size_checked(self):
        with tempfile.TemporaryDirectory() as f:
            p=Path(f)/'m.png'
            for mode,size,value in [('L',(16,16),128),('L',(15,16),255),('RGB',(16,16),'white')]:
                Image.new(mode,size,value).save(p)
                with self.assertRaises(ValueError):C.supplied_support(self.fixture()[0],self.spec(p))

    def test_supplied_mask_roundtrip(self):
        image,mask=self.fixture()
        with tempfile.TemporaryDirectory() as f:
            p=Path(f)/'m.png';Image.fromarray(mask.astype('uint8')*255).save(p)
            result,evidence=C.supplied_support(image,self.spec(p))
            np.testing.assert_array_equal(np.array(result)[mask],np.array(image)[mask])
            self.assertTrue(evidence['paint_preserved_before_quantization'])

    def test_source_paint_requires_observed_plan(self):
        with tempfile.TemporaryDirectory() as f:
            src=Path(f)/'s.png';self.fixture()[0].save(src)
            with self.assertRaisesRegex(ValueError,'part plan'):
                C.trace_component(src,Path(f)/'o.svg',[0,0,16,16],source_support={})

    def test_single_ownership_authority(self):
        with tempfile.TemporaryDirectory() as f:
            src=Path(f)/'s.png';self.fixture()[0].save(src)
            with self.assertRaisesRegex(ValueError,'one source ownership'):
                C.trace_component(src,Path(f)/'o.svg',[0,0,16,16],selector={},source_support={})

    def test_native_trace_keeps_multiple_paints_and_hole(self):
        image,mask=self.fixture()
        # Opaque variant qualifies the existing stacked source-color engine.
        a=np.array(image);a[:,:,3]=255;image=Image.fromarray(a)
        with tempfile.TemporaryDirectory() as f:
            r=Path(f);src=r/'s.png';image.save(src);p=r/'m.png';Image.fromarray(mask.astype('uint8')*255).save(p)
            plan=dict(part_id='cell',observation='Observed synthetic colored host and inner detail',source_sha256=C.digest(src),source_bbox=[0,0,16,16],max_native_paths=50,max_native_commands=500)
            result=C.trace_component(src,r/'o.svg',[0,0,16,16],colors=8,node=os.environ.get('EDITABLE_PPT_NODE'),representation='palette_stack',part_plan=plan,source_support=self.spec(p))
            specs,_,_=V.read_vectors(r/'o.svg')
            self.assertGreaterEqual(len({s['fill'] for s in specs}),3)
            self.assertEqual(result['geometry_basis'],'source_visible_ownership_and_paint')
            self.assertIn('selection',json.loads((r/'o.trace.json').read_text()))

if __name__=='__main__':unittest.main()
