"""Source-state and continuous native-paint regression, without remote data."""
import copy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from native_paint import normalize_paint, paint_xml, sampled_paints
from pdf_paint_scene import extract_page
from vendor.svg_paths.drawingml_paths import (PathCommand, path_bounds, path_commands_to_drawingml)


def gradient():
    return dict(kind='linear', angle=90, stops=[dict(position=0,color='204060'),
                                              dict(position=.3,color='6080A0'),
                                              dict(position=1,color='A0C0E0')])


class CompositeTests(unittest.TestCase):
    def expression(self, mode='multiply'):
        return dict(kind='composite', mode=mode, backdrop=gradient(),
                    source=dict(kind='solid',color='804020',alpha=.5),opacity=.6)

    def test_compilation_matches_independent_pixel_equations(self):
        for mode in ('normal','multiply','screen'):
            source=self.expression(mode); before=copy.deepcopy(source)
            out=normalize_paint(source)
            self.assertEqual(source, before)
            self.assertEqual(out['angle'], 90)
            for old,new in zip(gradient()['stops'],out['stops']):
                b=[int(old['color'][k:k+2],16) for k in (0,2,4)]
                s=[128,64,32]; a=.3
                expected=[round((1-a)*v+a*(w if mode=='normal' else v*w/255 if mode=='multiply' else 255-(255-v)*(255-w)/255)) for v,w in zip(b,s)]
                self.assertEqual(new['color'], ''.join(f'{v:02X}' for v in expected))
                self.assertEqual(new['position'], old['position'])
            xml=paint_xml(source)
            self.assertIn('<a:gradFill',xml); self.assertNotIn('blip',xml)

    def test_midpoint_remains_continuous_with_rounding_bound(self):
        out=normalize_paint(self.expression())
        for i in range(2):
            for channel in (0,2,4):
                ends=[int(s['color'][channel:channel+2],16) for s in gradient()['stops'][i:i+2]]
                actual=sum(int(s['color'][channel:channel+2],16) for s in out['stops'][i:i+2])/2
                c=int('804020'[channel:channel+2],16)/255
                expected=sum(ends)/2*(.7+.3*c)
                self.assertLessEqual(abs(actual-expected),.5)

    def test_changed_source_recomputes_not_cached(self):
        value=self.expression(); first=normalize_paint(value)
        value['source']['color']='FFFFFF'
        self.assertNotEqual(first, normalize_paint(value))
        self.assertEqual(normalize_paint(value), normalize_paint(gradient()))

    def test_reject_unsupported_not_solid_fallback(self):
        variants=[]
        p=self.expression(); p['source']=gradient(); variants.append(p)
        p=self.expression(); p['backdrop']['stops'][0]['alpha']=.8; variants.append(p)
        for field,value in [('mode','overlay'),('opacity',float('nan')),('domain',[0,0,1,1])]:
            p=self.expression();p[field]=value;variants.append(p)
        p=self.expression()
        for _ in range(9):p=dict(kind='composite',mode='normal',backdrop=p,source='FFFFFF')
        variants.append(p)
        for value in variants:
            with self.subTest(value=str(value)[:80]),self.assertRaises(ValueError):normalize_paint(value)

    def test_provenance_remains_on_input_not_computed_colors(self):
        p=self.expression()
        evidence=dict(sha256='a'*64,size=[3,1],patches=[[0,0,1,1],[1,0,1,1],[2,0,1,1]])
        p['backdrop']['source_samples']=evidence
        self.assertEqual(sampled_paints(p),[p['backdrop']])
        self.assertNotIn('source_samples',normalize_paint(p))


class BoundsTests(unittest.TestCase):
    def test_extrema_not_controls_and_cubic_preserved(self):
        commands=[PathCommand('M',[0,0]),PathCommand('C',[0,100,100,100,100,0]),PathCommand('Z',[])]
        self.assertEqual(path_bounds(commands),(0,0,100,75))
        xml,x,y,w,h=path_commands_to_drawingml(commands)
        self.assertEqual((x,y,w,h),(0,0,100,75));self.assertIn('cubicBezTo',xml)
        self.assertEqual(path_commands_to_drawingml(commands,10,20,-2,3)[1:],(-190,20,200,225))

    def test_degenerate_derivative_and_multiple_subpaths(self):
        commands=[PathCommand('M',[0,0]),PathCommand('C',[1,1,2,2,3,3]),PathCommand('Z',[]),PathCommand('M',[-4,-2]),PathCommand('L',[-3,-1])]
        self.assertEqual(path_bounds(commands),(-4,-2,3,3))

    def test_small_shapes_not_enlarged_to_pixel(self):
        _,_,_,w,h=path_commands_to_drawingml([PathCommand('M',[0,0]),PathCommand('L',[.01,0])])
        self.assertEqual(w,.01);self.assertEqual(h,1/9525)


class FakePage:
    rect=[0,0,100,100]
    def __init__(self, records, display):self.records,self.display=records,display
    def get_drawings(self,extended=False):
        assert extended is True
        return copy.deepcopy(self.records)
    def get_bboxlog(self):return self.display


def path(level,seq,box=None):
    return dict(type='f',level=level,seqno=seq,rect=box or [0,0,10,10],
                fill_opacity=1,fill=[.2,.4,.6],items=[('re',[0,0,10,10],1)])


class SceneTests(unittest.TestCase):
    def test_scope_is_retained_and_sibling_exits(self):
        rows=[dict(type='group',level=0,rect=[-100,-100,200,200],opacity=.5,blendmode='Multiply',isolated=False,knockout=False),
              dict(type='clip',level=1,scissor=[0,0,80,80],items=[('re',[0,0,80,80],1)]),path(2,0),path(0,1)]
        page=FakePage(rows,[('fill-path',[0,0,10,10]),('fill-path',[0,0,10,10]),('fill-image',[0,0,3,3])])
        out=extract_page(page,[1,1,5,5]);a,b=out['paths']
        self.assertEqual(len(a['scopes']),2);self.assertEqual(b['scopes'],[])
        self.assertIn('blend:Multiply',a['scope_hazards']);self.assertIn('group_opacity',a['scope_hazards'])
        self.assertEqual(a['fill_opacity'],1) # Not falsely multiplied to each leaf.
        self.assertEqual(len(out['unresolved_operations']),1)
        self.assertEqual(out['native_conversion_status'],'NOT_PERFORMED')

    def test_fillstroke_covers_two_display_entries_not_shade(self):
        row=path(0,0);row['type']='fs'
        out=extract_page(FakePage([row],[('fill-path',[0,0,10,10]),('stroke-path',[0,0,10,10]),('fill-shade',[0,0,10,10])]))
        self.assertEqual([r['kind'] for r in out['unresolved_operations']],['fill-shade'])

    def test_missing_extended_state_is_error(self):
        row=path(0,0);del row['level']
        with self.assertRaises(ValueError):extract_page(FakePage([row],[]))
        with self.assertRaises(ValueError):extract_page(FakePage([],[]),[10,10,0,0])

    def test_true_bounds_not_control_hull(self):
        row=path(0,0);row['rect']=[0,0,100,100]
        row['items']=[('c',[0,0],[0,100],[100,100],[100,0])]
        out=extract_page(FakePage([row],[('fill-path',[0,0,100,100])]))
        self.assertEqual(out['paths'][0]['tight_bounds'],[0,0,100,75])
        self.assertEqual(out['paths'][0]['rect'],[0,0,100,100])


if __name__=='__main__':unittest.main()
