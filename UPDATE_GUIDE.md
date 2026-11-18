# 更新手册

## v3.26.0 可检查并修正原生文本布局

阅读 22 个 GitHub 项目的重建、排版、对象关系及验证代码。项目星数和公开
Release 附件下载量分别排序，并逐项记录原理、适用情况和限制。
[双排行及源码对照](research/2026-11-18-detect-and-correct-comparison.md)

| 更新位置 | 变化 |
|---|---|
| [实际 Office 证据](scripts/verify_powerpoint.ps1) 与 [证据读取](scripts/office_evidence.py) | 从同一次 PowerPoint 回读取得实际行数，按稳定对象 ID 分别核对预期换行、实际行数和是否越框。 |
| [质量检查](scripts/run-quality-checks.py) | 在现有报告中按文本列出问题。确定的意外换行或越框可阻止自动通过。旧证据和不支持的变换显示未验证。 |
| [重建入口](scripts/reconstruction_pipeline.py) | `revise-text` 读取绑定原清单 SHA-256 的修正计划，为指定文本配置新框或统一字号，另存清单。原图观测区与构建用文本框分开。 |
| [文字修正说明](references/text-fidelity.md#office-layout-and-text-correction) | 通过同一个准备与构建入口重新生成。收集新成品的 Office 证据，再验证文字、字号、净空和其他对象。 |

实测样例中，标题被错误排成两行，Office 测量最大越框为 7.55 pt。按原图修正文本框后，标题恢复为一行。同时恢复脚注字号，保留右侧显式两行标签。重新打开成品后，8 个原生文本对象通过布局检查。改字和移动后保存重开均通过，实际渲染在两个修正区以外没有像素变化。

这个检查适用于本流程有对象绑定的未旋转、未分组原生文本。分组、旋转、表格内文字和混合字号需要相应的编辑器验证。图标、曲线、连线端点与图层继续走各自的检查和修正流程。

## v3.25.0：源文字测量与真实字体建议

本轮针对截图提到的
[image-to-editable-ppt-skill](https://github.com/ningzimu/image-to-editable-ppt-skill)
深入阅读关键源码和测试。它与11月6日记录为同一提交，并非新版本。
[功能优缺点、实际反例和取舍](research/2026-11-15-image-to-editable-ppt-comparison.md)
保留在研究说明，日常绘图无需加载。

| 更新位置 | 实际变化 |
|---|---|
| [source_text_metrics.py](scripts/source_text_metrics.py) | 从既有文字清单读取源区域，输出墨迹边界、行带和可查看的crop/mask；保留小点、贴边笔画和不确定性。指定匹配本地TTF/OTF后，用实际字串宽高给字号建议。 |
| [reconstruction_pipeline.py](scripts/reconstruction_pipeline.py) | 同一入口增加可选measure-text；显式源像素画布检查、分数框外取整和可选上下文边距，测量范围与排版框分开。prepare/build不增加必经步骤。 |
| [text-fidelity](references/text-fidelity.md#optional-source-measurements)、[typography-hierarchy](references/typography-hierarchy.md) | 在现有字体规则内连接前置测量与成品Office检查，不根据原始墨迹高度自动分层，不自动改清单或抹平上下标。 |
| [第三方说明](THIRD_PARTY_NOTICES.md) | 记录改编Otsu实现的固定提交并保留MIT原文；不引入上游OCR、OAuth、图像服务、安装器或另一套构建器。 |

### 用法与验证

字体难以目测时，按[text-fidelity](references/text-fidelity.md#optional-source-measurements)
运行measure-text，核对原图及测量图，再把认可的建议应用到既有字号字段。
未指定字体也能得到像素几何。字体集合TTC、复杂混合字号、旋转与纹理背景不
在自动字号建议的可靠范围；同一行混用大小字可能返回看似合理的整体值，必须
保留原始run差异。ADVISORY不等于视觉通过。

- 新增文字能力14项测试通过，包含真实Arial、深底白字、多行、细小笔画、
  贴边、低对比、错误字体/缺字、输入变更、禁止覆盖、画布不匹配和分数坐标。
- 全套520项运行：504通过、16项SciPy相关跳过；随后新增的2项坐标回归已
  包含在上述14项中，合计522个独立测试均有执行覆盖。16项跳过在已有科研
  Python中补跑，空间背景14项＋联合颜色5项全部通过（3项跨环境重复）。
  首次全套及一次科研运行遇到SciPy文件读取PermissionError；独立重新导入
  成功后重跑通过，保留首轮失败日志，未改变系统权限或安装包。
- 独立审查从新合成源图运行CLI，核对来源字节、单位、缺字、混杂内容与边界。
  审查发现显式缩放canvas与分数框适配问题后，在统一坐标入口修正；独立复验通过。
- 实际PowerPoint导出原始文字页→测量→既有prepare/build→保存重开渲染：
  8个文字区的 nominal 字号建议最大误差0.64源像素；同为32px的三种字串给出
  32.00/32.12/31.91。这个已知字体合成结果不是一般精度保证。成品保留8个
  原生文本框和1个背景矩形，改字及移动后保存重开2项通过。
- 实图机制层的识别、透明边缘、C3部件缺损没有因这次文字测试而宣告解决。
  本轮不新增云服务、不改变默认原生/已授权小组件混合策略。公开发布状态需
  单独核对，版本号更新本身不等于已推送GitHub。

## v3.24.0：固定透明度颜色分离、一次 Office 回读与 PDF 源结构

本轮先按功能和适配性比较 **24 个项目**，实际阅读固定提交的关键源码、README
与许可，再选择三项能力。另检查两个直相关高星项目作为补充。
[逐项优缺点、星数快照与采用理由](research/2026-11-06-upstream-system-upgrade.md)
不进入日常绘图默认上下文。

| 更新位置 | 实际改变 |
|---|---|
| [joint_foreground.py](scripts/joint_foreground.py)、[source_layers.py](scripts/source_layers.py) | 显式固定 alpha 后联合估计前景／背景颜色，参考 PyMatting 多尺度 2×2 更新，适配为现有 NumPy。新九文件层包仍通过同一 reader/准备/冻结链消费；旧 constant/affine 七文件结果保持。 |
| [office_evidence.py](scripts/office_evidence.py) | 将原来分散在净空检查内的 Office 证据验证提成唯一公共入口；同一次实际回读可供布局、文字净空和 HTML 复核使用。 |
| [text_clearance.py](scripts/text_clearance.py)、[run-quality-checks.py](scripts/run-quality-checks.py) | 补查 XML 框不交、但实际文字溢出后相交的情况；合并去重，预览覆盖双方实际边界。无关装饰对象不阻塞已有合格节点，所选不支持对象仍披露。 |
| [pdf_paint_scene.py](scripts/pdf_paint_scene.py) | 可选提取原生文字／字符／字体资源、图像实例变换和源绘制序号；保留隐藏文字、重复实例和未解决操作，不冒称已转换。 |
| [source-assembly](references/source-assembly.md)、[source-layers](references/source-layers.md) | 软层详细字段按需读取；原组装入口和锚点仍可发现。二值提取无需加载软层算法说明。 |
| [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md) | 明确保留 PyMatting 改编部分的 MIT 原文、固定提交和修改说明；其余研究项目没有作为新运行依赖引入。 |

### 验证结果

- 集成后的完整 Python 套件 **508 项**：PPT 环境 492 项通过、16 项因缺 SciPy
  跳过；这些16项在已有科研环境全部实际通过（该环境运行14项空间背景＋5项
  新颜色测试，其中3项跨环境重复）。没有把跳过记作通过，没有新增安装。
- 新版与旧版 constant/affine 的七 PNG 和序列化 receipt 字节一致。
  新九文件层包可在不导入 SciPy/Numba 的 PPT 环境读入、准备资产并冻结后重读。
- 已知真值的二次平滑背景测试，边界前景色平均绝对误差从带底色RGB的64.321
  降至0.166（8位RGB代码值），alpha字节不变；保存后重合成平均/最大误差
  为0.0289/0.6588。这是受控测试，不是所有科学图片的改善比例。
- 真实 PowerPoint 三例：溢出正例被新逻辑检出；无碰撞对照和原生连接图通过。
  同一次快照可支持所选节点布局与实际绑定，未推断复杂曲线路由。
- 独立使用者从原始合成PDF和候选技能出发生成1页5个原生对象、0图片的PPT。
  首版 `VISIBLE` 因 Helvetica→Arial 替代出现末字母换行，渲染检查发现后，
  一次扩大文字保护框纠正。首版失败保留，不能称首次完美。最终保存重开，
  改字／移动／改线色三项通过；独立相关51项测试通过。
- 主线程从新层包创建了两个真实旧图组件的独立诊断PPT，实际PowerPoint渲染、
  另存重开和改字／移动组件两项通过。这仅证明表示与编辑行为。
  技能格式、本地链接、文档可达性和部署文件一致性另由本机交付回执记录。

### 仍未通过的实图问题

旧 C3 的 BP@D/N 与 Astrocyte 沿用原始观察标记，仅显式改用新颜色路线做回归。
现在可以生成可审查候选，但**没有通过局部保真**：BP 浅黄色／青色附属结构在
深底上明显变弱，Astrocyte仍混入上方箭头、细枝边界存在截断。最大重合成误差
分别为52.451和32.118；低平均误差不能掩盖局部失败。两者仍标为CANDIDATE，
没有放宽旧仿射容差、改历史图或把合成测试当作全图通过。

新增方法改善的是给定 alpha 后的颜色分离，不能补回错误或遗漏的 alpha，
也不保证恢复未知纹理。这是明确可选能力，不替换旧默认、不静默fallback。
源PDF信息减少重新猜测，但仍要核对可见性和最终字体排版。

本版改动集中在通用提取、证据适配和现有检查入口；没有按图名、固定坐标或
个别案例设置运行豁免。调用名称仍为 **图片转ppt skill**／**editable-ppt-redraw**。
本次只更新本地技能及工作副本，GitHub commit/push/tag/release 未执行。

## v3.23.0：统一混合组件组装、编辑单元和可定位的复核

本轮在原生产链内修改，不增加第二套绘图器、网络服务或模型；不在执行代码中
加入案例名称、固定坐标或按图豁免。原有原生路径仍可用，新增能力显式选择。

| 更新位置 | 实际能力与边界 |
|---|---|
| [source_layers.py](scripts/source_layers.py) | 已观察背景可选择仿射颜色场，复用原 alpha 求解和前景逆合成；恒定背景旧配方保持。不是通用复杂背景抠图。 |
| [raster_components.py](scripts/raster_components.py) | `source-layer` 准备方式直接消费来源绑定的七文件层包，保留估计 RGB／alpha 身份，不重裁原图、不伪装成真实透明度。 |
| [reconstruction_pipeline.py](scripts/reconstruction_pipeline.py)、[reconstruction_scene.py](scripts/reconstruction_scene.py) | construction v4 接入批准的独立图片、语义编辑组、现有矩形绑定连接器；准备、搬移、重建都核对原图、资产和依赖。分组不改变遮挡顺序。 |
| [reconstruction_scene.py](scripts/reconstruction_scene.py)、[native_vectors.py](scripts/native_vectors.py) | 新建普通矩形与绑定线显式阻断主题默认阴影；不清理整张幻灯片、不删除明确声明的 Paint 效果。 |
| [component_assets.py](scripts/component_assets.py) | 原生组覆盖检查识别实际组身份；深层图片仍不能冒充原生对象。替换审查仍按叶子对象核对，不因父组 XML 变化误报整组被改。 |
| [verify_powerpoint.ps1](scripts/verify_powerpoint.ps1) | 本机 Office 逐页渲染、读取真实文本边界，在隔离副本中修改文字／移动／改线色并保存重开；不覆盖原件、不退出用户程序。 |
| [text_clearance.py](scripts/text_clearance.py)、[run-quality-checks.py](scripts/run-quality-checks.py) | 纯文字页也参与检查；用新鲜 Office 证据定位既有候选，区分文本框留白与实际文字包围框交叠，生成局部 HTML。旧碰撞没有自动豁免，过期布局不进入下游。 |

### 使用变化

调用名称仍为 **图片转ppt skill**。普通重建只读入口及适用功能文档，不默认加载
更新历史或研究材料。入口只调整通用组装路线一句话；参数保留在
[source-assembly](references/source-assembly.md)、[混合组件规范](references/hybrid-component-schema.md)
和[检查入口](references/quality-runner.md)，没有复制成另一套任务流程。

矩形连接仅限已有受支持端口；复杂生物曲线仍是可编辑静态路径，不保证随对象拖动。
语义组限平面、互斥、连续绘制区间。图像内部仍是像素，支持移动／缩放／替换，
不冒充每个细节都是矢量。实际编辑能力以保存重开测试为准。

### 实图边界（不能被测试数量掩盖）

旧 C3 复原文件只读重开并渲染后，33 条原净空候选仍被保留：15 条属于文本框
留白相交，18 条仍与 PowerPoint 文字包围框相交。后者不是 18 处已确认遮字；
仍需看实际画面。新逻辑是定位和分类，不是完整字形检测，也不会发现所有框外溢出。

BP@D/N 和 Astrocyte 去底的真实源图测试**未通过**。错误背景样本曾混入白边、
箭头或文字；修正后 BP 背景仍不符合本轮仿射模型。Astrocyte 仍存在近标签／淡细枝
取样问题。没有提高固定容差、抹掉细节或输出未经验证的新组件；旧图未覆盖。
因此本轮是通用生产与诊断能力升级，**不是宣布这张复杂图已全部修好**。

### 验证状态

- 更新前基线 421 项通过。最终 472 个 Python 用例分环境验证：PPT 环境
  458 项通过，跳过的 14 项 SciPy 提取用例在现有科研解释器中全部通过；没有
  安装依赖、混拼包路径或把跳过项当成通过。原恒定背景七文件产物保持字节兼容。
- PowerPoint 应用验证工具 24 项通过；技能格式检查通过。独立只读复核没有
  发现已确认阻断缺陷，其建议的非正方形／非对称裁切／90° 旋转用例已补充并通过。
- 独立使用者仅按入口及适用文档，从新合成原图完成 prepare/build。首次把
  inventory role 写成 `illustration` 被拒绝，修正为 `image` 后构建成功。
  已在原有 [manifest 字段说明](references/visual-manifest.md) 中区分模块、资产和
  inventory 的角色，不另建流程；没有把首次失败改写成首次成功。
- 主线程实际渲染发现默认主题多加阴影，修正通用创建点后，从相同源清单重新构建，
  没有编辑旧 PPT。最后渲染确认阴影消失；在隔离副本完成 5 项改字／分组移动／
  节点与标签移动／连接线改色，保存重开通过，连接绑定和端点几何仍通过。
  这是编辑行为及受控渲染验证，不代表复杂机制图全部保真；完整自动保真报告仍保留
  未运行项目，不能据此宣称全图自动验收通过。

本机升级不等于 GitHub 发布；本轮没有自动 commit、push、tag 或 release。

## v3.22.0：颜色与透明度分开重建，消除重复构建和色阶猜测

本轮重新在线核查 **20 个项目**，实际阅读关键实现及许可后，在现有生产链内
升级五项通用能力；没有新增模型、服务、依赖或第二套绘图后端。
[逐项源码优缺点与采用理由](research/2026-10-22-source-fields-and-assembly.md)
包含固定提交链接；研究报告不进入普通绘图的默认上下文。

| 更新位置 | 解决的问题与当前行为 |
|---|---|
| [source_fields.py](scripts/source_fields.py) | 圆形/环形支持只覆盖部分径向色阶时，求解可辨识列，不因未观测外侧列误拒绝；延拓明确不是隐藏真值。 |
| 同一字段求解器 | 同一对象颜色与透明度可用不同方向、半径和色阶数；使用现有原生 fill + alpha mask，零 alpha RGB 不干扰方向，禁止误伤组内独立着色子对象。 |
| 同一字段求解器及 [source-fields](references/source-fields.md) | 新增显式 `stop_count: "auto"`，在固定 4..16 候选范围内选择最少合格色阶；独立两场最多各求解每种数量一次。不放宽容差，不更换模型，固定整数旧行为保留。 |
| [reconstruction_pipeline.py](scripts/reconstruction_pipeline.py) | field_fit 可消费已绑定的估计软层，冻结 receipt 与全部七项输出；构建时复算，保持 estimated 身份。 |
| [native_components.py](scripts/native_components.py)、[reconstruction_scene.py](scripts/reconstruction_scene.py) | 批量构建只做一次完整清单快照预检，每项仍核对源身份、源采色及输出命名；20 个组件解析次数由实测 420 降为 40。 |
| [test_surface_fields.py](tests/test_surface_fields.py) | 新增受控数学、真实生产构建、完整图层冻结/篡改、透明不变性、非同数量色阶和批量行为测试。 |

### 实际验证

- 更新前基线 404 项通过；最终 **421 项通过、0 失败、0 跳过**，技能格式检查通过。
- PowerPoint 16.0 实际渲染 12 个受控结果（4 类源场 × 3 种底色），均为
  原生对象、0 图片。9 个矩形案例全像素最大 RGB 差 2/255。
- 3 个圆形案例内部最大差 2/255；每例另报告 856 个边界像素的抗锯齿差异，
  全图最大差分别 92、71、89/255、平均差 1.56、1.15、1.43/255。
  **没有把这些边缘从原图拟合/支持中删掉，也不声称圆形全像素最大差只有 2/255。**
- 在实际 PowerPoint 应用接口中移动对象、改变原生渐变色、另存、关闭并重开，
  回读通过；两种渐变和 alpha effect 均保留、0 图片。不是鼠标手动交互测试。
- 独立使用测试首次按 12/11 色阶失败、没有 PPT；暴露出均匀网格不嵌套且
  参数靠猜的问题，促成上述 auto 能力。修订后的同一独立使用者只重读操作文档，
  保持原图及 3/255 标准完成接续构建：自动 4+4 色阶，全 4,800 像素最大
  合成误差 0.003987。主线程再做三底色 Office 渲染，全像素最大差均为 2/255。
  这是**修订后接续成功**，不是把首次失败改成首次盲测成功。

### 保留的边界

此次受控色场和编辑行为通过，不代表旧 ROS、内质网或整张生物机制图全部通过。
任意多域混色、自由网格、隐藏结构恢复仍不支持；旧原图和失败产物没有被覆盖。
技能入口仍保持按需阅读，本轮只增加一行，未宣称测得固定 token 节省比例。
调用仍用 **图片转ppt skill**；本机升级和 GitHub 发布是两个动作，本轮未自动发布。

## v3.21.0：源图连续颜色直接拟合为原生渐变

本轮实际读取 20 个项目的关键源码后，选择复用已有原生 Paint 输出器，
补足源像素到连续颜色参数的计算。不是继续增加“必须有层次感”的提示词，
也不是给某张图片添加特例。逐项优缺点、许可边界和采用理由见
[源码比较与验证记录](research/2026-10-03-continuous-fields.md)。

| 更新位置 | 实际变化 |
|---|---|
| [source_fields.py](scripts/source_fields.py) | 在已确认的部件边界上拟合纯色、任意角线性及居中圆形渐变；颜色和真实 alpha 分开计算，最终按原生量化后的表示复算误差。 |
| [reconstruction_pipeline.py](scripts/reconstruction_pipeline.py) | 原有 native_component 可选择 field_fit；冻结来源与取色范围、审查、复算后使用同一个输出器。文字、图层提取、分组和硬边描摹流程不被替换。 |
| [source-fields.md](references/source-fields.md) | 新操作的唯一参数与适用范围说明；入口、外观、描摹、Paint 文档仅按条件指向它。 |
| [test_source_fields.py](tests/test_source_fields.py) | 18 项回归覆盖非正方方向、RGB/alpha、径向半径、已有透明效果、颜色资格、几何不变及来源绑定。 |

全量 **404 项通过、0 跳过**。15 个受控案例在本机 PowerPoint 16.0 实际渲染，
最大单通道 RGB 差为 3/255；另在 PowerPoint 应用接口中移动对象、修改渐变颜色，
另存并重开，回读一致。此项不是鼠标手动拖动测试。独立使用者只读技能与原始 PNG，
首次 prepare/build 生成了 0 图片、8 个原生渐变点的可编辑组件，未查看测试答案。

仍未通过：旧 ROS 估计图层在固定单个居中径向模型下误差 0.984646，大于预定 0.025。
该层本身含估计覆盖与插值，不是独立真实透明图层；本轮没有修改它或提高阈值。
因此本次是适用平滑色域的能力升级，**不能宣称旧复杂交界或整张机制图已经通过**。

调用名称仍为 **图片转ppt skill**。不需要新模型、云服务或新依赖；通常绘图不加载
本手册、源码研究或版本历史。正式 GitHub 发布仍是单独动作，本地升级不会自动发布。

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
