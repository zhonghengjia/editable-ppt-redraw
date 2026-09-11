# Source-owned native tracing

Read only when source pixels must become native component geometry. The source-first plan is in [component-fidelity](component-fidelity.md); final checks use [regional-fidelity](regional-fidelity.md).

## Source selection, representation and native tracing

Use one pipeline: source coordinates and assembly support → source part ownership → joint boundary representation → native paths → actual-file evidence. Ownership chooses which observed pixels belong to construction inputs; it is never an output ignore mask or semantic certification. Representation determines how those pixels become geometry; neither stage may change the acceptance contract after seeing an output.

### Marked-source assemblies

For a cluster of adjacent/interleaved visible objects, `source_partition.build_source_partition(source, support_path, plan, node=existing_node)` builds all candidate pieces from one source-coordinate label map before invoking the existing pinned boundary scanner and native component serializer. It returns ordinary `native_components`, the label map and preparation evidence; add those components through `native_components.add_manifest_component`. The helper writes no files and does not accept previous renders or fitted output geometry.

The plan requires `source_sha256`, `source_bbox` `[x,y,w,h]`, `support_sha256`, `support_observation`, `markers`, `colors_per_part` (2–64), `max_native_paths` and `max_native_commands` (positive declared assembly budgets). Optional `representation` selects `palette_edges` (compatibility default) or `palette_stack` as defined below; no other fields are accepted. The support is a binary 0/255 grayscale PNG at crop size. Prepare it from the original source: visible silhouette and real holes, with extraction/measurement provenance; never use a convex hull, filled-hole operation or old output as source truth. It is construction support only, not the mask for final QA. Source must be opaque, qualified sRGB. The shared one-million-pixel bound and importer limits remain unchanged.

Each marker has exactly `id`, `observation`, `seeds`: 1–100 explicit crop-local integer `[x,y]` source witnesses, with at most 100 named parts. Multiple witnesses may identify disconnected visible fragments of one observed object. Every connected support island needs a witness; duplicate/out-of-support seeds fail without snapping. The deterministic four-neighbor priority flood minimizes maximum local RGB change, then path length, with FIFO ties. It assigns support pixels once, leaves outside/holes unassigned and does not discard a watershed separator as transparency. This is an original bounded source-partition adapter informed by marker-controlled watershed, not the OpenCV/scikit-image implementation and not automatic object recognition. Inspect the resulting ownership map against source boundaries; a poor seed or low-contrast boundary can merge or misassign visible pieces even with perfect coverage. Unknown identity remains NOT_VERIFIED.

Each named visible piece reuses the source palette preparation and exact pixel-boundary scanner. No piece is independently smoothed, no background patch is inserted, and native geometry for all colors/owners uses the same lattice. Alpha membership is checked after quantization. The returned ledger binds source/support/plan/label hashes, all assigned pixels, color approximation and native path/command counts. Budgets apply to the complete assembly, not a succession of smaller exemptions. Exceeded budgets or unseeded islands fail; no partial candidate is returned.

The result preserves visible pieces, not complete hidden cells. Within-piece color partitions are independently editable native paths but are not automatically named nuclei or organelles; where those need independent semantic editing, explicitly inventory/mark those pieces instead of claiming color tracing recognized them. Quantization does not reproduce continuous native gradients, and source-grid edges can show steps at high magnification. Keep the existing native Paint route for suitable isolated/overlapping smooth parts; select the source-supported representation before construction. Confirm useful selection/movement in PowerPoint and inspect native rendering for antialias seams.

Assembly coverage is evaluated under the existing [regional structure contract](regional-fidelity.md), including `coverage`. Declare the complete assembly as a sensitive inventory region as well as reviewing its named parts. A selected-source/label-map comparison proves preparation only; final geometry/color/coverage checks use original source and the actual saved/reopened render. Missing declarations cannot be counted as not-applicable passes.

```text
python scripts/component_fidelity.py trace reference.png component.svg \
  --crop 120 178 72 95 --colors 16 --node /path/to/existing/node
```

The crop is `[left, top, width, height]` in **source pixels**. It must fit the source, each dimension <=4096 and area <=1 million pixels. Without a selector the adapter uses pinned ImageTracerJS smooth color tracing and an explicit source-derived palette: all observed colors within the color budget, otherwise existing Pillow RGBA octree quantization without dithering. There is no blur, small-path omission, random reseeding, palette re-averaging or coordinate rounding. Color reduction and curve fitting can still lose rare features, small holes and thin bridges. It keeps the crop background and unwanted source letters; these are not editable text. A prepared alpha asset needs recorded extraction provenance, not an unrecorded background erasure.

