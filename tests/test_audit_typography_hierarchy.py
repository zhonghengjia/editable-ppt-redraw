from __future__ import annotations

import importlib.util
import tempfile
import unittest
import zipfile
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "audit-typography-hierarchy.py"
SPEC = importlib.util.spec_from_file_location("audit_typography_hierarchy", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def manifest() -> dict[str, object]:
    return {
        "typography_hierarchy": {
            "basis": "source_observed",
            "measurement": "resolved_font_size",
            "baseline_role": "body",
            "default_tolerance": 0.10,
            "default_max_intra_role_spread": 0.10,
            "roles": {
                "title": {
                    "target_ratio": 1.5,
                    "output_name_regex": "^title-",
                },
                "body": {
                    "target_ratio": 1.0,
                    "output_name_regex": "^body-",
                },
                "footnote": {
                    "target_ratio": 0.6,
                    "output_name_regex": "^footnote-",
                },
            },
        }
    }


def layout(title: float = 24, body: float = 16, footnote: float = 9.6) -> dict[str, object]:
    return {
        "elements": [
            {"name": "title-main", "text": "Title", "resolvedFontSize": title},
            {"name": "body-one", "text": "Body", "resolvedFontSize": body},
            {"name": "body-two", "text": "Body", "resolvedTextStyle": {"fontSize": body}},
            {"name": "footnote-source", "text": "Note", "resolvedFontSize": footnote},
        ]
    }


class TypographyHierarchyAuditTests(unittest.TestCase):
    def test_expected_role_ratios_pass(self) -> None:
        report = MODULE.audit_typography(manifest(), [layout()])
        self.assertTrue(report["valid"], report["issues"])
        self.assertEqual(report["stats"]["measured_roles"], 3)
        self.assertAlmostEqual(report["roles"]["footnote"]["observed_ratio"], 0.6)

    def test_flattened_footnote_ratio_fails(self) -> None:
        report = MODULE.audit_typography(manifest(), [layout(footnote=14)])
        self.assertFalse(report["valid"])
        self.assertTrue(any("footnote" in issue and "outside" in issue for issue in report["issues"]))

    def test_overlapping_role_regexes_fail(self) -> None:
        data = manifest()
        data["typography_hierarchy"]["roles"]["title"]["output_name_regex"] = ".*"
        report = MODULE.audit_typography(data, [layout()])
        self.assertFalse(report["valid"])
        self.assertTrue(any("multiple typography roles" in issue for issue in report["issues"]))

    def test_missing_required_role_fails(self) -> None:
        source = layout()
        source["elements"] = [item for item in source["elements"] if not item["name"].startswith("footnote-")]
        report = MODULE.audit_typography(manifest(), [source])
        self.assertFalse(report["valid"])
        self.assertTrue(any("footnote" in issue and "matched no" in issue for issue in report["issues"]))

    def test_intra_role_size_drift_fails(self) -> None:
        source = layout()
        source["elements"][2]["resolvedTextStyle"]["fontSize"] = 20
        report = MODULE.audit_typography(manifest(), [source])
        self.assertFalse(report["valid"])
        self.assertTrue(any("intra-role spread" in issue for issue in report["issues"]))

    def test_native_pptx_reader_preserves_run_sizes(self) -> None:
        slide = """<?xml version="1.0" encoding="UTF-8"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
 xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
 <p:cSld><p:spTree>
  <p:sp><p:nvSpPr><p:cNvPr id="2" name="title-main"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
   <p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r><a:rPr sz="1800"/><a:t>Title</a:t></a:r></a:p></p:txBody>
  </p:sp>
  <p:sp><p:nvSpPr><p:cNvPr id="3" name="footnote-source"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
   <p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r><a:rPr sz="700"/><a:t>Note</a:t></a:r></a:p></p:txBody>
  </p:sp>
 </p:spTree></p:cSld>
</p:sld>"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sizes.pptx"
            with zipfile.ZipFile(path, "w") as package:
                package.writestr("ppt/slides/slide1.xml", slide)
            elements, slide_count = MODULE.collect_pptx_elements(path)
        self.assertEqual(slide_count, 1)
        sizes = {element["name"]: element["resolvedFontSize"] for element in elements}
        self.assertEqual(sizes, {"title-main": 18.0, "footnote-source": 7.0})


if __name__ == "__main__":
    unittest.main()
