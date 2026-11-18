"""Source-first prepare/build over the existing inventory, extractors and emitters.

No image recognition, renderer, installer, arbitrary callback or old-deck input.
All outputs are new candidates. Human source/actual-render review remains separate.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys

from reconstruction_scene import (SourceFrame, SceneNode, ReconstructionScene,
    EditingGroup, RectLink, assemble_pptx, rectangle_draw, svg_draw, text_draw,
    manifest_component_draw, picture_draw)

SCRIPTS = Path(__file__).resolve().parent


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), SCRIPTS / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write_json(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)


def _keys(value, required, optional=()):
    if not isinstance(value, dict) or not set(required) <= set(value) or set(value) - set(required) - set(optional):
        raise ValueError('missing or unexpected construction fields')


def _positive(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def _hash(value):
    return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _editing_groups(config):
    groups = config.get('editing_groups', [])
    if not isinstance(groups, list) or ('editing_groups' in config and config['version'] < 4):
        raise ValueError('editing_groups requires construction version 4 and a list')
    result = []
    for group in groups:
        _keys(group, ('id', 'members', 'observation'))
        if not _text(group['observation']):
            raise ValueError('editing group requires a source/editing-scope observation')
        result.append(EditingGroup(group['id'], group['members']))
    return result


def _validate_rect_link(item, by):
    recipe = item['construction']
    options = recipe['options']
    _keys(options, ('source_port', 'target_port'), ('color', 'width_pt'))
    ports = {'top', 'bottom', 'left', 'right'}
    if options['source_port'] not in ports or options['target_port'] not in ports:
        raise ValueError('unknown rectangular connection port')
    color = options.get('color', '173D6A')
    if (not isinstance(color, str) or len(color.removeprefix('#')) != 6
            or any(c not in '0123456789abcdefABCDEF' for c in color.removeprefix('#'))
            or not _positive(options.get('width_pt', 1.8))):
        raise ValueError('rect_link requires six-digit RGB color and positive width_pt')
    source, target = [by[v] for v in recipe['endpoints']]
    if source is target or any(v['construction']['kind'] != 'rectangle' for v in (source, target)):
        raise ValueError('rect_link requires distinct native rectangle source/target items')
    def port(node, side):
        x, y, w, h = node['bbox']
        return {'top': (x+w/2, y), 'bottom': (x+w/2, y+h),
                'left': (x, y+h/2), 'right': (x+w, y+h/2)}[side]
    start, end = port(source, options['source_port']), port(target, options['target_port'])
    delta = (end[0]-start[0], end[1]-start[1])
    outward = {'top': (0, -1), 'bottom': (0, 1), 'left': (-1, 0), 'right': (1, 0)}
    dot = lambda a, b: a[0]*b[0]+a[1]*b[1]
    if (start == end or (abs(delta[0]) > 1e-8 and abs(delta[1]) > 1e-8)
            or dot(delta, outward[options['source_port']]) <= 0
            or dot(delta, outward[options['target_port']]) >= 0):
        raise ValueError('rect_link requires aligned outward-facing rectangular ports')
    x, y, w, h = item['bbox']
    if any(not x-1e-8 <= p[0] <= x+w+1e-8 or not y-1e-8 <= p[1] <= y+h+1e-8 for p in (start, end)):
        raise ValueError('rect_link endpoints exceed source-observed relationship bbox')


def validate_contract(manifest):
    """Only executable fields; base and feature schemas retain their own validators."""
    if 'construction' not in manifest:
        return []
    try:
        config = manifest['construction']
        _keys(config, ('version', 'slide_width_inches'), ('editing_groups',))
        if type(config['version']) is not int or config['version'] not in (1,2,3,4) or not _positive(config['slide_width_inches']):
            raise ValueError('construction version 1/2/3/4 and positive slide width required')
        policy = manifest.get('editing_policy', 'native')
        if manifest.get('mode') != 'faithful' or policy not in ('native', 'hybrid', None):
            raise ValueError('this adapter supports faithful native or explicitly approved hybrid output only')
        if policy == 'hybrid':
            if config['version'] < 4:
                raise ValueError('hybrid assembly requires construction version 4')
            from component_assets import validate_contract as validate_assets
            errors = validate_assets(manifest)
            if errors:
                raise ValueError('; '.join(errors))
        groups = _editing_groups(config)
        source, canvas = manifest['source'], manifest['canvas']
        if not _hash(source.get('sha256')):
            raise ValueError('source.sha256 required before construction')
        if any(type(source.get(k)) is not int or source[k] <= 0 or canvas.get(k) != source[k]
               for k in ('width', 'height')):
            raise ValueError('adapter requires source-pixel canvas; do not silently rescale observations')
        targets = manifest['targets']
        if len(targets) != 1 or targets[0]['format'] != 'pptx':
            raise ValueError('adapter requires one PPTX target')
        if Path(targets[0]['path']).suffix.lower() != '.pptx':
            raise ValueError('PPTX target filename must end with .pptx')
        items = manifest.get('source_inventory', [])
        if not items:
            raise ValueError('source inventory required before preparation')
        frame = SourceFrame((0, 0, source['width'], source['height']),
                            (0, 0, config['slide_width_inches'], config['slide_width_inches']*source['height']/source['width']))
        by = {i['id']: i for i in items}
        if len(by) != len(items):
            raise ValueError('duplicate source inventory IDs')
        nodes = []
        used_connections = set()
        connections = {c['id']: c for c in manifest.get('connections', [])}
        instances = {i['instance_id']: i for i in manifest.get('component_instances', [])}
        for item in items:
            identity = item['id']
            recipe = item.get('construction')
            _keys(recipe, ('kind', 'observation'), ('options', 'extract', 'trace', 'asset', 'field_fit',
                'parent', 'behind', 'z', 'container', 'connection', 'endpoints', 'frame_bbox'))
            if not _text(recipe['observation']):
                raise ValueError(identity + ': source observation required')
            if item.get('output_name', identity) != identity or item.get('output_slide', 1) != 1 or item.get('required_count', 1) != 1:
                raise ValueError(identity + ': one named editing unit on slide 1 required')
            kind = recipe['kind']
            specific = {'text': {'options'}, 'rectangle': {'options'},
                        'svg': {'asset'}, 'trace': {'extract', 'trace'}, 'native_component': set(),
                        'picture': set(), 'rect_link': {'options'}}
            if kind not in specific:
                raise ValueError(identity + ': unsupported route; no template fallback')
            if kind in ('picture', 'rect_link') and config['version'] < 4:
                raise ValueError(identity + ': picture/rect_link requires construction version 4')
            if kind == 'picture':
                if policy != 'hybrid' or item.get('representation') != 'component_raster':
                    raise ValueError(identity + ': picture requires approved hybrid component_raster')
                instance = instances.get(item.get('component_instance'))
                if instance is None or instance['output_name'] != identity or instance['slide'] != 1:
                    raise ValueError(identity + ': picture must use its exact canonical instance/output_name on slide 1')
                if instance['rotation'] not in (0, 90, 180, 270):
                    raise ValueError(identity + ': picture route supports orthogonal rotation only')
                if any(abs(a-b) > 1e-6 for a, b in zip(frame.place(item['bbox']), instance['bbox_inches'])):
                    raise ValueError(identity + ': source bbox and component instance placement disagree')
            elif item.get('representation') not in ('native_primitive', 'native_composite'):
                raise ValueError(identity + ': native route requires native representation')
            extra = set(recipe) & {'options', 'extract', 'trace', 'asset'}
            if extra != specific[kind]:
                raise ValueError(identity + ': route fields do not match kind')
            if 'field_fit' in recipe:
                if kind!='native_component' or config['version']<3:
                    raise ValueError('field_fit requires native_component and construction version 3 or newer')
                from source_fields import validate_options
                validate_options(recipe['field_fit'])
            role = 'relation' if item['role'] == 'connector' else ('text' if item['role'] == 'text' else 'component')
            if (role == 'text') != (kind == 'text'):
                raise ValueError(identity + ': text must use native text route')
            if 'frame_bbox' in recipe and (kind != 'text' or not isinstance(recipe['frame_bbox'], list)):
                raise ValueError(identity + ': frame_bbox requires the native text route and a box list')
            if recipe.get('container') is not None:
                if recipe['container'] is not True or role != 'component' or kind == 'picture':
                    raise ValueError(identity + ': invalid container role')
                role = 'container'
            if kind == 'text':
                _keys(recipe['options'], ('font_size_px',), ('color', 'font', 'bold', 'align'))
                text_draw(item['text'], **recipe['options'])
            elif kind == 'rectangle':
                _keys(recipe['options'], (), ('fill', 'stroke', 'stroke_pt'))
                for key in ('fill', 'stroke'):
                    color = recipe['options'].get(key)
                    if color is not None and (not isinstance(color, str) or len(color.lstrip('#')) != 6
                            or any(c not in '0123456789abcdefABCDEF' for c in color.lstrip('#'))):
                        raise ValueError(identity + ': RGB color must contain six hex digits')
                if not _positive(recipe['options'].get('stroke_pt', 1)):
                    raise ValueError(identity + ': positive stroke width required')
                if item['role'] not in ('shape', 'decoration'):
                    raise ValueError(identity + ': rectangle cannot stand in for an icon/chart')
            elif kind == 'svg':
                _keys(recipe['asset'], ('path', 'sha256'))
                if not _text(recipe['asset']['path']) or not _hash(recipe['asset']['sha256']):
                    raise ValueError(identity + ': SVG path/hash required')
            elif kind == 'native_component':
                matches = [c for c in manifest.get('native_components', []) if c['id'] == identity]
                if len(matches) != 1 or matches[0]['output_name'] != identity:
                    raise ValueError(identity + ': native_component requires the same canonical component ID/output_name')
            elif kind == 'trace':
                extraction = recipe['extract']
                _keys(extraction, ('method', 'foreground', 'background', 'reserved_regions'),
                      ('selector', 'annotations','matting','occlusions'))
                if extraction['method'] not in ('selector', 'grabcut','closed_form') or (extraction['method'] == 'selector') != ('selector' in extraction):
                    raise ValueError(identity + ': explicit extraction method required')
                layered=extraction['method']=='closed_form'
                if layered:
                    if config['version']<2: raise ValueError('closed_form layers require construction version 2 or newer')
                    from source_layers import validate_layer_options
                    validate_layer_options(extraction)
                    if recipe['trace']['representation']=='palette_stack':
                        raise ValueError('soft layers require disjoint palette_edges or smooth; never flatten alpha')
                elif 'matting' in extraction or 'occlusions' in extraction:
                    raise ValueError('layer fields require closed_form extraction')
                if 'annotations' in extraction and extraction['method'] not in ('grabcut','closed_form'):
                    raise ValueError(identity + ': annotations require grabcut/closed_form')
                trace = recipe['trace']
                _keys(trace, ('colors', 'representation', 'max_native_paths', 'max_native_commands'))
                if trace['representation'] not in ('palette_edges', 'palette_stack', 'smooth'):
                    raise ValueError(identity + ': trace must retain source paint')
                if type(trace['colors']) is not int or not 2 <= trace['colors'] <= 64:
                    raise ValueError(identity + ': colors must be 2..64')
                for key in ('max_native_paths', 'max_native_commands'):
                    if type(trace[key]) is not int or not 1 <= trace[key] <= 1_000_000:
                        raise ValueError(identity + ': invalid native edit budget')
                if any(type(v) is not int for v in item['bbox']):
                    raise ValueError(identity + ': extraction context uses integer source pixels')
            endpoints = recipe.get('endpoints')
            if role == 'relation':
                if kind not in ('svg', 'rect_link') or recipe.get('connection') not in connections:
                    raise ValueError(identity + ': relation requires observed SVG/rect_link and known connection')
                if not isinstance(endpoints, list) or len(endpoints) != 2 or any(v not in by for v in endpoints):
                    raise ValueError(identity + ': source item endpoints required')
                connection = connections[recipe['connection']]
                if [by[v]['module'] for v in endpoints] != [connection['source'], connection['target']]:
                    raise ValueError(identity + ': item endpoints disagree with module connection')
                if recipe['connection'] in used_connections:
                    raise ValueError('connection emitted more than once')
                used_connections.add(recipe['connection'])
                if kind == 'rect_link':
                    _validate_rect_link(item, by)
            elif 'connection' in recipe or endpoints is not None:
                raise ValueError(identity + ': endpoints require connector role')
            if kind == 'rect_link' and role != 'relation':
                raise ValueError('rect_link requires connector role')
            draw = RectLink(**recipe['options']) if kind == 'rect_link' else lambda *a: None
            nodes.append(SceneNode(identity, recipe.get('frame_bbox', item['bbox']), draw, role,
                recipe.get('parent'), recipe.get('behind', ()), recipe.get('z', 0), endpoints))
        if used_connections != set(connections):
            raise ValueError('all declared connections require source-observed construction')
        if {c['id'] for c in manifest.get('native_components', [])} != {
                i['id'] for i in items if i['construction']['kind'] == 'native_component'}:
            raise ValueError('declared native components must use their canonical construction route')
        ReconstructionScene(frame, nodes, groups).ordered()
        return []
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        return ['construction: ' + str(exc)]


def runtime_check(manifest, *, node=None, extract_python=None, check_extraction=True):
    required = ('pptx', 'PIL', 'numpy')
    missing = [name for name in required if importlib.util.find_spec(name) is None]
    versions = {}
    for name in required:
        if name not in missing:
            try:
                module = importlib.import_module(name)
                versions[name] = getattr(module, '__version__', 'unknown')
            except ImportError as exc:
                missing.append(name + ': ' + str(exc))
    traces = [i for i in manifest['source_inventory'] if i['construction']['kind'] == 'trace']
    node = node or shutil.which('node')
    if traces and not node:
        missing.append('Node.js (supply --node)')
    if traces and node:
        subprocess.run([str(node), '--version'], check=True, capture_output=True, timeout=15)
    methods={i['construction']['extract']['method'] for i in traces}
    if check_extraction and methods & {'grabcut','closed_form'}:
        interpreter = extract_python or sys.executable
        imports={'PIL','numpy'}
        if 'grabcut' in methods: imports.add('cv2')
        if 'closed_form' in methods: imports.add('scipy')
        check = subprocess.run([str(interpreter), '-c', 'import '+', '.join(sorted(imports))],
            capture_output=True, text=True, timeout=30)
        if check.returncode:
            missing.append('/'.join(sorted(imports))+' in extraction interpreter; use --extract-python')
    if missing:
        raise RuntimeError('Missing installed dependencies: ' + ', '.join(missing) + '; no automatic install/fallback')
    return {'python': sys.executable, 'node': str(node) if node else None,
            'extract_python': str(extract_python or sys.executable), 'versions': versions,
            'pipeline_sha256': sha(Path(__file__)), 'skill_sha256': sha(SCRIPTS.parent / 'SKILL.md')}


def _check_manifest_data(data):
    report = load('validate-visual-manifest').validate_manifest(data)
    if not report['valid']:
        raise ValueError('Invalid manifest before construction: ' + '; '.join(report['errors'][:8]))
    if 'construction' not in data:
        raise ValueError('manifest has no executable construction recipes')
    return data


def checked_manifest(path):
    return _check_manifest_data(read_json(path))


def revise_text(manifest_path, changes_path, output):
    """Create a new canonical manifest from reviewed native text adjustments."""
    manifest_path, changes_path, output = map(Path, (manifest_path, changes_path, output))
    if output.parent.resolve() != manifest_path.resolve().parent or output.suffix.lower() != '.json':
        raise ValueError('write a new sibling JSON manifest to preserve relative source and asset paths')
    payload = manifest_path.read_bytes()
    data = _check_manifest_data(json.loads(payload.decode('utf-8')))
    _bound_file(manifest_path.resolve().parent, data['source'])

    def unique_keys(pairs):
        values = dict(pairs)
        if len(values) != len(pairs):
            raise ValueError('duplicate key in text revision')
        return values

    plan = json.loads(changes_path.read_bytes(), object_pairs_hook=unique_keys)
    _keys(plan, ('manifest_sha256', 'items'))
    if plan['manifest_sha256'] != hashlib.sha256(payload).hexdigest():
        raise ValueError('text revision targets a different manifest hash')
    if not isinstance(plan['items'], list) or not plan['items']:
        raise ValueError('text revision requires one or more reviewed items')
    by_id = {item['id']: item for item in data['source_inventory']}
    changed = []
    seen = set()
    for change in plan['items']:
        _keys(change, ('id', 'reason'), ('frame_bbox', 'font_size_px'))
        identity = change['id']
        if not isinstance(identity, str) or identity not in by_id or identity in seen or not _text(change['reason']):
            raise ValueError('text revision requires a unique existing item ID and source-grounded reason')
        item = by_id[identity]
        recipe = item['construction']
        if recipe['kind'] != 'text':
            raise ValueError(identity + ': only native text recipes can be revised')
        frame = change.get('frame_bbox', recipe.get('frame_bbox', item['bbox']))
        size = change.get('font_size_px', recipe['options']['font_size_px'])
        if not isinstance(frame, list) or not _positive(size):
            raise ValueError(identity + ': frame must be a box list and font size a finite positive number')
        if frame == recipe.get('frame_bbox', item['bbox']) and size == recipe['options']['font_size_px']:
            raise ValueError(identity + ': no effective text change')
        if 'frame_bbox' in change:
            recipe['frame_bbox'] = frame
        if 'font_size_px' in change:
            recipe['options']['font_size_px'] = size
        seen.add(identity)
        changed.append(identity)
    _check_manifest_data(data)
    result = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)
    with output.open('x', encoding='utf-8') as stream:
        stream.write(result)
    return changed


def _bound_file(base, entry):
    path = (base / entry['path']).resolve()
    if sha(path) != entry['sha256']:
        raise ValueError('prepared input hash changed: ' + entry['path'])
    return path


def _frozen_file(base, entry):
    """Prepared component bindings must travel inside the preparation tree."""
    path = (Path(base) / entry['path']).resolve()
    if Path(entry['path']).is_absolute() or not path.is_relative_to(Path(base).resolve()):
        raise ValueError('frozen component path must stay inside the preparation directory')
    return _bound_file(Path(base), entry)


def _freeze_component_assets(data, base, output):
    """Copy approved bytes and every file needed by existing provenance checks."""
    from raster_components import read_image, verify_preparation
    records = []
    for index, asset in enumerate(data.get('component_assets', [])):
        folder = output / 'component-assets' / f'asset-{index:04d}'
        folder.mkdir(parents=True)
        original = _bound_file(base, asset)
        image = read_image(original, asset['sha256'])
        image.close()
        if asset['source_kind'] == 'source_crop':
            if asset['source_sha256'] != data['source']['sha256']:
                raise ValueError(asset['asset_id'] + ': source crop must bind the original source')
            x, y, w, h = asset['source_bbox']
            if x+w > data['source']['width'] or y+h > data['source']['height']:
                raise ValueError(asset['asset_id'] + ': source crop exceeds original source')
        if 'preparation' in asset:
            verify_preparation(data, asset['asset_id'], base, original.read_bytes())
        def freeze(binding, filename):
            path = _bound_file(base, binding)
            target = folder / filename
            shutil.copyfile(path, target)
            if sha(target) != binding['sha256']:
                raise ValueError('component input changed while freezing: ' + binding['path'])
            return {'path': target.relative_to(output).as_posix(), 'sha256': sha(target)}
        record = {'asset_id': asset['asset_id'],
                  'asset': freeze(asset, 'approved' + original.suffix.lower())}
        preparation = asset.get('preparation', {})
        if 'alpha_path' in preparation:
            record['alpha'] = freeze({'path': preparation['alpha_path'], 'sha256': preparation['alpha_sha256']}, 'alpha.png')
        if preparation.get('method') == 'source-layer':
            from source_layers import read_layer_bundle
            binding = {'path': preparation['receipt_path'], 'sha256': preparation['receipt_sha256']}
            original_receipt = _bound_file(base, binding)
            layer, _ = read_layer_bundle(dict(binding, path=str(original_receipt)),
                                         data['source']['sha256'], asset['source_bbox'])
            layer.close()
            (folder / 'source-layer').mkdir()
            record['source_layer'] = freeze(binding, 'source-layer/candidate.json')
            record['source_layer_outputs'] = {
                name: freeze({'path': str(original_receipt.parent / (name + '.png')), 'sha256': expected},
                             'source-layer/' + name + '.png')
                for name, expected in read_json(original_receipt)['outputs_sha256'].items()}
            layer, _ = read_layer_bundle(dict(record['source_layer'], path=str(output / record['source_layer']['path'])),
                                         data['source']['sha256'], asset['source_bbox'])
            layer.close()
        if asset['source_kind'] == 'generated':
            record['references'] = [freeze(ref, f'reference-{j:04d}' + Path(ref['path']).suffix.lower())
                                    for j, ref in enumerate(asset['generation']['references'])]
        records.append(record)
    return records


def _bound_component_manifest(data, receipt, prepared):
    """Rebase only file locations; retain canonical approval/content fields."""
    from raster_components import read_image, verify_preparation
    records = receipt.get('component_assets', [])
    assets = data.get('component_assets', [])
    if [r['asset_id'] for r in records] != [a['asset_id'] for a in assets]:
        raise ValueError('prepared component asset inventory is incomplete or reordered')
    rebound = copy.deepcopy(data)
    rebound['source']['path'] = receipt['source']['path']
    for asset, record in zip(rebound.get('component_assets', []), records):
        expected_fields = {'asset_id', 'asset'}
        preparation = asset.get('preparation', {})
        if 'alpha_path' in preparation:
            expected_fields.add('alpha')
        if preparation.get('method') == 'source-layer':
            expected_fields.update(('source_layer', 'source_layer_outputs'))
        if asset['source_kind'] == 'generated':
            expected_fields.add('references')
        if set(record) != expected_fields:
            raise ValueError('missing or unexpected frozen component provenance files')
        path = _frozen_file(prepared, record['asset'])
        if record['asset']['sha256'] != asset['sha256']:
            raise ValueError(asset['asset_id'] + ': frozen approved asset hash differs from canonical manifest')
        image = read_image(path, asset['sha256'])
        image.close()
        asset['path'] = record['asset']['path']
        if 'alpha_path' in preparation:
            _frozen_file(prepared, record['alpha'])
            if record['alpha']['sha256'] != preparation['alpha_sha256']:
                raise ValueError(asset['asset_id'] + ': frozen alpha differs from canonical preparation')
            preparation['alpha_path'] = record['alpha']['path']
        if preparation.get('method') == 'source-layer':
            from source_layers import read_layer_bundle
            frozen_receipt = _frozen_file(prepared, record['source_layer'])
            if record['source_layer']['sha256'] != preparation['receipt_sha256']:
                raise ValueError(asset['asset_id'] + ': frozen source-layer receipt differs from canonical preparation')
            expected = read_json(frozen_receipt)['outputs_sha256']
            outputs = record['source_layer_outputs']
            if set(outputs) != set(expected):
                raise ValueError('frozen source-layer companions are incomplete or unexpected')
            for name, expected_hash in expected.items():
                companion = outputs[name]
                location = (Path(record['source_layer']['path']).parent / (name + '.png')).as_posix()
                if companion['path'] != location or companion['sha256'] != expected_hash:
                    raise ValueError('frozen source-layer companion identity/location changed')
                _frozen_file(prepared, companion)
            layer, _ = read_layer_bundle(dict(record['source_layer'], path=str(frozen_receipt)),
                                         data['source']['sha256'], asset['source_bbox'])
            layer.close()
            preparation['receipt_path'] = record['source_layer']['path']
        if asset['source_kind'] == 'generated':
            refs = asset['generation']['references']
            if len(refs) != len(record['references']):
                raise ValueError('frozen generation references are incomplete')
            for ref, binding in zip(refs, record['references']):
                _frozen_file(prepared, binding)
                if binding['sha256'] != ref['sha256']:
                    raise ValueError('frozen generation reference differs from canonical provenance')
                ref['path'] = binding['path']
        if 'preparation' in asset:
            verify_preparation(rebound, asset['asset_id'], prepared, path.read_bytes())
    return rebound


def _picture_candidate(data, item, source_binding, asset_records):
    instance = next(i for i in data['component_instances'] if i['instance_id'] == item['component_instance'])
    asset = next(a for a in data['component_assets'] if a['asset_id'] == instance['asset_id'])
    frozen = next(a for a in asset_records if a['asset_id'] == asset['asset_id'])
    return {'kind': 'approved_independent_picture', 'source_sha256': data['source']['sha256'],
            'source_bbox': item['bbox'], 'observation': item['construction']['observation'],
            'instance': instance, 'asset': asset,
            'review_inputs': {'original_source': source_binding, 'approved_asset': frozen['asset']},
            'review_scope': 'Inspect original source and approved independent asset; final render/editor review NOT_PERFORMED'}


def _stage_component_inputs(data, prepared, output):
    """Make the final component-audit inputs portable alongside the saved deck."""
    result = copy.deepcopy(data)
    def stage(record):
        relative = Path(record['path'])
        binding = {'path': relative.as_posix(), 'sha256': record['sha256']}
        original = _frozen_file(prepared, binding)
        target = output / 'inputs' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            shutil.copyfile(original, target)
        elif sha(target) != sha(original):
            raise ValueError('conflicting portable input names')
        record['path'] = target.relative_to(output).as_posix()
    stage(result['source'])
    for asset in result.get('component_assets', []):
        stage(asset)
        preparation = asset.get('preparation', {})
        if 'alpha_path' in preparation:
            binding = {'path': preparation['alpha_path'], 'sha256': preparation['alpha_sha256']}
            stage(binding)
            preparation['alpha_path'] = binding['path']
        if preparation.get('method') == 'source-layer':
            original_receipt = _frozen_file(prepared, {'path': preparation['receipt_path'],
                                                      'sha256': preparation['receipt_sha256']})
            for name, expected in read_json(original_receipt)['outputs_sha256'].items():
                companion = {'path': (Path(preparation['receipt_path']).parent / (name + '.png')).as_posix(),
                             'sha256': expected}
                stage(companion)
            binding = {'path': preparation['receipt_path'], 'sha256': preparation['receipt_sha256']}
            stage(binding)
            preparation['receipt_path'] = binding['path']
        if asset['source_kind'] == 'generated':
            for ref in asset['generation']['references']:
                stage(ref)
    return result


def _field_candidate(source, data, item, support, base, layer=None):
    """Fit in one frozen coordinate frame; never use an old compiled tree as input."""
    from source_fields import fit_component, digest
    if support['sha256'] != item['construction']['field_fit']['support']['sha256']:
        raise ValueError(item['id'] + ': field support differs from frozen recipe')
    source_item=copy.deepcopy(item)
    source_item['construction']['field_fit']['support']=support
    original_layer=item['construction']['field_fit'].get('source_layer')
    if bool(original_layer)!=bool(layer) or (layer and layer['sha256']!=original_layer['sha256']):
        raise ValueError(item['id']+': field layer differs from frozen recipe')
    if layer:source_item['construction']['field_fit']['source_layer']=layer
    component=next(c for c in data['native_components'] if c['id']==item['id'])
    evidence,preview=fit_component(source,data['source']['sha256'],source_item,component,base_dir=base)
    evidence['input_options_sha256']=digest(item['construction']['field_fit'])
    return evidence,preview


def prepare(manifest_path, output, *, node=None, extract_python=None):
    """Freeze source inventory; extract measured supports and copy observed vectors."""
    from PIL import Image
    manifest_path, output = Path(manifest_path).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError('use a new preparation directory')
    data = checked_manifest(manifest_path)
    runtime = runtime_check(data, node=node, extract_python=extract_python)
    source = (manifest_path.parent / data['source']['path']).resolve()
    if sha(source) != data['source']['sha256']:
        raise ValueError('original source hash changed')
    with Image.open(source) as image:
        if image.size != (data['source']['width'], data['source']['height']) or getattr(image, 'n_frames', 1) != 1:
            raise ValueError('source dimensions/frame mismatch')
    output.mkdir(parents=True)
    frozen_source = output / ('source' + source.suffix)
    shutil.copyfile(source, frozen_source)
    write_json(output / 'input-manifest.json', data)
    records = []
    try:
        component_assets = _freeze_component_assets(data, manifest_path.parent, output)
        for index, item in enumerate(data['source_inventory']):
            recipe, record = item['construction'], {'id': item['id'], 'kind': item['construction']['kind']}
            folder = output / f'item-{index:04d}'
            if recipe['kind'] == 'picture':
                folder.mkdir()
                write_json(folder / 'candidate.json', _picture_candidate(data, item,
                    {'path': frozen_source.name, 'sha256': sha(frozen_source)}, component_assets))
                record['candidate'] = {'path': (folder / 'candidate.json').relative_to(output).as_posix(),
                                       'sha256': sha(folder / 'candidate.json')}
                record['source_bbox'] = item['bbox']
            elif recipe['kind'] == 'trace':
                plan = dict(recipe['extract'], source_sha256=data['source']['sha256'],
                            context_bbox=item['bbox'], observation=recipe['observation'])
                if extract_python:
                    plan_path = output / f'extraction-{index:04d}.json'
                    write_json(plan_path, plan)
                    result = subprocess.run([str(extract_python), '-X', 'utf8', '-B',
                        str(SCRIPTS / 'source_objects.py'), str(frozen_source), str(plan_path), str(folder)],
                        capture_output=True, text=True, encoding='utf-8', timeout=180)
                    if result.returncode:
                        raise RuntimeError(item['id'] + ': extraction failed: ' + result.stderr[-2000:])
                else:
                    from source_objects import extract_source_object
                    outputs, evidence = extract_source_object(frozen_source, plan)
                    folder.mkdir()
                    for name, content in outputs.items():
                        (folder / (name + '.png')).write_bytes(content)
                    write_json(folder / 'candidate.json', evidence)
                evidence = read_json(folder / 'candidate.json')
                # Show the candidate in its original context coordinate system,
                # not a tightly fitted thumbnail that hides crop/placement errors.
                with Image.open(frozen_source) as original:
                    x, y, w, h = item['bbox']
                    context = original.convert('RGBA').crop((x, y, x+w, y+h))
                context.save(folder / 'source-context.png')
                candidate = Image.new('RGBA', (w, h), '#eeeeee')
                bx, by, _, _ = evidence['source_bbox']
                with Image.open(folder / 'rgba.png') as rgba:
                    candidate.alpha_composite(rgba.convert('RGBA'), (bx-x, by-y))
                comparison = Image.new('RGB', (w*2+8, h), '#888888')
                comparison.paste(context.convert('RGB'), (0, 0))
                comparison.paste(candidate.convert('RGB'), (w+8, 0))
                comparison.save(folder / 'comparison.png')
                record['candidate'] = {'path': str((folder / 'candidate.json').relative_to(output)),
                                       'sha256': sha(folder / 'candidate.json')}
                record['source_bbox'] = evidence['source_bbox']
            elif 'field_fit' in recipe:
                asset=_bound_file(manifest_path.parent,recipe['field_fit']['support'])
                folder.mkdir()
                shutil.copyfile(asset,folder/'support.png')
                record['support']={'path':str((folder/'support.png').relative_to(output)),'sha256':sha(asset)}
                if 'source_layer' in recipe['field_fit']:
                    from source_layers import read_layer_bundle
                    binding=recipe['field_fit']['source_layer']
                    original=_bound_file(manifest_path.parent,binding)
                    layer,_=read_layer_bundle(dict(binding,path=str(original)),data['source']['sha256'],item['bbox'])
                    layer.close()
                    frozen=folder/'layer';frozen.mkdir()
                    shutil.copyfile(original,frozen/'candidate.json')
                    for name in read_json(original)['outputs_sha256']:
                        shutil.copyfile(original.parent/(name+'.png'),frozen/(name+'.png'))
                    record['source_layer']={'path':str((frozen/'candidate.json').relative_to(output)),
                                            'sha256':sha(original)}
                evidence,preview=_field_candidate(frozen_source,data,item,record['support'],output,record.get('source_layer'))
                write_json(folder/'candidate.json',evidence)
                Image.fromarray(preview).save(folder/'predicted-field.png')
                record['candidate']={'path':str((folder/'candidate.json').relative_to(output)),
                                     'sha256':sha(folder/'candidate.json')}
                record['source_bbox']=item['bbox']
            elif recipe['kind'] == 'svg':
                from native_vectors import read_vectors
                asset = _bound_file(manifest_path.parent, recipe['asset'])
                read_vectors(asset)
                folder.mkdir()
                shutil.copyfile(asset, folder / 'source.svg')
                record['asset'] = {'path': str((folder / 'source.svg').relative_to(output)), 'sha256': sha(asset)}
            records.append(record)
        receipt = {'status': 'PREPARED', 'input_sha256': sha(output / 'input-manifest.json'),
                   'source': {'path': frozen_source.name, 'sha256': sha(frozen_source)},
                   'runtime': runtime, 'items': records,
                   'source_coverage': 'REQUIRES_SOURCE_REVIEW'}
        if component_assets:
            receipt['component_assets'] = component_assets
        write_json(output / 'prepared.json', receipt)
        write_json(output / 'review-template.json', {'prepared_sha256': sha(output / 'prepared.json'),
            'items': [{'id': r['id'], 'candidate_sha256': r['candidate']['sha256'],
                       'accepted': False, 'note': ''} for r in records if 'candidate' in r]})
        return receipt
    except Exception as exc:
        write_json(output / 'failure.json', {'status': 'FAILED', 'phase': 'prepare', 'error': str(exc)})
        raise


def build(prepared, output, *, review=None, node=None):
    """Trace qualified support, assemble new deck, reopen and run existing checks."""
    from pptx import Presentation
    from pptx.util import Inches
    from component_fidelity import trace_component
    prepared, output = Path(prepared).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError('use a new build directory; never overlay a previous deck')
    receipt = read_json(prepared / 'prepared.json')
    if receipt.get('status') != 'PREPARED' or sha(prepared / 'input-manifest.json') != receipt['input_sha256']:
        raise ValueError('prepared manifest changed or preparation incomplete')
    data = checked_manifest(prepared / 'input-manifest.json')
    source = (_frozen_file if data['construction']['version'] >= 4 else _bound_file)(prepared, receipt['source'])
    if sha(source) != data['source']['sha256']:
        raise ValueError('prepared source disagrees with manifest')
    frozen_manifest = _bound_component_manifest(data, receipt, prepared)
    records = receipt['items']
    if [r['id'] for r in records] != [i['id'] for i in data['source_inventory']]:
        raise ValueError('prepared inventory is incomplete or reordered')
    required_candidates={i['id'] for i in data['source_inventory']
                         if i['construction']['kind'] in ('trace', 'picture') or 'field_fit' in i['construction']}
    if {r['id'] for r in records if 'candidate' in r} != required_candidates:
        raise ValueError('prepared component candidates are incomplete or unexpected')
    approvals = {}
    if review:
        review_data = read_json(review)
        if review_data.get('prepared_sha256') != sha(prepared / 'prepared.json'):
            raise ValueError('review belongs to a different preparation')
        entries = review_data.get('items', [])
        approvals = {e['id']: e for e in entries}
        if len(approvals) != len(entries):
            raise ValueError('duplicate component reviews')
    if set(approvals) != required_candidates:
        raise ValueError('inspect extracted components and supply their exact review; no automatic approval')
    # Check all support/asset identities before drawing anything. Evidence hashes
    # bind files, not reviewer truth; no claim of cryptographic attestation.
    field_components={}
    for item, record in zip(data['source_inventory'], records):
        if record['kind'] != item['construction']['kind']:
            raise ValueError('prepared route changed')
        if 'candidate' in record:
            path = _bound_file(prepared, record['candidate'])
            evidence = read_json(path)
            approval = approvals[item['id']]
            if approval.get('candidate_sha256') != sha(path):
                raise ValueError(item['id'] + ': stale component inspection')
            if approval.get('accepted') is False:
                raise ValueError(item['id'] + ': component inspection rejected; revise source observations')
            if approval.get('accepted') is not True or not _text(approval.get('note')):
                raise ValueError(item['id'] + ': missing/stale component inspection')
        if record['kind'] == 'picture':
            if evidence != _picture_candidate(data, item, receipt['source'], receipt['component_assets']) or record.get('source_bbox') != item['bbox']:
                raise ValueError(item['id'] + ': picture candidate differs from original source/approved component')
        elif 'field_fit' in item['construction']:
            from source_fields import digest
            _bound_file(prepared,record['support'])
            if 'source_layer' in record:_bound_file(prepared,record['source_layer'])
            expected,_=_field_candidate(source,data,item,record['support'],prepared,record.get('source_layer'))
            if digest(expected)!=digest(evidence):
                raise ValueError(item['id']+': fitted field differs from frozen source/recipe')
            field_components[item['id']]=expected['component']
        elif record['kind'] == 'trace':
            plan = dict(item['construction']['extract'], source_sha256=data['source']['sha256'],
                        context_bbox=item['bbox'], observation=item['construction']['observation'])
            if (evidence['source_sha256'] != sha(source) or evidence['source_bbox'] != record['source_bbox']
                    or evidence['plan_sha256'] != hashlib.sha256(json.dumps(plan, sort_keys=True).encode()).hexdigest()):
                raise ValueError(item['id'] + ': candidate source/recipe binding changed')
            for key, expected in evidence['outputs_sha256'].items():
                if sha(path.parent / (key + '.png')) != expected:
                    raise ValueError(item['id'] + ': prepared support bytes changed')
        elif record['kind'] == 'svg':
            asset = _bound_file(prepared, record['asset'])
            if sha(asset) != item['construction']['asset']['sha256']:
                raise ValueError(item['id'] + ': SVG differs from source observation')
    # Extraction was already completed. Its separate interpreter is not required
    # during build, but the trace worker and PPTX dependencies are.
    runtime = runtime_check(data, node=node, extract_python=receipt['runtime']['extract_python'], check_extraction=False)
    output.mkdir(parents=True)
    try:
        artifact = output / Path(data['targets'][0]['path']).name
        width = data['construction']['slide_width_inches']
        frame = SourceFrame((0, 0, data['source']['width'], data['source']['height']),
            (0, 0, width, width*data['source']['height']/data['source']['width']))
        nodes = []
        # The frozen manifest retains its original bytes. Resolve source reads in
        # a runtime copy so sampled Paint cannot accidentally read a sibling run.
        drawing_manifest = copy.deepcopy(frozen_manifest)
        drawing_manifest['source']['path'] = str(source)
        if field_components:
            drawing_manifest['native_components']=[field_components.get(c['id'],c)
                                                   for c in data['native_components']]
        component_builder=None
        if drawing_manifest.get('native_components'):
            from native_components import ManifestComponentBuilder
            component_builder=ManifestComponentBuilder(drawing_manifest,base_dir=prepared)
        for index, (item, record) in enumerate(zip(data['source_inventory'], records)):
            recipe, bbox = item['construction'], item['bbox']
            kind = recipe['kind']
            if kind == 'trace':
                bbox = record['source_bbox']
                evidence_path = prepared / record['candidate']['path']
                evidence = read_json(evidence_path)
                options = recipe['trace']
                part_plan = dict(part_id=item['id'], observation=recipe['observation'],
                    source_sha256=data['source']['sha256'], source_bbox=bbox,
                    max_native_paths=options['max_native_paths'], max_native_commands=options['max_native_commands'])
                svg = output / f'item-{index:04d}.svg'
                if recipe['extract']['method']=='closed_form':
                    paint_input={'source_layer':dict(path=str(evidence_path),sha256=sha(evidence_path))}
                else:
                    paint_input={'source_support':dict(path=str(evidence_path.parent/'alpha.png'),
                        sha256=evidence['outputs_sha256']['alpha'],observation=recipe['observation'])}
                trace_component(source, svg, bbox, colors=options['colors'], node=runtime['node'],
                    representation=options['representation'], part_plan=part_plan, support_paint='source',**paint_input)
                draw = svg_draw(svg, expected_sha256=sha(svg))
            elif kind == 'svg':
                draw = svg_draw(_bound_file(prepared, record['asset']), expected_sha256=record['asset']['sha256'])
            elif kind == 'text':
                bbox = recipe.get('frame_bbox', bbox)
                draw = text_draw(item['text'], **recipe['options'])
            elif kind == 'native_component':
                draw = manifest_component_draw(component_builder, item['id'], base_dir=prepared)
            elif kind == 'picture':
                instance = next(i for i in drawing_manifest['component_instances'] if i['instance_id'] == item['component_instance'])
                asset = next(a for a in drawing_manifest['component_assets'] if a['asset_id'] == instance['asset_id'])
                draw = picture_draw(prepared / asset['path'], expected_sha256=asset['sha256'],
                                    crop=instance['crop'], rotation=instance['rotation'])
            elif kind == 'rect_link':
                draw = RectLink(**recipe['options'])
            else:
                draw = rectangle_draw(**recipe['options'])
            role = 'relation' if item['role'] == 'connector' else ('text' if kind == 'text' else 'component')
            if recipe.get('container'):
                role = 'container'
            nodes.append(SceneNode(item['id'], bbox, draw, role, recipe.get('parent'),
                recipe.get('behind', ()), recipe.get('z', 0), recipe.get('endpoints')))
        deck = Presentation()
        deck.slide_width, deck.slide_height = Inches(frame.viewport[2]), Inches(frame.viewport[3])
        scene_receipt = assemble_pptx(deck.slides.add_slide(deck.slide_layouts[6]),
                                    ReconstructionScene(frame, nodes, _editing_groups(data['construction'])))
        stream = io.BytesIO()
        deck.save(stream)
        payload = stream.getvalue()
        reopened = Presentation(io.BytesIO(payload))
        actual = list(reopened.slides[0].shapes)
        if [s.name for s in actual] != scene_receipt['top_level_paint_order']:
            raise ValueError('saved shape inventory/order mismatch')
        def walk(shapes):
            for shape in shapes:
                yield shape
                if hasattr(shape, 'shapes'):
                    yield from walk(shape.shapes)
        actual_by = {s.name: s for s in walk(actual)}
        resolved = copy.deepcopy(drawing_manifest)
        resolved['source']['path'] = str(source)
        if data['construction']['version'] >= 4:
            portable = _stage_component_inputs(frozen_manifest, prepared, output)
            resolved['source'] = portable['source']
            if 'component_assets' in portable:
                resolved['component_assets'] = portable['component_assets']
        resolved['targets'] = [{'format': 'pptx', 'path': str(artifact)}]
        for item in resolved['source_inventory']:
            item.update(output_name=item['id'], output_id=str(actual_by[item['id']].shape_id), output_slide=1)
            if item['role'] == 'text' and actual_by[item['id']].text != item['text']:
                raise ValueError(item['id'] + ': saved text mismatch')
        expected = []
        for item in data['source_inventory']:
            if item['construction']['kind'] != 'rect_link':
                continue
            source_id, target_id = item['construction']['endpoints']
            connector = actual_by[item['id']]
            for tag, identity in (('stCxn', source_id), ('endCxn', target_id)):
                bindings = connector._element.xpath('./p:nvCxnSpPr/p:cNvCxnSpPr/a:' + tag)
                if len(bindings) != 1 or bindings[0].get('id') != str(actual_by[identity].shape_id):
                    raise ValueError(item['id'] + ': saved connector binding disagrees with exact source/target ID')
            expected.append({'slide': 1, 'name': item['id'], 'source': source_id, 'target': target_id,
                             'start_arrow': 'none', 'end_arrow': 'triangle'})
        with artifact.open('xb') as target:
            target.write(payload)
        write_json(output / 'resolved-manifest.json', resolved)
        expected_path = None
        if expected:
            expected_path = output / 'expected-connections.json'
            write_json(expected_path, expected)
        scene_receipt.update(artifact_sha256=sha(artifact), artifact=artifact.name,
            prepared_sha256=sha(prepared / 'prepared.json'), runtime=runtime,
            status='CANDIDATE', visual_review='NOT_PERFORMED', editor_review='NOT_PERFORMED')
        quality = load('run-quality-checks').run_checks(artifact, output / 'resolved-manifest.json',
                                                     expected_path=expected_path, node=runtime['node'])
        write_json(output / 'quality-report.json', quality)
        scene_receipt.update(automation_passed=quality['automation_passed'], delivery_ready=None,
            pending_checks=[c['check'] for c in quality['checks'] if c['status'] in ('FAIL', 'NOT_VERIFIED')])
        write_json(output / 'build-receipt.json', scene_receipt)
        return scene_receipt
    except Exception as exc:
        write_json(output / 'failure.json', {'status': 'FAILED', 'phase': 'build', 'error': str(exc)})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    measurement = sub.add_parser('measure-text', help='Optional local source-ink/font advice; never changes the manifest')
    measurement.add_argument('input', type=Path)
    measurement.add_argument('output', type=Path)
    measurement.add_argument('--font-file', type=Path)
    measurement.add_argument('--context-padding-px', type=int, default=0, help='Optional source context around text boxes; does not change placement')
    measurement.add_argument('--item', action='append', dest='item_ids', help='Measure selected source text ID; repeat for multiple IDs')
    revision = sub.add_parser('revise-text', help='Create a canonical revision from reviewed text changes')
    revision.add_argument('input', type=Path)
    revision.add_argument('changes', type=Path)
    revision.add_argument('output', type=Path)
    for command in ('doctor', 'prepare', 'build'):
        p = sub.add_parser(command)
        p.add_argument('input', type=Path)
        if command != 'doctor':
            p.add_argument('output', type=Path)
        p.add_argument('--node')
        if command != 'build':
            p.add_argument('--extract-python')
        else:
            p.add_argument('--review', type=Path)
    args = parser.parse_args()
    try:
        if args.command == 'revise-text':
            changed = revise_text(args.input, args.changes, args.output)
            print(json.dumps({'status': 'REVISED_INPUT', 'manifest': str(args.output), 'changed_ids': changed}, ensure_ascii=False))
            return 0
        if args.command == 'measure-text':
            from source_text_metrics import measure_manifest
            result = measure_manifest(args.input, args.output, font_file=args.font_file, item_ids=args.item_ids,
                                      context_padding_px=args.context_padding_px)
            print(json.dumps({'status': 'ADVISORY', 'report': str(args.output / 'measurements.json'),
                              'overview': str(args.output / 'overview.png'), 'manifest_modified': False}))
            return 0
        elif args.command == 'doctor':
            result = runtime_check(checked_manifest(args.input), node=args.node, extract_python=args.extract_python)
        elif args.command == 'prepare':
            result = prepare(args.input, args.output, node=args.node, extract_python=args.extract_python)
        else:
            result = build(args.input, args.output, review=args.review, node=args.node)
        print(json.dumps({'status': result.get('status', 'RUNTIME_AVAILABLE'),
                          'items': len(result.get('items', [])), 'visual_review': 'NOT_PERFORMED',
                          'automation_passed': result.get('automation_passed'),
                          'pending_checks': result.get('pending_checks', []), 'delivery_ready': None}))
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print(json.dumps({'status': 'FAILED', 'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
