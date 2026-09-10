# Visual manifest and layout fingerprint

Use a visual manifest for dense, multi-panel, batch, multi-output or approved hybrid reconstruction. It is the compact source of truth for semantics, layout, uncertainty, assets and output routing. A trivial native icon does not need one; a hybrid component does, to bind its authorization, bytes and output instance.

## Why it exists

- Prevent different output formats from drifting in labels, geometry, or connector logic.
- Make uncertain text, raster exceptions, and source-derived approximations explicit before drawing.
- Enable module-first construction and local QA before final integration.
- Keep format-specific builders focused on rendering rather than rediscovering the source.

## Minimal schema

For faithful source-specific shapes, `fidelity_sensitive`/`regional_fidelity` and `surface_detail`/`surface_relations` are defined solely in [component-fidelity.md](component-fidelity.md). These contracts use decoded source pixels, not manifest canvas coordinates. Declare observed ownership and source landmarks before building; regional pixel checks and native relationship checks have separate acceptance scopes.

Save JSON with this structure:

```json
{
  "schema_version": 1,
  "mode": "faithful",
  "execution_profile": "dense",
  "source": {
    "path": "reference.png",
    "width": 1536,
    "height": 1024
  },
  "canvas": {
    "width": 1536,
    "height": 1024
  },
  "targets": [
    {"format": "pptx", "path": "output_v2.pptx"},
    {"format": "svg", "path": "output_v2.svg"}
  ],
  "styles": {
    "font_families": ["Microsoft YaHei"],
    "palette": {"navy": "#0A2E68", "red": "#D81818"}
  },
  "typography_hierarchy": {
    "basis": "source_observed",
    "measurement": "resolved_font_size",
    "baseline_role": "node_label",
    "default_tolerance": 0.12,
    "default_max_intra_role_spread": 0.10,
    "roles": {
      "section_title": {
        "target_ratio": 1.35,
        "output_name_regex": "^section-.*-title$"
      },
      "node_label": {
        "target_ratio": 1.0,
        "output_name_regex": "^node-.*-label$"
      },
      "footnote": {
        "target_ratio": 0.58,
        "tolerance": 0.15,
        "output_name_regex": "^footnote-"
      }
    }
  },
  "modules": [
    {
      "id": "assessment",
      "type": "flow-module",
      "bbox": [558, 149, 272, 54],
      "reading_order": 3,
      "source_notes": "Central assessment node"
    },
    {
      "id": "stable",
      "type": "flow-module",
      "bbox": [313, 204, 141, 45],
      "reading_order": 4,
      "source_notes": "Stable branch"
    },
    {
      "id": "unstable",
      "type": "flow-module",
      "bbox": [900, 204, 154, 45],
      "reading_order": 5,
      "source_notes": "Unstable branch"
    }
  ],
  "source_inventory": [
    {
      "id": "assessment-label",
      "module": "assessment",
      "role": "text",
      "bbox": [582, 163, 224, 28],
      "text": "生命体征/血流动力学评估",
      "representation": "native_primitive"
    },
    {
      "id": "specialist-tool",
      "module": "assessment",
      "role": "icon",
      "bbox": [604, 163, 44, 44],
      "representation": "native_composite"
    },
    {
      "id": "stable-label",
      "module": "stable",
      "role": "text",
      "bbox": [345, 214, 78, 24],
      "text": "稳定",
      "representation": "native_primitive"
    },
    {
      "id": "unstable-label",
      "module": "unstable",
      "role": "text",
      "bbox": [932, 214, 90, 24],
      "text": "不稳定",
      "representation": "native_primitive"
    }
  ],
  "connections": [
    {
      "id": "assessment-to-stable",
      "source": "assessment",
      "target": "stable",
      "kind": "directed",
      "line_style": "solid"
    }
  ],
  "diagram_grammar": {
    "visual_type": "clinical_flowchart",
    "preserve_visual_type": true,
    "allow_representation_change": false,
    "routing": "orthogonal",
    "node_roles": {
      "assessment": {
        "role": "assessment_process",
        "allowed_geometries": ["rect", "roundRect"],
        "output_names": ["assessment-box"]
      },
      "stable": {
        "role": "branch_state",
        "allowed_geometries": ["rect", "roundRect"],
        "output_names": ["stable-box"]
      }
    },
    "edge_roles": {
      "assessment-to-stable": {
        "role": "stable_branch",
        "output_name_regex": "^flow-assessment-to-stable-",
        "endpoint_binding": {
          "source_output_name": "assessment-box",
          "target_output_name": "stable-box"
        }
      }
    }
  },
  "icon_signatures": [
    {
      "id": "specialist-tool",
      "module": "assessment",
      "object_class": "diagnostic instrument",
      "required_features": ["distinctive outer contour", "open terminal", "circular end component"],
      "source_crop": [604, 163, 44, 44]
    }
  ],
  "raster_exceptions": [
    {
      "id": "ct-image",
      "bbox": [100, 100, 240, 180],
      "reason": "Radiology evidence must not be redrawn"
    }
  ],
  "semantic_constraints": [
    {
      "id": "unstable-route-required",
      "type": "must_connect",
      "subjects": ["assessment", "unstable"],
      "rule": "The unstable branch must lead from assessment to emergency resuscitation.",
      "verification": "Inspect the named connection and reopened render."
    }
  ],
  "negative_constraints": [
    {
      "id": "no-duplicate-panel-border",
      "type": "single_stroke_owner",
      "subjects": ["assessment"],
      "rule": "No same-bounds overlay may duplicate the panel border.",
      "verification": "PPTX duplicate-border audit is empty for this panel."
    }
  ],
  "uncertainties": [
    {"id": "u01", "location": "panel-b subtitle", "detail": "Last character illegible"}
  ]
}
```

