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
    point = float(raw_x), float(raw_y)
    if not all(math.isfinite(value) for value in point):
        raise ValueError("nonfinite path coordinate")
    return point


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
    if not all(math.isfinite(value) and value > 0 for value in (width, height)):
        raise ValueError("custom geometry path has non-positive width or height")
    points: list[tuple[float, float]] = []
    current: tuple[float, float] | None = None
    contour_start: tuple[float, float] | None = None
    for command in list(path):
        name = tag_name(command)
        raw_points = [point_from(node) for node in command.findall("./a:pt", NS)]
        if name == "moveTo" and raw_points:
            if contour_start is not None:
                raise ValueError("multiple contours in one path are unsupported")
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
        else:
            raise ValueError(f"unsupported or malformed path command: {name}")
    if len(points) < 2:
        raise ValueError("custom geometry path has fewer than two sampled points")
    return [(x / width, y / height) for x, y in points]


def profile_from_closed_geometry(points: list[tuple[float, float]], count: int = 201, mode: str = "upper_envelope") -> list[tuple[float, float]]:
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
            unique = {round(value, 9) for value in ys}
            if len(unique) > 2:
                raise ValueError("filled geometry has multiple intervals at one x; unsupported profile")
            raw.append((index / (count - 1), 1.0 - min(ys) if mode == "upper_envelope" else max(ys)))
    if len(raw) != count:
        raise ValueError("filled path does not cover the declared x coordinate frame")
    return raw


def _axis_transform(node: ET.Element, *, group: bool = False) -> tuple[float, float, float, float]:
    """DrawingML axis transform from child units to parent units, including flips."""
    if float(node.get("rot", "0")) % 21600000:
        raise ValueError("nonzero rotation is unsupported for x-aligned curve audit")
    off, ext = node.find("a:off", NS), node.find("a:ext", NS)
    if off is None or ext is None:
        raise ValueError("incomplete transform off/ext")
    x, y = float(off.get("x", "nan")), float(off.get("y", "nan"))
    w, h = float(ext.get("cx", "nan")), float(ext.get("cy", "nan"))
    cx, cy, cw, ch = 0., 0., 1., 1.
    if group:
        child_off, child_ext = node.find("a:chOff", NS), node.find("a:chExt", NS)
        if child_off is None or child_ext is None:
            raise ValueError("incomplete group child coordinate transform")
        cx, cy = float(child_off.get("x", "nan")), float(child_off.get("y", "nan"))
        cw, ch = float(child_ext.get("cx", "nan")), float(child_ext.get("cy", "nan"))
    if not all(math.isfinite(v) for v in (x, y, w, h, cx, cy, cw, ch)) or min(w, h, cw, ch) <= 0:
        raise ValueError("nonfinite or non-positive transform dimensions")
    sx, sy = w / cw, h / ch
    tx, ty = x - sx * cx, y - sy * cy
    for attribute in ("flipH", "flipV"):
        if node.get(attribute, "0") not in ("0", "1", "true", "false"):
            raise ValueError(f"invalid {attribute} transform flag")
    if node.get("flipH") in ("1", "true"):
        sx, tx = -sx, 2*x+w-tx
    if node.get("flipV") in ("1", "true"):
        sy, ty = -sy, 2*y+h-ty
    return sx, sy, tx, ty


def collect_pptx_profiles(path: Path) -> tuple[list[dict[str, Any]], int, list[str]]:
    """Inventory actual objects; names are selectors, never identity keys."""
    profiles: list[dict[str, Any]] = []
    warnings: list[str] = []
    with zipfile.ZipFile(path) as package:
        slide_parts = sorted(
            name for name in package.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)
        )
        for part in slide_parts:
            root = ET.fromstring(package.read(part))
            parents = {child: parent for parent in root.iter() for child in parent}
            for shape in root.findall(".//p:sp", NS):
                properties = shape.find("./p:nvSpPr/p:cNvPr", NS)
                name = properties.attrib.get("name", "") if properties is not None else ""
                if not name.strip():
                    continue
                custom_paths = shape.findall("./p:spPr/a:custGeom/a:pathLst/a:path", NS)
                for path_index, custom_path in enumerate(custom_paths or [None]):
                    record = {"name": name, "slide_part": part, "shape_id": properties.get("id"),
                              "path_index": path_index if custom_path is not None else None,
                              "path_count": len(custom_paths), "status": "supported"}
                    profiles.append(record)
                    try:
                        if custom_path is None:
                            raise ValueError("selected object has no native custom path")
                        sampled = parse_custom_path(custom_path)
                        record["closed"] = tag_name(list(custom_path)[-1]) == "close"
                        transforms = []
                        xfrm = shape.find("./p:spPr/a:xfrm", NS)
                        record["absolute_coordinates_available"] = xfrm is not None
                        if xfrm is not None:
                            transforms.append(_axis_transform(xfrm))
                        parent = parents.get(shape)
                        while parent is not None:
                            if tag_name(parent) == "grpSp":
                                group_xfrm = parent.find("./p:grpSpPr/a:xfrm", NS)
                                if xfrm is None or group_xfrm is None:
                                    raise ValueError("grouped shape lacks a complete coordinate transform")
                                transforms.append(_axis_transform(group_xfrm, group=True))
                            parent = parents.get(parent)
                        corners = [(0., 0.), (1., 1.)]
                        for sx, sy, tx, ty in transforms:
                            sampled = [(sx*x+tx, sy*y+ty) for x, y in sampled]
                            corners = [(sx*x+tx, sy*y+ty) for x, y in corners]
                        left, right = sorted(point[0] for point in corners)
                        top, bottom = sorted(point[1] for point in corners)
                        record["points"] = sampled
                        record["bbox_emu"] = [left, top, right-left, bottom-top]
                    except (ValueError, OverflowError) as exc:
                        record.update(status="unsupported", reason=str(exc))
                        warnings.append(f"{part} shape {record['shape_id']} path {record['path_index']}: {exc}")
    return profiles, len(slide_parts), warnings


