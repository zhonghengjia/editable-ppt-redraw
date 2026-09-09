"""Adversarial source-support checks; fixtures are not claimed Office renders."""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import component_geometry as G
import component_fidelity as CF

NODE = os.environ.get('EDITABLE_PPT_NODE') or shutil.which('node')
SELECTOR = dict(rgb=[[0,90],[60,180],[100,240]],differences=[[2,0,40,230]],
                observation='Synthetic blue foreground separated from white background; no occluding text')
CONTRACT = dict(selector=SELECTOR,min_iou=.98,max_boundary_px=1,max_boundary_p95_px=1,
                topology='exact',rationale='Synthetic one-pixel error bound, narrow gap must remain open')


def fixture():
    image = Image.new('RGB',(60,60),'white')
    d = ImageDraw.Draw(image)
    d.rectangle((10,10,45,42),fill='#2277aa')
    d.rectangle((20,20,28,29),fill='white')
    d.rectangle((34,40,35,54),fill='#2277aa')
    return image


class GeometryTests(unittest.TestCase):
    def test_identical_and_boundary_units(self):
        image = fixture()
        report = G.compare(image,image,CONTRACT)
        self.assertTrue(report['passed'])
        self.assertEqual(report['source_topology']['holes'],1)
        self.assertEqual(report['source_topology']['components'],1)
        self.assertEqual(report['boundary_max_px'],0)
        self.assertEqual(report['semantic_segmentation'],'NOT_VERIFIED')
        a = np.zeros((10,10),dtype=bool); b = a.copy()
        a[1,1] = True; b[4,5] = True
        self.assertEqual(G.compare_masks(a,b)['boundary_max_px'],5)

    def test_missing_branch_extra_part_filled_hole_shift(self):
        source = fixture()
        for kind in ('branch','extra','hole','shift'):
            image = source.copy(); d = ImageDraw.Draw(image)
            if kind == 'branch': d.rectangle((34,43,35,54),fill='white')
            elif kind == 'extra': d.rectangle((1,1,3,3),fill='#2277aa')
            elif kind == 'hole': d.rectangle((20,20,28,29),fill='#2277aa')
            else:
                image = Image.new('RGB',source.size,'white'); image.paste(source,(4,0))
            report = G.compare(source,image,CONTRACT)
            self.assertFalse(report['passed'],kind)
            self.assertGreater(report['boundary_max_px'],1,kind)

    def test_closed_one_pixel_gap_changes_topology(self):
        a = Image.new('RGB',(10,10),'white')
        d = ImageDraw.Draw(a); d.rectangle((1,1,8,8),outline='#2277aa'); d.point((4,1),fill='white')
        b = a.copy(); ImageDraw.Draw(b).point((4,1),fill='#2277aa')
        c = dict(CONTRACT,min_iou=.9)
        result = G.compare(a,b,c)
        self.assertEqual(result['source_topology']['holes'],0)
        self.assertEqual(result['render_topology']['holes'],1)
        self.assertFalse(result['passed'])

    def test_complementary_connectivity_and_border(self):
        a = np.eye(3,dtype=bool)
        self.assertEqual(G.topology(a)['components'],1)
        self.assertEqual(G.topology(a)['holes'],0)
        self.assertEqual(G.topology(np.ones((3,3),dtype=bool))['holes'],0)

    def test_empty_and_invalid_masks_cannot_pass(self):
        a = np.zeros((10,10),dtype=bool); b = a.copy(); b[4,4] = True
        full = np.ones_like(a)
        for left,right in ((a,a),(a,b),(b,a),(b,b[:3,:3]),(b.astype(int),b),(full,full),(b,full)):
            with self.assertRaises(ValueError): G.compare_masks(left,right)

    def test_exact_distance_matches_bruteforce(self):
        rng = np.random.default_rng(7)
        for _ in range(5):
            a,b = rng.random((2,12,12)) > .8
            p,q = G.boundary(a),G.boundary(b)
            matrix = np.sqrt(((p[:,None,:]-q[None,:,:])**2).sum(axis=2))
            result = G.distances(a,b)
            self.assertAlmostEqual(result['boundary_max_px'],max(matrix.min(axis=0).max(),matrix.min(axis=1).max()))

    def test_resource_bound_never_subsamples(self):
        a = np.eye(20,dtype=bool)
        with patch.object(G,'MAX_PAIRS',10):
            with self.assertRaises(G.GeometryLimit): G.compare_masks(a,a)

    def test_color_change_can_preserve_geometry_but_not_color_gate(self):
        source = fixture(); other = source.copy()
        arr = np.array(other); arr[(arr == [34,119,170]).all(axis=2)] = [70,170,230]
        self.assertTrue(G.compare(source,Image.fromarray(arr),CONTRACT)['passed'])

    def test_signed_channel_math_and_transparency(self):
        image = Image.new('RGB',(2,1)); image.putdata([(250,80,110),(0,80,110)])
        selector = dict(SELECTOR,rgb=[[0,255],[0,255],[0,255]])
        self.assertEqual(G.select(image,selector).tolist(),[[False,True]])
        transparent = Image.new('RGBA',(1,1),(34,119,170,0))
        self.assertFalse(G.select(transparent,SELECTOR).any())

    def test_contract_rejects_typos_nonfinite_and_disabled_gate(self):
        for key,value in [('min_iou',0),('max_boundary_px',float('nan')),('max_boundary_p95_px',True),('topology','ignore'),('rationale','')]:
            self.assertTrue(G.validate_structure(dict(CONTRACT,**{key:value})),key)
        for recipe in (None,dict(SELECTOR,extra=1),dict(SELECTOR,differences=[[0,0,0,1]]),dict(SELECTOR,rgb=[[0,256]]*3)):
            self.assertTrue(G.selector_errors(recipe))

    def test_structural_inventory_requires_contract(self):
        value = dict(mode='faithful',source_inventory=[dict(id='part',structure_sensitive=True)],
                     regional_fidelity=dict(source_size=[60,60],source_sha256='0'*64,regions=[
                         dict(id='part',source_bbox=[0,0,60,60],features=['gap'],threshold=.1,window=4,
                              max_mismatch_ratio=.1,max_window_ratio=.3,rationale='source')]))
        self.assertTrue(CF.validate_contract(value))
        value['regional_fidelity']['regions'][0]['structure'] = copy.deepcopy(CONTRACT)
        self.assertFalse(CF.validate_contract(value))
        del value['regional_fidelity']
        self.assertTrue(CF.validate_contract(value))

    @unittest.skipUnless(NODE,'existing Node required')
    def test_selector_trace_is_source_bound_deterministic_and_keeps_hole(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); source = root/'source.png'; fixture().save(source)
            first = CF.trace_component(source,root/'one.svg',[0,0,60,60],2,NODE,SELECTOR)
            second = CF.trace_component(source,root/'two.svg',[0,0,60,60],2,NODE,SELECTOR)
            self.assertEqual(first['svg_sha256'],second['svg_sha256'])
            self.assertEqual(first['source_sha256'],CF.digest(source))
            self.assertEqual(first['selection']['topology']['holes'],1)
            self.assertEqual(first['selection']['mask_sha256'],hashlib.sha256(G.select(fixture(),SELECTOR).tobytes()).hexdigest())
            self.assertFalse(first['semantics_verified'])
            import native_vectors as NV
            specs,_,_ = NV.read_vectors(root/'one.svg')
            self.assertTrue(any(sum(c.cmd=='M' for c in spec['commands'])>1 for spec in specs))
            for recipe in (dict(SELECTOR,rgb=[[0,0]]*3),dict(SELECTOR,rgb=[[0,255]]*3,differences=[])):
                with self.assertRaises(ValueError): CF.trace_component(source,root/'bad.svg',[0,0,60,60],2,NODE,recipe)

    @unittest.skipUnless(NODE,'existing Node required')
    def test_color_gate_still_blocks_and_limit_is_unverified(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); source = fixture(); source.save(root/'source.png')
            arr = np.array(source); arr[(arr == [34,119,170]).all(axis=2)] = [70,170,230]
            Image.fromarray(arr).save(root/'render.png'); (root/'artifact.bin').write_bytes(b'synthetic fixture')
            region = dict(id='part',source_bbox=[0,0,60,60],features=['gap'],threshold=.01,window=4,
                          max_mismatch_ratio=.01,max_window_ratio=.01,rationale='fixed test',structure=CONTRACT)
            manifest = dict(mode='faithful',source={'path':'source.png'},source_inventory=[dict(id='part',structure_sensitive=True)],
                            regional_fidelity=dict(source_size=[60,60],source_sha256=CF.digest(root/'source.png'),regions=[region]))
            evidence = dict(artifact_sha256=CF.digest(root/'artifact.bin'),render_path='render.png',render_sha256=CF.digest(root/'render.png'),
                            rendered_from_final_artifact=True,renderer='synthetic fixture only; not an actual renderer')
            (root/'evidence.json').write_text(json.dumps(evidence))
            result = CF.audit_fidelity(root/'artifact.bin',manifest,root/'manifest.json',root/'evidence.json',NODE)
            self.assertEqual(result['regions'][0]['structure_status'],'PASS')
            self.assertFalse(result['regions'][0]['color_passed'])
            self.assertFalse(result['valid'])
            with patch.object(G,'MAX_PAIRS',1):
                result = CF.audit_fidelity(root/'artifact.bin',manifest,root/'manifest.json',root/'evidence.json',NODE)
            self.assertEqual(result['regions'][0]['structure_status'],'NOT_VERIFIED')
            self.assertTrue(result['unverified'])
            self.assertFalse(result['regions'][0]['passed'])


if __name__ == '__main__': unittest.main()
