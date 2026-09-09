# Native vector components and connector checks

Use these helpers inside an existing local python-pptx builder for reusable vector components and aligned rectangular connections. Dependencies: python-pptx, lxml (its dependency) and Pillow. Probe imports once in the selected runtime. No networking, model download, service, plugin or environment change is performed.

This native importer does not recognize raster images or render arbitrary SVG. For selected raster components, the optional local tracing adapter in [component-fidelity.md](component-fidelity.md) supplies source-derived SVG; source inspection, semantic part separation and final-render comparison remain necessary. Keep text in native text boxes, process/decision nodes in appropriate AutoShapes, and scientific values in the canonical source. Never outline text to force it through this SVG profile.

## SVG profile

`scripts/native_vectors.py` accepts UTF-8 SVG up to 2 MB and 2000 elements. Supported: path, rect (including rounded corners), circle, ellipse, line, polyline, polygon and nested groups. Relative/absolute M/L/H/V/C/S/Q/T/A/Z paths become native DrawingML curves. Arcs use cubic Bézier approximation, not mathematically exact Office arcs. A component becomes one editable group with separately editable paths. Nested source groups flatten inside that component, preserving paint order and composed coordinates, not arbitrary group hierarchy.

Styles: solid fill/stroke, currentColor, inherited supported attributes/inline style, stroke width, round/flat/square caps, round/bevel/miter joins, nonzero fill rule, fill/stroke opacity. SVG defaults remain black fill/no stroke. Transforms: translation, positive uniform scale, rotation and composition. Placement uses aspect-preserving contain and a nonzero viewBox origin is honored.

Unsupported content fails before adding shapes: text/tspan, image, use/href, nested SVG viewports, CSS selectors, gradients, markers, masks/clips, filters, group opacity, external resources, DTD/entities, even-odd fill, skew/matrix/nonuniform/mirrored scaling and unknown attributes. Normalize vector geometry in the canonical source or use the selected builder's native equivalent. Do not strip visual features, silently rasterize them or upload unsupported material as a fallback.

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

Run `python -B -m unittest discover -s tests -p test_*.py` from the skill folder. Reopen/render the actual task output and run its editability, grammar, icon and applicable connection checks. Synthetic tests establish supported tool behavior, not the fidelity of a new user image.
