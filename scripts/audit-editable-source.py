#!/usr/bin/env python3
"""Audit editable visual-source formats for structure and flattening risks."""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
SUPPORTED = {"svg", "drawio", "excalidraw", "mermaid", "graphviz", "html"}


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def external_url(value: str | None) -> bool:
    if not value:
        return False
    candidate = value.strip().lower()
    return candidate.startswith(("http://", "https://", "//"))


def parse_number(value: str | None) -> float | None:
    if value is None:
        return None
    match = re.match(r"^\s*(-?(?:\d+(?:\.\d*)?|\.\d+))", value)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def base_report(fmt: str) -> dict[str, Any]:
    return {"format": fmt, "valid": True, "errors": [], "risks": [], "warnings": [], "stats": {}}


def finalize(report: dict[str, Any]) -> dict[str, Any]:
    report["valid"] = not report["errors"]
    return report


def audit_svg(path: Path) -> dict[str, Any]:
    report = base_report("svg")
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError) as exc:
        report["errors"].append(f"cannot parse SVG XML: {exc}")
        return finalize(report)
    if local_name(root.tag) != "svg":
        report["errors"].append("root element is not <svg>")
        return finalize(report)

    drawable_tags = {"path", "rect", "circle", "ellipse", "line", "polyline", "polygon", "text"}
    counts: dict[str, int] = {}
    images: list[ET.Element] = []
    external_assets: list[str] = []
    for element in root.iter():
        name = local_name(element.tag)
        counts[name] = counts.get(name, 0) + 1
        if name == "image":
            images.append(element)
        if name in {"image", "use", "script"}:
            href = element.attrib.get("href") or element.attrib.get(f"{{{XLINK_NS}}}href")
            if external_url(href):
                external_assets.append(href or "")

    view_box = root.attrib.get("viewBox")
    canvas_width = canvas_height = None
    if view_box:
        parts = re.split(r"[\s,]+", view_box.strip())
        if len(parts) == 4:
            try:
                _, _, canvas_width, canvas_height = (float(part) for part in parts)
            except ValueError:
                report["warnings"].append("viewBox is present but cannot be parsed")
    if canvas_width is None or canvas_height is None:
        canvas_width = parse_number(root.attrib.get("width"))
        canvas_height = parse_number(root.attrib.get("height"))
    if not view_box:
        report["warnings"].append("SVG has no explicit viewBox; editor and browser scaling may diverge")

    native_drawables = sum(counts.get(tag, 0) for tag in drawable_tags)
    full_canvas_images = 0
    if canvas_width and canvas_height and canvas_width > 0 and canvas_height > 0:
        for image in images:
            width = parse_number(image.attrib.get("width"))
            height = parse_number(image.attrib.get("height"))
            if width and height and (width * height) / (canvas_width * canvas_height) >= 0.8:
                full_canvas_images += 1
    if images and native_drawables == 0:
        report["risks"].append("SVG contains raster image elements but no native drawable or text elements")
    elif full_canvas_images and native_drawables < 4:
        report["risks"].append("a raster image covers most of the SVG canvas with little native reconstruction")
    if external_assets:
        report["risks"].append(f"SVG depends on {len(external_assets)} external asset URL(s)")
    if counts.get("foreignObject", 0):
        report["warnings"].append("foreignObject content may not round-trip across SVG editors")
    if counts.get("script", 0):
        report["warnings"].append("SVG contains script elements; verify that interaction is required and local")
    if native_drawables == 0 and not images:
        report["errors"].append("SVG contains no drawable content")

    report["stats"] = {
        "native_drawables": native_drawables,
        "text": counts.get("text", 0),
        "groups": counts.get("g", 0),
        "images": len(images),
        "full_canvas_images": full_canvas_images,
        "external_assets": len(external_assets),
    }
    return finalize(report)


