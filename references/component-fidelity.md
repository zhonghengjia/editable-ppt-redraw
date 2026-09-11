# Source-specific component fidelity

Read for faithful reconstruction of curved scientific illustrations, anatomy, protein complexes, layered side/cutaway views, device symbols, non-chart contours, or any object whose inner geometry matters. The object need not be biological. This contract complements icon recognition; recognition alone is insufficient in faithful mode. Quantitative x-aligned series still use [curve-fidelity.md](curve-fidelity.md).

## Source-first geometry

Use [appearance-fidelity.md](appearance-fidelity.md) as the shared appearance
planning and evidence authority for native and hybrid representations. Geometry
preservation alone cannot preserve shading, semantic colors or visible overlap;
its probes and visual findings do not replace this document's structural gates.

This is the exact-source/native geometry route. Explicitly approved raster
illustrations use [hybrid-components.md](hybrid-components.md). Generated substitutes
never inherit source-pixel or native-surface PASS. Keep any still-required relation
visible as unverified until independently reviewed; hybrid cannot erase a hard gate.

1. Decode the actual source pixels or vector canvas, not the resized chat preview. Record true dimensions, hash and source-coordinate crops before authoring. Keep source and output coordinate frames distinct.
2. Inventory each sensitive instance and its projected part hierarchy before drawing. Distinguish an independent object, a host surface, a surface-attached band/rib/mark, a hole, and a shading-only region. Follow visible bridges and every gap's termination before deciding whether lobes are separate objects or one connected surface; the number of protrusions is not the number of independent parts. Record view, silhouette, negative spaces, terminals and foreground occluders. A side view permits visible projection reconstruction, not invention of hidden anatomy or a new 3D perspective. If attachment is ambiguous, record uncertainty instead of inventing a relation.
3. Measure the host boundary, surface-detail start/end and bend landmarks, and occlusion intersections independently from the source. Meaningful silhouettes, branches, holes and narrow gaps require `structure_sensitive: true` and the [regional structural contract](regional-fidelity.md#visible-support-structure-within-the-same-region). Do not replace an irregular outline with a few convenient hand-guessed curves; check compact paths against independent source support. Construct attached details in the host's shared local coordinate frame; derive boundaries from the same projected surface. Fit visible source segments and constrain them to that surface, using native intersection geometry when needed. Do not place guessed strips independently or infer a regular cylindrical/helical pattern that the pixels do not establish. A builder/export self-comparison is serialization evidence only.
4. Model neighboring visible pieces together before drawing. Distinguish edge-sharing partitions from true front/back overlap; a globally non-overlapping map cannot recover hidden surfaces. Shared boundaries come from a common arc/label representation and must not be fitted independently for each owner. Preserve source gaps, corner contacts and occlusion terminations; no filler backdrop, uniform inflation or post-output nearest-object reassignment may hide missing coverage. Keep hosts and details grouped for editing without mistaking grouping for a geometric constraint. Use the [marked-source assembly route](source-tracing.md#marked-source-assemblies) when source pixels, rather than reliable vector arcs, establish the common support. Ambiguous fragments remain uncertain, not invented anatomy.
5. Retain editable text separately. Split semantic parts before tracing when their independent selection matters; a crop containing several independent objects is a module, not one conveniently named part. Construct observable part hierarchies through the manifest's `native_components` and [native toolkit](native-toolkit.md), so local coordinates and independently editable fills reach actual output. Use native Paint for supported continuous tones; the [appearance construction](appearance-fidelity.md) route supplies source-patch colors. Choose the [source-part editing budget](source-tracing.md#multi-color-part-representation-and-editing-budget) before dense multi-color tracing. Automatic color layers are not semantic segmentation, and discrete color partitioning is not gradient reconstruction. Do not infer hidden backgrounds to remove source labels; unresolved covered surface remains an explicit limitation.
6. Qualify the selected backend using a representative component containing the needed curves, compound holes, narrow parts and opacity, then save/reopen/render. A textbox or rectangle smoke test does not qualify layered organic geometry. Follow the existing bounded fallback rule; unsupported curves do not justify replacing them with bars.

## Load only the required operation contracts

| Operation / observed feature | Read before use |
|---|---|
| Raster pixels, connected ownership, multicolor native tracing or marked-source assemblies | [source-tracing](source-tracing.md) |
| Faithful standard/dense sensitive shapes, silhouettes, holes, narrow gaps or assembly coverage | [regional-fidelity](regional-fidelity.md) |
| Source-observed attached details | [surface-relations](surface-relations.md) |
| Executable nested parts or continuous native paint | [native-paint](native-paint.md) and [native-component-schema](native-component-schema.md) |

The small router does not waive feature requirements. Select all applicable rows;
do not load tracing recipes for reliable native source paths. Construction masks
and traces are not final-output acceptance evidence.

## Acceptance boundary

Accept a component only when source inventory coverage, host-surface relationships, applicable native geometry checks and actual-render review all support it. Pixel metrics remain diagnostics, not proof of biological correctness, topology, attachment or editability. Report region and relation results separately. A correct outer contour with a detached/misaligned inner band or changed occlusion fails even when the regional metric passes; do not describe the whole component as passed from that metric alone.

In faithful mode stop only when this source-specific comparison and applicable native checks pass, with residual raster/gradient/resolution limitations disclosed. In semantic/restructured mode stop at the explicitly selected invariant contract; do not claim pixel-faithful replication. Neither mode demands unobservable subpixel ornament, but a visible required part is not ornament. Follow the existing bounded correction pass; unresolved defects remain incomplete.
