"""Source-grounded host/detail geometry checks, using actual native PPTX paths.

Single closed-path profile only. No semantic segmentation or automatic 3D inference.
"""
from __future__ import annotations
import hashlib
import importlib.util
import math
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path


def finite(v):
    return isinstance(v, (float, int)) and not isinstance(v, bool) and math.isfinite(v)


def validate_contract(manifest):
    errors = []
    inventory = manifest.get('source_inventory', [])
    if not isinstance(inventory, list):
        return ['source_inventory must be a list for surface validation']
    required = {i['id'] for i in inventory if isinstance(i, dict) and i.get('surface_detail') is True and 'id' in i}
    contract = manifest.get('surface_relations')
    if contract is None:
        return ['surface_detail inventory requires surface_relations'] if required else []
    if not isinstance(contract, dict):
        return ['surface_relations must be an object']
    if not re.fullmatch('[0-9a-f]{64}', str(contract.get('source_sha256', ''))):
        errors.append('surface_relations requires source_sha256')
    relations = contract.get('relations')
    if not isinstance(relations, list) or not 1 <= len(relations) <= 100:
        return errors + ['surface_relations.relations must contain 1..100 items']
    known = {i.get('id') for i in inventory if isinstance(i, dict)}
    ids, details = set(), set()
    for r in relations:
        if not isinstance(r, dict):
            errors.append('surface relation must be an object'); continue
        rid = r.get('id')
        if not isinstance(rid, str) or not rid.strip() or rid in ids:
            errors.append('surface relation id missing or duplicated')
        else:
            ids.add(rid)
        sid = r.get('source_inventory_id')
        if not isinstance(sid, str) or sid not in known or sid in details:
            errors.append(f'{rid}: unknown or reused source detail')
        else:
            details.add(sid)
        for key in ('host_name', 'detail_name', 'source_observation'):
            if not isinstance(r.get(key), str) or not r[key].strip():
                errors.append(f'{rid}: missing {key}')
        if r.get('host_name') == r.get('detail_name'):
            errors.append(f'{rid}: host and detail must differ')
        for key in ('max_landmark_error_px', 'max_escape_px'):
            if not finite(r.get(key)) or not 0 <= r[key] <= 20:
                errors.append(f'{rid}: {key} must be finite source pixels in 0..20')
        for key in ('host_landmarks', 'detail_landmarks'):
            points = r.get(key)
            if not isinstance(points, list) or not 3 <= len(points) <= 100:
                errors.append(f'{rid}: {key} needs 3..100 source boundary landmarks'); continue
            for p in points:
                if not isinstance(p, list) or len(p) != 2 or not all(finite(v) for v in p):
                    errors.append(f'{rid}: invalid landmark'); break
                source = manifest.get('source', {})
                if not all(finite(source.get(k)) and source[k] > 0 for k in ('width', 'height')) or not (0 <= p[0] <= source['width'] and 0 <= p[1] <= source['height']):
                    errors.append(f'{rid}: landmark outside source'); break
        fronts = r.get('occluders')
        if not isinstance(fronts, list) or any(not isinstance(n, str) or not n.strip() for n in fronts):
            errors.append(f'{rid}: occluders must be an explicit name list')
        elif len(set(fronts)) != len(fronts) or r.get('host_name') in fronts or r.get('detail_name') in fronts:
            errors.append(f'{rid}: invalid occluder identity')
    if required - details:
        errors.append('surface_detail inventory has uncovered instances: ' + ', '.join(sorted(required-details)))
    return errors


def distance(p, a, b):
    dx, dy = b[0]-a[0], b[1]-a[1]
    t = max(0., min(1., ((p[0]-a[0])*dx+(p[1]-a[1])*dy)/(dx*dx+dy*dy))) if dx or dy else 0.
    return math.hypot(p[0]-a[0]-t*dx, p[1]-a[1]-t*dy)


def boundary_distance(p, poly):
    return min(distance(p, a, b) for a, b in zip(poly, poly[1:]+poly[:1]))


