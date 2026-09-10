# Source-bound appearance contract

This is the single authority for appearance planning, source-color construction,
generation binding and scoped appearance evidence. It applies across scientific objects, devices, maps and other
illustrations, whether native or approved hybrid. Geometry, source inventory,
curves, text and host-surface requirements retain their existing independent gates.

## Plan before choosing a representation

Inspect actual source pixels at composition and detail scale. Record semantic
colors separately from shading. Identify observable within-part tone differences,
contour treatment, local overlap, transparency and intentionally flat regions.
Mark each relevant inventory item `appearance_sensitive: true`. Hybrid components
require this contract even when their geometry looks simple. Do not infer a fixed
layer count, dark foreground, bright background, lighting direction, cylindrical
pattern or hidden anatomy. A brighter foreground and a flat source are valid.

For each requirement, write an independently observed source fact and a checkable
criterion before building. Mark ambiguous relations `uncertain`; a plausible
replacement does not resolve them. Scope local crossings to fragments when a
whole-object front/back order cannot express the visible relation. Do not invent
a global depth graph for objects that cross in both directions.

Select native solid fills for source-flat parts. For visible continuous tones,
construct source-supported Paint with the [native toolkit](native-toolkit.md),
keeping the part tree and geometry fixed while colors are assigned. Discrete color
regions remain a separate representation choice; quantization is an approximation,
not preservation of a continuous gradient. A prompt requirement alone does not
produce native shading or enforce a part relationship.
If an approved picture component is needed, carry the same observations into
generation, placement and review. Do not change a failed exact-source comparison
into a surrogate comparison, raise tolerances or move sample regions after seeing
the output merely to clear the gate. A changed contract needs an explicit decision
and new generation/readback/review evidence.

## Source observations into executable color

First identify the visible part and choose its contour/local coordinates using
[component-fidelity.md](component-fidelity.md). Then decide the fill type and
direction from the source. Keep semantic color variation separate from illumination;
do not apply the same light direction, cell template or depth order to every object.

`appearance_fidelity.sample_paint(source_path, recipe)` reads independently chosen
source patches into actual `native_paint` colors. It does not edit the source or
create an image. Example syntax (coordinates are illustrative, not defaults):

```python
fill = sample_paint(source_path, {
    "source_sha256": source_hash,
    "kind": "linear", "angle": 90,
    "positions": [0, 0.5, 1],
    "patches": [[110, 110, 8, 8], [110, 140, 8, 8], [110, 170, 8, 8]]
})
manifest["native_components"][0]["parts"][0]["fill"] = fill
```

Solid sampling uses one patch and omits positions/angle/focus. Path sampling uses
`focus` instead of angle. Select patches inside the visible part, away from labels,
occluders and boundary mixing. Positions/direction/focus are supplied decisions,
not an automatic shading fit. The helper reads channel medians with NumPy rounding
and returns native Paint plus `source_samples: {sha256,size,patches}`. Keep this
returned value in the same manifest; do not maintain an independent color ledger.

The sampling profile reads opaque sRGB patches only (at most 32, each at most one
million pixels, source at most 50 million pixels). It rejects nonopaque pixels,
unqualified ICC profiles, out-of-bounds samples and source-hash changes. It cannot
unmix a foreground from an already opaque background, infer alpha or reconstruct
occluded colors. It estimates colors, not physically calibrated reflectance or
lighting. Existing matting is a separately authorized optional route, not a silent
fallback. Manually chosen colors require source/approval evidence in part observations
and must not be mislabeled as sampled colors.

`native_components.add_manifest_component` re-reads declared patches and refuses
stale or manually altered sampled colors before output. Changing a source-bound
paint means changing its canonical source recipe with a justified observation and
regenerating, not overwriting stops to pass a comparison. This association check is
not full-image fidelity: final rendering can interpolate or antialias differently.

## Manifest evidence fields

`appearance_fidelity` is an optional schema-1 extension, required for new hybrid
work or inventory marked appearance-sensitive. Existing native manifests without
these declarations keep their previous machine checks. Legacy hybrid manifests
without it remain parseable but the runner reports appearance NOT_VERIFIED.

```json
{
  "appearance_fidelity": {
    "source_sha256": "<SHA-256 of original source bytes>",
    "source_size": [800, 600],
    "color_space": "srgb",
    "matte": [255, 255, 255],
    "items": [{
      "id": "source-object-01",
      "source_bbox": [100, 100, 160, 140],
      "comparison": "source_exact",
      "requirements": [{
        "id": "observed-tone-contrast",
        "dimension": "tone",
        "observation": "The left visible patch is darker than the right patch",
        "certainty": "observed",
        "criterion": "Preserve the source signed contrast at delivered size",
        "measurement": {
          "kind": "luma_delta",
          "samples": [[110, 110, 12, 12], [210, 110, 12, 12]],
          "tolerance": 0.05,
          "min_pixels": 100
        }
      }]
    }]
  }
}
```

