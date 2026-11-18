# image-to-editable-ppt-skill 源码对照与选择

核对日期：2026-11-15。截图项目是
[ningzimu/image-to-editable-ppt-skill](https://github.com/ningzimu/image-to-editable-ppt-skill)。
创建于2026-05-21，查询时3359 stars、180 forks，MIT。最新提交为
`b7be494e31a0ed56ef98716891db5474606b8cdf`（2026-09-16），与本项目
2026-11-06补充检索记录一致。因此这是对同一版本的深入检查，不是发现新版本。
星数是查询快照，不代表实现或视觉质量。

## 架构及关键代码

下表链接均固定到实际阅读的提交。除入口文档，还追读对应调用与测试。

| 能力 | 实现、优点 | 限制与本项目决策 |
|---|---|---|
| 文字预测量 | [page_text_metrics.py](https://github.com/ningzimu/image-to-editable-ppt-skill/blob/b7be494e31a0ed56ef98716891db5474606b8cdf/skills/image-to-editable-ppt/cli/editppt/runtime/page_text_metrics.py)：Otsu双极性阈值、局部墨迹、行带、紧边界；[text_hints.py](https://github.com/ningzimu/image-to-editable-ppt-skill/blob/b7be494e31a0ed56ef98716891db5474606b8cdf/skills/image-to-editable-ppt/cli/editppt/runtime/text_hints.py)整页分块与层级提示。可减少目测字号。 | **采用局部测量机制**；直接复用已有source_inventory。不给不同字符串的原始字形高度自动分层；不把经验em系数当精确字号。 |
| OCR | [paddle_text_hints.py](https://github.com/ningzimu/image-to-editable-ppt-skill/blob/b7be494e31a0ed56ef98716891db5474606b8cdf/skills/image-to-editable-ppt/cli/editppt/runtime/paddle_text_hints.py)可给文本内容/框，局部再测量。 | 依赖外部配置/上传，识别仍可能合并或漏项。本轮不接入；既有本地/native PDF证据继续可用。 |
| 独立素材板 | [process_asset_sheet.py](https://github.com/ningzimu/image-to-editable-ppt-skill/blob/b7be494e31a0ed56ef98716891db5474606b8cdf/skills/image-to-editable-ppt/cli/editppt/runtime/process_asset_sheet.py)、[split_alpha_components.py](https://github.com/ningzimu/image-to-editable-ppt-skill/blob/b7be494e31a0ed56ef98716891db5474606b8cdf/skills/image-to-editable-ppt/cli/editppt/runtime/split_alpha_components.py)：命名region保留离散笔画，透明图保留alpha，处理后对账。 | 对已授权生成的稀疏素材板有价值；连通域不等于语义对象，region内相邻对象不会自动辨认。本地已有源对象/原生路径/独立图片资产冻结链，不再加平行素材台账。 |
| 色键 | [remove_chroma_key.py](https://github.com/ningzimu/image-to-editable-ppt-skill/blob/b7be494e31a0ed56ef98716891db5474606b8cdf/skills/image-to-editable-ppt/cli/editppt/runtime/remove_chroma_key.py)从纯背景距离得到alpha。 | 主体颜色接近色键、细小浅色附件仍可能消失；不能用于一般科学原图恢复。本轮不接入默认路线。 |
| 原生表格 | [native_tables.py](https://github.com/ningzimu/image-to-editable-ppt-skill/blob/b7be494e31a0ed56ef98716891db5474606b8cdf/skills/image-to-editable-ppt/cli/editppt/runtime/native_tables.py)：矩形合并、行列比例、可编辑cell、统一预览和校验。 | 相关11项本机测试通过，是可采用的后续能力。需接入本地现有场景和逻辑读回，避免按整个XML树相等判定Office兼容。本轮先补频繁出现的字体问题，表格暂缓。 |
| 原生曲线 | [path_geometry.py](https://github.com/ningzimu/image-to-editable-ppt-skill/blob/b7be494e31a0ed56ef98716891db5474606b8cdf/skills/image-to-editable-ppt/cli/editppt/runtime/path_geometry.py)：连续线单对象、Bezier、端点箭头/虚线。 | 本地已有源坐标路径、实际分组及矩形连接关系，不引入第二个路径转换器；曲线路径也不等于数据关联图表。 |
| 输入与备注 | [_input_normalization.py](https://github.com/ningzimu/image-to-editable-ppt-skill/blob/b7be494e31a0ed56ef98716891db5474606b8cdf/skills/image-to-editable-ppt/cli/editppt/runtime/_input_normalization.py)、prepare_deck_run.py：页序、源比例、PDF渲染和备注提取。 | 合成PPTX探针发现单大图快提取丢失裁切/旋转；旧.ppt路径有未定义args，见下文。保留实际Office渲染优先，不整体移植。 |
| 可恢复多页执行 | [deck_run_state.py](https://github.com/ningzimu/image-to-editable-ppt-skill/blob/b7be494e31a0ed56ef98716891db5474606b8cdf/skills/image-to-editable-ppt/cli/editppt/runtime/deck_run_state.py)、record_page_dispatch.py、record_page_result.py、finalize_deck_run.py：明确页面归属、重用已验证资产、按manifest重建最终deck。 | 面向多页有用；本地已有prepare/build与来源绑定。单页科研图不强制另起安装、并发lease或多状态文件；新增编排保留为真实多页需求。 |
| 构建与验收 | [build_pptx_from_manifest.py](https://github.com/ningzimu/image-to-editable-ppt-skill/blob/b7be494e31a0ed56ef98716891db5474606b8cdf/skills/image-to-editable-ppt/cli/editppt/runtime/build_pptx_from_manifest.py)、[validate_pptx.py](https://github.com/ningzimu/image-to-editable-ppt-skill/blob/b7be494e31a0ed56ef98716891db5474606b8cdf/skills/image-to-editable-ppt/cli/editppt/runtime/validate_pptx.py)：直接OpenXML、库存/比例/曲线/表格检查。 | Pillow预览不是Office渲染；最终deck校验有媒体缺失漏检。本地保存重开、实际Office及已哈希资产检查继续使用。 |
| 指令组织 | [SKILL.md](https://github.com/ningzimu/image-to-editable-ppt-skill/blob/b7be494e31a0ed56ef98716891db5474606b8cdf/skills/image-to-editable-ppt/SKILL.md)、page-decision-tree.md、manifest-schema.md、page-worker.md按操作分层。 | 一处规则一处权威值得保留；所有前景必须图像编辑、不允许本地原生重建的要求不适合科研保真；不搬入隐式上传或OAuth处理。 |

## 实际探针，区分能力与边界

在隔离目录使用已安装依赖读取源码、执行选定测试。没有配置上游OCR/图像API，
没有读取认证令牌，也没有将用户图片上传给上游服务。

- 同一Arial32px，`xxxxxx`、`HHHHHH`、`Hybrid group`的ink高分别为17、23、29px，
  上游原始高度分组成为3个层级。其Latin列在1px→1pt的诊断画布上给出23.5、32、40.5pt。
  这是同字体不同字串的反例，不能将它推广为所有图的误差率。
- 上游边界清理可将贴边文字的墨迹宽从63缩成38px，返回仍为ok。
  新测量保留该墨迹并提示边界问题；不给清理后的伪精确建议。
- 红字/绿底灰度相近时，灰度分离不可靠；标明限制，不猜字号。
- 构建/表格/路径/校验相关53项上游测试通过52项；1项在Windows失败于仅macOS
  默认字体候选。表格相关11项全部通过。不将这个平台失败概括为项目不可用。
- 单图片PPTX设左右25%裁切和180度旋转后，快提取仍输出未变换原始图片；
  同例普通备注字符串保留成功。旧.ppt在替身转换器成功后复现args未定义，
  不冒称实际运行了LibreOffice转换。
- 合成deck删除`ppt/media/image1.png`后，page校验拒绝，而deck校验仍返回通过。
  这是最终分支漏检，不能用该结构结果替代编辑器打开和嵌入资产检查。

## 本轮实施边界

在既有reconstruction_pipeline增加可选measure-text，读取已有清单并输出source
crop、ink mask、overview及来源绑定报告。保留边界与小点，不静默清理；指定
本地字体时用真实字串的宽高拟合字号，保留字体覆盖/风格/行数/低对比等限制。
建议经源图核对后写回既有font_size_px，prepare/build和最终Office验收保持原状。
这属于增加构建前能力，不是给某张图加坐标例外，也不新设必经门禁。

MIT复用范围与原许可见[第三方说明](../THIRD_PARTY_NOTICES.md)。
实际本地验证与未完成边界记入[更新手册](../UPDATE_GUIDE.md)。既往C3软层缺损
不属于这次文字改进的已解决事项。
