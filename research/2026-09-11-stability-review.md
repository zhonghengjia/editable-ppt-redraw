# Stability review and implementation decision — 2026-09-11

Scope: source-specific editable reconstruction, not a new model, generic slide
generator, renderer replacement or tighter visual acceptance thresholds. Reviewed
21 code-bearing projects plus one prompt-only candidate before implementation.
The review covers the named implementations, **not every file or an end-to-end
qualification of every upstream project**. Similarity does not establish maturity.
No upstream programs or model downloads were executed during this review.

## Failure mechanism

Two independent ferroptosis redraws exposed different execution failures:

- A nominally faithful builder substituted generic protein/cell templates and
  fixed zigzags. Its `link()` used box midpoints and four proportional line
  segments even for a curved source relationship. Some GPX4-named links used a
  GSH object binding. A valid presentation package cannot detect this semantic
  substitution.
- Another builder used hand-selected RGB rectangular crops, then added duplicate
  native text. Several crop bounds cut through visible cells. It appended filled
  containers *after* pictures, hiding their contents. Declared asset fields and an
  empty connection inventory did not describe what was actually visible.
- Existing quality reports were not successful overall. Treating creation of a
  file as completion was an execution error, not evidence that QA passed.
- The skill already forbade these shortcuts. Its capability gap was between
  source observations and construction: supplied-alpha preparation assumed that
  a suitable mask already existed, while independently written builders controlled
  placement and paint order separately. More prohibitions would not close it.

## Compared implementations (ordered by task relevance, not popularity)

Each source link points to the reviewed code. Mutable upstream links identify the
implementation; this review's downloaded source inventory retains file hashes.