Outputs are a new SVG plus schema-2 `.trace.json` containing source hash/size/crop, engine hash/options, representation, measured byte/element/path/command complexity and explicit unverified semantic/final-artifact status. Failed tracing or preflight writes `.trace.failed.json` with source binding, available measurements and the error, without emitting an SVG or successful sidecar. Existing success or failure paths are refused. SVG generator metadata is removed and primitive opacity is represented as fill/stroke opacity; native-profile preflight rejects unsupported content before emitting the candidate. Use the existing [native toolkit](native-toolkit.md) to import paths as native DrawingML, not an SVG picture. Output IDs identify path pieces, not automatically recognized semantic parts. Record the helper's native object mapping and give source-grounded names/groups.

Source ownership and source paint are separate choices. `--selector selector.json`
identifies visible pixels; optional `--ownership` retains one observed connected
part. Empty/full-crop selections are rejected. The compatibility default
`--support-paint uniform` creates a median-colored silhouette, not a colored-object
reconstruction. Use it for genuinely flat silhouettes or explicit silhouette tests.

For colored objects use `--support-paint source --part-plan part.json`: original
RGBA survives at every selected pixel before tracing. Alternatively,
`--source-support support.json --part-plan part.json` accepts an independently
observed, crop-sized binary grayscale ownership mask. The JSON has exactly `path`,
`sha256`, `observation`; path is relative to that JSON. Its observation identifies
original geometry/measurement, not an output-derived mask. This route excludes
selector/connected ownership: one source of ownership per part. The original image
hash/crop is bound by the part plan; support hashes and preparation evidence use
the existing trace sidecar, not a second pipeline.

Source-paint ownership accepts `smooth`, `palette_edges` or `palette_stack` under
their existing alpha/budget constraints. It does not average RGB/alpha, remove faint
alpha, fill holes, blur pixels or infer hidden anatomy. Binary ownership is not
soft alpha: within ownership, original RGBA is unchanged until color quantization.
Retained source letters remain drawn letters, so separate source text before
acquiring object paint. For PDFs with native text, use
`pdf_paint_scene.render_artwork(source, page_number, region, scale=3)`. It returns
an RGBA image and source/page/clip/pixel-origin evidence, removes only PDF text
in memory, keeps graphics/images and inserts no covering rectangle. The source
file is never saved. Restore labels as native text from the original extraction.
Outlined/rasterized lettering remains unresolved; this is not OCR or inpainting.
Use the original, text-containing source for final comparison, not this prepared
render as replacement ground truth.

For PDF blends unsupported by native Paint, use that installed PDF artwork
renderer, then retain independently observed **visible object support** from
that source render. Trace the object, not a whole panel, through this source-paint
entrypoint. This bakes the observed backdrop into its colors; it does not recover
hidden color or dynamically recomposite when moved onto another background.
Declare that editing tradeoff before use. Retain PDF/page/crop/render mapping and
source-render hash. Prefer native continuous Paint where qualified; bounded color
layers are a practical alternative, not a native-gradient claim.

Uniform silhouette support defaults to `--representation source_edges`: pinned ImageTracerJS `layeringstep`/`pathscan` supplies exact integer pixel-cell boundaries, bypassing internode averaging and spline fitting. Only exactly collinear vertices are removed; opposite hole winding produces compound native paths with real gaps, not background-colored masks. This retains source-resolution stair steps and potentially many editable vertices; it does not infer continuous subpixel curves. Choose this representation before authoring when narrow connections/gaps must survive. `--representation smooth` explicitly selects the fitted alternative; it is not a fallback after a failed source-edge export. Multi-color tracing, including source-paint ownership, defaults to smooth; the explicitly planned palette alternatives are described below. `source_edges` without a selector, with source paint, non-binary support or unsupported requests fails. Any smoothed or manually fitted replacement must independently pass the same source-defined limits, never inherit the raw-edge candidate's result.

### Multi-color part representation and editing budget

For a source-inventoried multicolor part, choose one composition before authoring: `--representation palette_edges --part-plan part.json` emits disjoint color faces, while `palette_stack` emits opaque source-color-tree paint layers. Both reuse the same boundary scanner, preserve quantized source color at pixel centers and are not automatic object recognition. Required part-plan fields, no others:

- `part_id`, `observation`: nonempty identity and source evidence for the chosen editing unit. Keep required independent objects/labels separate; grouping a whole panel as one part is not a remedy for over-complexity.
- `source_sha256`, `source_bbox`: exact input-byte hash and trace crop. Freeze the recipe against the raw input, not the output.
- `max_native_paths`, `max_native_commands`: positive integer task budgets selected before construction for the intended editor interaction. The helper bounds these numeric inputs at one million, but still enforces the unchanged, more restrictive SVG import profile. These are not fidelity thresholds or universal defaults. Judge budgets from the intended component granularity and representative editor behavior; never raise them after a failure to certify that candidate.

The plan may also constrain `smooth` or `source_edges`. It is mandatory for both palette representations. They accept source-paint ownership above, but not uniform silhouette selection. A separated alpha input must retain its extraction provenance and linkage to the original source inventory.

