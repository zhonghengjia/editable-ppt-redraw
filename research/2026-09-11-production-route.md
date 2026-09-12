# Production route decision — 2026-09-11

Scope: implement the accepted source-first construction route, not another model,
web service, scientific template library or stricter fidelity thresholds. Existing
uncommitted v3.17 work is the baseline and remains intact. Raw figures, old decks
and other task builders are protected. No Git publication is authorized here.

## Evidence and reuse

The [21-project code review](2026-09-11-stability-review.md) remains the comparison
inventory; this iteration does not pretend to be a second fresh 21-project search.
Re-read the relevant fig2slide renderer, diagram-pptx scene, OpenCV GrabCut sample
and our extraction/scene/trace/manifest implementation. Online rechecked
[fig2slide rendering](https://github.com/Yutao-Yang/fig2slide/blob/main/src/fig2slide/render.py),
[OpenCV's sample](https://github.com/opencv/opencv/blob/4.x/samples/python/grabcut.py),
and [python-pptx grouping](https://github.com/scanny/python-pptx/blob/master/src/pptx/shapes/shapetree.py).

| Mechanism | Advantage | Limitation / decision |
|---|---|---|
| fig2slide manifest dispatch | One element inventory controls construction | Its ignored items, image strategy and box-diagonal line defaults do not preserve this task's contract. Reuse the dispatch pattern, not its renderer. |
| diagram-pptx scene | Stable paint order and shared coordinate frame | Does not extract source objects. Retain our existing scene implementation. |
| OpenCV GrabCut | Installed seeded segmentation, no extra model weights | Can merge text or miss disconnected detail. Call existing source_objects, retain candidate inspection. |
| ImageTracer + existing native SVG emitter | Source paint becomes grouped editable paths | Quantization and pixel complexity remain explicit limitations. Call existing trace_component; no second tracer/parser. |
| python-pptx | Native text, grouped paths and actual package readback | Does not supply source semantics or visual review. Retain the qualified existing backend. |

Failure was at the integration boundary: tools existed, but agents could rebuild
the pipeline independently, reuse an unrelated candidate, then infer a checklist
from that candidate. A source-owned executable route must consume the observed
inventory and extracted components before producing a deck. It cannot force an
agent that deliberately bypasses the route to comply or prove an inventory's
scientific completeness.

## Approved impact matrix

| ID | Decision | Current → target | Affected files / verification | Status |
|---|---|---|---|---|
| P1 | ACCEPT | Per-image glue → prepare/build commands on the existing manifest inventory | scripts/reconstruction_pipeline.py; end-to-end extraction/native group/text readback tests | VERIFIED within scope below |
| P2 | ACCEPT | Independent extraction and placement → measured source bounds consumed by shared scene | Same entrypoint and existing source_objects/reconstruction_scene; nonzero origin and cropped support tests | VERIFIED within scope below |
| P3 | ACCEPT | Reused candidate/overlay correction → fresh build from source snapshot and hash-bound prepared components | Same entrypoint; missing/tampered/stale input, failed export and repeated build tests | VERIFIED within scope below |
| P4 | ACCEPT | Instructions for optional helper use → concise executable route with typed component selection | SKILL.md, source-assembly, visual-manifest, README, update manual/changelog; link and format checks | VERIFIED within scope below |
| P5 | ACCEPT | Runtime mismatch found during tracing → explicit dependency check and optional isolated extraction interpreter | Same entrypoint; missing runtime, no automatic install/fallback tests | VERIFIED within scope below |
| P6 | DEFER | Automatic semantic inventory, OCR/model integration, all target adapters, full-figure success across models | Outside this bounded integration upgrade | DEFERRED |

Implementation replaces affected operation guidance in place. Feature contracts,
budgets, thresholds and the single quality runner remain authoritative. The new
manifest extension stores only executable recipes, not a second content inventory.
Prepared files and output mappings are generated derivatives, never new canonical
observations. Stop after the accepted route, regression suite, real-source local
probe and installation parity checks; report any unverified renderer/editor scope.

## Verification and limitations

- Baseline: 348 unittest cases. Updated: 364 passed, no skips. The 16 added tests
  exercise actual source extraction, tracing, grouped-path export/reopen, two
  retained source colors, text scaling, measured bounds, native curve controls,
  custom output filename, isolated extraction, changed source/support/manifest,
  stale review, missing route, incorrect relation/module mapping and failure
  without a partial deck. Rebuilding changes the canonical text once without
  increasing shape count or changing the earlier output.
- Existing documentation link/anchor tests and skill format validation passed.
  Git whitespace check found no errors (existing LF/CRLF conversion notices only).
- A local two-component regression reused prior raw-source observations, **not
  old PPTX, extracted masks or native paths**. This is a reproducible integration
  regression, not a blinded independent-model benchmark. The new prepare/build
  commands called installed OpenCV 4.10.0 in its separate interpreter and the
  existing source-color/native SVG emitters. The saved/reopened PPTX contains two
  editable component groups, 46 native paths and zero pictures.
- LibreOffice 26.2.5.2 rendered that actual package to PDF; PyMuPDF rasterized it
  for source comparison. Main protein folds/gaps and the cell's nucleus, blebs and
  internal paint were visible. Source quantization and pixel-edge stair steps
  remain visible at magnification; 44 unselected foreground pixels around the
  cell candidate include disconnected fragments. These were explicitly disclosed,
  not considered recovered, and no complete-cell/full-figure fidelity PASS was
  assigned. The construction report correctly left regional/render review pending.
- No PowerPoint interactive selection/drag test or fresh Sol/Terra conversation
  test was performed. Object IDs/groups establish package editing structure, not
  those interaction or cross-model claims. Actual model token savings were not
  measured; shared scripts reduce repeated code authoring but do not prove a
  particular reduction percentage.
- The executable adapter currently covers one faithful raster-canvas PPTX using
  text, rectangles, solid SVG and source-color tracing. Native Paint/part trees,
  PDF source extraction, approved hybrid units and other targets retain their
  qualified APIs; they are not newly integrated or removed. Automatic scientific
  identity, OCR and segmentation of every visible fragment remain out of scope.

The accepted production link is implemented; the broader skill is not declared
universally stable on arbitrary scientific images. No thresholds or original
source pixels were changed to turn the local probe into a fidelity pass.
