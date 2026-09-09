#!/usr/bin/env python3
"""Extract an x-aligned editable curve trace from a local raster crop."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from curve_fidelity_lib import detect_peaks, interpolate_profile, valleys_between_peaks


def parse_bbox(value: str) -> tuple[int, int, int, int]:
    try:
        values = tuple(int(part.strip()) for part in value.split(","))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("bbox must be x,y,width,height") from exc
    if len(values) != 4 or values[0] < 0 or values[1] < 0 or values[2] <= 1 or values[3] <= 1:
        raise argparse.ArgumentTypeError("bbox must be non-negative x,y and positive width,height")
    return values


def parse_color(value: str) -> tuple[int, int, int]:
    text = value.strip().lstrip("#")
    if len(text) != 6:
        raise argparse.ArgumentTypeError("color must be #RRGGBB")
    try:
        return tuple(int(text[index : index + 2], 16) for index in (0, 2, 4))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("color must be #RRGGBB") from exc


def longest_gap(has_signal: np.ndarray) -> int:
    longest = current = 0
    for value in has_signal.tolist():
        if value:
            current = 0
        else:
            current += 1
            longest = max(longest, current)
    return longest


def extract_curve_trace(
    image_path: Path,
    bbox: tuple[int, int, int, int],
    colors: list[tuple[int, int, int]],
    *,
    tolerance: float = 60.0,
    mode: str = "upper_envelope",
    baseline_y: float | None = None,
    min_peak_prominence: float = 0.08,
    min_peak_distance: float = 0.06,
    smoothing_window: int = 5,
    min_column_coverage: float = 0.90,
    max_gap_fraction: float = 0.05,
) -> dict[str, object]:
    for name, value in (("min_column_coverage", min_column_coverage), ("max_gap_fraction", max_gap_fraction)):
        if not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError(f"{name} must be finite in [0, 1]")
    if not colors or not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError("nonempty colors and finite nonnegative tolerance required")
    if len(bbox) != 4 or min(bbox[:2]) < 0 or min(bbox[2:]) < 2:
        raise ValueError("invalid crop bbox")
    with Image.open(image_path) as source:
        rgb = source.convert("RGB")
        x, y, width, height = bbox
        if x + width > rgb.width or y + height > rgb.height:
            raise ValueError("bbox extends beyond the source image")
        crop = np.asarray(rgb.crop((x, y, x + width, y + height)), dtype=np.float32)

    targets = np.asarray(colors, dtype=np.float32)
    distances = np.sqrt(((crop[:, :, None, :] - targets[None, None, :, :]) ** 2).sum(axis=3))
    mask = distances.min(axis=2) <= float(tolerance)
    has_signal = mask.any(axis=0)
    if int(has_signal.sum()) < 2:
        raise ValueError("target colors produced fewer than two curve columns")

    selected = np.full(width, np.nan, dtype=np.float64)
    for column in range(width):
        ys = np.flatnonzero(mask[:, column])
        if not len(ys):
            continue
        if mode == "upper_envelope":
            selected[column] = float(ys.min())
        elif mode == "lower_envelope":
            selected[column] = float(ys.max())
        elif mode == "centerline":
            selected[column] = float(np.median(ys))
        else:
            raise ValueError(f"unsupported mode: {mode}")

    coverage = float(has_signal.mean())
    gap = longest_gap(has_signal)
    # Do not manufacture a complete trace across unobserved regions.
    if coverage < min_column_coverage or gap / width > max_gap_fraction or not has_signal[0] or not has_signal[-1]:
        return {
            "schema_version": 2, "status": "fail", "points": [], "peaks": [],
            "reason": "insufficient observed columns, excessive gap, or unobserved crop endpoints",
            "source_image": str(image_path.resolve()),
            "source_sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
            "bbox_px": list(bbox),
            "trace_quality": {"column_coverage": coverage, "longest_missing_run_px": gap,
                              "min_column_coverage": min_column_coverage, "max_gap_fraction": max_gap_fraction},
        }
    known = np.flatnonzero(~np.isnan(selected))
    all_columns = np.arange(width)
    selected = np.interp(all_columns, known, selected[known])

    if mode == "centerline":
        signal = 1.0 - selected / max(1.0, height - 1.0)
    else:
        baseline = float(height - 1 if baseline_y is None else baseline_y)
        if not math.isfinite(baseline) or baseline < 0 or baseline > height - 1:
            raise ValueError("baseline_y must be inside the crop")
        if mode == "upper_envelope":
            signal = np.maximum(0.0, baseline - selected)
        else:
            signal = np.maximum(0.0, selected - baseline)
        maximum = float(signal.max())
        if maximum <= 0:
            raise ValueError("extracted envelope has zero amplitude; check baseline or color")
        signal /= height - 1

    points = [[index / (width - 1), float(value)] for index, value in enumerate(signal)]
    profile = interpolate_profile(points)
    peaks = detect_peaks(
        profile,
        min_prominence=min_peak_prominence,
        min_distance_fraction=min_peak_distance,
        smoothing_window=smoothing_window,
    )
    valleys = valleys_between_peaks(profile, peaks)
    return {
        "schema_version": 2,
        "status": "pass",
        "normalization": "crop_height",
        "baseline_normalized": (float(height - 1 if baseline_y is None else baseline_y) / (height - 1)),
        "source_sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
        "source_image": str(image_path.resolve()),
        "bbox_px": list(bbox),
        "mode": mode,
        "target_colors": ["#%02X%02X%02X" % color for color in colors],
        "color_tolerance": float(tolerance),
        "points": points,
        "peaks": peaks,
        "valleys": valleys,
        "trace_quality": {
            "column_coverage": float(has_signal.mean()),
            "interpolated_columns": np.flatnonzero(~has_signal).tolist(),
            "min_column_coverage": min_column_coverage,
            "max_gap_fraction": max_gap_fraction,
            "longest_missing_run_px": longest_gap(has_signal),
            "width_px": width,
            "height_px": height,
        },
        "claim_boundary": "Visible raster geometry only; not recovered original numerical data.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract visible curve coordinates from a local image crop.")
    parser.add_argument("image", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--bbox", required=True, type=parse_bbox, help="x,y,width,height in source pixels")
    parser.add_argument("--color", action="append", required=True, type=parse_color, help="#RRGGBB; repeat for gradient colors")
    parser.add_argument("--tolerance", type=float, default=60.0)
    parser.add_argument("--mode", choices=("upper_envelope", "lower_envelope", "centerline"), default="upper_envelope")
    parser.add_argument("--baseline-y", type=float)
    parser.add_argument("--min-peak-prominence", type=float, default=0.08)
    parser.add_argument("--min-peak-distance", type=float, default=0.06)
    parser.add_argument("--smoothing-window", type=int, default=5)
    parser.add_argument("--min-column-coverage", type=float, default=0.90)
    parser.add_argument("--max-gap-fraction", type=float, default=0.05)
    args = parser.parse_args()
    try:
        report = extract_curve_trace(
            args.image,
            args.bbox,
            args.color,
            tolerance=args.tolerance,
            mode=args.mode,
            baseline_y=args.baseline_y,
            min_peak_prominence=args.min_peak_prominence,
            min_peak_distance=args.min_peak_distance,
            smoothing_window=args.smoothing_window,
            min_column_coverage=args.min_column_coverage,
            max_gap_fraction=args.max_gap_fraction,
        )
    except (OSError, ValueError) as exc:
        print(f"Cannot extract curve trace: {exc}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        "Curve trace: "
        f"points={len(report['points'])}, peaks={len(report['peaks'])}, "
        f"coverage={report['trace_quality']['column_coverage']:.3f}, output={args.output.resolve()}"
    )
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
