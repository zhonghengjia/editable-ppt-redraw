#!/usr/bin/env python3
"""Audit reopened layout text against a manifest typography hierarchy."""

from __future__ import annotations

import argparse
import json
import math
import re
import statistics
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
}


def layout_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    if path.is_dir():
        return sorted(path.rglob("*.layout.json"))
    raise FileNotFoundError(path)


def collect_elements(layout_documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    elements: list[dict[str, Any]] = []
    for document in layout_documents:
        raw_elements = document.get("elements", [])
        if isinstance(raw_elements, list):
            elements.extend(item for item in raw_elements if isinstance(item, dict))
    return elements


def collect_pptx_elements(path: Path) -> tuple[list[dict[str, Any]], int]:
    elements: list[dict[str, Any]] = []
    with zipfile.ZipFile(path) as package:
        slide_parts = sorted(
            name
            for name in package.namelist()
            if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)
        )
        for slide_number, part in enumerate(slide_parts, start=1):
            root = ET.fromstring(package.read(part))
            for shape in root.findall(".//p:sp", NS):
                properties = shape.find("./p:nvSpPr/p:cNvPr", NS)
                name = properties.attrib.get("name", "") if properties is not None else ""
                text = "".join(node.text or "" for node in shape.findall(".//a:t", NS))
                if not name.strip() or not text.strip():
                    continue
                sizes: list[float] = []
                for node in shape.findall(".//a:rPr", NS) + shape.findall(".//a:defRPr", NS):
                    raw = node.attrib.get("sz")
                    if raw is None:
                        continue
                    try:
                        value = float(raw) / 100.0
                    except ValueError:
                        continue
                    if math.isfinite(value) and value > 0:
                        sizes.append(value)
                element: dict[str, Any] = {
                    "name": name,
                    "text": text,
                    "slideNumber": slide_number,
                }
                if sizes:
                    element["resolvedFontSize"] = float(statistics.median(sizes))
                    element["resolvedFontSizes"] = sizes
                elements.append(element)
    return elements, len(slide_parts)


def resolved_font_size(element: dict[str, Any]) -> float | None:
    direct = element.get("resolvedFontSize")
    if isinstance(direct, (int, float)) and not isinstance(direct, bool):
        value = float(direct)
        if math.isfinite(value) and value > 0:
            return value
    style = element.get("resolvedTextStyle")
    if isinstance(style, dict):
        nested = style.get("fontSize")
        if isinstance(nested, (int, float)) and not isinstance(nested, bool):
            value = float(nested)
            if math.isfinite(value) and value > 0:
                return value
    return None


