# 阶段 1 自动结果（待人工金标准）

日期：2026-08-10

## 已完成

- 16 个代表页已从主 PDF 以 300 dpi 渲染并逐页视觉验收。
- IA DjVu XML 已提取为 16 份逐页基线。
- Tesseract 5.4.0 已完成三组 Fraktur 配置，共 48 份识别结果。
- Latin script 模型已对 5 个 Antiqua／混合语言页补跑。
- 446 页映射、模型校验值、运行日志、评分脚本和项目验证器均已生成。
- 自动验证结果为 `ready_for_human_review`；人工金标准已完成并复核 2/15 页。

## 前两个真实评分：PDF 第 21、60 页

两页均先由项目所有者逐字录入，再以本地 IA 扫描和 MDZ `bsb10600235` 对应 canvas 进行第二遍裁决。用户初稿保存在 `pilot/ground_truth/drafts/`，复核版作为评分金标准。

| Candidate | Normalized CER | WER |
|---|---:|---:|
| Internet Archive | 35.33% | 88.24% |
| Tesseract `deu_latf`, PSM 3 | 3.08% | 19.25% |
| Tesseract `Fraktur`, PSM 3 | 3.08% | 20.32% |
| Tesseract `deu_latf`, PSM 6 | 9.31% | 21.39% |

第 60 页单页结果如下：

| Candidate | Normalized CER | WER |
|---|---:|---:|
| Internet Archive | 29.35% | 86.15% |
| Tesseract `deu_latf`, PSM 3 | 3.19% | 21.33% |
| Tesseract `Fraktur`, PSM 3 | 2.72% | 17.73% |
| Tesseract `deu_latf`, PSM 6 | 3.58% | 22.44% |

两页都足以排除 IA OCR 直接翻译。`Fraktur + PSM 3` 目前以 2.90% 的两页中位 CER 暂时领先，但样本仍不足以冻结全书模型；继续按既定顺序补齐金标准。

## 不依赖金标准即可确认的现象

1. **IA OCR 只能当最低基线。** 普通正文已有大量字母替换、符号噪声和 Fraktur 系统性误认，不能直接翻译。
2. **Tesseract 显著改善可读性，但远未达到免校订。** 典型错误包括把 1828 识成 1328／4823、把 `ch` 识作 `<`、漏标题字、错专名和标点。
3. **PSM 6 会把页顶横线等噪声当成文字。** 对全页默认路线，PSM 3 暂时更稳；PSM 6 仍可在裁好的单一正文区使用。
4. **Antiqua 必须分流。** 第 44 页意大利文用 Fraktur 模型时错误明显；Latin script 模型明显改善普通字母和重音，但装饰性竖排首字母仍需人工校对／区域单独处理。
5. **特殊结构不能由纯文本 OCR 保真。** 离合诗的竖排 `PAGANINI`、目录点线、索引分区和并栏比较都需要结构标注。
6. **手稿应另走路线。** PDF 第 442 页的意大利文手稿和音乐材料在全页印刷体 OCR 下基本无结果；应标为手稿／音乐专家复核，不纳入印刷体 CER。

## 暂定全书路线

- 普通 Fraktur 正文：优先比较 `deu_latf + PSM 3` 与 `Fraktur + PSM 3`，待金标准 CER 后二选一。
- 裁切后的单一正文块：保留 `deu_latf + PSM 6` 作为候选。
- Antiqua 外语区：Latin script 模型；语言层面仍要由意大利语／法语／拉丁语读者核对。
- 目录、索引、离合诗：版面分区后 OCR，并把阅读顺序、缩进和类型作为结构数据保存。
- 手稿／音乐：不批量套印刷体 OCR。

## 为什么现在不能报准确率

CER／WER 必须以逐字人工转录为参考。当前仍有 13 个 `.gt.txt` 文件为空，因此相应行在 `reports/ocr-benchmark.csv` 中标为 `pending_ground_truth`。不能从当前两页外推整本准确率。
