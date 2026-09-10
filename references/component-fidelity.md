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
3. Measure the host boundary, surface-detail start/end and bend landmarks, and occlusion intersections independently from the source. Meaningful silhouettes, branches, holes and narrow gaps require `structure_sensitive: true` and the structural contract below. Do not replace an irregular outline with a few convenient hand-guessed curves; check compact paths against independent source support. Construct attached details in the host's shared local coordinate frame; derive boundaries from the same projected surface. Fit visible source segments and constrain them to that surface, using native intersection geometry when needed. Do not place guessed strips independently or infer a regular cylindrical/helical pattern that the pixels do not establish. A builder/export self-comparison is serialization evidence only.
4. Model neighboring visible pieces together before drawing. Distinguish edge-sharing partitions from true front/back overlap; a globally non-overlapping map cannot recover hidden surfaces. Shared boundaries come from a common arc/label representation and must not be fitted independently for each owner. Preserve source gaps, corner contacts and occlusion terminations; no filler backdrop, uniform inflation or post-output nearest-object reassignment may hide missing coverage. Keep hosts and details grouped for editing without mistaking grouping for a geometric constraint. Use the marked-source assembly route below when source pixels, rather than reliable vector arcs, establish the common support. Ambiguous fragments remain uncertain, not invented anatomy.
5. Retain editable text separately. Split semantic parts before tracing when their independent selection matters; a crop containing several independent objects is a module, not one conveniently named part. Construct observable part hierarchies through the manifest's `native_components` and [native toolkit](native-toolkit.md), so local coordinates and independently editable fills reach actual output. Use native Paint for supported continuous tones; the [appearance construction](appearance-fidelity.md) route supplies source-patch colors. Choose the source-part editing budget below before dense multi-color tracing. Automatic color layers are not semantic segmentation, and discrete color partitioning is not gradient reconstruction. Do not infer hidden backgrounds to remove source labels; unresolved covered surface remains an explicit limitation.
6. Qualify the selected backend using a representative component containing the needed curves, compound holes, narrow parts and opacity, then save/reopen/render. A textbox or rectangle smoke test does not qualify layered organic geometry. Follow the existing bounded fallback rule; unsupported curves do not justify replacing them with bars.

## Source selection, representation and native tracing

Use one pipeline: source coordinates and assembly support → source part ownership → joint boundary representation → native paths → actual-file evidence. Ownership chooses which observed pixels belong to construction inputs; it is never an output ignore mask or semantic certification. Representation determines how those pixels become geometry; neither stage may change the acceptance contract after seeing an output.

### Marked-source assemblies

For a cluster of adjacent/interleaved visible objects, `source_partition.build_source_partition(source, support_path, plan, node=existing_node)` builds all candidate pieces from one source-coordinate label map before invoking the existing pinned boundary scanner and native component serializer. It returns ordinary `native_components`, the label map and preparation evidence; add those components through `native_components.add_manifest_component`. The helper writes no files and does not accept previous renders or fitted output geometry.

The plan requires `source_sha256`, `source_bbox` `[x,y,w,h]`, `support_sha256`, `support_observation`, `markers`, `colors_per_part` (2–64), `max_native_paths` and `max_native_commands` (positive declared assembly budgets). Optional `representation` selects `palette_edges` (compatibility default) or `palette_stack` as defined below; no other fields are accepted. The support is a binary 0/255 grayscale PNG at crop size. Prepare it from the original source: visible silhouette and real holes, with extraction/measurement provenance; never use a convex hull, filled-hole operation or old output as source truth. It is construction support only, not the mask for final QA. Source must be opaque, qualified sRGB. The shared one-million-pixel bound and importer limits remain unchanged.

Each marker has exactly `id`, `observation`, `seeds`: 1–100 explicit crop-local integer `[x,y]` source witnesses, with at most 100 named parts. Multiple witnesses may identify disconnected visible fragments of one observed object. Every connected support island needs a witness; duplicate/out-of-support seeds fail without snapping. The deterministic four-neighbor priority flood minimizes maximum local RGB change, then path length, with FIFO ties. It assigns support pixels once, leaves outside/holes unassigned and does not discard a watershed separator as transparency. This is an original bounded source-partition adapter informed by marker-controlled watershed, not the OpenCV/scikit-image implementation and not automatic object recognition. Inspect the resulting ownership map against source boundaries; a poor seed or low-contrast boundary can merge or misassign visible pieces even with perfect coverage. Unknown identity remains NOT_VERIFIED.

