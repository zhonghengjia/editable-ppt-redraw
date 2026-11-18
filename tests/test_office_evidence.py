"""Synthetic saved-package fixtures, not claims of real Office rendering."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Inches

S=Path(__file__).resolve().parents[1]/'scripts';sys.path.insert(0,str(S))
import office_evidence as office
from native_vectors import add_rect_link


def snapshot(deck, root):
    """A clearly synthetic evidence producer for isolated validation tests."""
    p=Presentation(deck)
    slides=[]
    for index,slide in enumerate(p.slides,1):
        render=root/f'slide-{index}.png';Image.new('RGB',(1000,500),'white').save(render)
        shapes=[];bounds=[];connectors=[]
        names={str(s.shape_id):s.name for s in slide.shapes}
        for shape in slide.shapes:
            text=shape.text if shape.has_text_frame else ''
            record={'shape_id':shape.shape_id,'name':shape.name,'rotation':shape.rotation,
                    'box_pt':[v/12700 for v in (shape.left,shape.top,shape.width,shape.height)],'text':text}
            shapes.append(record)
            if text:bounds.append(dict(record))
            if shape._element.tag.endswith('}cxnSp'):
                binding={'name':shape.name,'shape_id':shape.shape_id}
                for prefix,tag in [('begin','stCxn'),('end','endCxn')]:
                    native=shape._element.find('p:nvCxnSpPr/p:cNvCxnSpPr/a:'+tag,office.NS)
                    sid=native.get('id') if native is not None else None
                    binding[prefix+'_connected']=sid is not None
                    binding[prefix+'_shape_id']=int(sid) if sid else None
                    binding[prefix+'_name']=names.get(sid)
                    binding[prefix+'_site']=int(native.get('idx'))+1 if native is not None else None
                connectors.append(binding)
        slides.append({'index':index,'render_path':render.name,'render_sha256':hashlib.sha256(render.read_bytes()).hexdigest(),
                       'shapes':shapes,'text_bounds':bounds,'connectors':connectors,'unverified':[]})
    return {'schema_version':1,'status':'PASS','source_unchanged':True,'artifact_sha256':hashlib.sha256(deck.read_bytes()).hexdigest(),
            'renderer':'Microsoft PowerPoint synthetic unit-test stub','slide_width_pt':p.slide_width/12700,
            'slide_height_pt':p.slide_height/12700,'slides':slides}


class OfficeEvidence(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.deck=self.root/'case.pptx'
        p=Presentation();p.slide_width=Inches(10);p.slide_height=Inches(5)
        slide=p.slides.add_slide(p.slide_layouts[6]);nodes=[]
        for name,x in [('node-a',1),('node-b',5)]:
            node=slide.shapes.add_shape(MSO_SHAPE.RECTANGLE,Inches(x),Inches(1),Inches(2),Inches(1))
            node.name=name;node.text=name;nodes.append(node)
        add_rect_link(slide,*nodes,source_port='right',target_port='left',name='flow-a-b-link')
        p.save(self.deck);self.data=snapshot(self.deck,self.root);self.path=self.root/'office.json';self.save()
    def tearDown(self):self.tmp.cleanup()
    def save(self):self.path.write_text(json.dumps(self.data),encoding='utf-8')
    def adapt(self):return office.layouts(office.read(self.deck,self.path),{'width':1000,'height':500})
    def grammar(self):
        return {'diagram_grammar':{'preserve_visual_type':True,'node_roles':{
            'a':{'allowed_geometries':['rect'],'output_names':['node-a']},
            'b':{'allowed_geometries':['rect'],'output_names':['node-b']}},
            'edge_roles':{'a-b':{'output_name_regex':'^flow-a-b-link$',
                'endpoint_binding':{'source_output_name':'node-a','target_output_name':'node-b'}}}}}
    def runner(self):
        spec=importlib.util.spec_from_file_location('office_runner',S/'run-quality-checks.py')
        mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod
    def test_adapter_joins_saved_ids_types_and_real_bindings(self):
        report=self.adapt();self.assertEqual(report['status'],'BOUND',report)
        doc=report['documents'][0];elements={v['name']:v for v in doc['elements']}
        self.assertEqual(doc['artifact_sha256'],self.data['artifact_sha256'])
        self.assertEqual(elements['node-a']['geometry'],'rect');self.assertEqual(elements['node-a']['bbox'],[100,100,200,100])
        link=elements['flow-a-b-link'];self.assertEqual(link['source_name'],'node-a');self.assertEqual(link['target_name'],'node-b')
        self.assertNotIn('endpoints',link);self.assertFalse(link['route_geometry_supported'])
        self.assertNotIn('source_port',link)
    def test_runner_uses_office_without_external_layout(self):
        manifest=self.root/'manifest.json';manifest.write_text(json.dumps(self.grammar()))
        checks={c['check']:c for c in self.runner().run_checks(self.deck,manifest,office_evidence=self.path)['checks']}
        self.assertEqual(checks['layout_provenance']['status'],'PASS')
        self.assertEqual(checks['diagram_grammar']['status'],'PASS')
    def test_one_shared_envelope_read_for_layout_clearance_and_preview(self):
        manifest=self.grammar();manifest.update(canvas={'width':1000,'height':500},
            text_clearance={'label_names':['node-a','node-b'],'obstacle_names':[],'min_gap_px':0})
        mf=self.root/'manifest.json';mf.write_text(json.dumps(manifest));runner=self.runner();original=runner.load
        def loader(name):return office if name=='office_evidence' else original(name)
        with patch.object(runner,'load',side_effect=loader),patch.object(office,'read',wraps=office.read) as read:
            report=runner.run_checks(self.deck,mf,office_evidence=self.path,clearance_review=self.root/'review.html')
            self.assertEqual(read.call_count,1)
        self.assertEqual(next(c for c in report['checks'] if c['check']=='clearance_review')['status'],'PASS')
    def test_explicit_stale_layout_is_not_silently_replaced(self):
        mf=self.root/'manifest.json';mf.write_text(json.dumps(self.grammar()))
        lf=self.root/'bad.layout.json';lf.write_text(json.dumps({'artifact_sha256':'stale','elements':[]}))
        checks={c['check']:c for c in self.runner().run_checks(self.deck,mf,lf,office_evidence=self.path)['checks']}
        self.assertEqual(checks['layout_provenance']['status'],'NOT_VERIFIED')
        self.assertEqual(checks['diagram_grammar']['status'],'NOT_VERIFIED')
    def test_changed_office_id_or_name_rejected(self):
        self.data['slides'][0]['shapes'][0]['shape_id']=999;self.save()
        self.assertEqual(self.adapt()['status'],'NOT_VERIFIED')
    def test_changed_native_endpoint_or_site_rejected(self):
        original=copy.deepcopy(self.data)
        for field,value in [('begin_shape_id',999),('begin_site',99),('begin_connected',False)]:
            self.data=copy.deepcopy(original);self.data['slides'][0]['connectors'][0][field]=value;self.save()
            self.assertEqual(self.adapt()['status'],'NOT_VERIFIED',field)
    def test_omitted_shape_is_unverified(self):
        self.data['slides'][0]['shapes'].pop();self.save();self.assertEqual(self.adapt()['status'],'NOT_VERIFIED')
    def test_rotated_group_and_unknown_geometry_not_certified(self):
        self.data['slides'][0]['shapes'][0]['ancestor_rotated']=True;self.save()
        report=self.adapt();self.assertEqual(report['status'],'NOT_VERIFIED')
        self.assertTrue(any('rotated' in reason for reason in report['unverified']))
    def test_unknown_geometry_is_not_filled_in_as_rectangle(self):
        p=Presentation(self.deck);shape=p.slides[0].shapes[0]
        geom=shape._element.find('p:spPr/a:prstGeom',office.NS);geom.getparent().remove(geom);p.save(self.deck)
        self.data=snapshot(self.deck,self.root);self.save();report=self.adapt()
        self.assertEqual(report['status'],'NOT_VERIFIED')
        self.assertEqual(report['documents'][0]['elements'][0]['geometry'],'unknown')
    def add_decoration(self):
        p=Presentation(self.deck);builder=p.slides[0].shapes.build_freeform(10,10,scale=12700)
        builder.add_line_segments([(20,15),(10,20)],close=False)
        builder.convert_to_shape().name='decoration';p.save(self.deck)
        self.data=snapshot(self.deck,self.root);self.save()
    def test_unselected_custom_path_does_not_block_verified_nodes_and_binding(self):
        self.add_decoration();mf=self.root/'manifest.json';mf.write_text(json.dumps(self.grammar()))
        checks={c['check']:c for c in self.runner().run_checks(self.deck,mf,office_evidence=self.path)['checks']}
        self.assertEqual(checks['layout_provenance']['status'],'PASS')
        self.assertEqual(checks['diagram_grammar']['status'],'PASS')
        detail=checks['layout_provenance']['detail']
        self.assertEqual(detail['adapter_status'],'NOT_VERIFIED')
        self.assertTrue(any('decoration' in reason for reason in detail['unselected_limitations']))
        self.assertEqual(len(self.adapt()['documents'][0]['elements']),4)
    def test_required_custom_node_keeps_unsupported_status(self):
        self.add_decoration();grammar=self.grammar()
        grammar['diagram_grammar']['node_roles']['decoration']={'allowed_geometries':['custom'],'output_names':['decoration']}
        mf=self.root/'manifest.json';mf.write_text(json.dumps(grammar))
        checks={c['check']:c for c in self.runner().run_checks(self.deck,mf,office_evidence=self.path)['checks']}
        self.assertEqual(checks['layout_provenance']['status'],'NOT_VERIFIED')
        self.assertEqual(checks['diagram_grammar']['status'],'NOT_VERIFIED')
    def test_table_limit_is_retained(self):
        self.data['slides'][0]['unverified'].append('table-cell text bounds are not supported');self.save()
        self.assertEqual(self.adapt()['status'],'NOT_VERIFIED')
        measured=office.text_bounds(office.read(self.deck,self.path),{'width':1000,'height':500})
        self.assertTrue(measured['unverified'])
    def test_unsupported_route_is_not_invented_from_bbox(self):
        p=Presentation(self.deck);link=p.slides[0].shapes[-1]
        link._element.find('p:spPr/a:prstGeom',office.NS).set('prst','bentConnector3');p.save(self.deck)
        self.data=snapshot(self.deck,self.root);self.save()
        manifest=self.grammar();manifest['diagram_grammar']['routing']='orthogonal'
        mf=self.root/'manifest.json';mf.write_text(json.dumps(manifest))
        checks={c['check']:c for c in self.runner().run_checks(self.deck,mf,office_evidence=self.path)['checks']}
        self.assertEqual(checks['orthogonal_routes']['status'],'NOT_VERIFIED')
    def test_partial_slide_evidence_rejected(self):
        p=Presentation(self.deck);p.slides.add_slide(p.slide_layouts[6]);p.save(self.deck)
        self.data=snapshot(self.deck,self.root);self.data['slides'].pop();self.save()
        self.assertEqual(office.read(self.deck,self.path)['status'],'NOT_VERIFIED')
    def test_render_escape_and_non_png_are_rejected(self):
        self.data['slides'][0]['render_path']='../outside.png';self.save()
        self.assertEqual(office.read(self.deck,self.path)['status'],'NOT_VERIFIED')
    def test_hash_matching_non_png_render_is_rejected(self):
        render=self.root/'slide-1.png';Image.new('RGB',(1000,500),'white').save(render,format='JPEG')
        self.data['slides'][0]['render_sha256']=hashlib.sha256(render.read_bytes()).hexdigest();self.save()
        self.assertEqual(office.read(self.deck,self.path)['status'],'NOT_VERIFIED')


if __name__=='__main__':unittest.main()