def load_source_trace(path: Path) -> tuple[list[tuple[float, float]], list[dict[str, float]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and payload.get("status", "pass") != "pass":
        raise ValueError("source trace failed extraction evidence thresholds")
    raw_points = payload.get("points") if isinstance(payload, dict) else None
    if not isinstance(raw_points, list):
        raise ValueError(f"{path} has no points list")
    profile = interpolate_profile(raw_points)
    raw_peaks = payload.get("peaks", []) if isinstance(payload, dict) else []
    peaks = [item for item in raw_peaks if isinstance(item, dict) and isinstance(item.get("x"), (int, float))]
    return profile, peaks


def audit_curve_fidelity(manifest: dict[str, Any], manifest_path: Path, output: Path) -> dict[str, Any]:
    issues, warnings, reports = [], [], {}
    contract = manifest.get("curve_fidelity", {})
    series = contract.get("series") if isinstance(contract, dict) else None
    if not isinstance(series, list) or not series:
        return {"valid": False, "issues": ["curve_fidelity.series must be non-empty"],
                "warnings": [], "series": {}, "stats": {}}
    profiles, slide_count, _ = collect_pptx_profiles(output)
    assigned = {}
    for index, spec in enumerate(series):
        if not isinstance(spec, dict):
            issues.append(f"curve series {index} is not an object")
            continue
        sid = str(spec.get("id", f"series-{index}"))
        if sid in reports:
            issues.append(f"duplicate curve series id {sid!r}")
            continue
        report = reports[sid] = {"instances": []}
        findings = issues if spec.get("required", True) else warnings
        try:
            pattern = re.compile(spec["output_name_regex"])
            matched = [p for p in profiles if pattern.search(p["name"])]
            # Count objects before selecting their component path. Never merge equal names.
            objects = {}
            for path in matched:
                objects.setdefault((path["slide_part"], path["shape_id"]), []).append(path)
            report["matched_shapes"] = [p[0]["name"] for p in objects.values()]
            expected = spec.get("expected_output_count", 1)
            if isinstance(expected, bool) or not isinstance(expected, int) or expected < 1:
                raise ValueError("expected_output_count must be a positive integer")
            if len(objects) != expected:
                findings.append(f"curve series {sid!r} matched {len(objects)} native objects; expected {expected}")
            trace_path = (manifest_path.parent / spec["source_trace"]).resolve()
            source, recorded_peaks = load_source_trace(trace_path)
            payload = json.loads(trace_path.read_text(encoding="utf-8"))
            def threshold(key, default):
                value = float(spec.get(key, contract.get("default_" + key, default)))
                if not math.isfinite(value) or not 0 <= value <= 1:
                    raise ValueError(f"{key} must be finite in [0, 1]")
                return value
            maximum = threshold("max_x_aligned_mae", .08)
            tolerance = threshold("peak_x_tolerance", .06)
            prominence = threshold("peak_prominence", .08)
            distance = threshold("min_peak_distance", .06)
            source_peaks = recorded_peaks or detect_peaks(source, min_prominence=prominence, min_distance_fraction=distance)
            positions = spec.get("expected_peak_positions", [p["x"] for p in source_peaks])
            if not isinstance(positions, list) or any(isinstance(v, bool) or not isinstance(v, (float, int)) or not math.isfinite(v) or not 0 <= v <= 1 for v in positions):
                raise ValueError("expected_peak_positions must be finite normalized coordinates")
            expected_peaks = spec.get("expected_peak_count", len(positions))
            report.update(source_trace=str(trace_path), expected_peak_count=expected_peaks,
                          source_peaks=source_peaks, peak_x_tolerance=tolerance,
                          maximum_x_aligned_mae=maximum)
            for identity, paths in objects.items():
                selected = spec.get("output_path_index")
                if selected is None and len(paths) != 1:
                    findings.append(f"{identity}: multiple component paths require output_path_index")
                    continue
                if selected is not None and (isinstance(selected, bool) or not isinstance(selected, int) or selected < 0):
                    raise ValueError("output_path_index must be a nonnegative integer")
                candidates = paths if selected is None else [p for p in paths if p["path_index"] == selected]
                if len(candidates) != 1:
                    findings.append(f"{identity}: selected component path is missing")
                    continue
                record = candidates[0]
                key = (*identity, record["path_index"])
                if key in assigned:
                    findings.append(f"native path {key} is assigned to multiple curve series: {assigned[key]!r}, {sid!r}")
                assigned[key] = sid
                instance = {k: record[k] for k in ("name", "slide_part", "shape_id", "path_index", "status")}
                report["instances"].append(instance)
                try:
                    if record["status"] != "supported":
                        raise ValueError(record["reason"])
                    frame = spec.get("coordinate_frame", "shape")
                    if frame == "shape":
                        x, y, w, h = record["bbox_emu"]
                    elif frame == "slide_bbox" and record["absolute_coordinates_available"]:
                        box = spec.get("output_bbox")
                        if not isinstance(box, list) or len(box) != 4:
                            raise ValueError("slide_bbox requires output_bbox in slide inches")
                        x, y, w, h = [float(v) * 914400 for v in box]
                    else:
                        raise ValueError("unsupported or unresolved coordinate frame")
                    if not all(math.isfinite(v) for v in (x, y, w, h)) or min(w, h) <= 0:
                        raise ValueError("invalid coordinate frame dimensions")
                    points = [((px-x)/w, (py-y)/h) for px, py in record["points"]]
                    mode = spec.get("profile_mode", payload.get("mode", "upper_envelope"))
                    if record["closed"]:
                        if mode not in ("upper_envelope", "lower_envelope"):
                            raise ValueError("filled path requires explicit upper or lower envelope")
                        profile = profile_from_closed_geometry(points, mode=mode)
                        if payload.get("schema_version") == 1:
                            maximum_signal = max(value for _, value in profile)
                            if maximum_signal <= 0:
                                raise ValueError("legacy peak-normalized envelope has zero amplitude")
                            profile = [(px, value / maximum_signal) for px, value in profile]
                            instance["normalization"] = "legacy_peak_normalized; absolute amplitude not verified"
                        if payload.get("schema_version") == 2:
                            baseline = payload.get("baseline_normalized", 1 if mode == "upper_envelope" else 0)
                            profile = [(px, py + baseline - 1 if mode == "upper_envelope" else py - baseline) for px, py in profile]
                    else:
                        xs = [p[0] for p in points]
                        if not (all(a <= b for a, b in zip(xs, xs[1:])) or all(a >= b for a, b in zip(xs, xs[1:]))):
                            raise ValueError("open path is not a single-valued x profile")
                        if min(xs) > 1e-6 or max(xs) < 1-1e-6:
                            raise ValueError("open path does not cover the declared x frame")
                        profile = interpolate_profile([(px, 1-py) for px, py in points])
                    mae = x_aligned_mae(source, profile)
                    peaks = detect_peaks(profile, min_prominence=prominence, min_distance_fraction=distance)
                    instance.update(x_aligned_mae=mae, output_peaks=peaks,
                                    coordinate_frame=frame, absolute_coordinates_available=record["absolute_coordinates_available"])
                    if mae > maximum + 1e-12:
                        findings.append(f"curve series {sid!r} object {key} x-aligned MAE {mae:.4f} exceeds {maximum:.4f}")
                    if len(peaks) != expected_peaks:
                        findings.append(f"curve series {sid!r} object {key} has {len(peaks)} prominent peaks; expected {expected_peaks}")
                    elif len(positions) == len(peaks):
                        for target, peak in zip(sorted(positions), peaks):
                            if abs(target-peak["x"]) > tolerance + 1e-12:
                                findings.append(f"curve series {sid!r} object {key} peak x={peak['x']:.3f} differs from expected {target:.3f}")
                except (ValueError, TypeError, KeyError, OverflowError) as exc:
                    instance.update(status="NOT_VERIFIED", reason=str(exc))
                    findings.append(f"curve series {sid!r} object {key} not verified: {exc}")
        except (OSError, ValueError, TypeError, KeyError, re.error) as exc:
            findings.append(f"curve series {sid!r}: {exc}")
    return {"valid": not issues, "issues": issues, "warnings": warnings, "series": reports,
            "stats": {"slide_count": slide_count,
                      "native_custom_paths": sum(p["path_index"] is not None for p in profiles),
                      "declared_series": len(series), "audited_series": len(reports)}}


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
    except (OSError, ValueError, TypeError, zipfile.BadZipFile, ET.ParseError) as exc:
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
