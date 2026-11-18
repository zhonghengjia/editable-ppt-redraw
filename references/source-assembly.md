# Source-object extraction and scene assembly

Use for context-sensitive crops or multi-object source reconstruction. The
production entrypoint connects existing extraction, tracing, scene and audit
operations. Read the selected operation here, not the upstream research on every
redraw. Source identity/part observations require visual reasoning; code handles
the repeated mechanics. This is not automatic scientific image recognition.

## Production entrypoint

For a new faithful native or approved hybrid PPTX from a raster reference, use
`scripts/reconstruction_pipeline.py` rather than a new per-image assembly script.
Keep **one** [visual manifest](visual-manifest.md): observe modules, visible editing
units, text and relationships from the source before authoring. Do not derive the
required inventory from a candidate's shape/text list. Simple primitives need no
segmentation; organic components need source-supported geometry, not a generic
protein/cell template. Quantitative series keep their curve contract.

The adapter supports native text, rectangles, observed solid SVG, source-color
tracing, source-fitted/canonical native Paint, approved independent pictures and
qualified rectangular bound links on one source-pixel canvas.
PDF source extraction, existing-deck editing and other
targets retain their feature-specific APIs; they are not silently converted to
this subset. Do not switch a qualified backend midway merely to use this CLI.

```text
python scripts/reconstruction_pipeline.py doctor manifest.json --node /path/to/node
python scripts/reconstruction_pipeline.py prepare manifest.json prepared --node /path/to/node
python scripts/reconstruction_pipeline.py build prepared build-v1 --review reviewed.json --node /path/to/node
```

