"""Local, manifest-bound component construction; no model or network calls.

Given source alpha is evidence, not a segmentation prediction. Diagnostic layer
previews are explicitly partial and never replace the target application's render.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import io
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image

MAX_PIXELS = 16_000_000
MAX_COMPONENT_PIXELS = 4_000_000


def digest(data):
    return hashlib.sha256(data).hexdigest()


def validate_preparation(asset):
    p = asset.get('preparation')
    if 'preparation' not in asset:
        return []
    errors = []
    if asset.get('source_kind') != 'source_crop':
        errors.append('preparation requires source_crop provenance')
    if not isinstance(p, dict):
        return errors + ['preparation must be an object']
    common = {'method', 'authorization'}
    method = p.get('method')
    if method == 'preserve-alpha':
        expected = common
    elif method == 'supplied-alpha':
        expected = common | {'alpha_path', 'alpha_sha256', 'rgb_mode'}
        if p.get('rgb_mode') == 'matted':
            expected |= {'matte_rgb'}
            matte = p.get('matte_rgb')
            if not isinstance(matte, list) or len(matte) != 3 or any(type(v) is not int or not 0 <= v <= 255 for v in matte):
                errors.append('matte_rgb must be three 8-bit integers')
        elif p.get('rgb_mode') != 'straight':
            errors.append('rgb_mode must be straight or matted')
        h = p.get('alpha_sha256')
        if not isinstance(h, str) or len(h) != 64 or any(c not in '0123456789abcdef' for c in h):
            errors.append('invalid alpha_sha256')
        if not isinstance(p.get('alpha_path'), str) or not p['alpha_path'].strip():
            errors.append('alpha_path required')
    else:
        return errors + ['unsupported preparation method']
    if set(p) != expected:
        errors.append('unexpected or missing preparation fields')
    if not isinstance(p.get('authorization'), str) or not p['authorization'].strip():
        errors.append('local preparation authorization required')
    return errors


def read_image(path, expected_hash=None, *, alpha=False):
    data = Path(path).read_bytes()
    if expected_hash is not None and digest(data) != expected_hash:
        raise ValueError('source/asset hash mismatch: ' + str(path))
    with Image.open(io.BytesIO(data)) as im:
        if im.width * im.height > MAX_PIXELS or getattr(im, 'n_frames', 1) != 1:
            raise ValueError('image size/frame limit exceeded')
        if im.info.get('icc_profile') or im.getexif().get(274, 1) != 1:
            raise ValueError('qualify ICC/EXIF orientation before component processing')
        if im.mode not in (('L',) if alpha else ('RGB', 'RGBA')):
            raise ValueError('alpha requires L; color requires RGB or straight RGBA')
        im.load()
        return im.copy()


def _assets():
    import component_assets
    return component_assets


def _contract(manifest):
    errors = _assets().validate_contract(manifest)
    if errors:
        raise ValueError('; '.join(errors))
    if manifest.get('editing_policy') != 'hybrid':
        raise ValueError('component construction requires explicit hybrid scope')


def _asset(manifest, asset_id):
    matches = [a for a in manifest.get('component_assets', []) if a.get('asset_id') == asset_id]
    if len(matches) != 1:
        raise ValueError('asset_id must resolve exactly once')
    return matches[0]


def prepare_asset(manifest, asset_id, base):
    """Return PNG bytes, copied canonical manifest and diagnostic metrics; no writes.

    Target sha256 is computed before contract validation (a planned target may
    omit it). Other assets still need valid records. No crop trimming/resampling.
    """
    base = Path(base)
    candidate = copy.deepcopy(manifest)
    asset = _asset(candidate, asset_id)
    errors = validate_preparation(asset)
    if errors or asset.get('preparation') is None:
        raise ValueError('; '.join(errors) or 'preparation required')
    # Validate authorization/inventory before opening source files.
    asset['sha256'] = '0' * 64
    _contract(candidate)
    source = read_image(base / candidate['source']['path'], asset['source_sha256'])
    if list(source.size) != [candidate['source']['width'], candidate['source']['height']]:
        raise ValueError('source dimensions differ from manifest')
    box = asset['source_bbox']
    if any(type(v) is not int for v in box):
        raise ValueError('preparation source_bbox must be integer [x,y,width,height]')
    x, y, w, h = box
    if x+w > source.width or y+h > source.height or w*h > MAX_COMPONENT_PIXELS:
        raise ValueError('component crop exceeds source/processing limit')
    out = source.crop((x, y, x+w, y+h)).convert('RGBA')
    p = asset['preparation']
    metrics = {'method': p['method'], 'source_bbox': box, 'size': [w, h],
               'alpha_inferred': False, 'hidden_content_generated': False,
               'semantic_identity': 'NOT_VERIFIED', 'visual_fidelity': 'NOT_VERIFIED'}
    if p['method'] == 'supplied-alpha':
        if out.getextrema()[3] != (255, 255):
            raise ValueError('supplied alpha requires opaque source; cannot apply alpha twice')
        alpha = read_image(base / p['alpha_path'], p['alpha_sha256'], alpha=True)
        if alpha.size != (w, h):
            raise ValueError('alpha must exactly match source crop; no resizing')
        a = np.asarray(alpha, dtype=np.float64) / 255.
        rgb = np.asarray(out, dtype=np.float64)[:, :, :3].copy()
        visible = a > 0
        if p['rgb_mode'] == 'matted':
            # Invert C = alpha * F + (1-alpha) * B only when B and alpha are given.
            # Account for <= half a channel level of source 8-bit quantization.
            background = np.array(p['matte_rgb'], dtype=np.float64)
            av = a[visible, None]
            foreground = (rgb[visible] - (1-av)*background) / av
            tolerance = .5000001 / av
            if np.any(foreground < -tolerance) or np.any(foreground > 255+tolerance):
                raise ValueError('alpha/matte incompatible with source colors; no silent clipping')
            metrics['quantization_clamped_channels'] = int(((foreground < 0) | (foreground > 255)).sum())
            rgb[visible] = np.rint(np.clip(foreground, 0, 255))
            recomposed = rgb[visible]*av + (1-av)*background
            observed = np.asarray(out, dtype=np.float64)[:, :, :3][visible]
            metrics['visible_roundtrip_max_channel_error'] = float(np.max(np.abs(recomposed-observed), initial=0))
        rgb[~visible] = 0
        rgba = np.dstack((rgb, np.asarray(alpha))).astype(np.uint8)
        out = Image.fromarray(rgba)
    if out.getchannel('A').getbbox() is None:
        raise ValueError('component is fully transparent')
    if asset['requires_alpha'] and out.getextrema()[3] == (255, 255):
        raise ValueError('required transparency absent; no background removal was performed')
    buffer = io.BytesIO()
    out.save(buffer, format='PNG')
    data = buffer.getvalue()
    asset['sha256'] = digest(data)
    _contract(candidate)
    return data, candidate, metrics


def verify_preparation(manifest, asset_id, base, actual_data):
    expected, _, _ = prepare_asset(manifest, asset_id, base)
    with Image.open(io.BytesIO(expected)) as a, Image.open(io.BytesIO(actual_data)) as b:
        if b.mode != 'RGBA' or a.size != b.size or a.tobytes() != b.tobytes():
            raise ValueError('prepared component pixels differ from bound source recipe')


def replace_instance_asset(manifest, instance_id, new_asset, base):
    """Copy-on-write binding: one instance changes; shared users stay unchanged.

    Caller supplies the full approved replacement asset record, including new
    provenance. This does not edit PPTX bytes or establish biological equivalence.
    """
    _contract(manifest)
    candidate = copy.deepcopy(manifest)
    instances = [i for i in candidate['component_instances'] if i['instance_id'] == instance_id]
    if len(instances) != 1 or not isinstance(new_asset, dict):
        raise ValueError('replacement instance/asset invalid')
    old = _asset(candidate, instances[0]['asset_id'])
    if new_asset.get('asset_id') in {a['asset_id'] for a in candidate['component_assets']}:
        raise ValueError('replacement requires a fresh asset_id; shared assets are immutable')
    candidate['component_assets'].append(copy.deepcopy(new_asset))
    instances[0]['asset_id'] = new_asset.get('asset_id')
    used = {i['asset_id'] for i in candidate['component_instances']}
    candidate['component_assets'] = [a for a in candidate['component_assets'] if a['asset_id'] in used]
    _contract(candidate)
    before = read_image(Path(base)/old['path'], old['sha256'])
    after = read_image(Path(base)/new_asset['path'], new_asset['sha256'])
    if before.width * after.height != before.height * after.width:
        raise ValueError('replacement aspect ratio changed; replan placement explicitly')
    if new_asset.get('preparation'):
        verify_preparation(candidate, new_asset['asset_id'], base, (Path(base)/new_asset['path']).read_bytes())
    return candidate


def render_components(manifest, base, order, *, canvas_inches, dpi=96, background=(255, 255, 255)):
    """Partial raster-component preview only, with explicit back-to-front order.

    Orthogonal unrotated uncropped instances only. Native text/paths/relations are
    not rendered here. Existing target renderer remains the final authority.
    """
    _contract(manifest)
    if not isinstance(order, list) or not order or any(not isinstance(i, str) for i in order) or len(set(order)) != len(order):
        raise ValueError('unique explicit instance order required')
    if not isinstance(canvas_inches, (list, tuple)) or len(canvas_inches) != 2 or any(isinstance(v, bool) or not isinstance(v, (float, int)) or not math.isfinite(v) or v <= 0 for v in canvas_inches):
        raise ValueError('positive canvas_inches required')
    if type(dpi) is not int or not 1 <= dpi <= 600:
        raise ValueError('dpi must be 1..600')
    if not isinstance(background, (list, tuple)) or len(background) != 3 or any(type(v) is not int or not 0 <= v <= 255 for v in background):
        raise ValueError('background must be three 8-bit values')
    width, height = [round(v*dpi) for v in canvas_inches]
    if min(width, height) < 1 or width*height > MAX_PIXELS:
        raise ValueError('preview canvas processing limit exceeded')
    canvas = Image.new('RGBA', (width, height), tuple(background)+(255,))
    by_id = {i['instance_id']: i for i in manifest['component_instances']}
    if any(i not in by_id for i in order) or len({by_id[i]['slide'] for i in order}) != 1:
        raise ValueError('all selected instances must exist on one slide')
    for iid in order:
        instance = by_id[iid]
        if instance['rotation'] != 0 or instance['crop'] != [0, 0, 0, 0]:
            raise ValueError('preview does not support rotation/crop; use target renderer')
        asset = _asset(manifest, instance['asset_id'])
        image = read_image(Path(base)/asset['path'], asset['sha256']).convert('RGBA')
        x, y, w, h = instance['bbox_inches']
        if x+w > canvas_inches[0] or y+h > canvas_inches[1]:
            raise ValueError('preview instance outside canvas')
        if abs((w/h)/(image.width/image.height)-1) > 1e-6:
            raise ValueError('preview would distort component aspect ratio')
        left, top, right, bottom = [round(v*dpi) for v in (x, y, x+w, y+h)]
        if min(right-left, bottom-top) < 1:
            raise ValueError('component subpixel at requested preview dpi')
        # Premultiplied-alpha resampling avoids interpolation of hidden RGB into edges.
        image = image.convert('RGBa').resize((right-left, bottom-top), Image.Resampling.LANCZOS).convert('RGBA')
        canvas.alpha_composite(image, (left, top))
    return canvas, {'scope': 'PARTIAL_COMPONENT_PREVIEW', 'order': order,
                    'background': list(background), 'native_objects_rendered': False,
                    'delivery_ready': None}


def _write_new(path, data):
    with Path(path).open('xb') as stream:
        stream.write(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    prep = sub.add_parser('prepare')
    prep.add_argument('--manifest', type=Path, required=True)
    prep.add_argument('--asset-id', required=True)
    prep.add_argument('--out-manifest', type=Path, required=True)
    replace = sub.add_parser('replace')
    replace.add_argument('--manifest', type=Path, required=True)
    replace.add_argument('--instance-id', required=True)
    replace.add_argument('--asset-record', type=Path, required=True)
    replace.add_argument('--out-manifest', type=Path, required=True)
    preview = sub.add_parser('preview')
    preview.add_argument('--manifest', type=Path, required=True)
    preview.add_argument('--order', nargs='+', required=True)
    preview.add_argument('--canvas-inches', nargs=2, type=float, required=True)
    preview.add_argument('--background', nargs=3, type=int, default=[255, 255, 255])
    preview.add_argument('--dpi', type=int, default=96)
    preview.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
        base = args.manifest.resolve().parent
        if args.command in ('prepare', 'replace'):
            if args.out_manifest.resolve().parent != base or args.out_manifest.exists():
                raise ValueError('candidate manifest must be a new sibling of source manifest')
        if args.command == 'prepare':
            data, candidate, report = prepare_asset(manifest, args.asset_id, base)
            target = (base/_asset(candidate, args.asset_id)['path']).resolve()
            if not target.is_relative_to(base) or target.exists() or not target.parent.is_dir() or target == args.out_manifest.resolve():
                raise ValueError('target must be a new file inside existing workspace directory')
            _write_new(target, data)
            _write_new(args.out_manifest, json.dumps(candidate, ensure_ascii=False, indent=2).encode('utf-8'))
        elif args.command == 'replace':
            new_asset = json.loads(args.asset_record.read_text(encoding='utf-8'))
            candidate = replace_instance_asset(manifest, args.instance_id, new_asset, base)
            _write_new(args.out_manifest, json.dumps(candidate, ensure_ascii=False, indent=2).encode('utf-8'))
            report = {'scope': 'CANONICAL_INSTANCE_BINDING', 'instance_id': args.instance_id,
                      'asset_id': new_asset['asset_id'], 'pptx_regenerated': False,
                      'visual_fidelity': 'NOT_VERIFIED'}
        else:
            image, report = render_components(manifest, base, args.order, canvas_inches=args.canvas_inches, dpi=args.dpi, background=args.background)
            buffer = io.BytesIO(); image.save(buffer, format='PNG')
            _write_new(args.output, buffer.getvalue())
        print(json.dumps(report, ensure_ascii=False))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(2, str(exc)+'\n')


if __name__ == '__main__':
    main()
