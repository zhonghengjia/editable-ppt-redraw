# Continuous native fields: source review and bounded decision

Date: 2026-10-03. Baseline: v3.20.0. This is an implementation record, not a
routine redraw instruction or a benchmark of third-party products. Twenty distinct
repositories had representative implementation files actually read at the pinned
commits below. None was installed or executed; README, popularity and image
similarity were not treated as native-editability evidence. User images were not
sent to these projects. Main integration independently reread the selected fitting
functions and the bounded-reporting reference before deciding.

## Diagnosed gap

The existing source-layer route estimates straight foreground RGB and coverage,
but feeds them through palette tracing. Its `smooth` option changes contour
geometry, not continuous color. An in-memory 256-gray-ramp probe returned only
16 palette entries for budgets 16, 32 and 64 (one diagnostic, not a universal
16-color limit). Existing native Paint already supports continuous gradients.
The missing operation was fitting original color observations into that Paint
without replacing semantic boundaries or introducing another renderer.

## Twenty implementation comparisons

Order reflects relevance to this bounded change, not repository popularity.
Licenses describe inspected code/notices; review does not authorize redistribution.

| # | Project and pinned implementation | Useful mechanism | Limitation / decision |
|---|---|---|---|
|1|[Trazor gradient.ts](https://github.com/PhenX/Trazor/blob/d5dd561830defbff379a5fba18990cf7efc0267d/packages/raster/src/gradient.ts)|`fitRamp` uses inverse position covariance and channel slopes; explicit color/opacity fields (MIT).|Large TypeScript subsystem. Adopt small mathematical principles in existing NumPy route; do not import overlay decomposition or runtime.|
|2|[Inkvec fit.rs](https://github.com/logolabs/inkvec/blob/a07b39473a3b952338e366870f21fbfe73a28c41/crates/inkvec-trace/src/gradient/fit.rs), [bands.rs](https://github.com/logolabs/inkvec/blob/a07b39473a3b952338e366870f21fbfe73a28c41/crates/inkvec-trace/src/gradient/bands.rs)|True continuous fills, same-evidence comparisons and band merging (Apache-2.0).|Rust integration, automatic merging can cross semantic parts. Adopt continuous-field distinction; defer ellipse/model selection. Observed pushed Oct 2 / 36 stars indicates activity, not maturity proof.|
|3|[img2gradient index.html](https://github.com/MarcinDudekDev/img2gradient/blob/4e9a137bcda56ff4474aee0f7cfeacf20083285c/index.html)|`sartSolve` compensates overlap using alpha × transmittance; emits CSS gradients (MIT declared).|Coarse placeholder objective, not native PPT or anatomical reconstruction. Defer multiple blobs/overlays.|
|4|[python-pptx fill.py](https://github.com/scanny/python-pptx/blob/278b47b1dedd5b46ee84c286e77cdfb0bf4594be/src/pptx/dml/fill.py)|Real gradient stops and DrawingML emission (MIT).|High-level gradient_angle rejects radial. Retain existing project native radial emitter; no dependency upgrade.|
|5|[SVG-CLI-Creator vectorize_image.py](https://github.com/Joeyoey/SVG-CLI-Creator/blob/5a5f261f4820a447085f4db9aa8ec6e4fecd0378/vectorize_image.py)|Small PCA/channel-regression linear-gradient baseline (MIT).|Spatial PCA may not follow color; bounding-box aspect and two-stop limitations. Not adopted as production fitter.|
|6|[diffvg color.py](https://github.com/BachiLi/diffvg/blob/85802a71fbcc72d79cb75716eb4da4392fd09532/pydiffvg/color.py), [save_svg.py](https://github.com/BachiLi/diffvg/blob/85802a71fbcc72d79cb75716eb4da4392fd09532/pydiffvg/save_svg.py)|Linear/radial parameter classes, differentiable rendering (Apache-2.0).|Inspected exporter only handles linear correctly; Torch/compiled dependencies. Defer, do not equate renderer support with export support.|
|7|[LIVE main.py](https://github.com/Picsart-AI-Research/LIVE-Layerwise-Image-Vectorization/blob/679e1d16c5809367f2d2db3e403a8548c5419258/LIVE/main.py)|Residual-guided layer insertion and path optimization (Apache-2.0).|Optimized constant RGBA tensors, not continuous fills; heavy optimization. Not the missing color-field operation.|
|8|[Img2Num labels_to_svg.cpp](https://github.com/Ryan-Millard/Img2Num/blob/6cadf353e6dbc74dd64ec0f5151389feb69509d4/core/src/internal/labels_to_svg.cpp)|Explicit contour export and region colors (core MIT; other material differs).|kmeans/flat #RRGGBB paths retain palette bands. No replacement for continuous shading.|
|9|[JPG-to-SVG color vectorizer](https://github.com/Furinaaa-Cancan/JPG-to-SVG/blob/b378a5b0f46a591849609e6554d3023925476a6d/04_vectorization/semantic/sam3_color_vectorizer_fast.py)|Semantic masks before vectorization.|SAM/BLIP weights, root SAM license, actual route flat kmeans fills. Advertised mesh path unavailable; not counted as implemented. No adoption.|
|10|[LayerPeeler vectorize.py](https://github.com/kingnobro/LayerPeeler/blob/b75f2353011972f4c8c2dc748c1f0861ede2ee80/inference/vectorize.py)|Raster layer peeling / difference masks.|Vectorization uploads PNG to Recraft; Flux/LoRA, permissive license not verified. No code/model/API adoption.|
|11|[siril9 repair_packet.py](https://github.com/siril9/presentation-skill/blob/2776d8a7d08e64924a69cbf5bdb1271c5bedf99b/scripts/repair_packet.py)|Bounded reports preserve totals, missing states and truncation (MIT).|Content-generation system, not screenshot segmentation. Retain conditional reading and existing report authority; do not add a parallel packet system.|
|12|[ScanSci check_edit_units.py](https://github.com/Rimagination/scansci-svg/blob/f4dd394eb0797681fcfdf43f230483dcf8c144ac/skill/scripts/check_edit_units.py)|Explicit owner/member edit scopes and source/candidate comparison.|SVG grouping does not prove anatomical relationships or Office editing; license unverified. Reuse existing part tree, no second edit-unit inventory.|
|13|[Kevinyyy1 audit_pptx.py](https://github.com/Kevinyyy1/image-to-editable-pptx-v2/blob/a474793ad53c82aad375b2cc3f326994f3387ae1/skill/image-to-editable-pptx/scripts/audit_pptx.py)|Source text/object coverage, oversized picture checks and failure regions (MIT).|Name substring checks not bijective IDs; hybrid imagery remains. Existing project coverage/QA retained, not duplicated.|
|14|[Ningzimu manifest builder](https://github.com/ningzimu/image-to-editable-ppt-skill/blob/b7be494e31a0ed56ef98716891db5474606b8cdf/skills/image-to-editable-ppt/cli/editppt/runtime/build_pptx_from_manifest.py)|Native OOXML text/table/path, stable z-order (MIT).|Pillow preview is not Office; semantic groups not established by inspected entrypoint. Existing emitter retained.|
|15|[DOM-to-PPTX index.js](https://github.com/atharva9167j/dom-to-pptx/blob/939ef79f00db8f9f5f4f75b590e83e380abce197/src/index.js)|Known DOM geometry/IDs and sorted native render queue (MIT).|DOM input is not raster semantics; skipped queue entries/raster CSS require review. No new browser backend.|
|16|[Perpetualhui validate_native_pptx.py](https://github.com/perpetualhui/image-to-pptx/blob/4af43cdadf0bce265f37cf2f344c35787527e14c/tools/validate_native_pptx.py)|Lightweight XML audit distinguishes embedded SVG (MIT).|Native text absence is only a warning; object counts are not fidelity. Do not weaken existing source-aware checks.|
|17|[AutoFigure-Edit autofigure2.py](https://github.com/ResearAI/AutoFigure-Edit/blob/16f3749e9d512bdf7b7b55c162307bc289750b7a/autofigure2.py)|Stable SAM placeholders separate structure and complex icons (MIT code; models separate).|Final SVG includes base64 PNG icons, optional remote calls and weights. Not a fully native default.|
|18|[Image2PPT converter.py](https://github.com/dlinjiade-debug/Image2PPT/blob/7a17060f81c9b093d2ef131515327c7d43a7a05b/converter.py)|OCR clustering and text/image-module separation (MIT).|Charts/icons remain raster add_picture; no source-aware native semantic coverage. Not adopted.|
|19|[Agent4PPT project.py](https://github.com/xy040427-collab/agent4ppt-skill/blob/97c4d9ce52b2ec37206f7761bfb7e83961b9b732/skills/agent4ppt-skill/scripts/agent4ppt/project.py)|Hashes bind draft/preview/QA to current artifact.|Background plus selected native text; Personal Noncommercial Use License is not open-source permission to modify. No code or text copied.|
|20|[BRCOO svg-to-ppt-embedded.js](https://github.com/BRCOO/image2pptx/blob/16994433ba0bd62248ab2284aabb226e6547ac5d/scripts/svg-to-ppt-embedded.js)|Explicit embedded-svg mode makes representation inspectable.|Single full-page addImage, not element-level native output; license unverified. Negative reference, not a redraw solution.|

## Decisions and integration

| ID | Decision | Implementation / scope |
|---|---|---|
|U1|ACCEPT|Original bounded NumPy color-field fitter; fixed observed ownership/geometry, solid/linear/centered circle; actual straight alpha only.|
|U2|ACCEPT|Optional v3 field_fit in existing native_component recipe; original input/support bindings, recomputation and existing native emitter.|
|U3|ACCEPT|One conditional operation document; replace old routing sentences, not append contradictory instructions. Research/history not default context.|
|U4|ACCEPT|Numerical and full legacy regression, application render/edit readback, isolated independent raw-input usage test.|
|D1|DEFER|Unknown-background decomposition, ellipse/mesh, added gradient blobs, model installations, cloud services, second inventory/QA systems.|
|D2|DEFER|Git publication: local validated upgrade is not a pushed commit, tag or Release.|

No upstream implementation was vendored. Existing dependencies, native serializer,
source-layer extraction and interface names are unchanged. Operation authority is
[source-fields](../references/source-fields.md); parameters are not redefined here.

## Executed qualification and limitations

- Baseline 386 tests passed in the configured host environment. Initial sandbox
  failures were runtime visibility/access blocks, not counted as passes. Final
  suite: **404 tests, 0 failures, 0 skipped**, 25.793 s. Eighteen new field tests
  include fixed geometry, non-square directions, radius/rim, RGB/alpha, qualification
  reading, source/support/compiled-tree tampering and no partial success output.
- Independent review found repeated inherited alpha, bypassed ICC/EXIF checks,
  and missing canonical support-hash comparison. These were corrected in their
  common operations, with regression cases; reviewer reran 18 tests and closed
  all three findings. Missing candidate receipts are rejected from recipe requirements.
- Five controlled source profiles × three backgrounds produced **15 native decks**.
  Actual Microsoft PowerPoint **16.0** rendering at original 120×40 dimensions
  gave mean RGB error 0.228–0.640 and max 3 in 8-bit channel units (3/255).
  No palette bands or picture objects were used. These are synthetic profiles,
  not a biological-image performance estimate or universal rendering guarantee.
- PowerPoint application automation moved a native group by 5 pt, changed one
  gradient stop, saved a new artifact and reopened it. Name/stop count/color/position
  persisted and the original file hash did not change. No mouse-driven GUI test
  is claimed.
- An independent agent received only raw RGBA PNG, the current skill and isolated
  output directory. It selected the documented route, prepared and built on its
  first attempt, without reading fitter/test code or others' output. Output: one
  native path, eight color/alpha stops, zero pictures/media. Its LibreOffice actual
  white/dark renders had max RGB difference 5/255. Its separate Office session
  was unavailable. Main-thread follow-up confirmed its eight-stop output could be
  moved/color-edited/saved/reopened in PowerPoint 16.0; an extra PNG export failed
  and was not counted as render success. Its actual render evidence remains
  LibreOffice, separate from the 15 main-thread Office cases.
- **Old estimated ROS still fails.** Its read_layer_bundle source/plan/seven
  output bindings passed; all 100,633 alpha-positive pixels were retained.
  Fixed radial/eight-stop/max-error .025 fit returned .984646 and no Paint.
  The existing layer contains 30,064 interpolated pixels and unverified physical
  layer identity; it is not original transparent ground truth. This diagnoses a
  representation mismatch, not merely insufficient stops or a small color correction.
  No support erosion, tolerance increase, model switch or per-image exception followed.

Consequently this release adds a tested continuous-color operation and preserves
existing capabilities. It does not establish general soft-cell cross-fade recovery,
the previous ROS region's acceptance, or whole-figure visual stability. The ordinary
source/render review remains required; automated passing is not visual proof.
