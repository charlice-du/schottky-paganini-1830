[English](README.md) | [简体中文](README.zh-CN.md)

# Schottky–Paganini 1830

A page-verifiable OCR, German transcription, and eventual Chinese translation project for Julius Max Schottky's 1830 biography of Niccolò Paganini, *Paganini's Leben und Treiben als Künstler und als Mensch, mit unpartheiischer Berücksichtigung der Meinungen seiner Anhänger und Gegner*.

Much of the book is printed in Fraktur, with other type and languages appearing in places. Historical letterforms, ligatures, and varied page layouts make automated recognition unreliable without review. This project keeps the source page, page-level transcription, normalized German, Chinese translation, and notes linked so that a reader can check each interpretation against its source. Independent library scans are used as control copies where available. Our [current source audit](docs/source-audit.md) has not identified an easily accessible complete Chinese digital translation; it does not establish that no such translation exists.

## Current status

- A 16-page OCR pilot and candidate outputs are available. Fifteen pages are intended for textual gold-standard evaluation; the remaining manuscript/facsimile page requires a different review path.
- PDF pages 21 and 60 are verified against the scans (`2/15`). PDF page 115 is still in human review. A non-empty draft is not a verified gold-standard page. The [review log](pilot/ground_truth/review-log.csv) controls scoring status.
- The default OCR model has not been selected. Full-book transcription and Chinese translation are not complete; the online reader has not been built.

See [project status](STATUS.md) and the [manual review guide](docs/manual-review-guide.md) for the current workflow. The source and online-version survey is documented in the [source audit](docs/source-audit.md).

## Text and evidence layers

```text
Facsimile → diplomatic German transcription → normalized German
                                             → Chinese translation → notes
                 stable page and region identifiers connect the layers
```

The diplomatic transcription retains historical spelling, punctuation, printed lines, and significant layout. Normalization handles typographic variants and ordinary line-break hyphenation for search; it does not silently modernize the wording. Translations and notes remain separate from the German source text. The planned reader will show the facsimile, transcription, and translation together with their provenance. Its proposed English/Simplified Chinese interface is described in the [reader architecture](docs/reader-architecture.md); no reader is implemented yet.

## Repository layout

- `data/`: source records and the PDF-to-printed-page map.
- `docs/`: source research, editorial rules, manual review instructions, and reader design.
- `pilot/ocr/`: candidate OCR output for representative pages, not corrected text.
- `pilot/ground_truth/`: verified transcriptions and work-in-progress drafts; `review-log.csv` records their status.
- `scripts/` and `reports/`: processing scripts and reproducible pilot results.

## Reproduce the pilot

The repository includes candidate OCR text and the current scoring inputs. With Python 3.10+ available, these commands recalculate scores and check project structure. Only pages marked `verified` in `pilot/ground_truth/review-log.csv` are scored:

```powershell
python scripts/score_ocr.py
python scripts/validate_project.py
```

A fresh clone lacks the deliberately excluded page images and IA source cache, so the validator may report missing images as a warning. To rerun the PDF rendering and local Tesseract portion, obtain the primary scan independently (matching the PDF recorded in [`data/sources.json`](data/sources.json)), place it at the repository root as `1830年版朱利叶斯版传记.pdf`, and prepare Poppler, Tesseract 5.x, and the `tessdata_best` models listed in the [pilot plan](docs/pilot-plan.md). Then run:

```powershell
python scripts/audit_pdf.py
python scripts/render_pilot.py
python scripts/run_tesseract.py
```

Rebuilding the page map and IA OCR candidates also requires three external files from the [Internet Archive source item](https://archive.org/details/paganinislebenun00scho). The scripts expect these paths by default, all under the Git-ignored `sources/cache/` directory:

- `sources/cache/internet_archive/paganinislebenun00scho_scandata.xml` and `sources/cache/internet_archive/paganinislebenun00scho_page_numbers.json` for `build_page_map.py`;
- `sources/cache/internet_archive/paganinislebenun00scho_djvu.xml` for `extract_ia_ocr.py`.

The repository does not yet provide a tested download procedure for these IA inputs. A fresh clone plus the PDF alone therefore cannot rebuild the complete pilot. If you acquire the three files separately and put them at those paths, run `python scripts/build_page_map.py` and `python scripts/extract_ia_ocr.py`; otherwise, use the checked-in page map and OCR candidates for scoring and validation.

`run_tesseract.py` looks for Tesseract on `PATH` or at the standard Windows installation path, and for the selected models under the local `tools/tessdata_best/` directory. The required versions and model names are in the [pilot plan](docs/pilot-plan.md).

## Sources, rights, and contributions

Original PDFs, page images, downloaded caches, and OCR model files are excluded from Git. Redistribution of third-party scans depends on each source's terms; the repository publishes source metadata and links rather than whole-page images. Project code, human transcription, and future translation have not yet been assigned an open licence. See [rights and publication notes](RIGHTS.md) and the [publication plan](docs/github-publishing.md).

For transcription corrections, Fraktur questions, source variants, translation suggestions, OCR tooling, or reader ideas, see [contribution guidance](CONTRIBUTING.md). The detailed status, contribution, rights, and most research documents are currently in Chinese; English versions of those documents can be added separately.
