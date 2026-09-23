#!/usr/bin/env python3
"""Validate stage 0/1 project structure and report remaining human work."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []
    required = [
        ROOT / "data" / "sources.json",
        ROOT / "data" / "page-map.csv",
        ROOT / "pilot" / "selection.csv",
        ROOT / "pilot" / "ocr-configs.json",
        ROOT / "docs" / "source-audit.md",
        ROOT / "docs" / "editorial-policy.md",
    ]
    for path in required:
        if not path.is_file():
            errors.append(f"Missing required file: {path.relative_to(ROOT)}")

    selection_path = ROOT / "pilot" / "selection.csv"
    selected = []
    if selection_path.is_file():
        with selection_path.open(encoding="utf-8-sig", newline="") as stream:
            selected = list(csv.DictReader(stream))
        if len(selected) != 16:
            errors.append(f"Expected 16 pilot pages, found {len(selected)}")
        pages = [int(row["pdf_page"]) for row in selected]
        if len(pages) != len(set(pages)):
            errors.append("Pilot selection contains duplicate pages")

    page_map_path = ROOT / "data" / "page-map.csv"
    page_map_rows = 0
    if page_map_path.is_file():
        with page_map_path.open(encoding="utf-8-sig", newline="") as stream:
            page_map_rows = sum(1 for _ in csv.DictReader(stream))
        if page_map_rows != 446:
            errors.append(f"Expected 446 page-map rows, found {page_map_rows}")

    image_count = sum((ROOT / "pilot" / "images" / f"page-{int(row['pdf_page']):03d}.png").is_file() for row in selected)
    if selected and image_count != len(selected):
        warnings.append(f"Pilot images present: {image_count}/{len(selected)}")

    expected_ocr_counts = {"internet_archive": len(selected)}
    config_path = ROOT / "pilot" / "ocr-configs.json"
    if config_path.is_file():
        for config in json.loads(config_path.read_text(encoding="utf-8")):
            expected_ocr_counts[config["id"]] = len(config.get("pages", selected))
    ocr_counts = {}
    for config_id, expected_count in expected_ocr_counts.items():
        folder = ROOT / "pilot" / "ocr" / config_id
        ocr_counts[config_id] = sum((folder / f"page-{int(row['pdf_page']):03d}.txt").is_file() for row in selected)
        if selected and ocr_counts[config_id] != expected_count:
            warnings.append(f"OCR {config_id}: {ocr_counts[config_id]}/{expected_count} expected pages")

    scoreable = [row for row in selected if row["score_text"].lower() == "true"]
    review_log_path = ROOT / "pilot" / "ground_truth" / "review-log.csv"
    verified_pages = set()
    if review_log_path.is_file():
        with review_log_path.open(encoding="utf-8-sig", newline="") as stream:
            verified_pages = {
                int(row["pdf_page"])
                for row in csv.DictReader(stream)
                if row["status"].strip().lower() == "verified"
            }
    else:
        errors.append("Missing ground-truth review log")
    scoreable_pages = {int(row["pdf_page"]) for row in scoreable}
    for page in sorted(verified_pages - scoreable_pages):
        errors.append(f"Verified page is not scoreable: {page}")
    ground_truth_complete = 0
    for page in sorted(verified_pages & scoreable_pages):
        path = ROOT / "pilot" / "ground_truth" / f"page-{page:03d}.gt.txt"
        if path.is_file() and path.read_text(encoding="utf-8").strip():
            ground_truth_complete += 1
        else:
            errors.append(f"Verified page has no ground truth: {page}")
    if scoreable and ground_truth_complete != len(scoreable):
        warnings.append(f"Human ground truth complete: {ground_truth_complete}/{len(scoreable)}")

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "error" if errors else ("ready_for_human_review" if warnings else "complete"),
        "errors": errors,
        "warnings": warnings,
        "counts": {
            "page_map_rows": page_map_rows,
            "pilot_pages": len(selected),
            "pilot_images": image_count,
            "ocr_pages_by_candidate": ocr_counts,
            "ground_truth_complete": ground_truth_complete,
            "ground_truth_required": len(scoreable),
        },
    }
    output = ROOT / "reports" / "project-validation.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
