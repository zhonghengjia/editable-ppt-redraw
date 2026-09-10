#!/usr/bin/env python3
"""Audit whether a PPTX is built from editable objects or dominated by pictures."""

from __future__ import annotations

import argparse
import json
import math
import posixpath
import re
import sys
import unicodedata
import zipfile
from itertools import combinations
from pathlib import Path
from xml.etree import ElementTree as ET


PML = "http://schemas.openxmlformats.org/presentationml/2006/main"
DML = "http://schemas.openxmlformats.org/drawingml/2006/main"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
CHART = "http://schemas.openxmlformats.org/drawingml/2006/chart"

NS = {"p": PML, "a": DML, "r": REL, "c": CHART, "pr": PKG_REL}

PLACEHOLDER_PATTERNS = (
    re.compile(r"^click to add(?: title| text| subtitle)?$", re.IGNORECASE),
    re.compile(r"^lorem ipsum\b", re.IGNORECASE),
    re.compile(r"^(?:todo|tbd|replace with|placeholder)(?:\b|\s|:)", re.IGNORECASE),
    re.compile(r"^slide number$", re.IGNORECASE),
)
MOJIBAKE_MARKERS = ("\ufffd", "Ã", "Â", "â€", "锟斤拷", "烫烫烫", "屯屯屯")
CJK_PATTERN = re.compile(r"[\u2e80-\u2fff\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")


def configure_utf8_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8")


def natural_key(value: str) -> list[object]:
    return [int(part) if part.isdigit() else part for part in re.split(r"(\d+)", value)]


def read_xml(archive: zipfile.ZipFile, part: str) -> ET.Element:
    return ET.fromstring(archive.read(part))


def relationships_part(part: str) -> str:
    folder, filename = posixpath.split(part)
    return posixpath.join(folder, "_rels", f"{filename}.rels")


def read_relationships(archive: zipfile.ZipFile, part: str) -> dict[str, str]:
    rels_part = relationships_part(part)
    if rels_part not in archive.namelist():
        return {}
    root = read_xml(archive, rels_part)
    return {
        rel.attrib.get("Id", ""): rel.attrib.get("Target", "")
        for rel in root.findall("pr:Relationship", NS)
    }


def read_relationship_records(archive: zipfile.ZipFile, part: str) -> list[dict[str, str]]:
    rels_part = relationships_part(part)
    if rels_part not in archive.namelist():
        return []
    root = read_xml(archive, rels_part)
    return [
        {
            "source_part": part,
            "id": rel.attrib.get("Id", ""),
            "target": rel.attrib.get("Target", ""),
            "target_mode": rel.attrib.get("TargetMode", ""),
            "type": rel.attrib.get("Type", ""),
        }
        for rel in root.findall("pr:Relationship", NS)
    ]


