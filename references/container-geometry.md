# Container geometry and border ownership

Use these rules for cards, rounded panels, colored header bands, callouts, repeated boxes, legends, and nested modules.

## One visible boundary, one stroke owner

- Assign every visible border to exactly one object.
- A fill layer, clipping mask, cleanup mask, or edge-aligned color band must be borderless.
- Do not stack same-bounds shapes with matching visible strokes. This creates discontinuous, doubled, or darker borders after PowerPoint rendering.
- When a colored band touches the outer edge of a rounded panel, keep the band rectangular or clipped to the panel and put one border-only outline above both fills. The band's interior edge stays square unless the source shows otherwise.
- Do not hide a duplicated border with a white patch. Fix the layer model.

## Explicit inner content box

For each container, define an inner box after subtracting border width and content padding. Position icons, text, and repeated columns relative to this inner box, not the outer panel.

- Center a single content group by its union bounds, not by any one child.
- For repeated columns or rows, use common centers, baselines, and gaps. Calculate positions from the container's inner box rather than nudging each object independently.
- Resolve overflow in this order: correct the parent bounds, reduce unnecessary spacing, resize decoration, then shorten or reflow text. Do not scale the whole group as the first response.
- Preserve source occupancy. A technically centered group that is visibly too small or sparse still fails faithful reconstruction.

## Geometry QA

After reopening the PowerPoint, reject:

- duplicate same-bounds strokes;
- bands whose outer corners do not follow the panel boundary;
- content whose union bounds are visibly off-center;
- inconsistent repeated gaps or baselines;
- children outside the declared inner box;
- borders interrupted by overlays, cleanup patches, or foreground icons.

`audit-pptx-editability.py` reports duplicate-border candidates and top-level out-of-bounds objects. Visual review remains required for optical centering and edge-band corner fidelity.
