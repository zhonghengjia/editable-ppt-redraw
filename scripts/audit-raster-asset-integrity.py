#!/usr/bin/env python3
"""Audit raster icon and evidence assets for clipping and placement risks."""

from __future__ import annotations

import argparse
import io
import json
import math
import sys
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageOps


SUPPORTED = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}


def collect_files(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path] if input_path.suffix.lower() in SUPPORTED else []
    if input_path.is_dir():
        return sorted(
            path for path in input_path.rglob("*")
            if path.is_file() and path.suffix.lower() in SUPPORTED
        )
    return []


def alpha_bbox(image: Image.Image, threshold: int) -> tuple[int, int, int, int] | None:
    alpha = image.getchannel("A")
    mask = alpha.point(lambda value: 255 if value > threshold else 0)
    return mask.getbbox()


def audit_asset(
    path: Path,
    alpha_threshold: int,
    edge_risk_ratio: float,
    min_long_edge: int,
    min_occupancy: float,
    max_occupancy: float,
) -> dict[str, Any]:
    errors: list[str] = []
    risks: list[str] = []
    warnings: list[str] = []
    try:
        with Image.open(path) as opened:
            frame_count = int(getattr(opened, "n_frames", 1))
            rgba = ImageOps.exif_transpose(opened).convert("RGBA")
    except Exception as exc:
        return {
            "path": str(path.resolve()),
            "valid": False,
            "errors": [f"cannot read image: {exc}"],
            "risks": [],
            "warnings": [],
        }

    width, height = rgba.size
    alpha = rgba.getchannel("A")
    alpha_min, alpha_max = alpha.getextrema()
    meaningful_alpha = alpha_min < 255
    bbox = alpha_bbox(rgba, alpha_threshold)
    if bbox is None:
        errors.append("no visible pixels above alpha threshold")
        visible_width = visible_height = visible_pixels = 0
        margins = {"left": 0, "top": 0, "right": 0, "bottom": 0}
        occupancy = 0.0
        pixel_occupancy = 0.0
        edge_risk = {key: False for key in margins}
    else:
        left, top, right, bottom = bbox
        visible_width = right - left
        visible_height = bottom - top
        flattened = getattr(alpha, "get_flattened_data", None)
        pixel_values = flattened() if flattened is not None else alpha.getdata()
        visible_pixels = sum(1 for value in pixel_values if value > alpha_threshold)
        margins = {
            "left": left,
            "top": top,
            "right": width - right,
            "bottom": height - bottom,
        }
        edge_limit = max(1, math.ceil(min(width, height) * edge_risk_ratio))
        edge_risk = {key: value < edge_limit for key, value in margins.items()}
        occupancy = (visible_width * visible_height) / max(1, width * height)
        pixel_occupancy = visible_pixels / max(1, width * height)
        if meaningful_alpha and any(edge_risk.values()):
            risks.append("visible pixels enter the alpha edge-risk band")
        if meaningful_alpha and occupancy < min_occupancy:
            risks.append("visible subject occupies too little of the asset canvas")
        if meaningful_alpha and occupancy > max_occupancy:
            risks.append("alpha-visible bounds are implausibly tight to the asset canvas")

    if max(width, height) < min_long_edge:
        risks.append(f"asset longest edge is below {min_long_edge}px")
    if frame_count != 1:
        warnings.append(f"asset contains {frame_count} frames; only the first frame was audited")
    if not meaningful_alpha:
        warnings.append("opaque rectangular asset; alpha edge clipping was not evaluated")

    return {
        "path": str(path.resolve()),
        "valid": not errors,
        "size": [width, height],
        "frame_count": frame_count,
        "meaningful_alpha": meaningful_alpha,
        "alpha_range": [alpha_min, alpha_max],
        "visible_bbox": list(bbox) if bbox else None,
        "visible_size": [visible_width, visible_height],
        "visible_pixels": visible_pixels,
        "bbox_occupancy": round(occupancy, 6),
        "pixel_occupancy": round(pixel_occupancy, 6),
        "edge_margins_px": margins,
        "edge_risk": edge_risk,
        "errors": errors,
        "risks": risks,
        "warnings": warnings,
    }


