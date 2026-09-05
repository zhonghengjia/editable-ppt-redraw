# PowerPoint connector geometry for editable diagrams

Read this reference for PowerPoint flowcharts, clinical pathways, mechanisms, study designs, timelines, architecture diagrams, and other PPTX visuals in which connectors define the reading order. For draw.io, SVG, Excalidraw, Mermaid, or Graphviz, use the target-specific routing rules in [output-formats.md](output-formats.md) and still preserve the shared centerline, bus, direction, and attachment invariants below.

## Establish geometry before drawing links

1. Inventory the nodes and assign every repeated vertical or horizontal sequence to a shared centerline.
2. Align node centers before creating connectors. Do not rely on an automatic router to hide differences of a few pixels; it can turn them into visible short diagonals.
3. Define each split, convergence point, trunk, and bus once and reuse the same coordinate. Parallel branches that rejoin must terminate on one shared bus rather than on independently routed near-duplicate lines.
4. Keep connectors outside node interiors, stop them at node borders, and keep arrowhead size and line weight consistent within one semantic class.

## Choose a routing method

- Use attached PowerPoint connectors for simple links when the endpoints are aligned and the exported, reopened deck preserves the intended route. For top-level unrotated rectangular nodes, `add_rect_link` in the [native toolkit](native-toolkit.md) binds verified sites and rejects diagonal, inward or zero-length links before mutation. Do not apply rectangle site indices to arbitrary shapes.
- Use explicitly routed native horizontal and vertical line segments plus an editable arrowhead when automatic routing introduces a slant, detour, or inconsistent convergence. Name route legs `flow-<route-id>-segment-1`, `flow-<route-id>-segment-2`, and so on. Name a shared bus `flow-<bus-id>-bus`; name its branches `flow-<bus-id>-<branch-id>-segment-N`. These stable relationships let the audit verify continuity and bus attachment instead of checking only individual lines.
- Preserve intentional diagonal arrows only when the source uses them or the geometry requires them. Give them a distinctive name and document the exception in QA.

## Artifact Tool invariant for axis-aligned line shapes

For a free-positioned horizontal or vertical line, describe its bounding box directly and do not rotate it:

```js
slide.shapes.add({
  geometry: "line",
  name: "flow-assessment-to-treatment-segment-1",
  position: {
    left: Math.min(x1, x2),
    top: Math.min(y1, y2),
    width: Math.abs(x2 - x1),
    height: Math.abs(y2 - y1),
  },
  fill: "none",
  line: { style: "solid", fill: "#0A2E68", width: 2.2 },
});
```

An axis-aligned flow segment must have either `width = 0` or `height = 0`. Do not create a horizontal line and rotate it by 90 or 180 degrees to make a vertical or reversed segment. PowerPoint importers can recalculate the rotated bounding box around its center, shifting the line even when a pre-export preview looked correct.

For an orthogonal route with several bends, compose sequentially numbered axis-aligned segments whose adjacent endpoints use identical coordinates. Start numbering at 1 without gaps. Place one arrowhead at the final node border. Avoid overlapping independent arrowheads at a convergence bus, and define a shared bus once rather than drawing near-duplicate parallel buses.

## Required connector QA

1. Export the PPTX, reopen or reimport that exact file, then export fresh slide renders and layout JSON. A pre-export preview is insufficient.
2. Inspect the full slide and connector-dense crops. Check direction, attachment to node borders, shared centerlines, equal gaps, right-angle bends, dashed-versus-solid semantics, and z-order.
3. For native `p:cxnSp` connections, run `scripts/audit-pptx-connections.py <deck> --expected <connections.json> --fail-on-risk` against the actual PPTX. Use `--require-bound` only when every native connector is intended to be attached, and `--require-geometry` only for the documented straight rectangular-port profile. The expected JSON maps slide/name to source, target and arrow directions as defined in [native-toolkit.md](native-toolkit.md). Missing objects, wrong bindings, dangling IDs and wrong arrow direction block delivery. Unsupported geometry still requires reopened-layout and visual checks; it is not a successful geometry check.

4. For explicitly routed named orthogonal line segments, run:

```text
python scripts/audit-orthogonal-flow-lines.py <layout-json-or-dir> --require-matches --fail-on-risk
```

The audit must report zero diagonal, rotated, and zero-length named flow segments. Sequential `...-segment-N` routes must have no numbering gaps or disconnected adjacent endpoints. A named branch under `flow-<bus-id>-...` must terminate on its corresponding `flow-<bus-id>-bus`, and repeated buses with the same semantic ID must not overlap or drift onto near-parallel coordinates. Use `--allow-regex` only for a source-grounded intentional diagonal and record the reason in the QA notes.
5. If the actual reopened render differs from the preview, fix the geometry and rerun the applicable audit. Stored bindings do not prove arbitrary dragging and automatic rerouting work; claim interactive behavior only after testing it in the target application.
