#!/usr/bin/env python3
"""Create local overlay and difference diagnostics for a reference and rendered slide."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from PIL import Image, ImageChops, ImageFilter, ImageOps, ImageStat
except ImportError as exc:  # pragma: no cover - environment-dependent failure path
    raise SystemExit(
        "Pillow is required. Use the bundled presentation workspace Python; do not install packages."
    ) from exc


def configure_utf8_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8")


def align_reference(reference: Image.Image, size: tuple[int, int], fit: str) -> Image.Image:
    reference = reference.convert("RGB")
    if fit == "stretch":
        return reference.resize(size, Image.Resampling.LANCZOS)
    if fit == "crop":
        return ImageOps.fit(reference, size, method=Image.Resampling.LANCZOS)

    contained = ImageOps.contain(reference, size, method=Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", size, "white")
    x = (size[0] - contained.width) // 2
    y = (size[1] - contained.height) // 2
    canvas.paste(contained, (x, y))
    return canvas


def normalized_difference(first: Image.Image, second: Image.Image) -> tuple[float, float]:
    difference = ImageChops.difference(first, second)
    channel_means = ImageStat.Stat(difference).mean
    mean_absolute_difference = sum(channel_means) / len(channel_means) / 255.0
    similarity = max(0.0, 1.0 - mean_absolute_difference)
    return mean_absolute_difference, similarity


def changed_pixel_fraction(difference: Image.Image, threshold: int = 16) -> float:
    grayscale = difference.convert("L")
    histogram = grayscale.histogram()
    changed = sum(histogram[threshold + 1 :])
    total = grayscale.width * grayscale.height
    return changed / total if total else 0.0


def foreground_mask(first: Image.Image, second: Image.Image, threshold: int = 16) -> Image.Image:
    first_ink = ImageOps.invert(first.convert("L"))
    second_ink = ImageOps.invert(second.convert("L"))
    union = ImageChops.lighter(first_ink, second_ink)
    return union.point(lambda value: 255 if value > threshold else 0)


def mask_fraction(mask: Image.Image) -> float:
    histogram = mask.histogram()
    selected = histogram[255]
    total = mask.width * mask.height
    return selected / total if total else 0.0


def masked_difference_metrics(
    difference: Image.Image, mask: Image.Image, threshold: int = 16
) -> tuple[float, float, float]:
    selected = mask.histogram()[255]
    if selected == 0:
        return 0.0, 1.0, 0.0
    channel_means = ImageStat.Stat(difference, mask=mask).mean
    mean_absolute_difference = sum(channel_means) / len(channel_means) / 255.0
    similarity = max(0.0, 1.0 - mean_absolute_difference)
    changed_mask = difference.convert("L").point(lambda value: 255 if value > threshold else 0)
    changed_foreground = ImageChops.multiply(changed_mask, mask).histogram()[255]
    changed_fraction = changed_foreground / selected
    return mean_absolute_difference, similarity, changed_fraction


def compare_images(reference_path: Path, rendered_path: Path, fit: str) -> tuple[dict[str, object], Image.Image, Image.Image]:
    with Image.open(reference_path) as reference_source, Image.open(rendered_path) as rendered_source:
        original_reference_size = reference_source.size
        original_rendered_size = rendered_source.size
        rendered = rendered_source.convert("RGB")
        reference = align_reference(reference_source, rendered.size, fit)

    difference = ImageChops.difference(reference, rendered)
    mean_absolute_difference, pixel_similarity = normalized_difference(reference, rendered)
    content_mask = foreground_mask(reference, rendered, 16)
    (
        foreground_mean_absolute_difference,
        foreground_pixel_similarity,
        foreground_changed_fraction,
    ) = masked_difference_metrics(difference, content_mask, 16)

    reference_edges = reference.convert("L").filter(ImageFilter.FIND_EDGES)
    rendered_edges = rendered.convert("L").filter(ImageFilter.FIND_EDGES)
    edge_difference = ImageChops.difference(reference_edges, rendered_edges)
    edge_mean = ImageStat.Stat(edge_difference).mean[0] / 255.0
    edge_similarity = max(0.0, 1.0 - edge_mean)
    edge_mask = ImageChops.lighter(reference_edges, rendered_edges).point(
        lambda value: 255 if value > 16 else 0
    )
    _, edge_foreground_similarity, _ = masked_difference_metrics(
        edge_difference.convert("RGB"), edge_mask, 16
    )

    overlay = Image.blend(reference, rendered, 0.5)
    heatmap_source = ImageOps.autocontrast(difference.convert("L"))
    heatmap = ImageOps.colorize(heatmap_source, black="#FFFFFF", white="#D73027")

    metrics: dict[str, object] = {
        "reference": str(reference_path.resolve()),
        "rendered_slide": str(rendered_path.resolve()),
        "reference_size": {"width": original_reference_size[0], "height": original_reference_size[1]},
        "rendered_size": {"width": original_rendered_size[0], "height": original_rendered_size[1]},
        "alignment_fit": fit,
        "mean_absolute_difference": round(mean_absolute_difference, 6),
        "pixel_similarity": round(pixel_similarity, 6),
        "foreground_coverage": round(mask_fraction(content_mask), 6),
        "foreground_mean_absolute_difference": round(foreground_mean_absolute_difference, 6),
        "foreground_pixel_similarity": round(foreground_pixel_similarity, 6),
        "foreground_changed_fraction_above_16": round(foreground_changed_fraction, 6),
        "edge_similarity": round(edge_similarity, 6),
        "foreground_edge_similarity": round(edge_foreground_similarity, 6),
        "changed_pixel_fraction_above_16": round(changed_pixel_fraction(difference, 16), 6),
        "interpretation": (
            "Metrics are diagnostic only. Inspect the overlay and difference image, and pair this "
            "result with the PPTX editability audit."
        ),
    }
    return metrics, overlay, heatmap


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare a local reference image with a rendered PowerPoint slide."
    )
    parser.add_argument("reference", type=Path, help="Reference image")
    parser.add_argument("rendered_slide", type=Path, help="Rendered slide image")
    parser.add_argument("--output-dir", type=Path, required=True, help="Directory for diagnostic outputs")
    parser.add_argument("--prefix", default="comparison", help="Output filename prefix")
    parser.add_argument(
        "--fit",
        choices=("contain", "crop", "stretch"),
        default="contain",
        help="How to align the reference to the rendered slide canvas (default: contain)",
    )
    return parser.parse_args()


def main() -> int:
    configure_utf8_console()
    args = parse_args()
    for path, label in ((args.reference, "reference"), (args.rendered_slide, "rendered slide")):
        if not path.is_file():
            print(f"ERROR: {label} image not found: {path}", file=sys.stderr)
            return 2

    args.output_dir.mkdir(parents=True, exist_ok=True)
    overlay_path = args.output_dir / f"{args.prefix}-overlay.png"
    difference_path = args.output_dir / f"{args.prefix}-difference.png"
    metrics_path = args.output_dir / f"{args.prefix}-metrics.json"

    try:
        metrics, overlay, heatmap = compare_images(args.reference, args.rendered_slide, args.fit)
        overlay.save(overlay_path)
        heatmap.save(difference_path)
        metrics.update(
            {
                "overlay": str(overlay_path.resolve()),
                "difference": str(difference_path.resolve()),
            }
        )
        metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    except (OSError, ValueError) as exc:
        print(f"ERROR: Could not compare images: {exc}", file=sys.stderr)
        return 2

    print(
        "Comparison: "
        f"foreground_similarity={metrics['foreground_pixel_similarity']:.4f}, "
        f"foreground_edge_similarity={metrics['foreground_edge_similarity']:.4f}, "
        f"foreground_changed_fraction={metrics['foreground_changed_fraction_above_16']:.4f}, "
        f"whole_slide_similarity={metrics['pixel_similarity']:.4f}"
    )
    print(f"Overlay: {overlay_path.resolve()}")
    print(f"Difference: {difference_path.resolve()}")
    print(f"Metrics: {metrics_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
