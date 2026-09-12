# Editable Visual to PowerPoint

> Codex skill: **editable-ppt-redraw** · 中文触发词：**图片转ppt skill**

将参考图、PDF 页面或已有视觉文件重建成可编辑对象，而不是把整张图片贴进 PPT。
默认忠实重建为 PowerPoint；也支持用户指定的 SVG、draw.io、Excalidraw、
Mermaid/Graphviz 和 HTML。具体编辑能力取决于目标格式。

**更新位置、升级方法及版本说明：[更新手册](UPDATE_GUIDE.md)**

历史变更：[CHANGELOG.md](CHANGELOG.md)。

## 能做什么

- 重建流程图、研究设计图、机制图、图表和多面板图，保留内容与关系。
- 保留文字比例、连接线方向、逐条曲线形态、图标识别特征和分组。
- 复用原始矢量；需要时从原图提取轮廓、颜色与部件归属，生成原生路径。
- 用统一准备/构建入口，把源图清单、点／笔画／区域标注提取、源色描摹、原生渐变组件和文件检查串联起来；坐标、字号和前后顺序共用一个场景。
- 用受支持的原生渐变、共享填充和透明效果表达层次。
- 对背景可观察且近似恒定的局部图像，分开估计软透明度和前景色；明确授权时插值文字遮挡下的平滑色场。它不是通用抠图或隐藏结构恢复。
- 在明确授权后使用独立图片组件，支持移动、缩放和替换；不冒充内部矢量可编辑。
- 检查实际保存文件的结构、文字、编辑性及相关几何证据，再进行渲染对照。

它不保证任意 PDF/SVG 完美转换，也不能自动恢复隐藏结构、原始实验数据或
生物学语义。色块描摹会近似渐变，复杂路径可能难以编辑；不支持的源混色仍须
保留限制说明。各接口及边界见 [native-toolkit](references/native-toolkit.md)、
[component-fidelity](references/component-fidelity.md) 与
[quality-runner](references/quality-runner.md)，不在本页重复定义。

## 安装与调用

Windows：

~~~powershell
git clone https://github.com/zhonghengjia/editable-ppt-redraw.git "$env:USERPROFILE\.codex\skills\editable-ppt-redraw"
~~~

macOS / Linux：

~~~bash
git clone https://github.com/zhonghengjia/editable-ppt-redraw.git ~/.codex/skills/editable-ppt-redraw
~~~

已有同名目录时不要覆盖；更新步骤见更新手册。重新启动 Codex 后可自动发现，
或显式使用 `$editable-ppt-redraw`。**仅说出名字不会自动安装此 skill。**

~~~text
使用图片转ppt skill，将这张图忠实重建为可编辑 PowerPoint。
保留原图的文字比例、曲线、图标和连接关系。
~~~

~~~text
使用图片转ppt skill，重新设计这张机制图的版式，
但不要改变机制关系、箭头含义或图的类型。
~~~

## 运行与验证

采用环境中已安装的目标格式工具；不会自动增加网页服务、OCR 或模型。
常规包/图形审计多数只用标准库；图像、原生组件和 PDF 功能的 Python 依赖
统一由 requirements.txt 声明（包括 PyMuPDF）。像素描摹及区域比较还需要
已有 Node；WPF 功能仅在 Windows 可用。可选的 GrabCut 候选分割使用已安装的
OpenCV；可选连续分层使用已安装的 SciPy。二者均不在基础依赖中、不自动安装，
颜色选择路线不需要它们。可显式指定独立
提取用 Python，避免与 PPTX 运行环境混装。统一构建接口及适用范围见
[source-assembly](references/source-assembly.md)。

~~~bash
python -m pip install -r requirements.txt
python -B -m unittest discover -s tests -q
python scripts/run-quality-checks.py output.pptx --manifest visual-manifest.json --json quality-report.json --fail-on-risk
~~~

按实际功能提供渲染、布局等证据，参数见质量检查手册。测试通过、用户视觉认可
和自动保真检查是不同结论，不能相互替代。

## 隐私与文件

默认本地处理；未经授权不向第三方编辑器、OCR、转换或生成服务发送材料。
原文件和历史版本不覆盖。若授权生成组件，按实际发送内容单独记录授权范围。

| 位置 | 用途 |
|---|---|
| SKILL.md | 技能入口与按需阅读路由 |
| references/ | 共享规则及条件化构建、验证 schema |
| scripts/、tests/ | 实际构建/审计能力及回归测试 |
| agents/、assets/ | 界面元数据及固定来源素材 |
| UPDATE_GUIDE.md、CHANGELOG.md | 更新手册、历史记录；普通绘图不必读取 |

## License

The repository does not yet declare a project-wide license. Third-party code and
assets retain their upstream licenses; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md),
[scripts/vendor/svg_paths/LICENSE](scripts/vendor/svg_paths/LICENSE) and
[assets/lucide/LICENSE](assets/lucide/LICENSE). Code availability does not license
unrelated artwork or model weights.
