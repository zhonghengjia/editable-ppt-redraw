"""Visible pixel-support diagnostics, not anatomy segmentation or continuous geometry.

Uses existing Pillow/NumPy only. The selector is identical for source and render;
no registration, hole filling, morphology, random sampling or fragment omission.
"""
from __future__ import annotations

from collections import deque
import math

MAX_PAIRS = 50_000_000
MAX_PIXELS = 1_000_000


class GeometryLimit(ValueError):
    """Applicable exact diagnostic exceeds the bounded local profile."""


def selector_errors(selector):
    errors = []
    if not isinstance(selector, dict):
        return ['selector must be an object']
    if set(selector) != {'rgb', 'differences', 'observation'}:
        errors.append('selector requires only rgb, differences and observation')
    rgb = selector.get('rgb')
    if not isinstance(rgb, list) or len(rgb) != 3 or not all(
            isinstance(v, list) and len(v) == 2 and all(type(n) is int for n in v)
            and 0 <= v[0] <= v[1] <= 255 for v in rgb):
        errors.append('rgb must be three inclusive integer [min,max] ranges in 0..255')
    differences = selector.get('differences')
    if not isinstance(differences, list) or len(differences) > 6:
        errors.append('differences must be a list of at most six [channel,channel,min,max] constraints')
    else:
        pairs = set()
        for rule in differences:
            if not isinstance(rule, list) or len(rule) != 4 or not all(type(v) is int for v in rule):
                errors.append('invalid channel difference constraint')
                continue
            a, b, lo, hi = rule
            if a not in (0,1,2) or b not in (0,1,2) or a == b or not -255 <= lo <= hi <= 255 or (a,b) in pairs:
                errors.append('invalid or duplicate channel difference constraint')
            pairs.add((a,b))
    if not isinstance(selector.get('observation'), str) or not selector['observation'].strip():
        errors.append('selector observation must describe source evidence and confounders before authoring')
    return errors


def select(image, selector):
    import numpy as np
    from PIL import Image
    errors = selector_errors(selector)
    if errors:
        raise ValueError('; '.join(errors))
    if image.width * image.height > MAX_PIXELS:
        raise GeometryLimit('visible-support crop exceeds one million pixels')
    # Same explicit matte on both inputs, including partially transparent PNGs.
    visible = Image.alpha_composite(Image.new('RGBA', image.size, 'white'), image.convert('RGBA'))
    rgb = np.asarray(visible, dtype=np.int16)[:, :, :3]
    mask = np.ones(rgb.shape[:2], dtype=bool)
    for channel, (lo,hi) in enumerate(selector['rgb']):
        mask &= (rgb[:,:,channel] >= lo) & (rgb[:,:,channel] <= hi)
    for a,b,lo,hi in selector['differences']:
        delta = rgb[:,:,a] - rgb[:,:,b]
        mask &= (delta >= lo) & (delta <= hi)
    return mask


def checked_mask(value):
    import numpy as np
    if not isinstance(value, np.ndarray) or value.dtype != np.bool_ or value.ndim != 2 or min(value.shape) < 1:
        raise ValueError('mask must be a nonempty 2D Boolean array')
    if value.size > MAX_PIXELS:
        raise GeometryLimit('mask exceeds one million pixels')
    return value


def label_regions(mask, diagonal=True):
    """Deterministic row-major components shared by source ownership and QA."""
    import numpy as np
    mask = checked_mask(mask)
    h,w = mask.shape
    labels = np.zeros(mask.shape, dtype=np.int32)
    neighbours = [(-1,0),(1,0),(0,-1),(0,1)]
    if diagonal:
        neighbours += [(-1,-1),(-1,1),(1,-1),(1,1)]
    regions = []
    for y,x in zip(*np.nonzero(mask)):
        if labels[y,x]:
            continue
        identity = len(regions)+1
        x,y = int(x),int(y)
        queue = deque([(y,x)]); labels[y,x] = identity
        count, touches = 0, False
        left,right,top,bottom = x,x,y,y
        while queue:
            cy,cx = queue.popleft(); count += 1
            touches |= cy == 0 or cx == 0 or cy == h-1 or cx == w-1
            left,right,top,bottom = min(left,cx),max(right,cx),min(top,cy),max(bottom,cy)
            for dy,dx in neighbours:
                ny,nx = cy+dy,cx+dx
                if 0 <= ny < h and 0 <= nx < w and mask[ny,nx] and not labels[ny,nx]:
                    labels[ny,nx] = identity; queue.append((ny,nx))
        regions.append(dict(id=identity, area=count, bbox=[left,top,right-left+1,bottom-top+1], touches_border=touches))
    return labels, regions


