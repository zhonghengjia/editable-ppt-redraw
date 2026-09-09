"""Conservative label-box versus native paths/labels. Not an OCR or glyph audit."""
import importlib.util
import math
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile


def validate_contract(manifest):
    c = manifest.get('text_clearance')
    if c is None:
        return []
    if not isinstance(c, dict):
        return ['text_clearance must be an object']
    errors = []
    v = c.get('min_gap_px')
    if isinstance(v, bool) or not isinstance(v, (float, int)) or not math.isfinite(v) or not 0 <= v <= 20:
        errors.append('text_clearance.min_gap_px must be finite in 0..20 canvas pixels')
    for key in ('label_names', 'obstacle_names'):
        names = c.get(key)
        if not isinstance(names, list) or (key=='label_names' and not names) or len(names)>2000 or any(not isinstance(n,str) or not n.strip() for n in names):
            errors.append(f'text_clearance.{key} needs a bounded exact-name list; labels must not be empty')
        elif len(set(names)) != len(names):
            errors.append(f'text_clearance.{key} contains duplicates')
    if errors:
        return errors
    if set(c['label_names']) & set(c['obstacle_names']):
        errors.append('text clearance label/obstacle selections must be disjoint')
    inventory=manifest.get('source_inventory', [])
    if not isinstance(inventory,list):
        return errors+['source_inventory must be a list']
    for i in inventory:
        if not isinstance(i,dict):
            continue
        if i.get('role') == 'text' and i.get('output_name') and i['output_name'] not in c['label_names']:
            errors.append(f"text clearance omits source text {i['output_name']}")
    return errors


def segment_hits_box(a,b,box):
    """Slab intersection, including segment interiors, tangencies and endpoints."""
    x,y,w,h=box; lower,upper=0.,1.
    for start,delta,lo,hi in ((a[0],b[0]-a[0],x,x+w),(a[1],b[1]-a[1],y,y+h)):
        if abs(delta)<1e-12:
            if start<lo or start>hi:return False
        else:
            t0,t1=sorted(((lo-start)/delta,(hi-start)/delta));lower=max(lower,t0);upper=min(upper,t1)
            if lower>upper:return False
    return True


def point_inside(p,poly):
    odd=False
    for a,b in zip(poly,poly[1:]+poly[:1]):
        if (a[1]>p[1]) != (b[1]>p[1]) and p[0] < (b[0]-a[0])*(p[1]-a[1])/(b[1]-a[1])+a[0]:odd=not odd
    return odd


def path_hits_box(points,box,pad=0,closed=False):
    x,y,w,h=box;expanded=[x-pad,y-pad,w+2*pad,h+2*pad]
    sequence=points+([points[0]] if closed and points[-1]!=points[0] else [])
    return any(segment_hits_box(a,b,expanded) for a,b in zip(sequence,sequence[1:])) or (closed and point_inside((x+w/2,y+h/2),points))


def boxes_overlap(a,b,gap):
    return min(a[0]+a[2]+gap,b[0]+b[2]+gap)>max(a[0],b[0])+1e-7 and min(a[1]+a[3]+gap,b[1]+b[3]+gap)>max(a[1],b[1])+1e-7


