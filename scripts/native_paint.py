"""Bounded native DrawingML paint. No SVG-gradient conversion or inferred lighting.

Geometry is independent of paint. Linear angles use Office degrees clockwise
from left-to-right; path gradients use the object's normalized bounding box.
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


def normalize_paint(value):
    """Return one canonical paint value; None and RGB strings remain compatible."""
    if value is None:
        return {'kind': 'none'}
    if isinstance(value, str):
        return {'kind': 'solid', 'color': rgb(value), 'alpha': 1.0}
    if not isinstance(value, dict):
        raise ValueError('paint must be an object, RGB string or null')
    kind = value.get('kind')
    allowed = {'none': {'kind'}, 'solid': {'kind', 'color', 'alpha', 'source_samples'},
               'linear': {'kind', 'angle', 'stops', 'source_samples'},
               'path': {'kind', 'focus', 'stops', 'source_samples'}}
    if kind not in allowed:
        raise ValueError('paint kind must be none, solid, linear or path')
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


def paint_xml(value, opacity=1):
    """Emit real Office fills; source_samples are provenance, never OOXML attributes."""
    paint = normalize_paint(value)
    opacity = scalar(opacity, 'opacity')
    def color_xml(color, alpha):
        return f'<a:srgbClr val="{color}"><a:alpha val="{round(alpha*opacity*100000)}"/></a:srgbClr>'
    kind = paint['kind']
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
