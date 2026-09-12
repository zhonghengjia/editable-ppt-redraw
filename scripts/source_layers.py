"""Bounded source-layer estimation: coverage is not object membership.

Closed-form color Laplacian follows Levin et al. and the PyMatting formulation.
The vectorized SciPy implementation here has no model/Numba dependency. Optional
biharmonic interpolation is explicitly scoped to annotated smooth color fields.
Neither estimator identifies anatomy or recovers arbitrary hidden surfaces.
"""
from __future__ import annotations

import json
from pathlib import Path
import numpy as np
from PIL import Image
from raster_components import digest, read_image, unmix_background

# CSR assembly is O(81 * active 3x3 windows); cap work, not output fidelity.
MAX_LAYER_PIXELS = 250_000


def validate_layer_options(plan):
    from native_paint import keys, scalar
    m = plan.get('matting')
    keys(m, {'background_patches', 'background_tolerance', 'epsilon', 'max_iterations','solver'},
         {'background_patches', 'background_tolerance', 'epsilon'}, 'matting')
    solver=m.get('solver','cg')
    if solver not in ('cg','direct'): raise ValueError('matting solver must be cg or direct')
    if not isinstance(m['background_patches'], list) or not 1 <= len(m['background_patches']) <= 32:
        raise ValueError('1..32 independently observed background patches required')
    for patch in m['background_patches']:
        if (not isinstance(patch,list) or len(patch)!=4 or any(type(v)is not int for v in patch)
                or min(patch[:2])<0 or min(patch[2:])<=0):
            raise ValueError('background patches need integer positive source boxes')
    scalar(m['background_tolerance'], 'background tolerance in RGB codes', 0, 32)
    scalar(m['epsilon'], 'matting epsilon', 1e-9, .01)
    if solver=='cg' and (type(m.get('max_iterations')) is not int or not 1 <= m['max_iterations'] <= 5000):
        raise ValueError('bounded matting max_iterations required')
    if solver=='direct' and 'max_iterations' in m:raise ValueError('direct solver has no iteration parameter')
    occlusions = plan.get('occlusions', [])
    if not isinstance(occlusions, list) or len(occlusions) > 100:
        raise ValueError('occlusions must be a bounded list')
    for o in occlusions:
        keys(o, {'id','kind','authorization','marks'},
             {'id','kind','authorization','marks'}, 'occlusion')
        if o['kind'] != 'smooth_field' or any(not isinstance(o[k], str) or not o[k].strip() for k in ('id','authorization')):
            raise ValueError('only explicitly authorized smooth_field interpolation supported')
        if (not isinstance(o['marks'],list) or not o['marks']
                or any(not isinstance(v,dict) or v.get('label')!='occluder' for v in o['marks'])):
            raise ValueError('occlusion marks select the observed occluder pixels')
        for mark in o['marks']:
            fields={'kind','label','points','observation'} | ({'width'} if mark.get('kind')=='stroke' else set())
            if (set(mark)!=fields or mark.get('kind') not in ('stroke','polygon')
                    or not isinstance(mark['observation'],str) or not mark['observation'].strip()
                    or not isinstance(mark['points'],list) or not 1<=len(mark['points'])<=1000
                    or any(not isinstance(p,list) or len(p)!=2 or any(type(v)is not int for v in p) for p in mark['points'])):
                raise ValueError('invalid occluder source mark')
            if mark['kind']=='stroke' and (type(mark['width'])is not int or mark['width']<1 or mark['width']%2==0):
                raise ValueError('occluder stroke requires positive odd width')
            if mark['kind']=='polygon' and len({tuple(p) for p in mark['points']})<3:
                raise ValueError('occluder polygon requires three distinct points')
    if len({o['id'] for o in occlusions}) != len(occlusions):
        raise ValueError('duplicate occlusion ID')


