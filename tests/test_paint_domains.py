import copy
import shutil
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from native_components import component_xml,prepare_component
from native_paint import centered_radial_paint,normalize_paint,paint_xml
from native_support import fill_stroke_union
from vendor.svg_paths.drawingml_paths import parse_svg_path,path_bounds,normalize_path_commands,svg_path_to_absolute

NS={'a':'http://schemas.openxmlformats.org/drawingml/2006/main','p':'http://schemas.openxmlformats.org/presentationml/2006/main'}
def fixture():
    return dict(id='fixture',output_name='fixture',viewbox=[0,0,100,100],parts=[dict(id='owner',role='surface',observation='Synthetic common paint domain',
        group_fill=dict(kind='linear',angle=90,stops=[dict(position=0,color='000000'),dict(position=1,color='FFFFFF')]),
        children=[dict(id='body',role='host',observation='Real visible host defines domain',d='M0 0 L100 0 L100 100 L0 100 Z',fill='808080'),
                  dict(id='fragment',role='shade',observation='Partial coverage inherits host paint',d='M10 70 L80 70 L80 95 L10 95 Z',fill=dict(kind='group'))])])

class DomainTests(unittest.TestCase):
    def test_shared_domain_not_fragment_rebasing(self):
        tree,mapping=component_xml(fixture(),0,0,1,1,start_id=8)
        group=tree.find('p:grpSp',NS)
        self.assertIsNotNone(group.find('p:grpSpPr/a:gradFill',NS))
        child=group.findall('p:sp',NS)[1]
        self.assertIsNotNone(child.find('p:spPr/a:grpFill',NS))
        self.assertIsNone(child.find('p:spPr/a:gradFill',NS))
        self.assertEqual(len(mapping['element_map']),2)
        self.assertEqual(len(tree.findall('.//p:pic',NS)),0)

    def test_orphan_fill_and_stroke_rejected(self):
        for change in ('owner','stroke'):
            f=fixture()
            if change=='owner':del f['parts'][0]['group_fill']
            else:f['parts'][0]['children'][0]['stroke']={'kind':'group'}
            with self.assertRaises(ValueError):prepare_component(f)

    def test_nested_inheritance_and_transform(self):
        f=fixture();owner=f['parts'][0];child=owner['children'].pop()
        owner['children'].append(dict(id='nested',role='part',observation='Inherited synthetic fragment',translate=[2,3],scale=.5,children=[child]))
        tree,_=component_xml(f,0,0,1,1)
        nested=tree.find('p:grpSp/p:grpSp',NS)
        self.assertIsNotNone(nested.find('p:grpSpPr/a:grpFill',NS))
        off=nested.find('p:sp/p:spPr/a:xfrm/a:off',NS)
        self.assertEqual(int(off.get('x')),round(7*.96*9525))

    def test_radius_mapping_not_mutating_old_office_path(self):
        stops=[dict(position=0,color='FFFFFF'),dict(position=.5,color='808080'),dict(position=1,color='000000')]
        old=copy.deepcopy(stops)
        paint=centered_radial_paint(stops,50,[0,0,100,100])
        self.assertAlmostEqual(paint['stops'][-2]['position'],2**-.5)
        self.assertEqual(stops,old)
        self.assertEqual(paint['stops'][-1]['color'],'000000')
        self.assertEqual(normalize_paint(dict(kind='path',focus=[.5,.5],stops=stops))['stops'][-1]['position'],1)

    def test_radius_and_owner_fail_closed(self):
        stops=[dict(position=0,color='FFFFFF'),dict(position=1,color='000000')]
        for r,b in [(100,[0,0,100,100]),(float('nan'),[0,0,100,100]),(1,[0,0,0,100])]:
            with self.assertRaises(ValueError):centered_radial_paint(stops,r,b)
        with self.assertRaises(ValueError):paint_xml({'kind':'group'},.5)
        f=fixture();f['parts'][0]['group_fill']={'kind':'group'}
        with self.assertRaises(ValueError):prepare_component(f)

    def test_group_sample_provenance_remains_on_group(self):
        f=fixture();fill=f['parts'][0]['group_fill'];fill['source_samples']=dict(sha256='a'*64,size=[2,1],patches=[[0,0,1,1],[1,0,1,1]])
        prepared,_,_=prepare_component(f)
        self.assertEqual(prepared[0]['group_fill']['source_samples'],fill['source_samples'])

    def test_group_paint_regeneration_changes_owner_not_child_geometry(self):
        f=fixture();first,_=component_xml(f,0,0,1,1)
        f['parts'][0]['group_fill']['stops'][0]['color']='123456'
        second,_=component_xml(f,0,0,1,1)
        self.assertEqual([e.xml for e in first.findall('.//p:sp',NS)],
                         [e.xml for e in second.findall('.//p:sp',NS)])
        a=first.find('p:grpSp/p:grpSpPr/a:gradFill',NS)
        b=second.find('p:grpSp/p:grpSpPr/a:gradFill',NS)
        self.assertNotEqual(a.xml,b.xml)

class CoverageTests(unittest.TestCase):
    def test_invalid_geometry_before_external_call(self):
        for d in ['M0 0 L10 0','M0 0 L10 0 M5 5 L8 8 Z','M0 NaN Z']:
            with self.assertRaises(ValueError):fill_stroke_union(d,1,tolerance=.001)

    @unittest.skipUnless(shutil.which('powershell.exe'),'Windows WPF unavailable')
    def test_source_stroke_width_controls_union(self):
        result=fill_stroke_union('M0 0 L10 0 L10 10 L0 10 Z',2,tolerance=.001)
        for actual,expected in zip(result['bounds'],[-1,-1,11,11]):self.assertAlmostEqual(actual,expected,places=3)
        self.assertEqual(result['fill_rule'],'Nonzero')
        self.assertLess(result['commands'],5000)
        self.assertIn('PresentationCore',result['engine'])

if __name__=='__main__':unittest.main()
