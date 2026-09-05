# Curve-coordinate and profile-fidelity contract

Use this contract when visible geometry carries quantitative or distributional meaning: dose-response and survival lines, density or ridgeline profiles, flow-cytometry histograms, trajectories, spectra, signal traces, boundaries, or contours. A curve is not decoration. Its instance count, path, peaks, valleys, shoulders, steps, crossings, and ordering may encode the result.

## Source authority

Choose the highest available source in this order:

1. native paths from the supplied SVG, PDF, EPS, or editable source;
2. supplied raw coordinates or chart data;
3. locally digitized coordinates from the visible raster;
4. a careful manual trace with recorded uncertainty;
5. a bounded evidence raster only when editable reconstruction would misrepresent the source.

When the input is raster-only, coordinate extraction recovers visible geometry, not the original numerical observations. Keep that evidence boundary in the trace record and delivery notes. Do not describe visually digitized coordinates as recovered experimental data.

## Do not replace observations with templates

- Do not generate a Gaussian, logistic, spline family, or other parametric template merely because it resembles the source category.
- A parametric curve is allowed only when supplied data or the source itself establishes that model, or when the user explicitly authorizes a redesign or schematic abstraction.
- Repeated profiles must be traced as separate instances. Do not draw one curve and shift, recolor, or rescale it when the source profiles have different peak counts, shoulders, widths, skew, steps, or tails.
- Decorative ticks or short strokes placed over a smooth curve do not count as reproducing peaks that are absent from the actual path.

## Raster-to-coordinate procedure

1. Crop each plot or ridge stack at source resolution. Deskew or calibrate axes only when the source requires it.
2. Separate curve instances by source region, baseline, color, corridor, or user-verified seed. Whole-panel vectorization is not evidence that individual series were recovered.
3. Select the visible geometry appropriate to the mark:
   - `centerline` for a thin stroke;
   - `upper_envelope` for an upward filled ridge or density profile;
   - `lower_envelope` for a downward filled profile;
   - direct native path extraction when vector source is available.
4. Store dense source-relative coordinates in a trace JSON. Keep geometry unsmoothed; limited smoothing may be used only to detect peaks for QA.
5. Fill short segmentation gaps by interpolation. A long gap, merged series, or ambiguous overlap requires targeted inspection or manual correction.
6. If points are simplified or fitted to Bézier segments, use an explicit maximum deviation and preserve every declared landmark. Fewer nodes are an editing benefit only after fidelity passes.

The local extractor supports color-guided raster profiles:

```text
python scripts/extract-curve-trace.py source.png traces/ridge-01.json \
  --bbox 100,80,220,90 --color '#65A844' --tolerance 60 \
  --mode upper_envelope
```

Repeat `--color` for a gradient or antialiased palette. Inspect the reported column coverage and longest missing run. If color segmentation is unreliable, trace the isolated curve manually rather than broadening tolerance until unrelated marks merge.

## Manifest contract

Add `curve_fidelity` whenever a `standard` or `dense` faithful reconstruction contains one or more meaning-bearing curves:

```json
{
  "curve_fidelity": {
    "basis": "source_observed",
    "measurement": "x_aligned_profile",
    "default_max_x_aligned_mae": 0.08,
    "default_peak_x_tolerance": 0.06,
    "default_peak_prominence": 0.08,
    "default_min_peak_distance": 0.06,
    "series": [
      {
        "id": "B-tcell-ridge-1",
        "source_inventory_id": "B-tcell-ridge-1-source",
        "kind": "filled_ridge",
        "source_trace": "traces/B-tcell-ridge-1.source.json",
        "output_name_regex": "^B-tcell-ridge-1-fill$",
        "expected_output_count": 1,
        "expected_peak_count": 3,
        "expected_peak_positions": [0.48, 0.61, 0.72],
        "required": true
      }
    ]
  }
}
```

`basis` is `source_vector`, `raw_data`, `source_observed`, `source_estimated`, or `user_specified`. `measurement` is currently `x_aligned_profile`. Each series must reference a chart item in `source_inventory`, a task-relative trace JSON, and a mutually exclusive output-name regex. `kind` is `line_curve`, `filled_ridge`, `density_outline`, `step_curve`, or `signal_trace`.

Use explicit peak positions only when the source supports them. For a low-resolution source, use `source_estimated`, record the ambiguity, and widen positional tolerance. Low resolution may justify uncertainty; it does not justify replacing an obvious multi-peak profile with a single peak.

## Native authoring

- Build the PowerPoint curve from the recorded coordinates using one native custom path or a small semantic group, not a bitmap.
- Preserve the curve instance as one selectable object when practical. Keep its baseline separate only when the source does.
- Prefer direct cubic or quadratic path commands when the selected backend supports them. A dense polyline is acceptable when its rendered deviation stays within tolerance.
- Verify the actual PowerPoint package after export. A preview or builder-side point array is not proof that the delivered path survived serialization.

## Audit

Run:

```text
python scripts/audit-curve-fidelity.py visual-manifest.json output.pptx --fail-on-risk
```

The current auditor reads native DrawingML custom geometry from the delivered PPTX, converts a filled path to its upper profile, and compares it with the source trace. It checks:

- exactly the declared number of output curve objects;
- no output object assigned to multiple series;
- x-aligned normalized mean absolute error;
- prominent peak count;
- peak x-position tolerance.

This numeric audit is a hard gate for declared series. It complements rendered source-versus-output crops, which remain necessary for shoulders, fine oscillations, stroke weight, fill, overlap, and optical quality. The auditor currently targets single-valued x-aligned profiles; closed loops, self-crossing paths, polar curves, and arbitrary 2-D contours require explicit landmark constraints and visual review until a matching geometry audit is declared.

## Failure conditions

Block delivery when a required curve is missing, merged, split, replaced by a template, assigned to the wrong series, or fails its declared distance or peak constraints. If reliable extraction is impossible, preserve the minimum evidence raster and disclose the limitation instead of inventing a smooth editable curve.
