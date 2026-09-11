# Native vector components and connector checks

Use these helpers inside the selected local builder for reusable vector components, executable part trees and aligned rectangular connections. The python-pptx adapter uses python-pptx, lxml and Pillow; source-patch sampling also uses NumPy. `component_xml` exposes the same tree serializer for a target-owning native XML adapter, not a second converter. Its caller supplies free shape IDs and occupied names, and must perform the applicable manifest/source preflight. Probe imports once in the selected runtime. No networking, model download, service, plugin or environment change is performed.

This native importer does not recognize raster images or render arbitrary SVG. For selected raster components, the optional local tracing adapter in [component-fidelity.md](component-fidelity.md) supplies source-derived SVG; source inspection, semantic part separation and final-render comparison remain necessary. Keep text in native text boxes, process/decision nodes in appropriate AutoShapes, and scientific values in the canonical source. Never outline text to force it through this SVG profile.

## Select the operation

- Nested native parts, continuous fills, source alpha effects or shared domains: read [native-paint](native-paint.md) and [native-component-schema](native-component-schema.md).
- Supported solid SVG components, PDF source-state inspection or rectangular connectors: use the relevant interfaces below; they do not require the advanced paint schema.

## SVG input profile

`scripts/native_vectors.py` owns the unchanged limits in `MAX_SVG_BYTES` (2,000,000), `MAX_SVG_ELEMENTS` (2000 including the root/groups), and `MAX_PATH_CHARS` (100,000 per primitive). Supported: path, rect (including rounded corners), circle, ellipse, line, polyline, polygon and nested groups. Relative/absolute M/L/H/V/C/S/Q/T/A/Z paths become native DrawingML curves. Arcs use cubic Bézier approximation, not mathematically exact Office arcs. A component becomes one editable group with separately editable paths. Nested source groups flatten inside that component, preserving paint order and composed coordinates, not arbitrary group hierarchy. Import limits protect this serializer; they are not practical-editability criteria. The [component fidelity](component-fidelity.md) source-part budget checks native commands even when many contours are packed into fewer shapes.

Styles: solid fill/stroke, currentColor, inherited supported attributes/inline style, stroke width, round/flat/square caps, round/bevel/miter joins, nonzero fill rule, fill/stroke opacity. SVG defaults remain black fill/no stroke. Transforms: translation, positive uniform scale, rotation and composition. Placement uses aspect-preserving contain and a nonzero viewBox origin is honored.

Unsupported SVG input fails before adding shapes: text/tspan, image, use/href, nested SVG viewports, CSS selectors, gradient definitions/references, markers, masks/clips, filters, group opacity, external resources, DTD/entities, even-odd fill, skew/matrix/nonuniform/mirrored scaling and unknown attributes. The [native Paint route](native-paint.md) does not widen the SVG parser or silently translate unsupported paint servers. Represent source-supported shading explicitly in the canonical component tree, or use another qualified native equivalent. Do not strip visual features, silently rasterize them or upload unsupported material as a fallback.

Both native routes use the existing path serializer's analytic cubic-extrema
bounds, excluding stroke, while retaining original cubic controls. Shape extents
are bounded below by one EMU, not one pixel. Bounds drive paint and group geometry;
this is not automatic arbitrary radial-gradient equivalence or a raster trace.

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

## PDF source state

For an already available PDF source, `pdf_paint_scene.py` consumes installed
PyMuPDF's public `get_drawings(extended=True)` and `get_bboxlog()` APIs. It does
not install a renderer or add PDF contents to PowerPoint:

```text
python scripts/pdf_paint_scene.py source.pdf source-state.json --page 4 --region 89 112 139 161
```

Page is one-based; the optional region is `[x0,y0,x1,y1]` in unrotated page points.
Coordinates are illustrative. Output refuses overwrite and includes source hash,
extractor version, path commands, tight curve bounds, original extraction rects,
scope IDs and non-path/unrepresented display operations. Process the full level
stack before region selection so off-region ancestor scopes are not lost. A new
scope at the same/lower level ends the previous scope. Group opacity remains on
its group; it is not multiplied into overlapping child alphas.

This is construction evidence, not a quality PASS or a complete PDF paint IR.
Selection is bounding-box intersection, not actual clipping/visibility. Shade
bounds may include a region without visibly contributing there. Soft-mask recipes
are not fully exposed, and `get_images()` can omit inline image operations.
The report therefore retains unresolved operations and `NOT_PERFORMED` conversion
status. Interpret them before rebuilding the selected component; never erase them
to turn a path-only extraction into a complete reconstruction. Complex documents
are capped at 100,000 drawing/display operations and 128 scope levels.

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