def normalize_match_text(value: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFC", value or ""))


def text_occurrences(required: str, actual: str) -> int:
    value = normalize_match_text(required)
    if not value:
        return 0
    left = r"(?<![A-Za-z0-9_])" if value[0].isascii() and value[0].isalnum() else ""
    right = r"(?![A-Za-z0-9_])" if value[-1].isascii() and value[-1].isalnum() else ""
    if value[-1].isdigit():
        right += r"(?![.,][0-9])"
    # Preserve token boundaries in the actual text; removing all spaces would
    # turn 'cohort N=55' into 'cohortN=55' and incorrectly hide a real match.
    pattern = r"\s*".join(re.escape(char) for char in value)
    return len(re.findall(left + pattern + right, unicodedata.normalize("NFC", actual or "")))


def text_objects(archive, slide_parts):
    result = []
    for number, part in enumerate(slide_parts, 1):
        root = ET.fromstring(archive.read(part))
        for shape in root.findall(".//p:sp", NS) + root.findall(".//p:graphicFrame", NS):
            properties = shape.find("./p:nvSpPr/p:cNvPr", NS)
            if properties is None:
                properties = shape.find("./p:nvGraphicFramePr/p:cNvPr", NS)
            result.append({
                "slide": number, "id": properties.get("id") if properties is not None else None,
                "name": properties.get("name") if properties is not None else None,
                "text": "\n".join("".join(n.text or "" for n in p.findall(".//a:t", NS)) for p in shape.findall(".//a:p", NS)),
            })
    return result


def audit_text_inventory(inventory, objects):
    reports = []
    for index, item in enumerate(inventory or []):
        if not isinstance(item, dict) or not isinstance(item.get("text"), str) or not item["text"].strip():
            continue
        matches = [obj for obj in objects if
                   ("output_slide" not in item or obj["slide"] == item["output_slide"]) and
                   ("output_name" not in item or obj["name"] == item["output_name"]) and
                   ("output_id" not in item or obj["id"] == str(item["output_id"]))]
        observed = sum(text_occurrences(item["text"], obj["text"]) for obj in matches)
        expected = item.get("required_count", 1)
        valid_count = isinstance(expected, int) and not isinstance(expected, bool) and expected > 0
        reports.append({"id": item.get("id", index), "text": item["text"], "observed": observed,
                        "required_count": expected, "valid": valid_count and observed >= expected})
    return reports


def required_texts_from_manifest(path: Path | None) -> list[str]:
    if path is None:
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    inventory = data.get("source_inventory", [])
    if not isinstance(inventory, list):
        raise ValueError("manifest source_inventory must be a list")
    return [
        item["text"].strip()
        for item in inventory
        if isinstance(item, dict)
        and isinstance(item.get("text"), str)
        and item["text"].strip()
    ]


def unique_texts(values: list[str] | None) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        stripped = value.strip()
        normalized = normalize_match_text(stripped)
        if stripped and normalized not in seen:
            output.append(stripped)
            seen.add(normalized)
    return output


def resolve_target(source_part: str, target: str) -> str:
    if target.startswith("/"):
        return target.lstrip("/")
    return posixpath.normpath(posixpath.join(posixpath.dirname(source_part), target))


def slide_parts_in_order(archive: zipfile.ZipFile) -> tuple[list[str], tuple[int, int]]:
    presentation_part = "ppt/presentation.xml"
    root = read_xml(archive, presentation_part)
    size = root.find("p:sldSz", NS)
    slide_size = (
        int(size.attrib.get("cx", "0")) if size is not None else 0,
        int(size.attrib.get("cy", "0")) if size is not None else 0,
    )

    rels = read_relationships(archive, presentation_part)
    ordered: list[str] = []
    for slide_id in root.findall("./p:sldIdLst/p:sldId", NS):
        relationship_id = slide_id.attrib.get(f"{{{REL}}}id", "")
        target = rels.get(relationship_id)
        if target:
            part = resolve_target(presentation_part, target)
            if part in archive.namelist():
                ordered.append(part)

    if not ordered:
        ordered = sorted(
            [
                name
                for name in archive.namelist()
                if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)
            ],
            key=natural_key,
        )
    return ordered, slide_size


def picture_name(picture: ET.Element) -> str:
    node = picture.find("./p:nvPicPr/p:cNvPr", NS)
    return node.attrib.get("name", "") if node is not None else ""


def picture_target(picture: ET.Element, relationships: dict[str, str], slide_part: str) -> str | None:
    blip = picture.find("./p:blipFill/a:blip", NS)
    if blip is None:
        return None
    return blip_target(blip, relationships, slide_part)


def blip_target(blip: ET.Element, relationships: dict[str, str], source_part: str) -> str | None:
    relationship_id = blip.attrib.get(f"{{{REL}}}embed", "")
    target = relationships.get(relationship_id)
    return resolve_target(source_part, target) if target else None


def picture_geometry(picture: ET.Element, slide_size: tuple[int, int]) -> dict[str, object] | None:
    transform = picture.find("./p:spPr/a:xfrm", NS)
    if transform is None:
        return None
    offset = transform.find("a:off", NS)
    extent = transform.find("a:ext", NS)
    if offset is None or extent is None:
        return None
    try:
        x = int(offset.attrib.get("x", "0"))
        y = int(offset.attrib.get("y", "0"))
        width = int(extent.attrib.get("cx", "0"))
        height = int(extent.attrib.get("cy", "0"))
    except ValueError:
        return None
    slide_area = slide_size[0] * slide_size[1]
    area_ratio = (width * height / slide_area) if slide_area else None
    return {
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "area_ratio": round(area_ratio, 6) if area_ratio is not None else None,
    }


