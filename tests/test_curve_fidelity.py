from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))


def load_script(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


EXTRACT = load_script("extract_curve_trace", "extract-curve-trace.py")
AUDIT = load_script("audit_curve_fidelity", "audit-curve-fidelity.py")


def profile_points(two_peaks: bool = True) -> list[list[float]]:
    if two_peaks:
        anchors = [(0.0, 0.0), (0.18, 0.12), (0.32, 1.0), (0.50, 0.18), (0.70, 0.90), (0.84, 0.15), (1.0, 0.0)]
    else:
        anchors = [(0.0, 0.0), (0.30, 0.18), (0.55, 1.0), (0.78, 0.20), (1.0, 0.0)]
    points: list[list[float]] = []
    for index in range(201):
        x = index / 200
        for left, right in zip(anchors, anchors[1:]):
            if left[0] <= x <= right[0]:
                fraction = (x - left[0]) / (right[0] - left[0])
                points.append([x, left[1] + fraction * (right[1] - left[1])])
                break
    return points


def pptx_with_profile(path: Path, points: list[list[float]], shape_name: str = "ridge-fill") -> None:
    commands = [f'<a:moveTo><a:pt x="0" y="1000"/></a:moveTo>']
    for x, signal in points:
        commands.append(f'<a:lnTo><a:pt x="{int(round(x * 1000))}" y="{int(round((1 - signal) * 1000))}"/></a:lnTo>')
    commands.extend(['<a:lnTo><a:pt x="1000" y="1000"/></a:lnTo>', '<a:close/>'])
    slide = f'''<?xml version="1.0" encoding="UTF-8"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
 <p:cSld><p:spTree><p:sp><p:nvSpPr><p:cNvPr id="2" name="{shape_name}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
 <p:spPr><a:custGeom><a:pathLst><a:path w="1000" h="1000">{''.join(commands)}</a:path></a:pathLst></a:custGeom></p:spPr>
 </p:sp></p:spTree></p:cSld>
</p:sld>'''
    with zipfile.ZipFile(path, "w") as package:
        package.writestr("ppt/slides/slide1.xml", slide)


def curve_manifest() -> dict[str, object]:
    return {
        "curve_fidelity": {
            "basis": "source_observed",
            "measurement": "x_aligned_profile",
            "default_max_x_aligned_mae": 0.08,
            "default_peak_x_tolerance": 0.06,
            "default_peak_prominence": 0.08,
            "default_min_peak_distance": 0.06,
            "series": [
                {
                    "id": "ridge-1",
                    "source_inventory_id": "ridge-source",
                    "kind": "filled_ridge",
                    "source_trace": "ridge-source.json",
                    "output_name_regex": "^ridge-fill$",
                    "expected_peak_count": 2,
                    "expected_peak_positions": [0.32, 0.70],
                }
            ],
        }
    }


class CurveFidelityTests(unittest.TestCase):
    def test_raster_extractor_preserves_two_peaks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            image_path = Path(directory) / "ridge.png"
            image = Image.new("RGB", (101, 61), "white")
            draw = ImageDraw.Draw(image)
            profile = profile_points(True)
            polygon = [(int(round(x * 100)), int(round(58 - signal * 50))) for x, signal in profile]
            polygon.extend([(100, 58), (0, 58)])
            draw.polygon(polygon, fill="#58A942")
            image.save(image_path)
            result = EXTRACT.extract_curve_trace(
                image_path,
                (0, 0, 101, 61),
                [(0x58, 0xA9, 0x42)],
                tolerance=5,
                mode="upper_envelope",
                baseline_y=58,
                min_peak_prominence=0.08,
            )
        self.assertEqual(len(result["peaks"]), 2)
        self.assertGreater(result["trace_quality"]["column_coverage"], 0.95)

    def test_matching_native_pptx_profile_passes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = root / "manifest.json"
            trace_path = root / "ridge-source.json"
            output = root / "out.pptx"
            trace_path.write_text(json.dumps({"points": profile_points(True)}), encoding="utf-8")
            manifest = curve_manifest()
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            pptx_with_profile(output, profile_points(True))
            report = AUDIT.audit_curve_fidelity(manifest, manifest_path, output)
        self.assertTrue(report["valid"], report["issues"])
        self.assertEqual(report["series"]["ridge-1"]["expected_peak_count"], 2)

    def test_single_peak_template_fails_two_peak_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = root / "manifest.json"
            trace_path = root / "ridge-source.json"
            output = root / "out.pptx"
            trace_path.write_text(json.dumps({"points": profile_points(True)}), encoding="utf-8")
            manifest = curve_manifest()
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            pptx_with_profile(output, profile_points(False))
            report = AUDIT.audit_curve_fidelity(manifest, manifest_path, output)
        self.assertFalse(report["valid"])
        self.assertTrue(any("prominent peaks" in issue for issue in report["issues"]))

    def test_duplicate_native_path_assignment_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = root / "manifest.json"
            trace_path = root / "ridge-source.json"
            output = root / "out.pptx"
            trace_path.write_text(json.dumps({"points": profile_points(True)}), encoding="utf-8")
            manifest = curve_manifest()
            duplicate = dict(manifest["curve_fidelity"]["series"][0])
            duplicate["id"] = "ridge-2"
            manifest["curve_fidelity"]["series"].append(duplicate)
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            pptx_with_profile(output, profile_points(True))
            report = AUDIT.audit_curve_fidelity(manifest, manifest_path, output)
        self.assertFalse(report["valid"])
        self.assertTrue(any("assigned to multiple" in issue for issue in report["issues"]))


if __name__ == "__main__":
    unittest.main()
