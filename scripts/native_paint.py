"""Bounded native DrawingML paint. No SVG-gradient conversion or inferred lighting.

Geometry is independent of paint. Linear angles use Office degrees clockwise.
Path stop positions use Office's circumscribed radial domain, not a source radius.
"""
from __future__ import annotations

import copy
import math
import re


def scalar(value, label, low=0, high=1):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f'{label}: finite number in {low}..{high} required')
    return float(value)


def keys(obj, allowed, required, label):
    if not isinstance(obj, dict) or set(obj) - set(allowed) or set(required) - set(obj):
        raise ValueError(f'{label}: missing or unsupported fields')


def rgb(value):
    if not isinstance(value, str) or not re.fullmatch(r'#?[0-9a-fA-F]{6}', value):
        raise ValueError('paint color must be six-digit RGB')
    return value.lstrip('#').upper()


def normalize_paint(value, *, _depth=0):
    """Return one canonical paint value; None and RGB strings remain compatible."""
    if _depth > 8:
        raise ValueError('composite paint exceeds depth 8')
    if value is None:
        return {'kind': 'none'}
    if isinstance(value, str):
        return {'kind': 'solid', 'color': rgb(value), 'alpha': 1.0}
    if not isinstance(value, dict):
        raise ValueError('paint must be an object, RGB string or null')
    kind = value.get('kind')
    if kind == 'composite':
        return _compile_composite(value, _depth)
    allowed = {'none': {'kind'}, 'group': {'kind'}, 'solid': {'kind', 'color', 'alpha', 'source_samples'},
               'linear': {'kind', 'angle', 'stops', 'source_samples'},
               'path': {'kind', 'focus', 'stops', 'source_samples'}}
    if kind not in allowed:
        raise ValueError('paint kind must be none, group, solid, linear or path')
    keys(value, allowed[kind], {'kind'}, 'paint')
    result = {'kind': kind}
    if kind == 'solid':
        result.update(color=rgb(value.get('color')), alpha=scalar(value.get('alpha', 1), 'alpha'))
    if kind in ('linear', 'path'):
        stops = value.get('stops')
        if not isinstance(stops, list) or not 2 <= len(stops) <= 32:
            raise ValueError('gradient needs 2..32 ordered stops')
        result['stops'] = []
        for stop in stops:
            keys(stop, {'position', 'color', 'alpha'}, {'position', 'color'}, 'stop')
            result['stops'].append({'position': scalar(stop['position'], 'stop position'),
                                    'color': rgb(stop['color']), 'alpha': scalar(stop.get('alpha', 1), 'stop alpha')})
        positions = [round(s['position'] * 100000) for s in result['stops']]
        if result['stops'][0]['position'] != 0 or result['stops'][-1]['position'] != 1 or any(a >= b for a, b in zip(positions, positions[1:])):
            raise ValueError('stops must strictly increase at Office precision, spanning 0..1')
        if kind == 'linear':
            result['angle'] = scalar(value.get('angle'), 'angle', 0, 360) % 360
        else:
            focus = value.get('focus')
            if not isinstance(focus, list) or len(focus) != 2:
                raise ValueError('path focus must be [u,v]')
            result['focus'] = [scalar(v, 'focus') for v in focus]
    if 'source_samples' in value:
        evidence = value['source_samples']
        keys(evidence, {'sha256', 'size', 'patches'}, {'sha256', 'size', 'patches'}, 'source_samples')
        if not isinstance(evidence['sha256'], str) or not re.fullmatch('[0-9a-f]{64}', evidence['sha256']):
            raise ValueError('source_samples requires source SHA-256')
        size = evidence['size']
        if not isinstance(size, list) or len(size) != 2 or any(type(v) is not int or v <= 0 for v in size):
            raise ValueError('source_samples requires positive source size')
        patches = evidence['patches']
        count = 1 if kind == 'solid' else len(result['stops'])
        if not isinstance(patches, list) or len(patches) != count:
            raise ValueError('source patch count must match paint colors')
        for patch in patches:
            if not isinstance(patch, list) or len(patch) != 4 or any(type(v) is not int for v in patch):
                raise ValueError('source patch must be integer [x,y,w,h]')
            x, y, w, h = patch
            if min(x, y) < 0 or min(w, h) <= 0 or x+w > size[0] or y+h > size[1] or w*h > 1_000_000:
                raise ValueError('source patch outside bounds or sampling budget')
        result['source_samples'] = copy.deepcopy(evidence)
    return result