Each named visible piece reuses the source palette preparation and exact pixel-boundary scanner. No piece is independently smoothed, no background patch is inserted, and native geometry for all colors/owners uses the same lattice. Alpha membership is checked after quantization. The returned ledger binds source/support/plan/label hashes, all assigned pixels, color approximation and native path/command counts. Budgets apply to the complete assembly, not a succession of smaller exemptions. Exceeded budgets or unseeded islands fail; no partial candidate is returned.

The result preserves visible pieces, not complete hidden cells. Within-piece color partitions are independently editable native paths but are not automatically named nuclei or organelles; where those need independent semantic editing, explicitly inventory/mark those pieces instead of claiming color tracing recognized them. Quantization does not reproduce continuous native gradients, and source-grid edges can show steps at high magnification. Keep the existing native Paint route for suitable isolated/overlapping smooth parts; select the source-supported representation before construction. Confirm useful selection/movement in PowerPoint and inspect native rendering for antialias seams.

Assembly coverage is evaluated under the existing regional structure contract, including `coverage` below. Declare the complete assembly as a sensitive inventory region as well as reviewing its named parts. A selected-source/label-map comparison proves preparation only; final geometry/color/coverage checks use original source and the actual saved/reopened render. Missing declarations cannot be counted as not-applicable passes.

```text
python scripts/component_fidelity.py trace reference.png component.svg \
  --crop 120 178 72 95 --colors 16 --node /path/to/existing/node
```

The crop is `[left, top, width, height]` in **source pixels**. It must fit the source, each dimension <=4096 and area <=1 million pixels. Without a selector the adapter uses pinned ImageTracerJS smooth color tracing and an explicit source-derived palette: all observed colors within the color budget, otherwise existing Pillow RGBA octree quantization without dithering. There is no blur, small-path omission, random reseeding, palette re-averaging or coordinate rounding. Color reduction and curve fitting can still lose rare features, small holes and thin bridges. It keeps the crop background and unwanted source letters; these are not editable text. A prepared alpha asset needs recorded extraction provenance, not an unrecorded background erasure.

Outputs are a new SVG plus schema-2 `.trace.json` containing source hash/size/crop, engine hash/options, representation, measured byte/element/path/command complexity and explicit unverified semantic/final-artifact status. Failed tracing or preflight writes `.trace.failed.json` with source binding, available measurements and the error, without emitting an SVG or successful sidecar. Existing success or failure paths are refused. SVG generator metadata is removed and primitive opacity is represented as fill/stroke opacity; native-profile preflight rejects unsupported content before emitting the candidate. Use the existing [native toolkit](native-toolkit.md) to import paths as native DrawingML, not an SVG picture. Output IDs identify path pieces, not automatically recognized semantic parts. Record the helper's native object mapping and give source-grounded names/groups.

For a color-separable **visible silhouette**, add `--selector selector.json` using the selector schema below. Preparation selects source pixels on a fixed white matte and retains every fragment and hole unless an explicit source ownership recipe selects one observed connected part. It creates a uniform median source fill and records input/output Boolean mask hashes, selector hash, topology and fill. Empty/full-crop selections are rejected. There is no morphology, hole filling, automatic island deletion, inpainting or hidden continuation. Foreground letters/objects may produce genuine holes in visible color support; record them as unresolved occlusion, not automatically repaired anatomy. Uniform fill is not gradient reconstruction.

Selected support defaults to `--representation source_edges`: pinned ImageTracerJS `layeringstep`/`pathscan` supplies exact integer pixel-cell boundaries, bypassing internode averaging and spline fitting. Only exactly collinear vertices are removed; opposite hole winding produces compound native paths with real gaps, not background-colored masks. This retains source-resolution stair steps and potentially many editable vertices; it does not infer continuous subpixel curves. Choose this representation before authoring when narrow connections/gaps must survive. `--representation smooth` explicitly selects the fitted alternative; it is not a fallback after a failed source-edge export. Ordinary multi-color tracing defaults to smooth; the explicitly planned multi-color alternative is `palette_edges` below. `source_edges` without a selector, non-binary support or unsupported requests fail. Any smoothed or manually fitted replacement must independently pass the same source-defined limits, never inherit the raw-edge candidate's result.

