"""Measure advisory source-image ink geometry within existing text inventory boxes."""

from hashlib import sha256
from io import BytesIO
import json
import math
from pathlib import Path
from statistics import median
import unicodedata

import numpy as np
from PIL import Image, ImageDraw, ImageFont


MIN_CLASS_SEPARATION = 25
MIN_INK_PIXELS = 8
MAX_INK_FRACTION = 0.45
REFERENCE_FONT_PX = 64
FONT_RATIO_TOLERANCE = 1.18
MAX_OVERVIEW_SIDE = 1600


def _digest(data):
    return sha256(data).hexdigest()


def _otsu_threshold(gray):
    """Return the integer threshold and separation of two luminance classes.

    Adapted from image-to-editable-ppt, page_text_metrics.py, pinned revision
    b7be494e31a0ed56ef98716891db5474606b8cdf.
    Copyright (c) 2026 ningzimu, MIT. See the accompanying MIT license.
    """
    hist = np.bincount(gray.ravel(), minlength=256)
    weight_low = np.cumsum(hist)
    weight_high = gray.size - weight_low
    total_low = np.cumsum(np.arange(256) * hist)
    mean_low = total_low / np.maximum(weight_low, 1)
    mean_high = (total_low[-1] - total_low) / np.maximum(weight_high, 1)
    separation = np.abs(mean_low - mean_high)
    between_class = weight_low.astype(np.float64) * weight_high * separation**2
    threshold = int(np.argmax(between_class))
    return threshold, float(separation[threshold]) if between_class[threshold] else 0.0


def _occupied_runs(profile, merge_gap=0):
    positions = np.flatnonzero(profile)
    if not positions.size:
        return []
    return [(int(chunk[0]), int(chunk[-1]) + 1) for chunk in
            np.split(positions, np.flatnonzero(np.diff(positions) > merge_gap + 1) + 1)]


def _box(mask, x=0, y=0):
    rows = np.flatnonzero(mask.any(axis=1))
    if not rows.size:
        return None
    cols = np.flatnonzero(mask.any(axis=0))
    return [x + int(cols[0]), y + int(rows[0]),
            int(cols[-1] - cols[0] + 1), int(rows[-1] - rows[0] + 1)]


def _measure_crop(crop, box, text):
    x, y, width, height = box
    gray = np.asarray(crop.convert("L"))
    threshold, separation = _otsu_threshold(gray)
    dark = gray <= threshold
    polarity = "dark" if int(dark.sum()) * 2 <= gray.size else "light"
    mask = dark if polarity == "dark" else ~dark
    if separation == 0:
        mask = np.zeros_like(mask)
    count = int(mask.sum())
    bbox = _box(mask, x, y)
    # Keep every selected pixel. Bridging small gaps is for measuring bands only.
    bands = [_box(mask[top:bottom, :], x, y + top)
             for top, bottom in _occupied_runs(mask.any(axis=1), merge_gap=2)]
    perimeter = np.concatenate((gray[0, :], gray[-1, :], gray[1:-1, 0], gray[1:-1, -1]))
    bg_mid = float(np.median(perimeter))
    edge_contacts = [edge for edge, values in (
        ("top", mask[0, :]), ("bottom", mask[-1, :]), ("left", mask[:, 0]), ("right", mask[:, -1]),
    ) if values.any()]
    lighting = gray.astype(np.float32) - bg_mid
    mixed_polarity = (
        np.count_nonzero(lighting <= -MIN_CLASS_SEPARATION) >= MIN_INK_PIXELS
        and np.count_nonzero(lighting >= MIN_CLASS_SEPARATION) >= MIN_INK_PIXELS
    )
    text_lines = [line for line in text.splitlines() if line.strip()]
    uncertain = []
    alpha = crop.convert("RGBA").getchannel("A") if crop.mode in ("LA", "RGBA") else None
    if alpha is not None and alpha.getextrema() != (255, 255):
        uncertain.append("nonopaque_source")
    if not count:
        uncertain.append("no_detectable_ink")
    if separation < MIN_CLASS_SEPARATION:
        uncertain.append("low_luminance_contrast")
    if 0 < count < MIN_INK_PIXELS:
        uncertain.append("limited_ink_pixels")
    if count / gray.size > MAX_INK_FRACTION:
        uncertain.append("high_ink_fraction")
    if edge_contacts:
        uncertain.append("ink_touches_crop_edge")
    if mixed_polarity:
        uncertain.append("suspected_mixed_polarity")
    if bbox:
        rule_width = max(12, math.ceil(0.85 * bbox[2]))
        dense_rows = np.flatnonzero(mask.sum(axis=1) >= rule_width)
        rule_rows = np.zeros(height, dtype=bool)
        for row in dense_rows:
            rule_rows[row] = any(right - left >= rule_width for left, right in _occupied_runs(mask[row]))
        if any(bottom - top <= 3 for top, bottom in _occupied_runs(rule_rows)):
            uncertain.append("suspected_thin_rule")
    if len(text_lines) != len(bands):
        uncertain.append("line_count_disagrees_with_transcription")
    if not text_lines:
        uncertain.append("no_nonempty_explicit_lines")
    render_lines = [{"ink_bbox": band} for band in bands]
    return mask, {
        "status": "AMBIGUOUS" if uncertain else "INK_MEASURED",
        "ink_bbox": bbox,
        "line_bands": render_lines,
        "ink_polarity": polarity if count else None,
        "ink_pixels": count,
        "ink_fraction": round(count / gray.size, 6),
        "gray_separation": round(separation, 2),
        "threshold": threshold,
        "edge_contacts": edge_contacts,
        "uncertainty": uncertain,
    }