def audit_drawio(path: Path) -> dict[str, Any]:
    report = base_report("drawio")
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError) as exc:
        report["errors"].append(f"cannot parse draw.io XML: {exc}")
        return finalize(report)

    graph_models = [node for node in root.iter() if local_name(node.tag) == "mxGraphModel"]
    if not graph_models:
        diagrams = [node for node in root.iter() if local_name(node.tag) == "diagram"]
        if diagrams and any((node.text or "").strip() for node in diagrams):
            report["risks"].append("draw.io diagram is compressed or encoded; native cells cannot be inspected")
            report["stats"] = {"diagrams": len(diagrams), "inspectable_graph_models": 0}
        else:
            report["errors"].append("no mxGraphModel found")
        return finalize(report)

    cells = [node for model in graph_models for node in model.iter() if local_name(node.tag) == "mxCell"]
    duplicate_ids: set[str] = set()
    for page, model in enumerate(graph_models, 1):
        page_cells = [node for node in model.iter() if local_name(node.tag) == "mxCell"]
        # draw.io IDs belong to one graph model, not to the whole document.
        parents = {child: parent for parent in model.iter() for child in parent}
        ids = []
        for cell in page_cells:
            owner = parents.get(cell)
            cell_id = cell.get("id") or (owner.get("id") if owner is not None else None)
            if cell_id:
                if cell_id in ids:
                    duplicate_ids.add(f"page {page}: {cell_id}")
                ids.append(cell_id)
        for cell in page_cells:
            if cell.get("edge") != "1":
                continue
            geometry = next((c for c in cell if local_name(c.tag) == "mxGeometry"), None)
            for endpoint in ("source", "target"):
                target = cell.get(endpoint)
                if target is not None:
                    if target not in ids:
                        report["errors"].append(f"page {page} edge {cell.get('id')} has dangling {endpoint}={target!r}")
                elif geometry is None or not any(c.get("as") == endpoint + "Point" for c in geometry):
                    report["risks"].append(f"page {page} edge {cell.get('id')} has no {endpoint} binding or free point")
    vertices = edges = image_cells = native_vertices = 0
    malformed_edges = 0
    external_images = 0
    for cell in cells:
        is_vertex = cell.attrib.get("vertex") == "1"
        is_edge = cell.attrib.get("edge") == "1"
        style = cell.attrib.get("style", "")
        is_image = "shape=image" in style or re.search(r"(?:^|;)image=", style) is not None
        if is_vertex:
            vertices += 1
            if is_image:
                image_cells += 1
                image_match = re.search(r"(?:^|;)image=([^;]+)", style)
                if image_match and external_url(image_match.group(1)):
                    external_images += 1
            else:
                native_vertices += 1
        if is_edge:
            edges += 1
            geometries = [child for child in cell if local_name(child.tag) == "mxGeometry"]
            if not geometries or geometries[0].attrib.get("relative") != "1":
                malformed_edges += 1

    if duplicate_ids:
        report["errors"].append(f"duplicate mxCell IDs: {sorted(duplicate_ids)}")
    if not vertices and not edges:
        report["errors"].append("draw.io source contains no editable vertices or edges")
    if image_cells and native_vertices <= 1:
        report["risks"].append("draw.io source is image-dominant and may be a flattened screenshot substitute")
    if malformed_edges:
        report["risks"].append(f"{malformed_edges} edge cell(s) lack mxGeometry relative=\"1\"")
    if external_images:
        report["risks"].append(f"{external_images} draw.io image cell(s) depend on external URLs")
    if image_cells:
        report["warnings"].append("inspect image cells and confirm each is a justified portable symbol or evidence exception")

    report["stats"] = {
        "graph_models": len(graph_models),
        "cells": len(cells),
        "vertices": vertices,
        "native_vertices": native_vertices,
        "edges": edges,
        "image_cells": image_cells,
        "malformed_edges": malformed_edges,
        "external_images": external_images,
    }
    return finalize(report)


