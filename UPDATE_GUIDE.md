# 更新手册

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