def object_name(node: ET.Element) -> str:
    name_paths = {
        f"{{{PML}}}sp": "./p:nvSpPr/p:cNvPr",
        f"{{{PML}}}pic": "./p:nvPicPr/p:cNvPr",
        f"{{{PML}}}graphicFrame": "./p:nvGraphicFramePr/p:cNvPr",
        f"{{{PML}}}cxnSp": "./p:nvCxnSpPr/p:cNvPr",
    }
    name_node = node.find(name_paths.get(node.tag, "./p:cNvPr"), NS)
    return name_node.attrib.get("name", "") if name_node is not None else ""


def object_geometry(node: ET.Element) -> dict[str, int] | None:
    transform_paths = {
        f"{{{PML}}}sp": "./p:spPr/a:xfrm",
        f"{{{PML}}}pic": "./p:spPr/a:xfrm",
        f"{{{PML}}}graphicFrame": "./p:xfrm",
        f"{{{PML}}}cxnSp": "./p:spPr/a:xfrm",
    }
    transform = node.find(transform_paths.get(node.tag, ""), NS)
    if transform is None:
        return None
    offset = transform.find("a:off", NS)
    extent = transform.find("a:ext", NS)
    if offset is None or extent is None:
        return None
    try:
        x = int(offset.attrib.get("x", "0"))
        y = int(offset.attrib.get("y", "0"))
        width = int(extent.attrib.get("cx", "0"))
        height = int(extent.attrib.get("cy", "0"))
        rotation = int(transform.attrib.get("rot", "0")) / 60000.0
    except ValueError:
        return None
    if rotation % 360:
        radians = math.radians(rotation)
        rotated_width = abs(width * math.cos(radians)) + abs(height * math.sin(radians))
        rotated_height = abs(width * math.sin(radians)) + abs(height * math.cos(radians))
        center_x = x + width / 2.0
        center_y = y + height / 2.0
        x = round(center_x - rotated_width / 2.0)
        y = round(center_y - rotated_height / 2.0)
        width = round(rotated_width)
        height = round(rotated_height)
    return {"x": x, "y": y, "width": width, "height": height}


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def out_of_bounds_objects(
    sp_tree: ET.Element | None,
    slide_size: tuple[int, int],
    tolerance_emu: int,
) -> list[dict[str, object]]:
    if sp_tree is None or not all(slide_size):
        return []
    findings: list[dict[str, object]] = []
    supported_tags = {
        f"{{{PML}}}sp",
        f"{{{PML}}}pic",
        f"{{{PML}}}graphicFrame",
        f"{{{PML}}}cxnSp",
    }
    for node in list(sp_tree):
        if node.tag not in supported_tags:
            continue
        geometry = object_geometry(node)
        if geometry is None:
            continue
        x = geometry["x"]
        y = geometry["y"]
        width = geometry["width"]
        height = geometry["height"]
        if (
            x < -tolerance_emu
            or y < -tolerance_emu
            or x + width > slide_size[0] + tolerance_emu
            or y + height > slide_size[1] + tolerance_emu
        ):
            findings.append(
                {
                    "kind": local_name(node.tag),
                    "name": object_name(node),
                    "geometry": geometry,
                }
            )
    return findings


def line_signature(shape: ET.Element) -> tuple[int, str] | None:
    line = shape.find("./p:spPr/a:ln", NS)
    if line is None or line.find("a:noFill", NS) is not None:
        return None
    solid_fill = line.find("a:solidFill", NS)
    if solid_fill is None or not list(solid_fill):
        return None
    color_node = list(solid_fill)[0]
    color_value = (
        color_node.attrib.get("val")
        or color_node.attrib.get("lastClr")
        or json.dumps(sorted(color_node.attrib.items()))
    )
    try:
        width = int(line.attrib.get("w", "12700"))
    except ValueError:
        width = 12700
    return width, f"{local_name(color_node.tag)}:{color_value}"


def near_equal_geometry(
    first: dict[str, int], second: dict[str, int], tolerance_emu: int
) -> bool:
    return all(
        abs(first[key] - second[key]) <= tolerance_emu
        for key in ("x", "y", "width", "height")
    )