For uncertain raster-source typography, the optional `measure-text manifest.json
text-measurements` operation uses the same text inventory before preparation.
It produces source-bound advice and inspection crops; see
[text-fidelity](text-fidelity.md#optional-source-measurements) for font selection,
uncertainty and applying measurements. It is not a new required build stage.

`doctor` checks the chosen installed runtimes. For extraction in a separate installed
Python, pass `--extract-python /path/to/python` to doctor/prepare. Extraction runs
in that process; do not splice incompatible site-packages into the PPTX runtime.
No dependencies are installed and no source leaves the machine.

`prepare` validates the manifest before export, freezes its bytes and raw source,
and processes every declared item. Traced objects receive a measured support/crop,
original or explicitly estimated foreground RGB, source-context image and `comparison.png` (source left, candidate
right in the **same context frame**). Supplied SVGs are copied and checked by the
existing importer. Hybrid pictures freeze the canonical approved asset and its
preparation/reference dependencies; their review compares original source and asset.
Source-field fits freeze support and produce a predicted field
and compiled component under [source-fields](source-fields.md). Failure preserves
diagnostics but produces no prepared receipt.

Inspect the component comparisons and source; use `review-template.json` to record
the actual observations in a separate `reviewed.json`. Set `accepted: true` only
for reviewed supports and retain a meaningful note, including disclosed issues.
The binding hashes detect stale files, not dishonest review or scientific errors.
The agent performs this review; it need not ask the user at each component unless
an ambiguity changes the requested scope. A rejected mask needs corrected source
observations under the normal bounded correction rule, not filled gaps or erasure.

`build` requires this preparation and exact candidate review, traces discrete paint
or recomputes continuous fields through the selected operation, assembles editable groups
and native text, saves/reopens the PPTX, resolves actual output IDs and invokes the
existing quality runner. The filename is the manifest target's basename inside a
new build directory. Source inventory is unchanged; `resolved-manifest.json` adds
output bindings and fitted Paint, retaining canonical source recipes. Receipts distinguish
candidate creation, pending checks and visual/editor review. **CANDIDATE is not
delivery approval**, and unperformed render checks remain unverified.

Render the saved artifact and perform applicable source comparison/editor review
under [quality-runner](quality-runner.md); the CLI does not start a renderer or
certify an image. Correct source recipes in the canonical manifest and prepare a
new revision; rebuilding never opens an old PPTX or appends fixes. Existing
directories are refused. An over-budget trace keeps its failure evidence and no
partial deck is emitted. No unapproved raster fallback, ignored-item route or arbitrary
callback is accepted by this adapter.

### Executable recipe fields

The optional manifest `construction` extension is validated by the existing
manifest validator. Its top-level fields are `version`, `slide_width_inches` and
optional v4 `editing_groups` defined below.
For example, `{"version":4,"slide_width_inches":12}` enables the current routes.
Version 1 retains binary/native compatibility; 2 adds `closed_form` layers;
3 adds [source-field fitting](source-fields.md); 4 adds hybrid pictures, semantic
editing groups and rectangular bindings. Earlier routes retain behavior.
`source.sha256` is required; `canvas` dimensions equal the original raster pixels.
The slide preserves that aspect ratio. Other feature schemas remain applicable.
Plain rectangles and bound links explicitly block implicit theme shadows. Declared
native Paint effects retain their own emitter; no slide-wide effect stripping occurs.

Each `source_inventory` item adds `construction` with `kind`, nonempty source
`observation`, and the route fields below. Keep its existing ID, module, role, bbox,
representation and exact text; do not repeat these in a second scene inventory.

| kind | Route fields | Existing implementation |
|---|---|---|
| `text` | `options`: measured `font_size_px`; optional `font`, `bold`, `color`, `align` | `text_draw`; text comes from the item's `text` |
| `rectangle` | `options`: optional `fill`, `stroke`, positive `stroke_pt` | `rectangle_draw`; only observed rectangular shapes/decorations |
| `svg` | `asset`: source-derived `path`, `sha256` | `read_vectors` + `svg_draw`; restricted native SVG, no pictures or outlined labels |
| `trace` | `extract`: method/observations below; `trace`: `colors`, `representation`, `max_native_paths`, `max_native_commands` | `extract_source_object` + `trace_component` + `svg_draw` |
| `native_component` | Same ID/output_name as its canonical `native_components` entry; optional v3 `field_fit` under [source-fields](source-fields.md) | `manifest_component_draw` + existing Paint emitter |
| `picture` (v4) | No duplicated asset fields: item's `component_instance` references the existing approved instance | `picture_draw` + [hybrid asset contract](hybrid-component-schema.md) |
| `rect_link` (v4) | `options`: `source_port`, `target_port` (`top/bottom/left/right`); optional `color`, positive `width_pt`; connection/endpoints below | Existing [rectangular connections](native-toolkit.md#rectangular-connections) emitter |

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
uses the same scene mapping as text/paths. For measured continuous colors choose
`field_fit`; without it, Paint is supplied explicitly. Neither changes source
geometry; a bound estimated layer may supply foreground/alpha under its existing
extraction assumptions, not unknown-background recovery.

Optional shared recipe fields are `parent`, `behind`, integer `z`, and
`container:true`, with the scene semantics below. Connector items use `kind:svg` or
the qualified v4 `rect_link`,
`connection` referencing the existing connection ID and `endpoints:[item1,item2]`.
These exact item endpoints must belong to the connection's source/target modules;
module IDs are not substituted for actual connected shapes. Include observed
arrowheads/inhibition marks in the SVG, never infer a diagonal from its rectangle.
Every connection and inventory item must be emitted once. One source item maps to
one named editing unit, optionally within its declared editing group; internal color paths are editable but do not
claim automatic organelle identification or drag-bound connector behavior.

Native text recipes can also declare `frame_bbox` as the authored frame in source
pixels. The default is the inventory `bbox`. The original `bbox` remains the
observed region used for measurement. The same canvas, parent containment and
scene checks apply to the authored frame. See [text correction](text-fidelity.md#office-layout-and-text-correction).

Pictures require `editing_policy:hybrid`, its existing explicit approval and
`representation:component_raster`; native-required text/data/relationships cannot
be routed to pictures. The canonical instance bbox must equal the source-frame
placement; crop must preserve visible support/aspect, rotation is 0/90/180/270.
Prepare freezes exact approved bytes and dependencies; build rechecks them and
copies portable source/asset inputs beside the saved deck. No whole-panel fallback
or second asset ledger is introduced. Source extraction still precedes approval.

`construction.editing_groups` is a list of `{id,members,observation}`: a unique
group ID, at least two source-inventory IDs, and the intended observed editing unit.
Groups are flat/disjoint and must occupy a contiguous paint-order span; interleaved
members are rejected because grouping would change overlap. This is distinct from
`parent` (container background), not clipping or inferred anatomy.

`rect_link` connects distinct, aligned, outward-facing **top-level rectangles**;
its observed bbox encloses both exact ports. Both endpoints and connector stay
outside editing groups. The driver emits/rechecks actual shape-ID bindings and
`expected-connections.json`; qualify save/reopen/move in PowerPoint before claiming
interactive behavior. SVG biological arrows remain static source-observed paths,
not fake drag-bound links. See [v4 end-to-end tests](../tests/test_hybrid_assembly.py)
for executable synthetic schema, not source geometry to copy.

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

For `extract.method:closed_form`, read [source-layers](source-layers.md).
It owns trimap/foreground color estimation, background assumptions, optional
smooth-field occlusions and the bound layer bundle. Binary-only work need not
load this contract. Prepare/build and review stay on the common entrypoint above.

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
Production nested/source-sampled Paint uses `manifest_component_draw` with one
`native_components.ManifestComponentBuilder` snapshot per assembly. It preflights
the complete manifest once, preserves source checks on emission and calls the
existing serializer; its output name must match the scene ID.
Other already-qualified target adapters may consume `scene.ordered()` and
`frame.place()` without changing backend. Python callbacks take `(slide, bounds,
identity, source_scale)` and emit exactly one top-level editable shape/group. The adapter checks
actual IDs/names, but does not certify arbitrary callback contents.

Freeform relationships use source-observed SVG geometry with `role='relation'`
and `relation=(source_id,target_id)`. Existing native SVG import preserves curve
controls; put observed arrowhead/inhibition geometry in that same source component.
This is not automatic raster line recognition or drag-bound rerouting. Rectangular
bound connectors use v4 `rect_link` or the same qualified
[native-toolkit](native-toolkit.md#rectangular-connections) API.
Never derive a scientific bend from a box diagonal or invent its endpoints.

Assemble on a new empty disposable slide. If a callback fails, discard that failed
deck; do not save it as a successful partial export. No existing slide is rewritten.
The receipt contains actual shape IDs, paint order, placements and relations from
the same scene; use it to resolve manifest output bindings after reopen. Source
inventory still determines whether anything was omitted, and source review still
determines whether endpoint identities are correct. `visual_review` remains
`NOT_PERFORMED` until separately documented actual-render inspection. Do not run a
second independent renderer merely to manufacture an extra PASS.
