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

Version 3.4.0 combines curve, text, typography, endpoint, host-surface and label-clearance checks with source-frozen visible-support extraction and structural diagnostics. The [text-fidelity contract](references/text-fidelity.md) checks actual native shafts, tips and adjacent text separately from content and font ratios. [Component fidelity](references/component-fidelity.md) separates color mismatch from missing/extra support, bidirectional pixel-boundary distance and component/hole counts; its selector mode reuses pinned ImageTracerJS without filling holes or deleting fragments. Existing color limits remain mandatory. Ambiguous segmentation, resource limits and unreviewed semantic grouping do not become passes. Run the applicable local checks through:

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
