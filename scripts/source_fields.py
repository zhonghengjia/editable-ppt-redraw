"""Fit observed smooth fields to existing native Paint without color quantization.

Fixed source geometry/ownership; no segmentation, hidden-layer recovery or renderer.
Algorithms: bounded least squares and position-covariance color slopes. See notices.
"""
from __future__ import annotations
import copy
import hashlib
import json
import math
from pathlib import Path
import numpy as np
from native_paint import normalize_paint, centered_radial_paint, scalar, keys
from native_components import prepare_component
from vendor.svg_paths.drawingml_paths import path_bounds

MAX_PIXELS = 250_000


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False,
        separators=(',', ':')).encode()).hexdigest()


def validate_options(options):
    keys(options, {'part_id','support','model','semantics','stop_count','max_error','angle','radius',
                   'alpha_profile','source_layer'},
         {'part_id','support','model','semantics','stop_count','max_error'}, 'field fit')
    if not isinstance(options['part_id'],str) or not options['part_id'].strip():
        raise ValueError('field part_id required')
    keys(options['support'], {'path','sha256'}, {'path','sha256'}, 'field support')
    ref=options['support']
    if not isinstance(ref['path'],str) or not ref['path'].strip() or not isinstance(ref['sha256'],str) or len(ref['sha256'])!=64 or any(c not in '0123456789abcdef' for c in ref['sha256']):
        raise ValueError('field support requires path and SHA-256')
    if options['model'] not in ('solid','linear','radial'):
        raise ValueError('field model must be solid, linear or centered radial')
    if options['semantics'] not in ('visible_composite','source_rgba','estimated_layer'):
        raise ValueError('choose visible_composite, source_rgba or bound estimated_layer')
    if (options['semantics']=='estimated_layer') != ('source_layer' in options):
        raise ValueError('estimated_layer requires its source_layer receipt, and vice versa')
    if 'source_layer' in options:
        ref=options['source_layer']
        keys(ref, {'path','sha256'}, {'path','sha256'}, 'source layer')
        if (not isinstance(ref['path'],str) or not ref['path'].strip()
                or not isinstance(ref['sha256'],str) or len(ref['sha256'])!=64
                or any(c not in '0123456789abcdef' for c in ref['sha256'])):
            raise ValueError('source layer requires path and SHA-256')
    if options['stop_count']!='auto' and (type(options['stop_count']) is not int or not 4 <= options['stop_count'] <= 16):
        raise ValueError('field fit needs 4..16 stops or auto, avoiding special two/three-stop Office interpolation')
    scalar(options['max_error'],'field error',0,32/255)
    if 'angle' in options:
        if options['model']!='linear': raise ValueError('angle requires linear model')
        scalar(options['angle'],'angle',0,360)
    if 'radius' in options:
        if options['model']!='radial': raise ValueError('radius requires radial model')
        scalar(options['radius'],'radius',1e-6,1e6)
    if 'alpha_profile' in options:
        if options['semantics']=='visible_composite':
            raise ValueError('independent alpha requires an explicit RGBA source/layer')
        profile=options['alpha_profile']
        keys(profile, {'model','stop_count','angle','radius'}, {'model','stop_count'}, 'alpha profile')
        nested={k:v for k,v in options.items() if k not in ('alpha_profile','angle','radius')}
        nested.update(profile)
        validate_options(nested)


def box(value):
    if not isinstance(value,(list,tuple)) or len(value)!=4:
        raise ValueError('field bounds need [x,y,w,h]')
    v=[scalar(n,'field coordinate',-1e9,1e9) for n in value]
    if min(v[2:])<=0: raise ValueError('positive field extent required')
    return v


def profile_coordinates(points, bounds, model, *, angle=0, radius=None):
    x,y,w,h=box(bounds)
    if model=='solid': return np.zeros(len(points))
    if model=='linear':
        angle=round(angle*60000)/60000
        d=np.array([math.cos(math.radians(angle)),math.sin(math.radians(angle))])
        corners=np.array([[x,y],[x+w,y],[x,y+h],[x+w,y+h]])@d
        return np.clip((points@d-corners.min())/np.ptp(corners),0,1)
    if model!='radial': raise ValueError('unsupported field model')
    native_radius=math.hypot(w,h)/2
    radius=native_radius if radius is None else radius
    if not 0<radius<=native_radius: raise ValueError('radial radius exceeds actual owner domain')
    return np.clip(np.linalg.norm(points-[x+w/2,y+h/2],axis=1)/radius,0,1)


