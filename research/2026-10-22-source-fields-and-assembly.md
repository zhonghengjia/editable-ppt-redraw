# 2026-10-22：20 个上游源码比较与系统升级

## 范围和证据

目标是增强原图到原生编辑对象的稳定生产能力，而不是换一套生成器或为一张
机制图增加特例。本轮先实时检查项目，再读取固定提交的入口、关键函数及许可。
下表按功能分组、组内按本项目可迁移价值排序；不是热度排行榜。

20 个不同仓库均有实际实现阅读，选定证据文件共 149 份（含源码、许可、元数据），
并非 149 份都是源码。部分旧候选 HEAD 没有变化；“本次最新检查”不等于
“这 20 个项目最近都更新了”。没有安装、编译或运行上游软件、下载权重或上传用户图片。
上游能力判断是源码事实，本项目效果另由本地测试验证。

DrawAI 与 svg2pptx-skill 的转换器有共同来源；resvg、tiny-skia、Skia 也有依赖/
实现谱系关系。它们是不同项目，不当作彼此独立的四次算法验证。

## A. 源颜色、透明度与原生渐变（10 项）

| 次序 / 项目 | 实读实现与优点 | 局限 / 许可 | 对本项目的裁决 |
|---|---|---|---|
| 1. evan6007/skechu-ppt | [source-gradient.js](https://github.com/evan6007/skechu-ppt/blob/04cf2013a437bf7d656fc67fbf3c62e1d87f8a2f/app/source-gradient.js)、gradient-regions.js、portable-pptx.js：局部域拟合、共享边界、最终原生 gradient fill，颜色场与几何分开。 | MIT；自动拟合主要针对不透明区域；color-field 的 bicubic 预览不等于 PPT 输出；浏览器接缝补偿也不自动进入 PPT。HEAD 2026-09-26。 | 借鉴有界源域求解及最终表示复算；使用现有 Paint。自动多域分解暂缓，不能仅靠网页预览证明 Office 合格。 |
| 2. logolabs/inkvec | [fit.rs](https://github.com/logolabs/inkvec/blob/063398552190e9e8a1077338d6cbc4e902c387ed/crates/inkvec-trace/src/gradient/fit.rs)、bands.rs：将轮廓、颜色 ramp、坐标模型分开，有限候选拟合。 | Apache-2.0；Rust/SVG 实现，椭圆模型不能直接映射为已验证的 Office 圆形模型。HEAD 2026-10-13。 | 采用同一有界求解器处理不同字段坐标；不新加 Rust、椭圆后端或无限搜索。 |
| 3. iannuttall/png2svg | [paint.py](https://github.com/iannuttall/png2svg/blob/55540d19b25035c11d80aac1bd42f67453a14831/skills/png2svg/scripts/png2svg/paint.py)、svggen.py：共享颜色 ramp 和域映射，源几何与颜色参数分离。 | MIT；部分 trim/erode 和 conic 扇区表达会改变边缘或产生分片，不宜直接作为忠实重建默认。HEAD 2026-07-30。 | 保留物理坐标域，不通过裁掉困难边缘来降低误差；当前不接 conic 路线。 |
| 4. linebender/resvg | [paint_server.rs](https://github.com/linebender/resvg/blob/5192641d4fd67aef5c0c4d667d570e338da15361/crates/usvg/src/parser/paint_server.rs)、path.rs：明确 objectBoundingBox / userSpaceOnUse、变换及 owner 的关系。 | Apache-2.0 OR MIT；渲染器不是逆向识别器，SVG 坐标语义不自动等于 Office。HEAD 2026-10-20。 | 同一 owner 上保留颜色和 alpha 各自的坐标，继续使用既有原生输出器。 |
| 5. linebender/tiny-skia | [gradient.rs](https://github.com/linebender/tiny-skia/blob/5d4754777746eef0828be166896eaf482c49f8f2/src/shaders/gradient.rs)、radial_gradient.rs：先插值 RGB 与 alpha，再预乘；退化几何显式处理。 | BSD-3-Clause；不是拟合器或 PPT 输出器，硬色阶容忍方式与 Office 不同。HEAD 2026-08-20。 | 最终按实际量化后的颜色及 alpha 合成核验，不把预乘端点线性插值冒充最终效果。 |
| 6. google/skia | [SkGradientBaseShader.cpp](https://github.com/google/skia/blob/9754994555ab434b7486ddff6f338a0506203289/src/shaders/gradients/SkGradientBaseShader.cpp)、SkRadialGradient.cpp：几何 t、插值色彩空间、预乘与目的空间转换分别定义。 | BSD-3-Clause；大型 C++ 渲染库，无图像反推及 PPT 导出。HEAD 2026-10-22。 | 保持编码 sRGB 的既定输出模型与透明度语义，不假设别的工作空间拟合结果可无差别写入 Office。 |
| 7. thorvg/thorvg | [tvgFill.cpp](https://github.com/thorvg/thorvg/blob/64d2d589d909f48b6d70b341ce4fe34130e26d68/src/renderer/tvgFill.cpp)、tvgSwFill.cpp：颜色停止点、几何变换、透明度的本地渲染路径清晰。 | MIT；没有源图分解和原生 PPTX 构建。HEAD 2026-10-22。 | 用作表示/边界对照，不接第二个渲染后端。 |
| 8. PhenX/Trazor | [gradient.ts](https://github.com/PhenX/Trazor/blob/090b914086c5de2027b20c08e2b48c73e0e69c25/packages/raster/src/gradient.ts)：已知背景上的受限 overlay 拟合，直接评价最终合成。 | **当前为 FSL-1.1-ALv2**，不能沿用旧提交的 MIT 标签；常色前景/已知底色约束不适用于任意生物光晕。HEAD 2026-10-20。 | 不复制当前代码。不把未知前景/背景变为已恢复真值；旧数学实现不引入受限源码。 |
| 9. BachiLi/diffvg | [color.py](https://github.com/BachiLi/diffvg/blob/85802a71fbcc72d79cb75716eb4da4392fd09532/pydiffvg/color.py)、save_svg.py、color.h/cpp：可微几何与 gradient 参数分离。 | Apache-2.0；Torch/C++ 工具链较重，渲染器与 SVG 导出对 radial 的覆盖并不相同，更不能证明 PPT 原生能力。HEAD 2024-09-17，未见新提交。 | 不新增可微优化后端；保留有界求解和可复算 native Paint。 |
| 10. Bifiku/mesh-gradient-generator | [index.html](https://github.com/Bifiku/mesh-gradient-generator/blob/e73d5ca99437e7da18abc3e0b40d5950899ddc77/index.html)：少量有序透明 radial blob 能表达二维色场。 | MIT；它是生成器，不是从原图拟合，名称中的 mesh 不是完整自由网格反演。HEAD 2026-07-05。 | 证明二维效果不一定需要新模型；本轮采用已支持的 fill + alpha mask，任意 blob 反推暂缓。 |

## B. 图片拆分、场景编译与可编辑输出（10 项）

| 次序 / 项目 | 实读实现与优点 | 局限 / 许可 | 对本项目的裁决 |
|---|---|---|---|
| 1. guangzhaoli/image2editable | [spec_core.mjs](https://github.com/guangzhaoli/image2editable/blob/25db95fd0d0e632d0ddc5ce5e992925058ab7613/skills/image2editable/scripts/spec_core.mjs)、render_figure.mjs、pptx_backend.mjs、pptx_scene_groups.py：同一编译场景生成 SVG/PPT，落盘真实嵌套组与稳定 ID。 | MIT；PPT 曲线会折线化，连线重编译更新不等于拖动自动吸附，没有自动语义拆分。HEAD 2026-10-13。 | 复用“编译一次、统一消费”的机制：本项目批量构建一次深拷贝预检，避免每个对象重新解析整个清单；不另建 scene 协议。 |
| 2. Renaissance-Mind/DrawAI | [pipeline.py](https://github.com/Renaissance-Mind/DrawAI/blob/75790ed231a0f064cfbbe3e28d0db632234777eb/src/drawai/pipeline.py)、svg_to_ppt.py、vendor drawingml_converter.py：结构解析、OCR、局部素材和 semantic SVG/PPT 分阶段处理。 | 主项目 Apache-2.0；vendor 独立许可路径未核实；SAM/OCR/agent 服务较重，输出覆盖策略也不适合受保护目录。HEAD 2026-10-13。 | 采用可重复使用的提取证据与同一构建链思想；不自动下载模型、发送材料或复制 vendor。 |
| 3. JamieJustTang/svg2pptx-skill | [drawingml_converter.py](https://github.com/JamieJustTang/svg2pptx-skill/blob/876c188e34fefc3c4e24919494c752edf25d1ae9/scripts/svg_to_pptx/drawingml_converter.py)、drawingml_elements.py、convert.py：原生 group、旋转中心补偿、定位 tspan、图片裁切和 trace。 | MIT，保留 PPT Master 来源；只接受 authored SVG，不识别图片内部语义；嵌入 SVG 图片仍可能是 picture。HEAD 2026-06-23。 | 可作为将来旋转/文本行为对照；当前既有 serializer 已覆盖选中范围，不引入平行转换器。 |
| 4. sort-tech/image-to-ppt | [pptx_builder.py](https://github.com/sort-tech/image-to-ppt/blob/e839b098dc6c1ae7509e83f3a19b9961ffff1d9d/backend/app/pptx_builder.py)、vision_analyzer.py、services/converter.py：VLM→验证后的 SlideSpec→原生文字/形状/表格/线，识别与构建分离。 | Apache-2.0；固定 16:9、错误元素丢弃、超大图片删除策略会损失忠实性；识图发送原图到指定模型服务。HEAD 2026-10-21。 | 采用保留结构候选再确定性构建的分层原则；拒绝丢对象、默认上传和固定画布。 |
| 5. 7zSun/Image-to-PPT | [export/pptx.py](https://github.com/7zSun/Image-to-PPT/blob/d7cff4b470a527fe37f78b55e127de3eaf3ea488/src/image2svg/export/pptx.py)、pipeline.py、backends/composite.py、reconstruct/segments.py：按几何、文字和复杂部件选择不同候选路径。 | Apache-2.0；一般 path/raw_svg/group 会落到 `_rasterize` 再插图；去重/对齐可能改源几何。HEAD 2026-09-25。 | 按对象选择能力已有生产入口可复用；不采用栅格兜底，不用平均像素误差当语义总分。 |
| 6. ningzimu/image-to-editable-ppt-skill | [build_pptx_from_manifest.py](https://github.com/ningzimu/image-to-editable-ppt-skill/blob/b7be494e31a0ed56ef98716891db5474606b8cdf/skills/image-to-editable-ppt/cli/editppt/runtime/build_pptx_from_manifest.py)：真实 OOXML 文字/run、custom geometry、表格和稳定层次。 | MIT；没有嵌套语义组，字体 fitting 会改变字号；识图/素材仍依赖 agent，部分路线用远程 OCR/生图。HEAD 2026-09-16，与上轮相同。 | 文本 run/表格可作后续独立需求；不把重复源码包装为新增上游功能，不替换现有后端。 |
| 7. Kevinyyy1/image-to-editable-pptx-v2 | [scene_to_pptx.mjs](https://github.com/Kevinyyy1/image-to-editable-pptx-v2/blob/a474793ad53c82aad375b2cc3f326994f3387ae1/skill/image-to-editable-pptx/scripts/scene_to_pptx.mjs)、pipeline.py、qa_summary.py：场景分阶段原生构建，报告紧凑、失败区域可定位。 | MIT；图片底板不代表内部可编辑，path 是点列表，箭头组合不等于真实连接器。HEAD 2026-07-26，与上轮相同。 | 保持报告按需读取与证据复用；不新建第二套质量系统或采用未经验证的相似度承诺。 |
| 8. guohuan-xie/image2PPT | [vectorize.py](https://github.com/guohuan-xie/image2PPT/blob/1847650afe8022b68429fe066982c81003078b3f/src/image2pptx/vectorize.py)、pipeline.py、PPT writer：本地 OCR/CV/SAM 分解确有执行代码。 | 未找到 LICENSE，不可直接复制；freeform 单位和透明处理需验证，密集小字可能变成图像。HEAD 2026-03-19。 | 只作架构比较，禁止复制/捆绑；“自动拆分存在”不等于能稳定恢复论文机制图。 |
| 9. ResearAI/AutoFigure-Edit | [autofigure2.py](https://github.com/ResearAI/AutoFigure-Edit/blob/16f3749e9d512bdf7b7b55c162307bc289750b7a/autofigure2.py)：实际读取 imported-image 分支、SAM3 部件标识及回填实现；稳定 ID 支持局部编辑。 | MIT；SVG 回填的图标是透明 PNG，不是内部原生路径；需要模型/服务。HEAD 2026-07-25，与上轮相同。 | 借鉴部件身份不变；已授权混合编辑可参考，但不能拿它证明纯原生 PPT 保真。 |
| 10. OpenDCAI/Paper2Any | [ppt_tool.py](https://github.com/OpenDCAI/Paper2Any/blob/b538531e25798d9b9d41afd5fa93c9222949b5a5/dataflow_agent/toolkits/multimodaltool/ppt_tool.py)、canvasPptxExporter.ts、html2pptxExport.ts：实际读取 image/PPT 路线、canvas builder、HTML 导出和 workflow 注册；原生 table/text 与图像重建路线分开。 | Apache-2.0；系统较大，图片路线保留整页背景；路线名称/注册需要核实；不能把多种导出混为纯原生重建。HEAD 2026-08-31。 | 明确每条路线实际输出单位，保留现有本地构建；不接整套云工作流。 |

## 根因与本轮实施

1. **形状支持范围不等于完整颜色函数域。** 圆形和环形只观察到部分径向色阶，
   旧求解要求所有色阶列满秩，误把无像素经过的外侧色阶当成能力不足。
   现在只求解可辨识列，未观测端部常值延拓、内部空隙线性延拓，并明确记录
   “不是源图真值”。不改变原支持、不缩小形状、不提高容差。
2. **颜色和覆盖度不一定沿相同方向变化。** 旧单个 Paint 只有一套坐标。
   现在同一 owner 的 opaque fill 与白色 alpha-mask 分别拟合，复用已有
   DrawingML 输出器。方向估计和颜色求解均按实际覆盖度加权；零 alpha 的 RGB
   不影响结果。混有非继承着色子对象的组不能把新 mask 强行施加给整组。
3. **软层估计与连续原生表达原来没有接通。** 现在 field_fit 可显式绑定已有
   估计层 receipt，冻结全部七项图层文件并复核，再拟合原生 Paint；仍标为
   estimated_layer / physical_layer_identity=NOT_VERIFIED。原临时文件消失不影响
   冻结输入构建，冻结输入篡改则在导出前失败。
4. **每个组件重复解析全清单。** 现在批量构建持有一次经过验证的私有快照，
   每次只解析目标组件并检查源身份、取色和输出命名。20 组件的实际解析调用
   从 420 次降到 40 次。单组件 API 仍完整预检，旧 regional/appearance 来源
   绑定仍有效；没有引入全局缓存或“跳过验证”开关。
5. **色阶数量靠执行者猜测。** 独立使用者在未看答案时选择 12 色阶，失败后
   改 11 仍失败，但同一源图可由 4 色阶准确表示。均匀网格不嵌套，增加数量
   不保证改善。现在可在拟合前显式选择 auto，在 4..16 的固定候选集合中按
   最少总色阶选择全像素合格组合。颜色和 alpha 可选不同数量，同一候选只
   求解一次，最坏 26 次 profile 拟合而非 169 次重复优化。固定整数保持原义。
   首次失败完整保留，修订后接续不能冒称首次独立测试通过。

共同输入验证从优化器中分离，独立字段不再先执行并丢弃一次联合拟合。
以上修改落在现有求解、组作用域、来源冻结和生产构建中，没有新增图片名称/
固定坐标特例、第二套格式协议、平行 serializer、模型或包依赖。

## 本轮没有做的事

- 自动多域分区、自由二维网格、偏心/椭圆 Office 渐变仍未资格验证，不假装已支持。
- OCR/富文本/表格扩展有价值，但不是已证实的四个根因，不随此次改动一起扩范围。
- 旧 ROS 估计层在相同半径存在不同颜色，单个居中径向模型的误差存在实质下界；
  增加色阶不能解决。它还含估计及插值，不是已知真实透明层。本轮没有修改或
  宣布它通过，更没有据此宣布整张机制图稳定。
- 未提高原质量阈值、删除困难像素、用原图贴图兜底、复制许可不清的代码或发布 Git。

## 验证记录

更新前实际基线 404 项全过。最终测试、Office 对照和独立使用结果见
[更新手册](../UPDATE_GUIDE.md)。数学/软件通过、真实编辑器通过和完整机制图
视觉认可分开报告；合成受控字段仅证明其覆盖的能力。