def inside(p, poly):
    if boundary_distance(p, poly) < 1e-7:
        return True
    crossings = 0
    for a, b in zip(poly, poly[1:]+poly[:1]):
        if (a[1] > p[1]) != (b[1] > p[1]) and p[0] < (b[0]-a[0])*(p[1]-a[1])/(b[1]-a[1])+a[0]:
            crossings += 1
    return bool(crossings % 2)


def samples(poly):
    # Include segment interiors so a chord across a concave host cannot pass on vertices alone.
    for a, b in zip(poly, poly[1:]+poly[:1]):
        steps = max(1, math.ceil(math.dist(a, b)*2))
        if steps > 100000:
            raise ValueError('geometry exceeds bounded sampling profile')
        for k in range(steps+1):
            yield (a[0]+(b[0]-a[0])*k/steps, a[1]+(b[1]-a[1])*k/steps)


def audit(artifact, manifest, manifest_path):
    errors = validate_contract(manifest)
    report = {'valid': not errors, 'errors': errors, 'unverified': [], 'relations': [],
              'claim_boundary': 'Native sampled boundary, source landmarks and paint order only; rendered surface attachment and occlusion appearance require separate review.'}
    if errors:
        return report
    if Path(artifact).suffix.lower() != '.pptx':
        report['unverified'].append('native surface auditor supports PPTX only'); return report
    source = Path(manifest_path).parent / manifest['source']['path']
    if hashlib.sha256(source.read_bytes()).hexdigest() != manifest['surface_relations']['source_sha256']:
        report['valid'] = False; errors.append('surface source hash mismatch'); return report
    spec = importlib.util.spec_from_file_location('surface_native_reader', Path(__file__).with_name('audit-curve-fidelity.py'))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    records, _, _ = module.collect_pptx_profiles(Path(artifact))
    with zipfile.ZipFile(artifact) as z:
        size = ET.fromstring(z.read('ppt/presentation.xml')).find('p:sldSz', module.NS)
        sx, sy = manifest['source']['width']/int(size.get('cx')), manifest['source']['height']/int(size.get('cy'))
    def select(name):
        matches = [(k, p) for k, p in enumerate(records) if p['name'] == name]
        if len(matches) != 1:
            raise ValueError(f'{name}: expected one unique native single-path object, found {len(matches)}')
        k, p = matches[0]
        if p['status'] != 'supported' or not p.get('closed') or not p.get('absolute_coordinates_available'):
            raise NotImplementedError(f'{name}: closed absolute native path unavailable')
        return k, p, [(x*sx,y*sy) for x,y in p['points']]
    for r in manifest['surface_relations']['relations']:
        try:
            hk, host, hp = select(r['host_name']); dk, detail, dp = select(r['detail_name'])
            if host['slide_part'] != detail['slide_part']:
                raise ValueError('host/detail are on different slides')
            if hk >= dk:
                raise ValueError('detail must paint after host')
            for name in r['occluders']:
                fk, front, _ = select(name)
                if front['slide_part'] != host['slide_part'] or fk <= dk:
                    raise ValueError(f'{name}: incorrect foreground paint order')
            landmark_error = max([boundary_distance(p, hp) for p in r['host_landmarks']] + [boundary_distance(p, dp) for p in r['detail_landmarks']])
            escape = max((0. if inside(p,hp) else boundary_distance(p,hp)) for p in samples(dp))
            passed = landmark_error <= r['max_landmark_error_px'] and escape <= r['max_escape_px']
            report['relations'].append({'id':r['id'], 'max_landmark_error_px':landmark_error, 'max_escape_px':escape, 'passed':passed})
            if not passed:
                errors.append(f"{r['id']}: source alignment or host containment failed")
        except NotImplementedError as exc:
            report['unverified'].append(f"{r['id']}: {exc}")
        except ValueError as exc:
            errors.append(f"{r['id']}: {exc}")
    report['valid'] = not errors
    return report