def checkerboard(width: int, height: int, cell: int = 12) -> Image.Image:
    canvas = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(canvas)
    colors = ((238, 241, 245), (211, 217, 225))
    for y in range(0, height, cell):
        for x in range(0, width, cell):
            draw.rectangle(
                (x, y, min(width, x + cell), min(height, y + cell)),
                fill=colors[((x // cell) + (y // cell)) % 2],
            )
    return canvas


def audit_placement(blob, matrix, crop, min_dpi, min_visible_pixels):
    """Measure real embedded pixels at their actual transformed physical size.

    matrix maps uncropped picture-frame UV to slide inches. Alpha is assessed
    before resampling; transparent padding cannot inflate visible pixel support.
    No image is edited and no white-fringe detection is inferred from alpha.
    """
    errors = []
    try:
        with Image.open(io.BytesIO(blob)) as image:
            rgba = image.convert('RGBA')
        w,h = rgba.size
        l,t,r,b = crop
        if not all(math.isfinite(v) and 0 <= v < 1 for v in crop) or l+r >= 1 or t+b >= 1:
            raise ValueError('unsupported/invalid crop')
        box = (math.ceil(l*w),math.ceil(t*h),math.floor((1-r)*w),math.floor((1-b)*h))
        if box[2] <= box[0] or box[3] <= box[1]:
            raise ValueError('crop has no complete source pixels')
        visible = alpha_bbox(rgba,8)
        cut = alpha_bbox(rgba.crop(box),8)
        if not visible or not cut:
            raise ValueError('no visible pixels in placed asset')
        if visible[0] < box[0] or visible[1] < box[1] or visible[2] > box[2] or visible[3] > box[3]:
            errors.append('crop removes alpha-visible source pixels')
        physical_w = math.hypot(matrix[0],matrix[1])
        physical_h = math.hypot(matrix[2],matrix[3])
        if min(physical_w,physical_h) <= 0:
            raise ValueError('nonpositive physical placement')
        dpi = [(1-l-r)*w/physical_w,(1-t-b)*h/physical_h]
        support = [cut[2]-cut[0],cut[3]-cut[1]]
        if min(dpi) < min_dpi:
            errors.append('effective resolution below predeclared min_dpi')
        if min(support) < min_visible_pixels:
            errors.append('visible subject pixels below predeclared minimum')
        expected_ratio = (1-l-r)*w/((1-t-b)*h)
        if abs((physical_w/physical_h)/expected_ratio-1) > .005:
            errors.append('picture aspect ratio distorted beyond 0.5% serialization allowance')
        return dict(errors=errors,effective_dpi=dpi,visible_pixels=support,
                    visible_inches=[support[0]/dpi[0],support[1]/dpi[1]],
                    edge_color_review='NOT_VERIFIED')
    except (OSError,ValueError,TypeError) as exc:
        return {'errors':[str(exc)],'edge_color_review':'NOT_VERIFIED'}


def build_contact_sheet(report: dict[str, Any], output: Path) -> None:
    items = report["assets"]
    cell_w, cell_h, columns = 260, 210, 4
    rows = max(1, math.ceil(len(items) / columns))
    sheet = Image.new("RGB", (columns * cell_w, rows * cell_h), "white")
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("Arial.ttf", 13)
    except OSError:
        font = ImageFont.load_default()
    for index, item in enumerate(items):
        col, row = index % columns, index // columns
        x0, y0 = col * cell_w, row * cell_h
        draw.text((x0 + 8, y0 + 8), Path(item["path"]).name[:34], fill="#17212E", font=font)
        status = "ERROR" if item["errors"] else "RISK" if item["risks"] else "PASS"
        color = "#B42318" if status != "PASS" else "#087A55"
        draw.text((x0 + 8, y0 + 28), status, fill=color, font=font)
        if item.get("size"):
            draw.text((x0 + 62, y0 + 28), f"{item['size'][0]}x{item['size'][1]}", fill="#596579", font=font)
        preview = checkerboard(220, 132).convert("RGBA")
        try:
            with Image.open(item["path"]) as opened:
                icon = ImageOps.exif_transpose(opened).convert("RGBA")
                icon.thumbnail((204, 116), Image.Resampling.LANCZOS)
                preview.alpha_composite(icon, ((220 - icon.width) // 2, (132 - icon.height) // 2))
        except Exception:
            pass
        sheet.paste(preview.convert("RGB"), (x0 + 20, y0 + 54))
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Raster asset file or directory")
    parser.add_argument("--json", dest="json_path", type=Path, help="Optional JSON report")
    parser.add_argument("--contact-sheet", type=Path, help="Optional checkerboard contact sheet")
    parser.add_argument("--alpha-threshold", type=int, default=8)
    parser.add_argument("--edge-risk-ratio", type=float, default=0.02)
    parser.add_argument("--min-long-edge", type=int, default=32)
    parser.add_argument("--min-occupancy", type=float, default=0.05)
    parser.add_argument("--max-occupancy", type=float, default=0.96)
    parser.add_argument("--fail-on-risk", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not 0 <= args.alpha_threshold <= 254:
        print("ERROR: --alpha-threshold must be between 0 and 254", file=sys.stderr)
        return 2
    if not 0 <= args.edge_risk_ratio <= 0.2:
        print("ERROR: --edge-risk-ratio must be between 0 and 0.2", file=sys.stderr)
        return 2
    if not 0 <= args.min_occupancy < args.max_occupancy <= 1:
        print("ERROR: occupancy thresholds must satisfy 0 <= min < max <= 1", file=sys.stderr)
        return 2

    files = collect_files(args.input)
    if not files:
        print(f"ERROR: no supported raster assets found: {args.input}", file=sys.stderr)
        return 2
    assets = [
        audit_asset(
            path,
            args.alpha_threshold,
            args.edge_risk_ratio,
            args.min_long_edge,
            args.min_occupancy,
            args.max_occupancy,
        )
        for path in files
    ]
    report = {
        "input": str(args.input.resolve()),
        "assets": assets,
        "summary": {
            "assets": len(assets),
            "errors": sum(len(item["errors"]) for item in assets),
            "risks": sum(len(item["risks"]) for item in assets),
            "warnings": sum(len(item["warnings"]) for item in assets),
        },
    }
    if args.json_path:
        args.json_path.parent.mkdir(parents=True, exist_ok=True)
        args.json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.contact_sheet:
        build_contact_sheet(report, args.contact_sheet)

    summary = report["summary"]
    print(
        "Raster asset audit: "
        f"assets={summary['assets']}, errors={summary['errors']}, "
        f"risks={summary['risks']}, warnings={summary['warnings']}"
    )
    for item in assets:
        for level in ("errors", "risks", "warnings"):
            for message in item[level]:
                print(f"{level[:-1].upper()}: {Path(item['path']).name}: {message}")
    if summary["errors"] or (args.fail_on_risk and summary["risks"]):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
