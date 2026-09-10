import hashlib
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from source_partition import marked_partition, build_source_partition
from component_geometry import coverage_changes, compare, GeometryLimit

def markers():
    return [{'id':'left','observation':'synthetic left region','seeds':[[2,4]]},
            {'id':'right','observation':'synthetic right region','seeds':[[9,4]]}]

class PartitionTests(unittest.TestCase):
    def setUp(self):
        self.image=Image.new('RGB',(12,10),(160,80,70))
        self.image.paste((70,90,160),(6,0,12,10))
        self.support=np.ones((10,12),bool)

    def test_common_coverage_and_color_boundary(self):
        labels,e=marked_partition(self.image,self.support,markers())
        self.assertTrue(np.all(labels[:,:6]==1));self.assertTrue(np.all(labels[:,6:]==2))
        self.assertEqual(e['unassigned_pixels'],0)
        self.assertEqual(e['assigned_pixels'],120)

    def test_real_hole_and_disjoint_support_remain(self):
        self.support[2:4,4:6]=False
        labels,e=marked_partition(self.image,self.support,markers())
        self.assertTrue(np.array_equal(labels>0,self.support))
        self.assertEqual(coverage_changes(self.support,labels>0)['introduced_hole_pixels'],0)

    def test_unseeded_island_fails(self):
        self.support[:]=False;self.support[4,2]=True;self.support[4,9]=True;self.support[8,8]=True
        with self.assertRaisesRegex(ValueError,'unseeded'):marked_partition(self.image,self.support,markers())

    def test_duplicate_outside_empty_seed_fail(self):
        bads=[[],[dict(markers()[0],seeds=[[12,4]])],
              [markers()[0],dict(markers()[1],seeds=[[2,4]])]]
        for bad in bads:
            with self.subTest(bad=bad),self.assertRaises(ValueError):marked_partition(self.image,self.support,bad)

    def test_operation_budget_is_not_silent_partial(self):
        with patch('source_partition.MAX_OPERATIONS',2),self.assertRaises(GeometryLimit):
            marked_partition(self.image,self.support,markers())

    def test_deterministic_source_not_output_driven(self):
        a,ea=marked_partition(self.image,self.support,markers())
        b,eb=marked_partition(self.image,self.support,markers())
        self.assertTrue(np.array_equal(a,b));self.assertEqual(ea['label_sha256'],eb['label_sha256'])

    def test_real_native_components_and_hash_binding(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'source.png';support=root/'support.png'
            self.image.save(source);Image.fromarray(self.support.astype('uint8')*255).save(support)
            plan=dict(source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),source_bbox=[0,0,12,10],
                support_sha256=hashlib.sha256(support.read_bytes()).hexdigest(),support_observation='synthetic rectangle',
                markers=markers(),colors_per_part=4,max_native_paths=20,max_native_commands=100)
            comps,labels,e=build_source_partition(source,support,plan)
            self.assertEqual(len(comps),2);self.assertEqual(e['native_paths'],2)
            self.assertEqual(e['unassigned_pixels'],0)
            stacked,stack_labels,stack_e=build_source_partition(source,support,dict(plan,representation='palette_stack'))
            np.testing.assert_array_equal(labels,stack_labels)
            self.assertEqual(stack_e['representation'],'palette_stack')
            self.assertEqual(len(stacked),len(comps))
            self.assertTrue(all(p['composition']=='opaque_source_color_tree' for p in stack_e['parts']))
            bad=dict(plan,source_sha256='0'*64)
            with self.assertRaisesRegex(ValueError,'mismatch'):build_source_partition(source,support,bad)
            bad=dict(plan,max_native_paths=1)
            with self.assertRaises(GeometryLimit):build_source_partition(source,support,bad)

class CoverageTests(unittest.TestCase):
    def test_new_hole(self):
        a=np.ones((10,10),bool);b=a.copy();b[4:6,4:6]=False
        result=coverage_changes(a,b)
        self.assertEqual(result['introduced_hole_pixels'],4)
        self.assertEqual(result['introduced_holes'][0]['bbox'],[4,4,2,2])

    def test_filled_real_hole(self):
        a=np.ones((10,10),bool);a[4:6,4:6]=False
        result=coverage_changes(a,np.ones_like(a))
        self.assertEqual(result['filled_source_hole_pixels'],4)

    def test_same_hole_count_different_positions_not_pass(self):
        a=np.ones((10,10),bool);a[2,2]=False;b=np.ones_like(a);b[7,7]=False
        r=coverage_changes(a,b)
        self.assertEqual(r['introduced_hole_pixels'],1);self.assertEqual(r['filled_source_hole_pixels'],1)

    def test_edge_open_crack_is_retained_not_called_hole(self):
        a=np.ones((10,10),bool);b=a.copy();b[:5,4]=False
        r=coverage_changes(a,b)
        self.assertEqual(r['introduced_hole_pixels'],0)
        self.assertEqual(r['missing_support_regions'][0]['area'],5)

    def test_unchanged_real_hole(self):
        a=np.ones((10,10),bool);a[4:6,4:6]=False;r=coverage_changes(a,a.copy())
        self.assertEqual(r['introduced_hole_pixels'],0);self.assertEqual(r['filled_source_hole_pixels'],0)

    def test_coverage_is_additional_gate(self):
        a=np.zeros((12,12,3),dtype=np.uint8)+255;a[1:11,1:11]=[100,50,50]
        b=a.copy();b[5,5]=255
        spec=dict(selector=dict(rgb=[[0,150],[0,150],[0,150]],differences=[],observation='synthetic foreground'),
            min_iou=.9,max_boundary_px=20,max_boundary_p95_px=20,topology='report_only',rationale='test fixture',
            coverage=dict(max_introduced_hole_pixels=0,max_filled_source_hole_pixels=0))
        r=compare(Image.fromarray(a),Image.fromarray(b),spec)
        self.assertFalse(r['passed']);self.assertFalse(r['coverage']['passed'])

if __name__=='__main__':unittest.main()