def closed_form_alpha(rgb, labels, *, epsilon, max_iterations=None, solver='cg'):
    """Solve unknown coverage with exact FG/BG Dirichlet constraints.

    Labels: 0 background, 1 foreground, every other value unknown. Local color
    model is a prior, not a certificate of unique physical layer separation.
    """
    from scipy.sparse import coo_matrix, csr_matrix, diags
    from scipy.sparse.linalg import cg, spsolve, MatrixRankWarning
    import warnings
    from numpy.lib.stride_tricks import sliding_window_view
    rgb=np.asarray(rgb)
    labels=np.asarray(labels)
    if (labels.ndim!=2 or rgb.shape!=labels.shape+(3,) or not np.isfinite(rgb).all()
            or np.any((rgb<0)|(rgb>255)) or not np.isfinite(labels).all()):
        raise ValueError('finite matching RGB/label arrays required')
    if (not np.isfinite(epsilon) or not 1e-9<=epsilon<=.01
            or solver not in ('cg','direct')
            or (solver=='cg' and (type(max_iterations)is not int or not 1<=max_iterations<=5000))
            or (solver=='direct' and max_iterations is not None)):
        raise ValueError('invalid bounded matting solver settings')
    h,w = labels.shape
    if min(h,w) < 3 or h*w > MAX_LAYER_PIXELS:
        raise ValueError('closed-form layer needs >=3 pixels per side and <=250000 pixels')
    f = labels.ravel()
    unknown = (f != 0) & (f != 1)
    if not (f == 0).any() or not (f == 1).any():
        raise ValueError('closed-form matte requires observed opaque foreground and background')
    result = (f == 1).astype(float)
    if not unknown.any():
        return result.reshape(h,w), dict(solver=solver,iterations=0,raw_solver_residual=0.,
            clipped_solver_residual=0.,clipped_alpha_values=0,unknown_pixels=0)
    indices = sliding_window_view(np.arange(h*w).reshape(h,w), (3,3)).reshape(-1,9)
    indices = indices[unknown[indices].any(axis=1)]
    colors = np.asarray(rgb, dtype=float).reshape(-1,3)/255
    lap = csr_matrix((h*w,h*w), dtype=float)
    for start in range(0,len(indices),4096):
        ids = indices[start:start+4096]
        centered = colors[ids] - colors[ids].mean(axis=1,keepdims=True)
        cov = np.einsum('nki,nkj->nij',centered,centered)/9 + np.eye(3)*epsilon/9
        local = np.eye(9)[None] - (1 + np.einsum('nki,nij,nlj->nkl',centered,np.linalg.inv(cov),centered))/9
        rows = np.repeat(ids,9,axis=1).ravel()
        cols = np.tile(ids,(1,9)).ravel()
        lap += coo_matrix((local.ravel(),(rows,cols)),shape=lap.shape).tocsr()
    u = np.flatnonzero(unknown)
    known = np.flatnonzero(~unknown)
    system = lap[u][:,u].tocsr()
    rhs = -lap[u][:,known] @ result[known]
    diagonal = system.diagonal()
    if not np.isfinite(diagonal).all() or np.any(diagonal <= 0):
        raise ValueError('unconstrained/degenerate matting field')
    count = [0]
    def step(_): count[0] += 1
    if solver=='direct':
        with warnings.catch_warnings():
            warnings.simplefilter('error',MatrixRankWarning)
            try:solved=spsolve(system,rhs)
            except MatrixRankWarning as exc:raise ValueError('singular matting field') from exc
        info=0
    else:
        solved, info = cg(system,rhs,M=diags(1/diagonal),rtol=1e-7,atol=1e-10,
                          maxiter=max_iterations,callback=step)
    if info != 0 or not np.isfinite(solved).all():
        raise ValueError('closed-form solver did not converge; no silent mask fallback')
    residual = float(np.linalg.norm(system@solved-rhs))
    result[u] = np.clip(solved,0,1)
    return result.reshape(h,w), dict(solver=solver,iterations=count[0],raw_solver_residual=residual,
                                     clipped_solver_residual=float(np.linalg.norm(system@result[u]-rhs)),
                                     clipped_alpha_values=int(((solved<0)|(solved>1)).sum()),
                                     unknown_pixels=int(unknown.sum()))


