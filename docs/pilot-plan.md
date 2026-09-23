# 阶段 1：OCR 代表页试验

## 目标

用少量、覆盖面足够的页面回答三个问题：

1. 哪个公开 OCR／本地模型最适合这一本书的 Fraktur 字体？
2. 自动版面分析在哪些页面会破坏阅读顺序或形式信息？
3. 全书处理应采用“单一模型批量跑完”，还是按正文、诗歌、目录／索引、手稿分流？

## 样本

`pilot/selection.csv` 选取 16 页：8 页普通正文／标题／引文，4 页前置页与目录，2 页离合诗，1 页索引，1 页折页手稿。前 15 页用于文本 OCR；PDF 第 442 页只评估视觉与手稿路线，不纳入印刷体 CER。

该取样是“覆盖困难类型”，不是随机抽样，所以最终误差报告要分别列出普通正文和特殊版面，不能只报一个全局平均数。

## 候选基线

- `internet_archive`：IA DjVu XML 逐行文字，代表已有的公开自动 OCR。
- `tesseract-deu-latf-psm3`：德语 Fraktur 模型，自动版面分析。
- `tesseract-deu-latf-psm6`：同一模型，假定单一文本块，用于观察正文页是否更稳定。
- `tesseract-fraktur-psm3`：多语言 Fraktur script 模型，检验混合语言页面。
- `tesseract-latin-psm3`：只运行 5 个含 Antiqua／外语的代表页，用于判断是否应按页面区域切换到 Latin script 模型。

本机试验使用 Tesseract 5.4.0.20240606。模型来自 Tesseract 官方 `tessdata_best` 仓库；本地 SHA-256 记录在 `reports/ocr-run.json`。项目不会把安装程序或模型上传 GitHub。

## 指标与判定

- 原始 CER：只统一换行编码，保留空格和行结构。
- 规范化 CER：Unicode NFC，展开连字、`ſ → s`、连续空白折叠后比较。
- WER：按规范化空白分词计算。
- 版面检查：目录、索引、离合诗和脚注另做人工“阅读顺序／结构是否保存”的通过或失败标记。

普通正文页可按下列区间安排工作量：规范化 CER 不高于 2% 可进入抽检；2%–5% 需要逐页校订；高于 5% 或阅读顺序错误则需要预处理、分栏或换模型。阈值是工作流决策线，不是学术准确性终点；最终公开转录仍要人工核对。

## 执行顺序

```text
生成页码表 → 渲染 300 dpi 样本 → 提取 IA OCR → 跑 3 组 Tesseract
        → 人工逐页制作金标准 → 计算 CER/WER → 冻结全书 OCR 方案
```

运行命令见仓库根目录 `README.md`。生成物位置：

- 试验图：`pilot/images/page-NNN.png`（本地，不进 Git）
- 候选 OCR：`pilot/ocr/<candidate>/page-NNN.txt`
- 人工金标准：`pilot/ground_truth/page-NNN.gt.txt`
- 报告：`reports/ocr-benchmark.csv` 与 `reports/ocr-benchmark.md`

## 依赖

- Python 3.10+ 与 `pypdf`。
- Poppler 的 `pdftoppm`，用于 300 dpi 渲染。
- Tesseract 5.x。
- `tools/tessdata_best/deu_latf.traineddata`
- `tools/tessdata_best/Fraktur.traineddata`
- `tools/tessdata_best/Latin.traineddata`

没有 Tesseract 时，`run_tesseract.py` 会给出明确错误；其余阶段仍可运行。