| # | Project / inspected implementation | Useful mechanism | Limitation / decision |
|---|---|---|---|
| 1 | [fig2slide: render.py](https://github.com/Yutao-Yang/fig2slide/blob/main/src/fig2slide/render.py), `build_pptx`, `_add_image`, `_add_line`; pipeline orchestration | One manifest, ordered elements and source canvas units reduce independent layout decisions. | Image crops still need qualification; line default derives a diagonal from a box. Adopt scene discipline, not default line geometry or unsupported fidelity claims. |
| 2 | [figedit: crop_assets.py](https://github.com/giszzt/figedit/blob/main/scripts/crop_assets.py), `_clamp`, `_edge_check`; `prepare_clean_plate_mask.py` | Context around crops and foreground/edge review help detect truncation. | Border contrast is not semantic completeness; removing text via masks may damage objects. Use context and explicit ownership, not blind boundary heuristics. |
| 3 | [png2pptx: inpaint.py](https://github.com/chrispydizzle/png2pptx/blob/main/png2pptx/inpaint.py), `_build_word_mask`, `_filter_components`, `_build_mask` | Glyph-shaped local masks reduce rectangle-wide damage. | Inpainting cannot recover scientific structure; import fallback silently broadens masks. Keep text reservations/conflicts, reject automatic inpainting. |
| 4 | [Image2PPT: converter.py](https://github.com/dlinjiade-debug/Image2PPT/blob/main/converter.py), `erase_text`, `build_pptx` | Separates native text and background construction; patch handling addresses duplicate glyphs. | Clean whole-image background is not full native editing, and Telea invents missing paint. Not a replacement backend. |
| 5 | [px-image2pptx: inpaint.py](https://github.com/JadeLiu-tech/px-image2pptx/blob/main/px_image2pptx/inpaint.py) | Lazy model initialization and explicit device selection. | LaMa/model installation, synthesis and down/up-sampling are inappropriate default fixes. Defer optional model work; do not install. |
| 6 | [ppt-master: drawingml/converter.py](https://github.com/hugohe3/ppt-master/blob/main/skills/ppt-master/scripts/svg_to_pptx/drawingml/converter.py), `convert_svg_to_slide_shapes` | Original child paint order, semantic grouping and unresolved connector-target detection. | Large SVG conversion surface needs qualification; do not import its whole framework. Reuse our existing derived path serializer. |
| 7 | [diagram-pptx: scene.py](https://github.com/sci-gen/diagram-pptx/blob/main/src/diagram_pptx/scene.py), `DrawingScene.ordered_elements`; render transform | Renderer-neutral objects, stable order and uniform source transform. | A scene model alone does not recognize or reconstruct a scientific illustration. Adopt a small construction adapter with explicit ownership/order. |
| 8 | [ppt-scene-graph: pipeline.py](https://github.com/eluckydog/ppt-scene-graph/blob/main/ppt_scene_graph/pipeline.py), `evaluate` | Reopened package extraction separates construction from inspection. | Its text/background/picture-count scoring cannot certify source fidelity. Reject adoption of those scores as acceptance. |
| 9 | [OpenCV: grabcut.py](https://github.com/opencv/opencv/blob/4.x/samples/python/grabcut.py), seeded four-state mask / `grabCut` | Existing deterministic local foreground candidate extraction using positive and negative observations. | Similar colors, touching labels and small structures remain ambiguous; hard background borders can truncate. Adopt optional installed-library adapter, never automatic mask approval. |
| 10 | [SAM: predictor.py](https://github.com/facebookresearch/segment-anything/blob/main/segment_anything/predictor.py), `predict`, `predict_torch` | Source-frame point/box transforms, multiple mask candidates, explicit uncertainty. | Model weights/compute and prediction errors; scores are not scientific identity. Borrow input-coordinate discipline; defer model integration. |
| 11 | [rembg: bg.py](https://github.com/danielgatis/rembg/blob/main/rembg/bg.py), `alpha_matting_cutout`, `decontaminate_cutout`, `putalpha_cutout` | Distinguishes alpha from foreground RGB; avoids edge halos caused by double matting. | Object/background model priors and erosion can damage thin structures. Keep existing explicit matte preparation; no background-removal fallback. |
| 12 | [RapidOCR: main.py](https://github.com/RapidAI/RapidOCR/blob/main/python/rapidocr/main.py), `run_ocr_steps`, `build_final_output` | Maps word boxes back to original image coordinates; model loading isolated by stage. | Detection is not glyph truth; empty outputs and recognition errors need review. Accept externally measured text reservations, not new model dependency. |
| 13 | [PaddleOCR: db_postprocess.py](https://github.com/PaddlePaddle/PaddleOCR/blob/main/ppocr/postprocess/db_postprocess.py), `boxes_from_bitmap`, `unclip` | Polygon detection and bounded source-coordinate mapping. | Unclip expands by area/perimeter and can encompass neighboring artwork. Treat OCR bounds as reservations, not automatic erase/crop boundaries. |
| 14 | [scikit-image: watershed](https://github.com/scikit-image/scikit-image/blob/main/src/_skimage2/segmentation/_watershed.py), `_validate_inputs`, `watershed`; `skeletonize` dispatch | Marker/support separation, exact array frames; skeleton methods preserve stroke connectivity within assumptions. | Neither assigns biological identity; touching objects merge without correct support. Reuse our existing marked-source partition, defer extra segmentation stack. |
| 15 | [VTracer: color_cluster.rs](https://github.com/visioncortex/vtracer/blob/master/crates/vtracer/src/frontend/color_cluster.rs) | Hierarchical color clusters, deliberate reverse paint order and speckle controls. | Color layers are not semantic components; cluster thresholds lose detail. Keep available tracing route, do not equate clusters with organs/proteins. |
| 16 | [ImageTracerJS](https://github.com/jankovicsandras/imagetracerjs/blob/master/imagetracer_v1.2.6.js), `tracepath`, `fitseq`, `svgpathstring` | Fits line/quadratic segments against traced points and subdivides on error. | Color quantization, path omission and hole handling must be qualified. Reuse current pinned worker instead of another tracer. |
| 17 | [Paper.js: PathFitter.js](https://github.com/paperjs/paper.js/blob/develop/src/path/PathFitter.js), `fitCubic`, `generateBezier`, `reparameterize` | Endpoint-constrained least squares and error-driven subdivision, not guessed midpoint bends. | Still needs correct ordered source points; recursive fitting can overfit noise. Preserve measured controls with existing serializer now; fitting remains optional future work. |
| 18 | [svgpathtools: bezier.py](https://github.com/mathandy/svgpathtools/blob/master/svgpathtools/bezier.py), `bezier_real_minmax`, `bezier_bounding_box` | Derivative extrema give curve bounds, avoiding endpoint-only clipping. | Not semantic tracing or a PPT writer. Existing native serializer already computes analytic bounds; retain it. |
| 19 | [python-pptx: shapetree.py](https://github.com/scanny/python-pptx/blob/master/src/pptx/shapes/shapetree.py), `add_connector`, `add_group_shape`; connector XML | Actual append order, unique IDs, editable group and connector primitives. | Last-added opaque shape covers earlier content; low-level APIs do not know containment intent. Reuse package emitter with precomputed ordering. |
| 20 | [PptxGenJS: gen-objects.ts](https://github.com/gitbrent/PptxGenJS/blob/master/src/gen-objects.ts), `addShapeDefinition` | Explicit line/head/tail properties and deterministic slide-object list. | Appending is still paint order; defaults do not recover source shape or semantic endpoints. Do not add a parallel backend for this fix. |
| 21 | [Pillow: AlphaComposite.c](https://github.com/python-pillow/Pillow/blob/main/src/libImaging/AlphaComposite.c), `ImagingAlphaComposite` | Source-over alpha math preserves layer identity and visible paint. | Composition cannot infer masks or remove baked-in labels. Reuse existing Pillow processing; source bytes remain truth. |

Excluded from the 21 implementation count:
[Lancelot-Xie/img2pptx](https://github.com/Lancelot-Xie/img2pptx) provided a relevant
workflow/readme but no downloaded executable implementation matching this review.

## Decision ledger / impact matrix

The user's request authorizes implementation after comparison. The following
bounded decisions precede code edits; no unrelated cleanup or environment change.

| ID | Decision | Current → target | Files / verification | Status |
|---|---|---|---|---|
| S1 | ACCEPT | Hand crop or preexisting alpha → source-bound seeded support candidate, measured bounds, explicit text conflict | `source_objects.py`, tests; crop/seed/border/text/alpha/source tests and real-source diagnostic | VERIFIED within scope below |
| S2 | ACCEPT | Independent append-order builders → common source-frame assembly with containment and explicit ordering | `reconstruction_scene.py`, tests; ownership order, cycles, coordinates, actual reopened shape tree | VERIFIED within scope below |
| S3 | ACCEPT | Guessed route helper → source SVG paths in the same assembly, using existing curve emitter | Existing `native_vectors` reused, no second path parser; actual cubic geometry readback | VERIFIED within scope below |
| S4 | ACCEPT | Scattered construction advice → operation-scoped executable route and examples | Replace affected instruction paragraphs; update manual/version; links and whole suite | VERIFIED within scope below |
| S5 | REJECT | Whole-panel screenshots, inpainting, automatic anatomy repair, generic cell templates for faithful mode | No model/dependency installs or silent fallbacks | NOT IMPLEMENTED |
| S6 | DEFER | Automatic OCR/SAM recognition, automatic nonmonotonic stroke fitting, all-image certification | User-provided/observed identity and source geometry still necessary | DEFERRED |

Canonical: existing skill entrypoint, feature contracts and Python emitters.
Protected: source images, historical decks, other active tasks and their builders.
Generated: isolated review downloads and regression outputs, never runtime input
for unrelated images. No source figures or private machine paths are published in
this report. No upstream source is copied into this upgrade; small adapters call
installed libraries and existing attributed serializers.

Stop after these accepted mechanisms and integration tests are verified; report
unverified final-render/semantic scope, do not enlarge the work until every image
is mathematically identical. Test passing is not a new image's visual acceptance.

## Verification and remaining boundary

- Before: 332 local unittest tests passed. After: 348 passed, no skips, including
  16 new extraction/assembly tests. Actual saved/reopened cubic control ratios,
  curve endpoints, source origin, aspect ratio, text scaling and container order
  are asserted; these are not only documentation-string checks.
- Skill format check passed using Python UTF-8 mode. The first default Windows
  encoding attempt failed to decode Chinese text; no validator or skill text was
  weakened. Documentation links/reachability and Git whitespace checks passed.
- Installed OpenCV 4.10.0 was exercised on three original-source regions. An
  initial probable-foreground rectangle absorbed pale background, so the generic
  initialization was replaced in place with observed positive/negative color
  priors. No object-specific coordinates or semantic names entered runtime code.
- Visual comparison of the resulting apoptosis, oxytosis and LOXs candidates
  showed retained complete visible outlines and internal source paint, without
  the prior half-cell crop or retained surrounding labels. Inferred binary edge
  accuracy/semantics are not automatically certified by this observation.
- The same candidates fed the existing 24-color source-paint tracing route and
  common scene adapter. A newly saved/reopened three-slide local regression deck
  contains 73 native objects, 0 pictures, with no package/bounds/duplicate-border
  risks in the existing editability audit. LOXs deliberately declared its filled
  container after its children; output correctly painted the container first.
- An already-installed LibreOffice rendered the three slides to PDF, then local
  inspection confirmed no half-cell clipping, no duplicate object labels and no
  container hiding its protein. This is **LibreOffice render evidence**, not a
  PowerPoint interactive edit test. No Office processes were interrupted.
- Color quantization and source-resolution stair steps remain visible under
  magnification. A mask can still exclude legitimate disconnected details or
  include touching labels; source witnesses and human review remain necessary.
  Automatic scientific identity, correct semantic endpoint assignment, complete
  full-figure reconstruction and PowerPoint drag behavior are not established.

No thresholds were tightened/relaxed, no failed test deleted, no model installed,
no screenshot/background used as the native result. Existing emitters and feature
schemas remain unchanged. This release-sized local change does not include a Git
commit, push, tag or release, nor modifications to other active tasks' artifacts.