def interpolate_smooth_field(rgb, mask):
    """Joint finite-difference biharmonic solve on explicit unknown pixels.

    The standard 13-point squared-Laplacian stencil follows the same boundary
    system as scikit-image inpaint_biharmonic for interior masks. This bounded
    implementation requires two observed border pixels and never copies texture.
    """
    from scipy.sparse import coo_matrix
    from scipy.sparse.linalg import spsolve, MatrixRankWarning
    import warnings
    rgb=np.asarray(rgb);mask=np.asarray(mask)
    if (mask.ndim!=2 or mask.dtype!=np.bool_ or rgb.dtype!=np.uint8):
        raise ValueError('smooth interpolation requires uint8 RGB and boolean mask')
    h,w=mask.shape
    if h*w>MAX_LAYER_PIXELS or rgb.shape!=(h,w,3) or not mask.any():
        raise ValueError('bounded nonempty smooth field required')
    if mask[:2].any() or mask[-2:].any() or mask[:,:2].any() or mask[:,-2:].any():
        raise ValueError('smooth interpolation needs two observed boundary pixels')
    ys,xs=np.nonzero(mask); n=len(xs)
    lookup=np.full((h,w),-1,dtype=int);lookup[mask]=np.arange(n)
    rows=[];cols=[];values=[];rhs=np.zeros((n,3))
    stencil=[(0,0,20),(-1,0,-8),(1,0,-8),(0,-1,-8),(0,1,-8),
             (-1,-1,2),(-1,1,2),(1,-1,2),(1,1,2),(-2,0,1),(2,0,1),(0,-2,1),(0,2,1)]
    for dy,dx,coefficient in stencil:
        target=lookup[ys+dy,xs+dx]; inside=target>=0
        rows.append(np.flatnonzero(inside));cols.append(target[inside])
        values.append(np.full(int(inside.sum()),coefficient))
        rhs[~inside]-=coefficient*rgb[ys[~inside]+dy,xs[~inside]+dx].astype(float)
    matrix=coo_matrix((np.concatenate(values),(np.concatenate(rows),np.concatenate(cols))),shape=(n,n)).tocsr()
    with warnings.catch_warnings():
        warnings.simplefilter('error',MatrixRankWarning)
        try:solved=spsolve(matrix,rhs)
        except MatrixRankWarning as exc:raise ValueError('singular smooth field') from exc
    if not np.isfinite(solved).all():raise ValueError('nonfinite smooth interpolation')
    low=rgb[~mask].min(axis=0);high=rgb[~mask].max(axis=0)
    bounded=np.rint(np.clip(solved,low,high)).astype('uint8')
    output=rgb.copy();output[mask]=bounded
    return output,dict(method='biharmonic_13_point / SciPy spsolve',inferred_pixels=n,
        raw_system_residual=float(np.linalg.norm(matrix@solved-rhs)),
        clamped_channels=int(((solved<low)|(solved>high)).sum()))


