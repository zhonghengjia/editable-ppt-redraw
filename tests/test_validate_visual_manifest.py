from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate-visual-manifest.py"
SPEC = importlib.util.spec_from_file_location("validate_visual_manifest", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def valid_manifest() -> dict[str, object]:
    return {
        "schema_version": 1,
        "mode": "faithful",
        "execution_profile": "dense",
        "source": {"path": "reference.png", "width": 1000, "height": 600},
        "canvas": {"width": 1000, "height": 600},
        "targets": [{"format": "pptx", "path": "result.pptx"}],
        "modules": [
            {"id": "left", "bbox": [20, 20, 300, 200]},
            {"id": "right", "bbox": [400, 20, 300, 200]},
        ],
        "source_inventory": [
            {
                "id": "left-label",
                "module": "left",
                "role": "text",
                "bbox": [40, 40, 200, 30],
                "text": "稳定",
                "representation": "native_primitive",
            },
            {
                "id": "right-label",
                "module": "right",
                "role": "text",
                "bbox": [420, 40, 200, 30],
                "text": "不稳定",
                "representation": "native_primitive",
            },
        ],
        "connections": [
            {"id": "left-to-right", "source": "left", "target": "right"}
        ],
        "diagram_grammar": {
            "visual_type": "clinical_flowchart",
            "preserve_visual_type": True,
            "allow_representation_change": False,
            "routing": "orthogonal",
            "node_roles": {
                "left": {
                    "role": "process",
                    "allowed_geometries": ["rect", "roundRect"],
                    "output_names": ["left-box"],
                },
                "right": {
                    "role": "process",
                    "allowed_geometries": ["rect", "roundRect"],
                    "output_names": ["right-box"],
                },
            },
            "edge_roles": {
                "left-to-right": {
                    "role": "main_flow",
                    "output_name_regex": "^flow-left-to-right-",
                }
            },
        },
        "semantic_constraints": [
            {
                "id": "route-required",
                "type": "must_connect",
                "subjects": ["left", "right"],
                "rule": "The two modules must be connected.",
                "verification": "Inspect the reopened render.",
            }
        ],
        "negative_constraints": [],
    }


class VisualManifestValidationTests(unittest.TestCase):
    def test_dense_manifest_with_inventory_and_constraint_passes(self) -> None:
        report = MODULE.validate_manifest(valid_manifest())
        self.assertTrue(report["valid"], report["errors"])
        self.assertEqual(report["stats"]["source_inventory"], 2)
        self.assertEqual(report["stats"]["semantic_constraints"], 1)
        self.assertEqual(report["stats"]["diagram_node_roles"], 2)
        self.assertEqual(report["stats"]["diagram_edge_roles"], 1)

    def test_dense_manifest_requires_inventory_coverage_for_every_module(self) -> None:
        manifest = valid_manifest()
        manifest["source_inventory"] = manifest["source_inventory"][:1]
        report = MODULE.validate_manifest(manifest)
        self.assertFalse(report["valid"])
        self.assertTrue(any("right" in message and "no visible items" in message for message in report["errors"]))

    def test_constraint_subject_must_reference_a_known_id(self) -> None:
        manifest = valid_manifest()
        manifest["semantic_constraints"][0]["subjects"] = ["left", "missing"]
        report = MODULE.validate_manifest(manifest)
        self.assertFalse(report["valid"])
        self.assertTrue(any("unknown ID" in message for message in report["errors"]))

    def test_raster_representation_requires_a_declared_exception(self) -> None:
        manifest = copy.deepcopy(valid_manifest())
        manifest["source_inventory"][0]["representation"] = "source_crop"
        manifest["source_inventory"][0]["raster_exception"] = "missing-raster"
        report = MODULE.validate_manifest(manifest)
        self.assertFalse(report["valid"])
        self.assertTrue(any("unknown raster exception" in message for message in report["errors"]))

    def test_negative_constraint_rejects_a_positive_only_type(self) -> None:
        manifest = valid_manifest()
        manifest["negative_constraints"] = [
            {
                "id": "misfiled-rule",
                "type": "must_connect",
                "subjects": ["left", "right"],
                "rule": "This positive rule is in the wrong list.",
                "verification": "Validate the manifest.",
            }
        ]
        report = MODULE.validate_manifest(manifest)
        self.assertFalse(report["valid"])
        self.assertTrue(any("not valid for negative_constraints" in message for message in report["errors"]))

    def test_structured_dense_manifest_requires_diagram_grammar(self) -> None:
        manifest = valid_manifest()
        del manifest["diagram_grammar"]
        report = MODULE.validate_manifest(manifest)
        self.assertFalse(report["valid"])
        self.assertTrue(any("require diagram_grammar" in message for message in report["errors"]))

    def test_diagram_grammar_must_cover_connected_node_roles(self) -> None:
        manifest = valid_manifest()
        del manifest["diagram_grammar"]["node_roles"]["right"]
        report = MODULE.validate_manifest(manifest)
        self.assertFalse(report["valid"])
        self.assertTrue(
            any("does not cover connected module(s): right" in message for message in report["errors"])
        )

    def test_diagram_grammar_must_cover_every_connection(self) -> None:
        manifest = valid_manifest()
        manifest["diagram_grammar"]["edge_roles"] = {}
        report = MODULE.validate_manifest(manifest)
        self.assertFalse(report["valid"])
        self.assertTrue(
            any("does not cover connection(s): left-to-right" in message for message in report["errors"])
        )

    def test_representation_change_requires_explicit_authorization(self) -> None:
        manifest = valid_manifest()
        manifest["diagram_grammar"]["preserve_visual_type"] = False
        manifest["diagram_grammar"]["allow_representation_change"] = True
        report = MODULE.validate_manifest(manifest)
        self.assertFalse(report["valid"])
        self.assertTrue(any("explicit user authorization" in message for message in report["errors"]))

    def test_authorized_representation_change_passes(self) -> None:
        manifest = valid_manifest()
        manifest["diagram_grammar"]["preserve_visual_type"] = False
        manifest["diagram_grammar"]["allow_representation_change"] = True
        manifest["diagram_grammar"]["authorization"] = "Convert the flowchart to a timeline."
        report = MODULE.validate_manifest(manifest)
        self.assertTrue(report["valid"], report["errors"])

    def test_diagram_grammar_rejects_invalid_edge_name_regex(self) -> None:
        manifest = valid_manifest()
        manifest["diagram_grammar"]["edge_roles"]["left-to-right"]["output_name_regex"] = "["
        report = MODULE.validate_manifest(manifest)
        self.assertFalse(report["valid"])
        self.assertTrue(any("output_name_regex is invalid" in message for message in report["errors"]))

    def test_valid_typography_hierarchy_passes(self) -> None:
        manifest = valid_manifest()
        manifest["typography_hierarchy"] = {
            "basis": "source_observed",
            "measurement": "resolved_font_size",
            "baseline_role": "node_label",
            "default_tolerance": 0.12,
            "default_max_intra_role_spread": 0.10,
            "roles": {
                "title": {
                    "target_ratio": 1.4,
                    "output_name_regex": "^title-",
                },
                "node_label": {
                    "target_ratio": 1.0,
                    "output_name_regex": "^node-.*-label$",
                },
            },
        }
        report = MODULE.validate_manifest(manifest)
        self.assertTrue(report["valid"], report["errors"])
        self.assertEqual(report["stats"]["typography_roles"], 2)

    def test_typography_baseline_ratio_must_equal_one(self) -> None:
        manifest = valid_manifest()
        manifest["typography_hierarchy"] = {
            "basis": "source_estimated",
            "measurement": "resolved_font_size",
            "baseline_role": "body",
            "default_tolerance": 0.15,
            "default_max_intra_role_spread": 0.10,
            "roles": {
                "body": {
                    "target_ratio": 1.2,
                    "output_name_regex": "^body-",
                }
            },
        }
        report = MODULE.validate_manifest(manifest)
        self.assertFalse(report["valid"])
        self.assertTrue(any("baseline role" in message for message in report["errors"]))

    def test_typography_role_regex_must_compile(self) -> None:
        manifest = valid_manifest()
        manifest["typography_hierarchy"] = {
            "basis": "source_observed",
            "measurement": "resolved_font_size",
            "baseline_role": "body",
            "default_tolerance": 0.12,
            "default_max_intra_role_spread": 0.10,
            "roles": {
                "body": {
                    "target_ratio": 1.0,
                    "output_name_regex": "[",
                }
            },
        }
        report = MODULE.validate_manifest(manifest)
        self.assertFalse(report["valid"])
        self.assertTrue(any("output_name_regex is invalid" in message for message in report["errors"]))

    def test_valid_curve_fidelity_contract_passes(self) -> None:
        manifest = copy.deepcopy(valid_manifest())
        manifest["source_inventory"].append(
            {
                "id": "ridge-source",
                "module": "right",
                "role": "chart",
                "bbox": [430, 90, 180, 90],
                "representation": "native_composite",
            }
        )
        manifest["curve_fidelity"] = {
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
                    "source_trace": "traces/ridge-1.json",
                    "output_name_regex": "^ridge-1-fill$",
                    "expected_output_count": 1,
                    "expected_peak_count": 2,
                    "expected_peak_positions": [0.35, 0.68],
                }
            ],
        }
        report = MODULE.validate_manifest(manifest)
        self.assertTrue(report["valid"], report["errors"])
        self.assertEqual(report["stats"]["curve_series"], 1)

    def test_curve_fidelity_requires_known_inventory_item(self) -> None:
        manifest = copy.deepcopy(valid_manifest())
        manifest["curve_fidelity"] = {
            "basis": "source_estimated",
            "measurement": "x_aligned_profile",
            "default_max_x_aligned_mae": 0.10,
            "default_peak_x_tolerance": 0.08,
            "default_peak_prominence": 0.08,
            "default_min_peak_distance": 0.06,
            "series": [
                {
                    "id": "ridge-1",
                    "source_inventory_id": "missing",
                    "kind": "filled_ridge",
                    "source_trace": "traces/ridge-1.json",
                    "output_name_regex": "^ridge-1-fill$",
                }
            ],
        }
        report = MODULE.validate_manifest(manifest)
        self.assertFalse(report["valid"])
        self.assertTrue(any("unknown source item" in message for message in report["errors"]))

    def test_curve_peak_positions_must_match_peak_count(self) -> None:
        manifest = copy.deepcopy(valid_manifest())
        manifest["source_inventory"].append(
            {
                "id": "ridge-source",
                "module": "right",
                "role": "chart",
                "representation": "native_composite",
            }
        )
        manifest["curve_fidelity"] = {
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
                    "source_trace": "traces/ridge-1.json",
                    "output_name_regex": "^ridge-1-fill$",
                    "expected_peak_count": 2,
                    "expected_peak_positions": [0.5],
                }
            ],
        }
        report = MODULE.validate_manifest(manifest)
        self.assertFalse(report["valid"])
        self.assertTrue(any("count must equal" in message for message in report["errors"]))


if __name__ == "__main__":
    unittest.main()
