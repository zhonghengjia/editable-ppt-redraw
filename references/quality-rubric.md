# Quality and delivery rubric

Use this rubric on the actual delivered artifact. Content fidelity, visual fidelity, and editability are independent requirements; none can substitute for another.

## Content fidelity

Pass when visible text, values, units, legends, panel labels, axes, scales, arrows, line semantics, and reading order agree with the source within the selected reconstruction mode.

Block delivery when a material label, value, relationship, unit, or direction is missing, invented, or contradicted. Mark illegible content explicitly instead of guessing.

## Diagram-grammar fidelity

Pass when the delivered visual preserves the declared diagram family and professional role semantics: process, cohort, decision, exclusion, milestone, outcome, terminator, compartment, causal or mechanistic edge, chart mark, axis, scale, and legend roles remain compatible with the source grammar.

Block delivery when a redraw changes representation family without explicit user authorization, or when a semantic role is replaced by an incompatible shape or mark. A visually polished flowchart-to-timeline conversion still fails when the user authorized redesign but did not authorize changing the diagram type.

For a manifest-backed structured visual, run:

```text
python scripts/audit-diagram-grammar.py visual-manifest.json reopened.layout.json --fail-on-risk
```

The audit verifies declared role objects, allowed geometries, and named semantic connections in the actual reopened output. It complements rather than replaces visual review and connector routing audits.

## Typography-hierarchy fidelity

Pass when panel labels, titles, headings, body or node labels, axes, annotations, and footnotes retain the source's relative size and weight contrast. Complete text content does not compensate for flattened or inverted hierarchy.

For a manifest that declares `typography_hierarchy`, run:

```text
python scripts/audit-typography-hierarchy.py visual-manifest.json output.pptx --fail-on-risk
```

For PowerPoint, direct OOXML inspection is authoritative for run-level font sizes; reopened layout JSON remains supported for other targets. Block delivery when a required role is missing, one object is assigned to multiple roles, a role's median resolved size falls outside its source-declared ratio range, or same-role objects drift beyond the allowed spread. The audit is numeric evidence only: render inspection remains required for glyph substitution, optical weight, wrapping, and rotated text.

## Curve-coordinate fidelity

Pass when every meaning-bearing curve remains a distinct editable series and its visible coordinate path preserves the source's peak, valley, shoulder, step, crossing, width, skew, tail, and ordering structure within the declared evidence quality. A smooth category-appropriate substitute is not faithful when its topology differs from the source.

For a manifest that declares `curve_fidelity`, run:

```text
python scripts/audit-curve-fidelity.py visual-manifest.json output.pptx --fail-on-risk
```

The audit reads native DrawingML custom geometry from the delivered PPTX, not only the builder's input points. Block delivery for a missing, duplicated, merged, or split series; an object assigned to multiple series; excessive x-aligned trace error; a wrong prominent-peak count; or a peak outside its source-declared x tolerance. Read [curve-fidelity.md](curve-fidelity.md) for source authority, raster digitization, and current audit boundaries. Rendered crop review remains required for fine oscillations, shoulders, line weight, fill, and overlap.

## Native editability

Pass when ordinary text and redrawable components use the selected format's native editable representation, major logical modules can be selected or changed separately, and the source was not used as a flattened whole-composition substitute.

Use the applicable audit:

| Editable source | Audit |
|---|---|
| PowerPoint `.pptx` | `scripts/audit-pptx-editability.py <deck> --fail-on-risk` |
| SVG, draw.io, Excalidraw, Mermaid, Graphviz, or self-contained HTML | `scripts/audit-editable-source.py <source> --fail-on-risk` |
| Dense or multi-output visual manifest | `scripts/validate-visual-manifest.py <manifest> --fail-on-warning` |

- For diagrams, charts, tables, mechanisms, interfaces, and infographics, an unapproved canvas-sized picture is blocking.
- For photographs, microscopy, radiology, maps, and other evidence images, a large raster base may be valid when overlays remain editable and the delivery report discloses it.
- Imported SVG inside PowerPoint counts as a picture until its components are confirmed editable in PowerPoint.
- A PNG, JPEG, PDF, or screenshot is a rendered derivative, not the canonical editable source.
- For a dense PowerPoint task, add `--manifest <manifest.json>` so every text item declared in `source_inventory` is checked against the actual PPTX package. Add repeated `--require-text` values for exact labels that are not in the manifest.
- Zero-byte media, broken internal image or package relationships, non-hyperlink external resources, unresolved placeholders, suspicious mojibake, missing required text, out-of-bounds top-level objects, and same-bounds duplicate border candidates are blocking risks.
- A CJK run without an explicit East Asian typeface is a warning because a theme font may still render correctly; the reopened PowerPoint render remains the authority for glyph fit.

