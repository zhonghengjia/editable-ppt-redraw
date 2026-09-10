# Native vector components and connector checks

Use these helpers inside an existing local python-pptx builder for reusable vector components, executable part trees and aligned rectangular connections. Dependencies: python-pptx, lxml (its dependency) and Pillow; source-patch sampling also uses NumPy. Probe imports once in the selected runtime. No networking, model download, service, plugin or environment change is performed.

This native importer does not recognize raster images or render arbitrary SVG. For selected raster components, the optional local tracing adapter in [component-fidelity.md](component-fidelity.md) supplies source-derived SVG; source inspection, semantic part separation and final-render comparison remain necessary. Keep text in native text boxes, process/decision nodes in appropriate AutoShapes, and scientific values in the canonical source. Never outline text to force it through this SVG profile.

## Executable native parts and Paint

Use `native_components.add_manifest_component(slide, manifest, component_id,
x, y, width, height, base_dir=manifest_directory)` to construct an inventory-backed
tree in the existing builder. Placement uses inches and aspect-preserving contain.
The manifest schema is defined in [visual-manifest.md](visual-manifest.md).
For isolated geometry fixtures the lower-level `add_native_component` accepts the
same component value; production source-sampled work uses the manifest entrypoint,
which rechecks sampled colors and all declared regional/appearance contracts,
including source hash/size, before emitting anything. Missing sensitive-item
contracts fail before slide mutation. The lower-level geometry fixture helper
does not perform this manifest preflight and must not bypass it in source work.

