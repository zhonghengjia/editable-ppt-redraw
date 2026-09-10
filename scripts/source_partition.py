"""Source-only marked pixel partition -> existing native paint-part pipeline.

Not an image recognizer. Seeds and visible support are independently supplied
source observations. No output image, old fitted paths, gap filling or hidden
surface completion is accepted. The bounded priority flood is an original
adapter informed by marker-controlled watershed; contour tracing reuses the
project's pinned ImageTracerJS. Shared pixels are assigned once before tracing.
"""
from __future__ import annotations
import hashlib
import heapq
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
from PIL import Image

from component_geometry import checked_mask, label_regions, GeometryLimit
from component_fidelity import (worker, rgba, read_image, prepare_partition,
                                normalized_trace_svg)
from native_components import prepare_component
from native_vectors import MAX_PATH_CHARS

MAX_MARKERS = 100
MAX_OPERATIONS = 8_000_000


def marked_partition(image, support, markers):
    """Deterministic minimax local-RGB flood; tie-break by path length then FIFO.

    Returns a candidate ownership map, not verified biological identities.
    Support holes are never filled; every connected support must have a marker.
    No watershed-line pixels are dropped between competing owners.
    """
    support = checked_mask(support)
    if image.size != (support.shape[1], support.shape[0]):
        raise ValueError('image and source support dimensions differ')
    if not isinstance(markers, list) or not 1 <= len(markers) <= MAX_MARKERS:
        raise ValueError('markers requires 1..100 observed parts')
    h,w = support.shape
    rgb = np.asarray(image.convert('RGB'), dtype=np.int16)
    labels = np.zeros((h,w), dtype=np.int32)
    barrier = np.full((h,w), 256, dtype=np.int16)
    distance = np.full((h,w), h*w+1, dtype=np.int32)
    fixed = np.zeros((h,w), bool)
    queue=[]; tick=0; identities=set(); witnessed=set()
    components, regions = label_regions(support, diagonal=False)
    for owner, marker in enumerate(markers, 1):
        if not isinstance(marker,dict) or set(marker) != {'id','observation','seeds'}:
            raise ValueError('marker requires id, observation, seeds only')
        identity=marker['id']
        if not isinstance(identity,str) or not identity or '/' in identity or identity in identities:
            raise ValueError('unique nonempty marker ids without / required')
        identities.add(identity)
        if not isinstance(marker['observation'],str) or not marker['observation'].strip():
            raise ValueError('independent source observation required')
        seeds=marker['seeds']
        if not isinstance(seeds,list) or not 1<=len(seeds)<=100:
            raise ValueError('each part requires 1..100 source witnesses')
        for seed in seeds:
            if not isinstance(seed,list) or len(seed)!=2 or any(type(v) is not int for v in seed):
                raise ValueError('seed must be integer [x,y]')
            x,y=seed
            if not 0<=x<w or not 0<=y<h or not support[y,x] or fixed[y,x]:
                raise ValueError('seed outside support or duplicate; no snapping')
            labels[y,x]=owner;fixed[y,x]=True;barrier[y,x]=0;distance[y,x]=0
            witnessed.add(int(components[y,x]));tick+=1
            heapq.heappush(queue,(0,0,tick,y,x,owner))
    unseeded=[r for r in regions if r['id'] not in witnessed]
    if unseeded:
        raise ValueError('source support has unseeded components: '+str(unseeded[:12]))
    operations=0
    while queue:
        height,steps,_,y,x,owner=heapq.heappop(queue)
        operations+=1
        if operations>MAX_OPERATIONS:
            raise GeometryLimit('marked partition operation budget exceeded')
        if height!=barrier[y,x] or steps!=distance[y,x] or owner!=labels[y,x]:
            continue
        for dy,dx in ((-1,0),(0,-1),(0,1),(1,0)):
            ny,nx=y+dy,x+dx
            if not 0<=ny<h or not 0<=nx<w or not support[ny,nx] or fixed[ny,nx]:
                continue
            cost=max(height,int(np.max(np.abs(rgb[y,x]-rgb[ny,nx]))))
            length=steps+1
            if (cost,length)<(barrier[ny,nx],distance[ny,nx]):
                barrier[ny,nx]=cost;distance[ny,nx]=length;labels[ny,nx]=owner
                tick+=1;heapq.heappush(queue,(cost,length,tick,ny,nx,owner))
    if np.any(support & (labels==0)) or np.any(~support & (labels!=0)):
        raise RuntimeError('partition coverage invariant failed')
    return labels, {'support_pixels':int(support.sum()),'assigned_pixels':int((labels>0).sum()),
        'unassigned_pixels':0,'outside_support_pixels':0,'queue_pops':operations,
        'label_sha256':hashlib.sha256(labels.astype('<i4').tobytes()).hexdigest(),
        'parts':[{'id':m['id'],'label':i,'pixels':int((labels==i).sum())}
                 for i,m in enumerate(markers,1)],
        'semantics':'NOT_VERIFIED','geometry':'one_source_pixel_lattice'}


