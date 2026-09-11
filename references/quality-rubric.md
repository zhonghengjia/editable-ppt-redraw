# Quality and delivery rubric

This document owns rendered review and delivery decisions.
[Quality-runner](quality-runner.md) owns machine status/dispatch; feature contracts
own numerical and geometric requirements. Content, fidelity and editability do not
compensate for each other.

## Review the saved artifact

Reopen/reparse the deliverable and render every page/slide/canvas when a local route
exists. Inspect each whole composition, not only a montage: missing panels, reading
order and relative scale. Then compare all profile-required dense/recognition-critical
crops at delivered and magnified size.

For image-comparable faithful/semantic work use
`scripts/compare-reference-render.py`; overlays/differences are diagnostics, not a
universal similarity threshold. Prioritize foreground/edges over empty background.
Redesign checks retained content, grammar and hierarchy instead of pixel parity.
Each requested format needs its own readback/render; no cross-format inherited PASS.

## Visible checks by feature

Use the already-loaded feature contract; do not create a second schema/checklist.

| Feature | Inspect in the actual source/render comparison |
|---|---|
| Content / grammar | Labels, values, units, legends, repeated-panel content, directions and diagram family; no material omission, invention or unauthorized conversion. |
| Text / hierarchy | Readability, uncovered glyphs, intended line breaks, wrapping/rotation, weights and relative sizes. Numeric font or text-presence PASS cannot clear covered letters. |
| Curves / charts | Every series' peaks, shoulders, steps, tails, crossings, order, fill and overlap; no merged, missing or template-replaced instances. |
| Links / containers | Directed attachments, routes/buses, z-order, one border owner, centering, gaps and no unintended clipping/overflow. Stored binding is not drag/reroute proof. |
| Symbols / parts | Label-free recognition, silhouettes, terminals, holes/gaps, ownership, host-detail attachment, whole-assembly coverage and occlusion. A regional PASS cannot clear a detached detail. |
| Appearance | Source colors, tone differences, contour, transparency and overlap; no invented lighting/depth. Separate probes, paint order and visible results. |
| Raster / hybrid | Approved scope/provenance, complete subject, aspect, placed resolution and alpha edges on light/dark/actual backgrounds. Metadata is not semantic or edge-quality proof. |
| Editing | Required native roles and useful independently editable units. Test promised editor interactions on a copy; an SVG picture is not internally editable until verified. |

Use `scripts/build-comparison-contact-sheet.py reference.png rendered.png regions.json output.png`
for repeatable crops, not a replacement for whole-output review. Before placing a
raster asset, and after changed extraction, run
`scripts/audit-raster-asset-integrity.py <asset-or-directory> --fail-on-risk`;
its standalone checks are distinct from package placement checks.

Verify declared semantic/negative constraints even when no auditor implements them.
Broken package/media links, zero-byte media, non-hyperlink external resources,
placeholders, mojibake, missing text, out-of-canvas objects and same-bounds
duplicate-border candidates remain blocking package risks. Missing explicit East
Asian typeface is a warning requiring CJK render review, not proof of a defect.
Evidence rasters keep editable overlays and disclosure; illustration pictures
require their approved editing contract.

## Decision and delivery

An applicable FAIL or missing required evidence prevents an overall pass. High
pixel similarity and native-object counts do not establish completion. Keep
unsupported scopes, machine results and actual visual findings separate; never
rewrite reports to manufacture acceptance. Correction/exit rules are in
[execution-profiles](execution-profiles.md).

Deliver file links, page count, requested previews and the canonical editable source.
State mode/editing scope, meaningful editable units, raster origins, completed
checks, approximations, unsupported interactions and blockers. Include profile,
backend/fallback and correction use where they explain the result, not as another
long checklist. Mixed artifacts are not fully native. Keep detailed logs, hashes,
contracts and diagnostic renders with working evidence unless requested.