`bbox` uses `[left, top, width, height]` in the manifest canvas coordinate system. Source inventory text selectors/counts are defined in [text-fidelity.md](text-fidelity.md); directed endpoint evidence in [diagram-grammar.md](diagram-grammar.md); run exceptions in [typography-hierarchy.md](typography-hierarchy.md); actual curve identity and output coordinate frames in [curve-fidelity.md](curve-fidelity.md). These optional fields extend manifest schema 1. Do not duplicate their definitions in parallel configuration files.

The optional `text_clearance` contract is defined solely in [text-fidelity.md](text-fidelity.md). Dense text-bearing PPTX needs it for complete automated clearance evidence; keep label/obstacle selections and gap in that one contract, not duplicated rule lists.

## Required planning content

- Source dimensions and intended output canvas.
- Reconstruction mode and requested targets.
- Selected execution profile when it affects planning or QA.
- Major modules with stable IDs, bounding boxes, types, and reading order.
- For a `dense` profile, every visible item mapped in `source_inventory` to its owning module, source geometry, role, exact text when applicable, and representation strategy.
- Directed or undirected connections referencing module IDs.
- For a structured `standard` or `dense` task, a `diagram_grammar` contract that records the source visual type, representation-change authorization, routing family, node-role geometry, output object names, and semantic edge-name patterns.
- Repeated styles and reusable icon or component families.
- For visuals with three or more materially distinct text roles, a source-grounded `typography_hierarchy` with one baseline role, mutually exclusive output-name regexes, target ratios, and tolerances.
- For a `standard` or `dense` faithful visual containing meaning-bearing curves, a `curve_fidelity` contract with one source-relative coordinate trace per curve instance, mutually exclusive output-name regexes, and source-supported distance and peak constraints.
- Recognition signatures for compact symbols when the selected profile requires an inventory.
- Raster exceptions with a source-grounded reason.
- Uncertain text, symbols, directions, and values.
- Semantic constraints that must remain true and negative constraints that explicitly prohibit misleading topology, overlap, duplicate borders, raster shortcuts, or substitutions.