## Visual fidelity

For faithful and semantic reconstruction, render the actual output and run `scripts/compare-reference-render.py` against the matching source when both can be represented as images.

- Inspect overlay and difference images at full-composition and detail level.
- Prioritize foreground and edge differences over empty-background similarity.
- Use similarity metrics as diagnostics, not universal pass thresholds.
- A high similarity score is invalid evidence when the editability audit shows a flattened artifact.
- In redesign mode, verify retained content, relationships, and hierarchy; pixel similarity is not the goal.

For icons, pictograms, compact devices, and simplified scientific objects, compare source and reopened-output crops at delivered size and magnified detail. Generate repeatable contact sheets with:

```text
python scripts/build-comparison-contact-sheet.py reference.png rendered.png regions.json output.png
```

Pass only when the defining silhouette, topology, terminals, negative spaces, component relationships, orientation, and stroke continuity agree with the selected reconstruction mode. A broadly related symbol is not an acceptable substitute in faithful reconstruction.

For transparent or extracted raster assets, run:

```text
python scripts/audit-raster-asset-integrity.py <asset-or-directory> --fail-on-risk --contact-sheet asset-audit.png
```

Treat visible alpha pixels entering the edge-risk band, implausibly tight visible bounds, undersized assets, and unexpectedly low subject occupancy as asset risks. An opaque rectangle cannot be cleared for alpha-edge clipping by this audit; inspect the source crop and rendered placement manually.

## Layout, routing, and rendering

Block delivery for unintended overlap, clipping, overflow, broken connectors, incorrect z-order, unresolved placeholders, objects outside the canvas, or compact symbols whose defining parts collapse, disconnect, merge, or become ambiguous at delivered size.

- Check unexpected text wrapping, especially labels and headings intended to remain on one line.
- Compare text-role proportions, not only individual sizes. Small source notes must remain subordinate; headings must not collapse to body scale; role tokens should be consistent across panels.
- Enforce one stroke owner per visible container boundary. Header bands, masks, overlays, and inner backgrounds must not create a second same-bounds outline.
- Center inner content against the measured interior box after subtracting borders, padding, title bands, and reserved icon regions; do not center it against the outer panel by eye.
- Verify every manifest semantic constraint and negative constraint, including prohibited connections, overlaps, substitutions, curve-template shortcuts, and duplicate-border states.
- Verify the `diagram_grammar` contract, including its visual type, authorization state, node-role geometries, edge-role matches, and routing convention.
- Inspect every page, slide, panel, or canvas individually; a montage alone is insufficient.
- For PowerPoint diagrams expected to use orthogonal routing, reopen the PPTX, export layout JSON, and run `scripts/audit-orthogonal-flow-lines.py <layout-json-or-dir> --require-matches --fail-on-risk`.
- For draw.io, confirm unique cell IDs, native vertices and edges, and `mxGeometry relative="1"` on edges.
- For SVG and HTML, check the viewBox or viewport, text clipping, external assets, and overflow in a local renderer.
- For Excalidraw, verify scene parsing, bound labels, arrow relationships, and image-element exceptions.
- For Mermaid and Graphviz, verify the source parses and the rendered derivative preserves node and edge semantics.

## Multi-output consistency

When the user requests more than one format:

1. Name the canonical source or visual manifest.
2. Verify labels, values, modules, connections, and raster exceptions against that source.
3. Render and audit each format independently.
4. Disclose format-specific simplifications instead of claiming identical editability or pixel parity.

## Standard delivery summary

Report:

- reconstruction mode and target format;
- output path and page, slide, or canvas count;
- canonical editable source and rendered derivatives;
- principal editable components;
- remaining raster components and why they remain raster;
- visual approximations or uncertain text;
- editability or source-audit result;
- parsing, render, overflow, connector, and visual-comparison checks actually completed.

Keep detailed JSON, overlays, difference images, source notes, and temporary renders out of the final deliverables unless the user asks for them.
