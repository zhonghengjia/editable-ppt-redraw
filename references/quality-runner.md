# Applicable local checks and evidence status

Use one runner on each final editable artifact. It invokes the existing local auditors; it does not launch a model, renderer, Office instance, network service or installer.

```text
python scripts/run-quality-checks.py output.pptx \
  --manifest visual-manifest.json --layout reopened.layout.json \
  --expected-connections connections.json --json quality-report.json --fail-on-risk
```

Only the artifact is mandatory. Omit unused optional inputs. `--profile fast|standard|dense` overrides profile selection; otherwise the manifest profile or `standard` applies. Dense work requires a manifest. Fast/standard work may use working notes, but the report then cannot assert undeclared inventory, curve or typography coverage. Profile selection cannot disable a contract already present in the manifest.

## Status contract

| Status | Meaning |
|---|---|
| `PASS` | The named machine check ran with its required evidence and found no blocking issue within its documented scope. |
| `FAIL` | The check found a violation or an invalid input. |
| `NOT_APPLICABLE` | This check does not apply to the selected format or declared features. It does not prove the feature is absent from the image. |
| `NOT_VERIFIED` | Applicable evidence is missing, unsupported or unreadable; an exception is preserved as a reason, never silently skipped. |

`automation_passed` requires every applicable machine check to be `PASS` or `NOT_APPLICABLE`. With `--fail-on-risk`, failure or missing required evidence returns nonzero. `delivery_ready` is intentionally null: no machine flag certifies visual review. The final agent separately records the rendered pages/crops inspected, source inventory coverage and unresolved limitations. Do not invent a visual sign-off to change the runner's result.

Some individual auditors retain legacy `valid`/`ok` fields describing detected errors only. Their `unverified` or `status` fields control completeness. Use the runner or the auditor's `--fail-on-risk`, not just `valid: true`, to decide whether a declared automated gate is complete.

## Applicability and provenance

- All supported artifacts receive the target editability/source check. Unknown formats remain unverified.
- A supplied manifest receives schema validation. This validates contracts, not arbitrary semantic constraints.
- Declared grammar uses reopened layout; typography uses actual PPTX runs or resolved layout; curves use native PPTX custom paths. Unsupported target/feature combinations remain unverified.
- Native PPTX connectors receive binding inspection. `--expected-connections` adds source/target and arrow expectations according to [native-toolkit.md](native-toolkit.md). Unsupported geometry is not a pass.
- Orthogonal routes require native geometry evidence or the named-segment layout audit. Line-name screening alone cannot certify route meaning or obstacle avoidance.
- Reopened layout documents must include `artifact_sha256` matching the final editable artifact to associate the inspection with that exact file. Compute it after saving and reopening; never attach a current hash to stale builder-side geometry. The hash establishes association, not authenticity or rendered accuracy.
- Mermaid/Graphviz lexical screening is not native parsing. Record a separate successful run of the installed format-owning parser/renderer before delivering; the generic runner leaves that parser check unverified because it does not launch external tools.
- Declared `regional_fidelity` uses `--render-evidence` and an existing local `--node` under [component-fidelity.md](component-fidelity.md). Missing evidence is unverified; hash/coordinate disagreement or excessive regional differences fail. Within that contract, `structure_sensitive` requires source-frozen visible-support checks. Structural PASS never overrides color FAIL; missing NumPy or complexity limits stay unverified, empty support is invalid. Pixel boundaries and complementary connectivity do not certify semantic segmentation, exact continuous topology or renderer authenticity.
- Declared `surface_relations` or `surface_detail` inventory invokes the native host/detail auditor under [component-fidelity.md](component-fidelity.md). Missing ownership contracts fail; unsupported geometry/targets remain unverified. Source boundary landmarks, sampled containment and paint order are distinct from rendered attachment, opacity and visual meaning.
- Declared `text_clearance` checks actual PPTX label boxes against selected native arrow/path geometry and other labels, under [text-fidelity.md](text-fidelity.md). Dense text-bearing PPTX without that contract remains unverified. This is distinct from text presence, font-size ratios and glyph visibility; unsupported geometry is not a pass.
- Asset integrity, icon recognition, arbitrary semantic/negative constraints, exact glyph bounds, fine curve detail and actual editor behavior remain feature-specific checks under [quality-rubric.md](quality-rubric.md). Source-versus-render inspection remains mandatory alongside regional, surface and clearance metrics. These properties are not silently inferred from the automated summary.

Retain the JSON report, artifact hash, canonical builder/manifest and task-relative trace evidence with working QA material. Do not put private source paths, temporary diagnostics or raw extraction logs on the slide. A corrected artifact needs new readback evidence and a fresh report; it cannot inherit the previous artifact's pass.
