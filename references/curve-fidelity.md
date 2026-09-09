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
5. Interpolate only bounded interior gaps. The extractor requires observed crop endpoints, column coverage of at least 0.90, and a longest gap no greater than 0.05 of crop width by default. Set `--min-column-coverage` and `--max-gap-fraction` from source quality before extraction; do not relax them to obtain a passing output. Failed evidence produces `status: fail`, empty points, and a nonzero CLI exit, not a fabricated complete curve. Inspect merged series or ambiguous overlaps separately.
6. If points are simplified or fitted to Bézier segments, use an explicit maximum deviation and preserve every declared landmark. Fewer nodes are an editing benefit only after fidelity passes.

The local extractor supports color-guided raster profiles:

```text
python scripts/extract-curve-trace.py source.png traces/ridge-01.json \
  --bbox 100,80,220,90 --color '#65A844' --tolerance 60 \
  --mode upper_envelope
```

Repeat `--color` for a gradient or antialiased palette. Trace schema 2 records the source SHA-256, crop, mode, baseline normalized to crop height, threshold values, coverage and interpolated column indices. Coordinates retain crop-relative amplitude; each ridge is not independently rescaled to a unit peak. Use the same crop/baseline frame in the builder. For downward profiles specify the baseline explicitly, usually `--baseline-y 0`. Failed traces cannot be consumed by the auditor. Schema 1 remains readable as legacy peak-normalized evidence and cannot establish absolute amplitude fidelity. If segmentation merges unrelated marks, isolate the series or record manual coordinates with uncertainty.

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

The auditor identifies each actual object by slide part and shape ID, then selects its native component path. Names are selectors, not identity keys. It applies shape flips and axis-aligned nested-group transforms before comparing every matched instance. It checks:

- exactly the declared number of output curve objects;
- no selected output path assigned to multiple series;
- x-aligned normalized mean absolute error;
- prominent peak count;
- peak x-position tolerance.

Optional series fields are `output_path_index` (zero-based, required for a multi-path object), `coordinate_frame` (`shape` by default or `slide_bbox`), `output_bbox` (slide inches `[x,y,width,height]`, required for `slide_bbox`), and `profile_mode` (`upper_envelope`, `lower_envelope`, or `centerline`). `expected_output_count` counts objects before component selection. The default frame compares intrinsic shape geometry, not absolute slide placement; use an explicit slide frame to check placement and scale. Different source traces require separate series declarations.

Nonzero rotation, unsupported path commands, multiple contours, ambiguous envelopes and incomplete group transforms are reported as unverified failures for required series. Open paths must be single-valued and cover the declared x frame. Cubic and quadratic segments are sampled at 16 subdivisions, followed by a 201-point comparison grid: this is a bounded profile diagnostic, not an exact continuous-path or microscopic-oscillation certificate.

This numeric audit is a hard gate for declared series. It complements rendered source-versus-output crops, which remain necessary for shoulders, fine oscillations, stroke weight, fill, overlap, and optical quality. The auditor currently targets single-valued x-aligned profiles; closed loops, self-crossing paths, polar curves, and arbitrary 2-D contours require explicit landmark constraints and visual review until a matching geometry audit is declared.

## Failure conditions

Block delivery when a required curve is missing, merged, split, replaced by a template, assigned to the wrong series, or fails its declared distance or peak constraints. If reliable extraction is impossible, preserve the minimum evidence raster and disclose the limitation instead of inventing a smooth editable curve.
