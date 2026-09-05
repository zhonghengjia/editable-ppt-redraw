"""Inspect real PPTX connector IDs, direction and rectangular endpoint geometry.

No fixes are made. Non-straight, grouped or rotated connectors are explicitly
reported as geometry-unverified rather than interpreted with rectangle formulas.
"""
import argparse
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile

NS = {'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
      'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
      'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
EMU_PER_PT = 12700


def audit(path, require_bound=False, expected=None, tolerance_pt=0.25):
    if not math.isfinite(tolerance_pt) or tolerance_pt < 0:
        raise ValueError('Tolerance must be finite and non-negative')
    result = {'file': str(path), 'connectors': [], 'issues': [], 'geometry_unverified': []}
    seen = set()
    expected = expected or []
    def issue(code, slide, name, detail):
        result['issues'].append({'code': code, 'slide': slide, 'name': name, 'detail': detail})
    with ZipFile(path) as package:
        presentation = ET.fromstring(package.read('ppt/presentation.xml'))
        rels = ET.fromstring(package.read('ppt/_rels/presentation.xml.rels'))
        targets = {r.get('Id'): r.get('Target') for r in rels}
        slides = presentation.find('p:sldIdLst', NS)
        for index, sld in enumerate(slides if slides is not None else [], 1):
            target = targets[sld.get('{'+NS['r']+'}id')]
            member = target.lstrip('/') if target.startswith('/') else 'ppt/'+target
            root = ET.fromstring(package.read(member))
            sp_tree = root.find('p:cSld/p:spTree', NS)
            ids, top_ids, names = {}, set(), {}
            for shape in root.iter():
                nv = shape.find('./p:nvSpPr/p:cNvPr', NS)
                if nv is None:
                    nv = shape.find('./p:nvCxnSpPr/p:cNvPr', NS)
                if nv is None:
                    continue
                sid = nv.get('id'); name = nv.get('name')
                if sid in ids:
                    issue('duplicate_shape_id', index, name, sid)
                ids[sid], names[sid] = shape, name
            for shape in sp_tree:
                nv = shape.find('./p:nvSpPr/p:cNvPr', NS)
                if nv is not None:
                    top_ids.add(nv.get('id'))
            for connection in root.findall('.//p:cxnSp', NS):
                nv = connection.find('p:nvCxnSpPr/p:cNvPr', NS)
                name = nv.get('name', '')
                record = {'slide': index, 'name': name, 'shape_id': nv.get('id')}
                ends = []
                for label, tag in [('source', 'stCxn'), ('target', 'endCxn')]:
                    item = connection.find('p:nvCxnSpPr/p:cNvCxnSpPr/a:'+tag, NS)
                    sid = item.get('id') if item is not None else None
                    record[label] = names.get(sid)
                    record[label+'_id'] = sid
                    record[label+'_port'] = item.get('idx') if item is not None else None
                    if sid is None and require_bound:
                        issue('unbound_endpoint', index, name, label)
                    elif sid is not None and sid not in ids:
                        issue('dangling_endpoint', index, name, f'{label}:{sid}')
                    ends.append((sid, record[label+'_port']))
                for label, tag in [('start_arrow', 'headEnd'), ('end_arrow', 'tailEnd')]:
                    arrow = connection.find('p:spPr/a:ln/a:'+tag, NS)
                    record[label] = arrow.get('type', 'none') if arrow is not None else 'none'
                requirements = [r for r in expected if r.get('slide', 1) == index and r['name'] == name]
                key = (index, name)
                if key in seen:
                    issue('duplicate_connector_name', index, name, 'Names must identify one connection')
                seen.add(key)
                for requirement in requirements:
                    for field in ('source', 'target', 'start_arrow', 'end_arrow'):
                        if field in requirement and record[field] != requirement[field]:
                            issue('semantic_connection_mismatch', index, name,
                                  f'{field}: expected {requirement[field]!r}; got {record[field]!r}')
                xfrm = connection.find('p:spPr/a:xfrm', NS)
                geom = connection.find('p:spPr/a:prstGeom', NS)
                eligible = (connection in list(sp_tree) and xfrm is not None and
                            xfrm.get('rot', '0') == '0' and geom is not None and geom.get('prst') == 'line')
                node_ports = []
                for sid, port in ends:
                    node = ids.get(sid)
                    xf = node.find('p:spPr/a:xfrm', NS) if node is not None else None
                    prst = node.find('p:spPr/a:prstGeom', NS) if node is not None else None
                    if (sid not in top_ids or xf is None or prst is None or
                        prst.get('prst') not in ('rect', 'roundRect') or xf.get('rot', '0') != '0' or
                        xf.get('flipH', '0') not in ('0', 'false') or xf.get('flipV', '0') not in ('0', 'false') or
                        port not in ('0', '1', '2', '3')):
                        eligible = False; continue
                    off, ext = xf.find('a:off', NS), xf.find('a:ext', NS)
                    x, y, w, h = (int(off.get('x')), int(off.get('y')), int(ext.get('cx')), int(ext.get('cy')))
                    node_ports.append(((x+w/2, y), (x, y+h/2), (x+w/2, y+h), (x+w, y+h/2))[int(port)])
                if eligible:
                    off, ext = xfrm.find('a:off', NS), xfrm.find('a:ext', NS)
                    x, y, w, h = int(off.get('x')), int(off.get('y')), int(ext.get('cx')), int(ext.get('cy'))
                    sx, ex = (x+w, x) if xfrm.get('flipH') in ('1', 'true') else (x, x+w)
                    sy, ey = (y+h, y) if xfrm.get('flipV') in ('1', 'true') else (y, y+h)
                    tolerance = tolerance_pt*EMU_PER_PT
                    if w > tolerance and h > tolerance:
                        issue('diagonal_connector', index, name, 'Expected an axis-aligned straight connection')
                    if w == 0 and h == 0:
                        issue('zero_length_connector', index, name, 'Connector has no length')
                    for label, actual, desired in zip(('source', 'target'), ((sx, sy), (ex, ey)), node_ports):
                        if math.dist(actual, desired) > tolerance:
                            issue('endpoint_off_port', index, name, label)
                    record['geometry_verified'] = True
                else:
                    record['geometry_verified'] = False
                    result['geometry_unverified'].append({'slide': index, 'name': name,
                        'reason': 'Only top-level unrotated straight connectors with bound rectangular ports are verified'})
                result['connectors'].append(record)
    for requirement in expected:
        if (requirement.get('slide', 1), requirement['name']) not in seen:
            issue('missing_expected_connector', requirement.get('slide', 1), requirement['name'], 'Not in actual PPTX')
    if require_bound and not result['connectors']:
        issue('no_connectors', 0, '', 'No native p:cxnSp connectors found')
    result['ok'] = not result['issues']
    result['geometry_complete'] = bool(result['connectors']) and not result['geometry_unverified']
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pptx', type=Path)
    parser.add_argument('--expected', type=Path, help='JSON list of slide/name/source/target/arrow requirements')
    parser.add_argument('--require-bound', action='store_true')
    parser.add_argument('--require-geometry', action='store_true')
    parser.add_argument('--fail-on-risk', action='store_true')
    args = parser.parse_args()
    expected = json.loads(args.expected.read_text(encoding='utf-8')) if args.expected else None
    report = audit(args.pptx, args.require_bound, expected)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return int((args.fail_on_risk and not report['ok']) or
               (args.require_geometry and not report['geometry_complete']))


if __name__ == '__main__':
    raise SystemExit(main())
