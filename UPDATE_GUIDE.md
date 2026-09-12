# 更新手册

## v3.20.0：分离像素归属、透明度与前景色

本次是核心生产链的能力修改，不是针对 ROS 或某个细胞追加特例。
先逐项检查 20 个有效项目的源代码，再选择无需新模型的数学方法及已有运行库。
完整比较、采用/不采用理由与测试边界见 [研究及验证记录](research/2026-09-12-soft-layers.md)。

| 更新位置 | 当前行为 |
|---|---|
| [source_layers.py](scripts/source_layers.py) | 新增连续覆盖与前景色估计；明确授权的平滑遮挡区联合插值；记录实际修改像素、颜色约束与失败。不是语义识别或隐藏细胞器生成。 |
| [raster_components.py](scripts/raster_components.py) | 已知背景逆合成只有一个公共实现，旧 supplied-alpha 和新分层共同调用。 |
| [source_objects.py](scripts/source_objects.py)、[reconstruction_pipeline.py](scripts/reconstruction_pipeline.py) | 在原有入口接入显式 construction v2；已有二值/native v1 路线保持；选择已安装的提取解释器。 |
| [component_fidelity.py](scripts/component_fidelity.py) | 消费绑定原图、配方与全部图层文件的证据包，保留估计 RGB 和 alpha，经已有描摹器生成原生路径。 |
| [source-assembly.md](references/source-assembly.md) | 新路线唯一字段/参数规范；其余入口只引用，不复制配方定义。 |
| [test_source_layers.py](tests/test_source_layers.py) | 12 项新增测试，覆盖数学边界、修改范围、顺序无关、失败不导出、证据篡改及原生 PPTX。 |

验证结果：全量 **386 项通过、0 跳过**；通用技能格式检查通过（PyYAML 可用）。
实际保存、重开并渲染了合成透明组件与实图 ROS 诊断组件，各有原底、白底、深底三页。
输出无图片对象，透明度没有丢失；但颜色分区描摹产生明显色带，**复杂光晕外观未通过**。
主细胞交界也未通过恒定背景模型，不提高容差、不改成隐式贴图。

能力边界：这次解决“二值归属与软透明度混用”“混合 RGB 二次带底色”“平滑遮挡区被挖孔”的
生产机制缺口，但没有解决任意前背景逆解或柔和光晕的通用原生矢量拟合。
适用的连续原生 Paint 仍按原有源观察路线使用；不能把新图层色板路线宣传成无损渐变。
日常执行仅按需读技能入口和操作文档，不加载这份历史记录或 20 项研究。

## v3.19.0：原图归属标注与原生渐变接通

先阅读 21 个有效项目的关键实现，再采用现有 OpenCV 四类掩码初始化与现有
原生 Paint 输出器；没有下载模型、安装新依赖或复制另一套矢量转换框架。
逐项优缺点、裁决与验证范围见
[本轮源码比较](research/2026-09-12-source-ownership-and-paint.md)。

| 更新位置 | 实际改变 |
|---|---|
| [source_objects.py](scripts/source_objects.py) | 点观察之外支持原图笔画／多边形的确定及可能前景、背景。标注在分割前生效，保留细小断开部件，冲突不以覆盖顺序裁决；输出标注与初始化证据。 |
| [reconstruction_pipeline.py](scripts/reconstruction_pipeline.py) | 统一入口可直接消费既有 `native_components` 原生渐变／层级组件，重新核对冻结源图采色；区分审核拒绝与文件过期。 |
| [source-assembly.md](references/source-assembly.md) | 原位置更新操作说明和五种构建路线，引用既有 Paint schema，不建立第二套字段定义。 |
| [test_source_objects.py](tests/test_source_objects.py)、[test_reconstruction_pipeline.py](tests/test_reconstruction_pipeline.py) | 覆盖细线与同色邻居、四类标注、冲突与越界、源色不变，以及渐变进入保存重开的 PPTX、源采样篡改和同一组件唯一构建路线。 |
| [SKILL.md](SKILL.md)、[README.md](README.md)、[CHANGELOG.md](CHANGELOG.md) | 更新版本及能力入口。日常绘图不必加载研究报告或版本历史。 |