def sampled_paints(value):
    """Validated source leaves, not computed colors mislabelled as samples."""
    normalize_paint(value)
    def visit(paint):
        if isinstance(paint, dict):
            if paint.get('kind') == 'composite':
                yield from visit(paint['backdrop'])
                yield from visit(paint['source'])
            elif 'source_samples' in paint:
                yield paint
    return list(visit(value))


def _compile_composite(value, depth):
    """Affine color operation on one paint domain; not group compositing.

    With opaque backdrop and a constant source, Normal/Multiply/Screen are
    affine in backdrop RGB, so each continuous stop can be transformed without
    replacing the gradient by bands. Colors are encoded sRGB, not linear light.
    The expression stays in the canonical input and is recomputed on each build.
    """
    keys(value, {'kind', 'mode', 'backdrop', 'source', 'opacity'},
         {'kind', 'mode', 'backdrop', 'source'}, 'composite paint')
    mode = value['mode']
    if mode not in ('normal', 'multiply', 'screen'):
        raise ValueError('composite mode must be normal, multiply or screen')
    backdrop = normalize_paint(value['backdrop'], _depth=depth+1)
    source = normalize_paint(value['source'], _depth=depth+1)
    if backdrop['kind'] not in ('solid', 'linear', 'path') or source['kind'] != 'solid':
        raise ValueError('composite requires solid/gradient backdrop and constant solid source')
    entries = [backdrop] if backdrop['kind'] == 'solid' else backdrop['stops']
    if any(s['alpha'] != 1 for s in entries):
        raise ValueError('composite backdrop must be opaque throughout')
    alpha = scalar(value.get('opacity', 1), 'composite opacity') * source['alpha']
    foreground = [int(source['color'][i:i+2], 16)/255 for i in (0, 2, 4)]
    result = copy.deepcopy(backdrop)
    # Sampling evidence describes inputs only; the recipe retains that evidence.
    result.pop('source_samples', None)
    targets = [result] if result['kind'] == 'solid' else result['stops']
    for target in targets:
        background = [int(target['color'][i:i+2], 16)/255 for i in (0, 2, 4)]
        mixed = []
        for b, s in zip(background, foreground):
            blend = s if mode == 'normal' else b*s if mode == 'multiply' else b+s-b*s
            mixed.append(round(255*((1-alpha)*b+alpha*blend)))
        target['color'] = ''.join(f'{v:02X}' for v in mixed)
    return result


def paint_xml(value, opacity=1):
    """Emit real Office fills; source_samples are provenance, never OOXML attributes."""
    paint = normalize_paint(value)
    opacity = scalar(opacity, 'opacity')
    def color_xml(color, alpha):
        return f'<a:srgbClr val="{color}"><a:alpha val="{round(alpha*opacity*100000)}"/></a:srgbClr>'
    kind = paint['kind']
    if kind == 'group':
        if opacity != 1:
            raise ValueError('group fill cannot apply a separate leaf opacity')
        return '<a:grpFill/>'
    if kind == 'none':
        return '<a:noFill/>'
    if kind == 'solid':
        return '<a:solidFill>' + color_xml(paint['color'], paint['alpha']) + '</a:solidFill>'
    stops = ''.join(f'<a:gs pos="{round(s["position"]*100000)}">{color_xml(s["color"], s["alpha"])}</a:gs>' for s in paint['stops'])
    if kind == 'linear':
        geometry = f'<a:lin ang="{round(paint["angle"]*60000)}" scaled="0"/>'
    else:
        u, v = [round(n * 100000) for n in paint['focus']]
        geometry = (f'<a:path path="circle"><a:fillToRect l="{u}" t="{v}" '
                    f'r="{100000-u}" b="{100000-v}"/></a:path><a:tileRect/>')
    return f'<a:gradFill rotWithShape="1"><a:gsLst>{stops}</a:gsLst>{geometry}</a:gradFill>'


