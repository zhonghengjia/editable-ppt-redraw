# Text fidelity and font policy

Text fidelity is the combination of exact content, explicit font intent, and rendered glyph geometry.

## Content rules

- Preserve every legible character, number, unit, symbol, capitalization choice, and intentional line break.
- Normalize generated text to Unicode NFC before authoring. Do not normalize or replace characters when the source distinction is meaningful.
- Keep uncertain readings in the manifest instead of silently substituting a plausible word.
- For a dense manifest, place required editable strings in `source_inventory[].text`; pass the manifest to `audit-pptx-editability.py` so missing strings are detected after save.
- Reject placeholder copy, replacement glyphs, empty boxes, and common mojibake sequences.

## Font rules

- Verify that the selected font exists locally before the final build.
- When the backend exposes run-level font settings, declare both Latin and East Asian typefaces for mixed Chinese/Latin text.
- A missing explicit East Asian typeface is a warning, not automatic proof of a visible defect; render and inspect the actual output.
- Do not rely on autofit to repair incorrect geometry. Size the box and text deliberately, then use shrink-to-fit only as a guardrail when the requested backend requires it.
- When a source has multiple text roles, preserve their relative size and weight system rather than choosing each font size independently. Use [typography-hierarchy.md](typography-hierarchy.md) for the manifest contract and reopened-output audit.

## Rendered bounds

- Compare actual glyph bounds, baseline, line count, and visual width against the source.
- One-line labels and headings must remain one line unless the source wraps.
- Slide-canvas overflow is blocking. Container-boundary warnings require inspection of rotation, alignment, margins, and visible clipping.
- Correct in this order: exact text, box position and size, font family and weight, font size, line spacing, then optional wording changes only when the user authorized redesign.

## Audit command

```text
python scripts/audit-pptx-editability.py output.pptx --manifest visual-manifest.json --fail-on-risk
python scripts/audit-typography-hierarchy.py visual-manifest.json output.pptx --fail-on-risk
```

The editability audit checks required text, placeholder text, suspicious mojibake, zero-byte media, top-level slide bounds, duplicate borders, and raster dominance. The typography audit checks source-declared role ratios and intra-role consistency. Rendering is still required because OOXML font declarations and font-size ratios do not prove visual parity.