调用仍是 **图片转ppt skill**。标注和配方由执行者依原图生成，不要求用户逐个
写代码。标注并不自动识别科学语义；二值掩码也不是柔边抠图，不能恢复遮挡后的
原始颜色。原生渐变只用于已有接口能表达、且源图观察支持的色域。
整张铁死亡图的交界仍须用新版本重建后实际对照，不能由单元测试宣布通过。

本版保持原图、历史 PPT、其他任务构建代码及 Git 历史不动。验证结果在上述
源码比较末尾记录；本地更新不等于已发布 GitHub Release。

## v3.18.0：把拆分提取接入实际生产流程

本版解决“读了流程但没有调用提取工具”的生产衔接问题。复用上一轮已审查的
21 个项目比较，并在线复核相关上游实现；采用已有 OpenCV、ImageTracer 和
python-pptx 能力，没有复制另一套转换框架，也没有增加模型。裁决和验证范围见
[生产入口决策](research/2026-09-11-production-route.md)。

| 更新位置 | 实际改变 |
|---|---|
| [reconstruction_pipeline.py](scripts/reconstruction_pipeline.py) | 新增统一 doctor/prepare/build 入口。直接消费原有清单，提取实际边界，串联源色描摹、原生分组、保存重开和现有检查器。 |
| [validate-visual-manifest.py](scripts/validate-visual-manifest.py) | 调用生产配方的唯一验证实现，提前报告缺失步骤、错误类型和关系端点，不复制另一套内容清单。 |
| [source-assembly.md](references/source-assembly.md) | 统一命令、配方字段、组件对照图、审核与重建操作说明。替换原先只提示“自行调用 helper”的入口。 |
| [SKILL.md](SKILL.md)、[visual-manifest.md](references/visual-manifest.md)、[README.md](README.md) | 同步默认生产路由、扩展索引和适用边界，不改原有特征验收标准。 |
| [test_reconstruction_pipeline.py](tests/test_reconstruction_pipeline.py) | 源图提取到原生 PPTX 的真实调用测试，覆盖源色、多路径分组、字体比例、实际边界、旧审核/篡改/缺失输入、失败不导出和新版本不叠加。 |

使用方式不变：**图片转ppt skill**。执行者按源图确定有意义的编辑单元，再调用
统一入口，检查生成的组件对照图；不需要用户逐个填 JSON 或批准每个组件。
简单文字、矩形不强制分割，已有可靠 SVG 直接用原生路径。图片文字不会自动
OCR，曲线坐标、科学语义和组件识别仍需要观察；不支持的对象不会偷偷变成模板。

当前自动入口限定为单页、源像素坐标、忠实原生 PPTX 的四类构建操作。
其他目标、原生复杂 Paint、已有 PPT 编辑和经授权混合组件仍保留原 API，
并未宣称已全部接入新命令。构建结果标为候选，渲染与编辑器检查仍按原流程执行。

验证：原有 348 项回归加新增 16 项，共 364 项通过，无跳过；技能格式和文档
链接检查通过。真实源图的两个局部对象通过新命令生成了 2 个原生组、46 条原生
路径、0 张图片，并检查了实际 LibreOffice 渲染。仍有色阶近似、放大锯齿及少量
断开碎片未提取；未给整图保真通过结论，也未验证新 Sol/Terra 对话或 PowerPoint
交互操作。详细边界和证据口径见上述生产入口决策。

本地安装同步不等于 GitHub 发布。本轮保留既有未提交修改、原始图片、历史
PPT 和其他对话构建代码，不创建 commit、push、tag 或 Release。

## v3.17.0：从源对象提取到统一场景构建

本轮先检查两次失败的实际构建与结果，再阅读 21 个相关项目的关键实现。
逐项优缺点、采用/拒绝原因及影响矩阵见
[稳定性源码审查](research/2026-09-11-stability-review.md)。研究文件不进入日常绘图默认上下文。

| 更新位置 | 解决的问题与边界 |
|---|---|
| [source_objects.py](scripts/source_objects.py) | 从上下文和正负观察点提取候选，按实际像素支撑计算边界。可用已有颜色选择器或显式选择本机 OpenCV；不再把手填矩形当完整组件。文字交叠不自动擦除，候选仍需看原图复核。 |
| [reconstruction_scene.py](scripts/reconstruction_scene.py) | 一个源坐标变换同时管位置与字号，容器背景按归属先绘制，显式前后关系稳定排序。复用已有曲线/部件输出器，不新增矢量引擎。 |
| [source-assembly.md](references/source-assembly.md) | 新接口、调用例子与限制的唯一操作说明。入口、原生工具、像素描摹和混合组件文档直接链接此处，替换原来的孤立准备步骤。 |
| [test_source_objects.py](tests/test_source_objects.py)、[test_reconstruction_scene.py](tests/test_reconstruction_scene.py) | 回归覆盖截断、孔洞、同色干扰、保留源色、文字交叠、图层、关系绑定清单、曲线序列化和字体缩放。 |