def _font_candidate(path):
    if path is None:
        return {"status": "NOT_REQUESTED"}, None, None
    path = Path(path)
    record = {"basename": path.name}
    try:
        font_data = path.read_bytes()
    except OSError:
        return {**record, "status": "FONT_UNAVAILABLE"}, None, None
    record["sha256"] = _digest(font_data)
    if path.suffix.lower() not in (".ttf", ".otf") or font_data[:4] not in (b"\x00\x01\x00\x00", b"OTTO", b"true"):
        return {**record, "status": "UNSUPPORTED_FONT_FORMAT"}, None, None
    try:
        font = ImageFont.truetype(BytesIO(font_data), REFERENCE_FONT_PX)
    except OSError:
        return {**record, "status": "FONT_UNAVAILABLE"}, None, None
    family, style = font.getname()
    record.update(family=family, style=style)
    try:
        import pymupdf
    except ImportError:
        try:
            import fitz as pymupdf
        except ImportError:
            return {**record, "status": "FONT_COVERAGE_UNAVAILABLE"}, None, None
    try:
        coverage = pymupdf.Font(fontbuffer=font_data)
    except (AttributeError, RuntimeError, ValueError):
        return {**record, "status": "FONT_COVERAGE_UNAVAILABLE"}, None, None
    record.update(status="FONT_LOADED", bold=bool(coverage.is_bold), italic=bool(coverage.is_italic))
    return record, font, coverage


def _rendered_ink_box(font, text):
    left, top, right, bottom = font.getbbox(text)
    image = Image.new("L", (max(1, right - left + 6), max(1, bottom - top + 6)), 255)
    ImageDraw.Draw(image).text((3 - left, 3 - top), text, font=font, fill=0)
    gray = np.asarray(image)
    threshold, separation = _otsu_threshold(gray)
    return _box(gray <= threshold) if separation >= MIN_CLASS_SEPARATION else None


