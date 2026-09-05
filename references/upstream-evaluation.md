# Upstream selection and capability boundaries

Version 2.7.0 follows a 24-repository review completed on 2026-09-05. The detailed repository-by-repository decision report remains in the upgrade workspace; this reference records only the decisions that affect normal execution. No third-party source code from the review was copied into the curve extractor or auditor.

## Existing incorporated components retained

| Source | Reuse | Boundary |
|---|---|---|
| JamieJustTang/svg2pptx-skill, derived from ppt-master | Selected MIT path parsing and curve mathematics already pinned in `references/upstream-lock.json` | Restricted local SVG component profile; not a general raster-to-vector engine |
| Lucide | Three pinned attributed vector assets | Recognition signature must match; no automatic source-specific substitution |
| python-pptx | Existing library for grouping, bindings, ordinary PPTX copies, and package inspection | Only verified helper profiles are exposed; curve auditing reads DrawingML directly |

See [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md) for copied-code and asset notices.

## Curve-fidelity patterns adopted

| Source family | Adopted decision | What was not adopted |
|---|---|---|
| Lancelot-Xie/img2pptx | Hard semantic constraints must include peak, valley, cluster, and gap locations where they carry meaning | No full SVG-in-PPT execution protocol or external dependency |
| WebPlotDigitizer, PlotDigitizer variants, ai-plot-digitizer | Isolate each series, use color/corridor/seed evidence, sample coordinates, and keep manual correction as the honest fallback | No AGPL or unlicensed code; no assumption that automatic smoothing preserves sharp features |
| FTimg | Evaluate curve count, missed/false/split/merge behavior, and point-to-curve distance separately | No model, weights, training data, or unlicensed code |
| VTracer, Trazor, ImageTracerJS, Potrace wrappers | Treat deterministic vectorizers as optional local helpers for isolated regions, with explicit error bounds and post-trace review | No whole-slide auto-vectorization and no new runtime installation |
| fitCurves | Permit error-bounded Bézier fitting after source coordinates and landmarks are locked | No copied implementation; the local audit remains dependency-light |
| PptxGenJS and native DrawingML paths | Store curves as real custom geometry and re-read the delivered path from PPTX | No competing builder is mandated; backend selection remains task-specific |
| SVGDigitizer | Preserve a coordinate trace as the source of truth and distinguish visible digitization from recovered raw data | No GPL code or claim of recovering hidden measurements |

## Reviewed but not incorporated as curve engines

- `px-image2pptx`, `dlinjiade-debug/Image2PPT`, and similar OCR/inpainting tools primarily make text editable while retaining charts as raster backgrounds or picture modules. That does not solve internal curve editability.
- `BrainChen/image2ppt`, `ningzimu/image-to-editable-ppt-skill`, `Paul-Jeo/Image2PPT`, `happy-figure-edit`, and `image-to-editable-pptx-v2` contribute useful manifest, region, and QA patterns, but their generic pixel or region checks do not by themselves prove peak topology.
- `ChartOCR` and `OmniParser` require additional learned models or target other visual structures. They are disproportionate for local curve tracing and do not replace source-specific coordinate evidence.
- `image2ppt-sdk` is a hosted closed engine and conflicts with the default local privacy boundary.

## Operational boundary

Prefer native vector paths, then supplied data, then local raster digitization. Do not install a vectorizer, OCR stack, or model automatically. Generic vectorization may propose geometry for an isolated crop, but the canonical trace, declared peak constraints, actual-PPTX readback, and rendered review decide acceptance.
