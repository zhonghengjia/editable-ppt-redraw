# Regional source/render validation

Read before declaring sensitive-region comparison contracts. Source geometry planning is in [component-fidelity](component-fidelity.md); runtime dispatch is in [quality-runner](quality-runner.md).

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