def extract_layer(source, plan):
    from source_objects import _box, _points, _annotations, _png
    validate_layer_options(plan)
    image = read_image(source,plan['source_sha256'])
    x,y,w,h = _box(plan['context_bbox'], image.size)
    if w*h > MAX_LAYER_PIXELS or min(w,h) < 3:
        raise ValueError('layer context exceeds closed-form processing bound')
    crop = image.convert('RGBA').crop((x,y,x+w,y+h))
    if crop.getextrema()[3] != (255,255):
        raise ValueError('preserve existing alpha; do not infer it twice')
    fg = _points(plan['foreground'],(x,y,w,h),'foreground',True)
    bg = _points(plan['background'],(x,y,w,h),'background',True)
    labels = _annotations(plan.get('annotations',[]),(x,y,w,h),fg,bg)
    original = np.asarray(crop)[:,:,:3].copy()
    pixels = original.copy()
    settings = plan['matting']
    patches=[]
    for p in settings['background_patches']:
        px,py,pw,ph = _box(p,image.size)
        if pw*ph > MAX_LAYER_PIXELS: raise ValueError('background sample exceeds processing bound')
        patch = image.convert('RGBA').crop((px,py,px+pw,py+ph))
        if patch.getextrema()[3] != (255,255): raise ValueError('background samples must be opaque')
        patches.append(np.asarray(patch)[:,:,:3].reshape(-1,3))
    samples=np.concatenate(patches)
    background=np.median(samples,axis=0)
    deviation=float(np.max(np.abs(samples-background)))
    if deviation > settings['background_tolerance']:
        raise ValueError('background is not the declared constant matte; no hidden plane fitting')
    missing=np.zeros((h,w),dtype=bool)
    ranges=[]
    for o in plan.get('occlusions',[]):
        marked=_annotations([dict(m,label='foreground') for m in o['marks']],(x,y,w,h),[],[]) == 1
        if not marked.any() or marked[0].any() or marked[-1].any() or marked[:,0].any() or marked[:,-1].any():
            raise ValueError('smooth occlusion must be bounded by observed context')
        if np.any(marked & ((labels == 0) | (labels == 1))) or np.any(marked & missing):
            raise ValueError('occlusion overlaps hard ownership or another occlusion')
        missing |= marked
        ranges.append(dict(id=o['id'],method='biharmonic_13_point',
                           pixels=int(marked.sum()),authorization=o['authorization']))
    interpolation=None
    if missing.any():
        pixels,interpolation=interpolate_smooth_field(original,missing)
    labels[missing]=255  # Occlusion is unknown, never transparent background.
    alpha, solver = closed_form_alpha(pixels,labels,epsilon=settings['epsilon'],
        max_iterations=settings.get('max_iterations'),solver=settings.get('solver','cg'))
    # Known B bounds the feasible alpha interval: require F in the RGB cube.
    # Increase only inferred coverage when necessary; this chooses a feasible
    # solution, not uniquely recovered true foreground. Keep the adjustment map.
    c=pixels.astype(float)
    with np.errstate(divide='ignore',invalid='ignore'):
        lower=np.where(c>=background,(c-background)/np.maximum(255-background,1e-12),
                       (background-c)/np.maximum(background,1e-12)).max(axis=2)
    unknown=(labels!=0)&(labels!=1)
    effective=np.where(unknown,np.maximum(alpha,np.clip(lower,0,1)),alpha)
    # Upward quantization keeps the RGB feasibility bound; no alpha thresholding.
    coverage=np.ceil(effective*255).clip(0,255).astype('uint8')
    rgb, inverse=unmix_background(pixels,coverage/255,background)
    rgba=Image.fromarray(np.dstack((rgb,coverage)))
    visible=coverage>0
    if not visible.any(): raise ValueError('empty estimated source layer')
    # Keep full original coordinate domain, including zero-alpha padding.
    outputs={'context_mask':_png(Image.fromarray((visible*255).astype('uint8'))),
             'alpha':_png(Image.fromarray(coverage)), 'rgba':_png(rgba),
             'trimap':_png(Image.fromarray(np.where(labels==0,0,np.where(labels==1,255,128)).astype('uint8'))),
             'occlusion_mask':_png(Image.fromarray((missing*255).astype('uint8'))),
             'coverage_adjustment':_png(Image.fromarray(np.rint((effective-alpha)*255).astype('uint8'))),
             'reconstructed_color':_png(Image.fromarray(pixels))}
    issues=[]
    reserved=plan['reserved_regions']
    if not isinstance(reserved,list) or len(reserved)>1000:
        raise ValueError('reserved_regions must be a bounded rectangle list')
    overlaps=[]
    for index,region in enumerate(reserved):
        rx,ry,rw,rh=_box(region,image.size)
        a,b,c,d=max(0,rx-x),max(0,ry-y),min(w,rx+rw-x),min(h,ry+rh-y)
        count=int(visible[b:d,a:c].sum()) if a<c and b<d else 0
        if count: overlaps.append(dict(region_index=index,foreground_pixels=count))
    if overlaps:issues.append('reserved native content intersects layer; inspect restored/remaining overprints')
    if visible[0].any() or visible[-1].any() or visible[:,0].any() or visible[:,-1].any():
        issues.append('estimated coverage touches context edge; inspect truncation')
    if missing.any(): issues.append('annotated smooth-field pixels are inferred, not original observations')
    evidence=dict(status='CANDIDATE',plan=plan,source_sha256=plan['source_sha256'],
        plan_sha256=digest(json.dumps(plan,sort_keys=True).encode()),source_size=list(image.size),
        context_bbox=[x,y,w,h],source_bbox=[x,y,w,h],engine='closed-form color Laplacian / SciPy '+settings.get('solver','cg'),
        alpha_inferred=True,alpha_semantics='continuous_estimated_coverage',rgb_semantics='estimated_straight_foreground',
        hidden_content_generated=bool(missing.any()),hidden_content_scope='smooth_field_only',
        background_rgb=background.tolist(),background_sample_max_deviation=deviation,
        foreground_pixels=int(visible.sum()),intermediate_alpha_pixels=int(((coverage>0)&(coverage<255)).sum()),
        feasible_alpha_adjusted_pixels=int((effective>alpha+1e-10).sum()),
        output_alpha_adjustment_max=float(np.abs(coverage/255-alpha).max()),
        output_alpha_adjustment_mean=float(np.abs(coverage/255-alpha).mean()),reserved_overlaps=overlaps,
        solver=solver,inverse=inverse,interpolation=interpolation,occlusions=ranges,issues=issues,visual_review='NOT_PERFORMED',
        outputs_sha256={k:digest(v) for k,v in outputs.items()})
    return outputs,evidence


