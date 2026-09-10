"""Source-bound appearance construction, prompt binding and scoped render audit.

No model call, image editing, inferred depth, segmentation or visual certification.
The source is the numeric baseline; reviewer records remain human assertions.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import math
import re
import zipfile
from pathlib import Path


DIMENSIONS = {'semantic_color', 'tone', 'contour', 'occlusion', 'transparency', 'flat'}


def load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def contract_hash(contract):
    return hashlib.sha256(json.dumps(contract, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()


def text(value):
    return isinstance(value, str) and bool(value.strip())


def check_keys(obj, allowed, label):
    if not isinstance(obj, dict) or set(obj) - set(allowed.split()):
        raise ValueError(label + ': object required; unknown fields are not accepted')


def bbox(value, bounds):
    if not isinstance(value, list) or len(value) != 4 or any(type(v) is not int for v in value):
        raise ValueError('source/sample bbox must be four integers')
    x, y, w, h = value
    bx, by, bw, bh = bounds
    if w <= 0 or h <= 0 or w*h > 1_000_000 or max(w, h) > 4096 or x < bx or y < by or x+w > bx+bw or y+h > by+bh:
        raise ValueError('source/sample bbox outside declared bounds or size budget')


def sample_paint(source, recipe):
    """Read declared opaque sRGB patches into executable native Paint colors.

    Geometry, gradient type/direction and sample positions are source decisions,
    not inferred by this function. No pixel file is changed or emitted.
    """
    import numpy as np
    from PIL import Image
    from native_paint import normalize_paint
    check_keys(recipe, 'source_sha256 kind patches positions angle focus', 'paint sampling recipe')
    raw = Path(source).read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != recipe.get('source_sha256'):
        raise ValueError('paint sampling source hash mismatch')
    kind = recipe.get('kind')
    if kind not in ('solid', 'linear', 'path'):
        raise ValueError('source sampling supports solid, linear or path paint')
    patches = recipe.get('patches')
    if not isinstance(patches, list) or not 1 <= len(patches) <= 32:
        raise ValueError('paint sampling requires 1..32 source patches')
    with Image.open(source) as image:
        if image.width * image.height > 50_000_000:
            raise ValueError('source exceeds paint sampling pixel budget')
        if image.info.get('icc_profile'):
            raise ValueError('ICC conversion must be independently qualified before sampling')
        size, colors = list(image.size), []
        for patch in patches:
            bbox(patch, [0, 0, *size])
            x, y, w, h = patch
            crop = image.crop((x, y, x+w, y+h)).convert('RGBA')
            pixels = np.asarray(crop)
            if int(pixels[:, :, 3].min()) != 255:
                raise ValueError('sampling transparent pixels cannot estimate foreground color')
            color = np.rint(np.median(pixels[:, :, :3].reshape(-1, 3), axis=0)).astype(int)
            colors.append(''.join(f'{channel:02X}' for channel in color))
    result = {'kind': kind}
    if kind == 'solid':
        if len(patches) != 1 or any(k in recipe for k in ('positions', 'angle', 'focus')):
            raise ValueError('solid sampling requires one patch and no gradient fields')
        result['color'] = colors[0]
    else:
        positions = recipe.get('positions')
        if not isinstance(positions, list) or len(positions) != len(colors):
            raise ValueError('sample positions must match patches')
        result['stops'] = [{'position': p, 'color': c} for p, c in zip(positions, colors)]
        if kind == 'linear':
            if 'focus' in recipe:
                raise ValueError('linear paint does not have path focus')
            result['angle'] = recipe.get('angle')
        else:
            if 'angle' in recipe:
                raise ValueError('path paint does not have linear angle')
            result['focus'] = recipe.get('focus')
    result['source_samples'] = {'sha256': digest, 'size': size, 'patches': copy.deepcopy(patches)}
    return normalize_paint(result)


def verify_sampled_paint(source, paint):
    """Prevent stale/source-divergent sampled colors from reaching native output."""
    from native_paint import normalize_paint
    actual = normalize_paint(paint)
    evidence = actual['source_samples']
    recipe = {'source_sha256': evidence['sha256'], 'patches': evidence['patches'], 'kind': actual['kind']}
    if actual['kind'] != 'solid':
        recipe['positions'] = [s['position'] for s in actual['stops']]
        key = 'angle' if actual['kind'] == 'linear' else 'focus'
        recipe[key] = actual[key]
    if sample_paint(source, recipe) != actual:
        raise ValueError('sampled paint differs from declared source patches')
    return True


def validate_contract(manifest):
    try:
        return _validate(manifest)
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        return ['appearance_fidelity: ' + str(exc)]


def _validate(manifest):
    inventory = manifest.get('source_inventory', [])
    if not isinstance(inventory, list) or any(not isinstance(i, dict) for i in inventory):
        raise ValueError('source_inventory must contain objects')
    for item in inventory:
        if 'appearance_sensitive' in item and type(item['appearance_sensitive']) is not bool:
            raise ValueError('appearance_sensitive must be boolean')
    required = {i.get('id') for i in inventory if i.get('appearance_sensitive') is True}
    contract = manifest.get('appearance_fidelity')
    if contract is None:
        return ['appearance_fidelity required for appearance-sensitive inventory'] if required else []
    check_keys(contract, 'source_sha256 source_size color_space matte items', 'contract')
    if not isinstance(contract.get('source_sha256'), str) or not re.fullmatch('[0-9a-f]{64}', contract['source_sha256']):
        raise ValueError('source_sha256 required')
    size = contract.get('source_size')
    if not isinstance(size, list) or len(size) != 2 or any(type(v) is not int or v <= 0 for v in size):
        raise ValueError('positive integer source_size required')
    if contract.get('color_space') != 'srgb':
        raise ValueError('this profile requires explicitly declared srgb pixels')
    matte = contract.get('matte')
    if not isinstance(matte, list) or len(matte) != 3 or any(type(v) is not int or not 0 <= v <= 255 for v in matte):
        raise ValueError('explicit RGB matte required')
    regional = manifest.get('regional_fidelity')
    if regional and any(regional.get(k) != contract[k] for k in ('source_sha256', 'source_size')):
        raise ValueError('regional and appearance source binding disagree')
    items = contract.get('items')
    if not isinstance(items, list) or not 1 <= len(items) <= 100:
        raise ValueError('items must contain 1..100 objects')
    known = {i.get('id') for i in inventory}
    # Once this extension is adopted, component rasters cannot escape its coverage.
    required |= {i.get('id') for i in inventory if i.get('representation') == 'component_raster'}
    seen = set()
    for item in items:
        check_keys(item, 'id source_bbox comparison authorization requirements', 'item')
        iid = item.get('id')
        if not text(iid) or iid not in known or iid in seen:
            raise ValueError('appearance item ID missing, duplicated or outside inventory')
        seen.add(iid)
        bbox(item.get('source_bbox'), [0, 0, *size])
        mode = item.get('comparison')
        if mode not in ('source_exact', 'invariants'):
            raise ValueError('comparison must be source_exact or invariants')
        if mode == 'invariants' and not text(item.get('authorization')):
            raise ValueError('invariants comparison requires explicit authorization')
        reqs = item.get('requirements')
        if not isinstance(reqs, list) or not 1 <= len(reqs) <= 30:
            raise ValueError('requirements must contain 1..30 objects')
        ids = set()
        for req in reqs:
            check_keys(req, 'id dimension observation certainty criterion measurement scope paint_order', 'requirement')
            if not text(req.get('id')) or req['id'] in ids:
                raise ValueError('requirement ID missing or duplicated')
            ids.add(req['id'])
            if req.get('dimension') not in DIMENSIONS or req.get('certainty') not in ('observed', 'uncertain'):
                raise ValueError('invalid appearance dimension or certainty')
            if not all(text(req.get(k)) for k in ('observation', 'criterion')):
                raise ValueError('source observation and acceptance criterion required')
            order = req.get('paint_order')
            scope = req.get('scope')
            if req['dimension'] == 'occlusion':
                if scope not in ('native', 'mixed', 'raster_internal'):
                    raise ValueError('occlusion requires explicit scope')
                if scope != 'raster_internal' and order is None:
                    raise ValueError('native/mixed occlusion requires paint_order')
            elif scope is not None or order is not None:
                raise ValueError('scope/paint_order only apply to occlusion')
            if order is not None:
                check_keys(order, 'front_name back_name slide', 'paint_order')
                if scope == 'raster_internal' or type(order.get('slide')) is not int or order['slide'] != 1:
                    raise ValueError('package order supports slide 1, never raster-internal order')
                if not all(text(order.get(k)) for k in ('front_name', 'back_name')) or order['front_name'] == order['back_name']:
                    raise ValueError('distinct exact front/back object names required')
            probe = req.get('measurement')
            if probe is None:
                continue
            check_keys(probe, 'kind samples tolerance min_pixels', 'measurement')
            allowed = {'rgb_median': {'semantic_color'}, 'luma_delta': {'tone'}, 'luma_spread': {'tone', 'flat'}}
            if probe.get('kind') not in allowed or req['dimension'] not in allowed[probe['kind']]:
                raise ValueError('measurement does not support this appearance dimension')
            if mode != 'source_exact' or manifest.get('mode') != 'faithful':
                raise ValueError('numeric sampling requires faithful source_exact comparison')
            tol = probe.get('tolerance')
            if isinstance(tol, bool) or not isinstance(tol, (int, float)) or not math.isfinite(tol) or not 0 <= tol < 1:
                raise ValueError('tolerance must be finite in [0,1)')
            if type(probe.get('min_pixels')) is not int or probe['min_pixels'] < 1:
                raise ValueError('min_pixels must be a positive integer')
            samples = probe.get('samples')
            count = 2 if probe['kind'] == 'luma_delta' else 1
            if not isinstance(samples, list) or len(samples) != count:
                raise ValueError('measurement sample count mismatch')
            for sample in samples:
                bbox(sample, item['source_bbox'])
    if required - seen:
        raise ValueError('appearance contract does not cover required inventory IDs')
    return []


def prompt_requirements(manifest, item_ids):
    errors = validate_contract(manifest)
    if errors:
        raise ValueError('; '.join(errors))
    items = manifest.get('appearance_fidelity', {}).get('items', [])
    if not isinstance(item_ids, list) or not item_ids or any(not text(v) for v in item_ids) or len(set(item_ids)) != len(item_ids):
        raise ValueError('nonempty unique appearance item_ids required')
    chosen = [i for i in items if i['id'] in item_ids]
    if len(chosen) != len(item_ids) or any(i['comparison'] != 'invariants' for i in chosen):
        raise ValueError('generation requires known, authorized invariants items; no exact-source claim')
    content = [{'id': i['id'], 'requirements': i['requirements']} for i in chosen]
    return '\nSource-bound appearance requirements (do not invent unseen depth):\n' + json.dumps(content, ensure_ascii=False, sort_keys=True)


def bind_generation(request, manifest, item_ids):
    """Bind a fresh base request; do not accumulate corrective prompt fragments."""
    if 'appearance_binding' in request:
        raise ValueError('rebuild from the unbound base request, not a previously bound prompt')
    result = copy.deepcopy(request)
    result['prompt'] += prompt_requirements(manifest, item_ids)
    result['appearance_binding'] = dict(item_ids=list(item_ids), contract_sha256=contract_hash(manifest['appearance_fidelity']))
    return result


def validate_generation(request, manifest=None):
    binding = request.get('appearance_binding')
    if binding is None and not (manifest and 'appearance_fidelity' in manifest):
        return []
    try:
        check_keys(binding, 'item_ids contract_sha256', 'appearance_binding')
        if not manifest or binding.get('contract_sha256') != contract_hash(manifest['appearance_fidelity']):
            raise ValueError('appearance binding has missing context or stale contract hash')
        suffix = prompt_requirements(manifest, binding.get('item_ids'))
        if not isinstance(request.get('prompt'), str) or not request['prompt'].endswith(suffix):
            raise ValueError('prompt does not end with the current source-bound requirements')
    except (ValueError, KeyError, TypeError) as exc:
        return [str(exc)]
    return []


def measure(image, probe, matte):
    """Pillow display-luma diagnostics, not physical luminance or Delta E."""
    import numpy as np
    from PIL import Image
    values = []
    for x, y, w, h in probe['samples']:
        if w*h < probe['min_pixels']:
            raise LookupError('sample below predeclared min_pixels')
        crop = image.crop((x, y, x+w, y+h)).convert('RGBA')
        crop = Image.alpha_composite(Image.new('RGBA', crop.size, (*matte, 255)), crop)
        if probe['kind'] == 'rgb_median':
            values.append(np.median(np.asarray(crop.convert('RGB')).reshape(-1, 3), axis=0)/255.)
        else:
            pixels = np.asarray(crop.convert('L')).ravel()/255.
            values.append(float(np.percentile(pixels, 90)-np.percentile(pixels, 10))
                          if probe['kind'] == 'luma_spread' else float(np.median(pixels)))
    return (values[0]-values[1]) if probe['kind'] == 'luma_delta' else values[0]


def paint_order(artifact, req):
    if Path(artifact).suffix.lower() != '.pptx':
        raise LookupError('paint order readback supports PPTX only')
    with zipfile.ZipFile(artifact) as archive:
        objects, _ = load('component_assets').read_objects(archive)
    order = req['paint_order']
    selected = []
    for name in (order['back_name'], order['front_name']):
        matches = [(index, obj) for index, obj in enumerate(objects) if obj['slide'] == 1 and obj['name'] == name]
        if len(matches) != 1 or matches[0][1].get('unsupported'):
            raise LookupError('paint order needs uniquely named supported objects')
        selected.append(matches[0])
    kinds = [obj['kind'] for _, obj in selected]
    if any(k not in ('sp', 'pic') for k in kinds) or (req['scope'] == 'native' and 'pic' in kinds) or (req['scope'] == 'mixed' and set(kinds) != {'sp', 'pic'}):
        raise LookupError('declared native/mixed scope does not match actual objects')
    return selected[0][0] < selected[1][0]


def audit(artifact, manifest, manifest_path, evidence_path):
    errors = validate_contract(manifest)
    report = dict(valid=not errors, errors=errors, unverified=[], requirements=[], semantic_review='NOT_VERIFIED')
    if errors:
        return report
    contract = manifest.get('appearance_fidelity')
    if not contract or not evidence_path:
        report['unverified'].append('source-bound appearance contract and final render evidence required')
        return report
    try:
        fidelity = load('component_fidelity')
        align = any('measurement' in r for i in contract['items'] for r in i['requirements'])
        first, second, evidence, metadata = fidelity.load_render_pair(artifact, manifest, manifest_path, evidence_path, contract, align)
        report.update(metadata)
        if evidence.get('slide') != 1 or type(evidence.get('slide')) is not int:
            raise LookupError('appearance evidence must explicitly bind slide 1; other slides not supported by this profile')
        review = evidence.get('appearance_review')
        records = {}
        expected = {(i['id'], r['id']) for i in contract['items'] for r in i['requirements']}
        if review is not None:
            check_keys(review, 'contract_sha256 reviewer records', 'appearance_review')
            if review.get('contract_sha256') != contract_hash(contract) or not text(review.get('reviewer')):
                raise ValueError('appearance review has stale contract hash or missing reviewer')
            if not isinstance(review.get('records'), list):
                raise ValueError('review records must be a list')
            for record in review['records']:
                check_keys(record, 'item_id requirement_id status observation views', 'review record')
                key = (record.get('item_id'), record.get('requirement_id'))
                if key not in expected or key in records:
                    raise ValueError('unknown or duplicate appearance review record')
                if record.get('status') not in ('PASS', 'FAIL', 'NOT_VERIFIED') or not text(record.get('observation')):
                    raise ValueError('review status and observation required')
                if not isinstance(record.get('views'), list):
                    raise ValueError('review views must be a list')
                records[key] = record
        for item in contract['items']:
            for req in item['requirements']:
                key = (item['id'], req['id'])
                label = '/'.join(key)
                entry = dict(item_id=key[0], requirement_id=key[1], measurement='NOT_APPLICABLE', paint_order='NOT_APPLICABLE', review='NOT_VERIFIED')
                report['requirements'].append(entry)
                if req['certainty'] == 'uncertain':
                    report['unverified'].append(label + ': source relation uncertain; cannot certify inferred anatomy')
                if 'measurement' in req:
                    try:
                        if first.info.get('icc_profile') or second.info.get('icc_profile'):
                            raise LookupError('embedded ICC profile needs an explicitly verified sRGB conversion before measurement')
                        import numpy as np
                        probe = req['measurement']
                        before, after = measure(first, probe, contract['matte']), measure(second, probe, contract['matte'])
                        delta = float(np.max(np.abs(np.asarray(before)-np.asarray(after))))
                        entry['measurement'] = dict(source=np.asarray(before).tolist(), render=np.asarray(after).tolist(), deviation=delta, passed=delta <= probe['tolerance'])
                        if delta > probe['tolerance']:
                            errors.append(label + ': source-bound appearance measurement exceeded')
                    except (LookupError, ImportError) as exc:
                        entry['measurement'] = 'NOT_VERIFIED'
                        report['unverified'].append(label + ': ' + str(exc))
                if 'paint_order' in req:
                    try:
                        passed = paint_order(artifact, req)
                        entry['paint_order'] = 'PASS' if passed else 'FAIL'
                        if not passed:
                            errors.append(label + ': actual PPT paint order reversed')
                    except LookupError as exc:
                        entry['paint_order'] = 'NOT_VERIFIED'
                        report['unverified'].append(label + ': ' + str(exc))
                record = records.get(key)
                if record:
                    scales = set()
                    for view in record['views']:
                        check_keys(view, 'path sha256 scale', 'review view')
                        if not text(view.get('path')) or view.get('scale') not in ('delivered', 'detail', 'light', 'dark', 'actual'):
                            raise ValueError('view path and supported scale required')
                        path = Path(evidence_path).parent/view['path']
                        if fidelity.digest(path) != view.get('sha256'):
                            raise ValueError(label + ': review view hash mismatch')
                        fidelity.read_image(path)
                        scales.add(view['scale'])
                    needed = {'delivered', 'detail'}
                    if req['dimension'] == 'transparency':
                        needed |= {'light', 'dark', 'actual'}
                    entry['review'] = record['status']
                    if record['status'] == 'FAIL':
                        errors.append(label + ': reviewer rejected appearance')
                    if needed - scales:
                        entry['review'] = 'NOT_VERIFIED'
                if entry['review'] == 'NOT_VERIFIED':
                    report['unverified'].append(label + ': scoped delivered/detail/background review evidence incomplete')
        report['review_boundary'] = 'Hash-bound reviewer assertions and declared probes only; neither proves biological identity, visible occlusion or whole-figure fidelity.'
    except (LookupError, FileNotFoundError, ImportError) as exc:
        report['unverified'].append(str(exc))
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile) as exc:
        errors.append(str(exc))
    report['valid'] = not errors
    return report