def duplicate_border_candidates(
    sp_tree: ET.Element | None, tolerance_emu: int
) -> list[dict[str, object]]:
    if sp_tree is None:
        return []
    candidates: list[tuple[ET.Element, dict[str, int], tuple[int, str]]] = []
    for shape in sp_tree.findall("./p:sp", NS):
        geometry = object_geometry(shape)
        signature = line_signature(shape)
        if geometry is not None and signature is not None:
            candidates.append((shape, geometry, signature))
    duplicates: list[dict[str, object]] = []
    for first, second in combinations(candidates, 2):
        if first[2] != second[2] or not near_equal_geometry(first[1], second[1], tolerance_emu):
            continue
        duplicates.append(
            {
                "first": object_name(first[0]),
                "second": object_name(second[0]),
                "geometry": first[1],
                "line_width_emu": first[2][0],
                "line_color": first[2][1],
            }
        )
    return duplicates


def text_findings(root: ET.Element) -> dict[str, object]:
    text_nodes = [node.text or "" for node in root.findall(".//a:t", NS)]
    placeholder_texts = sorted(
        {
            text.strip()
            for text in text_nodes
            if text.strip() and any(pattern.search(text.strip()) for pattern in PLACEHOLDER_PATTERNS)
        }
    )
    mojibake_texts = sorted(
        {text.strip() for text in text_nodes if any(marker in text for marker in MOJIBAKE_MARKERS)}
    )
    cjk_runs_without_ea_font: list[str] = []
    for run in root.findall(".//a:r", NS) + root.findall(".//a:fld", NS):
        text_node = run.find("a:t", NS)
        value = text_node.text if text_node is not None and text_node.text else ""
        if not CJK_PATTERN.search(value):
            continue
        run_properties = run.find("a:rPr", NS)
        east_asian = run_properties.find("a:ea", NS) if run_properties is not None else None
        if east_asian is None or not east_asian.attrib.get("typeface", "").strip():
            cjk_runs_without_ea_font.append(value)
    return {
        "text": "\n".join(text_nodes),
        "placeholder_texts": placeholder_texts,
        "mojibake_texts": mojibake_texts,
        "cjk_runs_without_explicit_ea_font": cjk_runs_without_ea_font,
    }


def inspect_raster_part(
    archive: zipfile.ZipFile,
    part: str,
    kind: str,
    slide_size: tuple[int, int],
    picture_area_threshold: float,
) -> dict[str, object]:
    root = read_xml(archive, part)
    relationships = read_relationships(archive, part)
    sp_tree = root.find("./p:cSld/p:spTree", NS)
    top_level_pictures = sp_tree.findall("./p:pic", NS) if sp_tree is not None else []
    full_slide_pictures: list[dict[str, object]] = []
    for picture in top_level_pictures:
        geometry = picture_geometry(picture, slide_size)
        if geometry and isinstance(geometry.get("area_ratio"), float):
            if geometry["area_ratio"] >= picture_area_threshold:
                full_slide_pictures.append(
                    {
                        "name": picture_name(picture),
                        "target": picture_target(picture, relationships, part),
                        "geometry": geometry,
                    }
                )

    background_blips = root.findall("./p:cSld/p:bg/p:bgPr/a:blipFill/a:blip", NS)
    background_targets = [
        target
        for target in (blip_target(blip, relationships, part) for blip in background_blips)
        if target
    ]
    return {
        "kind": kind,
        "part": part,
        "picture_count": len(root.findall(".//p:pic", NS)),
        "full_slide_picture_count": len(full_slide_pictures),
        "full_slide_pictures": full_slide_pictures,
        "background_image_count": len(background_blips),
        "background_image_targets": background_targets,
        "raster_risk": bool(full_slide_pictures or background_blips),
    }


def inherited_raster_parts(
    archive: zipfile.ZipFile,
    slide_part: str,
    slide_relationships: dict[str, str],
    slide_size: tuple[int, int],
    picture_area_threshold: float,
) -> list[dict[str, object]]:
    inherited: list[dict[str, object]] = []
    seen: set[str] = set()
    layout_parts = [
        resolve_target(slide_part, target)
        for target in slide_relationships.values()
        if "slideLayout" in target and target.endswith(".xml")
    ]
    for layout_part in layout_parts:
        if layout_part not in archive.namelist() or layout_part in seen:
            continue
        seen.add(layout_part)
        inherited.append(
            inspect_raster_part(
                archive,
                layout_part,
                "layout",
                slide_size,
                picture_area_threshold,
            )
        )
        layout_relationships = read_relationships(archive, layout_part)
        master_parts = [
            resolve_target(layout_part, target)
            for target in layout_relationships.values()
            if "slideMaster" in target and target.endswith(".xml")
        ]
        for master_part in master_parts:
            if master_part not in archive.namelist() or master_part in seen:
                continue
            seen.add(master_part)
            inherited.append(
                inspect_raster_part(
                    archive,
                    master_part,
                    "master",
                    slide_size,
                    picture_area_threshold,
                )
            )
    return inherited


