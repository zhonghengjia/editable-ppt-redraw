# Source smooth fields to native Paint

Use for an observed smooth color field on **already source-grounded geometry**.
This operation fits color, not anatomy, segmentation or hidden layers. It reuses
[native Paint](native-paint.md) and the [production entrypoint](source-assembly.md).
Do not route continuous tones through a palette merely because `smooth` tracing
fits curved outlines. Hard/discrete regions retain their existing trace route.

## Production recipe

Use construction version 3, `kind: native_component`, and its existing canonical
part tree. Add one optional `field_fit` to that item's construction:

```json
{"part_id":"surface", "support":{"path":"support.png","sha256":"<source support hash>"},
 "model":"linear", "semantics":"visible_composite", "stop_count":"auto",
 "max_error":0.025, "angle":37}
```

Values above illustrate syntax, not defaults or coordinates to copy. Fields:

- `part_id`: one existing leaf or group owning fill. Geometry and ordering stay
  in `native_components`, not duplicated here. Group paint needs inheriting leaves.
- `support`: source-observed binary 0/255 grayscale PNG, exactly the item's crop
  size, with path/hash. It selects fitting evidence, **not** final QA pixels.
  Keep its original extraction/observation evidence. Review contour/holes separately.
- `model`: preselect `solid`, `linear` or `radial` from source observations. No
  automatic family switching, layer insertion or budget escalation on failure.
- `semantics`: `visible_composite` preserves opaque observed scene colors; it
  does not separate foreground/background. `source_rgba` preserves original alpha.
  `estimated_layer` requires `source_layer:{path,sha256}` bound to an existing
  [closed-form layer receipt](source-layers.md).
  It retains estimated coverage/foreground and occlusion provenance, not original
  transparent truth. The layer source hash and full-context bbox must match this item.
  Never call opaque RGB an independently recovered transparent layer.
- `stop_count`: a fixed integer 4..16, or `"auto"` for a predeclared bounded search
  over 4..16 (solid emits one color). Prefer auto when the source does not establish
  a specific count. Uniform grids are **not nested**: more stops need not fit better.
  Auto selects the fewest total stops meeting the original full-pixel error limit,
  with a deterministic tie-break; it changes neither family, support nor tolerance.
  Four or more avoid Office's special two/three-stop RGB interpolation.
- `max_error`: 0..32/255, fixed per-channel maximum error for premultiplied RGB
  and alpha. Select for the task before fitting; this is not a whole-image score.
- `angle`: optional for linear; degrees clockwise in original physical source
  coordinates. Omission estimates direction with bounded search. `radial` is
  centered on actual geometry bounds, not an inferred arbitrary ellipse/center.
- `radius`: radial only, optional source-pixel radius inside the owner's
  circumscribed circle. Outside it the final stop is constant. Default is that circle.
- `alpha_profile`: optional independent alpha model, with `model`, `stop_count`
  and optional `angle`/`radius` under the same definitions above. Only for RGBA or
  estimated layers. Omission keeps the single shared-coordinate Paint; specifying
  it fits opaque color Paint plus a white native alpha mask in its own coordinate
  system, applied once. A group owner must own **every** painted descendant;
  otherwise put the affected surface in its own source-grounded group/leaf.

The crop uses integer source pixels, at most 250,000. Viewbox-to-source mapping
must be uniform. Actual analytic geometry bounds own paint; crop/viewbox padding
cannot rebase the gradient. Stroked owners and pre-existing alpha effects on
owners, ancestors or inheriting consumers are rejected rather than double-composited.
Reuse the existing qualified RGB/RGBA reader; resolve ICC/EXIF before fitting.
Keep text/overprints outside
the fitting support, but inventory and reconstruct them separately.

`prepare` freezes raw source, support, recipe and any bound layer bundle (receipt
plus every bound companion PNG), then writes `candidate.json`
with the computed ordinary component and `predicted-field.png`. Inspect against
the original source, then use the existing review file. `build` recomputes from
frozen inputs before accepting the receipt, emits through the existing serializer,
and records the fitted component in the resolved manifest. It never calls tracing
for this item. Computed stops carry fitting evidence, not false `source_samples`.

## Fitting and evidence

`source_fields.fit_surface` returns `(paint, compositing, evidence, preview)`;
the single-Paint compatibility API `fit_field` rejects independent alpha rather
than silently discarding its mask. Both use at most 4096 deterministic fit samples and check
**every** owned pixel. Bounded least squares fits alpha then RGB against observed
premultiplied color. Final residuals use separately interpolated, Office-quantized
RGB and alpha, not linear interpolation of premultiplied endpoint colors. A zero
alpha pixel's irrelevant RGB cannot affect the fit. Direction estimation uses
position-covariance-normalized slopes and fixed coarse/refinement searches.

Only observable spline columns are solved. Knots wholly outside the owned support
use nearest observed endpoint values; unobserved gaps use coefficient interpolation.
These extensions are disclosed, **not inferred hidden content**. Circular supports
need not reach the outside of Office's circumscribed circle. A rank-deficient
observed basis still fails; support and fixed error tolerance are never changed.

Independent profiles reuse that solver: color is weighted by real coverage, alpha
uses its own direction/radius, and final acceptance evaluates composed, quantized
premultiplied RGBA on every owned pixel. Separate small channel costs do not prove
the composite passes. Auto considers pairs in increasing total stop count and
caches each profile/count solve once (at most 26 fits, not 169 fits). Color and
alpha can select different counts. A fixed integer remains fixed. No passing pair
means an explicit failure, not budget escalation or a switch to pictures.
Production reads original pixels or the fully hash-bound
`read_layer_bundle` result; arbitrary external PNGs cannot claim estimated-layer
provenance. The same original source remains the visual reference.
Unknown-background unmixing, off-center/elliptical fields, arbitrary
multilayer decomposition and high-frequency detail are outside this operation.
Insufficient evidence or excessive residual fails with no successful candidate.

Machine fit proves only sampled field representation. Save/reopen/render under
the existing appearance contract; check relevant gradients, light/dark backgrounds
for real RGBA, and actual editing units. Visible-composite colors are qualified
only in the original scene, not when independently moved onto another background.
No universal cell, organelle, biological ownership or final-quality claim follows.

Executable examples: [single profiles](../tests/test_source_fields.py) and
[independent profiles, layer binding and batch assembly](../tests/test_surface_fields.py).
