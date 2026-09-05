#!/usr/bin/env python3
"""Build repeatable source-versus-output crops for icon and module QA."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageOps


def load_font(size: int) -> ImageFont.ImageFont:
    for candidate in ("arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def normalize_render(rendered: Image.Image, size: tuple[int, int], fit: str) -> Image.Image:
    if rendered.size == size:
        return rendered
    if fit == "stretch":
        return rendered.resize(size, Image.Resampling.LANCZOS)
    if fit == "crop":
        return ImageOps.fit(rendered, size, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
    contained = ImageOps.contain(rendered, size, method=Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", size, "white")
    left = (size[0] - contained.width) // 2
    top = (size[1] - contained.height) // 2
    canvas.paste(contained, (left, top))
    return canvas


def load_regions(path: Path, canvas_size: tuple[int, int]) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    regions = data.get("regions") if isinstance(data, dict) else data
    if not isinstance(regions, list) or not regions:
        raise ValueError("regions JSON must be a non-empty list or an object with a non-empty regions list")
    validated: list[dict[str, Any]] = []
    canvas_width, canvas_height = canvas_size
    for index, region in enumerate(regions):
        if not isinstance(region, dict):
            raise ValueError(f"regions[{index}] must be an object")
        name = region.get("name")
        bbox = region.get("bbox")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"regions[{index}].name must be a non-empty string")
        if not isinstance(bbox, list) or len(bbox) != 4 or not all(isinstance(v, (int, float)) for v in bbox):
            raise ValueError(f"regions[{index}].bbox must be [left, top, width, height]")
        left, top, width, height = (int(round(float(v))) for v in bbox)
        if left < 0 or top < 0 or width <= 0 or height <= 0:
            raise ValueError(f"regions[{index}].bbox must use non-negative coordinates and positive size")
        if left + width > canvas_width or top + height > canvas_height:
            raise ValueError(f"regions[{index}].bbox extends outside the reference canvas")
        validated.append({"name": name.strip(), "box": (left, top, left + width, top + height)})
    return validated


def fit_crop(crop: Image.Image, max_size: tuple[int, int], zoom: float) -> Image.Image:
    width = max(1, int(round(crop.width * zoom)))
    height = max(1, int(round(crop.height * zoom)))
    enlarged = crop.resize((width, height), Image.Resampling.LANCZOS)
    enlarged.thumbnail(max_size, Image.Resampling.LANCZOS)
    return enlarged


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a source-versus-output contact sheet from explicit QA regions.")
    parser.add_argument("reference", type=Path, help="Reference image")
    parser.add_argument("rendered", type=Path, help="Rendered editable output")
    parser.add_argument("regions", type=Path, help="JSON regions using [left, top, width, height]")
    parser.add_argument("output", type=Path, help="Output contact-sheet PNG")
    parser.add_argument("--fit", choices=("stretch", "contain", "crop"), default="stretch", help="Align rendered canvas to reference")
    parser.add_argument("--zoom", type=float, default=4.0, help="Initial crop magnification before fitting")
    parser.add_argument("--columns", type=int, default=2, help="Number of region cells per row")
    parser.add_argument("--max-pane-width", type=int, default=420, help="Maximum width of each source/output pane")
    parser.add_argument("--max-pane-height", type=int, default=300, help="Maximum height of each source/output pane")
    args = parser.parse_args()

    if args.zoom <= 0 or args.columns <= 0 or args.max_pane_width <= 0 or args.max_pane_height <= 0:
        parser.error("zoom, columns, and pane dimensions must be positive")

    try:
        reference = Image.open(args.reference).convert("RGB")
        rendered = Image.open(args.rendered).convert("RGB")
        rendered = normalize_render(rendered, reference.size, args.fit)
        regions = load_regions(args.regions, reference.size)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    padding = 18
    title_height = 34
    footer_height = 28
    gap = 16
    pane_width = args.max_pane_width
    pane_height = args.max_pane_height
    cell_width = padding * 2 + pane_width * 2 + gap
    cell_height = padding * 2 + title_height + pane_height + footer_height
    rows = math.ceil(len(regions) / args.columns)
    sheet = Image.new("RGB", (cell_width * args.columns, cell_height * rows), "white")
    draw = ImageDraw.Draw(sheet)
    title_font = load_font(16)
    label_font = load_font(13)

    for index, region in enumerate(regions):
        row, column = divmod(index, args.columns)
        origin_x = column * cell_width
        origin_y = row * cell_height
        draw.rectangle(
            (origin_x, origin_y, origin_x + cell_width - 1, origin_y + cell_height - 1),
            outline="#D2D8E1",
            width=1,
        )
        draw.text((origin_x + padding, origin_y + 8), region["name"], fill="#111111", font=title_font)

        source_crop = fit_crop(reference.crop(region["box"]), (pane_width, pane_height), args.zoom)
        output_crop = fit_crop(rendered.crop(region["box"]), (pane_width, pane_height), args.zoom)
        pane_y = origin_y + padding + title_height
        source_x = origin_x + padding + (pane_width - source_crop.width) // 2
        output_base = origin_x + padding + pane_width + gap
        output_x = output_base + (pane_width - output_crop.width) // 2
        source_y = pane_y + (pane_height - source_crop.height) // 2
        output_y = pane_y + (pane_height - output_crop.height) // 2
        sheet.paste(source_crop, (source_x, source_y))
        sheet.paste(output_crop, (output_x, output_y))

        footer_y = origin_y + cell_height - padding - footer_height + 5
        draw.text((origin_x + padding, footer_y), "SOURCE", fill="#555555", font=label_font)
        draw.text((output_base, footer_y), "OUTPUT", fill="#555555", font=label_font)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(args.output)
    print(
        f"Comparison contact sheet: regions={len(regions)}, reference={reference.size}, "
        f"rendered_aligned={rendered.size}, output={args.output.resolve()}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
