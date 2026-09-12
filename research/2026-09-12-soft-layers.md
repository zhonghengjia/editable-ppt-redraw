# 软边分层与可编辑输出：20 项源码比较及裁决

2026-09-12。范围：解释二值分割、混合前景色、文字遮挡与原生 PPTX
色带问题，并实施已批准的生产链改造。没有安装包、下载权重、替换输出后端
或上传原图。以下是源代码审阅，不是 20 个上游项目的本机运行认证。

## 根因与边界

旧二值 mask 回答“属于哪个对象”，不回答“这个像素透明多少”。把已经与
背景混合的 RGB 再附上 alpha 会二次带入底色；把文字当背景排除则留下字形孔洞。
连续覆盖与前景 RGB 需要分开估计，遮挡低频色场需要明确的未知区。

本轮实测还发现：即使前一阶段保存了连续 alpha，有限色板转原生路径仍会
离散化渐变。因此 `alpha 存在` 不等于 `外观通过`；该输出限制没有被新的数学测试解决。
使用新方法不自动授予隐藏结构生成或图片替代权限。

## 逐项目比较

按与本次问题的关系分组排列。每行给出实际检查的实现入口、优缺点和裁决。
其中 Inkscape 的主源码位于 GitLab；其余是 GitHub 项目。

| 项目与源码入口 | 可借鉴的实现 | 优点 | 限制及本轮裁决 |
|---|---|---|---|
| [PyMatting](https://github.com/pymatting/pymatting/blob/6d5c4a6bed0e/pymatting/alpha/estimate_alpha_cf.py)；另读 `cf_laplacian.py`、`estimate_foreground_ml.py`、`estimate_foreground_cf.py` | 局部颜色 Laplacian、已知/未知分块、单独恢复 F/B | 无权重，明确区分 alpha/F/B，MIT | trimap 和颜色模型敏感；包与 Numba 未安装。采用公式和已有 SciPy，**未实现其 ML 前景恢复** |
| [rembg](https://github.com/danielgatis/rembg/blob/47ac53f593ac/rembg/bg.py)：`alpha_matting_cutout`、`decontaminate_cutout`；另读 session 工厂 | 模型 mask 后分别求 alpha 与前景色 | 工程上直接处理 soft-edge fringing | 模型下载、权重许可和默认分派需单独管理；只采用阶段分离，不引入运行时 |
| [scikit-image](https://github.com/scikit-image/scikit-image/blob/v0.25.2/skimage/restoration/inpaint.py)：`inpaint_biharmonic`；另读 random walker 和 `rgba2rgb` | 平滑未知区的稀疏双调和系统；正向合成 | 无权重；仅未知像素求解，BSD | 不恢复真实纹理/语义；采用标准内部 13 点方程，用已有 SciPy 独立实现；不引入包 |
| [OpenCV](https://github.com/opencv/opencv/blob/4.x/modules/photo/src/inpaint.cpp)；另读 `grabcut.cpp`、`seamless_cloning.cpp` | 离散 GMM/图割、NS/Telea 修复与 Poisson 编辑是不同操作 | 现有安装，接口成熟 | 图割不是 alpha；NS 真实光晕试验出现方块状痕迹。保留已有 GrabCut，**NS 实现被替换**，不作为 fallback |
| [libvips](https://github.com/libvips/libvips/blob/db4e6ac0aa5c/libvips/conversion/unpremultiply.c)；另读 `premultiply.c`、`composite.cpp` | 预乘与反预乘、零 alpha 处理 | 颜色合成语义明确，批处理成熟 | LGPL、不是语义拆分；只参考零 alpha/合成边界，不引入库 |
| [ImageMagick](https://github.com/ImageMagick/ImageMagick/blob/2814fa03d043/MagickCore/composite.c)；另读 `effect.c`、`enhance.c` | Porter-Duff over、mask 曲线和滤波 | 完整的合成操作参考 | 滤波不能识别原始 alpha；未安装。复用合成方程思想，不加工具链 |
| [FBA Matting](https://github.com/MarcoForte/FBA_Matting/blob/8dd100d76018/networks/models.py)：`fba_decoder`、`fba_fusion`；另读 `transforms.py`、`demo.py` | 网络同时预测 alpha/F/B，并按合成方程融合 | 目标比单输出 mask 更贴近分层 | 缺权重/依赖；部分训练权重有非商业约束。未采用 |
| [BiRefNet](https://github.com/ZhengPeng7/BiRefNet/blob/ebcc0bc8ec7f/models/birefnet.py)；另读 `inference.py` | 梯度引导、多尺度显著对象分割 | 可生成初始对象先验 | 输出 mask 不等于正确前景色，也非科研语义识别；未采用 |
| [MODNet](https://github.com/ZHKKKe/MODNet/blob/28165a451e46/src/models/modnet.py)；另读 demo inference | 语义、细节、融合三分支 | 轻量人物 matting | 人物域不匹配机制图，不能恢复 F；未采用 |
| [RVM](https://github.com/PeterL1n/RobustVideoMatting/blob/53d74c682673/model/model.py)；另读 `decoder.py`、`inference.py` | 循环状态及前景残差/alpha 联合输出 | 视频连续性与前景估计明确 | 静态机制图无时间优势，缺权重且 GPL；未复制或采用 |
| [diffvg](https://github.com/BachiLi/diffvg/blob/master/pydiffvg/color.py)；另读 `render_pytorch.py` | 可微路径、渐变参数和渲染序列化 | 已知拓扑下能联合拟合 | 相似度可由错误层序取得；编译/PyTorch 依赖重。仅研究，不采用 |
| [VTracer](https://github.com/visioncortex/vtracer/blob/master/crates/vtracer/src/pipeline.rs)：`segment`、`finish`、`to_svg` | 分割、颜色、曲线、优化阶段分离 | 可重用前端结果，不重复分割 | 离散填色不是连续渐变；无当前运行时。保持既有描摹器 |
| [ImageTracerJS](https://github.com/jankovicsandras/imagetracerjs/blob/master/imagetracer_v1.2.6.js)：`colorquantization`、`layering`、`imagedataToTracedata` | 颜色量化→分层→边缘→路径 | 本项目已冻结版本，离线可用 | 色层不是语义组件且会产生色带；继续唯一既有描摹链，明确不承诺光晕保真 |
| [SciPy](https://github.com/scipy/scipy/blob/main/scipy/optimize/_lsq/least_squares.py)：`least_squares`；另核对 sparse solve API | 有界拟合、稀疏线性求解 | 已有安装，无模型；可显式选择求解方式 | 只解决给定方程，不选择正确模型。采用稀疏 CG/direct，不新增优化器 fallback |
| [NumPy](https://github.com/numpy/numpy/blob/main/numpy/linalg/_linalg.py)：`lstsq` | 数组颜色运算与线性代数 | 已有依赖，易做有限性/秩检查 | 方程可解不证明层可辨识；复用数组计算 |
| [Pillow](https://github.com/python-pillow/Pillow/blob/main/src/libImaging/AlphaComposite.c)：`ImagingAlphaComposite`；另读 `Image.py` | RGBA over 与图像操作 | 已有依赖，用于多背景对照 | 正向合成不反推真实 F；复用，不当成恢复算法 |
| [Inkscape](https://gitlab.com/inkscape/inkscape/-/blob/master/src/object/sp-gradient.cpp)；另读 `sp-mesh-gradient.cpp` | 渐变坐标、stops、mesh 序列化 | 成熟矢量编辑语义 | 不是原生 PPT 后端，GPL；只读参考，无源码并入 |
| [WPF](https://github.com/dotnet/wpf/blob/main/src/Microsoft.DotNet.Wpf/src/Themes/Shared/Microsoft/Windows/Themes/SystemDropShadowChrome.cs)：`CreateStops`、`CreateBrushes`；另读 `GradientStopCollection` | 多 stop 渐变/阴影组合 | Windows 现有渐变语义可参考 | 不自动反解图像，跨平台有限；保留现有能力，不新建输出器 |
| [python-pptx](https://github.com/scanny/python-pptx/blob/master/src/pptx/dml/fill.py)：`gradient`、`_GradFill`、`_GradientStops` | DrawingML 渐变、stops 和保存读回 | 已有核心依赖，原生编辑 | 路径/径向等需已有受限适配；保持既有 native Paint/emitter |
| [PptxGenJS](https://github.com/gitbrent/PptxGenJS/blob/master/src/core-interfaces.ts)：`ShapeFillProps`；另读 `gen-utils.ts`、`gen-xml.ts` | 常规形状填充和图层序列化 | 成熟 PPTX 生成 | 审阅版本公开 shape fill 不是任意渐变生成器；不另建后端 |

检索中不可访问的 `mattdesl/quantize` 未计数，以实读 ImageTracerJS 替代。
许可证记录区分代码与权重；没有按 GitHub 星数替代源码审查。

## 采用的生产设计

1. 同一入口支持二值归属和显式连续分层；原有路线不改，v2 不自动迁移旧输入。
2. `source_layers.py` 处理 trimap、闭式 matting 与单独前景逆合成。源像素矩形是计算域，
   不是通过设置 crop 来声称对象完整。恒定背景模型不满足即保留失败。
3. 平滑遮挡只在明确授权且被源观察标出的未知区联合求解。两像素观测边界保证
   13 点 stencil 有完整邻域；所有区同时求解，不依赖处理顺序。范围外 RGB 不变。
4. 共享 `unmix_background` 只有一套实现。零 alpha、近零 alpha、颜色量化可行性
   都显式处理；上调估计 alpha 的数量与幅度保留，不能把小 solver residual 当外观通过。
5. 准备收据绑定原图、配方和七个图层文件；现有 tracing 消费实际 straight RGBA，
   不再回头从原始混合 RGB 简单挂 mask。输出仍是现有原生路径/分组。

字段、边界和操作只定义在 [source-assembly](../references/source-assembly.md)，
本研究不是第二份规范。未知背景、一般多前景逆解与隐藏解剖恢复本轮不实施。

## 验证与失败证据

- 原有 374 项加新增 12 项：386 项通过，0 跳过。主 Python 与单独提取 Python
  分别使用已安装依赖，不拼接 site-packages。没有调整原有测试阈值。
- 新增测试：背景逆合成；软 alpha/前景色；直接与迭代求解一致；非法/非有限输入；
  非常量背景失败；平滑线性色场恢复；修改范围和顺序无关；源包篡改拒绝；保存重开
  原生 PPTX alpha。失败不能产生可接受的候选。
- 通用 skill YAML 格式验证通过，PyYAML 已可用。
- 实际原生 PPTX 经 LibreOffice→PDF→PyMuPDF 渲染：合成组件每页 14 个原生形状、
  14 种中间 alpha；真实 ROS 诊断每页 64 个原生形状、53 种中间 alpha；均为 0 pictures。
- 原底/白底/深底三背景都有实际渲染。合成组件平均通道误差约 0.94–1.25，
  ROS 约 7.33–7.75（0–255）；这些仅比较候选 RGBA 与导出渲染，不是源图保真指标。
- 人工与独立只读复核均观察到明显色带：**两组不授予连续外观通过**。
  低平均误差不能掩盖这点。真实 ROS 的 85,541/100,648 个未知像素还经过颜色可行
  alpha 下界调整，主细胞背景采样不满足模型；**真实 ROS 与交界区均未解决**。

结论：生产链缺口得到局部、明确范围的补足；完整机制图没有通过。没有以新规则
豁免失败或重新生成一张号称通过的整图。试验性的 NS 色场实现被原位替换，
没有 NS/biharmonic 双路线或单图坐标分支。源照片、旧 PPTX、旧试验目录保持只读。
