# Source-object extraction and scene assembly

Use for context-sensitive crops or multi-object source reconstruction. The
production entrypoint connects existing extraction, tracing, scene and audit
operations. Read the selected operation here, not the upstream research on every
redraw. Source identity/part observations require visual reasoning; code handles
the repeated mechanics. This is not automatic scientific image recognition.

## Production entrypoint

For a new faithful native PPTX from a raster reference, use
`scripts/reconstruction_pipeline.py` rather than a new per-image assembly script.
Keep **one** [visual manifest](visual-manifest.md): observe modules, visible editing
units, text and relationships from the source before authoring. Do not derive the
required inventory from a candidate's shape/text list. Simple primitives need no
segmentation; organic components need source-supported geometry, not a generic
protein/cell template. Quantitative series keep their curve contract.

The adapter supports native text, rectangles, observed solid SVG, source-color
tracing and canonical native component trees/Paint on one source-pixel canvas.
PDF source extraction, approved hybrid objects, existing-deck editing and other
targets retain their feature-specific APIs; they are not silently converted to
this subset. Do not switch a qualified backend midway merely to use this CLI.

```text
python scripts/reconstruction_pipeline.py doctor manifest.json --node /path/to/node
python scripts/reconstruction_pipeline.py prepare manifest.json prepared --node /path/to/node
python scripts/reconstruction_pipeline.py build prepared build-v1 --review reviewed.json --node /path/to/node
```

`doctor` checks the chosen installed runtimes. For extraction in a separate installed
Python, pass `--extract-python /path/to/python` to doctor/prepare. Extraction runs
in that process; do not splice incompatible site-packages into the PPTX runtime.
No dependencies are installed and no source leaves the machine.

`prepare` validates the manifest before export, freezes its bytes and raw source,
and processes every declared item. Traced objects receive a measured support/crop,
original or explicitly estimated foreground RGB, source-context image and `comparison.png` (source left, candidate
right in the **same context frame**). Supplied SVGs are copied and checked by the
existing importer. Failure preserves diagnostics but produces no prepared receipt.

Inspect the component comparisons and source; use `review-template.json` to record
the actual observations in a separate `reviewed.json`. Set `accepted: true` only
for reviewed supports and retain a meaningful note, including disclosed issues.
The binding hashes detect stale files, not dishonest review or scientific errors.
The agent performs this review; it need not ask the user at each component unless
an ambiguity changes the requested scope. A rejected mask needs corrected source
observations under the normal bounded correction rule, not filled gaps or erasure.

`build` requires this preparation and the exact support review, traces source paint
through the existing engine, uses measured source bounds, assembles editable groups
and native text, saves/reopens the PPTX, resolves actual output IDs and invokes the
existing quality runner. The filename is the manifest target's basename inside a
new build directory. Source inventory is unchanged; `resolved-manifest.json` adds
output bindings only. `build-receipt.json` and `quality-report.json` distinguish
candidate creation, pending checks and visual/editor review. **CANDIDATE is not
delivery approval**, and unperformed render checks remain unverified.

Render the saved artifact and perform applicable source comparison/editor review
under [quality-runner](quality-runner.md); the CLI does not start a renderer or
certify an image. Correct source recipes in the canonical manifest and prepare a
new revision; rebuilding never opens an old PPTX or appends fixes. Existing
directories are refused. An over-budget trace keeps its failure evidence and no
partial deck is emitted. No raster fallback, ignored-item route or arbitrary
callback is accepted by this adapter.

### Executable recipe fields

The optional manifest `construction` extension is validated by the existing
manifest validator. Its top level is `{"version":1,"slide_width_inches":12}`.
Version 1 remains the binary/native compatibility contract. Use `version:2` when
selecting `closed_form` source layers below; other routes retain their behavior.
`source.sha256` is required; `canvas` dimensions equal the original raster pixels.
The slide preserves that aspect ratio. Other feature schemas remain applicable.

Each `source_inventory` item adds `construction` with `kind`, nonempty source
`observation`, and the route fields below. Keep its existing ID, module, role, bbox,
representation and exact text; do not repeat these in a second scene inventory.

| kind | Route fields | Existing implementation |
|---|---|---|
| `text` | `options`: measured `font_size_px`; optional `font`, `bold`, `color`, `align` | `text_draw`; text comes from the item's `text` |
| `rectangle` | `options`: optional `fill`, `stroke`, positive `stroke_pt` | `rectangle_draw`; only observed rectangular shapes/decorations |
| `svg` | `asset`: source-derived `path`, `sha256` | `read_vectors` + `svg_draw`; restricted native SVG, no pictures or outlined labels |
| `trace` | `extract`: method/observations below; `trace`: `colors`, `representation`, `max_native_paths`, `max_native_commands` | `extract_source_object` + `trace_component` + `svg_draw` |
| `native_component` | No extra route fields; the item's ID/output_name references its unique canonical `native_components` entry | `manifest_component_draw` + existing manifest Paint preflight/emitter |

