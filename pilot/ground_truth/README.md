# OCR 金标准目录

人工转录文件命名为 `page-NNN.gt.txt`，必须是 UTF-8 纯文本。不要从候选 OCR 直接复制后只改显眼错误；应以扫描页为唯一依据逐行核对。具体规则见 `docs/manual-review-guide.md`。

文件名沿用试验期约定，但非空文件也可能仍是草稿。`review-log.csv` 中的 `verified` 是可评分金标准的唯一状态标记；第 115 页目前为 `in_review`，不得据其计算 OCR 准确率。
