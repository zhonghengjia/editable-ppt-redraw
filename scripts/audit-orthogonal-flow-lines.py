#!/usr/bin/env python3
"""Audit named flow-line geometry, route continuity, and shared buses."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any


DEFAULT_INCLUDE = r"(?i)(?:^|[-_])(flow|connector|route|segment|bus|link)(?:[-_]|$)"
ROUTE_SEGMENT_RE = re.compile(
    r"^(?P<route>.+?)[-_]segment(?:[-_])?(?P<index>\d+)$",
    re.IGNORECASE,
)
BUS_RE = re.compile(
    r"^(?P<bus>.+?)[-_]bus(?:[-_](?P<index>\d+))?$",
    re.IGNORECASE,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Check named line shapes in Artifact Tool layout JSON for axis alignment, "
            "sequential route continuity, branch-to-bus attachment, and duplicate buses."
        )
    )
    parser.add_argument("input", type=Path, help="A .layout.json file or directory containing them")
    parser.add_argument("--include-regex", default=DEFAULT_INCLUDE, help="Regex selecting flow-line names")
    parser.add_argument("--allow-regex", default=None, help="Regex for documented intentional exceptions")
    parser.add_argument("--tolerance", type=float, default=0.05, help="Endpoint/coordinate/rotation tolerance")
    parser.add_argument(
        "--alignment-tolerance",
        type=float,
        default=1.0,
        help="Maximum offset treated as a suspicious near-parallel bus",
    )
    parser.add_argument("--require-matches", action="store_true", help="Fail when no named flow lines are found")
    parser.add_argument("--fail-on-risk", action="store_true", help="Return a nonzero exit code when issues exist")
    parser.add_argument("--json", dest="json_path", type=Path, help="Optional JSON report path")
    args = parser.parse_args()
    if args.tolerance < 0:
        parser.error("--tolerance must be non-negative")
    if args.alignment_tolerance < args.tolerance:
        parser.error("--alignment-tolerance must be greater than or equal to --tolerance")
    return args


def layout_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    if path.is_dir():
        return sorted(path.rglob("*.layout.json"))
    raise FileNotFoundError(path)


def number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def make_line(name: str, bbox: list[Any], rotation: float, tolerance: float) -> dict[str, Any]:
    left, top, raw_width, raw_height = (number(value) for value in bbox)
    width = abs(raw_width)
    height = abs(raw_height)
    if width <= tolerance and height <= tolerance:
        orientation = "point"
    elif width <= tolerance:
        orientation = "vertical"
    elif height <= tolerance:
        orientation = "horizontal"
    else:
        orientation = "diagonal"
    return {
        "name": name,
        "bbox": bbox,
        "rotation": rotation,
        "orientation": orientation,
        "endpoints": [(left, top), (left + raw_width, top + raw_height)],
    }


def endpoint_gap(first: dict[str, Any], second: dict[str, Any]) -> float:
    return min(
        max(abs(ax - bx), abs(ay - by))
        for ax, ay in first["endpoints"]
        for bx, by in second["endpoints"]
    )


def point_on_line(point: tuple[float, float], line: dict[str, Any], tolerance: float) -> bool:
    x, y = point
    (x1, y1), (x2, y2) = line["endpoints"]
    if line["orientation"] == "horizontal":
        return abs(y - y1) <= tolerance and min(x1, x2) - tolerance <= x <= max(x1, x2) + tolerance
    if line["orientation"] == "vertical":
        return abs(x - x1) <= tolerance and min(y1, y2) - tolerance <= y <= max(y1, y2) + tolerance
    return False


def projected_overlap(first: dict[str, Any], second: dict[str, Any]) -> float:
    if first["orientation"] == "horizontal":
        first_values = [point[0] for point in first["endpoints"]]
        second_values = [point[0] for point in second["endpoints"]]
    else:
        first_values = [point[1] for point in first["endpoints"]]
        second_values = [point[1] for point in second["endpoints"]]
    return min(max(first_values), max(second_values)) - max(min(first_values), min(second_values))


def constant_coordinate(line: dict[str, Any]) -> float:
    (x1, y1), _ = line["endpoints"]
    return y1 if line["orientation"] == "horizontal" else x1


def topology_issues(
    path: Path,
    lines: list[dict[str, Any]],
    tolerance: float,
    alignment_tolerance: float,
) -> tuple[list[dict[str, Any]], int, int]:
    issues: list[dict[str, Any]] = []
    routes: dict[str, list[tuple[int, dict[str, Any]]]] = defaultdict(list)
    buses: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for line in lines:
        route_match = ROUTE_SEGMENT_RE.match(line["name"])
        if route_match:
            routes[route_match.group("route").lower()].append((int(route_match.group("index")), line))
        bus_match = BUS_RE.match(line["name"])
        if bus_match:
            buses[bus_match.group("bus").lower()].append(line)

    for route_id, indexed_lines in routes.items():
        by_index: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for index, line in indexed_lines:
            by_index[index].append(line)
        duplicates = sorted(index for index, members in by_index.items() if len(members) > 1)
        if duplicates:
            issues.append(
                {
                    "file": str(path),
                    "name": route_id,
                    "risk": "duplicate-route-segment-index",
                    "indices": duplicates,
                }
            )

        indices = sorted(by_index)
        expected = list(range(1, indices[-1] + 1)) if indices else []
        if indices != expected:
            issues.append(
                {
                    "file": str(path),
                    "name": route_id,
                    "risk": "route-segment-numbering-gap",
                    "indices": indices,
                    "expected": expected,
                }
            )

        for first_index, second_index in zip(indices, indices[1:]):
            first = by_index[first_index][0]
            second = by_index[second_index][0]
            gap = endpoint_gap(first, second)
            if gap > tolerance:
                issues.append(
                    {
                        "file": str(path),
                        "name": route_id,
                        "risk": "disconnected-route",
                        "segments": [first["name"], second["name"]],
                        "gap": gap,
                    }
                )

    for bus_id, bus_lines in buses.items():
        valid_buses = [line for line in bus_lines if line["orientation"] in {"horizontal", "vertical"}]
        for first, second in combinations(valid_buses, 2):
            if first["orientation"] != second["orientation"]:
                continue
            overlap = projected_overlap(first, second)
            if overlap <= tolerance:
                continue
            offset = abs(constant_coordinate(first) - constant_coordinate(second))
            if offset <= tolerance:
                risk = "duplicate-overlapping-bus"
            elif offset <= alignment_tolerance:
                risk = "misaligned-parallel-bus"
            else:
                continue
            issues.append(
                {
                    "file": str(path),
                    "name": bus_id,
                    "risk": risk,
                    "buses": [first["name"], second["name"]],
                    "offset": offset,
                    "overlap": overlap,
                }
            )

        branch_prefixes = (f"{bus_id}-", f"{bus_id}_")
        for route_id, indexed_lines in routes.items():
            if not route_id.startswith(branch_prefixes):
                continue
            branch_endpoints = [endpoint for _, line in indexed_lines for endpoint in line["endpoints"]]
            if not any(
                point_on_line(endpoint, bus, tolerance)
                for endpoint in branch_endpoints
                for bus in valid_buses
            ):
                issues.append(
                    {
                        "file": str(path),
                        "name": route_id,
                        "risk": "route-misses-bus",
                        "buses": [line["name"] for line in valid_buses],
                    }
                )

    return issues, len(routes), sum(len(members) for members in buses.values())


def audit_file(
    path: Path,
    include: re.Pattern[str],
    allow: re.Pattern[str] | None,
    tolerance: float,
    alignment_tolerance: float,
) -> tuple[int, list[dict[str, Any]], int, int, int]:
    data = json.loads(path.read_text(encoding="utf-8"))
    elements = data.get("elements", [])
    matched = 0
    allowed = 0
    issues: list[dict[str, Any]] = []
    lines: list[dict[str, Any]] = []

    for element in elements:
        if element.get("geometry") != "line":
            continue
        name = str(element.get("name") or "")
        if not include.search(name):
            continue
        matched += 1
        if allow and allow.search(name):
            allowed += 1
            continue

        bbox = element.get("bbox") or []
        if len(bbox) != 4:
            issues.append({"file": str(path), "name": name, "risk": "missing-or-invalid-bbox", "bbox": bbox})
            continue

        width = abs(number(bbox[2]))
        height = abs(number(bbox[3]))
        rotation = number(element.get("rotation")) % 360.0
        rotation_distance = min(rotation, abs(rotation - 360.0))
        lines.append(make_line(name, bbox, rotation, tolerance))

        if width <= tolerance and height <= tolerance:
            issues.append({"file": str(path), "name": name, "risk": "zero-length", "bbox": bbox})
        if width > tolerance and height > tolerance:
            issues.append({"file": str(path), "name": name, "risk": "diagonal-bbox", "bbox": bbox})
        if rotation_distance > tolerance:
            issues.append(
                {
                    "file": str(path),
                    "name": name,
                    "risk": "rotated-line",
                    "rotation": rotation,
                    "bbox": bbox,
                }
            )

    route_issues, route_count, bus_count = topology_issues(
        path,
        lines,
        tolerance,
        alignment_tolerance,
    )
    issues.extend(route_issues)
    return matched, issues, allowed, route_count, bus_count


def main() -> int:
    args = parse_args()
    try:
        files = layout_files(args.input)
    except FileNotFoundError:
        print(f"Input not found: {args.input}", file=sys.stderr)
        return 2

    if not files:
        print(f"No .layout.json files found under: {args.input}", file=sys.stderr)
        return 2

    include = re.compile(args.include_regex)
    allow = re.compile(args.allow_regex) if args.allow_regex else None
    total_matched = 0
    total_allowed = 0
    total_routes = 0
    total_buses = 0
    issues: list[dict[str, Any]] = []

    for path in files:
        matched, file_issues, allowed, route_count, bus_count = audit_file(
            path,
            include,
            allow,
            args.tolerance,
            args.alignment_tolerance,
        )
        total_matched += matched
        total_allowed += allowed
        total_routes += route_count
        total_buses += bus_count
        issues.extend(file_issues)

    if args.require_matches and total_matched == 0:
        issues.append({"file": str(args.input), "name": "", "risk": "no-matching-flow-lines"})

    report = {
        "input": str(args.input),
        "files": len(files),
        "matched_flow_lines": total_matched,
        "continuity_routes": total_routes,
        "named_buses": total_buses,
        "allowed_exceptions": total_allowed,
        "issues": issues,
        "issue_count": len(issues),
        "status": "pass" if not issues else "fail",
    }

    if args.json_path:
        args.json_path.parent.mkdir(parents=True, exist_ok=True)
        args.json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        "Orthogonal flow-line audit: "
        f"files={len(files)}, matched={total_matched}, routes={total_routes}, "
        f"buses={total_buses}, allowed={total_allowed}, issues={len(issues)}"
    )
    for issue in issues:
        details = []
        for key in ("bbox", "rotation", "indices", "expected", "segments", "gap", "buses", "offset", "overlap"):
            if key in issue:
                details.append(f"{key}={issue[key]}")
        suffix = f" | {', '.join(details)}" if details else ""
        print(f"- {issue['risk']}: {issue.get('name') or '(unnamed)'} ({issue['file']}){suffix}")

    if issues and args.fail_on_risk:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
