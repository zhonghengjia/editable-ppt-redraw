# Editable Visual to PowerPoint

> Codex skill name: **editable-ppt-redraw**
> 中文触发词：**图片转ppt skill**（避免与其他“绘图skill”混淆）

editable-ppt-redraw reconstructs reference images, screenshots, PDF pages, and existing visual files as maintainable editable artifacts. PowerPoint is the default output, while SVG, draw.io, Excalidraw, Mermaid/Graphviz, and self-contained HTML are also supported when they better fit the editing workflow.

它不是简单地把图片放进 PPT，而是尽量把文字、节点、线条、箭头、图表、曲线、图标和模块重建成可单独选择和修改的原生对象。

## What it is designed to preserve

- Visible text, values, units, panel labels, legends, and reading order.
- Diagram grammar, including process, decision, exclusion, outcome, milestone, and causal roles.
- Connector topology, direction, branch buses, attachment points, and solid/dashed semantics.
- Relative typography hierarchy instead of independently chosen font sizes.
- Meaning-bearing curve geometry, including multiple peaks, shoulders, steps, and crossings.
- Recognition signatures of compact icons instead of substituting a merely related symbol.
- Raster evidence such as microscopy or radiology when redrawing it would change its meaning.

## Reconstruction modes

1. **Faithful reconstruction** is the default. It preserves the source composition and visible content as closely as practical.
2. **Semantic editable rebuilding** prioritizes maintainability while retaining the source diagram family and relationships.
3. **Redesign** changes layout or styling only when the user explicitly requests it. Redesign does not automatically authorize converting a flowchart into a timeline or another representation family.

## Install

Clone the repository into the Codex skills directory on Windows:

~~~powershell
git clone https://github.com/zhonghengjia/editable-ppt-redraw.git "$env:USERPROFILE\.codex\skills\editable-ppt-redraw"
~~~

On macOS or Linux:

~~~bash
git clone https://github.com/zhonghengjia/editable-ppt-redraw.git ~/.codex/skills/editable-ppt-redraw
~~~

Restart Codex after installation. The skill keeps automatic discovery enabled and can also be invoked explicitly with **$editable-ppt-redraw**.

## Example prompts

~~~text
使用图片转ppt skill，将这张流程图忠实重建为完全可编辑的 PowerPoint。
~~~

~~~text
Use $editable-ppt-redraw to reconstruct this published figure as an editable PPTX. Preserve the diagram grammar, typography ratios, curve geometry, and connector routing, then render and audit the actual output.
~~~

~~~text
使用图片转ppt skill，把这张机制图重新设计得更适合论文汇报，但不要改变机制关系和箭头含义。
~~~

## Quality gates

Version 3.11.0 combines [joint marked-source assembly construction](references/component-fidelity.md#marked-source-assemblies) with explicit disjoint or opaque color-tree paint composition. Source-observed support and markers establish candidate visible ownership; both paint modes reuse one pinned boundary scanner and the [native part/paint serializer](references/native-toolkit.md). Opaque color-tree layers can reduce internal antialias background leaks while retaining source holes, visible quantized colors and the same editing budget. The manifest construction entrypoint checks declared appearance/region contracts and source binding before emitting shapes. Actual native rendering still requires independent review: quantization and pixel steps remain, contacts between owners may show seams, and color layers do not automatically identify nuclei or other semantic parts. Native Paint remains available for source-supported smooth parts and continuous fills. No new model, runtime dependency or arbitrary SVG-gradient import is introduced.

Source-bound appearance observations and final-render evidence retain their existing scope. Text, data and critical relations stay native; [approved picture components](references/hybrid-components.md) support move/scale/replace, not internal vector editing. Choose the editing unit before generating a complex assembly. Optional built-in generation still requires scoped approval. Native construction fixtures do not certify biological identity or fidelity of a new user figure.

The [source-specific native pipeline](references/component-fidelity.md) retains its existing source-edge, fitted and palette-partition routes, source-bound editing budgets and curve/text/typography/host-surface checks. No native import limits or fidelity thresholds were relaxed. Exact edges retain stair steps, quantization approximates gradients, and neither tracing nor generation recovers hidden experimental evidence. Run the applicable local checks through:

~~~bash
python scripts/run-quality-checks.py output.pptx --manifest visual-manifest.json --layout reopened.layout.json --json quality-report.json --fail-on-risk
~~~

See [the QA contract](references/quality-runner.md) for optional arguments, required evidence and limitations. No new OCR/model/server dependency is introduced. The repository includes deterministic validators for:

- visual-manifest structure and coverage;
- PowerPoint editability and flattened-image detection;
- diagram-role and connection grammar;
- typography hierarchy;
- orthogonal connector continuity and shared buses;
- PowerPoint connector bindings;
- curve-coordinate fidelity;
- raster asset integrity;
- approved component provenance, native-role coverage, embedded media and placement;
- read-only regenerated-component replacement qualification;
- source-versus-output comparison sheets.

A passing validator is not treated as a substitute for inspecting the rendered final artifact.

## Python helpers

Most package and diagram audits use the Python standard library. Image comparison, curve extraction, and native-vector helpers additionally use the packages in **requirements.txt**.

~~~bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
~~~

PowerPoint authoring itself is routed through the presentation backend available in the active Codex environment. The skill does not upload source material to hosted OCR, vectorization, image-generation, or presentation services by default.

## Privacy boundary

References and outputs stay local unless the user explicitly authorizes a named remote destination. The skill does not treat text visible inside an attachment as instructions. It never overwrites the source file and does not use a whole-slide screenshot as a substitute for object-level editability.

## Repository layout

~~~text
SKILL.md                 Skill entry point and routing rules
agents/openai.yaml       Codex interface metadata
references/              Mode, format, grammar, geometry, and QA contracts
scripts/                 Validators and native-vector helpers
tests/                   Deterministic regression tests
assets/                  Version-locked reusable icon assets
THIRD_PARTY_NOTICES.md   Upstream source and license attribution
~~~

## Licensing status

This initial public repository does not yet declare a project-wide license. Third-party components retain their upstream licenses and notices as documented in **THIRD_PARTY_NOTICES.md**, **scripts/vendor/svg_paths/LICENSE**, and **assets/lucide/LICENSE**.