def design_matrix(t, count):
    if count==1: return np.ones((len(t),1))
    # Positions match serialized Office stop precision, not ideal fractional knots.
    knots=np.rint(np.linspace(0,1,count)*100000)/100000
    k=np.clip(np.searchsorted(knots,t,side='right')-1,0,count-2)
    f=(t-knots[k])/(knots[k+1]-knots[k])
    d=np.zeros((len(t),count)); rows=np.arange(len(t))
    d[rows,k]=1-f; d[rows,k+1]=f
    return d


def bounded_stops(design, target):
    """Small convex box-constrained least squares, no SciPy/runtime dependency."""
    if target.ndim==1: target=target[:,None]
    h=design.T@design; g=design.T@target
    values=np.clip(np.linalg.lstsq(design,target,rcond=None)[0],0,1)
    # Cyclic coordinate minimization uses the complete quadratic objective.
    # Zero-information colors remain irrelevant, never divide by tiny alpha.
    for _ in range(1000):
        previous=values.copy()
        for j in range(len(values)):
            if h[j,j]>1e-12:
                values[j]=np.clip(values[j]+(g[j]-h[j]@values)/h[j,j],0,1)
        if np.max(np.abs(values-previous))<1e-9: return values
    raise ValueError('bounded field solver did not converge within fixed budget')


def solve_profile(d, rgba, color_weights=None):
    # Unseen end knots do not make a circular/holed owner unrepresentable.
    # Only solve identifiable columns; extend missing coefficients deterministically.
    active=np.flatnonzero(np.any(np.abs(d)>1e-12,axis=0))
    observed=d[:,active]
    if not len(active) or np.linalg.matrix_rank(observed)<len(active):
        raise ValueError('insufficient observed field positions for stops')
    a=rgba[:,3:4]; p=rgba[:,:3]*a
    alpha=np.rint(bounded_stops(observed,a)*100000)/100000
    predicted_alpha=observed@alpha
    weights=np.ones_like(a) if color_weights is None else color_weights[:,None]
    color=np.rint(bounded_stops(observed*predicted_alpha*weights,p*weights)*255)/255
    def extend(values):
        return np.column_stack([np.interp(np.arange(d.shape[1]),active,values[:,i])
                                for i in range(values.shape[1])])
    color,alpha=extend(color),extend(alpha)
    predicted_color=d@color
    # Office interpolates RGB and alpha independently; their product is NOT a
    # linear interpolation of premultiplied endpoint colors.
    error=np.column_stack(((predicted_color*predicted_alpha-p)*weights,predicted_alpha-a))
    return color,alpha,float(np.mean(error**2))


def evaluate_paint(paint, points, bounds):
    paint=normalize_paint(paint)
    if paint['kind']=='solid':
        stops=[dict(color=paint['color'],alpha=paint['alpha'])]; t=np.zeros(len(points))
    else:
        if paint['kind']=='path' and paint['focus']!=[.5,.5]:
            raise ValueError('source field evaluator supports centered circular Paint only')
        t=profile_coordinates(points,bounds,'linear' if paint['kind']=='linear' else 'radial',angle=paint.get('angle',0))
        stops=paint['stops']
    cols=np.array([[int(s['color'][i:i+2],16)/255 for i in (0,2,4)]+[s['alpha']] for s in stops])
    if len(stops)==1: return np.broadcast_to(cols,(len(points),4)).copy()
    positions=np.rint(np.array([s['position'] for s in stops])*100000)/100000
    return np.column_stack([np.interp(t,positions,cols[:,i]) for i in range(4)])


