# Icon and compact-symbol reconstruction

Use this reference when a source visual contains icons, pictograms, compact device symbols, simplified organs, instruments, or other small graphics whose recognizability depends on a distinctive contour or arrangement of parts. Logos and evidence images follow their own provenance rules; do not redraw them as generic lookalikes.

## Define the recognition signature

Before drawing, inspect the icon separately from its label and record the minimum features that identify it:

- outer silhouette and orientation;
- topology: open or closed loops, branch count, connection order, and whether lines join or remain separate;
- characteristic terminals such as rings, hooks, tips, blades, probes, caps, or handles;
- negative spaces and holes that must remain visible;
- relative size and placement of the main components;
- stroke system: outline or solid silhouette, weight, cap shape, join shape, and color.

Treat these features as fidelity requirements. A symbol that conveys only the broad category, such as "medical" or "equipment", is not a faithful reconstruction when its recognition signature differs from the source.

For a `fast` task, keep the signature in the working notes. For a `standard` or `dense` task, inventory every recognition-dependent symbol. When a visual manifest is used, record the inventory in its optional `icon_signatures` field with a stable icon ID, owning module, object class, and non-empty list of required features. Do not reuse one generic signature across icons that represent different object classes.

## Choose one coherent native representation

Use the simplest representation that preserves the recognition signature:

1. Reuse the source's native object when editing an existing artifact in the same target format and the object is suitable.
2. Use a small module of AutoShapes for geometry defined by circles, rectangles, polygons, and straight segments.
3. Use one or a few native custom paths for continuous curved tubing, outlines, cutting edges, organic contours, or distinctive silhouettes. Preserve cubic Bézier paths directly when available. The [native toolkit](native-toolkit.md) imports supported SVG components without fragmenting curves into bars or pictures. Use sampling only when the selected backend cannot represent curves, and verify the approximation at delivered size.
4. Use a disclosed raster or limited-editability vector only when an honest target-native reconstruction is impractical and the selected reconstruction mode permits it.

Do not assemble a continuous curved source symbol from separated rotated bars, short line fragments, or background-colored masks when that construction creates visible gaps, false branches, abrupt joints, or dependence on one panel fill. Keep line continuity and z-order stable after export and reopen or reparse.

Bundled Lucide assets and their source hashes are listed in `assets/lucide/inventory.json`. An asset is eligible only after comparing its recognition signature with the source and mode. A generic library icon must not replace a distinct source icon, logo, anatomy or instrument merely because the label matches. Record the asset ID and source hash in the run record; no remote asset service is required.

## Raster asset integrity

When a compact symbol remains raster, the crop must preserve the complete visible subject before padding or placement:

- begin with source pixels beyond the apparent subject boundary; do not use a tight crop that already cuts a terminal, loop, handle, or outer stroke;
- reject an extracted alpha asset when visible pixels enter the configured edge-risk band; adding transparent padding after pixels are missing is not a repair;
- preserve intrinsic aspect ratio and use contain placement unless an intentional source crop is documented;
- keep one consistent transparent safe area around a family of icons so visual size does not drift merely because source crops differ;
- reject neighboring text, borders, connectors, shadows, or unrelated components inside the asset;
- keep the final asset project-local and record the source crop or provenance in the manifest.

Run `scripts/audit-raster-asset-integrity.py <asset-or-directory> --fail-on-risk` before placement and again on any corrected extraction. The script checks readability, alpha-visible bounds, edge contact, occupancy, and minimum visible size; semantic recognizability still requires the recognition-signature comparison below.

## Construct by semantic parts

Build the icon from its functional parts rather than from arbitrary geometric fragments. Each part should have a stable name and an intentional relationship to the others. Examples of part roles include a main body, paired tubes, a junction, a terminal ring, a handle, a neck, a blade, a sensor, or a support baseline.

Use these invariants:

- A continuous source stroke remains continuous in the native path model.
- Closed holes and rings remain open after export; do not fill their negative space accidentally.
- Intersections are intentional and use shared coordinates; near-misses are failures.
- Solid silhouettes use closed paths. Outline symbols use open paths plus explicit closed components where required.
- Stroke weight is chosen for the final display size, not only for a magnified authoring view.
- The module stays inside its allocated frame and does not intrude into adjacent labels.
- Logical parts remain independently selectable when that improves practical editing; do not fragment a single contour solely to increase object count.

## Recognition-first QA

For each reconstructed icon or symbol:

1. Confirm that every recognition-dependent symbol has a recorded signature; missing inventory is a planning failure for `standard` and `dense` work.
2. Crop the same region from the source and from the render of the reopened or reparsed final artifact. For repeated checks, define regions as `[left, top, width, height]` and run `scripts/build-comparison-contact-sheet.py`.
3. Inspect both at the delivered size, then at approximately 4-8 times magnification.
4. Temporarily ignore or cover the adjacent label. The symbol should still be identifiable by its visual structure. If it is ambiguous without the label, treat the reconstruction as failed.
5. Compare the recorded recognition signature: silhouette, topology, terminals, negative spaces, component proportions, stroke continuity, and orientation.
6. Check that small gaps, inner holes, and narrow strokes survive the actual target-format export and reopen cycle.
7. For raster assets, confirm the integrity audit passes and the placed shape preserves the asset's aspect ratio.
8. Confirm the icon remains native and editable, or is accurately disclosed as a movable raster exception, in the applicable editability or source audit.

Block delivery when any defining component is missing, a continuous path is visibly disconnected, an unintended branch appears, a ring or hole closes, a terminal becomes indistinct, the symbol overlaps its label, or the result represents a different object class. Stop refinement when the source-grounded signature is recognizable at the delivered size, the module is editable, and no blocking defect remains; pixel-perfect ornament is not required.
