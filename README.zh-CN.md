[English](README.md) | [简体中文](README.zh-CN.md)

# 《Paganini's Leben und Treiben》中文翻译项目

本仓库用于制作 Julius Max Schottky 1830 年帕格尼尼传记的可核查中文译本。项目不把“识别文字—直接翻译”视为一个黑箱，而是保留扫描底本、逐页转录、规范化德文、中文翻译和注释之间的对应关系。

原书使用 Fraktur（德语哥特体）排印，字形、连字和复杂版面让自动识别容易出错。项目以人工逐页校订建立金标准，并用独立馆藏扫描本交叉核对；[现有来源调查](docs/source-audit.md)尚未找到易于获取的完整中文电子译本，这不等于断言其他译本不存在。

## 当前状态

- 阶段 0：底本和网络版本核查已完成初版。详见 [`docs/source-audit.md`](docs/source-audit.md)。
- 阶段 1：16 页 OCR 试验包的自动流程已经建立；15 页需要人工金标准，其中 PDF 第 21、60 页已复核，第 115 页仍在人工校对。详见 [`STATUS.md`](STATUS.md) 和 [`docs/manual-review-guide.md`](docs/manual-review-guide.md)。
- OCR 默认模型尚未确定；全书批量 OCR、全书校勘、中文翻译、线上阅读器与排版出版均未完成。

## 数据层

```text
扫描底本 → 外交式转录 → 规范化德文 → 中文翻译 → 注释
   │            │              │            │
   └────────────稳定页码／区域标识────────────┘
```

其中“外交式转录”保留原书拼写、标点、段落和诗歌结构；“规范化德文”只处理换行断词、字形变体等机器处理问题；中文译文不覆盖原文。

计划中的阅读器会让读者并排查看原页、德文转录和中文译文，并追溯每段文字的来源。当前仓库还没有阅读器。未来的英文／简体中文界面设计见 [`docs/reader-architecture.md`](docs/reader-architecture.md)。

## 仓库结构

- `data/`：来源与页码映射。
- `docs/`：底本调查、编辑规则和人工校对指南。
- `pilot/ocr/`：代表页的候选 OCR 文本；不是校订本。
- `pilot/ground_truth/`：金标准文件与未完成的校对稿；复核状态以 `review-log.csv` 为准。
- `scripts/`、`reports/`：可复现的处理脚本和阶段性结果。

## 本地复现阶段 0/1

现有的候选 OCR 和评分报告已随仓库提供。运行下列命令可重新计算评分和检查项目；只有 `review-log.csv` 中标为 `verified` 的页会参与评分：

```powershell
python scripts/score_ocr.py
python scripts/validate_project.py
```

如需从扫描件重新生成完整试验包，先自行取得原书扫描 PDF，以 `1830年版朱利叶斯版传记.pdf` 放在仓库根目录。PDF 被 Git 忽略；还需按 [`docs/pilot-plan.md`](docs/pilot-plan.md) 准备 Tesseract 模型和其他依赖，再运行：

```powershell
python scripts/audit_pdf.py
python scripts/build_page_map.py
python scripts/render_pilot.py
python scripts/extract_ia_ocr.py
python scripts/run_tesseract.py
```

`run_tesseract.py` 会自动寻找 PATH 或 `C:\Program Files\Tesseract-OCR\tesseract.exe`，并使用本地 `tools/tessdata_best` 中的模型。依赖和下载说明见 [`docs/pilot-plan.md`](docs/pilot-plan.md)。

## GitHub 发布原则

首个公开里程碑只包含代码、书目清单、流程文档、人工转录和之后的原创译文。原始 PDF、试验页图片、下载缓存和 OCR 引擎均已排除在 Git 之外；第三方数字化图像是否可以再分发，要分别遵守来源网站的权利声明。

项目的文本与代码许可证尚未由项目所有者选定，当前不要把仓库内容视为已授予再许可。详见 [`RIGHTS.md`](RIGHTS.md)。

后续里程碑和公开内容边界见 [`docs/github-publishing.md`](docs/github-publishing.md)。

发现转录错误、难辨字形或来源异文，可先阅读 [`CONTRIBUTING.md`](CONTRIBUTING.md)。
