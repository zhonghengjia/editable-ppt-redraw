# Authoring backend routing

Choose a backend by the requested editing surface and the source geometry. Do not choose by repository popularity or by the number of advertised features.

## PowerPoint route

Use the first available route that passes a small native-object smoke test:

1. An installed presentation skill or a live PowerPoint connection when the user wants drawing in an existing deck.
2. A project-pinned native PPTX builder such as PptxGenJS, python-pptx, or an equivalent documented local library.
3. Direct OOXML only when the required object cannot be represented safely through the installed builder and the resulting package can be reopened and rendered.

The smoke test must create, save, reopen, and inspect one text box, one bordered shape, and one connector. Do not start a dense reconstruction when the selected route cannot preserve these objects.

## SVG-first route

SVG may be the canonical source when the visual is dominated by vector paths, freeform shapes, gradients, or reusable illustration modules. For local vector components, the bundled [native toolkit](native-toolkit.md) imports a restricted SVG profile as native curves using the selected python-pptx builder. Keep labels and semantic diagram nodes in native text/AutoShapes. The helper does not convert SVG text, arbitrary full figures or raster pixels.

For a complete SVG document beyond that component profile, a PowerPoint derivative is acceptable only when one of these is true:

- an installed MIT-licensed SVG-to-native-DrawingML converter produces independently editable PowerPoint objects and passes the SVG compatibility gate;
- the SVG is intentionally delivered as a picture object and the user accepts that PowerPoint will not expose its internal SVG elements;
- the user will use PowerPoint's Convert to Shape or Ungroup workflow and this manual boundary is disclosed.

Additional routes worth probing when already installed are [svg2pptx-skill](https://github.com/JamieJustTang/svg2pptx-skill) and the SVG converter in [ddpie/agent-skills](https://github.com/ddpie/agent-skills); they share converter ancestry and are not independent quality confirmations. Do not vendor another converter during an ordinary redraw. The selected bundled code is documented in [upstream-evaluation.md](upstream-evaluation.md). Do not automatically install or embed [svg2ooxml](https://github.com/BramAlkema/svg2ooxml); its AGPL/commercial licensing and Python runtime requirements require a separate decision.

## Routes that are not defaults

- Embedded full-slide SVG or PNG is not object-level PowerPoint editability.
- OCR plus an inpainted whole-slide base is appropriate only when the user explicitly accepts partial editability for text-heavy screenshots. It is not the default for diagrams, mechanisms, clinical pathways, or scientific figures.
- Hosted OCR, image generation, MinerU, VLM, or document-parsing APIs require explicit authorization for the named destination and current source material.
- A browser editor, local web service, job queue, or multi-agent state machine is not introduced for a one-off redraw unless the user requests that operating model.

## Backend record

Record the selected route, installed version or commit when readily available, smoke-test result, fallback reason, and known editability boundary. Keep verbose backend logs outside the delivered visual.
