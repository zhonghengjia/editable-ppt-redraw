"""Source-crop tracing and final-render regional checks; never semantic sign-off."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

import component_geometry as geometry

SCRIPTS = Path(__file__).resolve().parent
MAX_PIXELS = 1_000_000


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def unit(value):
    return isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value) and 0 <= value < 1


def integers(value, count):
    return isinstance(value, list) and len(value) == count and all(type(v) is int for v in value)


def validate_contract(manifest):
    """Only this function defines regional_fidelity schema and coverage rules."""
    errors = []
    inventory = manifest.get('source_inventory', [])
    inventory = inventory if isinstance(inventory, list) else []
    sensitive = set()
    structural = set()
    for item in inventory:
        if not isinstance(item, dict):
            continue
        if 'fidelity_sensitive' in item and type(item['fidelity_sensitive']) is not bool:
            errors.append('fidelity_sensitive must be boolean')
        if item.get('fidelity_sensitive') is True and isinstance(item.get('id'), str):
            sensitive.add(item['id'])
        if 'structure_sensitive' in item and type(item['structure_sensitive']) is not bool:
            errors.append('structure_sensitive must be boolean')
        if item.get('structure_sensitive') is True and isinstance(item.get('id'), str):
            sensitive.add(item['id'])
            structural.add(item['id'])
    contract = manifest.get('regional_fidelity')
    if contract is None:
        return errors + (['regional_fidelity required for fidelity_sensitive items'] if sensitive else [])
    if not isinstance(contract, dict):
        return errors + ['regional_fidelity must be an object']
    if manifest.get('mode') != 'faithful':
        errors.append('regional_fidelity requires faithful mode with unchanged composition')
    dimensions = contract.get('source_size')
    if not integers(dimensions, 2) or min(dimensions) <= 0:
        errors.append('source_size must contain two positive pixel integers')
        dimensions = None
    if not isinstance(contract.get('source_sha256'), str) or len(contract['source_sha256']) != 64 or any(c not in '0123456789abcdef' for c in contract['source_sha256']):
        errors.append('source_sha256 must be lowercase SHA256')
    regions = contract.get('regions')
    if not isinstance(regions, list) or not regions or len(regions) > 100:
        return errors + ['regions must contain 1..100 objects']
    seen = set()
    known = {item.get('id') for item in inventory if isinstance(item, dict) and isinstance(item.get('id'), str)}
    for region in regions:
        if not isinstance(region, dict):
            errors.append('region must be an object')
            continue
        identity = region.get('id')
        if not isinstance(identity, str) or identity not in known or identity in seen:
            errors.append('each region id must identify a unique source_inventory item')
        else:
            seen.add(identity)
        box = region.get('source_bbox')
        if not integers(box, 4) or min(box[:2]) < 0 or min(box[2:]) < 1:
            errors.append(f'{identity}: invalid source_bbox')
            box = None
        elif box[2] * box[3] > MAX_PIXELS or max(box[2:]) > 4096 or (dimensions and (box[0]+box[2] > dimensions[0] or box[1]+box[3] > dimensions[1])):
            errors.append(f'{identity}: source_bbox outside image or component limits')
        for name in ('threshold', 'max_mismatch_ratio', 'max_window_ratio'):
            if not unit(region.get(name)):
                errors.append(f'{identity}: {name} must be finite in 0..<1')
        window = region.get('window')
        if type(window) is not int or window < 1 or (box and window > min(box[2:])):
            errors.append(f'{identity}: window must fit source_bbox')
        if not isinstance(region.get('rationale'), str) or not region['rationale'].strip():
            errors.append(f'{identity}: record source-based thresholds rationale before authoring')
        features = region.get('features')
        if not isinstance(features, list) or not features or not all(isinstance(f, str) and f.strip() for f in features):
            errors.append(f'{identity}: features must record nonempty visual invariants')
        if 'structure' in region:
            errors.extend(f'{identity}: {error}' for error in geometry.validate_structure(region['structure']))
        elif isinstance(identity, str) and identity in structural:
            errors.append(f'{identity}: structure_sensitive item requires a structure contract')
    if sensitive - seen:
        errors.append('sensitive items lack regions: ' + ', '.join(sorted(sensitive - seen)))
    return errors


def worker(request, node=None):
    executable = node or shutil.which('node')
    if not executable:
        raise FileNotFoundError('Node.js unavailable; supply --node, do not silently skip')
    proc = subprocess.run([str(executable), str(SCRIPTS/'component-worker.mjs')],
                          input=json.dumps(request), capture_output=True, text=True,
                          encoding='utf-8', timeout=60, check=False)
    if proc.returncode:
        raise ValueError('component worker failed: ' + proc.stderr[-2000:])
    return json.loads(proc.stdout)


def rgba(image):
    return base64.b64encode(image.convert('RGBA').tobytes()).decode('ascii')


def read_image(path):
    from PIL import Image
    with Image.open(path) as image:
        if image.width * image.height > 40_000_000 or getattr(image, 'n_frames', 1) != 1:
            raise ValueError('single-frame source/render up to 40 million pixels required')
        return image.convert('RGBA')


def fresh_json(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)


def source_palette(image, colors):
    """Use actual colors when possible; Pillow octree otherwise, never sparse grid seeds."""
    from PIL import Image
    if type(colors) is not int or not 2 <= colors <= 64:
        raise ValueError('colors must be 2..64')
    entries = image.getcolors(colors)
    basis = 'all_observed_rgba_colors'
    if entries is None:
        entries = image.quantize(colors, method=Image.Quantize.FASTOCTREE,
                                 dither=Image.Dither.NONE).convert('RGBA').getcolors(colors)
        basis = 'Pillow_FASTOCTREE_RGBA_no_dither'
    palette = [dict(zip(('r','g','b','a'), color)) for color in sorted(color for _,color in entries)]
    return palette, basis


def recipe_digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',',':'),
                                     ensure_ascii=False, allow_nan=False).encode('utf-8')).hexdigest()


def prepare_support(cropped, selector, ownership, source_hash, crop):
    """One source-only extraction stage; representation and output QA are separate."""
    import numpy as np
    from PIL import Image
    mask = geometry.select(cropped, selector)
    if not mask.any() or mask.all():
        raise ValueError('selector must isolate nonempty visible support from background; review the source crop')
    selection = dict(selector=selector, selector_sha256=recipe_digest(selector),
                     input_mask_sha256=hashlib.sha256(mask.tobytes()).hexdigest())
    if ownership is not None:
        mask, evidence = geometry.owned_support(mask, ownership, source_hash, crop, selection['selector_sha256'])
        evidence['recipe_sha256'] = recipe_digest(ownership)
        selection['ownership'] = evidence
    visible = Image.alpha_composite(Image.new('RGBA',cropped.size,'white'),cropped)
    fill = np.median(np.asarray(visible)[:,:,:3][mask],axis=0).astype('uint8').tolist()
    pixels = np.zeros((cropped.height,cropped.width,4),dtype='uint8')
    pixels[mask] = fill+[255]
    selection.update(mask_sha256=hashlib.sha256(mask.tobytes()).hexdigest(),
        mask_encoding='row_major_bool_uint8', matte='white', topology=geometry.topology(mask),
        foreground_rgb=fill, representation='visible_support_uniform_median_fill',
        limitations=['No hidden surface inference or occlusion repair',
                     'Foreground labels may create real mask holes; no automatic filling',
                     'Source gradient intentionally not reconstructed by this silhouette candidate'])
    return Image.fromarray(pixels), selection


def validate_part_plan(plan, source_hash, crop):
    """Source-bound edit granularity and budget, selected before representation."""
    required = {'part_id', 'observation', 'source_sha256', 'source_bbox',
                'max_native_paths', 'max_native_commands'}
    if not isinstance(plan, dict) or set(plan) != required:
        raise ValueError('part plan requires identity, source binding, observation and two native budgets')
    for key in ('part_id', 'observation'):
        if not isinstance(plan[key], str) or not plan[key].strip() or len(plan[key]) > 2000:
            raise ValueError('part plan identity/observation must be nonempty bounded text')
    if not integers(plan['source_bbox'], 4) or plan['source_bbox'] != crop or plan['source_sha256'] != source_hash:
        raise ValueError('part plan source hash/crop mismatch')
    for key in ('max_native_paths', 'max_native_commands'):
        if type(plan[key]) is not int or not 1 <= plan[key] <= 1_000_000:
            raise ValueError('part plan budgets must be positive bounded integers')


def prepare_partition(cropped, colors):
    """Quantize once; pass these exact colors, not just a palette for a second map."""
    import numpy as np
    from PIL import Image
    prepared = cropped
    basis = 'all_observed_rgba_colors'
    if cropped.getcolors(colors) is None:
        prepared = cropped.quantize(colors, method=Image.Quantize.FASTOCTREE,
                                     dither=Image.Dither.NONE).convert('RGBA')
        basis = 'Pillow_FASTOCTREE_RGBA_no_dither'
    white = Image.new('RGBA', cropped.size, 'white')
    before = np.asarray(Image.alpha_composite(white, cropped))[:,:,:3].astype('float64')
    after = np.asarray(Image.alpha_composite(white, prepared))[:,:,:3].astype('float64')
    error = np.abs(after - before)
    return prepared, basis, dict(prepared_rgba_sha256=hashlib.sha256(prepared.tobytes()).hexdigest(),
        source_rgba_sha256=hashlib.sha256(cropped.tobytes()).hexdigest(),
        colors=len(prepared.getcolors(64)), matte='white',
        mean_absolute_rgb_error=float(error.mean()), max_rgb_error=float(error.max()),
        changed_pixels=int(np.any(error != 0, axis=2).sum()), fidelity_verified=False)


def normalized_trace_svg(result, representation):
    """Keep all visual attributes; only normalize known generator metadata."""
    ET.register_namespace('', 'http://www.w3.org/2000/svg')
    root = ET.fromstring(result['svg'])
    root.attrib.pop('desc', None)
    for index, path in enumerate(root):
        if path.tag != '{http://www.w3.org/2000/svg}path':
            raise ValueError('unexpected tracer element')
        prefix = {'source_edges':'support-path', 'palette_edges':'paint-path', 'palette_stack':'paint-path', 'smooth':'color-region'}[representation]
        path.set('id', f'{prefix}-{index+1:04}')
        if 'opacity' in path.attrib:
            opacity = path.attrib.pop('opacity')
            path.set('fill-opacity', opacity)
            path.set('stroke-opacity', opacity)
    svg = ET.tostring(root, encoding='utf-8', xml_declaration=True)
    paths = list(root)
    return svg, dict(svg_bytes=len(svg), xml_elements=sum(1 for _ in root.iter()),
        svg_paths=len(paths), max_path_chars=max((len(p.get('d','')) for p in paths), default=0),
        serialized_commands=sum(len(re.findall(r'[MLHVCSQTAZmlhvcsqtaz]',p.get('d',''))) for p in paths))


def trace_component(source, output, crop, colors=16, node=None, selector=None,
                    ownership=None, representation=None, part_plan=None):
    source, output = Path(source), Path(output)
    sidecar = output.with_suffix('.trace.json')
    failure = output.with_suffix('.trace.failed.json')
    if output.exists() or sidecar.exists() or failure.exists() or output.suffix.lower() != '.svg':
        raise ValueError('choose new .svg and trace evidence output paths')
    image = read_image(source)
    if not integers(crop, 4) or min(crop[:2]) < 0 or min(crop[2:]) < 1:
        raise ValueError('crop must be four pixel integers with positive size')
    x, y, w, h = crop
    if x+w > image.width or y+h > image.height or w*h > MAX_PIXELS or max(w,h) > 4096:
        raise ValueError('crop outside source or component limits')
    if type(colors) is not int or not 2 <= colors <= 64:
        raise ValueError('colors must be 2..64')
    if ownership is not None and selector is None:
        raise ValueError('ownership requires a source selector')
    if representation is None:
        representation = 'source_edges' if selector is not None else 'smooth'
    if representation not in ('source_edges','smooth','palette_edges','palette_stack') or (representation == 'source_edges' and selector is None):
        raise ValueError('representation must be smooth, source_edges with a selector, or palette_edges/palette_stack with a part plan')
    if representation in ('palette_edges','palette_stack') and (selector is not None or ownership is not None or part_plan is None):
        raise ValueError('palette representations require a source-bound part plan and no support selector/ownership')
    source_hash = digest(source)
    if part_plan is not None:
        validate_part_plan(part_plan, source_hash, crop)
    cropped = image.crop((x,y,x+w,y+h))
    selection = None
    if selector is not None:
        cropped, selection = prepare_support(cropped, selector, ownership, source_hash, crop)
    quantization = None
    if representation in ('palette_edges','palette_stack'):
        if representation == 'palette_stack' and any(cropped.getchannel('A').histogram()[1:255]):
            raise ValueError('palette_stack requires opaque source colors and binary alpha before quantization')
        cropped, palette_basis, quantization = prepare_partition(cropped, colors)
        palette = None
    elif representation == 'smooth':
        palette, palette_basis = source_palette(cropped, colors)
    else:
        palette, palette_basis = None, 'selected_support_uniform_source_fill_no_quantization'
    import native_vectors
    complexity = dict(native_profile='NOT_VERIFIED', budget_status='NOT_DECLARED')
    try:
        result = worker(dict(action='trace', width=w, height=h, representation=representation, colors=colors,
                             palette=palette, first=rgba(cropped), path_char_limit=native_vectors.MAX_PATH_CHARS), node)
        svg, measured = normalized_trace_svg(result, representation)
        complexity.update(measured)
        with tempfile.TemporaryDirectory() as folder:
            candidate = Path(folder)/'component.svg'
            candidate.write_bytes(svg)
            specs, _, _ = native_vectors.read_vectors(candidate)
        complexity.update(native_profile='PASS', native_paths=len(specs),
                          native_commands=sum(len(spec['commands']) for spec in specs))
        if part_plan is not None:
            complexity['budget_status'] = 'PASS'
            for key in ('native_paths','native_commands'):
                if complexity[key] > part_plan['max_'+key]:
                    complexity['budget_status'] = 'FAIL'
            if complexity['budget_status'] == 'FAIL':
                raise ValueError('source part exceeds declared native edit budget; packing does not simplify geometry')
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        if isinstance(exc, native_vectors.SVGProfileError):
            complexity['native_profile'] = 'FAIL'
        output.parent.mkdir(parents=True, exist_ok=True)
        fresh_json(failure, dict(status='FAIL', error=str(exc), source_sha256=source_hash,
            source_bbox=crop, representation=representation, part_plan=part_plan,
            complexity=complexity, quantization=quantization, candidate_emitted=False))
        raise
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('xb') as stream:
        stream.write(svg)
    record = dict(schema_version=2, source_sha256=source_hash, source_size=list(image.size),
                  source_bbox=crop, svg_sha256=digest(output), native_paths=len(specs),
                  native_commands=sum(len(spec['commands']) for spec in specs), representation=representation,
                  engine='ImageTracerJS 1.2.6', engine_sha256=digest(SCRIPTS/'vendor/imagetracer/imagetracer.cjs'),
                  options=result['options'], palette_basis=palette_basis, geometry_basis='source_pixel_color_regions',
                  practical_editability='NOT_VERIFIED',
                  complexity=complexity,
                  semantics_verified=False, final_artifact_verified=False,
                  limitations=['Source support is not semantic segmentation; source letters are not editable text',
                               'No hidden geometry inference; native path count does not prove practical editability'])
    if representation == 'smooth':
        record['limitations'].append('Palette reduction and independent curve fitting may lose rare features, holes or bridges and create seams')
    elif representation == 'source_edges':
        record['limitations'].append('Exact pixel-cell polygon edges retain source stair steps and can require many editable vertices; no subpixel curve inference')
    else:
        record.update(partition=result['partition'], quantization=quantization,
                      geometry_basis='single_source_palette_pixel_partition')
        record['limitations'].append('Palette partition preserves quantized cells, not original gradients or semantic parts; packing keeps every vertex')
    if part_plan is not None:
        record.update(part_plan=part_plan, part_plan_sha256=recipe_digest(part_plan))
    if selection is not None:
        record['selection'] = selection
        record['geometry_basis'] = 'source_visible_support_selector'
    else:
        record['limitations'].append('Crop background and unwanted source text remain present in color regions')
    fresh_json(sidecar, record)
    return record


def load_render_pair(artifact, manifest, manifest_path, evidence_path, contract, align=True):
    """Shared source/final-render provenance gate; never fit a transform to errors."""
    evidence_path = Path(evidence_path)
    evidence = json.loads(evidence_path.read_text(encoding='utf-8'))
    render = (evidence_path.parent/evidence['render_path']).resolve()
    source = (Path(manifest_path).parent/manifest['source']['path']).resolve()
    if not evidence.get('renderer') or evidence.get('rendered_from_final_artifact') is not True:
        raise ValueError('record renderer and final-artifact render assertion')
    for path, expected in ((artifact, evidence.get('artifact_sha256')), (render, evidence.get('render_sha256')),
                           (source, contract['source_sha256'])):
        if digest(path) != expected:
            raise ValueError('source/artifact/render hash mismatch')
    if Path(artifact).resolve() == render or source == render:
        raise ValueError('render must be a distinct final-artifact derivative')
    first, second = read_image(source), read_image(render)
    if list(first.size) != contract['source_size']:
        raise ValueError('source dimensions disagree with decoded pixels')
    w, h = first.size
    rw, rh = second.size
    if align:
        if rw < w or rh < h:
            raise ValueError('final render must be at least source resolution')
        if abs(rh-rw*h/w) > 1.0:
            raise ValueError('canvas aspect mismatch; no nonuniform registration permitted')
        from PIL import Image
        second = second.resize(first.size, Image.Resampling.LANCZOS)
    metadata = dict(alignment=dict(source_size=[w,h], render_size=[rw,rh],
                                   method='whole_canvas_size_only' if align else 'not_registered'),
                    artifact_sha256=digest(artifact), render_sha256=digest(render))
    return first, second, evidence, metadata


def audit_fidelity(artifact, manifest, manifest_path, evidence_path, node=None):
    errors = validate_contract(manifest)
    report = dict(valid=not errors, errors=errors, regions=[], unverified=[], semantic_review='NOT_VERIFIED')
    if errors:
        return report
    if 'regional_fidelity' not in manifest:
        report['unverified'].append('no regional_fidelity contract')
        return report
    if not evidence_path:
        report['unverified'].append('final render evidence required')
        return report
    try:
        contract = manifest['regional_fidelity']
        first, second, _, metadata = load_render_pair(artifact, manifest, manifest_path, evidence_path, contract)
        report.update(metadata)
        for region in contract['regions']:
            x,y,cw,ch = region['source_bbox']
            box = (x,y,x+cw,y+ch)
            metrics = worker(dict(action='compare', width=cw, height=ch,
                                  first=rgba(first.crop(box)), second=rgba(second.crop(box)),
                                  threshold=region['threshold'], window=region['window']), node)
            total = metrics['mismatch_pixels']/(cw*ch)
            worst = metrics['worst_window_pixels']/region['window']**2
            passed = total <= region['max_mismatch_ratio'] and worst <= region['max_window_ratio']
            entry = dict(id=region['id'], mismatch_ratio=total, worst_window_ratio=worst,
                         color_passed=passed, passed=passed, structure_status='NOT_DECLARED', **metrics)
            if 'structure' in region:
                try:
                    entry['structure'] = geometry.compare(first.crop(box),second.crop(box),region['structure'])
                    entry['structure_status'] = 'PASS' if entry['structure']['passed'] else 'FAIL'
                    entry['passed'] &= entry['structure']['passed']
                    if not entry['structure']['passed']:
                        errors.append(region['id'] + ': visible-support structure limits exceeded')
                except (geometry.GeometryLimit, ImportError) as exc:
                    entry['structure_status'] = 'NOT_VERIFIED'
                    entry['passed'] = False
                    report['unverified'].append(region['id'] + ': ' + str(exc))
            report['regions'].append(entry)
            if not passed:
                errors.append(region['id'] + ': regional fidelity limits exceeded')
        report['valid'] = not errors
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        report['unverified'].append(str(exc))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        errors.append(str(exc))
    report['valid'] = not errors
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    trace = sub.add_parser('trace')
    trace.add_argument('source', type=Path)
    trace.add_argument('output', type=Path)
    trace.add_argument('--crop', nargs=4, type=int, required=True)
    trace.add_argument('--colors', type=int, default=16)
    trace.add_argument('--node')
    trace.add_argument('--selector', type=Path, help='source-frozen visible-support RGB selector JSON; no automatic mask repair')
    trace.add_argument('--ownership', type=Path, help='source-bound connected-part witnesses JSON; unassigned support is recorded')
    trace.add_argument('--representation', choices=('smooth','source_edges','palette_edges','palette_stack'), help='default: source_edges for selected support; smooth for ordinary color crops')
    trace.add_argument('--part-plan', type=Path, help='source-bound part identity and predeclared native edit budget; required for palette_edges/palette_stack')
    audit = sub.add_parser('audit')
    audit.add_argument('artifact', type=Path)
    audit.add_argument('--manifest', type=Path, required=True)
    audit.add_argument('--render-evidence', type=Path, required=True)
    audit.add_argument('--node')
    audit.add_argument('--json', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.action == 'trace':
            selector = json.loads(args.selector.read_text(encoding='utf-8')) if args.selector else None
            ownership = json.loads(args.ownership.read_text(encoding='utf-8')) if args.ownership else None
            part_plan = json.loads(args.part_plan.read_text(encoding='utf-8')) if args.part_plan else None
            result = trace_component(args.source, args.output, args.crop, args.colors, args.node, selector,
                                     ownership, args.representation, part_plan)
        else:
            if args.json.exists():
                raise ValueError('choose a new report path')
            manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
            result = audit_fidelity(args.artifact, manifest, args.manifest, args.render_evidence, args.node)
            fresh_json(args.json, result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return int(result.get('valid') is False or bool(result.get('unverified')))
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        parser.exit(1, str(exc)+'\n')


if __name__ == '__main__':
    sys.exit(main())