def _font_suggestion(item, measured, candidate, font, coverage, pt_per_px):
    if font is None:
        return {"status": "NOT_ESTIMATED", "reason": candidate["status"].lower()}
    if measured["uncertainty"]:
        return {"status": "NOT_ESTIMATED", "reason": "ambiguous_ink_geometry"}
    construction = item.get("construction")
    options = construction.get("options", {}) if isinstance(construction, dict) else {}
    if not isinstance(options, dict):
        return {"status": "NOT_ESTIMATED", "reason": "font_mismatch"}
    font_name = options.get("font", "Arial")
    bold = options.get("bold", False)
    if (not isinstance(font_name, str) or type(bold) is not bool or candidate["italic"]
            or candidate["family"].casefold().strip() != font_name.casefold().strip()
            or candidate["bold"] != bold):
        return {"status": "NOT_ESTIMATED", "reason": "font_mismatch"}
    text_lines = [line for line in item["text"].splitlines() if line.strip()]
    characters = sorted(set("".join(text_lines)))
    if any(unicodedata.category(ch).startswith("C") for ch in characters):
        return {"status": "NOT_ESTIMATED", "reason": "unsupported_text_control"}
    missing = [f"U+{ord(ch):04X}" for ch in characters
               if not ch.isspace() and not coverage.has_glyph(ord(ch), fallback=False)]
    if missing:
        return {"status": "NOT_ESTIMATED", "reason": "font_missing_glyphs", "missing_codepoints": missing}
    estimates = []
    for text, band in zip(text_lines, measured["line_bands"]):
        bounds = _rendered_ink_box(font, text)
        if bounds is None or band["ink_bbox"][3] < 6:
            return {"status": "NOT_ESTIMATED", "reason": "glyph_size_not_comparable"}
        width_px = band["ink_bbox"][2] * REFERENCE_FONT_PX / bounds[2]
        height_px = band["ink_bbox"][3] * REFERENCE_FONT_PX / bounds[3]
        estimates.append({"width_based_px": width_px, "height_based_px": height_px})
    values = [value for estimate in estimates for value in estimate.values()]
    evidence = {"per_line": [{key: round(value, 3) for key, value in estimate.items()} for estimate in estimates]}
    if max(values) / min(values) > FONT_RATIO_TOLERANCE:
        return {**evidence, "status": "NOT_ESTIMATED", "reason": "width_height_or_line_scales_disagree"}
    size = median(values)
    result = {**evidence, "status": "ADVISORY_ESTIMATE", "font_size_px": round(size, 2)}
    if pt_per_px is not None:
        result["font_size_pt"] = round(size * pt_per_px, 2)
    return result


def _read_inputs(manifest_path):
    payload = manifest_path.read_bytes()
    manifest = json.loads(payload.decode("utf-8-sig"))
    source = manifest.get("source") if isinstance(manifest, dict) else None
    if not isinstance(source, dict) or not isinstance(source.get("path"), str) or not source["path"]:
        raise ValueError("manifest source.path is required")
    if not isinstance(source.get("sha256"), str):
        raise ValueError("manifest source.sha256 is required")
    path = manifest_path.parent / source["path"]
    data = path.read_bytes()
    if _digest(data) != source["sha256"]:
        raise ValueError("source hash differs from manifest source.sha256")
    with Image.open(BytesIO(data)) as image:
        if (getattr(image, "n_frames", 1) != 1 or any(type(source.get(k)) is not int for k in ("width", "height"))
                or image.size != (source["width"], source["height"])):
            raise ValueError("source dimensions or frame count differ from the manifest contract")
        if image.getexif().get(274, 1) != 1:
            raise ValueError("use normalized source orientation for source-pixel coordinates")
        if image.mode not in ("1", "L", "LA", "P", "RGB", "RGBA"):
            raise ValueError(f"unsupported source pixel mode for measurement: {image.mode}")
        decoded = image.convert("RGBA") if image.mode == "P" or "transparency" in image.info else image.copy()
    if 'canvas' in manifest:
        canvas = manifest['canvas']
        if (not isinstance(canvas, dict) or any(
            type(canvas.get(key)) not in (int, float) or canvas[key] != source[key]
            for key in ('width', 'height'))):
            raise ValueError('measure-text requires a source-pixel canvas matching source dimensions')
    return manifest, _digest(payload), source, decoded


def _select_items(manifest, item_ids, size):
    inventory = manifest.get("source_inventory")
    if not isinstance(inventory, list) or any(not isinstance(item, dict) for item in inventory):
        raise ValueError("manifest source_inventory must be a list of objects")
    text_items = [item for item in inventory if item.get("role") == "text"]
    identifiers = [item.get("id") for item in text_items]
    if (any(not isinstance(value, str) or not value.strip() for value in identifiers)
            or len(set(identifiers)) != len(identifiers)):
        raise ValueError("text inventory IDs must be nonempty and unique")
    if item_ids is not None:
        if isinstance(item_ids, str):
            raise ValueError("pass item_ids as a list of text inventory IDs")
        selected = list(item_ids)
        if not selected or any(not isinstance(item_id, str) or item_id not in identifiers for item_id in selected):
            raise ValueError("item_ids must select existing text inventory IDs")
        text_items = [item for item in text_items if item["id"] in selected]
    if not text_items:
        raise ValueError("source_inventory contains no selected text items")
    for item in text_items:
        box = item.get("bbox")
        if (not isinstance(box, list) or len(box) != 4 or any(
                type(value) not in (int, float) or not math.isfinite(value) for value in box)):
            raise ValueError(f"{item['id']}: bbox must be finite source [x,y,width,height]")
        x, y, width, height = box
        if min(x, y) < 0 or min(width, height) <= 0 or x + width > size[0] or y + height > size[1]:
            raise ValueError(f"{item['id']}: bbox exceeds source pixels")
        if not isinstance(item.get("text"), str):
            raise ValueError(f"{item['id']}: text must contain the source transcription")
    return text_items


