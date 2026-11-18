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


MAX_CONTENT_RECORDS = 100000
MAX_CONTENT_CHARACTERS = 500000


def _content_frame(page):
    """Public page transforms; no mutation of source rotation or crop box."""
    return dict(rotation_degrees=page.rotation, page_rect=_box(page.rect),
                cropbox=_box(page.cropbox),
                rotation_matrix=_plain(page.rotation_matrix),
                derotation_matrix=_plain(page.derotation_matrix),
                unrotated_bounds=_box(page.rect * page.derotation_matrix),
                coordinates='unrotated PDF page points',
                matrix_convention='PyMuPDF public six-value Matrix; page points, not PDF user-space CTM')


def _content_call(page, method, invoke, convert):
    """Optional public API channels fail explicitly without guessed fallback data."""
    if not callable(getattr(page, method, None)):
        return dict(status='UNAVAILABLE', api=method, records=[], reason='public method missing')
    try:
        raw = invoke()
    except (TypeError, NotImplementedError) as exc:
        return dict(status='UNSUPPORTED', api=method, records=[], reason=type(exc).__name__)
    except Exception as exc:
        return dict(status='ERROR', api=method, records=[], reason=type(exc).__name__)
    try:
        records, count = convert(raw)
    except (ValueError, TypeError, KeyError, IndexError, OverflowError) as exc:
        # Do not include exception messages: these can contain source text/paths.
        return dict(status='REJECTED', api=method, records=[], reason=type(exc).__name__,
                    detail='invalid result or content evidence budget exceeded; no truncation')
    return dict(status='EXTRACTED', api=method, source_record_count=count,
                selected_record_count=len(records), records=records)


def _content_records(value):
    if not isinstance(value, (list, tuple)) or len(value) > MAX_CONTENT_RECORDS:
        raise ValueError('invalid or over-budget content records')
    return value


def _extract_content(page, region, display, frame):
    """Extra evidence only; never marks an operation converted or resolved.

    Trace seqno is supplied by MuPDF and checked against display operation kind.
    rawdict order and image block numbers are not display-list sequence numbers.
    Images remain per-instance, including repeated xrefs and xref=0 inline images.
    """
    # Candidate lookup is linear, bounded even when many instances share a bbox.
    image_operations = {}
    for seq, op in enumerate(display):
        if op[0] == 'fill-image':
            key = tuple(round(v, 4) for v in _box(op[1]))
            entry = image_operations.setdefault(key, dict(seqnos=[], count=0))
            entry['count'] += 1
            if len(entry['seqnos']) < 32:
                entry['seqnos'].append(seq)

    def traces(raw):
        raw = _content_records(raw)
        if sum(len(r['chars']) for r in raw) > MAX_CONTENT_CHARACTERS:
            raise ValueError('text trace character budget exceeded')
        result = []
        for i, record in enumerate(raw):
            if not _intersects(_box(record['bbox']), region):
                continue
            record = _plain(record)
            seq = record.get('seqno')
            kind = display[seq][0] if type(seq) is int and 0 <= seq < len(display) else None
            expected = {0: 'fill-text', 1: 'stroke-text', 3: 'ignore-text'}.get(record.get('type'))
            record.update(evidence_id='texttrace-'+str(i),
                          display_seqno_validation=('TEXT_KIND_MATCH' if expected is not None
                              and kind == expected else 'UNVERIFIED'),
                          display_kind=kind, visibility='NOT_INFERRED')
            result.append(record)
        return result, len(raw)

    def text_spans(raw):
        if not isinstance(raw, dict):
            raise ValueError('rawdict must be a dictionary')
        blocks = _content_records(raw['blocks'])
        result, count, characters = [], 0, 0
        for bi, block in enumerate(blocks):
            if block.get('type') != 0:
                continue
            for li, line in enumerate(_content_records(block['lines'])):
                for si, span in enumerate(_content_records(line['spans'])):
                    count += 1
                    chars = _content_records(span['chars'])
                    characters += len(chars)
                    if count > MAX_CONTENT_RECORDS or characters > MAX_CONTENT_CHARACTERS:
                        raise ValueError('raw text evidence budget exceeded')
                    if not _intersects(_box(span['bbox']), region):
                        continue
                    item = _plain(span)
                    item.update(evidence_id=f'rawtext-{bi}-{li}-{si}',
                                source_block_number=block.get('number'),
                                source_line_index=li, source_span_index=si,
                                line_direction=_plain(line.get('dir')),
                                writing_mode=line.get('wmode'),
                                paint_sequence_association='NOT_INFERRED', visibility='NOT_INFERRED')
                    result.append(item)
        return result, count

    def fonts(raw):
        raw = _content_records(raw)
        result = []
        for i, font in enumerate(raw):
            if not isinstance(font, (list, tuple)) or len(font) < 6:
                raise ValueError('invalid public font tuple')
            item = dict(zip(('xref', 'extension', 'type', 'basefont', 'resource_name', 'encoding'),
                            _plain(font[:6])))
            item.update(evidence_id='font-'+str(i),
                        referencer_xref=font[6] if len(font) > 6 else None,
                        api_tuple=_plain(font), scope='whole_page_resource_inventory',
                        embedded_font_bytes='NOT_EXTRACTED',
                        text_span_mapping='NOT_INFERRED')
            result.append(item)
        return result, len(raw)

    def images(raw):
        raw = _content_records(raw)
        result = []
        for i, original in enumerate(raw):
            bounds = _box(original['bbox'])
            if not _intersects(bounds, region):
                continue
            # get_image_info's digest is a content identifier supplied by MuPDF,
            # not a claim that it is SHA256, and not a reason to deduplicate uses.
            item = dict(original)
            digest = item.pop('digest', None)
            if digest is not None and not isinstance(digest, bytes):
                raise ValueError('unexpected image digest')
            transform = _plain(item.get('transform'))
            if (not isinstance(transform, list) or len(transform) != 6
                    or any(type(v) not in (int, float) for v in transform)):
                raise ValueError('invalid image instance transform')
            item = _plain(item)
            candidates = image_operations.get(tuple(round(v, 4) for v in bounds),
                                               dict(seqnos=[], count=0))
            item.update(evidence_id='image-instance-'+str(i),
                        digest_hex=digest.hex() if digest is not None else None,
                        digest_algorithm='PyMuPDF image-info digest; not asserted as SHA256',
                        instance_ctm=transform,
                        ctm_convention='unit image rectangle to unrotated page points; PyMuPDF transform',
                        source_block_number_not_seqno=original.get('number'),
                        candidate_display_seqnos_by_bbox=candidates['seqnos'],
                        candidate_display_operation_count=candidates['count'],
                        candidate_list_truncated=candidates['count'] > 32,
                        candidate_match_method='bounds rounded to four decimal page points; not proof',
                        paint_sequence_association='NOT_INFERRED',
                        xref_zero_meaning='inline image or resource xref not identified',
                        visibility='NOT_INFERRED')
            result.append(item)
        return result, len(raw)

    # Disable image payload extraction explicitly. Image placement is a separate
    # public-API channel, never rawdict bitmap bytes in an evidence JSON file.
    def raw_text():
        import pymupdf
        flags = pymupdf.TEXTFLAGS_RAWDICT & ~pymupdf.TEXT_PRESERVE_IMAGES
        return page.get_text('rawdict', flags=flags, sort=False)

    channels = dict(
        text_trace=_content_call(page, 'get_texttrace', lambda: page.get_texttrace(), traces),
        text_spans=_content_call(page, 'get_text', raw_text, text_spans),
        fonts=_content_call(page, 'get_fonts', lambda: page.get_fonts(full=True), fonts),
        image_instances=_content_call(page, 'get_image_info',
            lambda: page.get_image_info(hashes=True, xrefs=True), images))
    return dict(schema=1, status=('EXTRACTED' if all(c['status'] == 'EXTRACTED'
                     for c in channels.values()) else 'PARTIAL'),
                purpose='SOURCE_EVIDENCE_ONLY', native_conversion_status='NOT_PERFORMED',
                page_frame=frame, channels=channels,
                budgets=dict(records_per_channel=MAX_CONTENT_RECORDS,
                             characters_per_text_channel=MAX_CONTENT_CHARACTERS),
                limitations=[
                    'API results are materialized by PyMuPDF before evidence budgets can be checked.',
                    'Region selection keeps intersecting whole spans or image instances; no geometric clipping.',
                    'Font resources cover the whole page and are not asserted to match spans one-to-one.',
                    'Trace seqno kind checks do not establish visibility, clipping or editable text equivalence.',
                    'Image bbox candidates and block numbers are not verified display-list associations.',
                    'Outlined or rasterized text, font embedding rights and full PDF paint state are not recovered.',
                    'Additional content evidence never removes an unresolved display operation.'])


