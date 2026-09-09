# Typography hierarchy contract

Use this contract when a reference contains three or more visibly distinct text roles, especially dense scientific figures, multi-panel diagrams, graphical abstracts, dashboards, posters, and flowcharts with titles, node labels, annotations, and footnotes.

## Preserve ratios, not isolated font sizes

A reconstruction can contain every word and still fail visually when small source notes are enlarged to body-text size or when headings lose their contrast. Treat typography as a role system:

- identify text roles before choosing target font sizes;
- estimate each role's source rendered height from representative glyphs, excluding surrounding blank space;
- choose one stable baseline role, normally `body`, `node_label`, or `axis_title`;
- record every other role as a ratio to that baseline;
- scale the entire role system to the target canvas, then round to practical target-format sizes;
- preserve weight, line count, alignment, and capitalization separately from size.

Do not derive ratios from text-box height alone. A box may contain padding, rotation, or multiple lines. Use visible glyph height, local OCR bounds, PDF text metrics, or a careful manual estimate. When the reference is too small for reliable measurement, set `basis` to `source_estimated`, widen tolerance, and record the uncertainty.

## Manifest contract

Add `typography_hierarchy` to a standard or dense visual manifest when relative text scale materially affects the design:

```json
{
  "typography_hierarchy": {
    "basis": "source_observed",
    "measurement": "resolved_font_size",
    "baseline_role": "axis_title",
    "default_tolerance": 0.12,
    "default_max_intra_role_spread": 0.10,
    "default_max_intra_object_run_spread": 0.50,
    "roles": {
      "panel_label": {
        "target_ratio": 1.35,
        "output_name_regex": "^panel-[ABC]-label$"
      },
      "axis_title": {
        "target_ratio": 1.0,
        "output_name_regex": "(^A-.*-x-title$|^panel-A-.*-y-title$|^C-[xy]-title$)"
      },
      "footnote": {
        "target_ratio": 0.56,
        "tolerance": 0.15,
        "output_name_regex": "^(A-bottom-(definitions|assay)|B-assay-notes)$"
      }
    }
  }
}
```

`basis` is one of:

- `source_observed`: ratios were measured from reliable source text or glyph bounds;
- `source_estimated`: the source is low resolution, so ratios are bounded estimates;
- `user_specified`: the user supplied the hierarchy;
- `redesign_system`: a new hierarchy is part of an explicitly authorized redesign.

`measurement` is currently `resolved_font_size`. It is a deterministic proxy for hierarchy, not proof of rendered equivalence. `baseline_role` must exist in `roles` and have `target_ratio: 1.0`. Every role requires a positive `target_ratio` and a non-empty `output_name_regex`. `tolerance` is a fractional deviation from the target ratio. `required` defaults to `true`. `max_intra_role_spread` limits unintended size drift among objects assigned to the same role.

`default_max_intra_object_run_spread` limits `(largest non-exempt run - smallest non-exempt run) / representative object size`; a role may override it with `max_intra_object_run_spread`. The default 0.50 is an anomaly threshold, not a promise of source-level typographic parity. Set tighter source-supported values before building. `allow_script_runs` defaults to true and excludes baseline-shifted runs no larger than the normal body size. A large non-script label requires a bounded `run_exceptions` entry with `text_regex` (full-run match), nonempty `reason`, `min_size_ratio` and `max_size_ratio`. Exceptions must reflect the source, not hide a failed test.

Keep role regexes mutually exclusive. A text object matching more than one role is a contract error because the intended hierarchy is ambiguous.

## Authoring procedure

1. Create a text-role inventory from the source before setting target sizes.
2. Measure or estimate representative source glyph heights for every role.
3. Normalize the measurements to the baseline role and record the ratios.
4. Define one font-size token per role in the canonical builder. Do not scatter unrelated numeric sizes across drawing calls.
5. Apply tokens consistently. Use a role-specific exception only when the source visibly contains that exception.
6. Export the actual output. For PowerPoint, audit the native PPTX package so text-run sizes are read from OOXML; for another target, reopen it and export layout JSON.
7. Run the hierarchy audit and then inspect the rendered slide. The numeric audit catches flattened hierarchy; the render remains authoritative for wrapping, font substitution, and optical balance.

## Audit command

```text
python scripts/audit-typography-hierarchy.py visual-manifest.json output.pptx --fail-on-risk
```

The audit accepts reopened `.layout.json` for other targets. Each text element should include `runs: [{text, fontSize, baseline}]`, with baseline 0 for ordinary text, and `runEvidenceComplete`. Legacy `resolvedFontSizes` can establish spread but not script/text exceptions; a lone object median cannot establish run-level completeness.

PPTX inspection resolves explicit run sizes, paragraph defaults, local list-level defaults and stored normal-autofit scale. It does not guess layout/master/theme inherited fonts. Unresolved runs are reported as `NOT_VERIFIED`, and `--fail-on-risk` returns nonzero. A resolved layout from the target renderer can supply the missing evidence. Normal-run medians remain the role-size proxy; explicit script runs do not flatten that role baseline.

Reports separate role ratios/spread, per-object run spread, used exceptions and unresolved evidence. `valid` describes detected violations; use `status` and `unverified` for completeness. Missing required roles, ambiguous assignments, ratio violations and unexplained run-size drift block acceptance.

## Correction order

When the audit or render shows a hierarchy problem, correct in this order:

1. role assignment and baseline choice;
2. source ratio estimate;
3. target font-size tokens;
4. text-box geometry and line breaks;
5. font weight and line spacing;
6. optional optical adjustment within the declared tolerance.

Do not make footnotes larger merely to fill empty space. Do not shrink a whole panel to fix one oversized title. Do not use autofit as the primary hierarchy mechanism.