def topology(mask):
    """Foreground 8-connected / background 4-connected; all pixels retained."""
    mask = checked_mask(mask)
    _, foreground = label_regions(mask, True)
    _, background = label_regions(~mask, False)
    components = [r['area'] for r in foreground]
    holes = [r['area'] for r in background if not r['touches_border']]
    return dict(components=len(components), holes=len(holes),
                largest_component_areas=sorted(components, reverse=True)[:10],
                largest_hole_areas=sorted(holes, reverse=True)[:10],
                foreground_pixels=int(mask.sum()), connectivity='foreground8_background4')


def owned_support(mask, recipe, source_sha256, crop, selector_sha256):
    """Source-only membership selection. Never applied to an evaluated render."""
    mask = checked_mask(mask)
    keys = {'part_id','source_sha256','source_bbox','selector_sha256','seeds','observation'}
    if not isinstance(recipe,dict) or set(recipe) != keys:
        raise ValueError('ownership requires exactly part_id, source_sha256, source_bbox, selector_sha256, seeds, observation')
    for key in ('part_id','observation'):
        if not isinstance(recipe[key],str) or not recipe[key].strip():
            raise ValueError('ownership '+key+' must be nonempty text')
    if recipe['source_sha256'] != source_sha256 or recipe['selector_sha256'] != selector_sha256:
        raise ValueError('ownership source or selector hash mismatch')
    if (not isinstance(recipe['source_bbox'],list) or len(recipe['source_bbox']) != 4
            or not all(type(v) is int for v in recipe['source_bbox']) or recipe['source_bbox'] != crop):
        raise ValueError('ownership source_bbox mismatch')
    seeds = recipe['seeds']
    if not isinstance(seeds,list) or not 1 <= len(seeds) <= 100:
        raise ValueError('ownership requires 1..100 crop-local source witnesses')
    h,w = mask.shape
    for seed in seeds:
        if (not isinstance(seed,list) or len(seed) != 2 or not all(type(v) is int for v in seed)
                or not 0 <= seed[0] < w or not 0 <= seed[1] < h or not mask[seed[1],seed[0]]):
            raise ValueError('ownership seed must hit source support; no snapping to nearest component')
    if len({tuple(s) for s in seeds}) != len(seeds):
        raise ValueError('ownership seeds must be unique')
    labels, regions = label_regions(mask)
    if len(regions) > 2000:
        raise GeometryLimit('ownership ledger exceeds 2000 components; no fragments discarded')
    identities = {int(labels[y,x]) for x,y in seeds}
    if len(identities) != 1:
        raise ValueError('ownership witnesses disagree: one connected visible part required per recipe')
    identity = identities.pop()
    return labels == identity, dict(recipe=recipe, selected_component=identity,
        unassigned_components=[r for r in regions if r['id'] != identity],
        selected=regions[identity-1], semantics_verified=False)


def boundary(mask):
    import numpy as np
    mask = checked_mask(mask)
    padded = np.pad(mask, 1)
    inside = mask & padded[:-2,1:-1] & padded[2:,1:-1] & padded[1:-1,:-2] & padded[1:-1,2:]
    return np.argwhere(mask & ~inside).astype(np.float64)


def distances(first, second):
    """Exact nearest distances on pixel-center boundary sets, in bounded blocks."""
    import numpy as np
    a,b = boundary(first), boundary(second)
    if len(a) == 0 or len(b) == 0:
        raise ValueError('empty selected source or render support cannot prove geometry')
    if len(a)*len(b) > MAX_PAIRS:
        raise GeometryLimit('exact boundary comparison exceeds 50 million pairs; no subsampling performed')
    da,db = np.full(len(a), np.inf), np.full(len(b), np.inf)
    # At most 512x512 float pairs per temporary, independent of region size.
    for i in range(0,len(a),512):
        aa = a[i:i+512]
        for j in range(0,len(b),512):
            bb = b[j:j+512]
            squared = (aa[:,None,0]-bb[None,:,0])**2 + (aa[:,None,1]-bb[None,:,1])**2
            da[i:i+len(aa)] = np.minimum(da[i:i+len(aa)], squared.min(axis=1))
            db[j:j+len(bb)] = np.minimum(db[j:j+len(bb)], squared.min(axis=0))
    da,db = np.sqrt(da),np.sqrt(db)
    ia,ib = int(da.argmax()),int(db.argmax())
    direction,point = ('source_to_render',a[ia]) if da[ia] >= db[ib] else ('render_to_source',b[ib])
    return dict(boundary_max_px=float(max(da.max(),db.max())),
                boundary_p95_px=float(max(np.percentile(da,95),np.percentile(db,95))),
                source_to_render_max_px=float(da.max()), render_to_source_max_px=float(db.max()),
                worst_boundary_point_xy=[int(point[1]),int(point[0])], worst_direction=direction,
                boundary_samples=[len(a),len(b)], distance_basis='exact_pixel_center_sets_not_continuous_curves')


