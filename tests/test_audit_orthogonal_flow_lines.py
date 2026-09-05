from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "audit-orthogonal-flow-lines.py"


class OrthogonalFlowLineAuditTests(unittest.TestCase):
    def run_audit(self, elements: list[dict[str, object]]) -> tuple[int, dict[str, object]]:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            layout_path = root / "slide.layout.json"
            report_path = root / "report.json"
            layout_path.write_text(json.dumps({"elements": elements}), encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    str(layout_path),
                    "--require-matches",
                    "--fail-on-risk",
                    "--json",
                    str(report_path),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            report = json.loads(report_path.read_text(encoding="utf-8"))
            return result.returncode, report

    def test_connected_numbered_route_passes(self) -> None:
        code, report = self.run_audit(
            [
                {"geometry": "line", "name": "flow-main-segment-1", "bbox": [0, 0, 10, 0]},
                {"geometry": "line", "name": "flow-main-segment-2", "bbox": [10, 0, 0, 5]},
            ]
        )
        self.assertEqual(code, 0)
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["continuity_routes"], 1)

    def test_route_gap_and_numbering_gap_fail(self) -> None:
        code, report = self.run_audit(
            [
                {"geometry": "line", "name": "flow-main-segment-1", "bbox": [0, 0, 10, 0]},
                {"geometry": "line", "name": "flow-main-segment-3", "bbox": [12, 0, 0, 5]},
            ]
        )
        risks = {issue["risk"] for issue in report["issues"]}
        self.assertEqual(code, 1)
        self.assertIn("route-segment-numbering-gap", risks)
        self.assertIn("disconnected-route", risks)

    def test_branch_that_misses_named_bus_fails(self) -> None:
        code, report = self.run_audit(
            [
                {"geometry": "line", "name": "flow-main-bus", "bbox": [0, 5, 10, 0]},
                {"geometry": "line", "name": "flow-main-left-segment-1", "bbox": [2, 0, 0, 4.5]},
            ]
        )
        risks = {issue["risk"] for issue in report["issues"]}
        self.assertEqual(code, 1)
        self.assertIn("route-misses-bus", risks)

    def test_near_parallel_duplicate_bus_fails(self) -> None:
        code, report = self.run_audit(
            [
                {"geometry": "line", "name": "flow-main-bus-1", "bbox": [0, 5, 10, 0]},
                {"geometry": "line", "name": "flow-main-bus-2", "bbox": [0, 5.4, 10, 0]},
            ]
        )
        risks = {issue["risk"] for issue in report["issues"]}
        self.assertEqual(code, 1)
        self.assertIn("misaligned-parallel-bus", risks)


if __name__ == "__main__":
    unittest.main()
