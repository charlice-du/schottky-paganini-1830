# OCR review packets

The review-packet generator compares **existing OCR candidate texts** for one physical PDF page. It helps a human find disagreements and suspicious OCR shapes before checking the scan and control copy. It does not produce, edit, or verify a transcription.

Run from the repository root with Python 3.10+:

```powershell
python scripts/build_review_packet.py 115
```

This writes `reports/review/page-115.md` (human-readable) and `reports/review/page-115.json` (machine-readable). Use `--output-dir tmp/review-test` to keep test runs out of the tracked reports. The command needs only the checked-in `pilot/ocr/` texts, `data/page-map.csv`, `pilot/selection.csv`, and `pilot/ground_truth/review-log.csv`. It does **not** need the source PDF, page PNGs, Tesseract, or IA cache files. Candidate directories are discovered automatically. A directory lacking the requested page is reported as unavailable; an existing page file with no alphanumeric OCR text is reported separately as empty/unusable and excluded from alignment. If no usable candidate remains, the command fails clearly.

The JSON uses `schema_version: 1` and includes page metadata, review status, candidate names, an alignment anchor, agreement counts, an independent `review_priority` and its reasons, aligned segments, unaligned candidate lines, and `raw_candidates` containing the complete original OCR strings. The Markdown opens with high-priority targets and their readings, followed by medium, low, and alignment-only queues; lower-priority full readings are collapsible. Both outputs are deterministic for unchanged inputs and contain no scan image.

## Comparison and alignment

The packet shows both match similarity and anchor-line coverage. A fragment may match strongly while covering only part of a grouped anchor segment; such a correspondence remains uncertain.

For **comparison only**, the script applies Unicode NFC, expands long `ſ` and a few ligatures, lowercases, and collapses whitespace. It ignores punctuation when computing alignment similarity, including standalone punctuation-only tokens, but retains original punctuation and line breaks in the readings and flags. No source or gold-standard file is normalized or rewritten.

The alignment anchor is the available candidate with the highest average full-page token similarity to the others. This is only a coordinate choice, **not** a quality ranking. Each other candidate is aligned monotonically with dynamic programming: one or two nonblank OCR lines may match one or two anchor OCR lines. Matches below 0.68 similarity are rejected; matches from 0.68 to below 0.82 are marked `uncertain`. Skipped candidate lines are shown separately as `unaligned`. The script never assumes that the same line number in two OCR outputs is the same printed line.

`high` agreement requires at least two aligned readings with identical comparison-normalized text **and** no missing or uncertain candidate for that segment. `low` means at least two confidently aligned readings differ. All other segments are `uncertain`. With a noisy candidate such as IA OCR, high agreement can be rare; low agreement does **not** imply that any particular candidate is wrong.

## Inspection priority

`review_priority` is an independent triage label, **not** a reading recommendation or transcription-confidence score. It considers only the OCR texts and alignment quality. It never reads human ground truth. Well-aligned readings are compared using a punctuation-insensitive lexical key that joins ordinary line-end hyphenation; raw text and the original agreement label remain unchanged.

- `high`: substantial numeric conflicts involving a three-or-more-digit string, competing well-supported lexical readings, a substantial lexical conflict without a majority, or the same suspicious word/number token in at least two well-aligned candidates.
- `medium`: one or a few outliers against a near-consensus, limited lexical differences, or a suspicious token isolated to one well-aligned candidate.
- `low`: only formatting differences (including punctuation, whitespace, or ordinary line-end hyphenation), or a very small lexical deviation.
- `alignment_only`: too few well-aligned readings, or stable aligned text with only uncertain/unaligned alternatives. Alignment problems remain visible but are not promoted into textual conflict.

Near-consensus and repeated tokens are used solely to order inspection; **a majority is not evidence of correctness**. OCR candidates may share a model and repeat the same error, so repeated tokens are not independent corroboration. Thresholds are deterministic heuristics, not calibrated probabilities. Verified pages 21 and 60 can be used for an offline sanity check, but two pages cannot statistically validate or train the ranking.

### Limited offline sanity check

During development, the verified page-21 and page-60 texts were inspected **outside** the production generator. High-priority examples caught visible OCR problems, including conflicting year-like digit strings on page 21 and symbol substitutions in words on both pages. The first rule also put small but real word errors such as `Anefdoten` and `niht` in Low; the general rule was therefore changed so a lexical outlier against an exact aligned group is at least Medium. Single-digit heading/footnote noise is not automatically High. These are qualitative checks on only two pages, not precision/recall estimates, a learned model, or a claim that Low contains no errors.

## Flag meanings

- `candidate_disagreement`: confidently aligned OCR readings differ; examples show variants without preferring one.
- `punctuation_disagreement`: the alphanumeric content agrees, but punctuation differs.
- `line_end_hyphen_disagreement`: aligned readings differ on a line-ending hyphen-like mark.
- `possible_ocr_artifact`: a token contains a symbol such as `<`, `>`, or `[`.
- `suspicious_internal_symbol`: a suspicious mark appears between letters, such as the colon in `unwürd:gen`.
- `possible_digit_letter_confusion`: a digit touches a letter in a token, as in `182Z`.
- `uncertain_alignment` / `unaligned`: the text correspondence is weak or absent.

These are **inspection prompts**, not linguistic judgments. Historical spelling, mixed languages, footnotes, legitimate punctuation, and OCR reading-order errors can trigger false positives. The generator does not use a modern German spellchecker, an LLM, or gold-standard text to choose a reading. Review status comes only from `review-log.csv`; an unlisted page is `not_started`, never inferred `verified` from a nonempty text file.

The example page 115 remains `in_review`. Human verification must still use the source image and, where useful, the independent control copy before changing its ground truth or review status.
