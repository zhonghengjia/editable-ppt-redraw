from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "audit-diagram-grammar.py"
SPEC = importlib.util.spec_from_file_location("audit_diagram_grammar", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def manifest() -> dict[str, object]:
    return {
        "diagram_grammar": {
            "visual_type": "cohort_flowchart",
            "preserve_visual_type": True,
            "allow_representation_change": False,
            "routing": "orthogonal",
            "node_roles": {
                "cohort": {
                    "role": "cohort_process",
                    "allowed_geometries": ["rect", "roundRect"],
                    "output_names": ["cohort-box"],
                },
                "exclusion": {
                    "role": "exclusion",
                    "allowed_geometries": ["rect"],
                    "output_names": ["exclusion-box"],
                },
            },
            "edge_roles": {
                "cohort-to-exclusion": {
                    "role": "exclusion_route",
                    "output_name_regex": "^flow-cohort-to-exclusion-",
                }
            },
        }
    }


def layout_elements() -> list[dict[str, object]]:
    return [
        {"name": "cohort-box", "geometry": "roundRect"},
        {"name": "exclusion-box", "geometry": "rect"},
        {"name": "flow-cohort-to-exclusion-segment-1", "geometry": "line"},
        {"name": "flow-cohort-to-exclusion-segment-2", "geometry": "line"},
    ]


class DiagramGrammarAuditTests(unittest.TestCase):
    def test_matching_node_shapes_and_semantic_edge_lines_pass(self) -> None:
        report = MODULE.audit_grammar(manifest(), [{"elements": layout_elements()}])
        self.assertTrue(report["valid"], report["issues"])
        self.assertEqual(report["stats"]["matched_node_objects"], 2)
        self.assertEqual(report["stats"]["matched_edge_objects"], 2)

    def test_wrong_node_geometry_fails(self) -> None:
        elements = layout_elements()
        elements[1]["geometry"] = "ellipse"
        report = MODULE.audit_grammar(manifest(), [{"elements": elements}])
        self.assertFalse(report["valid"])
        self.assertTrue(any("uses geometry 'ellipse'" in issue for issue in report["issues"]))

    def test_missing_required_role_object_fails(self) -> None:
        elements = [item for item in layout_elements() if item["name"] != "cohort-box"]
        report = MODULE.audit_grammar(manifest(), [{"elements": elements}])
        self.assertFalse(report["valid"])
        self.assertTrue(any("missing required output object 'cohort-box'" in issue for issue in report["issues"]))

    def test_semantic_edge_must_match_an_editable_line(self) -> None:
        elements = layout_elements()
        for item in elements:
            if str(item["name"]).startswith("flow-cohort-to-exclusion-"):
                item["geometry"] = "rect"
        report = MODULE.audit_grammar(manifest(), [{"elements": elements}])
        self.assertFalse(report["valid"])
        self.assertTrue(any("has no editable line" in issue for issue in report["issues"]))

    def test_unrecorded_representation_change_fails_defensively(self) -> None:
        data = copy.deepcopy(manifest())
        data["diagram_grammar"]["preserve_visual_type"] = False
        report = MODULE.audit_grammar(data, [{"elements": layout_elements()}])
        self.assertFalse(report["valid"])
        self.assertTrue(any("disabled without" in issue for issue in report["issues"]))


if __name__ == "__main__":
    unittest.main()