def _point_scale(manifest, width):
    construction = manifest.get("construction")
    if not isinstance(construction, dict) or "slide_width_inches" not in construction:
        return None
    inches = construction["slide_width_inches"]
    if type(inches) not in (float, int) or not math.isfinite(inches) or inches <= 0:
        raise ValueError("construction.slide_width_inches must be a finite positive number")
    scale = inches / width * 72
    if not math.isfinite(scale) or scale <= 0:
        raise ValueError("construction slide width gives an unrepresentable point scale")
    return scale


def measure_manifest(manifest_path, output_dir, *, font_file=None, item_ids=None, context_padding_px=0):
    """Measure selected text from the exact source bytes in an existing manifest."""
    manifest_path = Path(manifest_path)
    manifest, manifest_hash, source, image = _read_inputs(manifest_path)
    items = _select_items(manifest, item_ids, image.size)
    if type(context_padding_px) is not int or not 0 <= context_padding_px <= 128:
        raise ValueError('context_padding_px must be an integer from 0 to 128 source pixels')
    pt_per_px = _point_scale(manifest, image.width)
    font_record, font, coverage = _font_candidate(font_file)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=False)
    overlay = image.convert("RGB")
    overlay.thumbnail((MAX_OVERVIEW_SIDE, MAX_OVERVIEW_SIDE))
    scale_x, scale_y = overlay.width / image.width, overlay.height / image.height
    draw = ImageDraw.Draw(overlay)
    measurements = []
    for index, item in enumerate(items, 1):
        sx, sy, sw, sh = item["bbox"]
        x, y = max(0, math.floor(sx)-context_padding_px), max(0, math.floor(sy)-context_padding_px)
        right, bottom = min(image.width, math.ceil(sx+sw)+context_padding_px), min(image.height, math.ceil(sy+sh)+context_padding_px)
        width, height = right-x, bottom-y
        context_box = [x, y, width, height]
        crop = image.crop((x, y, x + width, y + height))
        mask, measured = _measure_crop(crop, context_box, item["text"])
        name = f"item-{index:04d}"
        folder = output / name
        folder.mkdir()
        crop.save(folder / "source-crop.png")
        Image.fromarray(mask.astype(np.uint8) * 255).save(folder / "ink-mask.png")
        draw.rectangle((int(x * scale_x), int(y * scale_y),
                        math.ceil((x + width) * scale_x) - 1,
                        math.ceil((y + height) * scale_y) - 1),
                       outline="#c82828" if measured["uncertainty"] else "#178466", width=2)
        draw.text((int(x * scale_x) + 3, int(y * scale_y) + 3), str(index),
                  fill="white", stroke_fill="black", stroke_width=2)
        measured["font_suggestion"] = _font_suggestion(item, measured, font_record, font, coverage, pt_per_px)
        measurements.append({"id": item["id"], "text": item["text"], "source_bbox": item["bbox"],
                             "measurement_bbox": context_box,
                             "crop_path": f"{name}/source-crop.png", "mask_path": f"{name}/ink-mask.png",
                             **measured})
    overlay.save(output / "overview.png")
    report = {
        "schema_version": 1,
        "status": "ADVISORY",
        "manifest": {"path": manifest_path.name, "sha256": manifest_hash},
        "source": {key: source[key] for key in ("path", "sha256", "width", "height")},
        "source_font_scale_pt_per_px": pt_per_px,
        "context_padding_px": context_padding_px,
        "font_candidate": font_record,
        "overview_path": "overview.png",
        "items": measurements,
        "limitations": [
            "The ink mask is a luminance-based candidate within the declared source bounds.",
            "A fitted nominal size is a starting estimate for the supplied face before PowerPoint rendering.",
            "Rotated or mixed-size/script runs may yield a plausible aggregate estimate; inspect source runs before applying it.",
        ],
    }
    (output / "measurements.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                                              encoding="utf-8")
    return report
