# Host-surface relationship evidence

Read when the source has attached bands, ribs, markings or other host-bound details. Shared geometry planning is in [component-fidelity](component-fidelity.md).

## Host-surface relationship evidence (single schema authority)

For faithful manifest-backed work, mark every observed attached detail `surface_detail: true` in `source_inventory`. Add `surface_relations` with `source_sha256` and a `relations` list. Each relation has:

- `id`, `source_inventory_id`: unique relation and source detail identities; one relation per detail.
- `host_name`, `detail_name`: exact, globally unique native output names. Each selects one closed custom path; use separate relations for independently visible fragments. Do not invent hidden continuation to fit this profile.
- `host_landmarks`, `detail_landmarks`: 3–100 boundary points each, measured in decoded source pixels before building. Include source-observed endpoints, bends and edge contacts rather than only convenient corners. Keep the crop/measurement provenance with the task. These landmarks must not be extracted from the output being evaluated.
- `occluders`: explicit list of foreground native object names, including an empty list when none. The current auditor supports single closed paths and validates paint order, not optical visibility or opacity.
- `max_landmark_error_px`, `max_escape_px`: finite, nonnegative source-pixel tolerances, bounded at 20 pixels by the audit profile. Choose tighter task-appropriate values before authoring; never enlarge them after a failure. `max_escape_px` bounds how far the detail may lie outside the host's sampled boundary.
- `source_observation`: concise visible evidence for attachment and the chosen tolerance. Describe uncertain or occluded source boundaries explicitly.

The existing manifest validator enforces IDs, numeric bounds and inventory coverage. The quality runner invokes `scripts/surface_relations.py` against the actual PPTX, reusing the native path reader and axis-aligned group transforms. It checks host/detail boundary landmarks, half-source-pixel sampled containment and native paint order. Nonzero rotations, compound/multi-path objects, missing transforms or unsupported targets remain unverified; duplicate/missing identities and geometric violations fail. This bounded geometric sampler is not a general exact boolean/3D surface solver. Preset shapes needed by a relation must be represented by a supported native path or verified separately without claiming this gate passed.

Reopen and render the actual artifact. Compare each relationship at delivered size and 4–8×: surface curvature, band widths/spacing, edge termination, negative gaps, foreground occlusion and translucent interactions. Record each relation as PASS, FAIL or NOT_VERIFIED with the crop and concrete observation. Machine geometry and regional color checks are supporting evidence; neither proves visible attachment. This applies to anatomy, instrument markings, membranes, layered machinery and other source-specific illustrations, not only one scientific figure.