def _field_data(pixels, support, field_bbox, owner_bbox, options):
    """Validate original observations without running an optimizer."""
    validate_options(options)
    values=np.asarray(pixels); support=np.asarray(support)
    if values.dtype!=np.uint8 or values.ndim!=3 or values.shape[2]!=4 or not 0<values.shape[0]*values.shape[1]<=MAX_PIXELS:
        raise ValueError('field requires bounded uint8 RGBA pixels')
    if support.dtype!=np.bool_ or support.shape!=values.shape[:2] or not support.any():
        raise ValueError('field requires nonempty binary source ownership')
    fx,fy,fw,fh=box(field_bbox); ox,oy,ow,oh=box(owner_bbox)
    if ox<fx or oy<fy or ox+ow>fx+fw+1e-8 or oy+oh>fy+fh+1e-8:
        raise ValueError('observed field must cover complete native owner')
    h,w=support.shape; ys,xs=np.nonzero(support)
    points=np.column_stack((fx+(xs+.5)*fw/w,fy+(ys+.5)*fh/h))
    if np.any((points[:,0]<ox)|(points[:,0]>ox+ow)|(points[:,1]<oy)|(points[:,1]>oy+oh)):
        raise ValueError('source support lies outside native owner')
    observed=values[support].astype(float)/255
    if options['semantics']=='visible_composite' and np.any(observed[:,3]!=1):
        raise ValueError('visible composite must be opaque; keep real source alpha explicit')
    if not np.any(observed[:,3]>0): raise ValueError('field contains no visible evidence')
    # Fit at most 4096 evenly indexed observations, but verify EVERY support pixel.
    sample=np.unique(np.linspace(0,len(points)-1,min(len(points),4096)).astype(int))
    return values,support,points,observed,sample


def _fit_profile(pixels, support, field_bbox, owner_bbox, options, *, enforce=True, color_weights=None):
    """Fit original RGB/RGBA or a receipt-bound layer, never a prior PPT render."""
    values,support,points,observed,sample=_field_data(pixels,support,field_bbox,owner_bbox,options)
    _,_,ow,oh=box(owner_bbox)
    pts,rgba=points[sample],observed[sample]
    weights=None if color_weights is None else np.asarray(color_weights)[support][sample]
    model=options['model']; count=1 if model=='solid' else options['stop_count']
    def solve(angle):
        t=profile_coordinates(pts,owner_bbox,model,angle=angle,radius=options.get('radius'))
        d=design_matrix(t,count)
        color,alpha,cost=solve_profile(d,rgba,weights)
        return cost,angle,color,alpha
    angle=options.get('angle',0)
    if model=='linear' and 'angle' not in options:
        # Position-covariance-normalized slopes keep non-square fields aspect correct.
        target=np.column_stack((rgba[:,:3]*rgba[:,3:4],rgba[:,3]))
        if weights is None:
            xy=pts-pts.mean(axis=0);centered=target-target.mean(axis=0)
        else:
            # Use the same coverage-weighted objective for direction and stops.
            # Otherwise invisible RGB can change the angle search's starting point.
            mass=weights**2
            if not np.any(mass>0):
                raise ValueError('no observed color information in deterministic fit sample')
            xy=(pts-np.average(pts,axis=0,weights=mass))*weights[:,None]
            centered=(target-np.average(target,axis=0,weights=mass))*weights[:,None]
        slopes=np.linalg.lstsq(xy,centered,rcond=None)[0]
        _,eigenvectors=np.linalg.eigh(slopes@slopes.T)
        seed=math.degrees(math.atan2(*eigenvectors[:, -1][::-1]))%180
        candidates=[]
        for a in sorted(set([seed]+list(np.arange(0,180,10,dtype=float)))):
            try: candidates.append(solve(a))
            except ValueError: continue
        if not candidates: raise ValueError('no observable linear field direction')
        result=min(candidates,key=lambda r:r[0])
        for extent,step in ((10,1),(1,.1)):
            candidates=[result]
            for a in np.arange(result[1]-extent,result[1]+extent+step/2,step):
                try: candidates.append(solve(round(float(a)%180,6)))
                except ValueError: continue
            result=min(candidates,key=lambda r:r[0])
    else: result=solve(angle)
    _,angle,color,alpha=result
    entries=[dict(position=round(float(p)*100000)/100000,color=''.join(f'{round(c*255):02X}' for c in rgb),alpha=float(a[0]))
             for p,rgb,a in zip(np.linspace(0,1,count),color,alpha)]
    if model=='solid': paint=dict(kind='solid',color=entries[0]['color'],alpha=entries[0]['alpha'])
    elif model=='linear': paint=dict(kind='linear',angle=round(angle*60000)/60000,stops=entries)
    elif options.get('radius',math.hypot(ow,oh)/2)<math.hypot(ow,oh)/2:
        paint=centered_radial_paint(entries,options['radius'],owner_bbox)
    else: paint=dict(kind='path',focus=[.5,.5],stops=entries)
    predicted=evaluate_paint(paint,points,owner_bbox)
    delta=predicted[:,:3]*predicted[:,3:4]-observed[:,:3]*observed[:,3:4]
    alpha_error=np.abs(predicted[:,3]-observed[:,3])
    error=float(max(np.max(np.abs(delta)),alpha_error.max()))
    if enforce and error>options['max_error']:
        raise ValueError(f'field not representable by declared {model}: max premultiplied RGB/alpha error {error:.6f} > {options["max_error"]:.6f}')
    preview=np.zeros_like(values); preview[support]=np.rint(predicted*255).astype('uint8')
    evidence=dict(model=model,semantics=options['semantics'],owner_bbox=list(owner_bbox),
        source_pixels=int(len(points)),fit_pixels=len(sample),max_error=error,
        mean_premultiplied_error=float(np.mean(np.abs(delta))),max_alpha_error=float(alpha_error.max()),
        color_model='encoded_sRGB_independent_RGB_alpha_interpolation',
        paint_sha256=digest(paint),final_render='NOT_VERIFIED',semantic_ownership='REQUIRES_SOURCE_REVIEW')
    coordinates=profile_coordinates(points,owner_bbox,model,angle=angle,radius=options.get('radius'))
    active=np.any(design_matrix(coordinates,count)>1e-12,axis=0)
    evidence.update(observed_profile_range=[float(coordinates.min()),float(coordinates.max())],
                    unobserved_stop_indices=np.flatnonzero(~active).tolist(),
                    unobserved_extension='nearest_end_or_linear_gap_not_source_truth')
    return normalize_paint(paint),evidence,preview


