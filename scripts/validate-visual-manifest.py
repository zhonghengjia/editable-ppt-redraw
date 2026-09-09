#!/usr/bin/env python3
"""Validate the compact visual-manifest contract used by the skill."""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import re
import sys
from pathlib import Path
from typing import Any


SUPPORTED_MODES = {"faithful", "semantic", "redesign"}
SUPPORTED_EXECUTION_PROFILES = {"fast", "standard", "dense"}
SUPPORTED_REPRESENTATIONS = {
    "native_primitive",
    "native_composite",
    "source_crop",
    "evidence_raster",
}
SUPPORTED_ITEM_ROLES = {
    "text",
    "shape",
    "icon",
    "connector",
    "image",
    "evidence",
    "decoration",
    "chart",
    "table",
}
SUPPORTED_CONSTRAINT_TYPES = {
    "must_connect",
    "must_not_connect",
    "must_contain",
    "must_not_overlap",
    "must_preserve_text",
    "single_stroke_owner",
    "same_style_token",
    "custom",
}
CONSTRAINT_TYPES_BY_FIELD = {
    "semantic_constraints": {
        "must_connect",
        "must_contain",
        "must_preserve_text",
        "same_style_token",
        "custom",
    },
    "negative_constraints": {
        "must_not_connect",
        "must_not_overlap",
        "single_stroke_owner",
        "custom",
    },
}
SUPPORTED_FORMATS = {
    "pptx",
    "svg",
    "drawio",
    "excalidraw",
    "mermaid",
    "graphviz",
    "dot",
    "html",
}
SUPPORTED_ROUTING = {"orthogonal", "direct", "curved", "mixed", "source_defined"}
SUPPORTED_TYPOGRAPHY_BASES = {
    "source_observed",
    "source_estimated",
    "user_specified",
    "redesign_system",
}
SUPPORTED_TYPOGRAPHY_MEASUREMENTS = {"resolved_font_size"}
SUPPORTED_CURVE_BASES = {
    "source_vector",
    "raw_data",
    "source_observed",
    "source_estimated",
    "user_specified",
}
SUPPORTED_CURVE_MEASUREMENTS = {"x_aligned_profile"}
SUPPORTED_CURVE_KINDS = {
    "line_curve",
    "filled_ridge",
    "density_outline",
    "step_curve",
    "signal_trace",
}


def is_positive_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0


def validate_bbox(value: Any, location: str, errors: list[str]) -> list[float] | None:
    if not isinstance(value, list) or len(value) != 4:
        errors.append(f"{location}: bbox must be [left, top, width, height]")
        return None
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in value):
        errors.append(f"{location}: bbox values must be finite numbers")
        return None
    left, top, width, height = (float(v) for v in value)
    if width <= 0 or height <= 0:
        errors.append(f"{location}: bbox width and height must be positive")
        return None
    if left < 0 or top < 0:
        errors.append(f"{location}: bbox left and top must be non-negative")
        return None
    return [left, top, width, height]


