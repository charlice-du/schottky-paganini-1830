#!/usr/bin/env python3
"""Extract page-aligned OCR from Internet Archive DjVu XML."""

from __future__ import annotations

import argparse
import csv
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_pages(selection: Path) -> list[int]:
    with selection.open(encoding="utf-8-sig", newline="") as stream:
        return [int(row["pdf_page"]) for row in csv.DictReader(stream)]


def object_text(obj: ET.Element) -> str:
    paragraphs = []
    for paragraph in obj.findall(".//PARAGRAPH"):
        lines = []
        for line in paragraph.findall(".//LINE"):
            words = [(word.text or "").strip() for word in line.findall(".//WORD")]
            text = " ".join(word for word in words if word)
            if text:
                lines.append(text)
        if lines:
            paragraphs.append("\n".join(lines))
    if paragraphs:
        return "\n\n".join(paragraphs).rstrip() + "\n"

    lines = []
    for line in obj.findall(".//LINE"):
        words = [(word.text or "").strip() for word in line.findall(".//WORD")]
        text = " ".join(word for word in words if word)
        if text:
            lines.append(text)
    return "\n".join(lines).rstrip() + ("\n" if lines else "")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--xml", type=Path, default=ROOT / "sources" / "cache" / "internet_archive" / "paganinislebenun00scho_djvu.xml")
    parser.add_argument("--selection", type=Path, default=ROOT / "pilot" / "selection.csv")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "pilot" / "ocr" / "internet_archive")
    args = parser.parse_args()

    objects = ET.parse(args.xml).getroot().findall(".//OBJECT")
    if len(objects) != 446:
        raise SystemExit(f"Expected 446 OCR pages, found {len(objects)}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    pages = load_pages(args.selection)
    char_counts = {}
    for page in pages:
        text = object_text(objects[page - 1])
        target = args.output_dir / f"page-{page:03d}.txt"
        target.write_text(text, encoding="utf-8", newline="\n")
        char_counts[str(page)] = len(text)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": args.xml.resolve().relative_to(ROOT).as_posix() if args.xml.resolve().is_relative_to(ROOT) else args.xml.name,
        "object_count": len(objects),
        "selected_pages": pages,
        "character_counts": char_counts,
    }
    report_path = ROOT / "reports" / "ia-ocr-extraction.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Extracted IA OCR for {len(pages)} pages to {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