def fit_field(pixels, support, field_bbox, owner_bbox, options):
    """Backward-compatible single Paint fit. Use fit_surface for alpha masks."""
    if 'alpha_profile' in options:
        raise ValueError('independent alpha requires fit_surface; do not discard its compositing')
    validate_options(options)
    if options['stop_count']!='auto':
        return _fit_profile(pixels,support,field_bbox,owner_bbox,options)
    # Uniform knot grids are not nested: more stops can fit worse. Search the
    # declared finite family, smallest first, instead of escalating on failure.
    _field_data(pixels,support,field_bbox,owner_bbox,options)
    best=None;failures=[]
    for count in _stop_counts(options):
        try:
            paint,evidence,preview=_fit_profile(pixels,support,field_bbox,owner_bbox,
                dict(options,stop_count=count),enforce=False)
        except ValueError as exc:
            failures.append(str(exc));continue
        best=evidence['max_error'] if best is None else min(best,evidence['max_error'])
        if evidence['max_error']<=options['max_error']:
            evidence['stop_selection']=dict(requested='auto',selected=count,maximum=16)
            return paint,evidence,preview
    raise ValueError(f'field not representable within declared auto stop budget 4..16: best error {best}; tolerance {options["max_error"]}; solver failures {failures[:1]}')


def _stop_counts(options):
    if options['model']=='solid':return (4,)  # The solver emits one solid color.
    return range(4,17) if options['stop_count']=='auto' else (options['stop_count'],)


