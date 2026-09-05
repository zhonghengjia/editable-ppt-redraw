# Diagram grammar and representation invariants

Use this reference for flowcharts, timelines, cohorts, study designs, mechanisms, causal diagrams, architecture diagrams, charts, matrices, and other structured visuals. Diagram grammar is the mapping between semantic roles and their visual forms. Redesign may reorganize a composition, but it does not change this grammar unless the user explicitly authorizes a representation conversion.

## Identify the grammar before layout

1. Classify the source visual type, such as cohort flowchart, clinical pathway, timeline, mechanism, causal DAG, statistical chart, matrix, or graphical abstract.
2. Inventory semantic roles: processes, cohorts, risk sets, decisions, exclusions, outcomes, milestones, compartments, entities, interventions, causal edges, axes, marks, intervals, legends, and evidence images.
3. Record how the source expresses each role through shape class, containment, direction, line style, routing, scale, mark type, or other professional convention.
4. Separate locked semantics from mutable presentation choices before drawing.

Locked by default:

- visual or diagram family;
- role-to-shape class and role-to-mark mapping;
- topology, directionality, inclusion and exclusion logic, causal or mechanistic semantics;
- start, process, decision, branch, convergence, milestone, outcome, and terminator distinctions;
- axis type, scale, category order, uncertainty encoding, legend meaning, and evidence boundaries;
- solid, dashed, inhibitory, activating, associative, or other source-defined edge meanings.

Mutable within the same grammar:

- panel proportions, spacing, alignment, grouping, and reading-path efficiency;
- typography, palette, stroke weight, emphasis, whitespace, and decorative treatment;
- positions of labels and explanations;
- connector route geometry when the source semantics and attachment points remain intact;
- cross-panel alignment that reduces searching without changing the underlying roles.

## Authorization boundary

Changing the representation family requires explicit user authorization. Acceptable authorization names the intended change, for example: convert the flowchart into a timeline, replace the DAG with a mechanism diagram, or choose a different chart type. Requests to redraw, redesign, rethink, modernize, simplify, beautify, or improve readability do not authorize that conversion by themselves.

When authorized, record `allow_representation_change: true` and a concise `authorization` statement in `diagram_grammar`. Otherwise set `preserve_visual_type: true` and `allow_representation_change: false`.

## Role examples

### Flowcharts, cohorts, and clinical pathways

- Cohorts, risk sets, and process steps remain process-style nodes compatible with the source convention.
- Decisions remain visually distinct decision nodes when the source contains an actual decision.
- Exclusions branch from the correct point in the main flow and remain distinguishable from continuing participants.
- Outcomes and terminal states remain outcome or terminal nodes.
- Main flow, exclusion branches, convergence points, and buses retain their topology and direction.
- A circle may represent a milestone or event when that is the source grammar; it must not replace a cohort or process box merely as a stylistic modernization.

### Timelines and study windows

- Time anchors, windows, milestones, and intervals remain tied to the same temporal positions and meanings.
- A timeline may be repositioned or aligned with related modules, but it may not replace a cohort flowchart unless the user explicitly requests that conversion.

### Mechanisms, pathways, and causal diagrams

- Entities, compartments, processes, interventions, and outcomes retain their semantic classes.
- Activation, inhibition, transport, feedback, causal, and associative edges remain distinct.
- A causal DAG does not become a process flow merely because both use arrows.

### Charts, matrices, and statistical figures

- Mark type, axis direction, scale, category order, reference lines, uncertainty intervals, censoring marks, and legends retain their statistical meaning.
- A chart-type change requires explicit authorization and must not fabricate unavailable source data.

## Manifest contract

For a manifest-backed structured visual, declare:

```json
"diagram_grammar": {
  "visual_type": "cohort_flowchart",
  "preserve_visual_type": true,
  "allow_representation_change": false,
  "routing": "orthogonal",
  "node_roles": {
    "cohort": {
      "role": "cohort_process",
      "allowed_geometries": ["rect", "roundRect"],
      "output_names": ["cohort-box"]
    },
    "exclusion": {
      "role": "exclusion_branch",
      "allowed_geometries": ["rect", "roundRect"],
      "output_names": ["exclusion-box"]
    }
  },
  "edge_roles": {
    "cohort-to-exclusion": {
      "role": "exclusion",
      "output_name_regex": "^flow-cohort-to-exclusion-"
    }
  }
}
```

`node_roles` keys reference manifest module or source-inventory IDs. For connected diagrams, cover every connection endpoint. Each node-role record gives the semantic role, allowed output geometries, and exact output object names. `edge_roles` keys reference connection IDs and provide a semantic role plus a regex matching the named output line objects.

## Required QA

1. Validate the manifest with `scripts/validate-visual-manifest.py`.
2. Reopen or reparse the actual output and export layout or source inspection data.
3. Run `scripts/audit-diagram-grammar.py <manifest> <layout-json-or-dir> --fail-on-risk`.
4. Run the target-specific routing, editability, text, and rendering audits required by the selected execution profile.

Block delivery when a role object is missing, a named object uses a disallowed geometry, a semantic connection has no matching output line, or the diagram family changed without recorded explicit authorization.
