from __future__ import annotations

import importlib.util
import tempfile
import unittest
import zipfile
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "audit-pptx-editability.py"
SPEC = importlib.util.spec_from_file_location("audit_pptx_editability", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

PRESENTATION = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
 xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
 <p:sldIdLst><p:sldId id="256" r:id="rId1"/></p:sldIdLst>
 <p:sldSz cx="12192000" cy="6858000"/>
</p:presentation>"""

PRESENTATION_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
 <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide1.xml"/>
</Relationships>"""


def shape_xml(
    identifier: int,
    name: str,
    x: int,
    y: int,
    width: int,
    height: int,
    text: str = "",
    rotation: int = 0,
) -> str:
    text_body = ""
    if text:
        text_body = f"""<p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r><a:rPr lang="zh-CN"><a:ea typeface="Microsoft YaHei"/></a:rPr><a:t>{text}</a:t></a:r></a:p></p:txBody>"""
    return f"""<p:sp>
 <p:nvSpPr><p:cNvPr id="{identifier}" name="{name}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
 <p:spPr><a:xfrm rot="{rotation}"><a:off x="{x}" y="{y}"/><a:ext cx="{width}" cy="{height}"/></a:xfrm>
 <a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:ln w="12700"><a:solidFill><a:srgbClr val="0A2E68"/></a:solidFill></a:ln></p:spPr>
 {text_body}</p:sp>"""


def write_minimal_pptx(path: Path, shapes: list[str]) -> None:
    slide = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
 xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
 <p:cSld><p:spTree>
  <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
  <p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
  {''.join(shapes)}
 </p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sld>"""
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("ppt/presentation.xml", PRESENTATION)
        archive.writestr("ppt/_rels/presentation.xml.rels", PRESENTATION_RELS)
        archive.writestr("ppt/slides/slide1.xml", slide)


class PptxEditabilityAuditTests(unittest.TestCase):
    def test_required_text_uses_unicode_and_whitespace_normalization(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "text.pptx"
            write_minimal_pptx(path, [shape_xml(2, "label", 100, 100, 1000000, 300000, "生命体征")])
            report = MODULE.audit_pptx(
                path,
                0.8,
                required_texts=["生命 体征", "缺失文字"],
            )
        self.assertEqual(report["totals"]["missing_required_texts"], 1)
        self.assertEqual(report["content_integrity"]["missing_required_texts"], ["缺失文字"])

    def test_duplicate_border_and_out_of_bounds_objects_are_blocking_risks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "geometry.pptx"
            shapes = [
                shape_xml(2, "panel", 100, 100, 1000000, 300000),
                shape_xml(3, "panel-overlay", 100, 100, 1000000, 300000),
                shape_xml(4, "outside", 12100000, 100, 500000, 300000),
            ]
            write_minimal_pptx(path, shapes)
            report = MODULE.audit_pptx(path, 0.8)
        self.assertEqual(report["totals"]["duplicate_border_candidates"], 1)
        self.assertEqual(report["totals"]["out_of_bounds_objects"], 1)
        self.assertGreaterEqual(report["totals"]["blocking_risks"], 2)

    def test_placeholder_and_mojibake_are_detected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "text-risk.pptx"
            shapes = [
                shape_xml(2, "placeholder", 100, 100, 1000000, 300000, "Click to add text"),
                shape_xml(3, "mojibake", 1200000, 100, 1000000, 300000, "Ãbad"),
            ]
            write_minimal_pptx(path, shapes)
            report = MODULE.audit_pptx(path, 0.8)
        self.assertEqual(report["totals"]["placeholder_texts"], 1)
        self.assertEqual(report["totals"]["mojibake_texts"], 1)

    def test_rotated_visible_bounds_are_used_for_boundary_audit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rotated.pptx"
            shape = shape_xml(
                2,
                "vertical-axis-title",
                -542925,
                2000000,
                1714500,
                400050,
                "Target cell lysis (%)",
                rotation=16200000,
            )
            write_minimal_pptx(path, [shape])
            report = MODULE.audit_pptx(path, 0.8)
        self.assertEqual(report["totals"]["out_of_bounds_objects"], 0)

    def test_zero_byte_media_is_a_package_integrity_risk(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "media-risk.pptx"
            write_minimal_pptx(path, [shape_xml(2, "label", 100, 100, 1000000, 300000, "Complete")])
            with zipfile.ZipFile(path, "a") as archive:
                archive.writestr("ppt/media/image1.png", b"")
            report = MODULE.audit_pptx(path, 0.8)
        self.assertEqual(report["totals"]["zero_byte_media"], 1)
        self.assertEqual(report["totals"]["blocking_risks"], 1)


if __name__ == "__main__":
    unittest.main()