`source_inventory[].representation` is one of `native_primitive`, `native_composite`, `source_crop`, `evidence_raster`, or `component_raster`. The last selects the hybrid contract below. Legacy native-policy `source_crop`/`evidence_raster` items still reference `raster_exceptions`; hybrid manifests migrate pictures to component assets instead of duplicating that authority. Constraints use stable subject IDs and state both the rule and its verification. Positive constraints use `must_connect`, `must_contain`, `must_preserve_text`, `same_style_token`, or `custom`; negative constraints use `must_not_connect`, `must_not_overlap`, `single_stroke_owner`, or `custom`. IDs are unique across both lists. Optional fields can record grouping, ports, axes and source crops when relevant. Icon signatures identify an owning module, object class and nonempty required-feature list. These optional contracts extend schema version 1.

## Executable native component contract (single authority)

Optional `native_components` extends schema 1 with construction inputs, not another
source inventory or an automatic reconstruction result. Each of 1..100 entries has
exactly `id`, `output_name`, `viewbox: [x,y,width,height]`, and `parts`. `id` uniquely
references a `native_composite` inventory item; its optional inventory output_name
must agree. The viewbox describes local geometry, not an alternative source image.

Each part has unique component-local `id` (no slash), a descriptive `role`, and a
nonempty source/approval-grounded `observation`. Groups have `children`; leaves have
SVG path `d` and `fill`. Optional `translate: [x,y]` and positive uniform `scale`
compose in the parent's local frame. A group cannot also contain path/fill fields.
Leaves optionally declare solid `stroke` and local `stroke_width` (default 0).
List order is back-to-front. Output names are `component/ancestor/part`; the builder
rejects collisions. Node/transform/paint fields are strict, so an unsupported
rotation, clipping or opacity field cannot silently disappear.

Paint values and numeric bounds have one authority in [native-toolkit.md](native-toolkit.md).
Source sampling/provenance is defined in [appearance-fidelity.md](appearance-fidelity.md).
Do not copy those schemas into separate manifests or store a second color truth.
This compact synthetic example demonstrates syntax, not a biological template:

```json
{
  "native_components": [{
    "id": "source-object-01", "output_name": "object-01", "viewbox": [0,0,100,100],
    "parts": [{
      "id": "assembly", "role": "object", "observation": "Synthetic API example",
      "children": [{
        "id": "body", "role": "surface", "observation": "Synthetic curved boundary",
        "d": "M10 20 C35 0 85 10 90 50 C85 90 20 95 10 20 Z",
        "fill": {"kind":"path", "focus":[0.3,0.25], "stops":[
          {"position":0,"color":"F4DFDD"}, {"position":1,"color":"A86173"}
        ]}
      }, {
        "id":"detail", "role":"inner part", "observation":"Synthetic internal detail",
        "d":"M40 40 L60 40 L60 60 L40 60 Z", "fill":"#704F69"
      }]
    }]
  }]
}
```

Use `native_components.add_manifest_component` from the existing builder with its
ordinary placement inputs. It emits real paths/groups, consumes source-sampled
Paint and returns the actual output mapping. Separate text/relationships remain
ordinary native objects. New fields do not change existing manifests without this
extension. Structural validation does not prove observations correct, parts attached
or colors faithful; the established source/final-render checks retain their scope.

## Hybrid component contract (single authority)

Set `editing_policy: "hybrid"` and nonempty `hybrid_authorization` quoting the user's
accepted editing scope. Omission means the existing `native` policy, including its
legacy evidence exceptions. Keep faithful/semantic/redesign unchanged. Hybrid needs
`component_assets`, `component_instances`, a complete `source_inventory`, and at
least standard profile.

Each asset has:

- `asset_id`: unique reusable identity; `path`: manifest-relative local file;
  `sha256`: lowercase hash of the exact approved bytes.
- `source_kind`: `local`, `licensed`, `source_crop`, or `generated`; `origin` and
  `authorization`: actual provenance and permitted use, not invented credentials.
