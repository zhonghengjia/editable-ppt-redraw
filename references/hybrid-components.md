# Independent image components with native editable structure

Read when the user accepts movable/scalable/replaceable raster illustration
components. Authoritative fields live in [hybrid-component-schema](hybrid-component-schema.md),
not a second asset ledger. Preserve the default native route and existing source
trace limits. Do not switch to hybrid merely because native reconstruction fails.

## Select an editing unit before technology

Inventory source objects, scientific roles and requested editing scope. Keep text,
axes, curves, chart values, legends and critical connections native. Use an image
only for a genuinely independent object or preserved evidence. Neither small area
nor a large native-object count permits slicing screenshots into tiles or hiding
them inside groups. Check every source item, including content inside pictures.
Uncertain anatomy stays uncertain; plausible generation cannot recover missing
scientific evidence.

Prefer a suitable original object, approved local asset or licensed asset before
generation when object-level picture editing is the accepted scope. When individual
inner parts matter, use source-grounded native part trees and Paint under
[native-paint](native-paint.md) rather than generating the entire assembly
as one image. A cell cluster, device assembly or branching surface is not one
editing unit merely because it fits in a small box. Whole-object generation is
appropriate only when its internal editability and illustrative substitution are
explicitly accepted; its geometry/appearance requirements are still not guaranteed
by prompt text. Record each asset's own license/attribution: repository code licensing
does not license artwork or model weights. No external model stack is required.

## Local component construction

For an approved source object with existing or independently qualified alpha, use
`scripts/raster_components.py` and the asset's optional `preparation` contract in
[hybrid-component-schema](hybrid-component-schema.md). This is a Pillow/NumPy processing route,
not automatic semantic segmentation or vectorization. It preserves supplied
texture/alpha; known-matte unmixing can remove edge color contamination. If alpha
is missing, the separate [source-object acquisition](source-assembly.md) operation
can propose support for inspection; preparation itself must not silently infer
unknown masks/mattes, fill transparent holes or act as a failed-native
fallback. The crop must be an accepted editing unit, not an arbitrary panel tile.

```text
python scripts/raster_components.py prepare --manifest plan.json --asset-id cell --out-manifest prepared.json
python scripts/raster_components.py preview --manifest prepared.json --order cell other-object --canvas-inches 10 6 --background 255 255 255 --output light.png
python scripts/raster_components.py preview --manifest prepared.json --order cell other-object --canvas-inches 10 6 --background 24 28 36 --output dark.png
```

Use actual IDs, not these illustrative names. Preparation reads the original,
writes a new PNG at the asset's planned path and a new sibling manifest, and
never overwrites files. The Python `prepare_asset` API returns bytes, copied
manifest and diagnostics without writing. Inputs are capped at 16 million pixels,
prepared crops at 4 million. Unknown ICC/orientation, frame/mode, source hash,
alpha size or incompatible matte fail explicitly. These are processing limits,
not quality thresholds; no automatic downsampling relaxes them.

Preview uses existing instance placements, explicit back-to-front instance order
and premultiplied-alpha resampling (1..600 DPI; 16 million output pixels). It is
only a **partial component preview**: native labels/paths/links are absent. It
rejects rotation, crop, distortion and off-canvas placements; use the selected
target renderer for those. Inspect light/dark views for halos, damaged branches,
holes and occlusion; do not substitute this diagnostic for final-slide rendering.

## Built-in generation route

Read the available `imagegen` skill and current tool interface before calling them.
Use `component_assets.generation_preflight(request, manifest=manifest, tool_available=...)` before
the call. It validates the record only, invokes no network, and is not a security
sandbox. The executing agent must match the record to what is actually sent.

1. Obtain approval for the component's illustrative substitution. Separately
   confirm approval for each transmitted reference. Text-only approval does not
   authorize a source upload; built-in approval does not authorize other services.
2. Prepare one isolated base request: identity, projection/orientation, style,
   intended aspect/physical size, transparent safe margin, no labels, numbers,
   axes or cross-component arrows. Bind the source-observed requirements through
   [appearance-fidelity.md](appearance-fidelity.md), which owns the appearance
   fields, prompt binding and comparison mode. Distinguish structure references
   from style references. Do not add hidden anatomy or invented depth.