def centered_radial_paint(stops, radius, bounds):
    """Map a centered circular source profile into Office radial stop positions.

    bounds is [x,y,width,height] of the actual native paint owner. The caller must
    establish source concentricity; this is not an off-center or elliptical fit.
    A group-owned fill preserves that owner's domain for partial children.
    """
    if not isinstance(bounds, (list, tuple)) or len(bounds) != 4:
        raise ValueError('radial bounds require [x,y,width,height]')
    x, y, w, h = [scalar(v, 'radial bound', -1e9, 1e9) for v in bounds]
    if min(w, h) <= 0:
        raise ValueError('radial bounds must have positive extent')
    radius = scalar(radius, 'source radius', 1e-9, 1e9)
    native_radius = math.hypot(w, h)/2
    if radius >= native_radius:
        raise ValueError('source radius must lie inside the Office circumscribed domain')
    result = normalize_paint({'kind':'path', 'focus':[.5,.5], 'stops':stops})
    if len(result['stops']) > 31:
        raise ValueError('source radial profile needs room for one constant edge stop')
    ratio = radius/native_radius
    for stop in result['stops']:
        stop['position'] *= ratio
    result['stops'].append(dict(result['stops'][-1], position=1.0))
    return normalize_paint(result)


def normalize_compositing(value):
    """Native source-over effect boundary, not PDF non-isolated blend conversion.

    Mask is an alpha-valued native Paint in the effect owner's coordinate domain.
    It is applied once after children are painted, before the constant opacity.
    Colors are deliberately white: RGB luminance is not implicitly an alpha mask.
    """
    if value is None:
        return {'opacity': 1.0, 'alpha_mask': None}
    keys(value, {'opacity', 'alpha_mask'}, set(), 'compositing')
    opacity = scalar(value.get('opacity', 1), 'compositing opacity')
    mask = value.get('alpha_mask')
    if mask is not None:
        if not isinstance(mask, dict) or mask.get('kind') not in ('solid', 'linear', 'path'):
            raise ValueError('alpha_mask needs a concrete alpha Paint')
        samples = [mask] if mask['kind'] == 'solid' else mask.get('stops')
        if not isinstance(samples, list) or any(not isinstance(s, dict) or 'alpha' not in s for s in samples):
            raise ValueError('alpha_mask needs explicitly declared alpha samples')
        mask = normalize_paint(mask)
        if mask['kind'] not in ('solid', 'linear', 'path') or 'source_samples' in mask:
            raise ValueError('alpha_mask needs explicit alpha Paint, not color samples or inherited fill')
        stops = [mask] if mask['kind'] == 'solid' else mask['stops']
        if any(s['color'] != 'FFFFFF' for s in stops):
            raise ValueError('alpha_mask uses white RGB and explicit alpha, not luminosity colors')
    return {'opacity': opacity, 'alpha_mask': mask}


def compositing_xml(value):
    """Emit group/leaf effects once; never multiply opacity into each child."""
    state = normalize_compositing(value)
    effects = ''
    if state['alpha_mask'] is not None:
        effects += '<a:alphaMod><a:cont><a:fill>'+paint_xml(state['alpha_mask'])+'</a:fill></a:cont></a:alphaMod>'
    if state['opacity'] != 1:
        effects += f'<a:alphaModFix amt="{round(state["opacity"]*100000)}"/>'
    return '<a:effectDag>'+effects+'</a:effectDag>' if effects else ''
