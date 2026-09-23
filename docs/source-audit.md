# 阶段 0：底本与网络版本核查

核查日期：2026-08-10

## 结论

网络上确有多份完整扫描记录，也有自动生成的全文 OCR／EPUB；因此不必从零开始定位扫描或重新切页。但是，截至本轮核查，没有发现可直接作为出版底稿的、经过人工逐字校订的完整德文电子文本，也没有发现完整中文或其他语言译本。现有自动 OCR 对 Fraktur 的识别错误很多，仍需重新识别和人工校勘。

本地文件 `1830年版朱利叶斯版传记.pdf` 与 Internet Archive 项目 `paganinislebenun00scho` 的 Text PDF 大小均为 26,543,836 字节，MD5 均为 `8af132b0c988de49096317a633bb7241`。两者为同一个文件，而不是两个独立见证。

## 在线记录对照

| 来源 | 书目／物理信息 | 数字对象 | 项目用途 |
|---|---|---:|---|
| [Internet Archive](https://archive.org/details/paganinislebenun00scho) | Prag, J. G. Calve, 1830 | 元数据称 448 images；访问 PDF 446 页；400 ppi；有 PDF、DjVu、hOCR、ABBYY、EPUB 等派生物 | 主底本；IA OCR 作为最低基线 |
| [MDZ / BSB `bsb10600235`](https://mdz-nbn-resolving.de/details:bsb10600235) | Prag: Calve；`XII, 410 S., 5 Bl.`；目录注明肖像和 1 幅摹真 | 444 个 IIIF canvases | 同版馆藏校本；核对缺图、污损、裁切和折页 |
| [MDZ / `bsb11236465`](https://mdz-nbn-resolving.de/details:bsb11236465) | Prag: Taussig；`III, XII, 415 S.` | 440 个 IIIF canvases | 书目／版次变体；只做有记录的异文对照，不与主底本静默混合 |
| [Google Play Books `KD5DAAAAcAAJ`](https://play.google.com/store/books/details?id=KD5DAAAAcAAJ) | Calve, 1830；页面显示 410 pages | 免费电子书记录 | 额外完整影像入口；必要时人工下载比对 |
| [Open Library `OL6951709M`](https://openlibrary.org/books/OL6951709M) | 德文原版记录及关联 work | 指向可借阅／扫描记录 | 书目交叉核对，不作为独立校本 |

## 本地 PDF 结构

- PDF 共 446 页；IA `scandata.xml` 中恰有 446 个 `addToAccessFormats=true` 的叶面。
- PDF 第 5 页为书名页，第 9 页起见罗马页码前言；PDF 第 21 页对应正文印刷页 1，第 430 页对应印刷页 410。
- PDF 第 431–440 页为索引；第 441–442 页被标作 `Foldout`，包含手稿／摹真材料；其后为馆藏附页和封底。
- PDF 内嵌了整本 OCR 字层，但它几乎没有可靠空格，且有大量 Fraktur 误识；不能当作校订文本。
- 目录在 PDF 第 19–20 页；印刷页 23–24（PDF 第 43–44 页）包含首字母纵向组成 `PAGANINI` 的离合诗，是版面语义必须保存的代表例。

完整页码映射由 `scripts/build_page_map.py` 从 IA 扫描数据生成到 `data/page-map.csv`，不依赖人工记忆的固定偏移量。

## 底本决定

1. **主底本**：本地／IA Calve 扫描。优点是本地已有完整 PDF、OCR 结构文件齐全、页码稳定。
2. **首要校本**：MDZ `bsb10600235`。它和主底本同为 Calve 书目形态，且目录明确记有肖像和摹真，可用于判断本地扫描是否漏图或折页处理不全。
3. **变体校本**：MDZ `bsb11236465`。其出版者和页数不同，先视为变体，不把额外的五页直接插入主底本。
4. **机器文字最低基线**：IA DjVu XML。它保留逐页、逐行和单词框信息，优于从 PDF 的无空格字层反向整理，但文本准确度仍低。

## MDZ Calve 副本的附页复核

已通过 IIIF 缩略图核对该副本的首尾结构：canvas 5 为书名页，9–20 为前置页，21–430 对应正文印刷页 1–410，431–440 为索引，441–443 为可见空白页，444 为封底。首八页和末八页均未见肖像或摹真，尽管目录题名注明 `Mit Portr. u. 1 Facsimile`。

这意味着“目录注明附图”不能直接等同于“这一数字副本实际含附图”。本地主底本反而在 PDF 441–442 保留了一件由两页承载的折页手稿／音乐摹真；目前仍未在任何已检查副本中找到目录所称的肖像。后续应把 Google Books 的前后附页作为肖像搜寻重点。

## 尚需一次人工核验的事项

- 登录／打开 Google Books 免费电子书，确认实际可下载格式、扫描来源和前后附页是否完整；API 在本轮核查时返回 429，商店公开页本身可访问。
- 公开 GitHub 仓库前，再核对扫描图像的再分发条件。MDZ 清单明确标注 [NoC-NC 1.0](https://rightsstatements.org/vocab/NoC-NC/1.0/)；因此默认只发布链接、转录和译文，不发布整本扫描。

## 阶段 0 验收

- [x] 确认本地 PDF 的来源和校验值。
- [x] 找到至少两份可独立调取的完整馆藏扫描记录。
- [x] 区分同版校本与出版者／页数变体。
- [x] 保存 IA 元数据、两份 MDZ IIIF 清单和 IA OCR 辅助文件。
- [x] 确定主底本、校本和 GitHub 初始发布边界。
- [x] 复核 MDZ Calve 副本前后附页；其数字对象未显示目录注明的肖像／摹真。
- [ ] 人工确认 Google Books 实际下载格式，并检查它是否保留肖像。
