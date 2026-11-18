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
- When a source has multiple text roles, preserve their relative size and weight system rather than choosing each font size independently. Use the optional source measurements below when pixel sizing is uncertain, then [typography-hierarchy.md](typography-hierarchy.md) for the role contract and reopened-output audit. Different strings in the same font can have different visible ink heights; raw height clusters alone do not establish text roles.

## Optional source measurements

Before setting uncertain raster-source font sizes, run the existing pipeline's
`measure-text` operation against the same manifest. It reads only selected text
inventory regions and writes a new diagnostic directory; it never changes the
manifest, sends images, transcribes text or changes prepare/build behavior.

```text
python scripts/reconstruction_pipeline.py measure-text manifest.json text-measurements --font-file /fonts/Arial.ttf
python scripts/reconstruction_pipeline.py measure-text manifest.json selected-measurements --item title --item axis-title
```

`--item` is repeatable; omit it for all text items. `--font-file` is optional and
accepts one local TTF/OTF face. The report binds the original source and manifest
hashes, transcription and source box to measured ink bounds, row bands, polarity,
and uncertainty; `overview.png` and per-item crops/masks expose what was measured.
Coordinates are original source pixels; an explicit `canvas` must match source
dimensions. Fractional boxes retain their declared values and the measurement
crop rounds outward to pixel boundaries. Conversion to points uses the declared
slide width and source width, never screenshot DPI.

If the declared text box is tight, `--context-padding-px 4` adds an explicit
source-pixel inspection margin (0 by default, at most 128, clipped to the image).
The report keeps `source_bbox` and `measurement_bbox` separate; no text is moved.
Check this expanded crop for neighboring content before adopting its advice.

With a matching font family/weight and verified character coverage, the helper
fits the actual transcribed strings' local font widths/heights to the observed
bands. This avoids a universal Latin/CJK height-to-em constant. It gives advice,
not automatic typography or Office layout certification. Missing fonts/glyphs,
low contrast, mixed polarity, boundary ink, suspect rules, incompatible line counts
or poor fit retain explicit limitations and no applicable size recommendation.
No boundary-connected or tiny ink is silently deleted to make a crop look valid.

Inspect the source crop and mask, preserve intentional breaks and script runs,
then apply accepted sizes to the existing `construction.options.font_size_px`
and role tokens. Keep the text protection box distinct from the tight ink box;
do not shrink the former automatically. In a role shared by several strings,
reconcile their suggestions with the source rather than assigning a new role per
height. Rotated text, mixed run sizes, formulas and textured/low-resolution labels
still need manual or native PDF evidence. Remeasure only when source, selected
region, transcription or candidate font changes. Existing saved-file and actual
render checks remain the final typography evidence.

An apparently consistent estimate does not detect every rotated or mixed-size
run. A single baseline containing large and small characters may produce a
plausible aggregate size; do not apply that value to each run or erase subscripts.

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

For actionable locations rather than a count alone, use the optional hash-bound
PowerPoint text measurements and localized review under
[quality-runner](quality-runner.md#installed-powerpoint-evidence-optional-windows-route).
Frame-only and measured-text-bound overlaps are diagnostic categories, not an
automatic reduction of failures or a reason to tighten every label indefinitely.
Measured bounds also add overflow-only candidates for selected labels/paths;
unchanged frame checks remain in the same audit. Neither category is a glyph mask.

## Verification entrypoint

[Quality-runner](quality-runner.md) dispatches actual-object text presence,
source-declared typography ratios and named-obstacle clearance. Use standalone
auditors only for diagnosis not already covered on the same inputs. Rendering
still checks all glyphs, line breaks and visibility; those numerical checks alone
do not prove every character is unobscured.

## Office layout and text correction

Run [the existing Office verification route](quality-runner.md#installed-powerpoint-evidence-optional-windows-route)
and pass its evidence to the quality runner with the build's
`resolved-manifest.json`. The `office_text_layout` result identifies each
checked text ID, explicit and rendered line counts, frame and text bounds.
PowerPoint bounds exceeding the frame by more than 1 point are flagged
separately from line-count mismatches. This compares layout bounds in slide
points. Review intentional glyph overhangs and inspect actual renders.
Grouped, rotated, unbound and legacy measurements without line counts remain
unverified for this check. Existing text and clearance audits still apply.

For a confirmed label defect, keep the original transcription and observed
source box. Correct the native text's authored frame, uniform font size or
both. Select the frame using the original and nearby shapes and paths. Use
[source measurements](#optional-source-measurements) or font evidence for a
size change. The revision input records the SHA-256 of the canonical manifest
bytes and the reviewed changes.

```json
{
  "manifest_sha256": "<digest of canonical manifest>",
  "items": [
    {
      "id": "observed-title",
      "reason": "The source title is one line and Office wraps the current frame.",
      "frame_bbox": [80,40,600,90]
    }
  ]
}
```

The plan accepts only `frame_bbox` and `font_size_px` as edits on each named
native text recipe. Keep the plan as the revision record. Write the new manifest
beside the base so relative source and asset paths remain valid.

```text
python scripts/reconstruction_pipeline.py revise-text canonical.json changes.json revised.json
python scripts/reconstruction_pipeline.py prepare revised.json prepared-revision
python scripts/reconstruction_pipeline.py build prepared-revision build-revision
```

Use the current preparation's review for a build with applicable asset checks.
After the saved revision reopens, collect fresh Office evidence and rerun the
runner. Accept the correction when the targeted defect clears and unaffected
content, connections and layout retain their intended behavior. Compare the
changed regions and their neighbors in the actual Office render. Mixed font
runs, text inside tables and complex transformations require editing through
their own qualified routes.