def build_source_partition(source, support_path, plan, *, node=None):
    """Build all named visible pieces afresh; no mutation or file emission.

    One support and marker plan binds the whole assembly, so independent object
    fits cannot create internal holes. Each result is an ordinary native
    component consumed by the existing manifest-backed emitter.
    """
    expected={'source_sha256','source_bbox','support_sha256','support_observation',
              'markers','colors_per_part','max_native_paths','max_native_commands'}
    if not isinstance(plan,dict) or set(plan) not in (expected,expected|{'representation'}):
        raise ValueError('invalid source partition plan fields')
    representation=plan.get('representation','palette_edges')
    if representation not in ('palette_edges','palette_stack'):
        raise ValueError('assembly representation must be palette_edges or palette_stack')
    source,support_path=Path(source),Path(support_path)
    for path,key in ((source,'source_sha256'),(support_path,'support_sha256')):
        if hashlib.sha256(path.read_bytes()).hexdigest()!=plan[key]:
            raise ValueError(key+' mismatch')
    crop=plan['source_bbox']
    image=read_image(source)
    if not isinstance(crop,list) or len(crop)!=4 or any(type(v)is not int for v in crop):
        raise ValueError('source_bbox must contain four integers')
    x,y,w,h=crop
    if min(x,y)<0 or min(w,h)<1 or x+w>image.width or y+h>image.height:
        raise ValueError('source_bbox outside source')
    if image.info.get('icc_profile') or image.getextrema()[3]!=(255,255):
        raise ValueError('partition requires qualified opaque sRGB source')
    if not isinstance(plan['support_observation'],str) or not plan['support_observation'].strip():
        raise ValueError('source support provenance required')
    with Image.open(support_path) as mask_image:
        if mask_image.mode not in ('1','L') or mask_image.size!=(w,h):
            raise ValueError('support must be source-crop-sized binary grayscale')
        values=np.asarray(mask_image.convert('L'))
    if np.any((values!=0)&(values!=255)):
        raise ValueError('support contains ambiguous nonbinary pixels')
    support=values==255
    colors=plan['colors_per_part']
    if type(colors)is not int or not 2<=colors<=64:
        raise ValueError('colors_per_part must be 2..64')
    for k in ('max_native_paths','max_native_commands'):
        if type(plan[k])is not int or not 1<=plan[k]<=1_000_000:
            raise ValueError('invalid declared edit budget')
    cropped=image.crop((x,y,x+w,y+h))
    labels,evidence=marked_partition(cropped,support,plan['markers'])
    components=[];path_count=0;command_count=0;reports=[]
    # Partition each semantic piece without resampling or independently fitting
    # its contour. Every piece retains the same [0,w] x [0,h] coordinate lattice.
    for index,marker in enumerate(plan['markers'],1):
        pixels=np.array(cropped)
        pixels[:,:,3]=np.where(labels==index,255,0)
        pixels[labels!=index,:3]=0
        prepared,basis,quantization=prepare_partition(Image.fromarray(pixels),colors)
        # Alpha membership must survive color reduction exactly.
        if not np.array_equal(np.asarray(prepared)[:,:,3]>0,labels==index):
            raise ValueError('palette preparation changed source ownership')
        traced=worker(dict(action='trace',width=w,height=h,representation=representation,
            first=rgba(prepared),path_char_limit=MAX_PATH_CHARS),node)
        svg,stats=normalized_trace_svg(traced,representation)
        parts=[]
        for element in ET.fromstring(svg):
            color=element.attrib['fill'].lstrip('#')
            parts.append({'id':element.attrib['id'],'role':'source-paint-region',
                'observation':f"Source-visible paint within {marker['id']}; source palette quantization, not hidden anatomy or a gradient fit.",
                'd':element.attrib['d'],'fill':color})
        component={'id':marker['id'],'output_name':marker['id'],'viewbox':[0,0,w,h],'parts':parts}
        prepared_parts,_,_=prepare_component(component)
        count=sum(len(p['spec']['commands']) for p in prepared_parts)
        path_count+=len(parts);command_count+=count
        if path_count>plan['max_native_paths'] or command_count>plan['max_native_commands']:
            raise GeometryLimit('assembly exceeds source-declared native editing budget')
        components.append(component)
        reports.append({'id':marker['id'],'palette_basis':basis,'quantization':quantization,'composition':traced['partition']['composition'],
                        'native_paths':len(parts),'native_commands':count})
    evidence.update(source_sha256=plan['source_sha256'],support_sha256=plan['support_sha256'],
        source_bbox=crop,plan=plan,parts=reports,native_paths=path_count,native_commands=command_count,
        engine='existing pinned ImageTracerJS boundary scanner',representation=representation,
        practical_editability='NOT_VERIFIED',final_render_coverage='NOT_VERIFIED')
    return components,labels,evidence
