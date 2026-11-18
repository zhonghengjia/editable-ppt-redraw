"""Validate one saved Office snapshot and adapt measured, reopened PPTX evidence.

The snapshot's hashes bind files; they do not authenticate who produced it.
Text rectangles are not glyph masks. Unknown geometry is never guessed from a bbox.
"""
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import posixpath
import re
import unicodedata
import xml.etree.ElementTree as ET
import zipfile

NS = {'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
      'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
      'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}


def _finite(value):
    return not isinstance(value, bool) and isinstance(value, (float, int)) and math.isfinite(value)


def _box(value, positive=True):
    return (isinstance(value, list) and len(value) == 4 and all(_finite(v) for v in value)
            and (min(value[2:]) > 0 if positive else min(value[2:]) >= 0))


def _slide_parts(package):
    root = ET.fromstring(package.read('ppt/presentation.xml'))
    rels = ET.fromstring(package.read('ppt/_rels/presentation.xml.rels'))
    targets = {}
    for relation in rels:
        if relation.get('TargetMode') == 'External':
            continue
        target = relation.get('Target', '')
        targets[relation.get('Id')] = (posixpath.normpath(target.lstrip('/')) if target.startswith('/')
                                     else posixpath.normpath(posixpath.join('ppt', target)))
    result = {}
    for index, item in enumerate(root.findall('p:sldIdLst/p:sldId', NS), 1):
        part = targets.get(item.get('{'+NS['r']+'}id'))
        if not part or not part.startswith('ppt/slides/') or part not in package.namelist():
            raise ValueError('Office slide order cannot be resolved from final PPTX')
        result[index] = part
    if not result or len(set(result.values())) != len(result):
        raise ValueError('Office slide parts must be nonempty and unique')
    return root, result


def read(artifact, evidence_path, artifact_sha256=None):
    """Shared envelope authority. Consumers validate only their selected measurements."""
    result = {'status': 'NOT_PROVIDED', 'unverified': [], 'renders': {}, 'slides': [],
              'slide_parts': {}, 'artifact': str(Path(artifact).resolve())}
    if evidence_path is None:
        return result
    try:
        path = Path(evidence_path)
        data = json.loads(path.read_text(encoding='utf-8-sig'))
        digest = artifact_sha256 or hashlib.sha256(Path(artifact).read_bytes()).hexdigest()
        if data.get('schema_version') != 1 or data.get('artifact_sha256') != digest:
            raise ValueError('Office evidence schema/artifact hash does not match')
        if data.get('status') != 'PASS' or data.get('source_unchanged') is not True:
            raise ValueError('Office evidence did not complete with unchanged source')
        renderer = data.get('renderer', '')
        if not isinstance(renderer, str) or not renderer.startswith('Microsoft PowerPoint '):
            raise ValueError('Office measurements require Microsoft PowerPoint evidence')
        dims = [data.get('slide_width_pt'), data.get('slide_height_pt')]
        if any(not _finite(v) or v <= 0 for v in dims):
            raise ValueError('Office slide dimensions must be finite and positive')
        with zipfile.ZipFile(artifact) as package:
            root, parts = _slide_parts(package)
            size = root.find('p:sldSz', NS)
            def matches(emu, actual):
                if abs(emu/12700-actual) <= 1e-6:
                    return True
                # Match Office 16's exact 1/8-point normalization, not a loose tolerance.
                quantized = ((8*emu+6350)//12700)/8
                return renderer.startswith('Microsoft PowerPoint 16.') and abs(quantized-actual) <= 1e-6
            if size is None or any(not matches(int(size.get(k)), v) for k, v in zip(('cx', 'cy'), dims)):
                raise ValueError('Office slide dimensions differ from artifact')
        slides = data.get('slides')
        if not isinstance(slides, list) or not slides:
            raise ValueError('Office evidence must contain slides')
        for slide in slides:
            index = slide.get('index')
            if isinstance(index, bool) or not isinstance(index, int) or index < 1 or index in result['renders']:
                raise ValueError('Office slide indexes must be unique positive integers')
            render = (path.parent / slide['render_path']).resolve()
            if not render.is_relative_to(path.parent.resolve()):
                raise ValueError('Office render must stay within evidence directory')
            if hashlib.sha256(render.read_bytes()).hexdigest() != slide.get('render_sha256'):
                raise ValueError('Office render hash does not match')
            from PIL import Image
            with Image.open(render) as im:
                if im.format != 'PNG' or abs(im.width/im.height-dims[0]/dims[1]) > .005:
                    raise ValueError('Office render format/aspect does not match slide')
            result['renders'][index] = str(render)
        if set(result['renders']) != set(parts):
            raise ValueError('Office evidence must cover final PPTX slide order exactly')
        result.update(status='BOUND', slides=slides, slide_parts=parts, dimensions_pt=dims,
                      artifact_sha256=digest, renderer=renderer, evidence_path=str(path.resolve()))
    except (OSError, ValueError, KeyError, TypeError, AttributeError, ET.ParseError, zipfile.BadZipFile) as exc:
        result.update(status='NOT_VERIFIED', renders={}, slides=[], slide_parts={})
        result['unverified'].append(str(exc))
    return result


def text_bounds(evidence, canvas, selected_names=None):
    """Resolve selected text rectangles in canvas pixels without inspecting glyphs."""
    result = {'status': evidence['status'], 'unverified': list(evidence['unverified']),
              'bounds': {}, 'renders': evidence['renders'], 'unselected_limitations': []}
    if evidence['status'] != 'BOUND':
        return result
    try:
        sx, sy = _scale(evidence, canvas)
        for slide in evidence['slides']:
            # The collector prefixes shape-scoped limitations with its exact name.
            # Preserve unselected table limits without vetoing unrelated label checks.
            for value in slide.get('unverified', []):
                message = str(value)
                name, separator, _ = message.partition(':')
                key = ('unverified' if selected_names is None or not separator or name in selected_names
                       else 'unselected_limitations')
                result[key].append(message)
            for item in slide.get('text_bounds', []):
                if selected_names is not None and item.get('name') not in selected_names:
                    continue
                key = (slide['index'], item.get('name'))
                if not isinstance(key[1], str) or not key[1] or key in result['bounds']:
                    raise ValueError('Office text measurements require unique names within each slide')
                if not _box(item.get('box_pt')):
                    raise ValueError('Office text bounds must be finite with positive dimensions')
                # Track names before skipping unsupported measurements, so duplicates cannot hide.
                result['bounds'][key] = None
                if not _unrotated(item):
                    result['unverified'].append(f'{key[1]}: rotated Office text bounds not supported')
                    continue
                if not isinstance(item.get('text'), str) or not item['text'].strip():
                    raise ValueError('Office text evidence is empty')
                result['bounds'][key] = {'box': _scaled_box(item['box_pt'], sx, sy), 'text': item['text']}
        result['bounds'] = {key: value for key, value in result['bounds'].items() if value is not None}
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        result.update(status='NOT_VERIFIED', bounds={}, renders={})
        result['unverified'].append(str(exc))
    return result


def _scale(evidence, canvas):
    dims = evidence['dimensions_pt']
    if canvas is None:
        return 1., 1.
    if not isinstance(canvas, dict) or any(not _finite(canvas.get(k)) or canvas[k] <= 0 for k in ('width', 'height')):
        raise ValueError('Office canvas dimensions must be finite and positive')
    return canvas['width']/dims[0], canvas['height']/dims[1]


def _scaled_box(box, sx, sy):
    return [box[0]*sx, box[1]*sy, box[2]*sx, box[3]*sy]


def _unrotated(item):
    angle = item.get('rotation')
    return (item.get('ancestor_rotated') is not True and _finite(angle) and abs(angle) <= .001
            and item.get('rotation_composition_verified') is not False)


def _normalized_text(text):
    return unicodedata.normalize('NFC', text.replace('\r\n', '\n').replace('\r', '\n').replace('\v', '\n'))


def text_layout(evidence, inventory):
    """Compare rendered lines and frame containment for resolved native text."""
    result = {'valid': True, 'checked': [], 'issues': [], 'unverified': []}
    if evidence['status'] != 'BOUND':
        result['unverified'] = list(evidence['unverified']) or ['fresh Office snapshot is required']
        return result
    indexed = {}
    for slide in evidence['slides']:
        for key in ('shapes', 'text_bounds'):
            for record in slide.get(key, []):
                indexed.setdefault((slide['index'], key, record.get('name')), []).append(record)
    for item in inventory:
        identity = item['id']
        slide, name = item.get('output_slide', 1), item.get('output_name', identity)
        bounds = indexed.get((slide, 'text_bounds', name), [])
        frames = indexed.get((slide, 'shapes', name), [])
        bound_id = item.get('output_id')
        if (not bound_id or len(bounds) != 1 or len(frames) != 1
                or any(str(rows[0].get('shape_id')) != str(bound_id) for rows in (bounds, frames))):
            result['unverified'].append(f'{identity}: resolved output ID/name needs one matching Office frame and text range')
            continue
        bounds, frame = bounds[0], frames[0]
        if any(r.get('parent_groups') or not _unrotated(r) or not _box(r.get('box_pt'))
               for r in (bounds, frame)):
            result['unverified'].append(f'{identity}: only unrotated top-level text with finite frame and bounds is supported')
            continue
        lines = bounds.get('line_count')
        expected = _normalized_text(item['text'])
        if not isinstance(bounds.get('text'), str) or _normalized_text(bounds['text']) != expected:
            result['unverified'].append(f'{identity}: Office text does not match declared text and explicit breaks')
            continue
        if type(lines) is not int or lines < 1:
            result['unverified'].append(f'{identity}: actual PowerPoint line count is unavailable')
            continue
        x, y, w, h = bounds['box_pt']
        left, top, width, height = frame['box_pt']
        overflow = round(max(left-x, top-y, x+w-left-width, y+h-top-height, 0), 3)
        row = {'id': identity, 'slide': slide, 'shape_id': bound_id,
               'expected_lines': expected.count('\n')+1, 'rendered_lines': lines,
               'text_bounds_pt': bounds['box_pt'], 'frame_pt': frame['box_pt'],
               'max_overflow_pt': overflow}
        result['checked'].append(row)
        if lines != row['expected_lines']:
            result['issues'].append({'id': identity, 'kind': 'rendered_line_count_mismatch',
                                     'expected': row['expected_lines'], 'actual': lines})
        if overflow > 1.0:
            result['issues'].append({'id': identity, 'kind': 'text_outside_frame', 'max_overflow_pt': overflow})
    result['valid'] = not result['issues']
    return result


def _package_shapes(root):
    shapes = {}
    for shape in root.iter():
        tag = shape.tag.rsplit('}', 1)[-1]
        nv = {'sp': 'nvSpPr', 'cxnSp': 'nvCxnSpPr', 'grpSp': 'nvGrpSpPr',
              'pic': 'nvPicPr', 'graphicFrame': 'nvGraphicFramePr'}.get(tag)
        if nv is None:
            continue
        props = shape.find('p:'+nv+'/p:cNvPr', NS)
        if props is None:
            continue
        sid = props.get('id')
        if sid in shapes:
            raise ValueError('Final PPTX shape IDs must be unique within a slide')
        shapes[sid] = (shape, props.get('name'), tag)
    return shapes


def layouts(evidence, canvas=None):
    """Adapt actual Office shape extents plus final-package types/native bindings.

    No builder geometry, semantic ports or font values are synthesized. An extent
    of a curved connector/custom shape never becomes an explicit straight route.
    """
    result = {'status': evidence['status'], 'unverified': list(evidence['unverified']), 'documents': []}
    if evidence['status'] != 'BOUND':
        return result
    try:
        sx, sy = _scale(evidence, canvas)
        with zipfile.ZipFile(evidence['artifact']) as package:
            for slide in evidence['slides']:
                index = slide['index']
                actual = _package_shapes(ET.fromstring(package.read(evidence['slide_parts'][index])))
                records = slide.get('shapes')
                if not isinstance(records, list):
                    raise ValueError('Office snapshot has no reopened shape records')
                by_id = {}
                for item in records:
                    sid = str(item.get('shape_id'))
                    if (not isinstance(item.get('name'), str) or not item['name'] or sid in by_id
                            or sid not in actual or item['name'] != actual[sid][1]):
                        raise ValueError('Office shape IDs/names do not match final PPTX uniquely')
                    if not _box(item.get('box_pt'), positive=False):
                        raise ValueError('Office shape extents must be finite and nonnegative')
                    by_id[sid] = item
                if set(by_id) != set(actual):
                    raise ValueError('Office snapshot omits final PPTX shapes')
                bindings = {}
                for binding in slide.get('connectors', []):
                    sid = str(binding.get('shape_id'))
                    if sid in bindings or sid not in actual or actual[sid][2] != 'cxnSp':
                        raise ValueError('Office connector IDs must match final native connectors uniquely')
                    bindings[sid] = binding
                elements, unresolved = [], [str(v) for v in slide.get('unverified', [])]
                names = Counter(item['name'] for item in records)
                for sid, item in by_id.items():
                    shape, name, tag = actual[sid]
                    element = {'name': name, 'shape_id': int(sid), 'slide': index,
                               'bbox': _scaled_box(item['box_pt'], sx, sy), 'rotation': item.get('rotation'),
                               'parent_groups': item.get('parent_groups', []),
                               'readback_source': 'Microsoft PowerPoint shape extent + final PPTX type'}
                    reasons = []
                    if names[name] > 1:
                        reasons.append('duplicate shape name within slide')
                    if not _unrotated(item):
                        reasons.append('rotated shape/group geometry is unsupported')
                    preset = shape.find('p:spPr/a:prstGeom', NS)
                    if tag == 'sp':
                        props = shape.find('p:nvSpPr/p:cNvSpPr', NS)
                        if props is not None and props.get('txBox') in ('1', 'true'):
                            geometry = 'text'
                        elif preset is not None:
                            geometry = preset.get('prst') or 'unknown'
                        elif shape.find('p:spPr/a:custGeom', NS) is not None:
                            geometry = 'custom'
                            reasons.append('custom path has only Office extent in this adapter')
                        else:
                            geometry = 'unknown'
                            reasons.append('shape geometry cannot be resolved from final PPTX')
                    elif tag == 'cxnSp':
                        geometry = 'line'
                        element['preset_geometry'] = preset.get('prst') if preset is not None else None
                        element['route_geometry_supported'] = False
                        binding = bindings.get(sid)
                        if binding is None:
                            reasons.append('Office native connector binding record unavailable')
                        else:
                            _bind_connector(element, shape, binding, actual)
                        # Deliberately omit endpoints: bbox and bindings alone do not prove a route.
                    elif tag == 'graphicFrame':
                        geometry = 'table' if shape.find('.//a:tbl', NS) is not None else 'unknown'
                        reasons.append('table-cell/graphic-frame geometry is unsupported')
                    else:
                        geometry = {'pic': 'picture', 'grpSp': 'group'}.get(tag, 'unknown')
                    element['geometry'] = geometry
                    body = shape.find('p:txBody', NS)
                    text = '\n'.join(''.join(t.text or '' for t in p.findall('.//a:t', NS))
                                     for p in body.findall('a:p', NS)) if body is not None else ''
                    if ' '.join(str(item.get('text', '')).split()) != ' '.join(text.split()):
                        reasons.append('Office shape text differs from final PPTX')
                    element['text'] = text
                    element['readback_status'] = 'NOT_VERIFIED' if reasons else 'PASS'
                    element['unverified'] = reasons
                    unresolved.extend(f'slide {index} / {name}: {reason}' for reason in reasons)
                    elements.append(element)
                document = {'artifact_sha256': evidence['artifact_sha256'], 'slide': index,
                            'slide_part': evidence['slide_parts'][index], 'elements': elements,
                            'coordinate_unit': 'canvas_px' if canvas else 'slide_pt',
                            'readback_source': 'validated_office_evidence', 'unverified': unresolved}
                result['documents'].append(document)
                result['unverified'].extend(unresolved)
        result['status'] = 'NOT_VERIFIED' if result['unverified'] else 'BOUND'
    except (OSError, ValueError, KeyError, TypeError, AttributeError, ET.ParseError, zipfile.BadZipFile) as exc:
        result.update(status='NOT_VERIFIED', documents=[])
        result['unverified'].append(str(exc))
    return result


def _bind_connector(element, shape, binding, actual):
    if binding.get('name') != element['name']:
        raise ValueError('Office connector name does not match final PPTX')
    for label, tag, prefix in (('source', 'stCxn', 'begin'), ('target', 'endCxn', 'end')):
        native = shape.find('p:nvCxnSpPr/p:cNvCxnSpPr/a:'+tag, NS)
        sid = native.get('id') if native is not None else None
        connected = binding.get(prefix+'_connected')
        if not isinstance(connected, bool) or connected != (sid is not None):
            raise ValueError('Office/native connector binding state differs')
        if sid is None:
            continue
        if (sid not in actual or str(binding.get(prefix+'_shape_id')) != sid
                or binding.get(prefix+'_name') != actual[sid][1]):
            raise ValueError('Office/native connector endpoint differs')
        port = native.get('idx')
        site = binding.get(prefix+'_site')
        if port is None or isinstance(site, bool) or not isinstance(site, int) or site != int(port)+1:
            raise ValueError('Office/native connector site differs')
        element[label+'_name'] = actual[sid][1]
        element[label+'_shape_id'] = int(sid)
        element[label+'_site'] = site


def grammar_scope(adapted, grammar):
    """Qualify only contract-selected objects while retaining the complete readback.

    A decorative custom path must not veto verified rectangular nodes/bindings.
    Missing objects are still audited by diagram grammar, never filled in here.
    """
    result = {'status': 'NOT_VERIFIED', 'documents': adapted['documents'],
              'unverified': [], 'unselected_limitations': []}
    if not adapted['documents']:
        result['unverified'] = list(adapted['unverified'])
        return result
    if not isinstance(grammar, dict):
        result['unverified'].append('diagram grammar contract is not an object')
        return result
    names, patterns = set(), []
    try:
        for role in grammar.get('node_roles', {}).values():
            for name in role.get('output_names', []):
                if isinstance(name, str):
                    names.add(name)
        for role in grammar.get('edge_roles', {}).values():
            pattern = role.get('output_name_regex')
            if isinstance(pattern, str) and pattern:
                patterns.append(re.compile(pattern))
    except (TypeError, AttributeError, re.error) as exc:
        result['unverified'].append(f'diagram grammar selection is invalid: {exc}')
        return result
    selected_reasons = set()
    for document in adapted['documents']:
        for element in document['elements']:
            name = element['name']
            if name in names or any(pattern.search(name) for pattern in patterns):
                for reason in element.get('unverified', []):
                    selected_reasons.add(f"slide {document['slide']} / {name}: {reason}")
    result['unverified'] = sorted(selected_reasons)
    result['unselected_limitations'] = [reason for reason in adapted['unverified'] if reason not in selected_reasons]
    result['status'] = 'NOT_VERIFIED' if selected_reasons else 'BOUND'
    return result
