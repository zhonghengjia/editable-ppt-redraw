# Source-specific component fidelity

Read for faithful reconstruction of curved scientific illustrations, anatomy, protein complexes, layered side/cutaway views, device symbols, non-chart contours, or any object whose inner geometry matters. The object need not be biological. This contract complements icon recognition; recognition alone is insufficient in faithful mode. Quantitative x-aligned series still use [curve-fidelity.md](curve-fidelity.md).

## Source-first geometry

1. Decode the actual source pixels or vector canvas, not the resized chat preview. Record true dimensions, hash and source-coordinate crops before authoring. Keep source and output coordinate frames distinct.
2. Inventory each sensitive instance and its projected part hierarchy before drawing. Distinguish an independent object, a host surface, a surface-attached band/rib/mark, a hole, and a shading-only region. Follow visible bridges and every gap's termination before deciding whether lobes are separate objects or one connected surface; the number of protrusions is not the number of independent parts. Record view, silhouette, negative spaces, terminals and foreground occluders. A side view permits visible projection reconstruction, not invention of hidden anatomy or a new 3D perspective. If attachment is ambiguous, record uncertainty instead of inventing a relation.
3. Measure the host boundary, surface-detail start/end and bend landmarks, and occlusion intersections independently from the source. Meaningful silhouettes, branches, holes and narrow gaps require `structure_sensitive: true` and the structural contract below. Do not replace an irregular outline with a few convenient hand-guessed curves; check compact paths against independent source support. Construct attached details in the host's shared local coordinate frame; derive boundaries from the same projected surface. Fit visible source segments and constrain them to that surface, using native intersection geometry when needed. Do not place guessed strips independently or infer a regular cylindrical/helical pattern that the pixels do not establish. A builder/export self-comparison is serialization evidence only.
4. Preserve front-to-back ordering and visible gaps. A detail terminates or disappears where the source host edge or foreground object requires it; do not cover errors with background-colored masks. Keep host and details logically grouped for editing, but do not treat grouping as a geometric constraint. Same labels or broad object classes do not authorize one template for visibly different instances. Prefer genuine vector paths or local source traces, preserving source samples and uncertainty; tracing colors alone does not establish part ownership.
5. Retain editable text separately. Split semantic parts before tracing when their independent selection matters. Automatic color layers are not semantic segmentation. Gradients may need several discrete editable fills; disclose this approximation and compare the final result.
6. Qualify the selected backend using a representative component containing the needed curves, compound holes, narrow parts and opacity, then save/reopen/render. A textbox or rectangle smoke test does not qualify layered organic geometry. Follow the existing bounded fallback rule; unsupported curves do not justify replacing them with bars.

## Local mature tracing adapter

```text
python scripts/component_fidelity.py trace reference.png component.svg \
  --crop 120 178 72 95 --colors 16 --node /path/to/existing/node
```

The crop is `[left, top, width, height]` in **source pixels**. It must fit the source, each dimension <=4096 and area <=1 million pixels. The adapter uses pinned ImageTracerJS with an explicit source-derived palette: all observed colors when within the color budget, otherwise existing Pillow RGBA octree quantization without dithering. Sparse grid palette sampling is not used because it can miss narrow rare-colored parts. There is no blur, small-path omission, random reseeding, palette re-averaging or coordinate rounding. Color reduction can still lose features; verify them. It keeps the crop background, including unwanted text if the crop contains text: isolate components properly before use; never claim traced letters are editable text. A prepared alpha asset must have its own recorded extraction provenance. Do not erase pixels automatically based only on “looks like background”.

Outputs are a new SVG plus `.trace.json` containing source hash/size/crop, engine hash/options, path count and explicit unverified semantic/final-artifact status. Existing outputs are refused. SVG generator metadata is removed and primitive opacity is represented as fill/stroke opacity; native-profile preflight rejects unsupported content. Use the existing [native toolkit](native-toolkit.md) to import these SVG paths as native DrawingML, not as an SVG picture. The color regions need source-grounded grouping/naming for meaningful editing.

For a color-separable **visible silhouette**, add `--selector selector.json` using the selector schema below. This selects source pixels on a fixed white matte, retains every fragment and hole, and traces support with a uniform median source fill. It records recipe/hash, row-major Boolean mask hash, topology and fill in `.trace.json`. No morphology, hole filling, island deletion, inpainting or hidden continuation occurs. Empty or full-crop selections are rejected. This is a silhouette candidate, not a gradient reconstruction. Foreground letters/objects may create mask holes; diagnose them rather than silently filling them or importing traced letters. Inspect the mask and path count; if it cannot be grouped into meaningful editable components, do not promote it to a finished illustration. Source-frozen selection provides traceability, not semantic proof.

No model, GPU, network, OCR or package installation is invoked. Node is an explicit existing local runtime, required only for these optional tools. Unsupported high-complexity/noisy crops fail the bounded native profile; do not silently increase limits or discard paths. Even below the hard limit, noisy screenshots may produce hundreds of fragments, and independently fitted adjacent color boundaries may show seams. Such SVGs are extraction candidates, not practically editable finished illustrations. Inspect path count, shared boundaries and logical part grouping before using them; simplify/rebuild from source evidence or disclose a permitted exception. Do not hide seams by arbitrary thick strokes that close genuine gaps.

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