def validate_manifest(data: Any) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    stats: dict[str, Any] = {}

    if not isinstance(data, dict):
        return {"valid": False, "errors": ["manifest root must be an object"], "warnings": [], "stats": {}}

    if data.get("schema_version") != 1:
        errors.append("schema_version must equal 1")

    mode = data.get("mode")
    if mode not in SUPPORTED_MODES:
        errors.append(f"mode must be one of {sorted(SUPPORTED_MODES)}")

    execution_profile = data.get("execution_profile")
    if execution_profile is not None and execution_profile not in SUPPORTED_EXECUTION_PROFILES:
        errors.append(f"execution_profile must be one of {sorted(SUPPORTED_EXECUTION_PROFILES)} when provided")

    source = data.get("source")
    if not isinstance(source, dict) or not isinstance(source.get("path"), str) or not source.get("path", "").strip():
        errors.append("source.path must be a non-empty string")
    elif source:
        for key in ("width", "height"):
            if key in source and not is_positive_number(source[key]):
                errors.append(f"source.{key} must be a positive number when provided")

    canvas = data.get("canvas")
    canvas_width = canvas_height = None
    if not isinstance(canvas, dict):
        errors.append("canvas must be an object")
    else:
        canvas_width = canvas.get("width")
        canvas_height = canvas.get("height")
        if not is_positive_number(canvas_width):
            errors.append("canvas.width must be a positive number")
        if not is_positive_number(canvas_height):
            errors.append("canvas.height must be a positive number")

    targets = data.get("targets")
    if not isinstance(targets, list) or not targets:
        errors.append("targets must be a non-empty list")
        targets = []
    seen_target_paths: set[str] = set()
    for index, target in enumerate(targets):
        location = f"targets[{index}]"
        if not isinstance(target, dict):
            errors.append(f"{location} must be an object")
            continue
        fmt = str(target.get("format", "")).lower()
        if fmt not in SUPPORTED_FORMATS:
            errors.append(f"{location}.format is unsupported: {fmt!r}")
        path = target.get("path")
        if not isinstance(path, str) or not path.strip():
            errors.append(f"{location}.path must be a non-empty string")
        elif path in seen_target_paths:
            errors.append(f"{location}.path duplicates another target: {path}")
        else:
            seen_target_paths.add(path)

    modules = data.get("modules")
    if not isinstance(modules, list) or not modules:
        errors.append("modules must be a non-empty list for a manifest-backed task")
        modules = []
    module_ids: set[str] = set()
    for index, module in enumerate(modules):
        location = f"modules[{index}]"
        if not isinstance(module, dict):
            errors.append(f"{location} must be an object")
            continue
        module_id = module.get("id")
        if not isinstance(module_id, str) or not module_id.strip():
            errors.append(f"{location}.id must be a non-empty string")
        elif module_id in module_ids:
            errors.append(f"{location}.id is duplicated: {module_id}")
        else:
            module_ids.add(module_id)
        bbox = validate_bbox(module.get("bbox"), location, errors)
        if bbox and is_positive_number(canvas_width) and is_positive_number(canvas_height):
            left, top, width, height = bbox
            if left + width > float(canvas_width) + 1e-6 or top + height > float(canvas_height) + 1e-6:
                errors.append(f"{location}: bbox extends beyond the manifest canvas")

    source_inventory = data.get("source_inventory", [])
    component_spec = importlib.util.spec_from_file_location("component_fidelity", Path(__file__).with_name("component_fidelity.py"))
    component_module = importlib.util.module_from_spec(component_spec)
    component_spec.loader.exec_module(component_module)
    errors.extend(component_module.validate_contract(data))
    if not isinstance(source_inventory, list):
        errors.append("source_inventory must be a list when provided")
        source_inventory = []
    if execution_profile == "dense" and not source_inventory:
        errors.append("dense manifests require a non-empty source_inventory")
    elif execution_profile == "standard" and mode == "faithful" and not source_inventory:
        warnings.append("faithful standard manifest has no source_inventory coverage list")

    source_item_ids: set[str] = set()
    inventory_modules: set[str] = set()
    raster_inventory_refs: list[tuple[str, str]] = []
    for index, item in enumerate(source_inventory):
        location = f"source_inventory[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{location} must be an object")
            continue
        item_id = item.get("id")
        if not isinstance(item_id, str) or not item_id.strip():
            errors.append(f"{location}.id must be a non-empty string")
        elif item_id in source_item_ids or item_id in module_ids:
            errors.append(f"{location}.id is duplicated or collides with a module: {item_id}")
        else:
            source_item_ids.add(item_id)
        module_id = item.get("module")
        if module_id not in module_ids:
            errors.append(f"{location}.module references an unknown module: {module_id!r}")
        else:
            inventory_modules.add(module_id)
        role = item.get("role")
        if role not in SUPPORTED_ITEM_ROLES:
            errors.append(f"{location}.role must be one of {sorted(SUPPORTED_ITEM_ROLES)}")
        representation = item.get("representation")
        if representation not in SUPPORTED_REPRESENTATIONS:
            errors.append(
                f"{location}.representation must be one of {sorted(SUPPORTED_REPRESENTATIONS)}"
            )
        for key in ("output_slide", "required_count"):
            value = item.get(key, 1)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                errors.append(f"{location}.{key} must be a positive integer")
        for key in ("output_name", "output_id"):
            if key in item and (not isinstance(item[key], str) or not item[key].strip()):
                errors.append(f"{location}.{key} must be a non-empty string")
        if role == "text":
            text = item.get("text")
            if not isinstance(text, str) or not text.strip():
                errors.append(f"{location}.text must be non-empty for a text item")
        if "bbox" in item:
            bbox = validate_bbox(item["bbox"], location, errors)
            if bbox and is_positive_number(canvas_width) and is_positive_number(canvas_height):
                left, top, width, height = bbox
                if left + width > float(canvas_width) + 1e-6 or top + height > float(canvas_height) + 1e-6:
                    errors.append(f"{location}: bbox extends beyond the manifest canvas")
        if representation in {"source_crop", "evidence_raster"}:
            raster_reference = item.get("raster_exception")
            if not isinstance(raster_reference, str) or not raster_reference.strip():
                errors.append(
                    f"{location}.raster_exception must reference a declared raster exception"
                )
            else:
                raster_inventory_refs.append((location, raster_reference))

    if execution_profile == "dense":
        uncovered_modules = sorted(module_ids - inventory_modules)
        if uncovered_modules:
            errors.append(
                "dense source_inventory has no visible items for module(s): "
                + ", ".join(uncovered_modules)
            )

    icon_signatures = data.get("icon_signatures", [])
    if not isinstance(icon_signatures, list):
        errors.append("icon_signatures must be a list when provided")
        icon_signatures = []
    icon_ids: set[str] = set()
    for index, icon in enumerate(icon_signatures):
        location = f"icon_signatures[{index}]"
        if not isinstance(icon, dict):
            errors.append(f"{location} must be an object")
            continue
        icon_id = icon.get("id")
        if not isinstance(icon_id, str) or not icon_id.strip():
            errors.append(f"{location}.id must be a non-empty string")
        elif icon_id in icon_ids:
            errors.append(f"{location}.id is duplicated: {icon_id}")
        else:
            icon_ids.add(icon_id)
        module_id = icon.get("module")
        if module_id not in module_ids:
            errors.append(f"{location}.module references an unknown module: {module_id!r}")
        object_class = icon.get("object_class")
        if not isinstance(object_class, str) or not object_class.strip():
            errors.append(f"{location}.object_class must be a non-empty string")
        required_features = icon.get("required_features")
        if (
            not isinstance(required_features, list)
            or not required_features
            or not all(isinstance(feature, str) and feature.strip() for feature in required_features)
        ):
            errors.append(f"{location}.required_features must be a non-empty list of non-empty strings")
        if "source_crop" in icon:
            crop = validate_bbox(icon["source_crop"], f"{location}.source_crop", errors)
            if crop and is_positive_number(canvas_width) and is_positive_number(canvas_height):
                left, top, width, height = crop
                if left + width > float(canvas_width) + 1e-6 or top + height > float(canvas_height) + 1e-6:
                    errors.append(f"{location}.source_crop extends beyond the manifest canvas")

    connections = data.get("connections", [])
    if not isinstance(connections, list):
        errors.append("connections must be a list when provided")
        connections = []
    connection_ids: set[str] = set()
    connected_module_ids: set[str] = set()
    for index, connection in enumerate(connections):
        location = f"connections[{index}]"
        if not isinstance(connection, dict):
            errors.append(f"{location} must be an object")
            continue
        connection_id = connection.get("id")
        if not isinstance(connection_id, str) or not connection_id.strip():
            errors.append(f"{location}.id must be a non-empty string")
        elif connection_id in connection_ids:
            errors.append(f"{location}.id is duplicated: {connection_id}")
        else:
            connection_ids.add(connection_id)
        for endpoint in ("source", "target"):
            value = connection.get(endpoint)
            if value not in module_ids:
                errors.append(f"{location}.{endpoint} references an unknown module: {value!r}")
            else:
                connected_module_ids.add(value)

    diagram_grammar = data.get("diagram_grammar")
    structured_visual = bool(connections) or any(
        isinstance(item, dict) and item.get("role") == "connector"
        for item in source_inventory
    )
    if structured_visual and execution_profile in {"standard", "dense"} and diagram_grammar is None:
        errors.append("structured standard/dense manifests require diagram_grammar")

    diagram_node_roles: dict[str, Any] = {}
    diagram_edge_roles: dict[str, Any] = {}
    if diagram_grammar is not None:
        if not isinstance(diagram_grammar, dict):
            errors.append("diagram_grammar must be an object when provided")
        else:
            visual_type = diagram_grammar.get("visual_type")
            if not isinstance(visual_type, str) or not visual_type.strip():
                errors.append("diagram_grammar.visual_type must be a non-empty string")

            preserve_visual_type = diagram_grammar.get("preserve_visual_type")
            if not isinstance(preserve_visual_type, bool):
                errors.append("diagram_grammar.preserve_visual_type must be a boolean")

            allow_representation_change = diagram_grammar.get("allow_representation_change")
            if not isinstance(allow_representation_change, bool):
                errors.append("diagram_grammar.allow_representation_change must be a boolean")
            elif allow_representation_change:
                authorization = diagram_grammar.get("authorization")
                if not isinstance(authorization, str) or not authorization.strip():
                    errors.append(
                        "diagram_grammar.authorization must record explicit user authorization "
                        "when allow_representation_change is true"
                    )
            elif preserve_visual_type is False:
                errors.append(
                    "diagram_grammar cannot disable visual-type preservation without "
                    "allow_representation_change"
                )

            routing = diagram_grammar.get("routing")
            if routing not in SUPPORTED_ROUTING:
                errors.append(
                    f"diagram_grammar.routing must be one of {sorted(SUPPORTED_ROUTING)}"
                )

            raw_node_roles = diagram_grammar.get("node_roles")
            if not isinstance(raw_node_roles, dict):
                errors.append("diagram_grammar.node_roles must be an object")
            else:
                diagram_node_roles = raw_node_roles
                if structured_visual and not diagram_node_roles:
                    errors.append("structured diagram_grammar.node_roles must not be empty")
                known_node_ids = module_ids | source_item_ids
                seen_output_names: set[str] = set()
                for subject_id, spec in diagram_node_roles.items():
                    location = f"diagram_grammar.node_roles[{subject_id!r}]"
                    if subject_id not in known_node_ids:
                        errors.append(f"{location} references an unknown module or source item")
                    if not isinstance(spec, dict):
                        errors.append(f"{location} must be an object")
                        continue
                    role = spec.get("role")
                    if not isinstance(role, str) or not role.strip():
                        errors.append(f"{location}.role must be a non-empty string")
                    allowed_geometries = spec.get("allowed_geometries")
                    if (
                        not isinstance(allowed_geometries, list)
                        or not allowed_geometries
                        or not all(
                            isinstance(value, str) and value.strip()
                            for value in allowed_geometries
                        )
                    ):
                        errors.append(
                            f"{location}.allowed_geometries must be a non-empty list "
                            "of non-empty strings"
                        )
                    output_names = spec.get("output_names")
                    if (
                        not isinstance(output_names, list)
                        or not output_names
                        or not all(isinstance(value, str) and value.strip() for value in output_names)
                    ):
                        errors.append(
                            f"{location}.output_names must be a non-empty list of non-empty strings"
                        )
                    else:
                        for output_name in output_names:
                            if output_name in seen_output_names:
                                errors.append(
                                    f"{location}.output_names duplicates another node-role output: "
                                    f"{output_name!r}"
                                )
                            seen_output_names.add(output_name)

                uncovered_endpoints = sorted(connected_module_ids - set(diagram_node_roles))
                if uncovered_endpoints:
                    errors.append(
                        "diagram_grammar.node_roles does not cover connected module(s): "
                        + ", ".join(uncovered_endpoints)
                    )

            raw_edge_roles = diagram_grammar.get("edge_roles")
            if not isinstance(raw_edge_roles, dict):
                errors.append("diagram_grammar.edge_roles must be an object")
            else:
                diagram_edge_roles = raw_edge_roles
                unknown_edge_ids = sorted(set(diagram_edge_roles) - connection_ids)
                if unknown_edge_ids:
                    errors.append(
                        "diagram_grammar.edge_roles references unknown connection(s): "
                        + ", ".join(unknown_edge_ids)
                    )
                uncovered_connections = sorted(connection_ids - set(diagram_edge_roles))
                if uncovered_connections:
                    errors.append(
                        "diagram_grammar.edge_roles does not cover connection(s): "
                        + ", ".join(uncovered_connections)
                    )
                for connection_id, spec in diagram_edge_roles.items():
                    location = f"diagram_grammar.edge_roles[{connection_id!r}]"
                    if not isinstance(spec, dict):
                        errors.append(f"{location} must be an object")
                        continue
                    binding = spec.get("endpoint_binding")
                    if binding is not None:
                        if not isinstance(binding, dict):
                            errors.append(f"{location}.endpoint_binding must be an object")
                        else:
                            for end in ("source_output_name", "target_output_name"):
                                if not isinstance(binding.get(end), str) or not binding[end].strip():
                                    errors.append(f"{location}.endpoint_binding.{end} must be a non-empty string")
                            names = binding.get("ordered_output_names")
                            if names is not None and (not isinstance(names, list) or not names or any(not isinstance(n, str) or not n.strip() for n in names) or len(names) != len(set(str(n) for n in names))):
                                errors.append(f"{location}.endpoint_binding.ordered_output_names must be unique non-empty strings")
                            tol = binding.get("tolerance", .01)
                            if isinstance(tol, bool) or not isinstance(tol, (float, int)) or not math.isfinite(tol) or tol < 0:
                                errors.append(f"{location}.endpoint_binding.tolerance must be finite nonnegative")
                    role = spec.get("role")
                    if not isinstance(role, str) or not role.strip():
                        errors.append(f"{location}.role must be a non-empty string")
                    pattern = spec.get("output_name_regex")
                    if not isinstance(pattern, str) or not pattern.strip():
                        errors.append(f"{location}.output_name_regex must be a non-empty string")
                    else:
                        try:
                            re.compile(pattern)
                        except re.error as exc:
                            errors.append(f"{location}.output_name_regex is invalid: {exc}")

    typography_hierarchy = data.get("typography_hierarchy")
    typography_roles: dict[str, Any] = {}
    if typography_hierarchy is not None:
        if not isinstance(typography_hierarchy, dict):
            errors.append("typography_hierarchy must be an object when provided")
        else:
            basis = typography_hierarchy.get("basis")
            if basis not in SUPPORTED_TYPOGRAPHY_BASES:
                errors.append(
                    "typography_hierarchy.basis must be one of "
                    f"{sorted(SUPPORTED_TYPOGRAPHY_BASES)}"
                )
            if basis == "redesign_system" and mode != "redesign":
                errors.append(
                    "typography_hierarchy.basis 'redesign_system' requires mode 'redesign'"
                )

            measurement = typography_hierarchy.get("measurement")
            if measurement not in SUPPORTED_TYPOGRAPHY_MEASUREMENTS:
                errors.append(
                    "typography_hierarchy.measurement must be one of "
                    f"{sorted(SUPPORTED_TYPOGRAPHY_MEASUREMENTS)}"
                )

            for key in ("default_tolerance", "default_max_intra_role_spread"):
                value = typography_hierarchy.get(key)
                if (
                    not isinstance(value, (int, float))
                    or isinstance(value, bool)
                    or not math.isfinite(value)
                    or value < 0
                    or value > 0.5
                ):
                    errors.append(f"typography_hierarchy.{key} must be between 0 and 0.5")

            run_limit = typography_hierarchy.get("default_max_intra_object_run_spread", .5)
            if isinstance(run_limit, bool) or not isinstance(run_limit, (float, int)) or not math.isfinite(run_limit) or run_limit < 0:
                errors.append("typography_hierarchy.default_max_intra_object_run_spread must be finite nonnegative")
            raw_roles = typography_hierarchy.get("roles")
            if not isinstance(raw_roles, dict) or not raw_roles:
                errors.append("typography_hierarchy.roles must be a non-empty object")
            else:
                typography_roles = raw_roles
                for role_name, spec in typography_roles.items():
                    location = f"typography_hierarchy.roles[{role_name!r}]"
                    if not isinstance(role_name, str) or not role_name.strip():
                        errors.append("typography_hierarchy role names must be non-empty strings")
                    if not isinstance(spec, dict):
                        errors.append(f"{location} must be an object")
                        continue
                    limit = spec.get("max_intra_object_run_spread", .5)
                    if isinstance(limit, bool) or not isinstance(limit, (float, int)) or not math.isfinite(limit) or limit < 0:
                        errors.append(f"{location}.max_intra_object_run_spread must be finite nonnegative")
                    if not isinstance(spec.get("allow_script_runs", True), bool):
                        errors.append(f"{location}.allow_script_runs must be boolean")
                    exceptions = spec.get("run_exceptions", [])
                    if not isinstance(exceptions, list):
                        errors.append(f"{location}.run_exceptions must be a list")
                    else:
                        for exception in exceptions:
                            if not isinstance(exception, dict):
                                errors.append(f"{location}.run_exceptions entries must be objects")
                                continue
                            try:
                                if not isinstance(exception.get("reason"), str) or not exception["reason"].strip():
                                    raise ValueError("nonempty reason required")
                                re.compile(exception["text_regex"])
                                low, high = exception["min_size_ratio"], exception["max_size_ratio"]
                                if not is_positive_number(low) or not is_positive_number(high) or low > high:
                                    raise ValueError("ordered positive ratio bounds required")
                            except (ValueError, KeyError, TypeError, re.error) as exc:
                                errors.append(f"{location}.run_exceptions: {exc}")
                    target_ratio = spec.get("target_ratio")
                    if not is_positive_number(target_ratio):
                        errors.append(f"{location}.target_ratio must be a positive number")
                    pattern = spec.get("output_name_regex")
                    if not isinstance(pattern, str) or not pattern.strip():
                        errors.append(f"{location}.output_name_regex must be a non-empty string")
                    else:
                        try:
                            re.compile(pattern)
                        except re.error as exc:
                            errors.append(f"{location}.output_name_regex is invalid: {exc}")
                    for key in ("tolerance", "max_intra_role_spread"):
                        if key not in spec:
                            continue
                        value = spec[key]
                        if (
                            not isinstance(value, (int, float))
                            or isinstance(value, bool)
                            or not math.isfinite(value)
                            or value < 0
                            or value > 0.5
                        ):
                            errors.append(f"{location}.{key} must be between 0 and 0.5")
                    if "required" in spec and not isinstance(spec["required"], bool):
                        errors.append(f"{location}.required must be a boolean when provided")

                baseline_role = typography_hierarchy.get("baseline_role")
                if not isinstance(baseline_role, str) or baseline_role not in typography_roles:
                    errors.append(
                        "typography_hierarchy.baseline_role must name a declared typography role"
                    )
                else:
                    baseline_spec = typography_roles.get(baseline_role)
                    baseline_ratio = (
                        baseline_spec.get("target_ratio")
                        if isinstance(baseline_spec, dict)
                        else None
                    )
                    if not isinstance(baseline_ratio, (int, float)) or abs(baseline_ratio - 1.0) > 1e-9:
                        errors.append(
                            "typography_hierarchy baseline role must have target_ratio 1.0"
                        )

    curve_fidelity = data.get("curve_fidelity")
    curve_series: list[dict[str, Any]] = []
    if curve_fidelity is not None:
        if not isinstance(curve_fidelity, dict):
            errors.append("curve_fidelity must be an object when provided")
        else:
            basis = curve_fidelity.get("basis")
            if basis not in SUPPORTED_CURVE_BASES:
                errors.append(
                    "curve_fidelity.basis must be one of "
                    f"{sorted(SUPPORTED_CURVE_BASES)}"
                )
            measurement = curve_fidelity.get("measurement")
            if measurement not in SUPPORTED_CURVE_MEASUREMENTS:
                errors.append(
                    "curve_fidelity.measurement must be one of "
                    f"{sorted(SUPPORTED_CURVE_MEASUREMENTS)}"
                )
            for key in (
                "default_max_x_aligned_mae",
                "default_peak_x_tolerance",
                "default_peak_prominence",
                "default_min_peak_distance",
            ):
                value = curve_fidelity.get(key)
                if (
                    not isinstance(value, (int, float))
                    or isinstance(value, bool)
                    or not math.isfinite(value)
                    or value < 0
                    or value > 0.5
                ):
                    errors.append(f"curve_fidelity.{key} must be between 0 and 0.5")

            raw_series = curve_fidelity.get("series")
            if not isinstance(raw_series, list) or not raw_series:
                errors.append("curve_fidelity.series must be a non-empty list")
            else:
                series_ids: set[str] = set()
                trace_paths: set[str] = set()
                curve_series = [item for item in raw_series if isinstance(item, dict)]
                for index, spec in enumerate(raw_series):
                    location = f"curve_fidelity.series[{index}]"
                    if not isinstance(spec, dict):
                        errors.append(f"{location} must be an object")
                        continue
                    series_id = spec.get("id")
                    if not isinstance(series_id, str) or not series_id.strip():
                        errors.append(f"{location}.id must be a non-empty string")
                    elif series_id in series_ids:
                        errors.append(f"{location}.id is duplicated: {series_id}")
                    else:
                        series_ids.add(series_id)

                    source_inventory_id = spec.get("source_inventory_id")
                    if source_inventory_id not in source_item_ids:
                        errors.append(
                            f"{location}.source_inventory_id references an unknown source item: "
                            f"{source_inventory_id!r}"
                        )
                    kind = spec.get("kind")
                    if kind not in SUPPORTED_CURVE_KINDS:
                        errors.append(
                            f"{location}.kind must be one of {sorted(SUPPORTED_CURVE_KINDS)}"
                        )
                    trace_path = spec.get("source_trace")
                    if not isinstance(trace_path, str) or not trace_path.strip():
                        errors.append(f"{location}.source_trace must be a non-empty task-relative path")
                    else:
                        candidate = Path(trace_path)
                        if candidate.is_absolute() or ".." in candidate.parts:
                            errors.append(f"{location}.source_trace must be task-relative and may not contain '..'")
                        elif trace_path in trace_paths:
                            errors.append(f"{location}.source_trace duplicates another series: {trace_path}")
                        else:
                            trace_paths.add(trace_path)

                    pattern = spec.get("output_name_regex")
                    if not isinstance(pattern, str) or not pattern.strip():
                        errors.append(f"{location}.output_name_regex must be a non-empty string")
                    else:
                        try:
                            re.compile(pattern)
                        except re.error as exc:
                            errors.append(f"{location}.output_name_regex is invalid: {exc}")

                    selected = spec.get("output_path_index")
                    if selected is not None and (isinstance(selected, bool) or not isinstance(selected, int) or selected < 0):
                        errors.append(f"{location}.output_path_index must be a nonnegative integer")
                    frame = spec.get("coordinate_frame", "shape")
                    if frame not in ("shape", "slide_bbox"):
                        errors.append(f"{location}.coordinate_frame must be shape or slide_bbox")
                    if frame == "slide_bbox":
                        validate_bbox(spec.get("output_bbox"), f"{location}.output_bbox", errors)
                    if spec.get("profile_mode", "upper_envelope") not in ("upper_envelope", "lower_envelope", "centerline"):
                        errors.append(f"{location}.profile_mode is unsupported")
                    expected_output_count = spec.get("expected_output_count", 1)
                    if (
                        not isinstance(expected_output_count, int)
                        or isinstance(expected_output_count, bool)
                        or expected_output_count < 1
                    ):
                        errors.append(f"{location}.expected_output_count must be a positive integer")
                    expected_peak_count = spec.get("expected_peak_count")
                    if expected_peak_count is not None and (
                        not isinstance(expected_peak_count, int)
                        or isinstance(expected_peak_count, bool)
                        or expected_peak_count < 0
                    ):
                        errors.append(f"{location}.expected_peak_count must be a non-negative integer")
                    expected_positions = spec.get("expected_peak_positions")
                    if expected_positions is not None:
                        if (
                            not isinstance(expected_positions, list)
                            or not all(
                                isinstance(value, (int, float))
                                and not isinstance(value, bool)
                                and math.isfinite(value)
                                and 0 <= value <= 1
                                for value in expected_positions
                            )
                        ):
                            errors.append(
                                f"{location}.expected_peak_positions must contain only numbers from 0 to 1"
                            )
                        elif isinstance(expected_peak_count, int) and len(expected_positions) != expected_peak_count:
                            errors.append(
                                f"{location}.expected_peak_positions count must equal expected_peak_count"
                            )
                    for key in (
                        "max_x_aligned_mae",
                        "peak_x_tolerance",
                        "peak_prominence",
                        "min_peak_distance",
                    ):
                        if key not in spec:
                            continue
                        value = spec[key]
                        if (
                            not isinstance(value, (int, float))
                            or isinstance(value, bool)
                            or not math.isfinite(value)
                            or value < 0
                            or value > 0.5
                        ):
                            errors.append(f"{location}.{key} must be between 0 and 0.5")
                    if "required" in spec and not isinstance(spec["required"], bool):
                        errors.append(f"{location}.required must be a boolean when provided")

    raster_exceptions = data.get("raster_exceptions", [])
    if not isinstance(raster_exceptions, list):
        errors.append("raster_exceptions must be a list when provided")
        raster_exceptions = []
    raster_ids: set[str] = set()
    for index, item in enumerate(raster_exceptions):
        location = f"raster_exceptions[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{location} must be an object")
            continue
        item_id = item.get("id")
        if not isinstance(item_id, str) or not item_id.strip():
            errors.append(f"{location}.id must be a non-empty string")
        elif item_id in raster_ids:
            errors.append(f"{location}.id is duplicated: {item_id}")
        else:
            raster_ids.add(item_id)
        reason = item.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            errors.append(f"{location}.reason must explain why raster is necessary")
        if "bbox" in item:
            validate_bbox(item["bbox"], location, errors)

    for location, raster_reference in raster_inventory_refs:
        if raster_reference not in raster_ids:
            errors.append(
                f"{location}.raster_exception references an unknown raster exception: "
                f"{raster_reference!r}"
            )

    known_subject_ids = module_ids | source_item_ids | connection_ids | icon_ids | raster_ids

    constraint_ids: set[str] = set()

    def validate_constraints(field: str) -> list[dict[str, Any]]:
        constraints = data.get(field, [])
        if not isinstance(constraints, list):
            errors.append(f"{field} must be a list when provided")
            return []
        valid_constraints: list[dict[str, Any]] = []
        for index, constraint in enumerate(constraints):
            location = f"{field}[{index}]"
            if not isinstance(constraint, dict):
                errors.append(f"{location} must be an object")
                continue
            constraint_id = constraint.get("id")
            if not isinstance(constraint_id, str) or not constraint_id.strip():
                errors.append(f"{location}.id must be a non-empty string")
            elif constraint_id in constraint_ids:
                errors.append(f"{location}.id is duplicated across constraints: {constraint_id}")
            else:
                constraint_ids.add(constraint_id)
            constraint_type = constraint.get("type")
            if constraint_type not in SUPPORTED_CONSTRAINT_TYPES:
                errors.append(
                    f"{location}.type must be one of {sorted(SUPPORTED_CONSTRAINT_TYPES)}"
                )
            elif constraint_type not in CONSTRAINT_TYPES_BY_FIELD[field]:
                errors.append(
                    f"{location}.type {constraint_type!r} is not valid for {field}; "
                    f"use one of {sorted(CONSTRAINT_TYPES_BY_FIELD[field])}"
                )
            subjects = constraint.get("subjects")
            if (
                not isinstance(subjects, list)
                or not subjects
                or not all(isinstance(subject, str) and subject.strip() for subject in subjects)
            ):
                errors.append(f"{location}.subjects must be a non-empty list of IDs")
            else:
                for subject in subjects:
                    if subject not in known_subject_ids:
                        errors.append(f"{location}.subjects references an unknown ID: {subject!r}")
            for key in ("rule", "verification"):
                value = constraint.get(key)
                if not isinstance(value, str) or not value.strip():
                    errors.append(f"{location}.{key} must be a non-empty string")
            valid_constraints.append(constraint)
        return valid_constraints

    semantic_constraints = validate_constraints("semantic_constraints")
    negative_constraints = validate_constraints("negative_constraints")

    uncertainties = data.get("uncertainties", [])
    if not isinstance(uncertainties, list):
        errors.append("uncertainties must be a list when provided")
        uncertainties = []
    for index, item in enumerate(uncertainties):
        if isinstance(item, str):
            if not item.strip():
                warnings.append(f"uncertainties[{index}] is empty")
        elif isinstance(item, dict):
            detail = item.get("detail")
            if not isinstance(detail, str) or not detail.strip():
                warnings.append(f"uncertainties[{index}] lacks a non-empty detail")
        else:
            warnings.append(f"uncertainties[{index}] should be a string or object")

    surface_spec = importlib.util.spec_from_file_location('surface_relations', Path(__file__).with_name('surface_relations.py'))
    surface_module = importlib.util.module_from_spec(surface_spec)
    surface_spec.loader.exec_module(surface_module)
    errors.extend(surface_module.validate_contract(data))

    clearance_spec = importlib.util.spec_from_file_location('text_clearance', Path(__file__).with_name('text_clearance.py'))
    clearance_module = importlib.util.module_from_spec(clearance_spec)
    clearance_spec.loader.exec_module(clearance_module)
    errors.extend(clearance_module.validate_contract(data))

    stats.update(
        {
            "targets": len(targets),
            "modules": len(modules),
            "source_inventory": len(source_inventory),
            "connections": len(connections),
            "diagram_grammar": isinstance(diagram_grammar, dict),
            "diagram_node_roles": len(diagram_node_roles),
            "diagram_edge_roles": len(diagram_edge_roles),
            "typography_hierarchy": isinstance(typography_hierarchy, dict),
            "typography_roles": len(typography_roles),
            "curve_fidelity": isinstance(curve_fidelity, dict),
            "curve_series": len(curve_series),
            "icon_signatures": len(icon_signatures),
            "raster_exceptions": len(raster_exceptions),
            "semantic_constraints": len(semantic_constraints),
            "negative_constraints": len(negative_constraints),
            "uncertainties": len(uncertainties),
        }
    )
    return {"valid": not errors, "errors": errors, "warnings": warnings, "stats": stats}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate an editable-visual reconstruction manifest.")
    parser.add_argument("manifest", type=Path, help="Path to manifest JSON")
    parser.add_argument("--json", dest="json_path", type=Path, help="Optional JSON report path")
    parser.add_argument("--fail-on-warning", action="store_true", help="Return nonzero when warnings exist")
    args = parser.parse_args()

    try:
        data = json.loads(args.manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        report = {"valid": False, "errors": [f"cannot read manifest: {exc}"], "warnings": [], "stats": {}}
    else:
        report = validate_manifest(data)

    report["manifest"] = str(args.manifest.resolve())
    if args.json_path:
        args.json_path.parent.mkdir(parents=True, exist_ok=True)
        args.json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        "Visual manifest: "
        f"valid={report['valid']}, errors={len(report['errors'])}, "
        f"warnings={len(report['warnings'])}, stats={report['stats']}"
    )
    for message in report["errors"]:
        print(f"ERROR: {message}")
    for message in report["warnings"]:
        print(f"WARNING: {message}")

    if not report["valid"] or (args.fail_on_warning and report["warnings"]):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