For `trace`, the inventory bbox is the **context**. `extract` contains `method`,
`foreground`, `background`, `reserved_regions`, `selector` only for the selector
method, and optional `annotations` for GrabCut or closed-form layers. Layer-only
`matting`/`occlusions` are defined below. The driver derives source hash/context/observation once and feeds
the exact extraction API below. `trace` uses the existing source-paint modes and
budgets in [source-tracing](source-tracing.md); no numeric default is imposed.
The measured output crop feeds both tracing and placement, not the context box.

For `native_component`, read [native-component-schema](native-component-schema.md)
and its selected Paint operation. Keep geometry, source samples and part ordering
in that existing tree, not inside a second recipe asset. All declared trees must
use this route. Build rechecks source-sampled Paint against the frozen source and
uses the same scene mapping as text/paths. Continuous Paint must match an observed
supported profile; this route does not infer a gradient or unmix boundary colors.

Optional shared recipe fields are `parent`, `behind`, integer `z`, and
`container:true`, with the scene semantics below. Connector items use `kind:svg`,
`connection` referencing the existing connection ID and `endpoints:[item1,item2]`.
These exact item endpoints must belong to the connection's source/target modules;
module IDs are not substituted for actual connected shapes. Include observed
arrowheads/inhibition marks in the SVG, never infer a diagonal from its rectangle.
Every connection and inventory item must be emitted once. One source item maps to
one top-level native editing unit; internal color paths are editable but do not
claim automatic organelle identification or drag-bound connector behavior.

For executable syntax with a small synthetic source, see
[the end-to-end regression fixture](../tests/test_reconstruction_pipeline.py).
Use its schema shape, not its source coordinates or edit budgets on a real figure.

## 1. Acquire object support before fixing its crop

`source_objects.extract_source_object(source_path, plan)` returns PNG bytes and
measured evidence. The plan uses these required fields plus the conditional fields:

- `source_sha256`, `observation`: original bytes and observed identity/confounders.
- `context_bbox`: integer `[x,y,width,height]` search area in original source pixels,
  including visible background around the **whole** candidate. Not a tight crop.
- `foreground`, `background`: lists of original-source `[x,y]` pixel witnesses.
  At least one positive witness; each disconnected intended fragment needs a
  positive point or a hard foreground annotation.
- `method`: `selector` uses the existing [color selector](source-tracing.md) and
  additionally requires its `selector` object; `grabcut` requires installed OpenCV
  and at least one negative witness. No automatic installation or fallback.
- `reserved_regions`: source rectangles for native text/lines/neighboring content.
  Empty only when source inspection found no such content in the context.
- `annotations` (optional, GrabCut or closed-form): observed source marks as defined below.

The selector route reuses `component_geometry.select` and seeded connected support.
GrabCut initializes probable classes from observed seed colors, applies source
annotations before inference, then uses the same installed local algorithm.
Borders are not forced to background: contact remains
visible evidence of a too-small search area. No output-specific crop coordinates,
largest-blob choice, morphology, inpainting or generated anatomy are used.

Use annotations when sparse points miss pale/disconnected detail or neighboring
pixels share the object's colors. Each mark has `kind` (`stroke` or `polygon`),
`label` (`foreground`, `background`, `probable_foreground`, `probable_background`),
source-pixel `points` and a nonempty `observation`. A stroke additionally has odd
positive `width` in source pixels, wholly inside the context. A polygon needs at
least three distinct points. There are at most 1000 marks/points per list, using
the existing bounded observation limit. Mark visible ownership, not hidden shape
completion. Do not turn a reserved text rectangle automatically into background.

Hard foreground/background pixels remain fixed during GrabCut; probable labels
can change. Same-class hard marks dominate probable marks; opposite-class overlap
with any mark/point fails instead of using last-write-wins. Disconnected support
is selected by **all hard foreground pixels**, not just the original points.
Annotations alter the inference inputs, never erase/paint the final mask or RGB.

```json
{"kind":"stroke", "label":"foreground", "points":[[20,30],[35,31]],
 "width":1, "observation":"Synthetic visible pale one-pixel strand"}
```