def audit_slide(
    archive: zipfile.ZipFile,
    slide_part: str,
    slide_number: int,
    slide_size: tuple[int, int],
    picture_area_threshold: float,
    bounds_tolerance_emu: int,
) -> dict[str, object]:
    root = read_xml(archive, slide_part)
    relationships = read_relationships(archive, slide_part)
    shapes = root.findall(".//p:sp", NS)
    pictures = root.findall(".//p:pic", NS)
    connectors = root.findall(".//p:cxnSp", NS)
    groups = root.findall(".//p:grpSp", NS)
    graphic_frames = root.findall(".//p:graphicFrame", NS)
    charts = root.findall(".//c:chart", NS)
    tables = root.findall(".//a:tbl", NS)
    text_shapes = [
        shape
        for shape in shapes
        if shape.find("./p:txBody", NS) is not None and shape.findall(".//a:t", NS)
    ]
    text_characters = sum(len(node.text or "") for node in root.findall(".//a:t", NS))
    native_object_count = len(shapes) + len(connectors) + len(graphic_frames)

    sp_tree = root.find("./p:cSld/p:spTree", NS)
    geometry_risks = out_of_bounds_objects(sp_tree, slide_size, bounds_tolerance_emu)
    border_risks = duplicate_border_candidates(sp_tree, bounds_tolerance_emu)
    slide_text_findings = text_findings(root)
    top_level_pictures = sp_tree.findall("./p:pic", NS) if sp_tree is not None else []
    picture_details: list[dict[str, object]] = []
    full_slide_pictures: list[dict[str, object]] = []

    top_level_ids = {id(picture) for picture in top_level_pictures}
    for picture in pictures:
        geometry = picture_geometry(picture, slide_size) if id(picture) in top_level_ids else None
        detail: dict[str, object] = {
            "name": picture_name(picture),
            "target": picture_target(picture, relationships, slide_part),
            "top_level": id(picture) in top_level_ids,
            "geometry": geometry,
        }
        picture_details.append(detail)
        if geometry and isinstance(geometry.get("area_ratio"), float):
            if geometry["area_ratio"] >= picture_area_threshold:
                full_slide_pictures.append(detail)

    background_blips = root.findall("./p:cSld/p:bg/p:bgPr/a:blipFill/a:blip", NS)
    background_targets = [
        target
        for target in (blip_target(blip, relationships, slide_part) for blip in background_blips)
        if target
    ]
    inherited_parts = inherited_raster_parts(
        archive,
        slide_part,
        relationships,
        slide_size,
        picture_area_threshold,
    )
    inherited_raster_risks = [part for part in inherited_parts if part["raster_risk"]]

    warnings: list[str] = []
    if full_slide_pictures:
        warnings.append(
            f"{len(full_slide_pictures)} top-level picture(s) cover at least "
            f"{picture_area_threshold:.0%} of the slide."
        )
    if pictures and native_object_count == 0:
        warnings.append("The slide contains pictures but no detected native editable objects.")
    if background_blips:
        warnings.append(f"The slide uses {len(background_blips)} image background(s).")
    if inherited_raster_risks:
        locations = ", ".join(f"{part['kind']}:{part['part']}" for part in inherited_raster_risks)
        warnings.append(f"Raster-dominant content is inherited from {locations}.")
    if geometry_risks:
        warnings.append(f"{len(geometry_risks)} top-level object(s) extend outside the slide bounds.")
    if border_risks:
        warnings.append(f"{len(border_risks)} same-bounds duplicate border candidate(s) detected.")
    if slide_text_findings["placeholder_texts"]:
        warnings.append(
            f"{len(slide_text_findings['placeholder_texts'])} unresolved placeholder text value(s) detected."
        )
    if slide_text_findings["mojibake_texts"]:
        warnings.append(
            f"{len(slide_text_findings['mojibake_texts'])} suspicious mojibake text value(s) detected."
        )
    if slide_text_findings["cjk_runs_without_explicit_ea_font"]:
        warnings.append(
            f"{len(slide_text_findings['cjk_runs_without_explicit_ea_font'])} CJK run(s) lack an explicit East Asian font."
        )

    if full_slide_pictures or background_blips or inherited_raster_risks:
        classification = "raster-dominant-risk"
    elif pictures and native_object_count == 0:
        classification = "raster-only"
    elif pictures:
        classification = "mixed"
    elif native_object_count:
        classification = "native-only"
    else:
        classification = "empty-or-unsupported"

    max_area_ratio = max(
        (
            detail["geometry"]["area_ratio"]
            for detail in picture_details
            if detail.get("geometry") and detail["geometry"].get("area_ratio") is not None
        ),
        default=0.0,
    )

    return {
        "slide_number": slide_number,
        "part": slide_part,
        "classification": classification,
        "native_object_count": native_object_count,
        "shape_count": len(shapes),
        "text_shape_count": len(text_shapes),
        "text_character_count": text_characters,
        "connector_count": len(connectors),
        "group_count": len(groups),
        "graphic_frame_count": len(graphic_frames),
        "chart_count": len(charts),
        "table_count": len(tables),
        "picture_count": len(pictures),
        "background_image_count": len(background_blips),
        "background_image_targets": background_targets,
        "inherited_picture_count": sum(int(part["picture_count"]) for part in inherited_parts),
        "inherited_raster_risk_count": len(inherited_raster_risks),
        "inherited_parts": inherited_parts,
        "max_top_level_picture_area_ratio": round(float(max_area_ratio), 6),
        "full_slide_picture_count": len(full_slide_pictures),
        "pictures": picture_details,
        "text": slide_text_findings["text"],
        "placeholder_texts": slide_text_findings["placeholder_texts"],
        "mojibake_texts": slide_text_findings["mojibake_texts"],
        "cjk_runs_without_explicit_ea_font": slide_text_findings[
            "cjk_runs_without_explicit_ea_font"
        ],
        "out_of_bounds_objects": geometry_risks,
        "duplicate_border_candidates": border_risks,
        "warnings": warnings,
    }