### Multi-color part representation and editing budget

For a source-inventoried multicolor part, choose one composition before authoring: `--representation palette_edges --part-plan part.json` emits disjoint color faces, while `palette_stack` emits opaque source-color-tree paint layers. Both reuse the same boundary scanner, preserve quantized source color at pixel centers and are not automatic object recognition. Required part-plan fields, no others:

- `part_id`, `observation`: nonempty identity and source evidence for the chosen editing unit. Keep required independent objects/labels separate; grouping a whole panel as one part is not a remedy for over-complexity.
- `source_sha256`, `source_bbox`: exact input-byte hash and trace crop. Freeze the recipe against the raw input, not the output.
- `max_native_paths`, `max_native_commands`: positive integer task budgets selected before construction for the intended editor interaction. The helper bounds these numeric inputs at one million, but still enforces the unchanged, more restrictive SVG import profile. These are not fidelity thresholds or universal defaults. Judge budgets from the intended component granularity and representative editor behavior; never raise them after a failure to certify that candidate.

The plan may also constrain `smooth` or `source_edges`. It is mandatory for both palette representations, which cannot be combined with the uniform support selector/connected-ownership route. A separated alpha input must retain its extraction provenance and linkage to the original source inventory.

`palette_stack` requires opaque colors with only 0/255 source alpha, checked before quantization and again at the worker. It builds a deterministic binary tree by nearest RGB color-centroid distance, weighted by source pixel counts. A parent uses an observed representative color and exactly the union of its descendant source color supports. Preorder painting omits only inherited identical paint, not visible source pixels. Every original transparent hole stays outside every layer. Tree paint order is an encoding of visible colors, not anatomical depth. This reuses the existing scanner and packing logic; no second contour fitter, extra stroke, dilation, per-output seam locator or full-canvas backdrop is introduced. Partial-alpha artwork must retain the disjoint route or a separately qualified native representation, never flatten opacity to use stacking.

At ideal source-pixel centers, opaque overpainting gives the same quantized colors as disjoint faces. Parent color under adjacent child paints reduces background leakage inside a part when an editor antialiases each face separately. Actual antialiasing can still mix those colors, and contacts between independent owners remain subject to final-render review. Keep parts inside their original visible support. Moving an internal paint layer may reveal encoding colors underneath; only a source-supported semantic part hierarchy promises meaningful independent object movement. Whole-part recoloring/movement and native paint editing remain available. This route does not solve pixel stair steps or recover continuous source gradients.

The adapter quantizes once using the existing source palette policy, without dithering, and feeds those exact RGBA pixels to the pinned boundary scanner. Adjacent colors use the same integer pixel lattice, not independently fitted curves. Every visible pixel is assigned; alpha-zero pixels are accounted for but have no path. Prepared-pixel hashes and white-matte mean/max RGB error and changed-pixel counts identify the **color quantization** approximation. Exact tracing of this prepared input does not prove fidelity to original gradients or thin source features lost during quantization.

Within this declared part, disjoint same-fill outer contours and their hole children may share a native compound path. Hole winding and complete parent/child rings stay intact. The implementation reuses the existing boundary extraction and exactly collinear removal, with equivalent H/V encoding; it never combines overlapping arbitrary SVG paths, strokes, masks, separate semantic parts or fitted color layers. Packing follows source region order and the importer-owned path-character limit; an indivisible overlong region fails instead of being tiled or losing holes. The sidecar records each color's pixel/region count and half-open source-region ranges mapped to output IDs. Keep native part grouping and editable text separately in the builder.

Preflight evaluates both serialization limits and the declared path/command budget. A compound path can be small on disk yet contain tens of thousands of vertices; packing does not reset the command count. `complexity.native_profile: PASS` and `budget_status: PASS` establish only these numerical checks; `practical_editability` stays `NOT_VERIFIED` until actual output selection, recolor/move behavior, grouping and rendered fidelity are inspected. Preserve separate source-versus-preparation, preparation-versus-vector, and original-source-versus-final-render results. All final regional/structural/relationship gates still apply to the original source, never the quantized image as replacement ground truth.