def audit_excalidraw(path: Path) -> dict[str, Any]:
    report = base_report("excalidraw")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        report["errors"].append(f"cannot parse Excalidraw JSON: {exc}")
        return finalize(report)
    if not isinstance(data, dict) or not isinstance(data.get("elements"), list):
        report["errors"].append("Excalidraw root must contain an elements list")
        return finalize(report)

    elements = [item for item in data["elements"] if isinstance(item, dict) and not item.get("isDeleted", False)]
    ids = [element.get("id") for element in elements]
    if any(not isinstance(value, str) or not value for value in ids):
        report["errors"].append("active Excalidraw element lacks a string ID")
    valid_ids = [value for value in ids if isinstance(value, str)]
    if len(valid_ids) != len(set(valid_ids)):
        report["errors"].append("duplicate active Excalidraw IDs")
    for element in elements:
        for key in ("startBinding", "endBinding"):
            binding = element.get(key)
            if binding is not None and (not isinstance(binding, dict) or binding.get("elementId") not in valid_ids):
                report["errors"].append(f"{element.get('id')}: dangling or malformed {key}")
        for key in ("containerId", "frameId"):
            if element.get(key) is not None and element[key] not in valid_ids:
                report["errors"].append(f"{element.get('id')}: dangling {key}")
        bound = element.get("boundElements") or []
        if not isinstance(bound, list) or any(not isinstance(b, dict) or b.get("id") not in valid_ids for b in bound):
            report["errors"].append(f"{element.get('id')}: dangling or malformed boundElements")
    type_counts: dict[str, int] = {}
    for element in elements:
        element_type = str(element.get("type", "unknown"))
        type_counts[element_type] = type_counts.get(element_type, 0) + 1
    image_count = type_counts.get("image", 0)
    native_count = len(elements) - image_count
    external_files = 0
    files = data.get("files", {})
    if isinstance(files, dict):
        for item in files.values():
            if isinstance(item, dict) and external_url(str(item.get("dataURL", ""))):
                external_files += 1
    if not elements:
        report["errors"].append("Excalidraw scene has no active elements")
    if image_count and native_count <= 1:
        report["risks"].append("Excalidraw scene is image-dominant and may be a flattened reference")
    if external_files:
        report["risks"].append(f"Excalidraw scene depends on {external_files} external file URL(s)")
    if type_counts.get("text", 0) == 0:
        report["warnings"].append("scene contains no editable text elements")
    report["stats"] = {
        "elements": len(elements),
        "native_elements": native_count,
        "images": image_count,
        "external_files": external_files,
        "types": type_counts,
    }
    return finalize(report)


def audit_mermaid(path: Path) -> dict[str, Any]:
    report = base_report("mermaid")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        report["errors"].append(f"cannot read Mermaid source: {exc}")
        return finalize(report)
    stripped = re.sub(r"%%.*$", "", text, flags=re.MULTILINE).strip()
    headers = re.findall(r"(?im)^\s*(flowchart|graph|sequenceDiagram|classDiagram|stateDiagram(?:-v2)?|erDiagram|gantt|timeline|mindmap|journey|pie)\b", stripped)
    edge_tokens = re.findall(r"-->|---|==>|-.->|~~~|<-->|--\|", stripped)
    if not stripped:
        report["errors"].append("Mermaid source is empty")
    if not headers:
        report["errors"].append("no supported Mermaid diagram header found")
    if headers and not edge_tokens and headers[0].lower() not in {"pie", "mindmap", "timeline", "gantt", "journey"}:
        report["warnings"].append("no relationship token found; verify that the diagram is intentionally node-only")
    report["stats"] = {"headers": headers, "relationship_tokens": len(edge_tokens), "characters": len(text)}
    return finalize(report)


def audit_graphviz(path: Path) -> dict[str, Any]:
    report = base_report("graphviz")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        report["errors"].append(f"cannot read Graphviz source: {exc}")
        return finalize(report)
    stripped = re.sub(r"//.*$|/\*.*?\*/", "", text, flags=re.MULTILINE | re.DOTALL).strip()
    header = re.search(r"(?i)\b(?:strict\s+)?(di)?graph\b\s+[A-Za-z_0-9\"]*\s*\{", stripped)
    edges = re.findall(r"->|--", stripped)
    if not stripped:
        report["errors"].append("Graphviz source is empty")
    if not header:
        report["errors"].append("Graphviz source lacks a graph or digraph declaration")
    if stripped.count("{") != stripped.count("}"):
        report["errors"].append("Graphviz braces are unbalanced")
    if header and not edges:
        report["warnings"].append("no edge operator found; verify that the graph is intentionally node-only")
    report["stats"] = {"edge_tokens": len(edges), "characters": len(text)}
    return finalize(report)


class EditableHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.counts: dict[str, int] = {}
        self.external_assets: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        name = tag.lower()
        self.counts[name] = self.counts.get(name, 0) + 1
        attr_map = {key.lower(): value for key, value in attrs}
        if name in {"img", "script", "link", "source", "use"}:
            value = attr_map.get("src") or attr_map.get("href") or attr_map.get("xlink:href")
            if external_url(value):
                self.external_assets.append(value or "")


def audit_html(path: Path) -> dict[str, Any]:
    report = base_report("html")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        report["errors"].append(f"cannot read HTML source: {exc}")
        return finalize(report)
    parser = EditableHTMLParser()
    try:
        parser.feed(text)
    except Exception as exc:  # HTMLParser can surface malformed entity edge cases.
        report["errors"].append(f"cannot parse HTML: {exc}")
        return finalize(report)
    svg_drawables = sum(parser.counts.get(tag, 0) for tag in ("path", "rect", "circle", "ellipse", "line", "polyline", "polygon", "text"))
    structural = sum(parser.counts.get(tag, 0) for tag in ("div", "section", "article", "table", "svg", "canvas"))
    images = parser.counts.get("img", 0)
    if structural == 0 and svg_drawables == 0:
        report["errors"].append("HTML contains no editable visual structure")
    if images and svg_drawables == 0 and structural <= 2:
        report["risks"].append("HTML is image-dominant and may be a flattened visual wrapper")
    if parser.external_assets:
        report["risks"].append(f"HTML depends on {len(parser.external_assets)} external asset URL(s)")
    if parser.counts.get("svg", 0) and not re.search(r"<svg\b[^>]*\bviewBox=", text, re.IGNORECASE):
        report["warnings"].append("inline SVG has no explicit viewBox")
    report["stats"] = {
        "structural_elements": structural,
        "svg_drawables": svg_drawables,
        "images": images,
        "external_assets": len(parser.external_assets),
        "scripts": parser.counts.get("script", 0),
    }
    return finalize(report)


def detect_format(path: Path, override: str | None) -> str:
    if override:
        value = override.lower()
        return "graphviz" if value in {"dot", "gv"} else value
    suffix = path.suffix.lower()
    mapping = {
        ".svg": "svg",
        ".drawio": "drawio",
        ".excalidraw": "excalidraw",
        ".mmd": "mermaid",
        ".mermaid": "mermaid",
        ".dot": "graphviz",
        ".gv": "graphviz",
        ".graphviz": "graphviz",
        ".html": "html",
        ".htm": "html",
    }
    return mapping.get(suffix, "")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit an editable visual source for structure, portability, and flattening risk.")
    parser.add_argument("input", type=Path, help="SVG, draw.io, Excalidraw, Mermaid, Graphviz, or HTML source")
    parser.add_argument("--format", choices=sorted(SUPPORTED | {"dot", "gv"}), help="Override format detection")
    parser.add_argument("--json", dest="json_path", type=Path, help="Optional JSON report path")
    parser.add_argument("--fail-on-risk", action="store_true", help="Return nonzero when risks are found")
    args = parser.parse_args()

    fmt = detect_format(args.input, args.format)
    auditors = {
        "svg": audit_svg,
        "drawio": audit_drawio,
        "excalidraw": audit_excalidraw,
        "mermaid": audit_mermaid,
        "graphviz": audit_graphviz,
        "html": audit_html,
    }
    if fmt not in auditors:
        report = base_report(fmt or "unknown")
        report["errors"].append("unsupported or undetected editable-source format")
        finalize(report)
    else:
        report = auditors[fmt](args.input)
    report["input"] = str(args.input.resolve())

    if args.json_path:
        args.json_path.parent.mkdir(parents=True, exist_ok=True)
        args.json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        f"Editable source audit: format={report['format']}, valid={report['valid']}, "
        f"errors={len(report['errors'])}, risks={len(report['risks'])}, "
        f"warnings={len(report['warnings'])}, stats={report['stats']}"
    )
    for level in ("errors", "risks", "warnings"):
        for message in report[level]:
            print(f"{level[:-1].upper()}: {message}")

    if report["errors"] or (args.fail_on_risk and report["risks"]):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
