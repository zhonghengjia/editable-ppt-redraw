"""Executable manifest part trees using the existing native path serializer.

This constructs supplied geometry, not semantic segmentation or hidden anatomy.
No network, image generation, masking or environment installation is performed.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from xml.sax.saxutils import quoteattr

from native_paint import keys, normalize_paint, scalar
from native_vectors import (A_NS, P_NS, MAX_SVG_ELEMENTS, MAX_PATH_CHARS,
                            PathCommand, parse_svg_path, svg_path_to_absolute,
                            normalize_path_commands, path_shape_xml, parse_xml)


def label(value, name):
    if not isinstance(value, str) or not value.strip() or len(value) > 500 or any(ord(c) < 32 for c in value):
        raise ValueError(name + ': nonempty bounded label required')
    return value


def prepare_component(component):
    """Validate the entire tree before any slide mutation; return normalized parts."""
    keys(component, {'id', 'output_name', 'viewbox', 'parts'},
         {'id', 'output_name', 'viewbox', 'parts'}, 'native component')
    label(component['id'], 'component id')
    name = label(component['output_name'], 'output name')
    viewbox = component['viewbox']
    if not isinstance(viewbox, list) or len(viewbox) != 4:
        raise ValueError('viewbox must be [x,y,width,height]')
    viewbox = [scalar(v, 'viewbox coordinate', -1e9, 1e9) for v in viewbox]
    if min(viewbox[2:]) <= 0:
        raise ValueError('viewbox dimensions must be positive')
    seen, names, total = set(), {name}, 0

    def visit(nodes, parent_name, tx, ty, scale, depth):
        nonlocal total
        if depth > 16 or not isinstance(nodes, list) or not nodes:
            raise ValueError('nonempty parts/children required, maximum depth 16')
        prepared = []
        for node in nodes:
            total += 1
            if total >= MAX_SVG_ELEMENTS:
                raise ValueError('component exceeds native element budget')
            common = {'id', 'role', 'observation', 'translate', 'scale'}
            group = isinstance(node, dict) and 'children' in node
            allowed = common | ({'children'} if group else {'d', 'fill', 'stroke', 'stroke_width'})
            keys(node, allowed, {'id', 'role', 'observation'} | ({'children'} if group else {'d', 'fill'}), 'part')
            part_id = label(node['id'], 'part id')
            if '/' in part_id or part_id in seen:
                raise ValueError('part IDs must be unique and may not contain /')
            seen.add(part_id)
            label(node['role'], 'part role'); label(node['observation'], 'source observation')
            output_name = parent_name + '/' + part_id
            names.add(output_name)
            offset = node.get('translate', [0, 0])
            if not isinstance(offset, list) or len(offset) != 2:
                raise ValueError('translate requires [x,y]')
            dx, dy = [scalar(v, 'translation', -1e9, 1e9) for v in offset]
            local_scale = scalar(node.get('scale', 1), 'uniform scale', 1e-6, 1e6)
            nx, ny, ns = tx + dx*scale, ty + dy*scale, scale*local_scale
            if not all(math.isfinite(v) and abs(v) <= 1e9 for v in (nx, ny, ns)) or ns <= 0:
                raise ValueError('composed transform exceeds profile')
            entry = {'id': part_id, 'name': output_name, 'role': node['role']}
            if group:
                entry['children'] = visit(node['children'], output_name, nx, ny, ns, depth+1)
            else:
                path = node['d']
                if not isinstance(path, str) or not path.strip() or len(path) > MAX_PATH_CHARS:
                    raise ValueError('path empty or exceeds native path budget')
                commands = normalize_path_commands(svg_path_to_absolute(parse_svg_path(path)))
                transformed = []
                for cmd in commands:
                    args = [v*ns + (nx if i % 2 == 0 else ny) for i, v in enumerate(cmd.args)]
                    if any(not math.isfinite(v) or abs(v) > 1e9 for v in args):
                        raise ValueError('transformed path exceeds coordinate budget')
                    transformed.append(PathCommand(cmd.cmd, args))
                fill = normalize_paint(node['fill'])
                stroke = normalize_paint(node.get('stroke'))
                if stroke['kind'] not in ('none', 'solid'):
                    raise ValueError('gradient strokes are outside this profile')
                sw = scalar(node.get('stroke_width', 0), 'stroke width', 0, 1e6) * ns
                entry['spec'] = dict(commands=transformed, fill=fill, stroke=stroke,
                                     stroke_width=sw, cap='round', join='round', alpha=[1, 1])
            prepared.append(entry)
        return prepared

    return visit(component['parts'], name, 0, 0, 1, 1), viewbox, names


def validate_contract(manifest):
    if 'native_components' not in manifest:
        return []
    try:
        components = manifest['native_components']
        if not isinstance(components, list) or not 1 <= len(components) <= 100:
            raise ValueError('native_components needs 1..100 components')
        inventory = {i['id']: i for i in manifest.get('source_inventory', [])}
        seen, names = set(), set()
        for component in components:
            _, _, component_names = prepare_component(component)
            cid = component['id']
            if cid in seen or cid not in inventory:
                raise ValueError('component id must uniquely reference source_inventory')
            if inventory[cid].get('representation') != 'native_composite':
                raise ValueError('component tree requires native_composite representation')
            if inventory[cid].get('output_name', component['output_name']) != component['output_name']:
                raise ValueError('inventory and component output names disagree')
            if names & component_names:
                raise ValueError('component output names collide')
            names.update(component_names); seen.add(cid)
        return []
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        return ['native_components: ' + str(exc)]


def add_native_component(slide, component, x, y, width, height):
    """Build editable nested groups with local Paint; coordinates in inches."""
    for v in (x, y, width, height):
        scalar(v, 'placement', -1e6, 1e6)
    if min(width, height) <= 0:
        raise ValueError('placement dimensions must be positive')
    parts, (vx, vy, vw, vh), names = prepare_component(component)
    existing = {el.get('name') for el in slide._element.iter(f'{{{P_NS}}}cNvPr')}
    if names & existing:
        raise ValueError('component output names already exist on slide')
    scale = min(width*96/vw, height*96/vh)
    ox, oy = x*96+(width*96-vw*scale)/2-vx*scale, y*96+(height*96-vh*scale)/2-vy*scale
    next_id = max(int(el.get('id')) for el in slide._element.iter(f'{{{P_NS}}}cNvPr')) + 1
    element_map = []

    def allocate():
        nonlocal next_id
        result = next_id; next_id += 1
        return result

    def group_xml(nodes, name, parent_id=None):
        group_id = allocate()
        children, bounds = [], []
        for node in nodes:
            if 'children' in node:
                elem, box, _ = group_xml(node['children'], node['name'], group_id)
            else:
                sid = allocate()
                elem, box = path_shape_xml(node['spec'], sid, node['name'], ox, oy, scale)
                element_map.append(dict(source_id=node['id'], output_name=node['name'], shape_id=sid,
                                        parent_group_id=group_id, role=node['role'], bounds_inches=box))
            children.append(elem); bounds.append(box)
        left, top = min(b[0] for b in bounds), min(b[1] for b in bounds)
        right, bottom = max(b[0]+b[2] for b in bounds), max(b[1]+b[3] for b in bounds)
        lx, ty, w, h = [round(v*914400) for v in (left, top, right-left, bottom-top)]
        elem = parse_xml(f'<p:grpSp xmlns:p="{P_NS}" xmlns:a="{A_NS}"><p:nvGrpSpPr>'
                         f'<p:cNvPr id="{group_id}" name={quoteattr(name)}/><p:cNvGrpSpPr/><p:nvPr/>'
                         f'</p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="{lx}" y="{ty}"/>'
                         f'<a:ext cx="{w}" cy="{h}"/><a:chOff x="{lx}" y="{ty}"/>'
                         f'<a:chExt cx="{w}" cy="{h}"/></a:xfrm></p:grpSpPr></p:grpSp>')
        for child in children:
            elem.append(child)
        return elem, [left, top, right-left, bottom-top], group_id

    root, _, root_id = group_xml(parts, component['output_name'])
    # All validation and serialization finish before this one package mutation.
    slide.shapes._spTree.insert_element_before(root, 'p:extLst')
    return {'group': next(s for s in slide.shapes if s.shape_id == root_id),
            'group_id': root_id, 'element_map': element_map, 'raster_count': 0,
            'slide_part': str(slide.part.partname),
            'component_sha256': hashlib.sha256(json.dumps(component, sort_keys=True, allow_nan=False).encode()).hexdigest()}


def add_manifest_component(slide, manifest, component_id, x, y, width, height, *, base_dir):
    """Consume the same manifest; verify sampled paints against immutable source."""
    from component_fidelity import validate_contract as regional_contract, digest, read_image
    from appearance_fidelity import validate_contract as appearance_contract
    errors = validate_contract(manifest) + regional_contract(manifest) + appearance_contract(manifest)
    if errors:
        raise ValueError('; '.join(errors))
    for field in ('regional_fidelity','appearance_fidelity'):
        contract=manifest.get(field)
        if contract is not None:
            source=Path(base_dir)/manifest['source']['path']
            if digest(source)!=contract['source_sha256'] or list(read_image(source).size)!=contract['source_size']:
                raise ValueError(field+': source hash/size mismatch before construction')
    matches = [c for c in manifest.get('native_components', []) if c['id'] == component_id]
    if len(matches) != 1:
        raise ValueError('unknown native component')
    component = matches[0]
    def verify(nodes):
        for node in nodes:
            if 'children' in node:
                verify(node['children'])
            else:
                for field in ('fill', 'stroke'):
                    paint = node.get(field)
                    if isinstance(paint, dict) and 'source_samples' in paint:
                        from appearance_fidelity import verify_sampled_paint
                        verify_sampled_paint(Path(base_dir) / manifest['source']['path'], paint)
    verify(component['parts'])
    return add_native_component(slide, component, x, y, width, height)