沿用已有默认忠实/原生策略，不用通用细胞模板替代源对象，不以整图背景抹字
实现“原生可编辑”，不增加模型或降低验收阈值。已有 alpha、原生 Paint、源色
描摹和矩形绑定连接线继续走各自唯一实现。新场景不是强行更换后端的理由。

本地更新先通过回归与技能格式检查，再同步安装目录；原图、旧 PPT 和其他任务
的构建文件保持不动。此处版本表示本地功能版本，**不代表已经创建 GitHub Release**。
验证：修改前 332 项、修改后 348 项本地回归全部通过，无跳过；技能格式检查通过。
三个真实源图局部测试含 73 个原生对象、0 张嵌入图片，重新打开及 LibreOffice
渲染已核对。详细边界见稳定性审查末尾；局部通过不等于整张新图已通过，
也不代表 PowerPoint 交互编辑已经重新验证。

## v3.16.1：补齐 PDF 依赖声明

修改位置：`requirements.txt` 声明已有 PDF 功能需要的 `PyMuPDF>=1.24.3`；
`README.md` 统一安装说明；`SKILL.md` 更新版本号；`CHANGELOG.md` 记录原因。
该版本下限对应官方开始使用 `pymupdf` 模块名的版本，见
[PyMuPDF 更新记录](https://pymupdf.readthedocs.io/en/latest/changes.html#changes-in-version-1-24-3-2024-05-09)。

v3.16.0 在本机测试通过，但干净的 GitHub CI 缺少该依赖，PDF 测试导入失败。
本版从安装依赖的唯一入口解决问题，不跳过测试、不修改绘图实现或验收标准。
CI 继续使用同一个 requirements.txt；实际运行结果以对应提交的 Actions 为准。
v3.16.0 标签保留；正式发布使用新的 v3.16.1 标签。

## v3.16.0：按需阅读与流程精简

本次更新对技能的阅读、构建和验证流程进行瘦身，**不是针对某张图增加例外**。
以本地 v3.15.0 为基线，原有绘图实现、字段、数值限制、验收阈值、依赖和素材保持不变。
普通绘图只需入口及匹配功能的规则，不必读取本手册和历史更新。

### 更新位置

| 位置 | 本轮调整 |
|---|---|
| [SKILL.md](SKILL.md) | 缩短入口；按图的特征选择规则，再按实际操作读取 schema；保留忠实、原生、PPTX 默认行为和权限边界。 |
| [component-fidelity.md](references/component-fidelity.md) | 保留源几何、部件关系与验收原则，将不同操作的长规则拆出，不保留两套定义。 |
| [source-tracing.md](references/source-tracing.md) | 原始像素归属、彩色描摹、共享边界、编辑预算的唯一详细说明；可靠原生矢量不必加载。 |
| [regional-fidelity.md](references/regional-fidelity.md)；[surface-relations.md](references/surface-relations.md) | 区域保真和表面附着分别按需读取；原字段、阈值范围和失败语义未变。 |
| [native-toolkit.md](references/native-toolkit.md)；[native-paint.md](references/native-paint.md) | 常规 SVG/连接线接口与复杂部件、渐变、透明效果分开；仍使用同一序列化实现。 |
| [visual-manifest.md](references/visual-manifest.md) | 仅保留共享清单与扩展入口；不再默认加载所有组件字段。 |
| [native-component-schema.md](references/native-component-schema.md)；[hybrid-component-schema.md](references/hybrid-component-schema.md) | 分别承载原生部件树、经授权图片组件的 schema；没有新增数据结构。 |
| [execution-profiles.md](references/execution-profiles.md) | 合并重复流程表述，统一独立测试、重试和证据复用位置；次数与停止条件未变。 |
| [quality-rubric.md](references/quality-rubric.md)；[quality-runner.md](references/quality-runner.md) | 分清实际渲染复核与自动检查，更新拆分后的权威链接。 |
| [text-fidelity.md](references/text-fidelity.md)；[diagram-grammar.md](references/diagram-grammar.md) | 独立审计命令改为诊断入口，避免把已经由总检查执行的项目再跑一遍。 |
| [README.md](README.md) | 从逐版叠加功能介绍改为简明用途、调用、运行和限制说明。 |
| [test_documentation.py](tests/test_documentation.py) | 增加本地链接/锚点和规则可达性回归测试，防止拆分后形成断链或无人能发现的规则。 |

### 瘦身结果与计量口径

以 Unicode 字符数统计，不含运行日志；下列场景采用明确的固定阅读集合，按文件去重。
这衡量的是指令加载量，**不是实测模型 token、实际任务耗时或质量提升百分比**。

| 范围 | 更新前 | 更新后 | 减少 |
|---|---:|---:|---:|
| 技能入口 | 6,344 | 4,238 | 33.20% |
| 带 manifest、矩形连接线 helper 的流程图阅读集合 | 91,657 | 65,117 | 28.96% |
| 原生矢量复杂图阅读集合，不使用像素描摹或混合图片 | 163,531 | 136,049 | 16.81% |
| 全部运行指令：SKILL.md 与 references 中所有 Markdown | 189,473 | 186,521 | 1.56% |

流程图集合包含入口、execution-profiles、backend-routing、diagram-grammar、
visual-types、text-fidelity、connector-geometry、container-geometry、visual-manifest、
quality-runner、quality-rubric、native-toolkit。复杂矢量集合在此基础上包含
component-fidelity、appearance-fidelity、typography-hierarchy、icon-reconstruction、
curve-fidelity；更新后的集合还包含拆出的 regional-fidelity、native-paint、
native-component-schema、surface-relations。两者都没有省略该场景需要的规则。

主要收益来自**不加载无关操作的长文档**，而非删除保真能力。需要全部操作的任务
不会获得同样的节省，也不能据此承诺未来每张图都同样保真或少用固定数量的 token。

### 本轮与此前未发布更新的区别

本轮没有改动 v3.15.0 的 39 个既有 scripts 文件、25 个既有测试文件、5 个素材文件
和 1 个 agents 文件；仅增加文档完整性测试。上述分组的文件哈希在发布前复核。

上一个公开版本为 v3.11.0，因此本次公开更新还包含此前已在本地存在的
v3.12–v3.15 功能：执行流程归并、PDF 源绘制状态、原生混色与透明效果、共享填充域、
源颜色保留，以及本地独立图片组件准备。它们不是本次“瘦身”新写的功能。
逐版来源和边界见 [CHANGELOG.md](CHANGELOG.md)；第三方归属继续由
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) 与固定来源记录负责。

