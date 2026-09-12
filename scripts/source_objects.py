"""Source-bound foreground candidates, not automatic semantic approval.

The context is a search area, never the final object crop. The result feeds the
existing source-partition or supplied-alpha routes after independent inspection.
Binary modes preserve RGB. Explicit closed_form layers use the separate coverage
and foreground estimator; no model loading, networking or hidden anatomy.
"""
from __future__ import annotations

import argparse
import io
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from component_geometry import MAX_PIXELS, label_regions, select
from raster_components import digest, read_image


def _box(value, size):
    if (not isinstance(value, list) or len(value) != 4
            or any(type(v) is not int for v in value)):
        raise ValueError('bbox requires integer [x,y,width,height]')
    x, y, w, h = value
    if min(x, y) < 0 or min(w, h) <= 0 or x+w > size[0] or y+h > size[1]:
        raise ValueError('bbox outside source')
    return x, y, w, h


def _points(values, box, label, required=False):
    if not isinstance(values, list) or len(values) > 1000 or (required and not values):
        raise ValueError(label + ' requires source-pixel seed list (at most 1000)')
    x, y, w, h = box
    result = []
    for point in values:
        if (not isinstance(point, list) or len(point) != 2
                or any(type(v) is not int for v in point)
                or not (x <= point[0] < x+w and y <= point[1] < y+h)):
            raise ValueError(label + ' seed outside context')
        result.append((point[0]-x, point[1]-y))
    return result


def _png(image):
    stream = io.BytesIO()
    image.save(stream, format='PNG')
    return stream.getvalue()


def _annotations(values, box, fg, bg):
    """Rasterize observed source marks, never modify the source or final mask.

    Values follow OpenCV's four labels. Unmarked pixels retain the existing color
    prior. Same-class hard marks dominate probable marks, independent of order;
    opposite-class overlaps are ambiguous and must be corrected at the source.
    """
    if not isinstance(values, list) or len(values) > 1000:
        raise ValueError('annotations requires at most 1000 source marks')
    _, _, w, h = box
    labels = np.full((h, w), 255, dtype=np.uint8)
    classes = {'background': 0, 'foreground': 1,
               'probable_background': 2, 'probable_foreground': 3}

    def merge(mask, code):
        existing = labels[mask]
        if np.any((existing != 255) & ((existing % 2) != (code % 2))):
            raise ValueError('conflicting foreground/background annotations')
        labels[mask] = np.minimum(existing, code)

    for mark in values:
        if not isinstance(mark, dict):
            raise ValueError('annotation must be an object')
        kind = mark.get('kind')
        required = {'kind', 'label', 'points', 'observation'} | ({'width'} if kind == 'stroke' else set())
        if set(mark) != required or kind not in ('stroke', 'polygon') or mark.get('label') not in classes:
            raise ValueError('invalid source annotation fields/kind/label')
        if not isinstance(mark['observation'], str) or not mark['observation'].strip():
            raise ValueError('annotation source observation required')
        points = _points(mark['points'], box, 'annotation', True)
        layer = Image.new('L', (w, h))
        draw = ImageDraw.Draw(layer)
        if kind == 'polygon':
            if len(set(points)) < 3:
                raise ValueError('annotation polygon needs three distinct points')
            draw.polygon(points, fill=255)
        else:
            width = mark['width']
            if type(width) is not int or width < 1 or width % 2 == 0 or width > min(w, h):
                raise ValueError('annotation stroke width must be positive odd source pixels within context')
            radius = width // 2
            if any(px-radius < 0 or py-radius < 0 or px+radius >= w or py+radius >= h for px, py in points):
                raise ValueError('annotation stroke extends outside context')
            if len(points) > 1:
                draw.line(points, fill=255, width=width, joint='curve')
            for px, py in points:
                if radius:
                    draw.ellipse((px-radius, py-radius, px+radius, py+radius), fill=255)
                else:
                    draw.point((px, py), fill=255)
        merge(np.asarray(layer) > 0, classes[mark['label']])
    for points, code in ((fg, 1), (bg, 0)):
        mask = np.zeros((h, w), dtype=bool)
        for px, py in points:
            mask[py, px] = True
        merge(mask, code)
    return labels


