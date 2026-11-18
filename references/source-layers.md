# Continuous coverage and foreground layers

Use `extract.method:closed_form` in the existing [source-assembly](source-assembly.md)
entrypoint for an opaque sRGB component with observed foreground/background
ownership. [Source marks](source-assembly.md#1-acquire-object-support-before-fixing-its-crop)
use original pixel coordinates. Existing alpha uses preserve-alpha; binary-only
work does not need this operation.

## Shared alpha and ownership

Hard foreground/background fixes alpha to 1/0; all other pixels are unknown
coverage, not segmentation probabilities. The opaque foreground assumption needs
source review. Neither alpha nor color estimation reconstructs hidden anatomy.

`matting.epsilon` is 1e-9..0.01. `solver` is `cg` (default, with
`max_iterations` 1..5000) or `direct` (without that parameter).
The installed extraction Python needs SciPy. The same 3x3 closed-form color
Laplacian solves unknown pixels, with a 250,000-pixel context limit. Missing
dependencies and solver failures are explicit, with no automatic fallback.
Convergence, clipping and output quantization are separate diagnostics.

Choose one color route below. Prepare/build/review remain the common production
entrypoint; do not create an alternate component inventory or renderer.

## Observed background inverse: unchanged default

Required `matting.background_patches`: 1..32 source integer boxes of exposed
background, excluding labels/objects/hidden guesses. `background_tolerance`
is the maximum sample error in 8-bit RGB codes, 0..32, chosen before fitting.
No `background_model` means the existing constant-median calculation.

Optional `background_model` has exactly `kind:"affine"`, a nonempty
`observation` and finite `max_condition` in 1..1000000. It fits three
encoded-sRGB planes to 4..32 independent disjoint patches. Full and
leave-one-patch-out patch-center designs must be full rank and meet the condition
bound; all sampled pixels and hard background witnesses must meet the fixed
color tolerance. Patch corners enclose the whole context, including outside
samples when needed. Foreground, reserved content and occlusion overlap reject
a patch. No extrapolation, outlier removal or automatic model switch.

The shared `raster_components.unmix_background` inverse estimates straight RGB.
For unknown coverage it may increase inferred alpha to the RGB-feasible lower
bound, then rounds coverage upward; the adjustment map and metrics disclose this.
Affine receipts retain coefficients, condition, full/held-out residuals and field
hash. These are feasible estimates, not uniquely recovered physical layers.
Nonlinear/textured backgrounds can fail this declared model; do not relax its
tolerance to absorb another object. Old recipes and seven-PNG bundles are unchanged.

## Fixed-alpha joint colors: explicit nonuniform-background candidate

Select `matting.foreground_estimation` instead of `background_patches`,
`background_tolerance` and `background_model`; combining routes is rejected.
The existing alpha solve runs first, is rounded once to RGB8 coverage, and is
then immutable during the color stage. Hard foreground/background observations
are mandatory; every alpha=1 foreground and alpha=0 background color remains
anchored to observed RGB, including unmarked opaque pixels.

All settings are explicit. This example is a starting schedule, not a universal
accuracy threshold:

```json
{"epsilon":1e-7,"solver":"direct","foreground_estimation":{
  "kind":"multilevel_joint_fb","regularization":0.00001,
  "gradient_weight":1.0,"small_size":32,
  "small_iterations":30,"large_iterations":8
}}
```

`regularization` is positive finite; `gradient_weight` nonnegative finite.
`small_size` is an integer 1..128; both iteration counts are integers 1..100.
`joint_foreground.py` adapts PyMatting's multilevel local 2x2 color update to
synchronous NumPy operations, with explicit opaque anchors. It jointly estimates
spatially varying F/B, projects colors into the RGB cube and records each scale's
iterations, final update magnitude, projection count and recomposition errors.
It needs no additional model, Numba, download or remote service.

Completing the fixed schedule is **not convergence certification or visual
approval**. Inspect the residual and white/dark/actual-background comparisons;
recomposition alone cannot establish correct F or alpha. Wrong alpha, similar
foreground/background and texture remain ambiguous. This route neither expands
alpha to hide color errors nor repairs missing branches. It estimates background
behind the component, which is distinct from synthesizing foreground anatomy.

## Optional smooth-field occlusions

`occlusions` explicitly authorizes low-frequency color interpolation under
observed overprinting. Each entry has unique `id`, `kind:smooth_field`,
nonempty `authorization` and `marks` using the source stroke/polygon syntax with
`label:occluder`. Marks cannot overlap hard ownership, another occluder or the
outer two context pixels. All entries are interpolated jointly by the existing
13-point biharmonic SciPy solve; order cannot change the result. Only marked
pixels change, bounded by observed channel ranges; residual and clamping are
recorded. They remain unknown to the matte solver, not zero-alpha holes.

This never authorizes filling cell organelles, experimental curves or scientific
content. Keep native text/relations in their own source inventory; retained rims
or insufficient observations remain review issues.

## One versioned bundle and existing consumers

The source/plan-bound candidate contains `trimap`, binary `context_mask`,
continuous `alpha`, straight `rgba`, `occlusion_mask`,
`coverage_adjustment` and `reconstructed_color`, plus solver/uncertainty
evidence. Reservations are measured, never silently erased.
`hidden_content_generated` describes authorized smooth foreground interpolation.

The explicit joint-color route adds `bundle_version:3`,
`estimated_background.png` and `recomposition_residual.png` (nine PNGs total).
F is stored in RGBA; B and residual are quantized RGB8, not float truth.
`background_estimated:true` and the unobserved-background count disclose
inference. The reader validates recipe/version, every file hash, unchanged
coverage-adjustment, opaque anchors and recomputed quantized residual metrics.
Old bundles retain their exact seven-file contract.

All consumers use `read_layer_bundle`: native palette tracing, continuous
[field fitting](source-fields.md), and approved
[`preparation.method:source-layer`](hybrid-component-schema.md).
Prepare freezes every declared companion and build rechecks it. Do not invent
straight-RGB provenance or reclassify inferred alpha as supplied transparency.
Palette paths approximate continuous color/alpha; `palette_stack` rejects
partial alpha. Inspect the final saved/reopened PPTX and declared editing units.

