# Applicable local checks and evidence status

This is the machine-check entrypoint and status authority. The runner uses existing
local auditors; it launches no model, renderer, Office instance, service or installer.

```text
python scripts/run-quality-checks.py output.pptx \
  --manifest visual-manifest.json --layout reopened.layout.json \
  --expected-connections connections.json --render-evidence render-evidence.json \
  --node /path/to/existing/node --json quality-report.json --fail-on-risk
```

Only the artifact is mandatory; omit unused options. `--profile fast|standard|dense`
overrides the manifest profile (otherwise `standard`). Select the truthful profile
under [execution-profiles](execution-profiles.md); no override disables declared
contracts. Working notes cannot establish undeclared machine inventory coverage.

## Status contract

| Status | Meaning |
|---|---|
| `PASS` | The named check ran with required evidence and found no blocking violation within its scope. |
| `FAIL` | Detected violation or invalid input. |
| `NOT_APPLICABLE` | Outside target/declared features; not proof the feature is absent from the source. |
| `NOT_VERIFIED` | Applicable evidence missing, unreadable or unsupported; exceptions retain reasons. |

`automation_passed` requires all checks marked `required_for_automation` to be
PASS or NOT_APPLICABLE. `--fail-on-risk` returns nonzero otherwise.
`delivery_ready` stays null: the runner never certifies visual review.
Legacy auditor `valid`/`ok` may describe detected errors only; use completeness
fields, the runner or `--fail-on-risk`, never `valid: true` alone.

## Dispatch and inputs

This table describes `scripts/run-quality-checks.py`; do not execute covered
auditors a second time on unchanged inputs merely because a reference shows their CLI.

| Trigger | Runner check and required evidence | Scope authority |
|---|---|---|
| Every artifact | Read/hash and target editability; PPTX package or supported editable-source auditor. Unknown format unverified. | [output-formats](output-formats.md) |
| Supplied manifest | Schema, inventory and declared extension validation, including optional native component trees. Dense without manifest unverified. | [visual-manifest](visual-manifest.md) |
| `diagram_grammar` | Roles and directed endpoints from reopened layout | [diagram-grammar](diagram-grammar.md) |
| `typography_hierarchy` | Actual PPTX runs or resolved per-run layout | [typography-hierarchy](typography-hierarchy.md) |
| `curve_fidelity` | Actual native PPTX custom paths; other targets unverified | [curve-fidelity](curve-fidelity.md) |
| Every PPTX | Native binding inspection; optional `--expected-connections` adds source/target and arrow expectations | [native-toolkit](native-toolkit.md) |
| Orthogonal grammar, incomplete native geometry | Named-segment audit on reopened layout | [connector-geometry](connector-geometry.md) |
| `regional_fidelity`, `fidelity_sensitive` or `structure_sensitive` | Original source vs final render via `--render-evidence` and existing Node. Structural-only declarations invoke the same auditor. | [regional-fidelity](regional-fidelity.md) |
| `surface_relations` or `surface_detail` | Native host/detail landmarks, containment and paint order | [component-fidelity](component-fidelity.md) |
| `appearance_fidelity`, `appearance_sensitive` or hybrid policy | Source color/tone probes, native/mixed paint order, hash-bound reviewer records via `--render-evidence` | [appearance-fidelity](appearance-fidelity.md) |
| `text_clearance` | Native PPTX label/path boxes. Missing contract for dense text-bearing PPTX unverified. | [text-fidelity](text-fidelity.md) |
| Hybrid policy | Asset/instance package readback within PPTX editability: bytes, names, native roles, transforms, crop, visible resolution and anchors. Other targets unverified. | [hybrid-components](hybrid-components.md) |

Feature contracts retain their exact failure, applicability and unsupported-geometry
boundaries. In particular: structural coverage cannot override color failure;
preparation masks/paint trees do not certify final rendering; native paint order
does not prove visible attachment; legacy hybrid work without appearance evidence
is unverified. Current appearance render evidence covers slide 1 only. Scope
multi-slide/source comparisons separately; never inherit a result for unaudited pages.
Do not omit difficult source items or sensitive declarations to get NOT_APPLICABLE.

## Fresh artifact evidence

- Each reopened layout document includes `artifact_sha256` matching the final
  artifact. Measure after saving/reopening, not from builder-side geometry.
- Render evidence binds artifact, source and actual rendered bytes under the
  [regional evidence contract](regional-fidelity.md). Hashes associate files; they do not
  authenticate rendering history, scientific semantics or reviewer identity.
- Changed artifacts require fresh readback/evidence and a new runner report.
  Never attach a new hash to stale geometry, images or review assertions.
- Keep reports, source traces, contracts and hashes with working QA material,
  not as private paths or extraction logs inside the visual.

## Checks outside the runner

The runner does not perform source inspection, OCR, rendering, editor interaction,
general visual approval, standalone asset extraction checks or arbitrary
semantic/negative constraints. Use [quality-rubric](quality-rubric.md) for these
obligations; a machine PASS does not waive them.

For Mermaid/Graphviz, lexical screening is not native parsing: run the installed
format-owning parser/renderer separately and record its result. The runner's
unverified parser result is not rewritten to imply it launched that tool.
Generation preflight and component replacement comparison remain operation-specific
under [hybrid-components](hybrid-components.md), not repeated default work.
