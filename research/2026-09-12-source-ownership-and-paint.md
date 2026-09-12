# Source ownership and continuous Paint — 2026-09-12

## Evidence and decision scope

The full v3.18.0 ferroptosis preparation exposed two independent production gaps:
color-initialized binary segmentation lost faint disconnected bonds or absorbed
neighboring labels; the production CLI could not consume the existing native
Paint tree. The older annotated deck additionally showed a clipped radial field
and a straight crop seam. These are not evidence that every model or every native
gradient is faulty. Some initial positive witnesses also landed on background;
correcting those witnesses improved, but did not complete, extraction.

This review reads the relevant implementation paths below, not every file in each
repository. Twenty-one distinct useful repositories count; failed downloads,
README-only discoveries and thin wrappers do not count. Source snapshots and
download hashes were retained with the local research run. Branch links below
are navigation links, not immutable version pins. No downloaded source was run.

## Ranked implementation comparison

Rank reflects relevance to this failure, not a general product-quality rating.

| # | Project / implementation read | What the code actually does; advantage | Limitation / decision |
|---|---|---|---|
| 1 | [OpenCV](https://github.com/opencv/opencv/blob/4.x/modules/imgproc/src/grabcut.cpp), `constructGCGraph`, `estimateSegmentation`, `grabCut` | Four-class mask initialization fixes observed foreground/background while optimizing probable pixels through color GMMs and contrast-weighted graph cuts. Already installed. | Color segmentation is not semantic recognition or alpha matting. **Reuse installed API** with source-coordinate annotations; retain current point route. |
| 2 | [python-pptx](https://github.com/scanny/python-pptx/blob/master/src/pptx/dml/fill.py), `_GradFill` | Native fill and stop interfaces, package save/readback. | Public gradient-angle access only covers linear gradients; cannot treat it as arbitrary SVG radial conversion. **Reuse existing qualified DrawingML emitter**, not a new serializer. |
| 3 | [PyMatting](https://github.com/pymatting/pymatting/blob/master/pymatting/alpha/estimate_alpha_cf.py), `estimate_alpha_cf` | Trimap divides fixed samples from unknown pixels; closed-form Laplacian and conjugate-gradient solve estimate continuous alpha. | Alpha alone does not recover foreground RGB; source assumptions and additional dependencies required. **Defer integration**, do not call binary support matting. |
| 4 | [rembg](https://github.com/danielgatis/rembg/blob/main/rembg/bg.py), `alpha_matting_cutout`, `naive_cutout`, `decontaminate_cutout` | Matting path estimates alpha and foreground colors, showing why assigning alpha alone retains color fringes. | Erosion-generated trimaps and model-driven foreground masks may erase thin scientific structures; naive fallback does not solve this. **Do not adopt automatic fallback/model download**. |
| 5 | [CairoSVG](https://github.com/Kozea/CairoSVG/blob/main/cairosvg/defs.py), `draw_gradient` | Explicit object/user-space transforms, center/focal point, radius and stop opacity keep paint domain separate from geometry. | SVG rendering does not imply editable Office equivalence. **Use domain separation**, retain current native-paint authority. |
| 6 | [svgwrite](https://github.com/mozman/svgwrite/blob/master/svgwrite/gradients.py), gradient/stop constructors | Typed center/focus/radius/stop fields avoid ambiguous style-string interpretation. | Writes SVG only. **Reuse typed-Paint design already present**; no new dependency. |
| 7 | [scikit-image](https://github.com/scikit-image/scikit-image/blob/v0.25.2/skimage/segmentation/random_walker_segmentation.py), weights/Laplacian/linear solver | Positive region markers and sparse graph probabilities support interactive segmentation. | Probabilities are not physical alpha; solver cost and a missing dependency. **Defer**, avoid a second segmenter in this change. |
| 8 | [f-BRS implementation](https://github.com/iloleg/fbrs_interactive_segmentation/blob/master/isegm/inference/predictors/brs.py), `BRSBasePredictor`, `FeatureBRSPredictor` | Positive/negative click maps refine cached features using scale/bias optimization. | Requires learned weights/Torch; available implementation is not proof of active maintenance. **Adopt observation-driven refinement concept only**. |
| 9 | [SAM](https://github.com/facebookresearch/segment-anything/blob/main/segment_anything/predictor.py), `predict` | Points, boxes and previous mask logits share explicit original-image transforms. | Object masks/quality scores are not matting or molecular ownership. **Defer weights/runtime**. |
| 10 | [SAM 2](https://github.com/facebookresearch/sam2/blob/main/sam2/sam2_image_predictor.py), `predict` | Reuses image embeddings and normalizes prompts to original dimensions. | Heavy runtime and uncertain small scientific-detail coverage. **Defer**, not a substitute for source inspection. |
| 11 | [Grounded-Segment-Anything](https://github.com/IDEA-Research/Grounded-Segment-Anything/blob/main/grounded_sam_demo.py), detector-to-SAM pipeline | Text detector boxes become correctly scaled SAM box prompts. | Two model families; scientific symbols may be undetected or merged. **Do not integrate for this bounded fix**. |
| 12 | [BiRefNet](https://github.com/ZhengPeng7/BiRefNet/blob/main/models/birefnet.py), decoder and gradient refinement | Multiscale refinement targets high-resolution detail rather than only coarse saliency. | Learned foreground priors do not assign touching components or recover hidden content. **Defer**. |
| 13 | [InSPyReNet](https://github.com/plemeri/InSPyReNet/blob/main/lib/InSPyReNet.py), `forward_inference` | High/low-resolution predictions and Laplacian pyramid blending recover boundary detail. | Saliency is not instance ownership; normalized prediction is not validated physical opacity. **Defer**. |
| 14 | [U-2-Net](https://github.com/xuebinqin/U-2-Net/blob/master/model/u2net.py), `U2NET.forward`, side-output fusion | Nested U stages and six side outputs capture multiscale foreground. | Downsampling/weights and semantic ambiguity remain. **Defer**. |
| 15 | [PyDenseCRF](https://github.com/lucasb-eyer/pydensecrf/blob/master/pydensecrf/densecrf.pyx), unary/pairwise setup and inference | Bilateral image terms refine boundaries from provided unary beliefs. | Needs correct ownership beliefs; smoothing can erase small structures and cannot unmix alpha. **No new native-extension dependency**. |
| 16 | [ImageTracerJS](https://github.com/jankovicsandras/imagetracerjs/blob/master/imagetracer_v1.2.6.js), `imagedataToTracedata`, `colorquantization`, `tracepath`, `fitseq` | Separates indexed color layers, scans paths and fits bounded line/quadratic segments. Existing route produces native editable paths. | Palette quantization approximates continuous tone; omitted small paths and smoothing need source-specific budgets. **Keep existing pinned integration**, do not use it to infer ownership/alpha. |
| 17 | [VTracer](https://github.com/visioncortex/vtracer/blob/master/crates/vtracer/src/pipeline.rs), `segment`, `finish_ctx` (also `lib.rs`) | Segmentation, color fitting, compositing and geometry optimization are separate phases; segmentation can be reused. | Inspected current branch includes newer pipeline work; not proof that alpha releases are mature. **Adopt separation principle**, no backend replacement. |
| 18 | [DiffVG](https://github.com/BachiLi/diffvg/blob/master/apps/painterly_rendering.py), render/Adam optimization loop | Optimizes native path controls and colors against raster/perceptual loss. | Pixel loss can look similar with wrong scientific structures; extra runtime and optimization cost. **Reject for faithful automatic ownership recovery**. |
| 19 | [Tesseract](https://github.com/tesseract-ocr/tesseract/blob/main/src/api/baseapi.cpp), `GetComponentImages` | Exposes original-image text boxes separately from internally scaled binary images. | Text boxes are not exact glyph masks; clearing a padded box damages surrounding structures. **Use coordinate distinction**, no automatic rectangular erasure. |
| 20 | [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR/blob/main/ppocr/postprocess/db_postprocess.py), contour/box extraction | Scores text regions and expands contours for detection coverage. | Expanded regions overlap non-text content; learned detector is not clean foreground separation. **Defer OCR integration**, preserve text as separate native units. |
| 21 | [SciPy](https://github.com/scipy/scipy/blob/main/scipy/interpolate/_fitpack_impl.py), `splprep` | Parametric fitting checks knots, weights, dimensions and residuals; useful after coordinates are actually observed. | Cannot reconstruct missing data; smoothing can change peaks and topology. **Retain source-coordinate-first rule**, no new curve fitter here. |

## Accepted impact matrix (before implementation)

User authorization: repair the identified production failures systematically using
mature solutions. Originals, older PPTX, unrelated builders and Git history are
protected. No dependency/model installation or publication is included.

| ID | Decision | Current → target | Files / action | Verification / stop condition |
|---|---|---|---|---|
| A1 | ACCEPT | Sparse color points → optional explicit source-coordinate foreground/background strokes and polygons feeding the **same** GrabCut | Replace initialization/selection in `source_objects.py`; extend the existing extraction recipe validation; add tests | Hard-marked thin/disconnected pixels survive; hard-marked neighbor excluded before extraction; conflicting/out-of-context marks fail; source RGB unchanged; old point behavior retained |
| A2 | ACCEPT | Native Paint helper disconnected from CLI → `native_component` recipe reuses canonical `native_components` and existing manifest emitter | `reconstruction_pipeline.py`, existing pipeline tests | Frozen source used for sample recheck; same IDs, bounds/order; gradient XML and actual rendered gradient; no pictures; changed samples fail |
| A3 | ACCEPT | Ambiguous rejected/stale review message → explicit distinct reasons | Existing build review branch and test | Rejected evidence cannot build, no relaxed approval conditions |
| A4 | ACCEPT | Four-route description → current five-route documentation at existing authority | `source-assembly.md`, version/README, `CHANGELOG.md`, `UPDATE_GUIDE.md` | No parallel schema or per-image exception; full regression and skill-format checks; approved files synchronized locally |
| D1 | DEFER | Automatic matting, foreground unmixing and semantic model inference | No new model, dependency or fallback | Report limitations, do not equate this work with hidden-background or entire-figure recovery |
| D2 | DEFER | Git publication / whole-figure certification | No commit/push/release or old-deck overwrite | Only measured local code/probe results reported |

Source marks describe observed visible pixels; they do not reconstruct concealed
parts. Continuous Paint is selected only where the observed source profile fits
the existing supported native domain. A transparent radial example is not proof
that an irregular multicolored ROS field is radial. No per-image coordinates,
object names or magic color thresholds enter production code.

The stopping condition is A1–A4 implemented and verified with existing regression,
new extraction/gradient tests, a saved-and-reopened render probe and local install
parity. It is not an unlimited attempt to certify the full ferroptosis figure.

## Verification results

- Baseline: 364 unit/integration tests passed. Modified code: 374 tests passed,
  no skips, with the explicitly selected installed OpenCV 4.10.0 interpreter for
  the optional real extraction test. No dependencies were installed.
- Real GrabCut test retained all 67 marked pixels of a pale disconnected strand
  and excluded the separately marked same-color neighbor. Source RGB/bytes stayed
  unchanged. Four-class priority, conflicting labels and clipped strokes were
  checked separately. This is a synthetic ownership test, not semantic inference.
- The unified native-component route saved and reopened source-sampled gradient
  shapes; altered sampled colors failed and no partial PPTX was saved. Frozen
  source reads remained valid even after changing the current source filename's
  bytes outside preparation.
- A separate synthetic three-background probe used the actual production CLI,
  existing centered-radial conversion and native emitter. Saved PPTX: three native
  gradients, six top-level editing units and zero pictures. LibreOffice 26.2.5.2
  reopened it and exported PDF, then PyMuPDF produced the inspected image.
  Visual inspection found full round fields with continuous transitions on white,
  dark and pale-blue backgrounds; the old missing-quadrant failure did not recur
  in this supported profile. Equal-radius four-quadrant sample spreads were
  3/6/5 sRGB code values; this is a fixture check, not a real-figure tolerance.
- Probe PPTX SHA-256:
  `b87850bb766f027c26c07beeb3c1b8a736c77f41c38f8fded83d8071a3039bdf`.
  Actual render SHA-256:
  `082cb3b8f8802660a5977177c2b3ebb0c609f4654e0668b7076264212230a4e0`.

The real ferroptosis component comparison still shows why thin source structures
need better ownership input. This change does **not** certify that whole figure,
recover arbitrary mixed glow/cell colors, or verify PowerPoint interactive
editing. Unit passes and the radial probe must not be relabeled as those results.

Final status: A1–A4 **VERIFIED** within the scope above. Repository and installed
skill format checks passed; 212 local Markdown links resolved. Ten approved files
were synchronized to the local installation with a recoverable previous-version
backup and byte-hash parity. D1–D2 remain **DEFERRED**; no Git publication occurred.
