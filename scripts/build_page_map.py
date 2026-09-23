#!/usr/bin/env python3
"""Build a stable PDF-page/scan-leaf/printed-page map from IA scan data."""

from __future__ import annotations

import argparse
import csv
import json
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "sources" / "cache" / "internet_archive"


def section_for(pdf_page: int) -> str:
    if pdf_page == 1:
        return "cover"
    if 2 <= pdf_page <= 8:
        return "prelim_unpaginated"
    if 9 <= pdf_page <= 18:
        return "front_matter"
    if 19 <= pdf_page <= 20:
        return "contents"
    if 21 <= pdf_page <= 430:
        return "body"
    if 431 <= pdf_page <= 440:
        return "index"
    if 441 <= pdf_page <= 442:
        return "foldout_facsimile"
    return "end_matter"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scandata", type=Path, default=CACHE / "paganinislebenun00scho_scandata.xml")
    parser.add_argument("--page-numbers", type=Path, default=CACHE / "paganinislebenun00scho_page_numbers.json")
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "page-map.csv")
    args = parser.parse_args()

    scan_root = ET.parse(args.scandata).getroot()
    scan_pages = scan_root.findall(".//pageData/page")
    included = [p for p in scan_pages if (p.findtext("addToAccessFormats") or "").lower() == "true"]

    page_number_data = json.loads(args.page_numbers.read_text(encoding="utf-8"))
    detected = {int(p["leafNum"]): p for p in page_number_data.get("pages", [])}

    if len(included) != 446:
        raise SystemExit(f"Expected 446 access pages, found {len(included)}")

    rows = []
    for pdf_page, node in enumerate(included, start=1):
        leaf = int(node.attrib["leafNum"])
        printed = (node.findtext("pageNumber") or "").strip()
        source = "scandata" if printed else ""
        confidence = ""

        if not printed:
            detected_page = detected.get(leaf, {})
            printed = str(detected_page.get("pageNumber") or "").strip()
            if printed:
                source = "ia_page_number_model"
                confidence = detected_page.get("confidence") or ""

        if not printed and pdf_page == 9:
            printed, source = "I", "derived_sequence"
        elif not printed and 21 <= pdf_page <= 430:
            printed, source = str(pdf_page - 20), "derived_sequence"

        notes = []
        if pdf_page == 5:
            notes.append("title page")
        if pdf_page in (43, 44):
            notes.append("PAGANINI acrostic")
        if pdf_page in (441, 442):
            notes.append("foldout facsimile")

        rows.append(
            {
                "pdf_page": pdf_page,
                "ia_leaf": leaf,
                "page_type": node.findtext("pageType") or "",
                "printed_label": printed,
                "printed_label_source": source,
                "label_confidence": confidence,
                "section": section_for(pdf_page),
                "notes": "; ".join(notes),
            }
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
