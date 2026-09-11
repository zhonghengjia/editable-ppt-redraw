"""Read-only PDF paint-state extraction, not a PDF-to-PPT renderer.

Preserve extended group/clip scopes before selecting a region. Cross-check the
display list because paths alone omit shades, inline images and text. Requires
an already installed PyMuPDF only at the file entrypoint; downloaded PDF content
is data and is never executed. Inspection never flattens opacity. The explicit
artwork renderer supplies observed paint for native color partitioning, not an
image to embed in a presentation.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path

from vendor.svg_paths.drawingml_paths import PathCommand, path_bounds


def _plain(value):
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError('nonfinite source geometry')
        return value
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    return [_plain(v) for v in value]


def _box(value):
    vals = _plain(value)
    if (not isinstance(vals, list) or len(vals) != 4
            or any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in vals)
            or vals[0] > vals[2] or vals[1] > vals[3]):
        raise ValueError('box requires ordered finite [x0,y0,x1,y1]')
    return vals


def _intersects(a, b):
    return a[0] <= b[2] and b[0] <= a[2] and a[1] <= b[3] and b[1] <= a[3]


def drawing_commands(record):
    """Keep cubic controls exactly; PDF coordinates are already page-space."""
    result, previous = [], None
    for item in record['items']:
        op, *pts = item
        if op in ('l', 'c'):
            if previous != pts[0]:
                result.append(PathCommand('M', list(pts[0])))
            result.append(PathCommand('L' if op == 'l' else 'C', [n for p in pts[1:] for n in p]))
            previous = pts[-1]
        elif op == 're':
            x0, y0, x1, y1 = pts[0]
            corners = [(x0,y0), (x1,y0), (x1,y1), (x0,y1)]
            if pts[1] < 0:
                corners.reverse()
            result.extend([PathCommand('M', list(corners[0]))]
                          + [PathCommand('L', list(p)) for p in corners[1:]] + [PathCommand('Z', [])])
            previous = None
        elif op == 'qu':
            # PyMuPDF Quad iteration is UL, UR, LL, LR, not perimeter order.
            q = pts[0]
            corners = [q[0], q[1], q[3], q[2]]
            result.extend([PathCommand('M', list(corners[0]))]
                          + [PathCommand('L', list(p)) for p in corners[1:]] + [PathCommand('Z', [])])
            previous = None
        else:
            raise ValueError('unsupported PDF drawing operator: '+str(op))
    if record.get('closePath') and result and result[-1].cmd != 'Z':
        result.append(PathCommand('Z', []))
    return result


def extract_page(page, region=None):
    """Inspect source, with explicit limits. Scope is not opacity multiplication."""
    region = _box(page.rect if region is None else region)
    drawings = page.get_drawings(extended=True)
    display = page.get_bboxlog()
    if len(drawings) > 100000 or len(display) > 100000:
        raise ValueError('page exceeds paint operation budget')
    stack, scopes, selected, used, represented = [], {}, [], set(), set()
    for index, raw in enumerate(drawings):
        level = raw.get('level')
        if type(level) is not int or not 0 <= level <= 128:
            raise ValueError('extended drawing level missing or out of range')
        while stack and stack[-1]['level'] >= level:
            stack.pop()
        record = _plain(raw)
        sid = 'drawing-'+str(index)
        if record['type'] in ('group', 'clip'):
            record.update(id=sid, parent=stack[-1]['id'] if stack else None)
            scopes[sid] = record
            stack.append(record)
            continue
        if not _intersects(_box(record['rect']), region):
            continue
        if len(record.get('items', [])) > 100000:
            raise ValueError('path exceeds drawing item budget')
        record.update(id=sid, scopes=[s['id'] for s in stack])
        used.update(record['scopes'])
        record['tight_bounds'] = list(path_bounds(drawing_commands(record)))
        # get_drawings rect can include off-curve controls. Keep both, not relabel.
        record['scope_hazards'] = sorted({
            reason for s in stack for reason in (
                ['clip'] if s['type'] == 'clip' else
                (['group_opacity'] if s.get('opacity', 1) != 1 else [])
                + (['blend:'+str(s['blendmode'])] if s.get('blendmode', 'Normal') != 'Normal' else [])
                + (['isolated_group'] if s.get('isolated') else [])
                + (['knockout_group'] if s.get('knockout') else []))})
        selected.append(record)
        seq = record.get('seqno')
        if type(seq) is int and 0 <= seq < len(display):
            represented.add(seq)
            if record['type'] == 'fs' and seq+1 < len(display) and display[seq+1][0] == 'stroke-path':
                represented.add(seq+1)
    operations = [dict(seqno=i, kind=v[0], bounds=_box(v[1]), path_record_present=i in represented)
                  for i, v in enumerate(display) if _intersects(_box(v[1]), region)]
    unresolved = [o for o in operations if not o['path_record_present']]
    return dict(schema=1, region=region, coordinate_space='unrotated PDF page points',
                scopes=[r for sid,r in scopes.items() if sid in used], paths=selected,
                operations=operations, operation_counts=dict(Counter(o['kind'] for o in operations)),
                unresolved_operations=unresolved, native_conversion_status='NOT_PERFORMED',
                limitations=['Extended paths do not expose all soft masks or shading recipes.',
                             'Scope hazards require interpretation; do not distribute group alpha to children.',
                             'Region filters bounds only; it does not apply geometric clipping.',
                             'No paint-space or scientific editing-unit equivalence is inferred.'])


def inspect_pdf(source, page_number, region=None):
    import pymupdf
    source = Path(source)
    with pymupdf.open(source) as document:
        if type(page_number) is not int or not 1 <= page_number <= len(document):
            raise ValueError('page must be one-based and within document')
        result = extract_page(document[page_number-1], region)
    result.update(source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                  page=page_number, extractor='PyMuPDF '+pymupdf.VersionBind)
    return result


def render_artwork(source, page_number, region=None, scale=3):
    """Render existing PDF artwork without duplicating separately editable text.

    Redact only PDF text in an in-memory copy, with no cover fill and no removal
    of images or vector graphics. This cannot separate outlined/rasterized text
    or restore artwork that was absent from the source. Never save the copy.
    """
    import pymupdf
    from PIL import Image
    if isinstance(scale, bool) or not isinstance(scale, (int, float)) or not math.isfinite(scale) or scale <= 0:
        raise ValueError('scale must be positive and finite')
    raw = Path(source).read_bytes()
    with pymupdf.open(stream=raw, filetype='pdf') as document:
        if type(page_number) is not int or not 1 <= page_number <= len(document):
            raise ValueError('page must be one-based and within document')
        page = document[page_number-1]
        if page.rotation:
            raise ValueError('artwork rendering requires unrotated source coordinates')
        clip = pymupdf.Rect(_box(page.rect if region is None else region))
        if clip.is_empty or not page.rect.contains(clip):
            raise ValueError('artwork region must be nonempty and within page')
        if math.ceil(clip.width*scale)*math.ceil(clip.height*scale) > 16000000:
            raise ValueError('artwork render exceeds pixel budget')
        if any(a.type[0] == pymupdf.PDF_ANNOT_REDACT for a in page.annots() or []):
            raise ValueError('source has existing redactions; do not apply them implicitly')
        before = page.get_text()
        page.add_redact_annot(page.rect, fill=False, cross_out=False)
        page.apply_redactions(images=0, graphics=0, text=0)
        remaining = page.get_text()
        if remaining.strip():
            raise ValueError('PDF text separation incomplete')
        pix = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), clip=clip, alpha=False, annots=False)
        image = Image.frombytes('RGB', (pix.width,pix.height), pix.samples).convert('RGBA')
        evidence = dict(source_sha256=hashlib.sha256(raw).hexdigest(), page=page_number,
                        clip=list(clip), scale=scale, pixel_origin=[pix.x,pix.y],
                        pixel_size=[pix.width,pix.height], renderer='PyMuPDF '+pymupdf.VersionBind,
                        source_text_characters=len(before), remaining_text_characters=len(remaining),
                        text_separation='in_memory_text_only_redaction_no_cover',
                        limitations=['Outlined or rasterized text is not separated.',
                                     'Visible paint is composited against the original backdrop.',
                                     'No hidden artwork is synthesized.'])
    return image, evidence


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source'); parser.add_argument('output')
    parser.add_argument('--page', type=int, required=True)
    parser.add_argument('--region', type=float, nargs=4)
    args = parser.parse_args()
    result = inspect_pdf(args.source, args.page, args.region)
    with Path(args.output).open('x', encoding='utf8') as out:
        json.dump(result, out, ensure_ascii=False, indent=2, allow_nan=False)
    print(json.dumps(dict(paths=len(result['paths']), operations=result['operation_counts'],
                          unresolved=len(result['unresolved_operations']), status='EXTRACTED_NOT_CONVERTED')))
