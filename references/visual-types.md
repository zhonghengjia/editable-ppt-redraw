# Visual-type strategies

Read only the sections relevant to the current source. These strategies supplement the shared rules in `SKILL.md`; they do not authorize changes to the user's content.

## Flowcharts, timelines, cohorts, and study designs

- Read [diagram-grammar.md](diagram-grammar.md) and declare the source visual type, node roles, edge roles, and routing contract before relayout.
- Use native containers, nodes, connectors, arrowheads, brackets, milestones, and labels.
- Preserve branching logic, inclusion and exclusion counts, time anchors, line styles, and eligibility relationships.
- Preserve the professional role-to-shape mapping. Do not replace cohort, process, decision, exclusion, outcome, or milestone roles with a different diagram vocabulary merely to modernize the visual.
- Prefer attached connectors over decorative line segments. Keep recurring node styles consistent.

## Scientific mechanisms, pathways, and conceptual models

- Identify entities, compartments, processes, interventions, outcomes, and directional relationships before drawing.
- Preserve activation, inhibition, transport, feedback, causal, and associative arrow semantics. Reproduce the source legend rather than inventing conventions.
- Use grouped native shapes for cells, organs, molecules, devices, or conceptual modules when a faithful editable abstraction is practical.
- Do not infer biological pathways, chemical bonds, anatomical labels, or causal links that are not visible or supplied by the user.
- For highly detailed anatomy, microscopy, or molecular artwork, keep the image component raster if necessary while rebuilding all explanatory overlays as editable objects.

## Graphical abstracts and infographics

- Preserve the intended reading path, panel hierarchy, headline-to-detail contrast, icon repetition, and visual balance.
- Rebuild cards, badges, callouts, icons, arrows, and section backgrounds separately so the composition remains editable.
- Keep one source composition on one canvas, page, or slide unless the user asks to split it or readability requires a user-approved redesign.

## Charts and statistical figures

- When trustworthy source data are supplied, use a native chart object when the selected format supports it faithfully; otherwise keep the data and chart-generation source as the editable authority. Verify plotted values and labels against the data.
- When only a chart image is available, rebuild axes, ticks, labels, legends, markers, intervals, annotations, and visible geometry with editable objects. Do not fabricate hidden observations or exact values.
- Read [curve-fidelity.md](curve-fidelity.md) whenever visible curve geometry carries quantitative or distributional meaning. Extract native vector paths when available; otherwise digitize each visible curve into source-relative coordinates and build the editable path from those coordinates.
- Treat every line, ridge, density profile, histogram outline, step curve, signal, or trajectory as its own series. Preserve curve count, order, peak and valley structure, shoulders, steps, crossings, skew, tails, and source-visible irregularity. Do not reuse a generic parametric template unless the source or supplied data establishes that model.
- Preserve scale type, axis direction, zero or reference lines, confidence intervals, censoring marks, significance annotations, and category order.
- For dense figures such as forest plots, survival curves, ROC curves, heatmaps, nomograms, and multi-panel statistical plots, prioritize quantitative meaning over decorative simplification.
- If exact data cannot be recovered, label the result as a visual reconstruction rather than a data-regenerated chart.

## Tables, matrices, and discrete heatmaps

- Use native tables or aligned editable cell grids so text, borders, fills, and merged regions remain editable in the selected format.
- Preserve row and column hierarchy, units, footnotes, indentation, symbols, and conditional-color meaning.
- Do not recalculate, normalize, or reorder values unless explicitly requested.

## Architecture, network, and technical diagrams

- Use editable containers, layers, swimlanes, ports, components, databases, actors, and connectors.
- Preserve directionality, protocol or interface labels, cardinality, boundaries, trust zones, and dashed-versus-solid semantics.
- Keep repeated components as consistently styled groups that can be duplicated and edited.

## Dashboards and interface-like layouts

- Recreate cards, navigation, controls, tables, charts, status indicators, and labels as separate target-native objects.
- Preserve the visible state represented by the source; do not imply working interactivity.
- Keep photographs, map tiles, or complex screenshots raster only where native reconstruction would misrepresent the content. Rebuild annotations and overlays separately.

## Posters, one-page figures, and slide composites

- Match the original canvas or page aspect ratio and preserve margins, columns, gutters, panel labels, and reading order.
- Keep sections and panels grouped without flattening the full composition.
- Do not automatically convert a poster into a conventional slide deck. Split or reorganize it only when the user requests that transformation.

## Equations, chemical structures, maps, and image-heavy sources

- Use editable equations or text for formulas when the selected format supports them and verify symbols carefully.
- Reconstruct simple chemical structures with lines and text only when bonds, charges, and stereochemistry are unambiguous. Otherwise retain the structure as an image and disclose it.
- For maps, photographs, microscopy, radiology, and other image evidence, retain the evidence image and make every overlay editable. Do not redraw evidence in a way that changes its interpretation.

## Multi-panel figures and batches

- Preserve panel labels, shared legends, common axes, alignment, and relative panel dimensions.
- Group each panel separately and keep shared elements separate from panel-specific content.
- Apply one coherent canvas or page system across a batch while preserving source-specific information.
