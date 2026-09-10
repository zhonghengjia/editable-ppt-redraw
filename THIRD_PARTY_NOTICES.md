# Third-party components

## SVG path mathematics

Source: [JamieJustTang/svg2pptx-skill](https://github.com/JamieJustTang/svg2pptx-skill/tree/876c188e34fefc3c4e24919494c752edf25d1ae9), commit `876c188e34fefc3c4e24919494c752edf25d1ae9`.

Upstream file: `scripts/svg_to_pptx/drawingml_paths.py`. Destination: `scripts/vendor/svg_paths/drawingml_paths.py`. The upstream MIT license, including attribution to Jamie Tang and Hugo He/ppt-master and its asset notices, is retained in `scripts/vendor/svg_paths/LICENSE`.

Modifications: strict rejection of malformed/incomplete/nonfinite paths and invalid arc flags/radii; reset the current point to the subpath origin after closepath during normalization. `drawingml_utils.py` is a minimal original pixel/EMU adapter, not the upstream utilities. No upstream CLI, model pipeline, rasterizer or entire converter was bundled.

## Lucide assets

Source: [lucide-icons/lucide](https://github.com/lucide-icons/lucide/tree/94e4cb9d9db5907053ebf3636a97c45529cf776b), commit `94e4cb9d9db5907053ebf3636a97c45529cf776b`.

Selected assets: `assets/lucide/inventory.json`. Full upstream ISC/MIT notices: `assets/lucide/LICENSE`. Artwork geometry is unchanged; hashes distinguish source bytes from newline-normalized bundled bytes.

## Local raster component tracing and comparison

[ImageTracerJS](https://github.com/jankovicsandras/imagetracerjs), `imagetracer_v1.2.6.js`, is bundled byte-for-byte as `scripts/vendor/imagetracer/imagetracer.cjs` under the Unlicense; the complete upstream license is retained alongside it. [Pixelmatch](https://github.com/mapbox/pixelmatch), `index.js`, is bundled byte-for-byte as `scripts/vendor/pixelmatch/index.mjs` under ISC, with its complete license. Only filename extensions change to explicitly select Node module modes. Exact upstream tree/blob IDs, source/bundled hashes and license hashes are recorded in [upstream-lock.json](references/upstream-lock.json); no future HEAD update is automatic.

`component-worker.mjs` and `component_fidelity.py` are original local adapters. No upstream models, network loading utilities or browser image-loading code are invoked. Their tests exercise selected integration behavior, not the entire upstream test suites.

## Existing dependencies

The toolkit calls already available python-pptx, lxml, Pillow and optional NumPy packages, each separately installed with its own license. No unlicensed, restricted-use or AGPL source code was incorporated.

`references/upstream-lock.json` is the version/hash authority for bundled code; the asset inventory is the corresponding authority for artwork. The local wrapper and connection audit are original integration code.

## Native Paint and component construction

`native_paint.py`, `native_components.py` and the source sampling functions are
original integration code. They reuse the already bundled path mathematics and
native DrawingML fill semantics rather than copying diffusion/matting code.
The bounded fill representation follows Microsoft's [GradientFill](https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.drawing.gradientfill)
and [PathGradientFill](https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.drawing.pathgradientfill)
documentation. The [PowerPoint gradient-stop interface](https://learn.microsoft.com/en-us/office/vba/api/powerpoint.fillformat.gradientstops)
is used for application qualification.

The source review considered SVG.js, resvg and diffvg's separation of geometry and
paint, but their code is not bundled or imported. PyMatting, SAM, model checkpoints,
Bioicons artwork and Blender assets are not newly included. Review of a repository
is not adoption of its license or a claim that its runtime was tested here.

## Marked-source shared coverage

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