def package_integrity_findings(archive: zipfile.ZipFile) -> dict[str, object]:
    zero_byte_media = sorted(
        name
        for name in archive.namelist()
        if name.startswith("ppt/media/") and not name.endswith("/") and archive.getinfo(name).file_size == 0
    )
    external_resources: list[dict[str, str]] = []
    broken_internal_resources: list[dict[str, str]] = []
    relationship_sources = [
        name
        for name in archive.namelist()
        if name.endswith(".xml") and not "/_rels/" in name
    ]
    for source_part in relationship_sources:
        for record in read_relationship_records(archive, source_part):
            relationship_type = record["type"].rsplit("/", 1)[-1]
            if record["target_mode"].lower() == "external":
                if relationship_type != "hyperlink":
                    external_resources.append(record)
                continue
            if relationship_type not in {"image", "audio", "video", "oleObject", "package"}:
                continue
            target = resolve_target(source_part, record["target"])
            if target not in archive.namelist():
                broken_internal_resources.append({**record, "resolved_target": target})
    return {
        "zero_byte_media": zero_byte_media,
        "external_resources": external_resources,
        "broken_internal_resources": broken_internal_resources,
    }


def audit_pptx(
    path: Path,
    picture_area_threshold: float,
    required_texts: list[str] | None = None,
    bounds_tolerance_emu: int = 12700,
    source_inventory: list[dict] | None = None,
    component_manifest: dict | None = None,
    manifest_path: Path | None = None,
) -> dict[str, object]:
    with zipfile.ZipFile(path) as archive:
        slide_parts, slide_size = slide_parts_in_order(archive)
        slides = [
            audit_slide(
                archive,
                slide_part,
                index,
                slide_size,
                picture_area_threshold,
                bounds_tolerance_emu,
            )
            for index, slide_part in enumerate(slide_parts, start=1)
        ]
        package_findings = package_integrity_findings(archive)
        objects = text_objects(archive, slide_parts)

    required_texts = unique_texts(required_texts)
    missing_required_texts = [
        value for value in required_texts if not any(text_occurrences(value, obj["text"]) for obj in objects)
    ]

    inventory_report = audit_text_inventory(source_inventory, objects)
    totals = {
        "missing_inventory_items": sum(not item["valid"] for item in inventory_report),
        "slides": len(slides),
        "native_objects": sum(int(slide["native_object_count"]) for slide in slides),
        "text_shapes": sum(int(slide["text_shape_count"]) for slide in slides),
        "connectors": sum(int(slide["connector_count"]) for slide in slides),
        "charts": sum(int(slide["chart_count"]) for slide in slides),
        "tables": sum(int(slide["table_count"]) for slide in slides),
        "pictures": sum(int(slide["picture_count"]) for slide in slides),
        "background_images": sum(int(slide["background_image_count"]) for slide in slides),
        "inherited_pictures": sum(int(slide["inherited_picture_count"]) for slide in slides),
        "inherited_raster_risks": sum(
            int(slide["inherited_raster_risk_count"]) for slide in slides
        ),
        "raster_dominant_slides": sum(
            slide["classification"] in {"raster-dominant-risk", "raster-only"}
            for slide in slides
        ),
        "warnings": sum(len(slide["warnings"]) for slide in slides),
        "out_of_bounds_objects": sum(len(slide["out_of_bounds_objects"]) for slide in slides),
        "duplicate_border_candidates": sum(
            len(slide["duplicate_border_candidates"]) for slide in slides
        ),
        "placeholder_texts": sum(len(slide["placeholder_texts"]) for slide in slides),
        "mojibake_texts": sum(len(slide["mojibake_texts"]) for slide in slides),
        "cjk_runs_without_explicit_ea_font": sum(
            len(slide["cjk_runs_without_explicit_ea_font"]) for slide in slides
        ),
        "required_texts": len(required_texts),
        "missing_required_texts": len(missing_required_texts),
        "zero_byte_media": len(package_findings["zero_byte_media"]),
        "external_resources": len(package_findings["external_resources"]),
        "broken_internal_resources": len(package_findings["broken_internal_resources"]),
    }
    blocking_risk_count = (
        int(totals["raster_dominant_slides"])
        + int(totals["out_of_bounds_objects"])
        + int(totals["duplicate_border_candidates"])
        + int(totals["placeholder_texts"])
        + int(totals["mojibake_texts"])
        + int(totals["missing_required_texts"])
        + int(totals["missing_inventory_items"])
        + int(totals["zero_byte_media"])
        + int(totals["external_resources"])
        + int(totals["broken_internal_resources"])
    )
    component_report = None
    if component_manifest and (component_manifest.get('editing_policy') == 'hybrid' or 'component_assets' in component_manifest):
        import importlib.util
        spec = importlib.util.spec_from_file_location('component_assets', Path(__file__).with_name('component_assets.py'))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        component_report = module.audit(path, component_manifest, manifest_path)
        blocking_risk_count += len(component_report['errors'])
    totals["blocking_risks"] = blocking_risk_count
    return {
        "input": str(path.resolve()),
        "slide_size_emu": {"width": slide_size[0], "height": slide_size[1]},
        "picture_area_threshold": picture_area_threshold,
        "bounds_tolerance_emu": bounds_tolerance_emu,
        "totals": totals,
        "components": component_report,
        "unverified": component_report.get('unverified', []) if component_report else [],
        "slides": slides,
        "content_integrity": {
            "inventory": inventory_report,
            "required_texts": required_texts,
            "missing_required_texts": missing_required_texts,
        },
        "package_integrity": package_findings,
        "interpretation": (
            "Picture coverage is a risk indicator, not a universal failure. "
            "The audit includes slide, background, layout, and master raster content. "
            "Large evidence images may be valid when their overlays remain editable and are disclosed. "
            "Duplicate borders are strong geometric candidates and still require visual confirmation. "
            "CJK runs without explicit East Asian fonts are warnings, not blocking risks."
        ),
    }