def audit_typography(
    manifest: dict[str, Any], layout_documents: list[dict[str, Any]]
) -> dict[str, Any]:
    issues: list[str] = []
    warnings: list[str] = []
    hierarchy = manifest.get("typography_hierarchy")
    elements = collect_elements(layout_documents)

    if not isinstance(hierarchy, dict):
        issues.append("manifest does not contain a typography_hierarchy object")
        return {
            "valid": False,
            "issues": issues,
            "warnings": warnings,
            "roles": {},
            "stats": {"layout_documents": len(layout_documents), "elements": len(elements)},
        }

    roles = hierarchy.get("roles")
    if not isinstance(roles, dict) or not roles:
        issues.append("typography_hierarchy.roles must be a non-empty object")
        roles = {}

    baseline_role = hierarchy.get("baseline_role")
    default_tolerance = hierarchy.get("default_tolerance", 0.12)
    default_spread = hierarchy.get("default_max_intra_role_spread", 0.10)
    if not isinstance(default_tolerance, (int, float)):
        default_tolerance = 0.12
    if not isinstance(default_spread, (int, float)):
        default_spread = 0.10

    compiled: dict[str, re.Pattern[str]] = {}
    for role_name, spec in roles.items():
        if not isinstance(spec, dict):
            issues.append(f"typography role {role_name!r} is not an object")
            continue
        pattern_text = spec.get("output_name_regex")
        if not isinstance(pattern_text, str) or not pattern_text.strip():
            issues.append(f"typography role {role_name!r} has no output_name_regex")
            continue
        try:
            compiled[role_name] = re.compile(pattern_text)
        except re.error as exc:
            issues.append(f"typography role {role_name!r} has an invalid regex: {exc}")

    assignments: dict[str, list[tuple[str, float]]] = {role: [] for role in roles}
    matched_text_names: set[str] = set()
    for element in elements:
        name = element.get("name")
        text = element.get("text")
        if not isinstance(name, str) or not name.strip() or not isinstance(text, str) or not text.strip():
            continue
        matched_roles = [role for role, pattern in compiled.items() if pattern.search(name)]
        if len(matched_roles) > 1:
            issues.append(
                f"text object {name!r} matches multiple typography roles: {matched_roles}"
            )
            continue
        if not matched_roles:
            continue
        role = matched_roles[0]
        size = resolved_font_size(element)
        if size is None:
            issues.append(f"text object {name!r} in role {role!r} has no resolved font size")
            continue
        assignments[role].append((name, size))
        matched_text_names.add(name)

    role_reports: dict[str, dict[str, Any]] = {}
    for role_name, spec in roles.items():
        if not isinstance(spec, dict):
            continue
        values = [size for _, size in assignments.get(role_name, [])]
        required = spec.get("required", True)
        if not values:
            message = f"typography role {role_name!r} matched no text objects"
            if required:
                issues.append(message)
            else:
                warnings.append(message)
            role_reports[role_name] = {"count": 0, "objects": []}
            continue
        median_size = float(statistics.median(values))
        spread = (max(values) - min(values)) / median_size if median_size else 0.0
        allowed_spread = spec.get("max_intra_role_spread", default_spread)
        if isinstance(allowed_spread, (int, float)) and spread > float(allowed_spread) + 1e-9:
            issues.append(
                f"typography role {role_name!r} has intra-role spread {spread:.3f}; "
                f"allowed {float(allowed_spread):.3f}"
            )
        role_reports[role_name] = {
            "count": len(values),
            "objects": [name for name, _ in assignments[role_name]],
            "sizes": values,
            "median_size": median_size,
            "min_size": min(values),
            "max_size": max(values),
            "intra_role_spread": spread,
            "allowed_intra_role_spread": allowed_spread,
        }

    baseline_report = role_reports.get(baseline_role) if isinstance(baseline_role, str) else None
    baseline_size = (
        baseline_report.get("median_size")
        if isinstance(baseline_report, dict)
        else None
    )
    if not isinstance(baseline_size, (int, float)) or baseline_size <= 0:
        issues.append("baseline typography role has no measurable resolved font size")
    else:
        for role_name, spec in roles.items():
            if not isinstance(spec, dict):
                continue
            report = role_reports.get(role_name)
            if not isinstance(report, dict) or not isinstance(report.get("median_size"), (int, float)):
                continue
            target = spec.get("target_ratio")
            if not isinstance(target, (int, float)) or target <= 0:
                issues.append(f"typography role {role_name!r} has invalid target_ratio")
                continue
            tolerance = spec.get("tolerance", default_tolerance)
            if not isinstance(tolerance, (int, float)) or tolerance < 0:
                issues.append(f"typography role {role_name!r} has invalid tolerance")
                continue
            observed = float(report["median_size"]) / float(baseline_size)
            lower = float(target) * (1.0 - float(tolerance))
            upper = float(target) * (1.0 + float(tolerance))
            report.update(
                {
                    "observed_ratio": observed,
                    "target_ratio": float(target),
                    "tolerance": float(tolerance),
                    "allowed_ratio_range": [lower, upper],
                }
            )
            if observed < lower - 1e-9 or observed > upper + 1e-9:
                issues.append(
                    f"typography role {role_name!r} ratio {observed:.3f} is outside "
                    f"[{lower:.3f}, {upper:.3f}]"
                )

    text_element_count = sum(
        1
        for element in elements
        if isinstance(element.get("text"), str) and element.get("text", "").strip()
    )
    stats = {
        "layout_documents": len(layout_documents),
        "elements": len(elements),
        "text_elements": text_element_count,
        "matched_text_elements": len(matched_text_names),
        "roles": len(roles),
        "measured_roles": sum(1 for report in role_reports.values() if report.get("count", 0)),
        "baseline_role": baseline_role,
        "baseline_size": baseline_size,
    }
    return {
        "valid": not issues,
        "issues": issues,
        "warnings": warnings,
        "roles": role_reports,
        "stats": stats,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit native PPTX text or reopened layout text against a visual-manifest typography hierarchy."
    )
    parser.add_argument("manifest", type=Path, help="Path to visual-manifest JSON")
    parser.add_argument(
        "output",
        type=Path,
        help="A native .pptx, a reopened .layout.json file, or a directory containing layouts",
    )
    parser.add_argument("--json", dest="json_path", type=Path, help="Optional JSON report path")
    parser.add_argument(
        "--fail-on-risk", action="store_true", help="Return nonzero when typography issues exist"
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        if args.output.is_file() and args.output.suffix.lower() == ".pptx":
            elements, document_count = collect_pptx_elements(args.output)
            paths = [args.output]
            layout_documents = [{"elements": elements}]
            source_type = "pptx_ooxml"
        else:
            paths = layout_files(args.output)
            if not paths:
                raise FileNotFoundError(f"no .layout.json files found under {args.output}")
            layout_documents = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
            document_count = len(layout_documents)
            source_type = "layout_json"
    except (OSError, json.JSONDecodeError, zipfile.BadZipFile, ET.ParseError) as exc:
        print(f"Cannot run typography-hierarchy audit: {exc}", file=sys.stderr)
        return 2

    if not isinstance(manifest, dict) or not all(
        isinstance(document, dict) for document in layout_documents
    ):
        print(
            "Cannot run typography-hierarchy audit: manifest and layouts must be JSON objects",
            file=sys.stderr,
        )
        return 2

    report = audit_typography(manifest, layout_documents)
    report["stats"]["document_count"] = document_count
    report["stats"]["source_type"] = source_type
    report["manifest"] = str(args.manifest.resolve())
    report["outputs"] = [str(path.resolve()) for path in paths]
    if args.json_path:
        args.json_path.parent.mkdir(parents=True, exist_ok=True)
        args.json_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    print(
        "Typography hierarchy: "
        f"valid={report['valid']}, issues={len(report['issues'])}, "
        f"warnings={len(report['warnings'])}, stats={report['stats']}"
    )
    for message in report["issues"]:
        print(f"ISSUE: {message}")
    for message in report["warnings"]:
        print(f"WARNING: {message}")
    if args.fail_on_risk and report["issues"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