def extract_source_object(source, plan):
    """Return context mask, cropped alpha/RGBA bytes and measured evidence.

    Points/rectangles use original source pixels. `selector` reuses the existing
    color-support engine; `grabcut` is optional and requires installed OpenCV.
    Optional GrabCut annotations fix observed strokes/regions before inference.
    Reserved areas are measured, not erased. Disconnected intended parts each
    need a hard foreground witness. Results remain CANDIDATE.
    """
    common = {'source_sha256', 'context_bbox', 'foreground', 'background',
              'method', 'reserved_regions', 'observation'}
    if not isinstance(plan, dict):
        raise ValueError('plan must be an object')
    required = common | ({'selector'} if plan.get('method') == 'selector' else
                         {'matting'} if plan.get('method') == 'closed_form' else set())
    optional = {'annotations'} if plan.get('method') in ('grabcut','closed_form') else set()
    if plan.get('method') == 'closed_form': optional |= {'occlusions'}
    if not required <= set(plan) or set(plan) - required - optional or plan.get('method') not in ('selector', 'grabcut', 'closed_form'):
        raise ValueError('unknown method or missing/unexpected extraction fields')
    hsh = plan['source_sha256']
    if (not isinstance(hsh, str) or len(hsh) != 64
            or any(c not in '0123456789abcdef' for c in hsh)):
        raise ValueError('source_sha256 required')
    if not isinstance(plan['observation'], str) or not plan['observation'].strip():
        raise ValueError('source observation required')
    if plan['method'] == 'closed_form':
        from source_layers import extract_layer
        return extract_layer(source,plan)
    image = read_image(source, hsh)
    box = _box(plan['context_bbox'], image.size)
    x, y, w, h = box
    if w*h > MAX_PIXELS:
        raise ValueError('context exceeds existing support processing limit')
    crop = image.crop((x, y, x+w, y+h)).convert('RGBA')
    if crop.getextrema()[3] != (255, 255):
        raise ValueError('inference requires opaque source; preserve existing alpha instead')
    fg = _points(plan['foreground'], box, 'foreground', True)
    bg = _points(plan['background'], box, 'background', plan['method'] == 'grabcut')
    if set(fg) & set(bg):
        raise ValueError('conflicting positive and negative seeds')
    marks = _annotations(plan.get('annotations', []), box, fg, bg)
    reserved = plan['reserved_regions']
    if not isinstance(reserved, list) or len(reserved) > 1000:
        raise ValueError('reserved_regions must be a bounded rectangle list')
    reserved = [_box(b, image.size) for b in reserved]
    engine = 'component_geometry.select'
    if plan['method'] == 'selector':
        support = select(crop, plan['selector'])
    else:
        try:
            import cv2
        except ImportError as exc:
            raise RuntimeError('grabcut requires installed OpenCV; no automatic fallback/install') from exc
        # Initialize probable classes from the observed seed colors, not a solid
        # foreground rectangle. A rectangle bias absorbs pale source backgrounds.
        # No border is forced to background: a truncated object must remain visible.
        pixels = np.asarray(crop)[:, :, :3].astype(np.float32)
        samples = [np.unique(np.array([pixels[py, px] for px, py in points]), axis=0)
                   for points in (fg, bg)]
        if w*h*sum(len(s) for s in samples) > 50_000_000:
            raise ValueError('seed-color initialization exceeds processing bound')
        distances = []
        for group in samples:
            nearest = np.full((h, w), np.inf)
            for color in group:
                nearest = np.minimum(nearest, ((pixels-color)**2).sum(axis=2))
            distances.append(nearest)
        labels = np.where(distances[0] < distances[1], cv2.GC_PR_FGD, cv2.GC_PR_BGD).astype(np.uint8)
        observed = marks != 255
        labels[observed] = marks[observed]
        initial_labels = labels.copy()
        cv2.setRNGSeed(0)
        bmodel, fmodel = np.zeros((1, 65)), np.zeros((1, 65))
        cv2.grabCut(np.asarray(crop)[:, :, :3].copy(), labels, None,
                    bmodel, fmodel, 5, cv2.GC_INIT_WITH_MASK)
        support = (labels == cv2.GC_FGD) | (labels == cv2.GC_PR_FGD)
        engine = 'OpenCV ' + cv2.__version__ + ' grabCut (5 iterations, seed 0)'
    labels, regions = label_regions(support)
    selected = set(map(int, np.unique(labels[marks == 1])))
    if 0 in selected:
        raise ValueError('foreground seed excluded by extraction; revise observations, not pixels')
    negative = set(map(int, np.unique(labels[marks == 0]))) - {0}
    if selected & negative:
        raise ValueError('foreground/background share a connected support region')
    mask = np.isin(labels, list(selected))
    ys, xs = np.nonzero(mask)
    # One transparent edge pixel when context permits; no erosion or hole filling.
    left, top = max(0, int(xs.min())-1), max(0, int(ys.min())-1)
    right, bottom = min(w, int(xs.max())+2), min(h, int(ys.max())+2)
    issues = []
    if any(r['touches_border'] for r in regions if r['id'] in selected):
        issues.append('selected support touches context edge; completeness unresolved')
    overlaps = []
    for index, (rx, ry, rw, rh) in enumerate(reserved):
        a, b, c, d = max(0, rx-x), max(0, ry-y), min(w, rx+rw-x), min(h, ry+rh-y)
        count = int(mask[b:d, a:c].sum()) if a < c and b < d else 0
        if count:
            overlaps.append({'region_index': index, 'foreground_pixels': count})
    if overlaps:
        issues.append('reserved native content intersects object; no automatic erasure/inpainting')
    alpha = Image.fromarray((mask*255).astype(np.uint8))
    out = crop.crop((left, top, right, bottom))
    crop_alpha = alpha.crop((left, top, right, bottom))
    out.putalpha(crop_alpha)
    outputs = {'context_mask': _png(alpha), 'alpha': _png(crop_alpha), 'rgba': _png(out)}
    if plan['method'] == 'grabcut':
        outputs['initial_labels'] = _png(Image.fromarray(initial_labels))
        # Annotation display is evidence only; these colors never enter extraction.
        colors = np.array([[220, 40, 40], [30, 190, 90], [240, 155, 70], [60, 160, 240]], dtype=np.uint8)
        preview = np.asarray(crop).copy()
        marked = marks != 255
        preview[marked, :3] = colors[marks[marked]]
        outputs['annotations'] = _png(Image.fromarray(preview))
    evidence = {'status': 'CANDIDATE', 'source_sha256': hsh,
                'plan_sha256': digest(json.dumps(plan, sort_keys=True).encode()),
                'source_size': list(image.size), 'context_bbox': list(box),
                'source_bbox': [x+left, y+top, right-left, bottom-top],
                'foreground_pixels': int(mask.sum()), 'selected_regions': sorted(selected),
                'unselected_region_count': len(regions)-len(selected),
                'unselected_foreground_pixels': int(support.sum()-mask.sum()),
                'reserved_overlaps': overlaps, 'issues': issues, 'engine': engine,
                'alpha_inferred': True, 'hidden_content_generated': False,
                'annotation_count': len(plan.get('annotations', [])),
                'hard_foreground_pixels': int((marks == 1).sum()),
                'hard_background_pixels': int((marks == 0).sum()),
                'visual_review': 'NOT_PERFORMED', 'outputs_sha256': {k: digest(v) for k,v in outputs.items()}}
    return outputs, evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('plan', type=Path)
    parser.add_argument('output_directory', type=Path)
    args = parser.parse_args()
    if args.output_directory.exists():
        raise ValueError('use a new output directory')
    data, evidence = extract_source_object(args.source, json.loads(args.plan.read_text(encoding='utf8')))
    args.output_directory.mkdir(parents=True, exist_ok=False)
    for name, content in data.items():
        (args.output_directory / (name + '.png')).write_bytes(content)
    (args.output_directory / 'candidate.json').write_text(json.dumps(evidence, indent=2), encoding='utf8')
    print(json.dumps({'status': evidence['status'], 'issues': evidence['issues']}))


if __name__ == '__main__':
    main()