`palette_stack` requires opaque colors with only 0/255 source alpha, checked before quantization and again at the worker. It builds a deterministic binary tree by nearest RGB color-centroid distance, weighted by source pixel counts. A parent uses an observed representative color and exactly the union of its descendant source color supports. Preorder painting omits only inherited identical paint, not visible source pixels. Every original transparent hole stays outside every layer. Tree paint order is an encoding of visible colors, not anatomical depth. This reuses the existing scanner and packing logic; no second contour fitter, extra stroke, dilation, per-output seam locator or full-canvas backdrop is introduced. Partial-alpha artwork must retain the disjoint route or a separately qualified native representation, never flatten opacity to use stacking.

At ideal source-pixel centers, opaque overpainting gives the same quantized colors as disjoint faces. Parent color under adjacent child paints reduces background leakage inside a part when an editor antialiases each face separately. Actual antialiasing can still mix those colors, and contacts between independent owners remain subject to final-render review. Keep parts inside their original visible support. Moving an internal paint layer may reveal encoding colors underneath; only a source-supported semantic part hierarchy promises meaningful independent object movement. Whole-part recoloring/movement and native paint editing remain available. This route does not solve pixel stair steps or recover continuous source gradients.

The adapter quantizes once using the existing source palette policy, without dithering, and feeds those exact RGBA pixels to the pinned boundary scanner. Adjacent colors use the same integer pixel lattice, not independently fitted curves. Every visible pixel is assigned; alpha-zero pixels are accounted for but have no path. Prepared-pixel hashes and white-matte mean/max RGB error and changed-pixel counts identify the **color quantization** approximation. Exact tracing of this prepared input does not prove fidelity to original gradients or thin source features lost during quantization.

Within this declared part, disjoint same-fill outer contours and their hole children may share a native compound path. Hole winding and complete parent/child rings stay intact. The implementation reuses the existing boundary extraction and exactly collinear removal, with equivalent H/V encoding; it never combines overlapping arbitrary SVG paths, strokes, masks, separate semantic parts or fitted color layers. Packing follows source region order and the importer-owned path-character limit; an indivisible overlong region fails instead of being tiled or losing holes. The sidecar records each color's pixel/region count and half-open source-region ranges mapped to output IDs. Keep native part grouping and editable text separately in the builder.

Preflight evaluates both serialization limits and the declared path/command budget. A compound path can be small on disk yet contain tens of thousands of vertices; packing does not reset the command count. `complexity.native_profile: PASS` and `budget_status: PASS` establish only these numerical checks; `practical_editability` stays `NOT_VERIFIED` until actual output selection, recolor/move behavior, grouping and rendered fidelity are inspected. Preserve separate source-versus-preparation, preparation-versus-vector, and original-source-versus-final-render results. All final [regional/structural](regional-fidelity.md)/[relationship](surface-relations.md) gates still apply to the original source, never the quantized image as replacement ground truth.

### Connected source ownership (construction only)

If the crop's selected color belongs to several objects, inspect source support and optionally add `--ownership ownership.json`. One recipe identifies one **connected visible part**, not the largest region. Freeze it from the raw source before constructing output. Required fields, no others:

- `part_id`, `observation`: nonempty source inventory identity and evidence/uncertainty description.
- `source_sha256`, `source_bbox`: exact source-byte hash and the same integer crop used for tracing.
- `selector_sha256`: hash from `component_fidelity.recipe_digest(selector)` (UTF-8 canonical sorted-key compact JSON, not the recipe file's whitespace-dependent hash).
- `seeds`: 1–100 unique integer `[x,y]` witnesses in crop-local source pixels. Every witness must hit the same 8-connected selected component. Background, out-of-bounds, duplicate or disagreeing witnesses fail; no snapping, automatic largest-blob choice or invented bridge.

The trace sidecar records the full recipe/hash, selected component and **every unassigned component's ID, area and box**. The same `component_geometry.label_regions` traversal defines component membership and topology; there is no separate segmentation implementation. More than 2000 components exceeds this ownership-ledger profile and fails without dropping fragments. Unassigned content remains a source-inventory obligation, not approved deletion. If an occluded semantic part has multiple visible components, inventory/trace them separately and retain uncertainty rather than forcing a connected recipe.

Do not apply this ownership selection to final-render QA or use it to remove mismatches. The [regional contract](regional-fidelity.md) still compares full source/render regions with identical selectors and unchanged gates. Source versus extracted support checks establish preparation only; complete-figure color, occlusion, labels, practical grouping and actual native-render checks remain separate requirements.

No model, GPU, network, OCR or package installation is invoked. Node is an explicit existing local runtime. Unsupported high-complexity/noisy crops fail the native profile or source-part budget with retained diagnostics. Do not increase limits, discard paths, split the same object into arbitrary tiles or switch representation silently. A failed editing budget calls for source-grounded part decomposition or an explicitly approved representation change, not a numerical exemption. Fitted adjacent color layers can show seams, and exact shared pixel edges can remain cumbersome to edit. Inspect native rendering as well as geometry: identical mathematical boundaries do not guarantee identical antialiased paint in every editor. Arbitrary thick strokes must not hide seams or close genuine gaps.