### 验证及结论边界

- 修改前：330 项本地回归测试通过，无跳过。
- 修改后：332 项本地回归测试通过，无跳过；包括新增加的链接/锚点和规则可达性检查。技能格式检查通过，既有实现分组的文件哈希全部未变。
- 用户已认可本轮完整 GAS 重建图的使用效果。此为用户验收结果，不会改写该测试已有的自动保真缺项或发布检查失败记录，也不证明所有未来图片均通过。
- 本轮未重新生成该图、未提高导入限制、未改变验收阈值、未安装新依赖或模型。
- Windows WPF 相关测试依赖 Windows；Linux CI 的平台跳过不能算该功能已验证。

## 如何更新已安装的技能

1. 先备份当前技能目录和自己的定制内容。
2. 若为 Git 克隆，先在该目录运行 `git status --short`；有本地修改时先人工审查合并，**不要强制覆盖或 reset**。干净目录可以执行 `git pull --ff-only`。
3. 若为复制安装，从本仓库对应 Release 下载版本包；解压到新目录，比对后替换该技能目录。不要覆盖个人绘图项目或历史输出。
4. 以 [SKILL.md](SKILL.md) 的 `metadata.version` 为本地版本依据；可运行系统 skill-creator 提供的 `quick_validate.py`，以及本仓库 `python -B -m unittest discover -s tests -q`。
5. 重新启动 Codex 后继续用 **图片转ppt skill** 或 **$editable-ppt-redraw** 调用。名称与自动发现策略未变。

本手册只负责更新定位、方法和版本证据；实际作图规则从 SKILL.md 进入，避免把更新历史再次带进每次绘图上下文。
