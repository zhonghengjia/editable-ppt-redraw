#!/usr/bin/env python3
"""Audit reopened editable output against a manifest diagram-grammar contract."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Any


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


def endpoint_evidence(spec, lines, by_name):
    """Verify directed endpoint evidence; a line bbox cannot establish direction."""
    binding = spec.get("endpoint_binding")
    if not isinstance(binding, dict):
        return "NOT_VERIFIED", "no declared endpoint_binding"
    source, target = binding.get("source_output_name"), binding.get("target_output_name")
    for name in (source, target):
        if len(by_name.get(name, [])) != 1:
            return "FAIL", f"endpoint {name!r} is missing or ambiguous"
    if len(lines) == 1 and "source_name" in lines[0] and "target_name" in lines[0]:
        valid = lines[0]["source_name"] == source and lines[0]["target_name"] == target
        return ("PASS", "actual native endpoint bindings") if valid else ("FAIL", "native endpoints differ from declared source/target")
    names = binding.get("ordered_output_names")
    if not isinstance(names, list) or not names:
        return "NOT_VERIFIED", "explicit routed lines need ordered_output_names"
    if sorted(names) != sorted(line["name"] for line in lines):
        return "FAIL", "ordered route does not cover matched lines exactly"
    points = []
    for name in names:
        matches = by_name.get(name, [])
        if len(matches) != 1:
            return "FAIL", "route segment name is ambiguous"
        ends = matches[0].get("endpoints")
        if not isinstance(ends, list) or len(ends) != 2 or any(not isinstance(p, list) or len(p) != 2 or any(isinstance(v, bool) or not isinstance(v, (float, int)) or not math.isfinite(v) for v in p) for p in ends):
            return "NOT_VERIFIED", "directed endpoints not available from reopened layout"
        points.append(ends)
    tolerance = binding.get("tolerance", .01)
    if isinstance(tolerance, bool) or not isinstance(tolerance, (float, int)) or not math.isfinite(tolerance) or tolerance < 0:
        return "FAIL", "invalid endpoint tolerance"
    if any(math.dist(a[1], b[0]) > tolerance for a, b in zip(points, points[1:])):
        return "FAIL", "directed route is discontinuous"
    for name, point in ((source, points[0][0]), (target, points[-1][1])):
        node = by_name[name][0]
        box = node.get("bbox")
        if node.get("geometry") != "rect" or not isinstance(box, list) or len(box) != 4:
            return "NOT_VERIFIED", "coordinate endpoint validation supports explicit rectangular bboxes only"
        if any(isinstance(v, bool) or not isinstance(v, (float, int)) or not math.isfinite(v) for v in box):
            return "FAIL", "nonfinite node bbox"
        x, y, w, h = box
        px, py = point
        on_boundary = (w > 0 and h > 0 and x-tolerance <= px <= x+w+tolerance and
                       y-tolerance <= py <= y+h+tolerance and
                       min(abs(px-x), abs(px-x-w), abs(py-y), abs(py-y-h)) <= tolerance)
        if not on_boundary:
            return "FAIL", f"directed endpoint misses {name!r} boundary"
    return "PASS", "directed segment continuity and rectangular boundary attachment"


def audit_grammar(
    manifest: dict[str, Any], layout_documents: list[dict[str, Any]]
) -> dict[str, Any]:
    issues: list[str] = []
    warnings: list[str] = []
    grammar = manifest.get("diagram_grammar")
    elements = collect_elements(layout_documents)

    if not isinstance(grammar, dict):
        issues.append("manifest does not contain a diagram_grammar object")
        return {
            "valid": False,
            "issues": issues,
            "warnings": warnings,
            "stats": {"layout_documents": len(layout_documents), "elements": len(elements)},
        }

    if grammar.get("allow_representation_change") is True:
        authorization = grammar.get("authorization")
        if not isinstance(authorization, str) or not authorization.strip():
            issues.append(
                "representation change is enabled without recorded explicit user authorization"
            )
    elif grammar.get("preserve_visual_type") is False:
        issues.append("visual-type preservation is disabled without representation-change permission")

    elements_by_name: dict[str, list[dict[str, Any]]] = {}
    unnamed_elements = 0
    for element in elements:
        name = element.get("name")
        if not isinstance(name, str) or not name.strip():
            unnamed_elements += 1
            continue
        elements_by_name.setdefault(name, []).append(element)

    matched_node_objects = 0
    node_roles = grammar.get("node_roles", {})
    if not isinstance(node_roles, dict):
        issues.append("diagram_grammar.node_roles must be an object")
        node_roles = {}
    for subject_id, spec in node_roles.items():
        if not isinstance(spec, dict):
            issues.append(f"node role {subject_id!r} is not an object")
            continue
        allowed = spec.get("allowed_geometries", [])
        allowed_geometries = {
            value for value in allowed if isinstance(value, str) and value.strip()
        } if isinstance(allowed, list) else set()
        output_names = spec.get("output_names", [])
        if not isinstance(output_names, list):
            issues.append(f"node role {subject_id!r} has invalid output_names")
            continue
        for output_name in output_names:
            if not isinstance(output_name, str) or not output_name.strip():
                issues.append(f"node role {subject_id!r} contains an invalid output name")
                continue
            matches = elements_by_name.get(output_name, [])
            if not matches:
                issues.append(
                    f"node role {subject_id!r} is missing required output object {output_name!r}"
                )
                continue
            if len(matches) > 1:
                issues.append(
                    f"node role {subject_id!r} output object {output_name!r} is not unique"
                )
            matched_node_objects += len(matches)
            for element in matches:
                geometry = element.get("geometry")
                if geometry not in allowed_geometries:
                    issues.append(
                        f"node role {subject_id!r} output {output_name!r} uses geometry "
                        f"{geometry!r}; allowed: {sorted(allowed_geometries)}"
                    )

    matched_edge_objects = 0
    connection_reports = {}
    unverified = []
    connections = {c.get("id"): c for c in manifest.get("connections", []) if isinstance(c, dict)}
    edge_roles = grammar.get("edge_roles", {})
    if not isinstance(edge_roles, dict):
        issues.append("diagram_grammar.edge_roles must be an object")
        edge_roles = {}
    for connection_id, spec in edge_roles.items():
        if not isinstance(spec, dict):
            issues.append(f"edge role {connection_id!r} is not an object")
            continue
        pattern_text = spec.get("output_name_regex")
        if not isinstance(pattern_text, str) or not pattern_text.strip():
            issues.append(f"edge role {connection_id!r} has no output_name_regex")
            continue
        try:
            pattern = re.compile(pattern_text)
        except re.error as exc:
            issues.append(f"edge role {connection_id!r} has an invalid regex: {exc}")
            continue
        named_matches = [
            element
            for name, named_elements in elements_by_name.items()
            if pattern.search(name)
            for element in named_elements
        ]
        line_matches = [element for element in named_matches if element.get("geometry") == "line"]
        if not line_matches:
            issues.append(
                f"edge role {connection_id!r} has no editable line matching {pattern_text!r}"
            )
            continue
        matched_edge_objects += len(line_matches)
        binding = spec.get("endpoint_binding", {})
        declared = connections.get(connection_id)
        if isinstance(binding, dict) and declared:
            for end in ("source", "target"):
                role = node_roles.get(declared.get(end), {})
                if role and binding.get(end + "_output_name") not in role.get("output_names", []):
                    issues.append(f"edge role {connection_id!r}: {end} binding conflicts with declared node role")
        state, reason = endpoint_evidence(spec, line_matches, elements_by_name)
        connection_reports[connection_id] = {"status": state, "reason": reason}
        if state == "FAIL":
            issues.append(f"edge role {connection_id!r}: {reason}")
        elif state == "NOT_VERIFIED":
            unverified.append(f"edge role {connection_id!r}: {reason}")
        non_line_matches = len(named_matches) - len(line_matches)
        if non_line_matches:
            warnings.append(
                f"edge role {connection_id!r} pattern also matched {non_line_matches} non-line object(s)"
            )

    stats = {
        "layout_documents": len(layout_documents),
        "elements": len(elements),
        "named_elements": len(elements) - unnamed_elements,
        "node_roles": len(node_roles),
        "edge_roles": len(edge_roles),
        "matched_node_objects": matched_node_objects,
        "matched_edge_objects": matched_edge_objects,
    }
    return {"valid": not issues, "issues": issues, "warnings": warnings, "stats": stats,
            "endpoint_evidence": connection_reports, "unverified": unverified,
            "status": "FAIL" if issues else ("NOT_VERIFIED" if unverified else "PASS"),
            "coverage": "Named geometry and declared directed endpoints; arrow style and obstacle avoidance require separate checks."}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit named editable objects against a visual manifest diagram grammar."
    )
    parser.add_argument("manifest", type=Path, help="Path to visual-manifest JSON")
    parser.add_argument(
        "layout", type=Path, help="A reopened .layout.json file or directory containing them"
    )
    parser.add_argument("--json", dest="json_path", type=Path, help="Optional JSON report path")
    parser.add_argument(
        "--fail-on-risk", action="store_true", help="Return nonzero when grammar issues exist"
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        paths = layout_files(args.layout)
        if not paths:
            raise FileNotFoundError(f"no .layout.json files found under {args.layout}")
        layout_documents = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Cannot run diagram-grammar audit: {exc}", file=sys.stderr)
        return 2

    if not isinstance(manifest, dict) or not all(
        isinstance(document, dict) for document in layout_documents
    ):
        print("Cannot run diagram-grammar audit: manifest and layouts must be JSON objects", file=sys.stderr)
        return 2

    report = audit_grammar(manifest, layout_documents)
    report["manifest"] = str(args.manifest.resolve())
    report["layouts"] = [str(path.resolve()) for path in paths]
    if args.json_path:
        args.json_path.parent.mkdir(parents=True, exist_ok=True)
        args.json_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    print(
        "Diagram grammar: "
        f"valid={report['valid']}, issues={len(report['issues'])}, "
        f"warnings={len(report['warnings'])}, stats={report['stats']}"
    )
    for message in report["issues"]:
        print(f"ISSUE: {message}")
    for message in report["warnings"]:
        print(f"WARNING: {message}")
    if args.fail_on_risk and (report["issues"] or report.get("unverified")):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