def print_summary(report: dict[str, object]) -> None:
    totals = report["totals"]
    print(f"PPTX: {report['input']}")
    print(
        "Summary: "
        f"slides={totals['slides']}, native_objects={totals['native_objects']}, "
        f"pictures={totals['pictures']}, backgrounds={totals['background_images']}, "
        f"inherited_pictures={totals['inherited_pictures']}, "
        f"raster_dominant_slides={totals['raster_dominant_slides']}, "
        f"bounds_risks={totals['out_of_bounds_objects']}, "
        f"duplicate_borders={totals['duplicate_border_candidates']}, "
        f"missing_text={totals['missing_required_texts']}, "
        f"package_risks={totals['zero_byte_media'] + totals['external_resources'] + totals['broken_internal_resources']}, "
        f"blocking_risks={totals['blocking_risks']}, "
        f"warnings={totals['warnings']}"
    )
    for slide in report["slides"]:
        print(
            f"Slide {slide['slide_number']}: {slide['classification']} | "
            f"native={slide['native_object_count']} | text={slide['text_shape_count']} | "
            f"connectors={slide['connector_count']} | charts={slide['chart_count']} | "
            f"tables={slide['table_count']} | pictures={slide['picture_count']}"
        )
        for warning in slide["warnings"]:
            print(f"  WARNING: {warning}")
    for value in report["content_integrity"]["missing_required_texts"]:
        print(f"  RISK: Missing required text: {value}")
    for part in report["package_integrity"]["zero_byte_media"]:
        print(f"  RISK: Zero-byte media part: {part}")
    for relation in report["package_integrity"]["external_resources"]:
        print(f"  RISK: External resource: {relation['target']}")
    for relation in report["package_integrity"]["broken_internal_resources"]:
        print(f"  RISK: Missing internal resource: {relation['resolved_target']}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect a PPTX for native editable objects and raster-dominant slides."
    )
    parser.add_argument("pptx", type=Path, help="PowerPoint file to audit")
    parser.add_argument("--json", dest="json_path", type=Path, help="Optional JSON report path")
    parser.add_argument(
        "--manifest",
        type=Path,
        help="Optional visual manifest; source_inventory text becomes required deck text",
    )
    parser.add_argument(
        "--require-text",
        action="append",
        default=[],
        help="Text that must occur in the deck; repeat for multiple values",
    )
    parser.add_argument(
        "--picture-area-threshold",
        type=float,
        default=0.8,
        help="Flag top-level pictures covering at least this fraction of the slide (default: 0.8)",
    )
    parser.add_argument(
        "--bounds-tolerance-emu",
        type=int,
        default=12700,
        help="Allowed object-boundary tolerance in EMU (default: 12700, one point)",
    )
    parser.add_argument(
        "--fail-on-risk",
        action="store_true",
        help="Exit with status 1 for blocking raster, content, geometry, or package-integrity risks",
    )
    return parser.parse_args()