- `editing_unit`: independent semantic object. `extent: "object"` means
  move/scale/replace only. `content_class`: `illustration` or `evidence`.
  `contains_native_required: false` must follow inspection that the asset does not
  flatten text, quantitative marks, legends or cross-component relationships.
  A whole panel/reference/arbitrary tile is not an independent component.
- `requires_alpha`: explicit boolean; `min_visible_pixels`: minimum visible width
  AND height; `min_dpi`: minimum resolution at final physical placement. Select
  task-appropriate limits before construction, not after a failed check.
- `invariants`: nonempty source/approval-grounded descriptions of required
  projection, gaps, terminals, branch counts and uncertainty.
- `comparison`: `source_exact` for original/local/licensed assets; generated assets
  use `approved_surrogate` and cannot claim original pixels or experimental data.
- Licensed assets also require `license` and `attribution`. Source crops require
  original `source_sha256` and source-pixel `source_bbox: [x,y,w,h]`.

Generated assets additionally have a `generation` record:

- `provider: "builtin_imagegen"`, `authorization`, `subject`, `style`, actual
  `prompt`, and nonempty `invariants`.
- `attempt`: 1 or 2 within the existing construction/correction budget; attempt 2
  needs `correction_reason`. Only `status: "succeeded"` enters the asset list.
- `references`: explicit list, `[]` for text-only generation. Every transmitted
  image records `path`, `sha256`, `role` (`structure`, `style`, `edit_target`),
  `transmitted_scope` and its own upload `authorization`. A transmitted crop's hash
  identifies the actual crop, not the untransmitted whole source.
- Returned model version, seed or request ID stays null or absent when unavailable.
  Never fabricate reproducibility parameters.

Each instance has:

- unique `instance_id`, known `asset_id`, one-based `slide`, exact unique
  `output_name`; one p:pic per instance, reusable assets can have many instances.
- `bbox_inches: [left,top,width,height]`: planned slide-space axis-aligned bounds
  after rotation/group transforms; `rotation`: effective clockwise degrees.
- `crop: [left,top,right,bottom]`: explicit fractions of the source image, usually
  `[0,0,0,0]`; each nonnegative and opposite sums below 1. Preserve visible content
  and aspect. This verifier does not certify crops that remove alpha-visible pixels.
- `placement_tolerance_inches`: 0..0.05, chosen before authoring; not a scientific
  fidelity or font tolerance.
- `anchors`: explicit list including `[]`. Each has unique `id`, `uv: [u,v]`
  normalized to the full original asset canvas, and independently planned
  `expected_inches: [x,y]` in slide space. Actual crop/group transforms are applied.
  Static agreement does not prove interactive connector following.

A raster inventory item uses `representation: "component_raster"` and a known
`component_instance`; each instance maps to exactly one inventory item. Text,
chart, table and connector roles, plus `native_required: true`, cannot use it.
Hybrid native items require exact `output_name` and optional one-based
`output_slide`/`required_count`. Coverage is checked against the actual package.

`scripts/component_assets.py` implements this extension for the existing validator,
PPTX audit and quality runner. Schema validation does not read assets; package audit
compares actual local/embedded hashes, media integrity, geometry and coverage.
Neither is a semantic segmentation engine or authenticated provenance. False
origin/role assertions cannot be detected reliably from hashes; source/render
review remains mandatory.

`diagram_grammar.visual_type` names the source representation family. `preserve_visual_type` and `allow_representation_change` are booleans; when a representation change is allowed, `authorization` must contain the user's explicit instruction. `routing` is one of `orthogonal`, `direct`, `curved`, `mixed`, or `source_defined`. Each `node_roles` key references a module or source-inventory ID and declares a non-empty semantic `role`, one or more `allowed_geometries`, and the exact `output_names` that must carry that role in reopened layout inspection. Every connected module endpoint must have a node-role entry. Each `edge_roles` key references a connection ID and declares a semantic `role` plus an `output_name_regex` that must match one or more editable line objects. Every connection must have an edge-role entry. Names establish selection only, not endpoint truth; follow the endpoint-binding contract in [diagram-grammar.md](diagram-grammar.md).

