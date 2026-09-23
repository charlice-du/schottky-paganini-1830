# Bilingual reader architecture (design draft)

This document describes a future reader; it does not select a frontend framework, define a deployment, or make the current pilot into a finished edition. At present, PDF pages 21 and 60 are verified, page 115 is `in_review`, and no Chinese translation or reader has been published. The [editorial policy](editorial-policy.md) describes the intended separation of text layers.

## Two independent language choices

| Dimension | Planned values | What changes |
|---|---|---|
| Interface locale | `en`, `zh-Hans` | Navigation, headings, status messages, help, and correction controls |
| Book content | Scanned source page (mainly historical German print); diplomatic transcription; normalized German; Chinese translation; notes | The selected source or text layer, when that layer exists |

Changing the interface locale must never rewrite, translate, or replace the German transcription. Original-language passages in Italian or French should retain their own region-level language metadata. The current translation target is `zh-Hans`; an English translation would be a separate future entry such as `translations.en`, independent of `transcription.de`. Notes may eventually have localized versions, but missing English or Chinese notes should be shown as unavailable rather than silently translated.

Proposed interface labels include:

| Key | `en` | `zh-Hans` |
|---|---|---|
| `previousPage` | Previous page | 上一页 |
| `nextPage` | Next page | 下一页 |
| `facsimile` | Source page | 原书页面 |
| `transcription` | German transcription | 德文转录 |
| `translation` | Chinese translation | 中文译文 |
| `notes` | Notes | 注释 |
| `verified` | Verified | 已复核 |
| `inReview` | In review | 校对中 |
| `sources` | Sources | 来源 |
| `suggestCorrection` | Suggest a correction | 提交校订建议 |
| `unavailable` | Not yet available | 暂无内容 |

The locale choice can be reflected in the URL (for example, `?ui=zh-Hans`) so a shared link opens with the intended interface. Switching locale preserves the page and content-layer selection. Translation availability is a separate choice and must not be inferred from the UI locale.

## Page identity and proposed data contract

Use a stable ID based on the primary PDF's physical page number, such as `pdf-0115`. Do not use printed page labels as keys: front matter may use Roman numerals or lack a printed label. `data/page-map.csv` already records `pdf_page`, `printed_label`, and mapping evidence; source-specific canvas or leaf numbers must remain separate. A reader route could use `/page/pdf-0115`, with the interface locale carried independently.

A future page record could contain the following fields. This is a proposed contract, not a JSON file already present in the repository:

```json
{
  "id": "pdf-0115",
  "pdfPage": 115,
  "printedLabel": "95",
  "sourcePageRefs": [{ "sourceId": "ia:paganinislebenun00scho", "leaf": 115 }],
  "transcription": { "language": "de", "status": "in_review", "textRef": "pilot/ground_truth/page-115.gt.txt" },
  "normalizedGerman": null,
  "translations": { "zh-Hans": null },
  "notes": []
}
```

The example reports page 115's actual current review state, not a verified text or a completed translation. Review status comes from `pilot/ground_truth/review-log.csv`; a non-empty `.gt.txt` alone is never evidence of verification. If a draft is displayed, its `In review` badge stays adjacent to the transcription and it must not be exported or cited as verified. Pages without a translation show a localized availability message rather than generated filler.

The planned formal edition may use per-page TEI XML as the editorial source and produce reader JSON as a build artifact, as suggested in `docs/editorial-policy.md`. The schema should leave room for stable region and line IDs, reading order, footnotes, acrostics, source variants, and links from notes or translations back to the relevant German passage. No such conversion is implemented in this PR.

## Reader layout and navigation

```text
Schottky–Paganini 1830                         [English | 简体中文]
PDF 115 · printed page 95                       [Previous] [Next]
┌──────────────────┬──────────────────┬──────────────────┐
│ Source page      │ German           │ Chinese          │
│ external image   │ transcription    │ translation      │
│ or source link   │ In review        │ Not yet available│
└──────────────────┴──────────────────┴──────────────────┘
[Sources] [Notes] [Suggest a correction]
```

On narrow screens, the three panes can stack while retaining their labels, page context, and verification badge. Page navigation uses the stable PDF-page order. Each view displays both the PDF page number and any printed label, without assuming that the two numbers match. The correction action should carry the page ID, relevant region or line if known, and source reference into a proposed GitHub issue; it must not change the transcription automatically.

## Facsimile and provenance adapter

Raw PDFs, page PNGs, and downloaded image caches are deliberately absent from Git. A future source-image adapter should resolve a page ID plus a `sourceId` to a source-specific leaf or IIIF canvas, a catalog link, attribution, a rights statement, and an image URL only when display is permitted. The primary scan and independent control copy may use different page numbering or editions; mapping must be recorded per source rather than inferred from the primary PDF number.

If an image cannot be embedded under the source's terms, the pane should show a source link and provenance instead. The adapter must not copy the scan into the repository. Source records live in `data/sources.json`; the page map lives in `data/page-map.csv`. An image's presence or absence does not alter the German transcription or its verification status.

## Work left for implementation

Before building the reader, define and validate source-to-page mappings, region IDs, text-layer serialization, and the image-display rules for each source. Then implement the locale dictionary, navigation, panes, provenance and correction links against the verified data. Framework choice, hosting, full translation, and publication of scan images are outside this design draft.