def main() -> int:
    configure_utf8_console()
    args = parse_args()
    if not 0 < args.picture_area_threshold <= 1:
        print("ERROR: --picture-area-threshold must be greater than 0 and at most 1.", file=sys.stderr)
        return 2
    if args.bounds_tolerance_emu < 0:
        print("ERROR: --bounds-tolerance-emu must not be negative.", file=sys.stderr)
        return 2
    if not args.pptx.is_file():
        print(f"ERROR: PPTX not found: {args.pptx}", file=sys.stderr)
        return 2
    if args.manifest is not None and not args.manifest.is_file():
        print(f"ERROR: Manifest not found: {args.manifest}", file=sys.stderr)
        return 2
    try:
        manifest_texts = required_texts_from_manifest(args.manifest)
        report = audit_pptx(
            args.pptx,
            args.picture_area_threshold,
            required_texts=[*manifest_texts, *args.require_text],
            source_inventory=json.loads(args.manifest.read_text(encoding="utf-8")).get("source_inventory", []) if args.manifest else [],
            component_manifest=json.loads(args.manifest.read_text(encoding="utf-8")) if args.manifest else None,
            manifest_path=args.manifest,
            bounds_tolerance_emu=args.bounds_tolerance_emu,
        )
    except (zipfile.BadZipFile, KeyError, ET.ParseError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: Could not audit PPTX: {exc}", file=sys.stderr)
        return 2

    print_summary(report)
    if args.json_path:
        args.json_path.parent.mkdir(parents=True, exist_ok=True)
        args.json_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"JSON report: {args.json_path.resolve()}")

    if args.fail_on_risk and (report["totals"]["blocking_risks"] or report.get("unverified")):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