3. Invoke the actual built-in image-generation tool, one component per request.
   Inspect local edit targets with view_image first. Follow current tool arguments
   for reference paths/recent images; do not invent seeds, ControlNet weights or
   other controls absent from the interface.
4. Preserve the returned file and actual metadata. Copy the selected asset into
   the workspace without overwriting predecessors, then hash it. Failed calls,
   unavailable tools, missing outputs or empty files stay failures. Do not use
   placeholders, automatic API fallbacks, key requests or model installation.
5. Inspect structure and alpha before placement. Corrections share the entire
   redraw's one evidence-driven correction pass. Follow imagegen's editing rules;
   do not erase white pixels or erode edges to simulate a clean cutout. Matting or
   segmentation needs separately justified authorization and qualification.

A skill upgrade, research task or local validation request does not authorize
sending user images for generation. If generation is unavailable, stop that
component and retain useful completed native work.

## Assembly and replacement

Keep the selected presentation backend. Embed independently named picture objects
with preserved aspect ratio. Text, quantitative curves and key relations remain
separate native objects. SVG-as-picture is still object-level editing. Declare
crop and placement before export; reuse asset_id only for the same approved file,
and keep separate instance IDs for repeated placements and semantic variants.

Verify that the backend actually serializes picture names: alternative text or an
image facade ID may not become PowerPoint's selection-pane name. Where the backend
exposes a documented canonical document model, assign stable names there before
export and resolve actual native IDs afterward. Do not repair missing identity only
in the delivered ZIP or pretend an empty name is a unique component selector.

Replacement uses `raster_components.replace_instance_asset(manifest, instance_id,
new_asset, base)` or the CLI below. Supply the complete approved new asset record
with fresh asset ID/provenance/hash. It returns a copied canonical manifest,
changes only the selected binding, preserves shared users and instance geometry/
anchors, and rejects changed image aspect ratio. No old image files are deleted.

```text
python scripts/raster_components.py replace --manifest prepared.json --instance-id cell-01 --asset-record replacement-asset.json --out-manifest replacement-ready.json
```

The command does not modify PPTX. Regenerate through the same canonical builder,
preserving names, shape identity, alt text, placement, crop and anchors; do not let
the new filename silently change non-media properties. Re-run the
package audit and `component_assets.verify_replacement(before, after, slide, name,
expected_sha256)` on actual files. This read-only helper compares unrelated object
XML/media, target identity and geometry. Media relationship IDs resolve to their
actual byte hashes before comparison; shape IDs and all other object properties
remain strict. Shape renumbering cannot be waved through as unchanged. It does not compare every proprietary package extension or
certify application drag behavior.

Qualify real PowerPoint selection/replacement on an isolated copy before promising
practical editing. Grouping or static anchors cannot prove automatic rerouting.

## Layered acceptance

Run the ordinary quality runner with the manifest. The extended PPTX audit reads
actual embedded media and recursive group/rotation/crop coordinates. Asset checks
measure alpha bounds, edge contact, visible pixels and effective placement DPI.
They reject alpha-visible destructive crop and distorted aspect ratio. Reflected
or nonorthogonal transforms, nonrectangular clipping, effects and inherited media
stay unverified when unsupported. Neither standalone `--fail-on-risk` nor the
quality runner may count unsupported readback as success.

Inspect every asset against its source-bound [appearance requirements](appearance-fidelity.md),
then the final composition and detail crops. Keep requirement-specific findings
in the existing render evidence with hashes and applicable background views.
The appearance runner detects missing records and declared measurement violations,
not whether a human truly inspected them. Alpha does not prove clean edges; an RGB
checkerboard is opaque. Biology, false tile labels, missing inventory and visible
occlusion remain explicit visual obligations, not automated semantic certification.

Exact native components retain their original regional/structural/surface tests.
Generated substitutes use approved invariants and actual rendered appearance, not
pixel-copy claims. Required host/detail relations inside raster components do not
pass the closed-native-path surface gate: retain it as unverified and record a
separate source-grounded manual relation finding. Do not remove required relations,
relax tolerances or change them to NOT_APPLICABLE merely to clear QA.

Disclose native parts separately from independent picture parts. Retain provenance,
hashes, actual generated prompt and QA evidence with canonical source. Identity is
not scientific validation. The machine summary always keeps delivery_ready null;
the executing agent reports actual visual review separately. Remaining blockers
mean incomplete.
