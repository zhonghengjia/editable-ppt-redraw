#!/usr/bin/env python3
"""Audit source curve traces against native custom geometry in a delivered PPTX."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from curve_fidelity_lib import detect_peaks, interpolate_profile, x_aligned_mae


NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
}


def tag_name(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def point_from(node: ET.Element) -> tuple[float, float]:
    raw_x, raw_y = node.attrib.get("x"), node.attrib.get("y")
    if raw_x is None or raw_y is None:
        raise ValueError("path point lacks x or y")
    return float(raw_x), float(raw_y)


def sample_cubic(start: tuple[float, float], controls: list[tuple[float, float]], steps: int = 16) -> list[tuple[float, float]]:
    c1, c2, end = controls
    result: list[tuple[float, float]] = []
    for index in range(1, steps + 1):
        t = index / steps
        u = 1.0 - t
        x = u**3 * start[0] + 3 * u * u * t * c1[0] + 3 * u * t * t * c2[0] + t**3 * end[0]
        y = u**3 * start[1] + 3 * u * u * t * c1[1] + 3 * u * t * t * c2[1] + t**3 * end[1]
        result.append((x, y))
    return result


def sample_quadratic(start: tuple[float, float], controls: list[tuple[float, float]], steps: int = 16) -> list[tuple[float, float]]:
    control, end = controls
    result: list[tuple[float, float]] = []
    for index in range(1, steps + 1):
        t = index / steps
        u = 1.0 - t
        result.append(
            (
                u * u * start[0] + 2 * u * t * control[0] + t * t * end[0],
                u * u * start[1] + 2 * u * t * control[1] + t * t * end[1],
            )
        )
    return result


def parse_custom_path(path: ET.Element) -> list[tuple[float, float]]:
    width = float(path.attrib.get("w", "0"))
    height = float(path.attrib.get("h", "0"))
    if width <= 0 or height <= 0:
        raise ValueError("custom geometry path has non-positive width or height")
    points: list[tuple[float, float]] = []
    current: tuple[float, float] | None = None
    contour_start: tuple[float, float] | None = None
    for command in list(path):
        name = tag_name(command)
        raw_points = [point_from(node) for node in command.findall("./a:pt", NS)]
        if name == "moveTo" and raw_points:
            current = raw_points[0]
            contour_start = current
            points.append(current)
        elif name == "lnTo" and raw_points and current is not None:
            current = raw_points[0]
            points.append(current)
        elif name == "cubicBezTo" and len(raw_points) == 3 and current is not None:
            sampled = sample_cubic(current, raw_points)
            points.extend(sampled)
            current = raw_points[-1]
        elif name == "quadBezTo" and len(raw_points) == 2 and current is not None:
            sampled = sample_quadratic(current, raw_points)
            points.extend(sampled)
            current = raw_points[-1]
        elif name == "close" and current is not None and contour_start is not None:
            if current != contour_start:
                points.append(contour_start)
            current = contour_start
        elif name in {"arcTo"}:
            raise ValueError("arcTo is not supported by the curve fidelity auditor")
    if len(points) < 2:
        raise ValueError("custom geometry path has fewer than two sampled points")
    return [(x / width, y / height) for x, y in points]


def profile_from_closed_geometry(points: list[tuple[float, float]], count: int = 201) -> list[tuple[float, float]]:
    """Convert a filled path into its upper visible envelope on an x grid."""
    candidates: list[list[float]] = [[] for _ in range(count)]
    for start, end in zip(points, points[1:]):
        x0, y0 = start
        x1, y1 = end
        left = max(0, min(count - 1, int(math.floor(min(x0, x1) * (count - 1)))))
        right = max(0, min(count - 1, int(math.ceil(max(x0, x1) * (count - 1)))))
        if abs(x1 - x0) <= 1e-12:
            candidates[left].append(min(y0, y1))
            continue
        for index in range(left, right + 1):
            x = index / (count - 1)
            fraction = (x - x0) / (x1 - x0)
            if -1e-9 <= fraction <= 1.0 + 1e-9:
                candidates[index].append(y0 + fraction * (y1 - y0))
    raw: list[tuple[float, float]] = []
    for index, ys in enumerate(candidates):
        if ys:
            raw.append((index / (count - 1), 1.0 - min(ys)))
    profile = interpolate_profile(raw, count)
    maximum = max(y for _, y in profile)
    if maximum <= 0:
        raise ValueError("custom geometry has zero profile amplitude")
    return [(x, y / maximum) for x, y in profile]


def collect_pptx_profiles(path: Path) -> tuple[dict[str, list[tuple[float, float]]], int, list[str]]:
    profiles: dict[str, list[tuple[float, float]]] = {}
    warnings: list[str] = []
    with zipfile.ZipFile(path) as package:
        slide_parts = sorted(
            name for name in package.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)
        )
        for part in slide_parts:
            root = ET.fromstring(package.read(part))
            for shape in root.findall(".//p:sp", NS):
                properties = shape.find("./p:nvSpPr/p:cNvPr", NS)
                name = properties.attrib.get("name", "") if properties is not None else ""
                if not name.strip():
                    continue
                custom_paths = shape.findall("./p:spPr/a:custGeom/a:pathLst/a:path", NS)
                if not custom_paths:
                    continue
                try:
                    sampled = parse_custom_path(max(custom_paths, key=lambda item: len(list(item))))
                    profiles[name] = profile_from_closed_geometry(sampled)
                except ValueError as exc:
                    warnings.append(f"shape {name!r} could not be sampled: {exc}")
    return profiles, len(slide_parts), warnings


def load_source_trace(path: Path) -> tuple[list[tuple[float, float]], list[dict[str, float]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_points = payload.get("points") if isinstance(payload, dict) else None
    if not isinstance(raw_points, list):
        raise ValueError(f"{path} has no points list")
    profile = interpolate_profile(raw_points)
    raw_peaks = payload.get("peaks", []) if isinstance(payload, dict) else []
    peaks = [item for item in raw_peaks if isinstance(item, dict) and isinstance(item.get("x"), (int, float))]
    return profile, peaks


def audit_curve_fidelity(manifest: dict[str, Any], manifest_path: Path, output: Path) -> dict[str, Any]:
    issues: list[str] = []
    warnings: list[str] = []
    contract = manifest.get("curve_fidelity")
    if not isinstance(contract, dict):
        return {"valid": False, "issues": ["manifest does not contain curve_fidelity"], "warnings": [], "series": {}, "stats": {}}
    series = contract.get("series")
    if not isinstance(series, list) or not series:
        return {"valid": False, "issues": ["curve_fidelity.series must be non-empty"], "warnings": [], "series": {}, "stats": {}}

    profiles, slide_count, pptx_warnings = collect_pptx_profiles(output)
    warnings.extend(pptx_warnings)
    default_mae = float(contract.get("default_max_x_aligned_mae", 0.08))
    default_peak_tolerance = float(contract.get("default_peak_x_tolerance", 0.06))
    default_prominence = float(contract.get("default_peak_prominence", 0.08))
    default_distance = float(contract.get("default_min_peak_distance", 0.06))
    reports: dict[str, dict[str, Any]] = {}
    assigned_shapes: dict[str, str] = {}

    for index, spec in enumerate(series):
        if not isinstance(spec, dict):
            issues.append(f"curve_fidelity.series[{index}] is not an object")
            continue
        series_id = str(spec.get("id", f"series-{index}"))
        required = spec.get("required", True)
        pattern_text = spec.get("output_name_regex")
        try:
            pattern = re.compile(pattern_text) if isinstance(pattern_text, str) else None
        except re.error as exc:
            issues.append(f"curve series {series_id!r} has invalid output regex: {exc}")
            continue
        if pattern is None:
            issues.append(f"curve series {series_id!r} has no output regex")
            continue
        matched = sorted(name for name in profiles if pattern.search(name))
        expected_output_count = int(spec.get("expected_output_count", 1))
        if len(matched) != expected_output_count:
            message = f"curve series {series_id!r} matched {len(matched)} native paths; expected {expected_output_count}"
            (issues if required else warnings).append(message)
            reports[series_id] = {"matched_shapes": matched}
            continue
        for name in matched:
            if name in assigned_shapes:
                issues.append(
                    f"native path {name!r} is assigned to multiple curve series: {assigned_shapes[name]!r}, {series_id!r}"
                )
            assigned_shapes[name] = series_id

        trace_value = spec.get("source_trace")
        if not isinstance(trace_value, str) or not trace_value.strip():
            issues.append(f"curve series {series_id!r} has no source_trace")
            continue
        trace_path = (manifest_path.parent / trace_value).resolve()
        try:
            source_profile, recorded_source_peaks = load_source_trace(trace_path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            issues.append(f"curve series {series_id!r} source trace cannot be read: {exc}")
            continue

        output_profile = profiles[matched[0]]
        maximum_mae = float(spec.get("max_x_aligned_mae", default_mae))
        mae = x_aligned_mae(source_profile, output_profile)
        prominence = float(spec.get("peak_prominence", default_prominence))
        min_distance = float(spec.get("min_peak_distance", default_distance))
        source_peaks = recorded_source_peaks or detect_peaks(
            source_profile, min_prominence=prominence, min_distance_fraction=min_distance
        )
        output_peaks = detect_peaks(
            output_profile, min_prominence=prominence, min_distance_fraction=min_distance
        )
        explicit_positions = spec.get("expected_peak_positions")
        if isinstance(explicit_positions, list):
            expected_positions = [float(value) for value in explicit_positions]
        else:
            expected_positions = [float(item["x"]) for item in source_peaks]
        expected_count = int(spec.get("expected_peak_count", len(expected_positions)))
        peak_tolerance = float(spec.get("peak_x_tolerance", default_peak_tolerance))

        if mae > maximum_mae + 1e-12:
            issues.append(
                f"curve series {series_id!r} x-aligned MAE {mae:.4f} exceeds {maximum_mae:.4f}"
            )
        if len(output_peaks) != expected_count:
            issues.append(
                f"curve series {series_id!r} has {len(output_peaks)} prominent peaks; expected {expected_count}"
            )
        elif len(expected_positions) == len(output_peaks):
            for peak_index, (expected_x, observed) in enumerate(zip(sorted(expected_positions), output_peaks), start=1):
                if abs(expected_x - float(observed["x"])) > peak_tolerance + 1e-12:
                    issues.append(
                        f"curve series {series_id!r} peak {peak_index} x={observed['x']:.3f} differs from expected {expected_x:.3f} by more than {peak_tolerance:.3f}"
                    )
        reports[series_id] = {
            "matched_shapes": matched,
            "source_trace": str(trace_path),
            "x_aligned_mae": mae,
            "maximum_x_aligned_mae": maximum_mae,
            "expected_peak_count": expected_count,
            "source_peaks": source_peaks,
            "output_peaks": output_peaks,
            "peak_x_tolerance": peak_tolerance,
        }

    return {
        "valid": not issues,
        "issues": issues,
        "warnings": warnings,
        "series": reports,
        "stats": {
            "slide_count": slide_count,
            "native_custom_paths": len(profiles),
            "declared_series": len(series),
            "audited_series": len(reports),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit native PPTX curve geometry against source-coordinate traces.")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--json", dest="json_path", type=Path)
    parser.add_argument("--fail-on-risk", action="store_true")
    args = parser.parse_args()
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        report = audit_curve_fidelity(manifest, args.manifest.resolve(), args.output)
    except (OSError, json.JSONDecodeError, zipfile.BadZipFile, ET.ParseError) as exc:
        print(f"Cannot run curve-fidelity audit: {exc}", file=sys.stderr)
        return 2
    report["manifest"] = str(args.manifest.resolve())
    report["output"] = str(args.output.resolve())
    if args.json_path:
        args.json_path.parent.mkdir(parents=True, exist_ok=True)
        args.json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        "Curve fidelity: "
        f"valid={report['valid']}, issues={len(report['issues'])}, warnings={len(report['warnings'])}, stats={report['stats']}"
    )
    for message in report["issues"]:
        print(f"ISSUE: {message}")
    for message in report["warnings"]:
        print(f"WARNING: {message}")
    return 1 if args.fail_on_risk and report["issues"] else 0


if __name__ == "__main__":
    sys.exit(main())
