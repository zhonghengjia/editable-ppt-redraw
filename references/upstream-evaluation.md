# Upstream selection and capability boundaries

The 3.0.0 review examined 24 distinct repositories at pinned commits on 2026-09-08. The 3.1.0 component-fidelity review examined 23 related repositories, recording Git tree/blob IDs and source hashes before decisions. README/license/core-code inspection is not a whole-repository audit or runtime certification. Related forks/algorithm families are not independent corroboration. Detailed evidence and ranked comparisons belong to upgrade audit reports, not normal authoring instructions.

## Incorporated components retained

| Source | Existing reuse | Boundary |
|---|---|---|
| JamieJustTang/svg2pptx-skill, derived from ppt-master | Selected MIT path parsing and curve mathematics pinned in [upstream-lock.json](upstream-lock.json) | Restricted local SVG component profile, not general image recognition |
| Lucide | Three pinned attributed vector assets | Recognition signature must fit the source |
| python-pptx | Existing native grouping, freeform paths and rectangular bindings | Unsupported template features and arbitrary ports require explicit verification |
| ImageTracerJS | Unmodified local color-region tracing core, pinned by blob/hash | Selected small components; not semantic segmentation, editable text or final fidelity proof |
| Pixelmatch | Unmodified local image comparison core, pinned by blob/hash | Declared final-render regions and worst sliding window; not topology/semantic certification |

The lock file identifies the incorporated-component snapshot. The v3.1 adapters reuse these two small cores without adding models, pip packages or an installation step; an existing Node runtime is required when using them. See [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).

## Decisions that affect execution

- PptxGenJS and svg2pptx implementation patterns reinforce checking actual serialized object IDs and component mappings; imported SVG pictures do not become native shapes merely by being vector.
- WebPlotDigitizer calibration/mask patterns reinforce per-series source coordinates and bounded interpolation. Avoid automatic averaging/smoothing that merges series or removes peaks.
- draw.io uses model-local IDs. Native binding integrity and directed route geometry are independent evidence; Excalidraw endpoint-local routing and MSAGL fallback paths do not prove global obstacle avoidance.
- Mermaid/ELK/Dagre/Penrose layout and constraints remain optional. Do not change faithful source coordinates or diagram grammar merely because automatic layout is available.
- PyMuPDF can supply actual PDF paths when already installed, authorized and license-compatible; scanned pages still require source-grounded tracing. PaddleOCR, MinerU and Docling are optional input tools, not hidden curve-data recovery.
- VTracer supplies contours, not guaranteed curve centerlines. svgpathtools can help analyze paths but is not a full SVG/CSS renderer. MarkItDown is a text input tool, not a redraw engine.
- Existing-template reuse may use a separately verified pptx-automizer route; officegen is not a reason to introduce a duplicate default backend.

## Excluded and deferred integrations

Do not copy restricted Anthropic PPTX skill code or assume the repository's other licenses apply to it. PPTAgent's inspected exporter declares upstream ancestry whose license chain was not fully established, so no code was copied. Presenton's public wrapper was inspected, but its actual export-core engine source/license was unavailable; no fidelity claim or integration follows from the wrapper alone.

No new OCR model, hosted conversion service, presentation framework, graph engine or system dependency was installed. Future adapters require their own task scope, installed-version capability probe and complete output validation. Keep native source, declared measurements, actual-artifact readback and visual comparison as the acceptance chain.
