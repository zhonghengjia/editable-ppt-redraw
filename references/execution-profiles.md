# Execution profiles and bounded reconstruction

Select one profile before choosing a builder or drawing objects. The profile controls planning depth and QA cost; it does not lower the fidelity or editability promised to the user. Use `standard` when classification is uncertain. Approved hybrid work uses at least `standard` with the asset-backed manifest in [hybrid-components.md](hybrid-components.md); dense compositions still use `dense`.

## Profile selection

### `fast`

Use for a small single-panel visual with straightforward geometry, few or no compact symbols, no evidence-image exceptions, one requested output, and no dense cross-module routing.

Required work:

- record the canvas, principal objects, reading order, and uncertainties in working notes;
- build from one canonical editable source;
- reopen or reparse the delivered artifact;
- run the target-specific editability or source audit through [the local quality runner](quality-runner.md), without adding an unnecessary manifest;
- render the complete output when a local render path exists and inspect composition, clipping, and text wrapping;
- run connector or icon checks only when those features are present.

Do not create a visual manifest or contact sheet solely because the tools exist. This native fast profile does not apply to generated/approved hybrid components.

### `standard`

Use for ordinary flowcharts, clinical pathways, timelines, mechanisms, or study diagrams with branching connectors, repeated styles, several modules, or recognition-dependent icons.

Required work includes all `fast` checks plus:

- a compact visible-item, module, and connector inventory; a manifest is optional when one output and one canvas remain easy to track;
- a diagram-grammar contract in working notes for a structured visual, or in the manifest when one is created;
- the orthogonal connector audit when named flow segments are present;
- recognition signatures and label-free comparison for compact symbols;
- source-versus-output crops for the densest or most uncertain regions.
- for any meaning-bearing curve, a task-relative coordinate trace and source-versus-output curve check; use the manifest-backed `curve_fidelity` contract when more than one series, peak topology, or overlap makes informal notes ambiguous.

### `dense`

Use for multi-panel, batch, multi-output, raster-exception, or highly interconnected visuals where local modules can drift during integration.

Required work includes all `standard` checks plus:

- a validated visual manifest as the canonical planning model;
- a complete `diagram_grammar` contract for structured visuals, including visual type, representation-change authorization state, role-to-geometry mappings, semantic edge mappings, and routing;
- a complete `source_inventory` mapping every visible item to a module and representation strategy;
- a `typography_hierarchy` contract and reopened-output hierarchy audit when three or more distinct text roles materially affect the composition;
- a `curve_fidelity` contract, one source-coordinate trace per meaning-bearing series, and the reopened-PPTX curve audit when curves, ridges, density profiles, steps, trajectories, or signals appear;
- explicit semantic and negative constraints for topology, containment, border ownership, and prohibited substitutions when those rules are not obvious from geometry alone;
- module-first construction and local module review before global integration;
- independent validation of every requested output;
- complete-page or complete-slide rendering plus comparison crops for every dense or recognition-critical module;
- an explicit account of raster exceptions, uncertainties, and format-specific approximations.

## Bounded backend selection

Choose the authoring backend before construction:

1. Prefer an already installed, project-pinned, target-owning backend that produces the requested editable format.
2. Probe that preferred backend once with the smallest meaningful capability check. Do not repeatedly launch or rediscover the same application.
3. If the probe fails, record the concrete reason and try at most one fallback. Direct native-source generation counts as this fallback.
4. Once a backend succeeds, keep it for the whole build. Do not mix independent builders for the same canonical artifact unless the user explicitly requested a multi-backend comparison.
5. If both attempts fail, stop authoring and report the blocker. Do not install a new dependency or continue cycling through applications without authorization.

In unattended or noninteractive execution, do not repeatedly retry interactive PowerPoint automation after the first capability failure. Prefer a proven noninteractive local backend or direct native-source generation as the single fallback.

Record the selected backend, version when readily available, failed probe if any, and fallback reason in the task notes or manifest-adjacent run record. Do not place local absolute paths or internal diagnostics inside the delivered visual.

## Evidence and context discipline

- Inspect one downsampled whole composition to establish topology, then use full-resolution crops only for uncertain text, compact symbols, dense modules, and failed QA regions.
- Keep verbose OCR, XML, rendering, and pixel-difference output in files. Bring the compact summary, blocking findings, and affected object IDs into the working context.
- Do not rerun OCR or full-slide comparison after a change that affects only one already-identified local object; rerun the local evidence plus the final artifact reopen check.
- Keep baseline and corrected renders separately. A correction is accepted only when hard gates still pass and the named defect improves; otherwise retain the baseline and report the unresolved defect.

## Bounded correction cycle

Use exactly one canonical builder, source document, or manifest-backed source model.

Component generation belongs to this same construction/correction budget, not a separate retry loop. Retain failed requests and stop the affected component if the tool fails or the correction still fails; never insert a placeholder to report completion.

1. Complete one coherent construction pass.
2. Reopen or reparse the actual output and collect the checks required by the selected profile using [quality-runner.md](quality-runner.md). Missing evidence remains unverified; manual render checks remain separate from automatic results.
3. If evidence shows defects, make one targeted correction pass in the canonical source and regenerate all affected outputs.
4. Rerun only the checks affected by the change plus the final reopen or reparse check.

Do not perform repeated cosmetic rebuilds without new evidence. After the correction pass:

- if a blocking defect remains, mark the task incomplete and report the defect and affected artifact;
- if only a disclosed non-blocking approximation remains, deliver it and stop;
- if all applicable checks pass, deliver and stop.

Changing the reconstruction mode, target format, or backend after construction begins is not a correction pass; it is a contract change and requires user direction unless the original backend failed before producing a viable canonical artifact.
