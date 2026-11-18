# 2026-11-06：24 项高星/高相关项目源码比较与系统升级

这是本轮工程证据地图，不是系统综述或效果排行榜。先检查现有 v3.23.0 的完整调用链和旧问题，再由三条独立研究线分别阅读8个项目的README、实际许可和关键实现；主线程汇总后裁决。星数是当日GitHub API快照，维护时间为仓库push时间，不等于commit作者时间。以下按对本技能的可迁移价值排序，不按星数排序。没有安装或运行上游项目、模型或云服务；源码审查不能冒称准确率实测。

## 逐项结论

| 排名/项目（stars） | 功能 | 实读关键源码 | 优点/可迁移机制 | 缺点/限制 | 决定 |
|---|---|---|---|---|---|
| 1. [pymatting/pymatting](https://github.com/pymatting/pymatting) (1,923) | 颜色分离 | [pymatting/foreground/estimate_foreground_ml.py](https://github.com/pymatting/pymatting/blob/6d5c4a6bed0e5672abac0bad078e594423ffe4fd/pymatting/foreground/estimate_foreground_ml.py) | 固定alpha，多尺度联合F/B、局部2×2解；比再接一次alpha求解有实际新增能力 | 平滑先验不恢复隐藏真值；上游依赖Numba，不能直接在本机运行 | 采用算法结构，NumPy适配并保留MIT归属 |
| 2. [pymupdf/PyMuPDF](https://github.com/pymupdf/PyMuPDF) (11,078) | PDF源提取 | [src/__init__.py](https://github.com/pymupdf/PyMuPDF/blob/28b271bbfb42d13a084346d255d3b8b2e3b96544/src/__init__.py) | public API暴露文字span/字符、font、image CTM和paint seqno，复用现有源解析器 | AGPL/商业双许可；并非完整PDF→PPT，clip/shading/softmask仍可能未知 | 扩展现有可选content evidence；不复制AGPL实现 |
| 3. [scanny/python-pptx](https://github.com/scanny/python-pptx) (3,582) | 原生PPT | [src/pptx/shapes/freeform.py](https://github.com/scanny/python-pptx/blob/278b47b1dedd5b46ee84c286e77cdfb0bf4594be/src/pptx/shapes/freeform.py) | 成熟对象树、包关系与文本读写，可复用现有后端 | 公共freeform仅move/line/close；fit_text不是源字号真值 | 保留主后端及已有底层曲线序列化 |
| 4. [danielgatis/rembg](https://github.com/danielgatis/rembg) (25,361) | 组件接口 | [rembg/bg.py](https://github.com/danielgatis/rembg/blob/991927b77667946dab59c50df31f7d4640e80457/rembg/bg.py) | decontaminate与alpha_matting分离，支持独立颜色处理 | 当前默认BRIA权重另有许可；session可下载，云后端可传图；部分后处理二值化 | 借鉴拆分接口，不引入整包/默认模型 |
| 5. [docling-project/docling](https://github.com/docling-project/docling) (70,207) | 坐标与来源 | [docling/document_converter.py](https://github.com/docling-project/docling/blob/55f21d6a439a236965542f4fd2f21d8366306b93/docling/document_converter.py) | 原生PPT后端记录page/bbox/charspan/坐标原点和组变换 | shape外框不是Office文字实测；组旋转未处理，完整框架较重 | 复用provenance思想到现有Office证据适配 |
| 6. [gitbrent/PptxGenJS](https://github.com/gitbrent/PptxGenJS) (6,355) | PPT曲线 | [src/gen-xml.ts](https://github.com/gitbrent/PptxGenJS/blob/3c9ec1b687c174952166f6a34b5e87ebf69fa469/src/gen-xml.ts) | 原生custGeom支持cubic/quadratic/arc，可参照对象建模 | SVG入口仍media而非原生；换JS后端会重复维护 | 保留现有等价能力，不换后端 |
| 7. [opencv/opencv](https://github.com/opencv/opencv) (91,470) | 归属提取 | [modules/imgproc/src/grabcut.cpp](https://github.com/opencv/opencv/blob/43f8b1f5dacd967e5f632dd4a45109f182d41dce/modules/imgproc/src/grabcut.cpp) | 成熟四类GrabCut保留hard seeds；本机已有 | 二值support不等于alpha；inpaint不能恢复真实隐藏结构 | 复用现有路线，不重复包装或升级cv2 |
| 8. [scikit-image/scikit-image](https://github.com/scikit-image/scikit-image) (6,634) | 背景插值 | [src/_skimage2/restoration/inpaint.py](https://github.com/scikit-image/scikit-image/blob/e098ebbb684788df60b42e3bde112c014d0d9517/src/_skimage2/restoration/inpaint.py) | biharmonic源码明确边界、稀疏解和通道范围 | 推断平滑色不恢复纹理；本机已有同类算子 | 保留已有实现；本轮不叠加第二种自动fallback |
| 9. [visioncortex/vtracer](https://github.com/visioncortex/vtracer) (7,472) | 共享边界 | [crates/vtracer/src/lib.rs](https://github.com/visioncortex/vtracer/blob/e71343fbcbf469b8a72a255030408a39939162eb/crates/vtracer/src/lib.rs) | 新mosaic共享面边界，单次拟合再反向使用可降低独立边缘裂缝 | 当前1.0.0-alpha.4接口变化大；需要新Rust/绑定资格测试 | 暂缓，不能因高星替换稳定默认 |
| 10. [jankovicsandras/imagetracerjs](https://github.com/jankovicsandras/imagetracerjs) (1,547) | 彩色描摹 | [imagetracer_v1.2.6.js](https://github.com/jankovicsandras/imagetracerjs/blob/cb0c84a309df5e75614d3b5166cdc77a56f12a98/imagetracer_v1.2.6.js) | 成熟小型本地JS颜色分区、轮廓拟合；现有固定版本 | 离散颜色不能无损表示连续渐变，细节/对象数要权衡 | 保持既有固定引擎，平滑色域走native Paint |
| 11. [RapidAI/RapidOCR](https://github.com/RapidAI/RapidOCR) (8,463) | 源文字候选 | [python/rapidocr/main.py](https://github.com/RapidAI/RapidOCR/blob/a538d3a75e26ca7ac521da8602842b9d6e5a872d/python/rapidocr/main.py) | 轻量多后端，返回原图坐标与分数、字词框 | 字词框由识别列估算，不是真实glyph；需固定模型和依赖 | 可选未来adapter，本轮真实文字QA无需OCR |
| 12. [PaddlePaddle/PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) (92,369) | 源文字候选 | [paddleocr/_pipelines/ocr.py](https://github.com/PaddlePaddle/PaddleOCR/blob/dab3fe35379033fdcb2d0e9572fac0b36c9a9ebf/paddleocr/_pipelines/ocr.py) | 明确模型目录、阈值、方向及结构模块，适合复杂文档 | 整套PaddleX/VLM代价大，预处理变换需要逆映射 | 不新增默认模型，保留将来最小子管线路径 |
| 13. [tesseract-ocr/tesseract](https://github.com/tesseract-ocr/tesseract) (77,383) | 源文字候选 | [src/api/baseapi.cpp](https://github.com/tesseract-ocr/tesseract/blob/c21194d06998e244754d65329d6c9f1e14fe392e/src/api/baseapi.cpp) | 成熟TSV/hOCR层次框与置信度，可离线固定入口 | pointsize按行高/yres折算；截图DPI不等于字号真值 | 不替代Office测量，不新增环境 |
| 14. [microsoft/playwright](https://github.com/microsoft/playwright) (99,451) | 审查界面 | [packages/playwright-core/src/server/screenshotter.ts](https://github.com/microsoft/playwright/blob/58d69dcc392af3a6994eab0323dc2e883f05f396/packages/playwright-core/src/server/screenshotter.ts) | 截图等待字体、处理动画/裁切，结果可稳定命名 | 浏览器布局不是PowerPoint真值 | 保留审查页用途，本轮不新增强制浏览器测试栈 |
| 15. [facebookresearch/sam2](https://github.com/facebookresearch/sam2) (20,109) | 交互对象候选 | [sam2/sam2_image_predictor.py](https://github.com/facebookresearch/sam2/blob/2b90b9f5ceec907a1c18123530e92e794ad901a4/sam2/sam2_image_predictor.py) | 正负点、box、先前logits与多候选有助归属 | 默认二值/logits不是coverage；模型/CUDA后处理与细枝风险 | 暂缓，未来仅显式导入候选support |
| 16. [ZhengPeng7/BiRefNet](https://github.com/ZhengPeng7/BiRefNet) (4,376) | 高分辨率候选 | [inference.py](https://github.com/ZhengPeng7/BiRefNet/blob/f7079632d681ecf12161fcea8905682934e59e51/inference.py) | 区分segmentation和matting权重；原分辨率可保留更多候选细节 | 推理不分解F/B；科学插图效果与GPU环境未测 | 暂缓，不拿模型表当本项目保真证据 |
| 17. [tdewolff/canvas](https://github.com/tdewolff/canvas) (1,848) | 矢量几何 | [path.go](https://github.com/tdewolff/canvas/blob/09804640d00c5753b00ee0a449c88ad2338d13cf/path.go) | 仿射椭圆与路径机制完整，可参照几何算法 | Go绘图栈扩大维护面，既有SVG profile不含任意矩阵 | 保留受支持profile，不引入第二个转换器 |
| 18. [yWorks/svg2pdf.js](https://github.com/yWorks/svg2pdf.js) (838) | SVG解析 | [src/nodes/path.ts](https://github.com/yWorks/svg2pdf.js/blob/4c57644c9e766d7c62a7189cc9a04687a6cd62ee/src/nodes/path.ts) | DOM+jsPDF路径与文本流程有明确能力分层 | 目标PDF，不保证PPT原生；浏览器字体与Office不同 | 研究参照，不复制或新增运行依赖 |
| 19. [kieler/elkjs](https://github.com/kieler/elkjs) (2,882) | 授权重排 | [src/js/elk-api.js](https://github.com/kieler/elkjs/blob/bddee3a807b5ff6324a1f1af79d1f95105637458/src/js/elk-api.js) | 端口、层次、正交布局适合复杂有向图 | 不能从图片恢复布局；EPL许可；尺寸需调用方提供 | 仅将来授权重排候选，不擅改忠实布局 |
| 20. [dagrejs/dagre](https://github.com/dagrejs/dagre) (5,848) | 授权重排 | [lib/layout.ts](https://github.com/dagrejs/dagre/blob/877ead2bb0d5822daeb44ccb4396be1ebccbc9e4/lib/layout.ts) | 小型有向图rank/ordering/position实现成熟 | 当前动态历史WeakMap影响重复布局；默认宽高0不测字 | 不为当前问题添加第二布局引擎 |
| 21. [ZHKKKe/MODNet](https://github.com/ZHKKKe/MODNet) (4,388) | 人像alpha | [demo/image_matting/colab/inference.py](https://github.com/ZHKKKe/MODNet/blob/28165a451e4610c9d77cfdf925a94610bb2810fb/demo/image_matting/colab/inference.py) | 低分辨率语义/高分辨率细节/融合三分支 | 人像域不能外推机制图；缩放与缺F颜色分解 | 不采用默认科学插图路线 |
| 22. [xuebinqin/U-2-Net](https://github.com/xuebinqin/U-2-Net) (9,895) | 显著性候选 | [u2net_test.py](https://github.com/xuebinqin/U-2-Net/blob/ac7e1c817ecab7c7dff5ce6b1abba61cd213ff29/u2net_test.py) | 成熟nested U结构，模型示例清晰 | 320缩放、minmax预测不等于物理alpha；旧demo恒定预测除0风险 | 不作为软层/细枝保真终点 |
| 23. [opendatalab/MinerU](https://github.com/opendatalab/MinerU) (83,226) | 文档理解 | [mineru/types.py](https://github.com/opendatalab/MinerU/blob/8cd08422055858f55a64dff79f942318b51b96cc/mineru/types.py) | 4.1 DocVortex统一producer/page/schema，可参照来源设计 | 当前许可有额外商业/在线归属条件；不是可编辑PPT生成器 | 不引入复杂文档VLM代替已有Office |
| 24. [microsoft/markitdown](https://github.com/microsoft/markitdown) (194,160) | 内容抽取 | [packages/markitdown/src/markitdown/converters/_pptx_converter.py](https://github.com/microsoft/markitdown/blob/7482c092d9c0074a89803c9fdb63a969e7fe17fc/packages/markitdown/src/markitdown/converters/_pptx_converter.py) | 内容转换入口成熟，高星且广泛使用 | PPT按阅读内容输出，不保存paint order或编辑视觉 | 任务相关性较低，不因星数最高就集成 |

## 固定版本与许可核查

许可描述来自实读文件，模型/图片/字体不自动继承代码许可。没有复制未获许可的实现；使用已安装PyMuPDF公共API也不改变其许可。

| 项目 | HEAD | 最近push UTC | 许可 |
|---|---|---|---|
| pymatting/pymatting | [6d5c4a6bed0e](https://github.com/pymatting/pymatting/commit/6d5c4a6bed0e5672abac0bad078e594423ffe4fd) | 2026-09-08T13:39:16Z | MIT |
| pymupdf/PyMuPDF | [28b271bbfb42](https://github.com/pymupdf/PyMuPDF/commit/28b271bbfb42d13a084346d255d3b8b2e3b96544) | 2026-11-06T11:40:16Z | AGPL-3.0 |
| scanny/python-pptx | [278b47b1dedd](https://github.com/scanny/python-pptx/commit/278b47b1dedd5b46ee84c286e77cdfb0bf4594be) | 2024-08-07T17:36:44Z | MIT |
| danielgatis/rembg | [991927b77667](https://github.com/danielgatis/rembg/commit/991927b77667946dab59c50df31f7d4640e80457) | 2026-11-06T01:18:29Z | MIT core; weights separate |
| docling-project/docling | [55f21d6a439a](https://github.com/docling-project/docling/commit/55f21d6a439a236965542f4fd2f21d8366306b93) | 2026-11-06T14:51:41Z | MIT |
| gitbrent/PptxGenJS | [3c9ec1b687c1](https://github.com/gitbrent/PptxGenJS/commit/3c9ec1b687c174952166f6a34b5e87ebf69fa469) | 2025-11-28T20:17:14Z | MIT |
| opencv/opencv | [43f8b1f5dacd](https://github.com/opencv/opencv/commit/43f8b1f5dacd967e5f632dd4a45109f182d41dce) | 2026-11-06T15:21:52Z | Apache-2.0 root plus Intel BSD-type headers in the two inspected files |
| scikit-image/scikit-image | [e098ebbb6847](https://github.com/scikit-image/scikit-image/commit/e098ebbb684788df60b42e3bde112c014d0d9517) | 2026-11-03T20:39:06Z | BSD-3-Clause general; LICENSE lists BSD-2-Clause and MIT exceptions |
| visioncortex/vtracer | [e71343fbcbf4](https://github.com/visioncortex/vtracer/commit/e71343fbcbf469b8a72a255030408a39939162eb) | 2026-10-22T14:45:27Z | MIT |
| jankovicsandras/imagetracerjs | [cb0c84a309df](https://github.com/jankovicsandras/imagetracerjs/commit/cb0c84a309df5e75614d3b5166cdc77a56f12a98) | 2023-11-09T14:37:05Z | Unlicense |
| RapidAI/RapidOCR | [a538d3a75e26](https://github.com/RapidAI/RapidOCR/commit/a538d3a75e26ca7ac521da8602842b9d6e5a872d) | 2026-11-06T04:15:25Z | Apache-2.0 |
| PaddlePaddle/PaddleOCR | [dab3fe353790](https://github.com/PaddlePaddle/PaddleOCR/commit/dab3fe35379033fdcb2d0e9572fac0b36c9a9ebf) | 2026-09-16T03:31:50Z | Apache-2.0 |
| tesseract-ocr/tesseract | [c21194d06998](https://github.com/tesseract-ocr/tesseract/commit/c21194d06998e244754d65329d6c9f1e14fe392e) | 2026-11-02T18:20:18Z | Apache-2.0 |
| microsoft/playwright | [58d69dcc392a](https://github.com/microsoft/playwright/commit/58d69dcc392af3a6994eab0323dc2e883f05f396) | 2026-11-06T09:20:47Z | Apache-2.0 |
| facebookresearch/sam2 | [2b90b9f5ceec](https://github.com/facebookresearch/sam2/commit/2b90b9f5ceec907a1c18123530e92e794ad901a4) | 2026-05-30T02:29:40Z | Apache-2.0; README includes checkpoints; fonts and optional cctorch separate |
| ZhengPeng7/BiRefNet | [f7079632d681](https://github.com/ZhengPeng7/BiRefNet/commit/f7079632d681ecf12161fcea8905682934e59e51) | 2026-10-25T20:40:33Z | MIT repository; exact external weights not separately reviewed |
| tdewolff/canvas | [09804640d00c](https://github.com/tdewolff/canvas/commit/09804640d00c5753b00ee0a449c88ad2338d13cf) | 2026-09-23T21:43:31Z | MIT |
| yWorks/svg2pdf.js | [4c57644c9e76](https://github.com/yWorks/svg2pdf.js/commit/4c57644c9e766d7c62a7189cc9a04687a6cd62ee) | 2026-10-29T10:46:54Z | MIT |
| kieler/elkjs | [bddee3a807b5](https://github.com/kieler/elkjs/commit/bddee3a807b5ff6324a1f1af79d1f95105637458) | 2026-10-28T13:00:37Z | EPL-2.0; source SPDX EPL-2.0 OR GPL-3.0-or-later |
| dagrejs/dagre | [877ead2bb0d5](https://github.com/dagrejs/dagre/commit/877ead2bb0d5822daeb44ccb4396be1ebccbc9e4) | 2026-10-24T21:46:51Z | MIT |
| ZHKKKe/MODNet | [28165a451e46](https://github.com/ZHKKKe/MODNet/commit/28165a451e4610c9d77cfdf925a94610bb2810fb) | 2024-05-06T14:28:28Z | Apache-2.0; README excludes doc/gif |
| xuebinqin/U-2-Net | [ac7e1c817eca](https://github.com/xuebinqin/U-2-Net/commit/ac7e1c817ecab7c7dff5ce6b1abba61cd213ff29) | 2024-06-26T04:16:45Z | Apache-2.0 repository |
| opendatalab/MinerU | [8cd084220558](https://github.com/opendatalab/MinerU/commit/8cd08422055858f55a64dff79f942318b51b96cc) | 2026-11-06T09:31:36Z | MinerU Open Source License (Apache-2.0 plus additional terms) |
| microsoft/markitdown | [7482c092d9c0](https://github.com/microsoft/markitdown/commit/7482c092d9c0074a89803c9fdb63a969e7fe17fc) | 2026-10-28T15:33:14Z | MIT |

## 为什么选这三项

1. **组件颜色能力**：本地已有闭式alpha和constant/affine背景反解，继续加分割模型不能直接解决边缘带底色。引入显式固定alpha联合F/B颜色估计，允许非均匀背景候选；保留来源、硬标记、残差与推断身份。旧配方不改变，不自动切换算法。
2. **一次真实Office回读**：已有实际TextRange bounds，但旧净空检查只对XML框产生的候选分类，会漏掉框外文字溢出才造成的交叠。复用同一份新鲜Office证据生成布局并补扫实际bounds；不新增OCR、不增加平行门禁。
3. **更多源结构**：已有PDF路径/绘制状态抽取，直接补文本span/字符/字体与图像实例CTM比从渲染图片再猜更可靠。保留seqno关联的不确定性、未表达paint operations及未执行转换状态；不宣传任意PDF自动无损转PPT。

## 指令和生产链

常用入口保持特征路由。soft-layer完整字段从共用source-assembly移动到按需的source-layers，原锚点只留路由；二值组件无需加载软层算法说明。新版依旧使用一套prepare/build、一个layer reader、一套Office证据验证、一套质量runner。研究报告与变更历史不进入普通绘图默认阅读。

## 补充直相关项目（不用于凑24项）

- [ppt-master](https://github.com/hugohe3/ppt-master/tree/769547394107870a0c7b5ad8d1c0c75035123aef)：网页约74.2k stars，MIT。读README相关段、compact_svg_styles的继承/压缩机制及delivery checker入口。其样式集中有助减少重复SVG声明，但本地原生Paint/manifest已有共同样式；未因这一思路复制整个框架。并未完整审计该项目所有文件。
- [image-to-editable-ppt-skill](https://github.com/ningzimu/image-to-editable-ppt-skill/tree/b7be494e31a0ed56ef98716891db5474606b8cdf)：网页约3.3k stars，MIT。实读page_text_metrics与process_asset_sheet；Otsu双极性墨迹、line bands和资产分离是有用机制，但字号估计仍用CJK/Latin经验比例、组件默认面积过滤可能丢微小科学细节；还涉及可配置外部OCR与图像服务。我们采用Office真实边界并保留现有来源绑定资产，不照搬认证或传图流程。
- scientific-illustrator与DrawAI取得身份/HEAD，但后续原始文件请求429中断；未算作完整源码研究，也未据此采用实现。

## 验证边界

研究完成不等于新增能力通过。旧源图、旧PPT及既有未提交升级都受保护。本轮实施和实际验证结果由更新手册记录。已知C3复杂图的旧失败仍是旧失败；新合成实验或源证据提取不能把它改写成全图保真通过。