def read_layer_bundle(binding, source_hash, crop):
    """Read the authoritative estimator receipt, not caller-assembled RGB claims."""
    from native_paint import keys
    keys(binding,{'path','sha256'},{'path','sha256'},'source layer evidence')
    path=Path(binding['path'])
    payload=path.read_bytes()
    if digest(payload)!=binding['sha256']:raise ValueError('source layer evidence changed')
    evidence=json.loads(payload)
    plan=evidence.get('plan')
    if (not isinstance(plan,dict) or plan.get('method')!='closed_form'
            or evidence.get('source_sha256')!=source_hash or plan.get('source_sha256')!=source_hash
            or evidence.get('source_bbox')!=list(crop) or plan.get('context_bbox')!=list(crop)
            or evidence.get('plan_sha256')!=digest(json.dumps(plan,sort_keys=True).encode())
            or evidence.get('alpha_semantics')!='continuous_estimated_coverage'
            or evidence.get('rgb_semantics')!='estimated_straight_foreground'):
        raise ValueError('source layer recipe/semantics binding changed')
    validate_layer_options(plan)
    expected={'context_mask','alpha','rgba','trimap','occlusion_mask','coverage_adjustment','reconstructed_color'}
    if set(evidence.get('outputs_sha256',{}))!=expected:raise ValueError('incomplete source layer bundle')
    for key,hsh in evidence['outputs_sha256'].items():
        if digest((path.parent/(key+'.png')).read_bytes())!=hsh:
            raise ValueError('source layer bundle bytes changed')
    layer=read_image(path.parent/'rgba.png')
    alpha=read_image(path.parent/'alpha.png',alpha=True)
    missing=read_image(path.parent/'occlusion_mask.png',alpha=True)
    if (layer.mode!='RGBA' or layer.size!=tuple(crop[2:]) or alpha.size!=layer.size or missing.size!=layer.size
            or not np.array_equal(np.asarray(alpha),np.asarray(layer)[:,:,3])
            or evidence['hidden_content_generated']!=bool(np.asarray(missing).any())):
        raise ValueError('source layer coverage/occlusion files disagree')
    return layer,dict(method='estimated_source_layer',bundle=dict(binding),source_sha256=source_hash,
        source_bbox=list(crop),plan_sha256=evidence['plan_sha256'],
        alpha_semantics=evidence['alpha_semantics'],rgb_semantics=evidence['rgb_semantics'],
        hidden_content_generated=evidence['hidden_content_generated'],physical_layer_identity='NOT_VERIFIED')
