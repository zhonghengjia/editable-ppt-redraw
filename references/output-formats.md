# Editable output formats

Choose the target from the user's intended editing surface, fidelity requirement, and downstream workflow. Editability is format-specific; do not describe all outputs as equally editable.

## Routing table

| Target | Choose when | Native editable source | Main limitation |
|---|---|---|---|
| PowerPoint `.pptx` | The user will present, annotate, or continue drawing in Microsoft PowerPoint | Text boxes, shapes, custom paths, tables, charts, connectors, groups | Dense organic paths and advanced interactions are cumbersome; round-trip rendering can shift geometry |
| SVG `.svg` | The user needs a portable vector for Illustrator, Inkscape, Figma import, web, print, or later composition | XML elements such as text, paths, groups, shapes, and markers | Font availability and editor-specific text layout can change; imported SVG may become one picture in PowerPoint |
| draw.io `.drawio` | The visual is a maintained flowchart, architecture, pathway, study design, network, or multi-panel diagram | `mxCell` vertices, edges, groups, labels, tables, and portable embedded SVG assets | Requires diagrams.net/draw.io for the best editing and export; use uncompressed XML for inspectability |
| Excalidraw `.excalidraw` | The user wants a collaborative, sketch-like whiteboard or rapid conceptual editing | Scene JSON elements, bound text, arrows, groups, and libraries | Not suitable for faithful typography, dense tables, or pixel-level reconstruction |
| Mermaid or Graphviz source | The user values version control, semantic source, repeatable auto-layout, or code review more than exact placement | Text-based diagram source | Limited control over pixel-level layout, compact symbols, and source-faithful ornament |
| HTML with inline SVG | The visual needs responsive layout, interaction, accessible motion, or a self-contained browser artifact | HTML, CSS, SVG, and optional local JavaScript | Not a native office document; browser and font behavior must be verified |
| Google Slides or Figma | The user explicitly wants a connected collaborative editor and the required connector is available | Native remote editor objects where supported | Remote transfer changes the privacy boundary and may not preserve every native object |

## Selection rules

1. Honor an explicit format. Do not create a PowerPoint merely because this skill's compatibility name contains `ppt`.
2. When no format is specified, choose PowerPoint to preserve the established behavior of `$editable-ppt-redraw`.
3. Prefer draw.io for connector-heavy diagrams that will be maintained as diagrams rather than presented as slides.
4. Prefer SVG for freeform vector artwork, graphical abstracts, posters, reusable icons, and figures intended for design or publishing tools.
5. Prefer Excalidraw only when a sketch or whiteboard surface is desired; do not use it as a faithful reconstruction shortcut.
6. Prefer Mermaid or Graphviz when structural source control is more important than manual placement.
7. Use HTML with inline SVG when interaction or responsive behavior is a real requirement, not as an unnecessary wrapper around a static image.
8. For multiple outputs, name one canonical editable source and treat all other formats as derivatives unless each has been independently authored and verified.

## Mature backend reuse

Read [backend-routing.md](backend-routing.md), then use this order:

1. An already installed, trusted skill or editor integration that owns the requested format and can preserve its native objects.
2. A project-pinned local renderer or CLI whose version-matched documentation is available in the workspace.
3. Direct local generation of the native source using documented file formats and the bundled validators.

Do not install a renderer, desktop application, plugin, browser package, or system dependency without the authorization required by the current environment. Do not replace a missing editable backend with a hosted conversion service unless the user explicitly authorizes the upload.

## Format-specific construction notes

### PowerPoint

- Use the supplied deck, master, theme, slide size, and layouts when present.
- Keep ordinary text and redrawable components native and independently selectable.
- Render and reopen the exported `.pptx`; run the PPTX editability audit and any applicable connector audit.

### SVG

- Include an explicit `viewBox`; group modules and give important elements stable IDs.
- Keep text as text unless the user specifically needs outlined glyphs.
- Avoid external fonts, remote images, remote stylesheets, and scripts unless explicitly authorized and made portable.
- Use raster `<image>` elements only for disclosed evidence or texture exceptions.

### draw.io

- Prefer uncompressed `mxfile` / `diagram` / `mxGraphModel` XML so the source is inspectable and diffable.
- Keep text, boxes, tables, lanes, and connectors as native cells. Use portable data-URI SVG assets only for reusable symbols that native geometry cannot express honestly.
- Give every cell a unique ID within its own `mxGraphModel`; separate pages may reuse root/layer IDs. Explicit edge `source`/`target` IDs must resolve within that model. An intentionally free endpoint instead requires the corresponding geometry `sourcePoint`/`targetPoint`. Every edge needs `mxGeometry relative="1"`.
- If draw.io Desktop is locally available, export a preview and inspect it before delivery.

### Excalidraw

- Use valid scene JSON with unique active element IDs, bound text for labels, and explicit arrow bindings when appropriate. Active arrow, label/container, frame and `boundElements` references must resolve to active elements; null bindings are valid free endpoints.
- Preserve the source's reading order and relationships while accepting the requested sketch-like representation.
- Keep image elements exceptional and disclosed.

### Mermaid and Graphviz

- Keep the source file as the canonical editable deliverable and render a preview as a derivative. The bundled Mermaid/Graphviz audit is lexical screening, not a full parser; validate with the chosen installed native engine before claiming parsing succeeded.
- Preserve node IDs, labels, edge directions, subgraphs or clusters, and semantic line styles.
- Disclose layout differences caused by the engine rather than hand-editing the rendered derivative.

### HTML with inline SVG

- Keep the artifact self-contained by default: inline CSS, inline SVG, local or system fonts, and no remote assets.
- Separate semantic SVG groups from decorative HTML scaffolding.
- Verify the intended viewport, overflow behavior, accessibility text, and any interaction in a local browser.

## Output naming and preservation

- Never overwrite the user-provided source.
- Use a new versioned filename or isolated output folder.
- Keep the canonical source, rendered preview, comparison evidence, and temporary inspection files distinct.
- Deliver only the requested artifacts and useful editable source; keep transient QA evidence temporary unless the user asks for it.