def fit_surface(pixels, support, field_bbox, owner_bbox, options):
    """Compile one surface to existing fill + optional independent alpha Paint.

    Both channels reuse the same bounded solver. Final error is evaluated on all
    owned source pixels after native quantization and composition, not on the
    separate fit costs. Transparent RGB never supplies color evidence.
    """
    validate_options(options)
    if 'alpha_profile' not in options:
        paint,evidence,preview=fit_field(pixels,support,field_bbox,owner_bbox,options)
        return paint,None,evidence,preview
    base={k:v for k,v in options.items() if k!='alpha_profile'}
    values,support,points,observed,_=_field_data(pixels,support,field_bbox,owner_bbox,base)
    opaque=values.copy();opaque[:,:,3]=255
    color_opts=dict(base,semantics='visible_composite');color_opts.pop('source_layer',None)
    mask_values=values.copy();mask_values[:,:,:3]=255
    alpha_opts={k:v for k,v in base.items() if k not in ('angle','radius')}
    alpha_opts.update(options['alpha_profile'])
    cache={};failures=[]
    def candidate(channel,count):
        key=(channel,count)
        if key not in cache:
            opts=color_opts if channel=='color' else alpha_opts
            try:
                p,e,_=_fit_profile(opaque if channel=='color' else mask_values,support,
                    field_bbox,owner_bbox,dict(opts,stop_count=count),enforce=False,
                    color_weights=values[:,:,3]/255 if channel=='color' else None)
            except ValueError as exc:
                cache[key]=None;failures.append(str(exc));return None
            if channel=='alpha':
                # Invisible RGB is not measured; mask color is always white.
                if p['kind']=='solid':p['color']='FFFFFF'
                else:
                    for stop in p['stops']:stop['color']='FFFFFF'
                e['paint_sha256']=digest(p)
            prediction=evaluate_paint(p,points,owner_bbox)
            cache[key]=(p,e,prediction[:,:3] if channel=='color' else prediction[:,3:4])
        return cache[key]
    pairs=sorted(((c,a) for c in _stop_counts(color_opts) for a in _stop_counts(alpha_opts)),
                 key=lambda pair:(sum(pair),pair))
    best=None;selected=None
    for c,a in pairs:
        color_result=candidate('color',c);alpha_result=candidate('alpha',a)
        if color_result is None or alpha_result is None:continue
        paint,color_e,rgb=color_result;mask,alpha_e,alpha=alpha_result
        delta=rgb*alpha-observed[:,:3]*observed[:,3:4]
        alpha_error=np.abs(alpha[:,0]-observed[:,3])
        error=float(max(np.abs(delta).max(),alpha_error.max()))
        best=error if best is None else min(best,error)
        if error<=options['max_error']:
            selected=(c,a);predicted=np.column_stack((rgb,alpha));break
    if selected is None:
        raise ValueError(f'field not representable by declared independent profiles: best max premultiplied RGB/alpha error {best} > {options["max_error"]:.6f}; solver failures {failures[:1]}')
    effect=dict(alpha_mask=mask)
    preview=np.zeros_like(values);preview[support]=np.rint(predicted*255).astype('uint8')
    evidence=dict(model='independent_profiles',semantics=options['semantics'],owner_bbox=list(owner_bbox),
        source_pixels=int(support.sum()),max_error=error,mean_premultiplied_error=float(np.abs(delta).mean()),
        max_alpha_error=float(alpha_error.max()),profiles=dict(color=color_e,alpha=alpha_e),
        color_model='encoded_sRGB_independent_RGB_alpha_interpolation',
        paint_sha256=digest(paint),compositing_sha256=digest(effect),
        stop_selection=dict(color=selected[0],alpha=selected[1],
            requested_color=color_opts['stop_count'],requested_alpha=alpha_opts['stop_count'],
            profile_fits=len(cache),maximum_per_auto_profile=16),
        final_render='NOT_VERIFIED',semantic_ownership='REQUIRES_SOURCE_REVIEW')
    return paint,effect,evidence,preview


