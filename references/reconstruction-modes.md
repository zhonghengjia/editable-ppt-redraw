# Reconstruction modes

Select exactly one primary mode for each source composition. Editing policy is orthogonal: `native` preserves the established native/evidence workflow; user-approved `hybrid` allows independently replaceable picture components under [hybrid-components.md](hybrid-components.md). Neither a raster exception nor hybrid policy changes the primary mode or permits omission of source content.

## Faithful reconstruction

Use by default when the user asks to turn a reference into an editable artifact without requesting design changes.

- Match the source canvas, panel arrangement, object positions, relative dimensions, typography hierarchy, colors, line styles, and reading order as closely as practical.
- Preserve all visible content. Do not translate, simplify, modernize, or rearrange it without authorization.
- Rebuild ordinary text and redrawable graphical elements with target-native objects.
- Treat visual comparison against the reference as a required QA step. A generated component needs explicit component-level approval as an illustrative substitute; disclose that portion as non-exact. Other faithful source regions keep their original checks and tolerances.

## Semantic editable rebuilding

Use when the user prioritizes easy editing or when a literal target-native replica of complex artwork would be impractical. Disclose simplifications in authoring form, but preserve the source diagram family and professional grammar unless the user explicitly authorizes a representation conversion.

- Preserve entities, relationships, directionality, values, labels, units, legends, and evidence boundaries.
- Replace complex decorative artwork with simpler target-native editable abstractions only when meaning is preserved.
- Keep the original reading order and information hierarchy unless the user authorizes a relayout.
- Report every meaningful simplification or approximation. Do not present this mode as a pixel-accurate replica.

## Redesign

Use only when the user explicitly requests improvement, modernization, translation, restyling, relayout, or conversion to a template or house style.

- Preserve factual content, scientific meaning, and the source's diagram family and professional representation grammar while changing layout, hierarchy, spacing, typography, palette, or emphasis. Read [diagram-grammar.md](diagram-grammar.md) before relayout of a structured visual.
- Keep each semantic role in a compatible form: process and cohort nodes remain process or cohort nodes; decisions remain decisions; exclusions remain exclusion branches; milestones remain milestones; causal and mechanistic edges retain their meanings; chart marks, axes, scales, and uncertainty encodings retain their statistical roles.
- Treat a change from flowchart to timeline, diagram to card list, causal graph to process flow, statistical chart to infographic, or another representation family as a separate contract change. Perform it only when the user explicitly authorizes that type of conversion. Generic requests to redraw, improve, modernize, rethink, or make a visual clearer do not constitute that authorization.
- Separate user-approved design changes from factual corrections. Do not introduce new claims, pathways, data, or interpretations.
- Follow any supplied editable template. For PowerPoint, preserve its master, layouts, theme, and unrelated slides; for other formats, preserve the equivalent document-level styles and unrelated canvases.
- Record the locked or explicitly changed grammar in the visual manifest when one is required, then validate both content and grammar against the source even when pixel-level similarity is not an objective.

## Mode boundaries

- Do not silently switch from faithful reconstruction to redesign because the source looks dated or crowded.
- Do not silently switch diagram families inside redesign. A relayout may reduce cross-panel searching or improve alignment while retaining the source node roles, edge semantics, axes, compartments, and professional conventions.
- Do not use semantic rebuilding to omit difficult content. Retain it as an editable approximation or disclosed raster exception.
- If one panel requires a different treatment, keep the composition's primary mode and disclose the panel-level exception.
- If the requested mode cannot preserve material information, stop the affected portion and request a higher-resolution source or user decision.