def extract_page(page, region=None, *, include_content=False):
    """Inspect source, with explicit limits. Scope is not opacity multiplication."""
    if type(include_content) is not bool:
        raise ValueError('include_content must be boolean')
    frame = _content_frame(page) if include_content else None
    region = _box((frame['unrotated_bounds'] if include_content else page.rect)
                  if region is None else region)
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
    result = dict(schema=1, region=region, coordinate_space='unrotated PDF page points',
                scopes=[r for sid,r in scopes.items() if sid in used], paths=selected,
                operations=operations, operation_counts=dict(Counter(o['kind'] for o in operations)),
                unresolved_operations=unresolved, native_conversion_status='NOT_PERFORMED',
                limitations=['Extended paths do not expose all soft masks or shading recipes.',
                             'Scope hazards require interpretation; do not distribute group alpha to children.',
                             'Region filters bounds only; it does not apply geometric clipping.',
                             'No paint-space or scientific editing-unit equivalence is inferred.'])
    if include_content:
        result['content_evidence'] = _extract_content(page, region, display, frame)
    return result


def inspect_pdf(source, page_number, region=None, *, include_content=False):
    import pymupdf
    if type(include_content) is not bool:
        raise ValueError('include_content must be boolean')
    source = Path(source)
    with pymupdf.open(source) as document:
        if type(page_number) is not int or not 1 <= page_number <= len(document):
            raise ValueError('page must be one-based and within document')
        result = (extract_page(document[page_number-1], region, include_content=True)
                  if include_content else extract_page(document[page_number-1], region))
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
    parser.add_argument('--include-content', action='store_true',
                        help='add optional text/font/character/image source evidence; no conversion')
    args = parser.parse_args()
    result = inspect_pdf(args.source, args.page, args.region, include_content=args.include_content)
    with Path(args.output).open('x', encoding='utf8') as out:
        json.dump(result, out, ensure_ascii=False, indent=2, allow_nan=False)
    print(json.dumps(dict(paths=len(result['paths']), operations=result['operation_counts'],
                          unresolved=len(result['unresolved_operations']), status='EXTRACTED_NOT_CONVERTED')))
