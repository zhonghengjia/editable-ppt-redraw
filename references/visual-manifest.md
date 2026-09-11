# Visual manifest and layout fingerprint

Use one manifest when required by the [profile](execution-profiles.md) or a feature
contract. It owns source inventory, canvas, modules, constraints and links to conditional component
schemas. Specialized geometry/text/curve/appearance schemas stay in their
linked references, not copied here or into a second ledger.

## Minimal schema

This base example describes one simple visible part. It is not a complete contract
for a flowchart, chart, dense text-bearing slide or hybrid assembly; add the
applicable extensions from the table below.

```json
{
  "schema_version": 1,
  "mode": "faithful",
  "execution_profile": "standard",
  "source": {"path": "reference.png", "width": 800, "height": 600},
  "canvas": {"width": 800, "height": 600},
  "targets": [{"format": "pptx", "path": "output.pptx"}],
  "styles": {"font_families": ["Arial"], "palette": {"navy": "#173D6A"}},
  "modules": [
    {"id": "object", "type": "illustration", "bbox": [100,100,200,150], "reading_order": 1}
  ],
  "source_inventory": [
    {"id": "body", "module": "object", "role": "shape",
     "bbox": [100,100,200,150], "representation": "native_primitive"}
  ],
  "connections": [],
  "uncertainties": []
}
```

## Required planning content

Record source dimensions, canvas, mode, targets and profile; modules with stable
IDs, bounding boxes, type and reading order; visible items, connections, repeated
styles, recognition signatures, raster exceptions and uncertainties. Dense work
maps every visible item to its module, geometry, role and representation.
`bbox` is `[left,top,width,height]` in **manifest canvas coordinates**; source
pixel crops/landmarks in specialist contracts use their separately declared frame.

- `source_inventory[].representation`: `native_primitive`, `native_composite`,
  `source_crop`, `evidence_raster`, or `component_raster`. The last requires hybrid.
  Legacy native-policy source/evidence rasters reference `raster_exceptions`;
  hybrid pictures use component assets instead of duplicating that authority.
- Text items carry exact `text`; scoped output selectors/counts follow
  [text-fidelity](text-fidelity.md). Connections reference known module IDs and
  preserve direction/kind/style. Optional ports, grouping, axes and crops describe
  only relevant source features.
- `icon_signatures` entries have stable `id`, owning `module`, `object_class`
  and nonempty `required_features`; optional `source_crop` records the observed
  region. Inventory all recognition-dependent symbols when the profile requires it.
- Constraints have unique `id` across both lists, known `subjects`, `type`,
  `rule` and `verification`. `semantic_constraints` allows `must_connect`,
  `must_contain`, `must_preserve_text`, `same_style_token`, `custom`;
  `negative_constraints` allows `must_not_connect`, `must_not_overlap`,
  `single_stroke_owner`, `custom`. Declare non-obvious positive/negative
  requirements before building; a valid schema does not execute those rules.
- Keep illegible labels, ambiguous directions/parts and approximations in
  `uncertainties`, with stable identity, location and detail.

## Feature schema authorities

Read the applicable authority before populating its fields; examples are syntax,
not source-derived thresholds. These extensions retain schema version 1.

| Feature / applicability | Fields and authority |
|---|---|
| Structured standard/dense visual | `diagram_grammar`: [diagram-grammar](diagram-grammar.md), covering connected roles, output geometries, authorization and directed endpoints |
| Three or more materially distinct text roles | `typography_hierarchy`: [typography-hierarchy](typography-hierarchy.md), source ratios and per-run evidence |
| Standard/dense faithful meaning-bearing curves | `curve_fidelity`: [curve-fidelity](curve-fidelity.md), per-instance source traces and final native paths |
| Dense text-bearing PPTX | `text_clearance`: [text-fidelity](text-fidelity.md), label/obstacle selections and gap |
| Faithful source-specific sensitive shapes/icons/charts; meaningful support topology | `fidelity_sensitive`, `structure_sensitive`, `regional_fidelity`: [regional-fidelity](regional-fidelity.md) |
| Source-observed attached details | `surface_detail`, `surface_relations`: [surface-relations](surface-relations.md), source landmarks and host ownership |
| Source-dependent appearance; all new hybrid work | `appearance_sensitive`, `appearance_fidelity`: [appearance-fidelity](appearance-fidelity.md), observations, generation binding and review evidence |
| Executable native parts | `native_components`: [native-component-schema](native-component-schema.md); Paint in [native-paint](native-paint.md) |
| Approved independent pictures | `editing_policy`, assets and instances: [hybrid-component-schema](hybrid-component-schema.md); workflow in [hybrid-components](hybrid-components.md) |

## Source-of-truth rule

Change the canonical manifest/builder, then regenerate affected derivatives.
Use `scripts/validate-visual-manifest.py manifest.json --fail-on-warning` during
planning; final validation is included in [quality-runner](quality-runner.md).

The validator checks fields, IDs, references and supported contracts. It does not
prove source coverage, scientific truth, arbitrary semantic/negative constraints or
visual compliance. Complete the specialized actual-file checks and separate
render review; do not create a parallel checklist of the same definitions.