def audit(artifact,manifest):
    errors=validate_contract(manifest)
    report={'valid':not errors,'errors':errors,'unverified':[],'collisions':[],
            'claim_boundary':'Actual native text boxes versus sampled native custom paths, stroke padding and other text boxes. Not exact glyph visibility, arbitrary shape or renderer certification.'}
    if errors:return report
    if Path(artifact).suffix.lower()!='.pptx':report['unverified'].append('PPTX profile only');return report
    c=manifest['text_clearance']
    spec=importlib.util.spec_from_file_location('clearance_native_reader',Path(__file__).with_name('audit-curve-fidelity.py'))
    reader=importlib.util.module_from_spec(spec);spec.loader.exec_module(reader)
    profiles,_,_=reader.collect_pptx_profiles(Path(artifact))
    labels=[];widths={}
    with zipfile.ZipFile(artifact) as z:
        size=ET.fromstring(z.read('ppt/presentation.xml')).find('p:sldSz',reader.NS)
        sx=manifest['canvas']['width']/int(size.get('cx'));sy=manifest['canvas']['height']/int(size.get('cy'))
        for part in sorted({p['slide_part'] for p in profiles}):
            root=ET.fromstring(z.read(part));parents={child:parent for parent in root.iter() for child in parent}
            for s in root.findall('.//p:sp',reader.NS):
                props=s.find('p:nvSpPr/p:cNvPr',reader.NS);name=props.get('name','')
                if name not in c['label_names']+c['obstacle_names']:continue
                try:
                    xf=s.find('p:spPr/a:xfrm',reader.NS)
                    if xf is None:raise ValueError('missing local transform')
                    transforms=[reader._axis_transform(xf)]
                    parent=parents.get(s)
                    while parent is not None:
                        if reader.tag_name(parent)=='grpSp':
                            f=parent.find('p:grpSpPr/a:xfrm',reader.NS)
                            if f is None:raise ValueError('missing group transform')
                            transforms.append(reader._axis_transform(f,group=True))
                        parent=parents.get(parent)
                    corners=[(0,0),(1,1)]
                    for ax,ay,tx,ty in transforms:corners=[(ax*x+tx,ay*y+ty) for x,y in corners]
                    xx=sorted(p[0]*sx for p in corners);yy=sorted(p[1]*sy for p in corners)
                    if name in c['label_names']:
                        if not any((t.text or '').strip() for t in s.findall('.//a:t',reader.NS)):raise ValueError('selected label has no text')
                        labels.append({'name':name,'slide':part,'box':[xx[0],yy[0],xx[1]-xx[0],yy[1]-yy[0]]})
                    ln=s.find('p:spPr/a:ln',reader.NS)
                    # Group scaling affects line width too; use larger axis conservatively.
                    group_scale=math.prod(max(abs(t[0]),abs(t[1])) for t in transforms[1:])
                    width=0 if ln is None or ln.find('a:noFill',reader.NS) is not None else float(ln.get('w','0'))
                    widths[(part,props.get('id'))]=width*max(sx,sy)*group_scale
                except (ValueError,TypeError) as exc:report['unverified'].append(f'{name}: {exc}')
    chosen=[]
    for name in c['obstacle_names']:
        matches=[p for p in profiles if p['name']==name]
        if len(matches)!=1:errors.append(f'{name}: expected one unique custom path, got {len(matches)}');continue
        p=matches[0]
        if p['status']!='supported' or not p.get('absolute_coordinates_available'):
            report['unverified'].append(f'{name}: unsupported native path');continue
        chosen.append({'name':name,'slide':p['slide_part'],'points':[(x*sx,y*sy) for x,y in p['points']],
                       'closed':p.get('closed',False),'width':widths.get((p['slide_part'],p['shape_id']),0)})
    for name in c['label_names']:
        matches=[p for p in labels if p['name']==name]
        if len(matches)!=1:errors.append(f'{name}: expected one unique resolved label, got {len(matches)}')
    for i,label in enumerate(labels):
        for other in labels[i+1:]:
            if other['slide']==label['slide'] and boxes_overlap(label['box'],other['box'],c['min_gap_px']):
                report['collisions'].append({'label':label['name'],'obstacle':other['name'],'kind':'label-label'})
        for other in chosen:
            if other['slide']==label['slide'] and path_hits_box(other['points'],label['box'],c['min_gap_px']+other['width']/2,other['closed']):
                report['collisions'].append({'label':label['name'],'obstacle':other['name'],'kind':'label-path'})
    report['label_count']=len(labels);report['obstacle_count']=len(chosen)
    report['valid']=not errors and not report['collisions']
    return report
