# Hybrid component manifest schema

Read for explicitly approved independent picture components. This extends the [visual manifest](visual-manifest.md); [hybrid-components](hybrid-components.md) owns construction and replacement procedures.

## Hybrid component contract (single authority)

Set `editing_policy: "hybrid"` and nonempty `hybrid_authorization` quoting the user's
accepted editing scope. Omission means the existing `native` policy, including its
legacy evidence exceptions. Keep faithful/semantic/redesign unchanged. Hybrid needs
`component_assets`, `component_instances`, a complete `source_inventory`, and at
least standard profile.

Each asset has:

- `asset_id`: unique reusable identity; `path`: manifest-relative local file;
  `sha256`: lowercase hash of the exact approved bytes.
- `source_kind`: `local`, `licensed`, `source_crop`, or `generated`; `origin` and
  `authorization`: actual provenance and permitted use, not invented credentials.
- `editing_unit`: independent semantic object. `extent: "object"` means
  move/scale/replace only. `content_class`: `illustration` or `evidence`.
  `contains_native_required: false` must follow inspection that the asset does not
  flatten text, quantitative marks, legends or cross-component relationships.
  A whole panel/reference/arbitrary tile is not an independent component.
- `requires_alpha`: explicit boolean; `min_visible_pixels`: minimum visible width
  AND height; `min_dpi`: minimum resolution at final physical placement. Select
  task-appropriate limits before construction, not after a failed check.
- `invariants`: nonempty source/approval-grounded descriptions of required
  projection, gaps, terminals, branch counts and uncertainty.
- `comparison`: `source_exact` for original/local/licensed assets; generated assets
  use `approved_surrogate` and cannot claim original pixels or experimental data.
- Licensed assets also require `license` and `attribution`. Source crops require
  original `source_sha256` and source-pixel `source_bbox: [x,y,w,h]`.

For executable local source-crop preparation, add one optional `preparation` object:

- `method: "preserve-alpha"` and nonempty `authorization`: preserve the given
  crop's RGBA, including real holes and partial alpha, without trimming/resampling.
- `method: "supplied-alpha"`, `authorization`, `alpha_path`, `alpha_sha256`, and
  `rgb_mode: "straight"` or `"matted"`: use a provided crop-sized 8-bit L alpha
  image, not a predicted mask. `matted` additionally requires known `matte_rgb`
  as three 0..255 integers; no other preparation fields are allowed.

Preparation requires an integer source-pixel crop, exact source size/hash and
single-frame RGB/RGBA source with normalized orientation and no unqualified ICC.
Supplied alpha requires opaque source pixels (no double alpha). The matted route
inverts encoded-channel `C = alpha*F + (1-alpha)*B`, tolerating only source 8-bit
rounding; it does not infer the compositing color space. Qualify that convention
before use. Low alpha amplifies quantization and cannot recover exact lost RGB.
The planned asset may omit its target `sha256` only while invoking preparation;
the returned candidate and all ordinary validation require the computed hash.
The ordinary package audit re-executes this recipe and compares RGBA pixels as
well as embedded bytes. Neither given alpha nor reproducibility proves correct
object boundaries. Processing/preview limits and commands live in
[hybrid-components.md](hybrid-components.md).

Generated assets additionally have a `generation` record:

- `provider: "builtin_imagegen"`, `authorization`, `subject`, `style`, actual
  `prompt`, and nonempty `invariants`.
- `attempt`: 1 or 2 within the existing construction/correction budget; attempt 2
  needs `correction_reason`. Only `status: "succeeded"` enters the asset list.
- `references`: explicit list, `[]` for text-only generation. Every transmitted
  image records `path`, `sha256`, `role` (`structure`, `style`, `edit_target`),
  `transmitted_scope` and its own upload `authorization`. A transmitted crop's hash
  identifies the actual crop, not the untransmitted whole source.
- Returned model version, seed or request ID stays null or absent when unavailable.
  Never fabricate reproducibility parameters.

Each instance has:

- unique `instance_id`, known `asset_id`, one-based `slide`, exact unique
  `output_name`; one p:pic per instance, reusable assets can have many instances.
- `bbox_inches: [left,top,width,height]`: planned slide-space axis-aligned bounds
  after rotation/group transforms; `rotation`: effective clockwise degrees.
- `crop: [left,top,right,bottom]`: explicit fractions of the source image, usually
  `[0,0,0,0]`; each nonnegative and opposite sums below 1. Preserve visible content
  and aspect. This verifier does not certify crops that remove alpha-visible pixels.
- `placement_tolerance_inches`: 0..0.05, chosen before authoring; not a scientific
  fidelity or font tolerance.
- `anchors`: explicit list including `[]`. Each has unique `id`, `uv: [u,v]`
  normalized to the full original asset canvas, and independently planned
  `expected_inches: [x,y]` in slide space. Actual crop/group transforms are applied.
  Static agreement does not prove interactive connector following.

A raster inventory item uses `representation: "component_raster"` and a known
`component_instance`; each instance maps to exactly one inventory item. Text,
chart, table and connector roles, plus `native_required: true`, cannot use it.
Hybrid native items require exact `output_name` and optional one-based
`output_slide`/`required_count`. Coverage is checked against the actual package.

`scripts/component_assets.py` implements this extension for the existing validator,
PPTX audit and quality runner. Schema validation does not read assets; package audit
compares actual local/embedded hashes, media integrity, geometry and coverage.
Neither is a semantic segmentation engine or authenticated provenance. False
origin/role assertions cannot be detected reliably from hashes; source/render
review remains mandatory.
