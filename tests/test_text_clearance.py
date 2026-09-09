import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

S=Path(__file__).resolve().parents[1]/'scripts';sys.path.insert(0,str(S))
import text_clearance as mod

class Clearance(unittest.TestCase):
    def test_segment_crosses_with_both_ends_outside(self):
        self.assertTrue(mod.path_hits_box([[-5,5],[15,5]],[0,0,10,10]))
    def test_away(self):
        self.assertFalse(mod.path_hits_box([[-5,-2],[15,-2]],[0,0,10,10],1))
    def test_stroke_padding(self):
        self.assertTrue(mod.path_hits_box([[-5,-2],[15,-2]],[0,0,10,10],2))
    def test_arrowhead(self):
        self.assertTrue(mod.path_hits_box([[11,0],[8,5],[11,10]],[0,0,10,10],0,True))
    def test_whole_label_covered(self):
        self.assertTrue(mod.path_hits_box([[-5,-5],[15,-5],[15,15],[-5,15]],[0,0,10,10],0,True))
    def test_safe_adjacent_labels(self):
        self.assertFalse(mod.boxes_overlap([0,0,10,10],[12,0,10,10],1))
    def test_label_collision(self):
        self.assertTrue(mod.boxes_overlap([0,0,10,10],[9,1,10,10],0))
    def test_nan(self):
        self.assertTrue(mod.validate_contract({'text_clearance':{'label_names':['L'],'obstacle_names':['O'],'min_gap_px':float('nan')}}))
    def test_duplicate(self):
        self.assertTrue(mod.validate_contract({'text_clearance':{'label_names':['L','L'],'obstacle_names':['O'],'min_gap_px':1}}))
    def test_inventory_coverage(self):
        self.assertTrue(mod.validate_contract({'source_inventory':[{'role':'text','output_name':'omitted'}],'text_clearance':{'label_names':['L'],'obstacle_names':['O'],'min_gap_px':1}}))
    def test_explicit_no_path_obstacles(self):
        self.assertFalse(mod.validate_contract({'text_clearance':{'label_names':['L'],'obstacle_names':[],'min_gap_px':1}}))
    def test_invalid_inventory(self):
        self.assertTrue(mod.validate_contract({'source_inventory':None,'text_clearance':{'label_names':['L'],'obstacle_names':[],'min_gap_px':1}}))

    def run_native(self,end_y=15,rotation=0,missing=False):
        a='http://schemas.openxmlformats.org/drawingml/2006/main';p='http://schemas.openxmlformats.org/presentationml/2006/main'
        with tempfile.TemporaryDirectory() as d:
            deck=Path(d)/'case.pptx'
            label='<p:sp><p:nvSpPr><p:cNvPr id="1" name="L"/></p:nvSpPr><p:spPr><a:xfrm><a:off x="10" y="10"/><a:ext cx="20" cy="10"/></a:xfrm></p:spPr><p:txBody><a:p><a:r><a:t>TEXT</a:t></a:r></a:p></p:txBody></p:sp>'
            obstacle=f'<p:sp><p:nvSpPr><p:cNvPr id="2" name="O"/></p:nvSpPr><p:spPr><a:xfrm rot="{rotation}"><a:off x="0" y="0"/><a:ext cx="100" cy="100"/></a:xfrm><a:custGeom><a:pathLst><a:path w="100" h="100"><a:moveTo><a:pt x="0" y="{end_y}"/></a:moveTo><a:lnTo><a:pt x="40" y="{end_y}"/></a:lnTo></a:path></a:pathLst></a:custGeom><a:ln w="1"/></p:spPr></p:sp>'
            with zipfile.ZipFile(deck,'w') as z:
                z.writestr('ppt/presentation.xml',f'<p:presentation xmlns:p="{p}"><p:sldSz cx="100" cy="100"/></p:presentation>')
                z.writestr('ppt/slides/slide1.xml',f'<p:sld xmlns:p="{p}" xmlns:a="{a}"><p:cSld><p:spTree>{label}{obstacle}</p:spTree></p:cSld></p:sld>')
            return mod.audit(deck,{'canvas':{'width':100,'height':100},'text_clearance':{'label_names':['L'],'obstacle_names':['missing' if missing else 'O'],'min_gap_px':1}})
    def test_native_failure(self):self.assertFalse(self.run_native()['valid'])
    def test_native_pass(self):self.assertTrue(self.run_native(end_y=5)['valid'])
    def test_native_missing(self):self.assertFalse(self.run_native(missing=True)['valid'])
    def test_native_rotation_unverified(self):self.assertTrue(self.run_native(rotation=60000)['unverified'])

if __name__=='__main__':unittest.main()
