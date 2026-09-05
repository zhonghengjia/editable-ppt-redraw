from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "audit-raster-asset-integrity.py"
SPEC = importlib.util.spec_from_file_location("audit_raster_asset_integrity", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def run_audit(path: Path) -> dict[str, object]:
    return MODULE.audit_asset(
        path,
        alpha_threshold=8,
        edge_risk_ratio=0.02,
        min_long_edge=32,
        min_occupancy=0.05,
        max_occupancy=0.96,
    )


class RasterAssetIntegrityTests(unittest.TestCase):
    def test_transparent_asset_with_padding_passes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "padded.png"
            image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
            ImageDraw.Draw(image).ellipse((10, 10, 54, 54), fill=(10, 46, 104, 255))
            image.save(path)
            report = run_audit(path)
        self.assertTrue(report["valid"])
        self.assertFalse(report["risks"])

    def test_alpha_subject_touching_edge_is_a_risk(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "clipped.png"
            image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
            ImageDraw.Draw(image).rectangle((0, 10, 40, 54), fill=(10, 46, 104, 255))
            image.save(path)
            report = run_audit(path)
        self.assertTrue(any("edge-risk band" in message for message in report["risks"]))
        self.assertTrue(report["edge_risk"]["left"])

    def test_opaque_asset_reports_limitation_without_false_clipping_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "opaque.png"
            Image.new("RGB", (64, 64), "white").save(path)
            report = run_audit(path)
        self.assertFalse(report["risks"])
        self.assertTrue(any("not evaluated" in message for message in report["warnings"]))


if __name__ == "__main__":
    unittest.main()
