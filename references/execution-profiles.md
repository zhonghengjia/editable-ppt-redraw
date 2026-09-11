# Execution profiles and bounded reconstruction

This is the authority for planning depth, attempts, independent tests and evidence
reuse. Profiles control work volume, not fidelity. Choose from source features
before loading construction schemas; use `standard` when uncertain.

## Profile selection

| Profile | Suitable source | Planning / review |
|---|---|---|
| `fast` | Small single panel, simple geometry, few/no compact symbols, one output, no evidence-raster exceptions or dense routing | Working notes for canvas, objects, reading order and uncertainty. No manifest/contact sheet merely because a helper exists. |
| `standard` | Ordinary branching flowchart, pathway, timeline, mechanism or study diagram; repeated styles, modules or recognition-dependent icons | Item/module/link inventory, grammar and per-icon signatures with label-free review; compare densest/uncertain crops. A manifest is optional only if one canvas/output and required evidence remain unambiguous. |
| `dense` | Multi-panel, batch, multi-output, raster-exception or highly interconnected composition | Validated manifest with complete inventory, applicable contracts and semantic/negative constraints. Review modules locally before global integration; compare every dense/recognition-critical module and verify each output. |

Approved hybrid work needs at least standard and an asset-backed manifest; dense
sources stay dense. Feature contracts in [SKILL.md](../SKILL.md) can require a
manifest even when the profile allows notes. They own curve, hierarchy and other
evidence requirements; this table does not waive them.

Every profile reopens/reparses its canonical artifact, runs applicable
[checks](quality-runner.md) and renders each output when a local route exists.
Inspect composition and required details under [quality-rubric](quality-rubric.md).
Missing rendering is unverified, never inferred from a builder preview.

## Backend selection

Use one installed, trusted, target-owning route from [backend-routing](backend-routing.md).
Qualify its required objects once. If it fails, record the reason and try **at most
one fallback**; direct native-source generation counts as the fallback, not a third
attempt. In unattended work do not repeat a failed interactive Office probe.

Keep the successful backend for the canonical artifact; independent builders need
an explicitly requested comparison. If both routes fail, stop the affected work;
do not install dependencies without approval. Record route/version, object
qualification, failed probe and fallback reason once beside the manifest, not in
the visual. A mode/format/backend change after viable construction needs user
direction, not another free attempt.

## Source and evidence reuse

Inspect the whole source, then full-resolution uncertain/dense crops. Keep full
OCR/XML/logs/differences in working files; return compact status and affected IDs.
Reuse unchanged source observations instead of extracting again to restate a plan.

For an independent skill test, use a new directory and raw reference. Previous
decks, builder geometry, extracted parts and coordinates are not construction
inputs. Reusable serializers/utilities are allowed; record input provenance.

Use the quality runner once per evidence state. Standalone auditor examples are
diagnostic alternatives, not additional required passes on unchanged bytes.
Construction preflight and final-artifact readback remain distinct stages.

## Correction and stopping

Allow one coherent construction pass and **at most one evidence-driven correction
pass**, including component generation; generation has no separate retry loop.

Save/reopen and review the candidate. If correction is warranted, change canonical
inputs and regenerate, keeping baseline and corrected versions separate. No filler
placeholders. Reuse unchanged source contracts, but refresh changed artifact hashes,
readback, layout/render evidence and applicable machine reports. Inspect changed
regions and dependent labels, links, neighbors and paint order; repeat full
comparison for global changes or uncertain impact.

Accept the correction only when the defect improves and hard gates remain
satisfied; otherwise keep the baseline and disclose the defect. Remaining blockers
mean **incomplete**; nonblocking disclosed approximations may be delivered. Stop
when scope/checks are met, not after unlimited cosmetic rebuilding. A tool failure
does not erase useful completed work or make the failed part complete.