### Connected source ownership (construction only)

If the crop's selected color belongs to several objects, inspect source support and optionally add `--ownership ownership.json`. One recipe identifies one **connected visible part**, not the largest region. Freeze it from the raw source before constructing output. Required fields, no others:

- `part_id`, `observation`: nonempty source inventory identity and evidence/uncertainty description.
- `source_sha256`, `source_bbox`: exact source-byte hash and the same integer crop used for tracing.
- `selector_sha256`: hash from `component_fidelity.recipe_digest(selector)` (UTF-8 canonical sorted-key compact JSON, not the recipe file's whitespace-dependent hash).
- `seeds`: 1–100 unique integer `[x,y]` witnesses in crop-local source pixels. Every witness must hit the same 8-connected selected component. Background, out-of-bounds, duplicate or disagreeing witnesses fail; no snapping, automatic largest-blob choice or invented bridge.

The trace sidecar records the full recipe/hash, selected component and **every unassigned component's ID, area and box**. The same `component_geometry.label_regions` traversal defines component membership and topology; there is no separate segmentation implementation. More than 2000 components exceeds this ownership-ledger profile and fails without dropping fragments. Unassigned content remains a source-inventory obligation, not approved deletion. If an occluded semantic part has multiple visible components, inventory/trace them separately and retain uncertainty rather than forcing a connected recipe.

Do not apply this ownership selection to final-render QA or use it to remove mismatches. The regional contract below still compares full source/render regions with identical selectors and unchanged gates. Source versus extracted support checks establish preparation only; complete-figure color, occlusion, labels, practical grouping and actual native-render checks remain separate requirements.

No model, GPU, network, OCR or package installation is invoked. Node is an explicit existing local runtime. Unsupported high-complexity/noisy crops fail the native profile or source-part budget with retained diagnostics. Do not increase limits, discard paths, split the same object into arbitrary tiles or switch representation silently. A failed editing budget calls for source-grounded part decomposition or an explicitly approved representation change, not a numerical exemption. Fitted adjacent color layers can show seams, and exact shared pixel edges can remain cumbersome to edit. Inspect native rendering as well as geometry: identical mathematical boundaries do not guarantee identical antialiased paint in every editor. Arbitrary thick strokes must not hide seams or close genuine gaps.

## Host-surface relationship evidence (single schema authority)

For faithful manifest-backed work, mark every observed attached detail `surface_detail: true` in `source_inventory`. Add `surface_relations` with `source_sha256` and a `relations` list. Each relation has:

- `id`, `source_inventory_id`: unique relation and source detail identities; one relation per detail.
- `host_name`, `detail_name`: exact, globally unique native output names. Each selects one closed custom path; use separate relations for independently visible fragments. Do not invent hidden continuation to fit this profile.
- `host_landmarks`, `detail_landmarks`: 3–100 boundary points each, measured in decoded source pixels before building. Include source-observed endpoints, bends and edge contacts rather than only convenient corners. Keep the crop/measurement provenance with the task. These landmarks must not be extracted from the output being evaluated.
- `occluders`: explicit list of foreground native object names, including an empty list when none. The current auditor supports single closed paths and validates paint order, not optical visibility or opacity.
- `max_landmark_error_px`, `max_escape_px`: finite, nonnegative source-pixel tolerances, bounded at 20 pixels by the audit profile. Choose tighter task-appropriate values before authoring; never enlarge them after a failure. `max_escape_px` bounds how far the detail may lie outside the host's sampled boundary.
- `source_observation`: concise visible evidence for attachment and the chosen tolerance. Describe uncertain or occluded source boundaries explicitly.

The existing manifest validator enforces IDs, numeric bounds and inventory coverage. The quality runner invokes `scripts/surface_relations.py` against the actual PPTX, reusing the native path reader and axis-aligned group transforms. It checks host/detail boundary landmarks, half-source-pixel sampled containment and native paint order. Nonzero rotations, compound/multi-path objects, missing transforms or unsupported targets remain unverified; duplicate/missing identities and geometric violations fail. This bounded geometric sampler is not a general exact boolean/3D surface solver. Preset shapes needed by a relation must be represented by a supported native path or verified separately without claiming this gate passed.

Reopen and render the actual artifact. Compare each relationship at delivered size and 4–8×: surface curvature, band widths/spacing, edge termination, negative gaps, foreground occlusion and translucent interactions. Record each relation as PASS, FAIL or NOT_VERIFIED with the crop and concrete observation. Machine geometry and regional color checks are supporting evidence; neither proves visible attachment. This applies to anatomy, instrument markings, membranes, layered machinery and other source-specific illustrations, not only one scientific figure.

When the user requests an independent skill test, build in a new directory from the raw reference. Do not load the previous deck, builder geometry, extracted parts or coordinates as construction inputs. Reusable format serializers and skill utilities are allowed. Record raw inputs and test provenance separately from prior diagnostic findings.

## Regional evidence contract (single schema authority)

For faithful standard/dense work, mark source-specific sensitive shapes/icons/charts in `source_inventory` with `fidelity_sensitive: true`. Each marked item needs a region; the agent must inspect inventory completeness rather than omit difficult items to bypass QA. Fast isolated work may record the same comparison evidence in working notes; it cannot claim an unrun machine gate. Semantic/redesign tasks use source invariants and visual review, not an unchanged-layout pixel gate.

Optional manifest `regional_fidelity` has this structure (numbers are illustrative, **not universal acceptance defaults**):

```json
{
  "source_size": [854, 749],
  "source_sha256": "<64 lowercase hex characters>",
  "regions": [{
    "id": "component-left",
    "source_bbox": [120, 178, 72, 95],
    "features": ["open lower gap", "thin stalk", "front band overlaps rear envelope"],
    "threshold": 0.1,
    "window": 8,
    "max_mismatch_ratio": 0.10,
    "max_window_ratio": 0.35,
    "rationale": "Set before authoring from source resolution, thin features and acceptable render noise"
  }]
}
```

Region IDs uniquely reference inventory items. There are 1–100 regions, crops use integer source pixels and fit the source. Each region needs its own nonempty features/rationale. Threshold and both ratios must be finite in `[0,1)`; window is a positive integer fitting the crop. Do not tune thresholds after seeing failures or enlarge a region with white margins to dilute the defect. Region selection should include the complete component but avoid unrelated labels. For crowded interleaved content compare the whole module and manually inspect its named parts; do not use undocumented ignore masks.

### Visible-support structure (within the same region)

Every `structure_sensitive: true` inventory item requires a `structure` object in its existing region. Legacy color-only regions report `structure_status: NOT_DECLARED`, not geometric fidelity. There is no second region list. `component_fidelity.py::validate_contract` delegates these fields to `component_geometry.py` and remains the single regional entry point used by the manifest validator and quality runner.

```json
{
  "selector": {
    "rgb": [[0,90],[60,180],[100,240]],
    "differences": [[2,0,40,230]],
    "observation": "Illustrative blue support; inspect source mask and record foreground confounders"
  },
  "min_iou": 0.98,
  "max_boundary_px": 1,
  "max_boundary_p95_px": 1,
    "topology": "exact",
  "rationale": "Illustrative synthetic bounds; not universal screenshot defaults"
}
```

Freeze selector and bounds from source evidence before constructing the candidate. `rgb` is three inclusive R/G/B integer ranges in 0..255. Each difference constraint is `[channel_a,channel_b,min,max]` for signed `a-b`, channels 0/1/2, bounds -255..255; at most six unique ordered pairs. Both lists (differences may be empty) and nonempty `observation` are required; unknown fields fail. Apply the identical rule and white-matte compositing to source and final render. Do not fit separate render thresholds, register individual objects, or use output-derived masks as source truth.

`min_iou` is finite in `(0,1]`; both boundary bounds are finite source-pixel distances in `[0,20]`. `topology` is `exact` or `report_only`. Exact requires equal component/hole counts. Report-only must be justified before authoring by visible-occlusion/anti-alias confounders and does not certify topology. If support cannot be reliably separated, record the applicable structure evidence as incomplete; do not invent a permissive selector or switch topology mode after failure.

For adjacent/interleaved assembly coverage, include optional `structure.coverage` with exactly `max_introduced_hole_pixels` and `max_filled_source_hole_pixels`, integers from 0 to one million chosen from source resolution before construction. Zero is appropriate only when the source and renderer support a strict no-new-hole/no-filled-hole comparison; it is not a universal screenshot default. `component_geometry.coverage_changes` reports every bounded render hole's source-occupied pixels, every source hole's render-occupied pixels, and all missing-support connected regions with locations. This detects holes moved to new positions even when counts agree. Crop-edge-connected cracks remain missing-support regions, not closed holes, and are still subject to existing IoU/distance/color checks. Neither source nor render is filled, expanded or morphologically repaired. More than 2000 diagnostic regions stays unverified through the existing complexity-failure route. Coverage is an additional check, never a replacement for source boundaries, colors or original holes.

Reports contain IoU, missing/extra pixels and crop-local boxes, both directional maximum distances, worst boundary point, 95th percentile, and topology. Foreground uses 8-connectivity and background 4-connectivity; crop-edge background is not a hole. Every pixel participates; no fragment omission or filling. These describe **visible color support**, not hidden anatomy or semantic object counts. Display source/render masks with results, especially where foreground labels produce holes.

Distances are exact nearest distances between discrete foreground boundary pixel centers: not continuous Bézier distance, not area-weighted surfel distance, and not a perceptual score. Both directions detect erased and extra projections. The existing Pillow/NumPy implementation is bounded to one million crop pixels and 50 million point pairs in fixed memory blocks, without sampling. Missing NumPy or exceeding limits yields `NOT_VERIFIED`; empty or full-crop support is invalid because it does not isolate the requested silhouette. Do not silently enlarge limits or subsample.

Structural checks are additive: `passed` requires original color gates and all declared structure gates. Structural PASS cannot override color FAIL, and the 95th percentile cannot replace the maximum-distance gate. Source-versus-builder comparison is not final-artifact evidence. Selector candidates still require native editability, final-file rendering, text checks and visual review.

After rendering the saved/reopened final artifact, record a separate evidence JSON:

```json
{
  "artifact_sha256": "<hash of final editable file>",
  "render_path": "final-slide-1.png",
  "render_sha256": "<hash of that rendered image>",
  "renderer": "actual renderer and version used",
  "rendered_from_final_artifact": true
}
```

`render_path` is relative to this evidence file; `manifest.source.path` is relative to the manifest. The artifact/render/source hashes must match actual bytes. Assertions and hashes associate files, not independently authenticate their history: never attach a fresh hash to a stale builder preview. This adapter compares one full-canvas source/render pair per manifest/artifact run. Multi-slide/multi-source work needs independently scoped pairs; this gate does not prove every page was rendered.

```text
python scripts/run-quality-checks.py final.pptx --manifest visual-manifest.json \
  --render-evidence render-evidence.json --node /path/to/existing/node \
  --json qa.json --fail-on-risk
```

The local adapter checks real dimensions, refuses a render smaller than the source or a changed aspect ratio (only <=1 render pixel of rounding tolerated), and aligns by whole-canvas size only. It never optimizes rotation, elastic warp or a crop to hide differences. Pixelmatch measures each crop's total mismatch **and maximum sliding-window mismatch**. Anti-aliased differences are included so thin genuine features cannot silently disappear. Missing evidence/runtime is `NOT_VERIFIED`, inconsistent inputs or excess differences are `FAIL`; existing profile choices cannot disable a declared contract.

## Acceptance boundary

Accept a component only when source inventory coverage, host-surface relationships, applicable native geometry checks and actual-render review all support it. Pixel metrics remain diagnostics, not proof of biological correctness, topology, attachment or editability. Report region and relation results separately. A correct outer contour with a detached/misaligned inner band or changed occlusion fails even when the regional metric passes; do not describe the whole component as passed from that metric alone.

In faithful mode stop only when this source-specific comparison and applicable native checks pass, with residual raster/gradient/resolution limitations disclosed. In semantic/restructured mode stop at the explicitly selected invariant contract; do not claim pixel-faithful replication. Neither mode demands unobservable subpixel ornament, but a visible required part is not ornament. Follow the existing bounded correction pass; unresolved defects remain incomplete.