`typography_hierarchy` records relative font size instead of isolated absolute sizes. `basis` is `source_observed`, `source_estimated`, `user_specified`, or `redesign_system`; `measurement` is currently `resolved_font_size`. `baseline_role` must exist in `roles` and have `target_ratio: 1.0`. Each role declares a positive ratio and a regex matching the canonical output object names. Optional `tolerance`, `required`, and `max_intra_role_spread` override the hierarchy defaults. See [typography-hierarchy.md](typography-hierarchy.md) before assigning ratios.

`curve_fidelity` records visible curve geometry as coordinates rather than as a visual category. `basis` is `source_vector`, `raw_data`, `source_observed`, `source_estimated`, or `user_specified`; `measurement` is currently `x_aligned_profile`. Each series references one chart item in `source_inventory`, a task-relative JSON trace, a supported curve kind, and an output-name regex that identifies the native path in the delivered file. Defaults and series-level overrides bound x-aligned normalized MAE, peak prominence, minimum peak spacing, and peak-position tolerance. `expected_peak_count` and `expected_peak_positions` must agree when both are present. See [curve-fidelity.md](curve-fidelity.md) before extracting, fitting, simplifying, or rebuilding a curve.

Example for a chart inventory item named `ridge-01-source`:

```json
{
  "curve_fidelity": {
    "basis": "source_observed",
    "measurement": "x_aligned_profile",
    "default_max_x_aligned_mae": 0.08,
    "default_peak_x_tolerance": 0.06,
    "default_peak_prominence": 0.08,
    "default_min_peak_distance": 0.06,
    "series": [
      {
        "id": "ridge-01",
        "source_inventory_id": "ridge-01-source",
        "kind": "filled_ridge",
        "source_trace": "traces/ridge-01.source.json",
        "output_name_regex": "^ridge-01-fill$",
        "expected_output_count": 1,
        "expected_peak_count": 2,
        "expected_peak_positions": [0.44, 0.67],
        "required": true
      }
    ]
  }
}
```

## Module-first workflow

Appearance-sensitive inventory uses `appearance_sensitive: true`. The shared
`appearance_fidelity` extension, generation binding and render-review evidence
are defined only in [appearance-fidelity.md](appearance-fidelity.md). Use it for
all new hybrid work and any source-dependent tone/contour/occlusion requirement;
do not duplicate these facts in an asset-specific correction ledger.

1. Inventory modules and assign stable IDs.
2. Inventory every visible item and assign its representation before authoring; a visible region with no inventory item is an unresolved planning gap.
3. For a structured visual, declare its diagram grammar before changing layout or styling.
4. Freeze applicable appearance requirements before representation selection, then reconstruct each module within its declared bounding box.
5. Export local crops or previews and compare them with the matching source region.
6. Mark local modules acceptable before adding cross-module connections.
7. Integrate shared legends, global titles, buses, and cross-panel connectors.
8. Verify diagram grammar, typography hierarchy, curve fidelity, semantic constraints, and negative constraints, then revalidate the manifest and every requested output after changes.

## Source-of-truth rule

During authoring, change the manifest or the canonical format source, then regenerate derivatives. Do not fix only one exported file when the same fact or geometry is represented in several formats.

Run:

```text
python scripts/validate-visual-manifest.py manifest.json --fail-on-warning
```

The validator checks structure, supported modes, optional execution profile, targets, positive canvas dimensions, unique IDs, valid bounding boxes, source-inventory coverage requirements, representation strategies, connection references, diagram-grammar completeness and authorization, typography-role contract validity, curve-contract validity, icon-signature completeness, raster references, and constraint subjects. It does not execute arbitrary semantic/negative constraints or prove visual fidelity, semantic truth, icon recognizability, grammar, typography or curve compliance. Run [the applicable-check runner](quality-runner.md) on the actual artifact, then complete each declared manual/render constraint.