The numbers above illustrate syntax, not recommended universal thresholds. Freeze
sampling and tolerance using source resolution and the requested fidelity. Do not
use a single probe to claim complete object coverage.

- `items`: 1..100, unique IDs from `source_inventory`; cover all marked items and
  all `component_raster` inventory when the contract is present.
- `source_bbox` and sample boxes: integer source pixels `[x,y,width,height]`,
  positive, within their parent, at most 4096 pixels per side and 1 million pixels
  per box. Source hash/size must agree with `regional_fidelity` when both exist.
- `comparison`: `source_exact` or `invariants`. Invariants requires nonempty
  `authorization` recording user-approved illustrative/layout substitution, not
  an automated escape from a failed reconstruction.
- `requirements`: 1..30 per item, unique local `id`, nonempty `observation` and
  `criterion`, `certainty` of `observed` or `uncertain`.
- `dimension`: `semantic_color`, `tone`, `contour`, `occlusion`, `transparency` or
  `flat`. Declare all relevant distinctions; automation cannot discover omitted
  requirements. Contour geometry still uses the existing structural contract.
- Occlusion requires `scope`: `native`, `mixed` or `raster_internal`. Native/mixed
  requires `paint_order: {"front_name":"...","back_name":"...","slide":1}`.
  Use exact distinct output names for individually emitted parts, not group names.
  The current profile reads slide 1 only. Raster-internal relations cannot declare
  native paint order. Unsupported target/object geometry remains NOT_VERIFIED.
- Optional `measurement` is limited to faithful `source_exact` work. `rgb_median`
  supports semantic color using one patch; `luma_delta` supports tone using two;
  `luma_spread` supports tone/flat using one. Tolerance is finite in `[0,1)` and
  `min_pixels` a positive integer. Too-small samples remain NOT_VERIFIED.
- Fields in this extension are strict: misspelled/unknown fields fail validation.

Measurements compare source and final render after the existing whole-canvas
size-only registration, never output-fitting, cropping or elastic registration.
RGB median compares normalized channel medians. Luma is Pillow's display grayscale
on the declared RGB matte, not physical luminance, CIELAB, Delta E or 3D depth.
Signed luma delta preserves either light-to-dark direction; luma spread compares
the source 90th-minus-10th percentile. Embedded ICC profiles require independently
verified conversion to the declared sRGB profile before numeric checking. Current
probes do not implement color management. Missing NumPy/Pillow stays unverified.
Keep original sources immutable and retain conversion provenance where applicable.

## One generation binding

Prepare an unbound base request under [hybrid-components.md](hybrid-components.md).
Use `appearance_fidelity.bind_generation(request, manifest, item_ids)` to derive
the prompt requirements and `appearance_binding` from this same contract. It
accepts authorized `invariants` items, never exact-source generation claims.
Then run `component_assets.generation_preflight(request, manifest=manifest,
tool_available=...)` before the real tool call. This records no remote call itself.

The binding holds `item_ids` and the canonical JSON `contract_sha256`. Validation
requires the current requirements at the prompt end, and asset validation checks
that IDs exactly match that generated asset's inventory. Rebuild a changed request
from its unbound base instead of appending corrections to an already bound prompt.
Binding catches drift and omitted requirements, not a model's understanding or
compliance. Permissions, references and the shared two-attempt budget still apply.

## Final-artifact evidence and decision

Use the existing `--render-evidence` file, with `slide: 1`, source/final-file/render
hashes and renderer assertion under [component-fidelity.md](component-fidelity.md).
Do not create a second competing artifact ledger. Add `appearance_review`:

```json
{
  "appearance_review": {
    "contract_sha256": "<appearance_fidelity canonical JSON hash>",
    "reviewer": "<who actually inspected the final render>",
    "records": [{
      "item_id": "source-object-01",
      "requirement_id": "observed-tone-contrast",
      "status": "PASS",
      "observation": "<specific finding, not just approved>",
      "views": [
        {"path":"final.png","sha256":"<hash>","scale":"delivered"},
        {"path":"object-detail.png","sha256":"<hash>","scale":"detail"}
      ]
    }]
  }
}
```

Every requirement needs delivered-size and detail evidence. Transparency also
needs `light`, `dark` and `actual` background views. Paths resolve beside the
evidence JSON. Review status is PASS, FAIL or NOT_VERIFIED. Record actual views
and observations; do not relabel a single image as proof of different backgrounds.
Unknown/duplicate records, stale hashes and invalid values fail. Missing evidence,
uncertain source or unsupported scope stays NOT_VERIFIED. Unknown geometry cannot
inherit a color pass. Explicit review rejection cannot be overridden by metrics.

The runner reports measurements, package paint order and reviewer records
separately. Package order does not prove objects overlap, are opaque or look
correct. Image-internal order requires actual visual inspection, not alpha count,
generated layer count or the order of an enclosing picture object. Hashes associate
assertions with files; they do not authenticate the reviewer or scientifically
validate the image. Keep `delivery_ready` null and overall manual visual review
separate. Full scientific-figure fidelity is not certified by these probes.
