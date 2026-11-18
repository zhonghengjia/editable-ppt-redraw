# Third-party components

## Source text measurements

`source_text_metrics.py` adapts the local Otsu ink-measurement mechanism from
[ningzimu/image-to-editable-ppt-skill](https://github.com/ningzimu/image-to-editable-ppt-skill/blob/b7be494e31a0ed56ef98716891db5474606b8cdf/skills/image-to-editable-ppt/cli/editppt/runtime/page_text_metrics.py),
commit `b7be494e31a0ed56ef98716891db5474606b8cdf`, Copyright (c) 2026 ningzimu,
MIT. The complete [license](scripts/third_party/image-to-editable-ppt-skill/LICENSE.md)
is retained. Local changes preserve boundary/tiny ink, bind diagnostics to the
existing source inventory, disclose ambiguity, and optionally match the transcribed
strings with the selected installed font. No cloud OCR, OAuth/image backend,
upstream CLI, global height clusters or automatic border cleanup is imported.

## SVG path mathematics

Source: [JamieJustTang/svg2pptx-skill](https://github.com/JamieJustTang/svg2pptx-skill/tree/876c188e34fefc3c4e24919494c752edf25d1ae9), commit `876c188e34fefc3c4e24919494c752edf25d1ae9`.

Upstream file: `scripts/svg_to_pptx/drawingml_paths.py`. Destination: `scripts/vendor/svg_paths/drawingml_paths.py`. The upstream MIT license, including attribution to Jamie Tang and Hugo He/ppt-master and its asset notices, is retained in `scripts/vendor/svg_paths/LICENSE`.

Modifications: strict rejection of malformed/incomplete/nonfinite paths and invalid arc flags/radii; reset the current point to the subpath origin after closepath during normalization; compute cubic-extrema bounds analytically instead of using the control-point hull, with a one-EMU minimum extent. `drawingml_utils.py` is a minimal original pixel/EMU adapter, not the upstream utilities. No upstream CLI, model pipeline, rasterizer or entire converter was bundled.

## Lucide assets

Source: [lucide-icons/lucide](https://github.com/lucide-icons/lucide/tree/94e4cb9d9db5907053ebf3636a97c45529cf776b), commit `94e4cb9d9db5907053ebf3636a97c45529cf776b`.

Selected assets: `assets/lucide/inventory.json`. Full upstream ISC/MIT notices: `assets/lucide/LICENSE`. Artwork geometry is unchanged; hashes distinguish source bytes from newline-normalized bundled bytes.

## Local raster component tracing and comparison

[ImageTracerJS](https://github.com/jankovicsandras/imagetracerjs), `imagetracer_v1.2.6.js`, is bundled byte-for-byte as `scripts/vendor/imagetracer/imagetracer.cjs` under the Unlicense; the complete upstream license is retained alongside it. [Pixelmatch](https://github.com/mapbox/pixelmatch), `index.js`, is bundled byte-for-byte as `scripts/vendor/pixelmatch/index.mjs` under ISC, with its complete license. Only filename extensions change to explicitly select Node module modes. Exact upstream tree/blob IDs, source/bundled hashes and license hashes are recorded in [upstream-lock.json](references/upstream-lock.json); no future HEAD update is automatic.

`component-worker.mjs` and `component_fidelity.py` are original local adapters. No upstream models, network loading utilities or browser image-loading code are invoked. Their tests exercise selected integration behavior, not the entire upstream test suites.

## Existing dependencies

The toolkit calls already available python-pptx, lxml, Pillow and NumPy packages, each separately installed with its own license. Optional source-object extraction calls an independently installed OpenCV `grabCut`; no OpenCV code or models are vendored. `source_objects.py` and `reconstruction_scene.py` are original integration code; their source review is recorded in [the stability decision](research/2026-09-11-stability-review.md). No reviewed inpainting, OCR, segmentation-model or scene framework code was copied. No unlicensed, restricted-use or AGPL source code was incorporated.

`references/upstream-lock.json` is the version/hash authority for bundled code; the asset inventory is the corresponding authority for artwork. The local wrapper and connection audit are original integration code.

## Native Paint and component construction

`native_paint.py`, `native_components.py` and the source sampling functions are
original integration code. The bounded composite compiler independently implements
the [W3C compositing equations](https://www.w3.org/TR/compositing-1/); no reviewed
converter or renderer implementation was copied. `pdf_paint_scene.py` uses an
already installed PyMuPDF public API as an optional read-only source adapter;
PyMuPDF/MuPDF keep their separately distributed licenses, and their source is not
vendored. These helpers reuse the already bundled path mathematics and
native DrawingML fill semantics rather than copying diffusion/matting code.
`raster_components.py` is original Pillow/NumPy integration for given-alpha crop
processing, known-matte algebra, diagnostic compositing and immutable bindings.
No Canva artwork, private model, SDK or demonstration asset is bundled. Public
Canva demonstrations informed the object-level workflow, not a claim to reproduce
their unpublished segmentation or generative backend.
The bounded fill representation follows Microsoft's [GradientFill](https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.drawing.gradientfill)
and [PathGradientFill](https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.drawing.pathgradientfill)
documentation. The [PowerPoint gradient-stop interface](https://learn.microsoft.com/en-us/office/vba/api/powerpoint.fillformat.gradientstops)
is used for application qualification.

The source review considered SVG.js, resvg and diffvg's separation of geometry and
paint, but their code is not bundled or imported. The PyMatting package (distinct from the adapted color module below), SAM, model checkpoints,
Bioicons artwork and Blender assets are not newly included. Review of a repository
is not adoption of its license or a claim that its runtime was tested here.

`source_layers.py` independently implements the closed-form color-Laplacian
equations reviewed in [PyMatting's implementation](https://github.com/pymatting/pymatting/blob/6d5c4a6bed0e/pymatting/laplacian/cf_laplacian.py)
and the standard interior 13-point biharmonic boundary system reviewed in
[scikit-image's implementation](https://github.com/scikit-image/scikit-image/blob/v0.25.2/skimage/restoration/inpaint.py).
It uses separately installed NumPy and SciPy APIs. No PyMatting, Numba,
scikit-image, GPL implementation or model weights are copied or imported by this
alpha/interpolation route. The reviewed upstream projects have MIT (PyMatting) and BSD (scikit-image)
licenses; these are algorithm/source references, not newly bundled dependencies.
The shared source-over inverse is original algebra, not ML foreground recovery.

The optional observed affine-background adapter is original equal-patch-weight
NumPy least squares with SciPy convex-hull containment. It remains separate from
the optional joint-color estimator and does not claim unknown-background recovery.

`joint_foreground.py` adapts PyMatting's multilevel local 2x2 F/B mechanism at
[commit 6d5c4a6bed0e5672abac0bad078e594423ffe4fd](https://github.com/pymatting/pymatting/blob/6d5c4a6bed0e5672abac0bad078e594423ffe4fd/pymatting/foreground/estimate_foreground_ml.py).
Copyright (c) 2020 PyMatting, MIT. The complete license and modification notice
are retained in [LICENSE.md](scripts/third_party/PyMatting/LICENSE.md) and
[NOTICE.md](scripts/third_party/PyMatting/NOTICE.md). Local synchronous NumPy updates,
opaque color anchors and diagnostics differ from upstream Numba execution; no
equivalent output or recovery guarantee is claimed. The PyMatting/Numba packages
and model weights are not dependencies of this adapter.

The [24-project review](research/2026-11-06-upstream-system-upgrade.md) informed
this color route, the existing PyMuPDF public-API source evidence extension and
shared Office readback. No PyMuPDF AGPL implementation, OCR/model package,
Docling/MinerU converter, alternate layout engine or external service is bundled.

The reusable Office evidence utility uses the installed PowerPoint COM API,
including [TextRange bounds](https://learn.microsoft.com/en-us/office/vba/api/powerpoint.textrange.boundleft)
and [ConnectorFormat](https://learn.microsoft.com/en-us/office/vba/api/powerpoint.connectorformat).
Semantic groups and hybrid pictures reuse the existing python-pptx renderer;
no Office binary, alternate renderer or new third-party assets are distributed.
Plain primitive creation uses python-pptx's shadow inheritance control. The empty
local effect list follows Microsoft's [DrawingML inheritance rules](https://learn.microsoft.com/en-us/openspecs/office_standards/ms-oi29500/c0c046ec-a61d-405d-88fe-74d8487a37d7);
it blocks implicit theme effects without removing separately declared Paint effects.

## Source-field fitting

`source_fields.py` is an original NumPy implementation of bounded least squares,
source-coordinate profile fitting and native stop compilation. Algorithm review
used [Trazor gradient.ts (MIT)](https://github.com/PhenX/Trazor/blob/d5dd561830defbff379a5fba18990cf7efc0267d/packages/raster/src/gradient.ts)
and [Inkvec fit.rs (Apache-2.0)](https://github.com/logolabs/inkvec/blob/a07b39473a3b952338e366870f21fbfe73a28c41/crates/inkvec-trace/src/gradient/fit.rs):
position-covariance-normalized color slopes, bounded direction search and explicit
continuous fills rather than palette bands. No implementation files, Rust/TS
runtime, network service or model weights from these projects are bundled.
The MIT description above refers only to that historical pinned revision. The
2026-10-22 review of Trazor revision `090b914086c5de2027b20c08e2b48c73e0e69c25`
found FSL-1.1-ALv2; no code from that newer revision is copied or imported.
The same review studied skechu-ppt (MIT), current Inkvec (Apache-2.0),
resvg (MIT/Apache-2.0), tiny-skia/Skia (BSD-3-Clause) and Image2Editable (MIT)
for domain/ramp separation, interpolation order and shared scene compilation.
Observable-column fitting, coverage-weighted direction, bounded stop selection,
receipt freezing and batch assembly are original integration with the existing
NumPy and native emitters; no upstream renderer or second converter is bundled.
The [20-project comparison](research/2026-10-22-source-fields-and-assembly.md)
distinguishes source study from execution and adoption. License-missing image2PPT
and DrawAI's independently unverified vendor files are not copied.
Native gradient coordinates/interpolation follow the existing Microsoft references.
Other reviewed projects, including license-restricted Agent4PPT and unverified-license
ScanSci, are not copied or imported. Research does not grant redistribution rights.

## Marked-source shared coverage

Source-paint ownership in `component_fidelity.py` also reuses this tracing engine.
The new ownership integration is original code. Research inspected MuPDF/PDF.js
group compositing, resvg mask/group rendering, Sharp premultiplied-alpha handling
and SVG-to-DrawingML projects; no code from these reviews is newly vendored.
Source rendering uses an already installed renderer under its existing license.
Reviewing AGPL/LGPL projects does not authorize redistributing their implementations.

`source_partition.py` and the coverage diagnostics in `component_geometry.py`
are original integration code. The marker-controlled priority flood is not an
OpenCV or scikit-image runtime and is not a copy of their implementation.
Shared-boundary construction was informed by the TopoJSON, Mapshaper and VTracer
source reviews; no code from those projects is bundled by this change. The
adapter reuses the already pinned ImageTracerJS worker and native component
serializer. Its guarantees concern declared visible pixel ownership, not
automatic anatomical recognition, continuous gradients or seam-free Office
rasterization. The optional opaque color-tree compositor is original local code,
informed by VTracer's separation of stacked and mosaic compositing. No VTracer
code or runtime was copied. Both palette modes reuse the same pinned ImageTracerJS
scanner; partial-alpha stacking is rejected. Existing third-party version and
license authorities are unchanged.
