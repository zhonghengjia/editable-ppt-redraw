# Text fidelity and font policy

Text fidelity is the combination of exact content, explicit font intent, and rendered glyph geometry.

## Content rules

- Preserve every legible character, number, unit, symbol, capitalization choice, and intentional line break.
- Normalize generated text to Unicode NFC before authoring. Do not normalize or replace characters when the source distinction is meaningful.
- Keep uncertain readings in the manifest instead of silently substituting a plausible word.
- Put required editable strings in `source_inventory[].text`; the saved PPTX is checked at actual object level. Optional `output_slide` (one-based), `output_name` (exact), and `output_id` (OOXML string ID) scope a requirement; `required_count` is a positive minimum occurrence count, default 1. Use scopes or an explicit count for repeated labels so another panel cannot mask an omission. Unscoped requirements assert presence only; they do not automatically allocate unique matches across inventory entries.
- Matching tolerates NFC-equivalent text and whitespace, but respects Latin/numeric token boundaries: `N=55` cannot be satisfied by `N=550` or `N=55.0`. It never concatenates separate shapes into a required phrase. Punctuation, intentional line breaks, exact numeric formatting and glyph appearance still need source/render comparison.
- Reject placeholder copy, replacement glyphs, empty boxes, and common mojibake sequences.

## Font rules

- Verify that the selected font exists locally before the final build.
- When the backend exposes run-level font settings, declare both Latin and East Asian typefaces for mixed Chinese/Latin text.
- A missing explicit East Asian typeface is a warning, not automatic proof of a visible defect; render and inspect the actual output.
- Do not rely on autofit to repair incorrect geometry. Size the box and text deliberately, then use shrink-to-fit only as a guardrail when the requested backend requires it.
- When a source has multiple text roles, preserve their relative size and weight system rather than choosing each font size independently. Use [typography-hierarchy.md](typography-hierarchy.md) for the manifest contract and reopened-output audit.

## Label geometry and visible clearance

Plan text and connections together. Reserve a readable box around each complete label, matching source glyph width, line count and hierarchy before drawing arrows. Route shafts and arrowheads outside these boxes with a task-appropriate gap; an arrow may point to a label boundary, not cover its letters. Treat attached labels, adjacent headings and paragraph lines as separate relationships. Labels on their owning filled container are intentional; an unrelated arrow crossing a label is not.

Use actual paragraph/run font evidence. Some imported layouts report theme defaults at shape level while paragraphs carry the real font and size. Do not use that default as glyph width evidence. In faithful mode compare source/render line count, baselines and optical width. A non-overlapping textbox does not prove that text fits inside it; inspect overflow and unintended wrapping separately.

Correct exact text, then label box geometry and nearby arrow route/endpoint clearance, then source-supported font family, weight, size and line spacing. Do not erase characters, hide arrows under white masks, change pathway direction, shrink all text or merely raise text z-order to conceal a collision. Do not shrink the protected box below visible glyph bounds to make a numeric audit pass. Source-specific intentional intersections require explicit visual evidence and a disclosed manual limitation, not a broad exemption rule.

## Text-clearance contract (single schema authority)

For dense text-bearing PPTX, declare `text_clearance` in the manifest:

```json
{
  "text_clearance": {
    "label_names": ["label-substrate", "label-process"],
    "obstacle_names": ["reaction-shaft", "reaction-tip"],
    "min_gap_px": 1
  }
}
```

Names are exact, globally unique output names. Cover every source-inventory text with an output name and every relevant shaft, tip and other native path that can obscure a label. Use an explicit empty `obstacle_names` only when source/native inventory confirms there are no relevant path obstacles; label-label checks still run. The gap is finite, 0..20 manifest canvas pixels, chosen before correction. Declare shafts and arrowheads separately when authored as separate objects. A frame around the whole curved route is not the curve itself.

`scripts/text_clearance.py`, called through the existing runner, reparses actual PPTX text boxes and custom paths. It applies supported group transforms, tests label-label boxes and label-path segment intersections, includes half the line width as padding and recognizes closed paths covering a whole label. Path sampling reuses the existing native curve reader; it is conservative box protection, not exact glyph/pixel collision detection. It supports single custom paths and axis-aligned transforms. Unsupported objects, rotations and missing evidence remain unverified; missing/duplicate selected names and detected collisions fail. Other targets require their native layout/render equivalent without claiming this PPTX check ran.

The manifest validator checks selections, numbers and scoped inventory coverage. The quality runner leaves absent clearance for dense text-bearing PPTX `NOT_VERIFIED`. No check silently assumes a source label is absent because it was omitted from a hand-written list. Actual-render review must still check all labels, glyph overflow, path thickness, images and non-selected shapes; the numeric gate does not certify those properties.

## Verification entrypoint

[Quality-runner](quality-runner.md) dispatches actual-object text presence,
source-declared typography ratios and named-obstacle clearance. Use standalone
auditors only for diagnosis not already covered on the same inputs. Rendering
still checks all glyphs, line breaks and visibility; those numerical checks alone
do not prove every character is unobscured.