Groups, local translation and positive uniform scale are composed through the tree.
Children are emitted in back-to-front list order; a group is a contiguous paint
unit. Interleaved independent objects need source-supported visible-part grouping,
not a fabricated total depth order. A parent transform moves its nested parts;
this does not clip them or establish their scientific attachment. Source visibility,
contours and independent landmarks remain authoring inputs. For touching visible
pieces, construct the joint source partition under [component fidelity](component-fidelity.md#marked-source-assemblies)
before passing its ordinary component trees here; independent closed-path fits
are not a coverage model. Shared native coordinates still require an actual render
check for antialias seams and a source-grounded ownership review.

Each leaf uses the existing SVG path parser and `native_vectors.path_shape_xml`.
Solid SVG imports and these trees share the same path/paint emitter, not two
competing OOXML implementations. The entire component is prepared before the slide
changes. Names are stable hierarchical paths; the returned `element_map` includes
actual shape IDs, immediate parent group IDs and initial bounds. Reopen to resolve
final geometry. The tree has no text/image nodes, no automatic segmentation,
arbitrary clipping, group opacity, rotations or nonuniform/mirrored transforms.
The existing SVG path/element limits remain unchanged; tree depth is at most 16.

`native_paint.py` owns the supported Paint values:

- `null` or `{"kind":"none"}`: no fill.
- `"#AABBCC"` or `{"kind":"solid","color":"AABBCC","alpha":1}`.
- `{"kind":"linear","angle":90,"stops":[...]}`: Office linear gradient,
  clockwise degrees from a left-to-right direction; no automatic lighting inference.
- `{"kind":"path","focus":[0.3,0.25],"stops":[...]}`: Office circular path
  gradient centered at normalized bounding-box coordinates `[u,v]`. This is a
  bounded Office representation, not arbitrary SVG radial/mesh equivalence.
- Each stop is `{"position":0,"color":"AABBCC","alpha":1}`. Use 2..32 stops,
  strictly increasing at Office's 1/100000 precision with endpoints 0 and 1.
  Colors are six-digit sRGB; alpha is 0..1. Paths use nonzero winding; compound
  holes remain real holes. Gradient strokes are not supported.

Paint is independent of path geometry. Changing a stop must not refit a contour,
move a nucleus or reorder layers. Source sampling is defined only in
[appearance-fidelity.md](appearance-fidelity.md); its returned Paint carries a
`source_samples` provenance record and is assigned directly to the leaf fill.
Do not replace continuous shading with hundreds of flat regions unless that
approximation and editing scope are explicitly selected.

PowerPoint editing qualification uses actual saved/reopened files. In the tested
Office 16.0 COM interface, `GroupItems` enumerates leaves of nested groups even
for Office-authored groups. To edit an inner object as a unit, ungroup the outer
assembly once, then select/move the inner group; edit its native gradient stops
without ungrouping its individual paths. This was tested through application
automation, not a claim that every UI/version exposes identical selection behavior.
Keep grouping shallow enough for the requested editing task.

## SVG input profile

`scripts/native_vectors.py` owns the unchanged limits in `MAX_SVG_BYTES` (2,000,000), `MAX_SVG_ELEMENTS` (2000 including the root/groups), and `MAX_PATH_CHARS` (100,000 per primitive). Supported: path, rect (including rounded corners), circle, ellipse, line, polyline, polygon and nested groups. Relative/absolute M/L/H/V/C/S/Q/T/A/Z paths become native DrawingML curves. Arcs use cubic Bézier approximation, not mathematically exact Office arcs. A component becomes one editable group with separately editable paths. Nested source groups flatten inside that component, preserving paint order and composed coordinates, not arbitrary group hierarchy. Import limits protect this serializer; they are not practical-editability criteria. The [component fidelity](component-fidelity.md) source-part budget checks native commands even when many contours are packed into fewer shapes.

Styles: solid fill/stroke, currentColor, inherited supported attributes/inline style, stroke width, round/flat/square caps, round/bevel/miter joins, nonzero fill rule, fill/stroke opacity. SVG defaults remain black fill/no stroke. Transforms: translation, positive uniform scale, rotation and composition. Placement uses aspect-preserving contain and a nonzero viewBox origin is honored.

Unsupported SVG input fails before adding shapes: text/tspan, image, use/href, nested SVG viewports, CSS selectors, gradient definitions/references, markers, masks/clips, filters, group opacity, external resources, DTD/entities, even-odd fill, skew/matrix/nonuniform/mirrored scaling and unknown attributes. The native Paint route above does not widen the SVG parser or silently translate unsupported paint servers. Represent source-supported shading explicitly in the canonical component tree, or use another qualified native equivalent. Do not strip visual features, silently rasterize them or upload unsupported material as a fallback.

```python
import sys
sys.path.insert(0, str(skill_directory / 'scripts'))
from native_vectors import add_svg_component, add_rect_link

result = add_svg_component(slide, project_directory / 'instrument.svg',
                           x=1.2, y=2.0, width=.6, height=.6,
                           name='instrument-assessment', color='#173D6A')
# Record result['source_sha256'] and result['element_map']; result['group'] is native.
```

`element_map` records each accepted source primitive ID, actual output shape ID/name and initial bounds in inches. `group_id` and `slide_part` scope the mapping. Reopen the saved PPTX and resolve those IDs; after further transformations remeasure the actual bounds instead of treating initial placement as final evidence. The existing duplicate-source-ID rejection remains unchanged.

Coordinates are inches. Select a source/bundled asset only when its recognition signature fits. `assets/lucide/inventory.json` is the asset provenance authority; this starter pack is not an exhaustive medical library.

Standalone component smoke test:

```text
python scripts/native_vectors.py instrument.svg new-component.pptx
python scripts/native_vectors.py instrument.svg new-copy.pptx --template existing.pptx
```

The second command appends one slide to a new copy, requiring a blank layout (date/footer/page-number placeholders are permitted). It refuses existing output paths and preserves the original. This is not a guarantee that every animation, add-in, embedded object or proprietary template extension survives a python-pptx round trip. Verify required objects and actual rendered slides. Ordinary `.pptx` only; use a target-owning route for macros or unsupported features.

## Rectangular connections

```python
link = add_rect_link(slide, source_node, target_node,
                     source_port='right', target_port='left',
                     name='flow-assessment-treatment')
```

Eligible nodes: top-level, unrotated rectangles/rounded rectangles on the same slide, with aligned outward-facing ports. A straight native connector stores source/target IDs and a triangle at the target. Multi-bend links, buses, decisions and arbitrary-shape ports use [connector-geometry.md](connector-geometry.md), not guessed rectangle indices.

Expected connections are a JSON list. Names are stable and unique within each slide; slide numbers are one-based. Include source/target and both arrow fields for direction-sensitive edges:

```json
[
  {"slide": 1, "name": "flow-assessment-treatment", "source": "assessment",
   "target": "treatment", "start_arrow": "none", "end_arrow": "triangle"}
]
```

```text
python scripts/audit-pptx-connections.py new.pptx --expected connections.json --require-bound --require-geometry --fail-on-risk
```

The audit reads actual slide order, IDs, bindings, arrow ends and port coordinates. It reports missing/unbound/dangling or semantically wrong connections, duplicate connector names, zero length, diagonals and off-port endpoints within its profile. For grouped, rotated, freeform or elbow routes, `geometry_complete` is false. Topology can still be inspected, but geometry requires the existing layout audit and render review. It does not model obstacle avoidance or certify node-drag rerouting.

## Validation

Approved independent picture components use the selected target-owning backend
and [hybrid-components.md](hybrid-components.md), not this SVG importer.
`component_assets.verify_replacement` checks regenerated before/after PPTX identity,
geometry and unrelated object/media stability. It is read-only and does not certify
interactive drag rerouting. Asset/instance fields have one authority in
[visual-manifest.md](visual-manifest.md).

Run `python -B -m unittest discover -s tests -p test_*.py` from the skill folder. Reopen/render the actual task output and run its editability, grammar, icon and applicable connection checks. Synthetic tests establish supported tool behavior, not the fidelity of a new user image.