def compare_masks(first, second):
    import numpy as np
    first,second = checked_mask(first),checked_mask(second)
    if first.shape != second.shape:
        raise ValueError('mask dimensions must agree; no fitted registration')
    if not first.any() or not second.any():
        raise ValueError('empty selected source or render support cannot prove geometry')
    if first.all() or second.all():
        raise ValueError('full-crop support has no separated background; selector cannot prove the requested silhouette')
    missing,extra = first & ~second,second & ~first
    def box(mask):
        yy,xx = np.nonzero(mask)
        return None if len(xx) == 0 else [int(xx.min()),int(yy.min()),int(xx.max()-xx.min()+1),int(yy.max()-yy.min()+1)]
    result = dict(iou=float((first & second).sum()/(first | second).sum()),
                  missing_pixels=int(missing.sum()), extra_pixels=int(extra.sum()),
                  missing_bbox=box(missing), extra_bbox=box(extra),
                  source_topology=topology(first), render_topology=topology(second))
    result.update(distances(first,second))
    return result


def coverage_changes(first, second):
    """Locate new voids and filled source holes; never repair either mask.

    Compare position and source support, not only equal hole counts. Missing
    regions connected to the crop edge remain reported as open coverage losses.
    """
    import numpy as np
    first,second=checked_mask(first),checked_mask(second)
    if first.shape!=second.shape:
        raise ValueError('coverage masks have different dimensions')
    def events(voids, occupied):
        labels,regions=label_regions(voids,diagonal=False)
        if len(regions)>2000:
            raise GeometryLimit('coverage event ledger exceeds 2000 regions')
        counts=np.bincount(labels[occupied].ravel(),minlength=len(regions)+1)
        return [dict(region, changed_pixels=int(counts[region['id']]))
                for region in regions if not region['touches_border'] and counts[region['id']]]
    introduced=events(~second,first)
    filled=events(~first,second)
    _,missing=label_regions(first & ~second,diagonal=False)
    if len(missing)>2000:
        raise GeometryLimit('missing-support ledger exceeds 2000 regions')
    return dict(introduced_holes=introduced,filled_source_holes=filled,
        introduced_hole_pixels=sum(r['changed_pixels'] for r in introduced),
        filled_source_hole_pixels=sum(r['changed_pixels'] for r in filled),
        missing_support_regions=missing,
        scope='source-visible support only; crop-edge background is not a hole')


def validate_structure(value):
    if not isinstance(value, dict):
        return ['structure must be an object']
    errors = selector_errors(value.get('selector'))
    expected = {'selector','min_iou','max_boundary_px','max_boundary_p95_px','topology','rationale'}
    if set(value) not in (expected, expected | {'coverage'}):
        errors.append('structure requires exactly selector, min_iou, max_boundary_px, max_boundary_p95_px, topology, rationale')
    for key in ('min_iou','max_boundary_px','max_boundary_p95_px'):
        number = value.get(key)
        if type(number) not in (float,int) or not math.isfinite(number) or not 0 <= number <= (1 if key == 'min_iou' else 20):
            errors.append(key + ' outside finite structural profile')
    if type(value.get('min_iou')) in (float,int) and value['min_iou'] <= 0:
        errors.append('min_iou must be positive')
    if value.get('topology') not in ('exact','report_only'):
        errors.append('topology must be exact or report_only')
    if not isinstance(value.get('rationale'),str) or not value['rationale'].strip():
        errors.append('structure rationale must freeze tolerances and explain topology choice before authoring')
    if 'coverage' in value:
        coverage=value['coverage']
        fields={'max_introduced_hole_pixels','max_filled_source_hole_pixels'}
        if not isinstance(coverage,dict) or set(coverage)!=fields or any(
                type(v)is not int or not 0<=v<=MAX_PIXELS for v in coverage.values()):
            errors.append('coverage requires bounded integer new-hole and filled-source-hole pixel limits')
    return errors


def compare(first, second, contract):
    errors = validate_structure(contract)
    if errors:
        raise ValueError('; '.join(errors))
    result = compare_masks(select(first,contract['selector']), select(second,contract['selector']))
    if 'coverage' in contract:
        result['coverage']=coverage_changes(select(first,contract['selector']),select(second,contract['selector']))
        result['coverage']['passed']=all(result['coverage'][k] <= contract['coverage']['max_'+k]
            for k in ('introduced_hole_pixels','filled_source_hole_pixels'))
    topology_equal = all(result['source_topology'][key] == result['render_topology'][key] for key in ('components','holes'))
    result.update(topology_equal=topology_equal, topology_gate=contract['topology'],
                  coordinate_frame='region_local_source_pixels', matte='white',
                  semantic_segmentation='NOT_VERIFIED')
    result['passed'] = result['iou'] >= contract['min_iou'] and result['boundary_max_px'] <= contract['max_boundary_px'] and result['boundary_p95_px'] <= contract['max_boundary_p95_px'] and (contract['topology'] == 'report_only' or topology_equal) and result.get('coverage',{}).get('passed',True)
    return result