This is syntax, not coordinates to reuse. Review `annotations.png` alongside
`source-context.png`/`comparison.png`: hard foreground green, hard background red,
probable foreground blue, probable background orange. `initial_labels.png` records
the actual four-class initialization (OpenCV values 0/1/2/3); both are included in
the existing evidence hashes. A wrong observed stroke can still select wrong
pixels; this is a production capability, not automatic recognition.

```text
python scripts/source_objects.py reference.png extraction-plan.json new-candidate
```

The new directory contains `context_mask.png`, cropped `alpha.png`, source-colored
`rgba.png` and `candidate.json`. `source_bbox` is computed from selected support;
one transparent padding pixel is retained where possible. RGB is unchanged,
alpha is binary and inferred, and all outputs remain **CANDIDATE**. Processing
limits reuse the existing image/support limits; this is not a quality score.

Inspect candidate and full source context together, including lobes, holes, thin
details and reservations. Same-color touching glyphs may join an object; the
report measures intersection but never erases it. Revise source observations in
the normal bounded correction pass, using source annotations where ownership is
visible, or retain the unresolved limitation. Do not
approve a mask merely because `issues` is empty. Source-size/context-edge contact
cannot be repaired by hiding border pixels or filling gaps.

After independent visual qualification, use **one** existing route:

- Native color paths: pass `alpha.png` with its hash as the existing
  `component_fidelity.trace_component(..., source_support=..., part_plan=...)`
  support for the measured `source_bbox`; use source paint, not uniform silhouette.
  For adjacent semantic parts use `context_mask.png` with the original context
  bbox and [marked-source partition](source-tracing.md#marked-source-assemblies).
- Explicitly approved picture units: feed cropped `alpha.png` into existing
  `supplied-alpha` [preparation](hybrid-components.md). Extraction does not grant
  hybrid permission. Retain inference and review provenance beside the mask;
  downstream supplied-alpha processing does not turn inference into source truth.

Binary support does not recover soft alpha or foreground edge color. Use the
explicit layer route below when its background/trimap assumptions are supported;
do not blur a binary mask and label it matting. Existing alpha uses preserve-alpha
preparation. Source comparison remains against the untouched original.

### Continuous coverage and foreground layers (construction version 2)

Select `extract.method: closed_form` for a bounded, opaque sRGB source component
with independently observed foreground/background marks and an approximately
constant, visible background. Hard marks still fix foreground=1/background=0;
probable and unmarked pixels are **unknown coverage**, not segmentation
probabilities. An opaque foreground witness is an assumption that must be reviewed.
Do not force a glow/cell cross-fade into two independently recovered objects when
neither backdrop nor hidden surface is identifiable.

Required `matting` fields:

- `background_patches`: 1..32 original-source integer boxes sampling the same
  visible background; no labels, objects or hidden-background guesses.
- `background_tolerance`: allowed maximum sample deviation in 8-bit RGB codes,
  0..32, selected from source before the trial. Rejection means this constant
  background model is unsuitable; do not raise it to absorb another object.
- `epsilon`: 1e-9..0.01 local color covariance regularization.
- `solver`: `cg` (default) with required `max_iterations` 1..5000, or `direct`
  without an iteration parameter. Choose based on qualified runtime/size; no
  silent solver fallback. SciPy is required in the selected extraction Python.

`source_layers.py` assembles the closed-form 3x3 color Laplacian and solves only
unknown coverage with fixed foreground/background. Its 250,000-pixel context
limit bounds sparse-matrix work, not fidelity. It separately estimates straight
foreground RGB using the sampled background through the shared
`raster_components.unmix_background` source-over inverse. To remain within the
RGB cube it may increase **inferred** alpha to the color-feasible lower bound;
adjustment maps/statistics disclose this choice. This is one feasible layer,
not uniquely recovered physical alpha or hidden color. Solver convergence is
reported before/after clipping; output quantization/adjustment is separate.

Optional `occlusions` explicitly authorizes interpolation of a smooth field
under observed overprinting. Each entry has unique `id`, `kind:smooth_field`,
nonempty `authorization` and `marks`. Marks use the source stroke/
polygon syntax above but `label:occluder`. They must not overlap hard ownership,
another occluder or the outer two context pixels. All entries are interpolated
jointly by a 13-point biharmonic sparse solve using the already selected SciPy
runtime, so list order cannot change the result. Values are bounded by observed
channel ranges; clamping and the raw residual are recorded. Only annotated pixels
are modified; outside RGB is unchanged.
The repaired pixels remain unknown to the matte solver, **not zero-alpha holes**.

This operation infers low-frequency color behind labels, never cell organelles,
experimental curves or missing scientific content. Record the authorization and
mask; native text/relations still require their own original-source inventory.
Interpolation is not exact-source observation, and retained overprint rims or
insufficient neighbors require disclosure/rejection under the existing review.

The candidate retains the full context coordinate domain and binds `plan`,
`trimap`, binary `context_mask` (any represented coverage), continuous `alpha`,
straight `rgba`, `occlusion_mask`, `coverage_adjustment`, `reconstructed_color`,
solver/inverse results and source hashes. `reserved_regions` is still measured,
not silently erased. A layer has `hidden_content_generated:true` when smooth
occlusions were inferred; otherwise false. These fields are not a quality score.

Prepare/build uses the **same** review protocol and checks all bundle bytes.
Tracing consumes the authoritative candidate receipt, not caller-invented RGB
provenance. Use `palette_edges` or explicitly selected `smooth`; `palette_stack`
rejects partial alpha. This native path route approximates color/alpha through
the existing palette budget, not continuous native Paint. Review light, dark and
actual backgrounds, the final saved/reopened PPTX and practical editing scope.
An optional dependency missing in the extraction Python is an explicit failure,
never permission to install packages or flatten transparency.

## 2. Assemble once in a shared source frame

`reconstruction_scene` owns placement and back-to-front order. Keep content in the
existing canonical manifest/builder: derive nodes from its IDs and observations,
not a parallel hand-maintained inventory. A node contains `id`, source `bbox`,
`draw`, `role` (`component`, `text`, `container`, `relation`), optional `parent`,
`behind`, integer `z` and `relation` endpoints. See the executable API example below.

`SourceFrame(source_region, target_viewport)` maps original pixels uniformly into
inches; it preserves source origin/aspect ratio and centers any unused viewport
space. `text_draw` scales measured pixel font sizes with the same frame. Do not
replace source contours or source-specific parts with the example rectangle.

`parent` is specifically a **container background**: it must geometrically contain
the child and is painted first regardless of declaration order. It does not mean
anatomical parentage or clipping. Arbitrary visible occlusion uses `behind` IDs;
existing native part trees still own internal grouping and Paint. Dependencies
override `z`; unrelated ties preserve input order. Cycles and missing IDs fail
before drawing rather than choosing a visually convenient order.

```python
from reconstruction_scene import (SourceFrame, SceneNode, ReconstructionScene,
    assemble_pptx, rectangle_draw, text_draw, svg_draw)

frame = SourceFrame((0, 0, 800, 600), (0, 0, 10, 7.5))
nodes = [
    SceneNode('observed-object', (100, 130, 80, 60),
              svg_draw(object_svg, expected_sha256=object_svg_sha256),
              parent='panel'),
    SceneNode('label', (100, 100, 100, 24),
              text_draw('Label', font_size_px=18),
              role='text', parent='panel'),
    SceneNode('panel', (80, 80, 160, 150),
              rectangle_draw(fill='F3F7F2'), role='container'),
]
receipt = assemble_pptx(empty_slide, ReconstructionScene(frame, nodes))
```

The example coordinates are synthetic syntax, not a reusable scientific layout.
Production nested/source-sampled Paint uses `manifest_component_draw`, which calls
the existing manifest preflight/emitter; its output name must match the scene ID.
Other already-qualified target adapters may consume `scene.ordered()` and
`frame.place()` without changing backend. Python callbacks take `(slide, bounds,
identity, source_scale)` and emit exactly one top-level editable shape/group. The adapter checks
actual IDs/names, but does not certify arbitrary callback contents.

Freeform relationships use source-observed SVG geometry with `role='relation'`
and `relation=(source_id,target_id)`. Existing native SVG import preserves curve
controls; put observed arrowhead/inhibition geometry in that same source component.
This is not automatic raster line recognition or drag-bound rerouting. Rectangular
bound connectors still use [native-toolkit](native-toolkit.md#rectangular-connections).
Never derive a scientific bend from a box diagonal or invent its endpoints.

Assemble on a new empty disposable slide. If a callback fails, discard that failed
deck; do not save it as a successful partial export. No existing slide is rewritten.
The receipt contains actual shape IDs, paint order, placements and relations from
the same scene; use it to resolve manifest output bindings after reopen. Source
inventory still determines whether anything was omitted, and source review still
determines whether endpoint identities are correct. `visual_review` remains
`NOT_PERFORMED` until separately documented actual-render inspection. Do not run a
second independent renderer merely to manufacture an extra PASS.
