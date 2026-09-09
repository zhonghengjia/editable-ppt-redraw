import copy
import hashlib
import importlib.util
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import surface_relations as mod


class SurfaceRelations(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root/'source.bin').write_bytes(b'synthetic reference, no private pixels')
        self.m = {'source': {'path':'source.bin','width':100,'height':100},
                  'source_inventory':[{'id':'band','surface_detail':True}],
                  'surface_relations':{'source_sha256':hashlib.sha256((self.root/'source.bin').read_bytes()).hexdigest(),
                  'relations':[{'id':'r','source_inventory_id':'band','host_name':'body','detail_name':'band',
                                'host_landmarks':[[10,10],[40,10],[40,60],[10,60]],
                                'detail_landmarks':[[15,20],[20,20],[20,45],[15,45]],
                                'max_landmark_error_px':.1,'max_escape_px':.1,
                                'occluders':['front'],'source_observation':'Synthetic rectangular surface with stripe'}]}}

    def tearDown(self):
        self.tmp.cleanup()

    def deck(self, shift=0, order=('body','band','front'), duplicate=False, rotation=0):
        a='http://schemas.openxmlformats.org/drawingml/2006/main'
        p='http://schemas.openxmlformats.org/presentationml/2006/main'
        geometry={'body':[(10,10),(40,10),(40,60),(10,60)],
                  'band':[(15+shift,20),(20+shift,20),(20+shift,45),(15+shift,45)],
                  'front':[(17,10),(19,10),(19,60),(17,60)]}
        shapes=[]
        for k,name in enumerate(list(order)+(['band'] if duplicate else [])):
            pts=geometry[name]
            commands=''.join(f'<a:{"moveTo" if j==0 else "lnTo"}><a:pt x="{x}" y="{y}"/></a:{"moveTo" if j==0 else "lnTo"}>' for j,(x,y) in enumerate(pts))
            shapes.append(f'<p:sp><p:nvSpPr><p:cNvPr id="{k+1}" name="{name}"/></p:nvSpPr><p:spPr><a:xfrm rot="{rotation}"><a:off x="0" y="0"/><a:ext cx="100" cy="100"/></a:xfrm><a:custGeom><a:pathLst><a:path w="100" h="100">{commands}<a:close/></a:path></a:pathLst></a:custGeom></p:spPr></p:sp>')
        path=self.root/'test.pptx'
        with zipfile.ZipFile(path,'w') as z:
            z.writestr('ppt/presentation.xml',f'<p:presentation xmlns:p="{p}"><p:sldSz cx="100" cy="100"/></p:presentation>')
            z.writestr('ppt/slides/slide1.xml',f'<p:sld xmlns:p="{p}" xmlns:a="{a}"><p:cSld><p:spTree>{"".join(shapes)}</p:spTree></p:cSld></p:sld>')
        return path

    def audit(self, **kwargs):
        return mod.audit(self.deck(**kwargs),self.m,self.root/'manifest.json')

    def test_valid_actual_native(self):
        result=self.audit(); self.assertTrue(result['valid']); self.assertFalse(result['unverified'])

    def test_detached_detail(self):
        result=self.audit(shift=30); self.assertFalse(result['valid']); self.assertGreater(result['relations'][0]['max_escape_px'],0)

    def test_shifted_within_host(self):
        result=self.audit(shift=4); self.assertFalse(result['valid']); self.assertEqual(result['relations'][0]['max_escape_px'],0)

    def test_wrong_order(self):
        self.assertFalse(self.audit(order=('body','front','band'))['valid'])

    def test_host_after_detail(self):
        self.assertFalse(self.audit(order=('band','body','front'))['valid'])

    def test_duplicate_identity(self):
        self.assertFalse(self.audit(duplicate=True)['valid'])

    def test_rotation_unverified(self):
        self.assertTrue(self.audit(rotation=60000)['unverified'])

    def test_source_hash(self):
        self.m['surface_relations']['source_sha256']='0'*64
        self.assertFalse(self.audit()['valid'])

    def test_missing_contract(self):
        del self.m['surface_relations']; self.assertTrue(mod.validate_contract(self.m))

    def test_uncovered_detail(self):
        self.m['source_inventory'].append({'id':'other','surface_detail':True})
        self.assertTrue(mod.validate_contract(self.m))

    def test_nonfinite_tolerance(self):
        self.m['surface_relations']['relations'][0]['max_escape_px']=float('nan')
        self.assertTrue(mod.validate_contract(self.m))

    def test_unknown_host(self):
        self.m['surface_relations']['relations'][0]['host_name']='absent'
        self.assertFalse(self.audit()['valid'])

    def test_concave_host_chord(self):
        host=[(0,0),(10,0),(10,10),(6,10),(6,4),(4,4),(4,10),(0,10)]
        detail=[(2,8),(8,8),(8,9),(2,9)]
        self.assertTrue(all(mod.inside(p,host) for p in detail))
        self.assertTrue(any(not mod.inside(p,host) for p in mod.samples(detail)))

    def test_invalid_inventory_type(self):
        self.m['source_inventory']=None; self.assertTrue(mod.validate_contract(self.m))


if __name__=='__main__':
    unittest.main()