def fit_component(source, source_hash, item, component, *, base_dir):
    """Replace only one declared paint owner, keeping supplied geometry untouched."""
    from raster_components import read_image
    options=item['construction']['field_fit']; validate_options(options)
    if hashlib.sha256(Path(source).read_bytes()).hexdigest()!=source_hash:
        raise ValueError('field source hash changed')
    support_path=Path(base_dir)/options['support']['path']
    if hashlib.sha256(support_path.read_bytes()).hexdigest()!=options['support']['sha256']:
        raise ValueError('field support hash changed')
    x,y,w,h=item['bbox']
    if any(type(v) is not int for v in item['bbox']) or min(x,y)<0 or min(w,h)<1 or w*h>MAX_PIXELS:
        raise ValueError('field crop must be bounded integer source pixels')
    with read_image(source, source_hash) as image:
        if x+w>image.width or y+h>image.height: raise ValueError('field crop outside source')
        pixels=np.asarray(image.convert('RGBA').crop((x,y,x+w,y+h)))
    provenance=dict(method='original_source_pixels',physical_layer_identity='NOT_INFERRED')
    if 'source_layer' in options:
        from source_layers import read_layer_bundle
        binding=dict(options['source_layer'],path=str(Path(base_dir)/options['source_layer']['path']))
        layer,provenance=read_layer_bundle(binding,source_hash,item['bbox'])
        with layer:pixels=np.array(layer)
    with read_image(support_path, options['support']['sha256'], alpha=True) as image:
        if image.mode!='L' or image.size!=(w,h): raise ValueError('field support must be crop-sized grayscale')
        mask=np.array(image)
    if not np.isin(mask,[0,255]).all(): raise ValueError('field support is ownership, not inferred soft alpha')
    parts,viewbox,_=prepare_component(component)
    vx,vy,vw,vh=viewbox
    if not math.isclose(w/vw,h/vh,rel_tol=1e-9): raise ValueError('field viewbox requires uniform source mapping')
    found=[]
    def find(nodes, blocked=False):
        for n in nodes:
            effect=n['compositing']; blocked_here=blocked or effect['opacity']!=1 or effect['alpha_mask'] is not None
            if n['id']==options['part_id']:
                if blocked_here: raise ValueError('field owner already has compositing; no double alpha')
                found.append(n)
            if 'children' in n: find(n['children'],blocked_here)
    find(parts)
    if len(found)!=1: raise ValueError('field needs one existing paint owner')
    owner=found[0]
    if 'children' in owner:
        def consumers(nodes, blocked=False):
            total=0
            for n in nodes:
                effect=n['compositing']
                blocked_here=blocked or effect['opacity']!=1 or effect['alpha_mask'] is not None
                if 'children' in n:
                    if n['group_fill'] is None or n['group_fill']['kind']=='group':
                        total+=consumers(n['children'],blocked_here)
                    elif 'alpha_profile' in options:
                        raise ValueError('independent alpha group must own every painted descendant')
                elif n['spec']['fill']['kind']=='group':
                    if blocked_here: raise ValueError('field consumer already has compositing; no double alpha')
                    total+=1
                elif 'alpha_profile' in options:
                    raise ValueError('independent alpha group must own every painted descendant')
            return total
        if not consumers(owner['children']): raise ValueError('fitted group paint has no inheriting visible leaf')
    def bounds(node):
        if 'children' in node:
            bs=[bounds(n) for n in node['children']]
            return [min(b[0] for b in bs),min(b[1] for b in bs),max(b[2] for b in bs),max(b[3] for b in bs)]
        if node['spec']['stroke']['kind']!='none': raise ValueError('field owner requires unstroked geometry')
        return path_bounds(node['spec']['commands'])
    bx,by,br,bb=bounds(owner); scale=w/vw
    domain=[x+(bx-vx)*scale,y+(by-vy)*scale,(br-bx)*scale,(bb-by)*scale]
    paint,effect,evidence,preview=fit_surface(pixels,mask==255,item['bbox'],domain,options)
    result=copy.deepcopy(component)
    def replace(nodes):
        for n in nodes:
            if n['id']==options['part_id']:
                n['group_fill' if 'children' in n else 'fill']=paint
                if effect is not None:n['compositing']=effect
            if 'children' in n: replace(n['children'])
    replace(result['parts']); prepare_component(result)
    evidence.update(source_sha256=source_hash,source_bbox=item['bbox'],options_sha256=digest(options),
        geometry_input_sha256=digest(component),support_sha256=options['support']['sha256'],
        input_provenance=provenance,component=result)
    return evidence,preview
