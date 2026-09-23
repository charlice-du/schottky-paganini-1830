#!/usr/bin/env python3
"""Score OCR candidates against manually prepared page-level ground truth."""

from __future__ import annotations

import argparse
import csv
import re
import statistics
import unicodedata
from pathlib import Path
from typing import Sequence, TypeVar


ROOT = Path(__file__).resolve().parents[1]
T = TypeVar("T")


def edit_distance(reference: Sequence[T], hypothesis: Sequence[T]) -> int:
    if len(reference) < len(hypothesis):
        reference, hypothesis = hypothesis, reference
    previous = list(range(len(hypothesis) + 1))
    for row, ref_item in enumerate(reference, start=1):
        current = [row]
        for col, hyp_item in enumerate(hypothesis, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[col] + 1,
                    previous[col - 1] + (ref_item != hyp_item),
                )
            )
        previous = current
    return previous[-1]


def raw_text(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").rstrip("\n")


def normalized_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = text.translate(str.maketrans({"ſ": "s", "ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl"}))
    text = re.sub(r"⟦unclear:[^⟧]*⟧", "", text)
    return re.sub(r"\s+", " ", text).strip()


def ratio(distance: int, reference_length: int) -> float:
    return distance / max(reference_length, 1)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selection", type=Path, default=ROOT / "pilot" / "selection.csv")
    parser.add_argument("--ground-truth", type=Path, default=ROOT / "pilot" / "ground_truth")
    parser.add_argument("--review-log", type=Path, default=ROOT / "pilot" / "ground_truth" / "review-log.csv")
    parser.add_argument("--ocr-root", type=Path, default=ROOT / "pilot" / "ocr")
    parser.add_argument("--csv-output", type=Path, default=ROOT / "reports" / "ocr-benchmark.csv")
    parser.add_argument("--md-output", type=Path, default=ROOT / "reports" / "ocr-benchmark.md")
    args = parser.parse_args()

    with args.selection.open(encoding="utf-8-sig", newline="") as stream:
        selected = [row for row in csv.DictReader(stream) if row["score_text"].lower() == "true"]
    with args.review_log.open(encoding="utf-8-sig", newline="") as stream:
        verified_pages = {
            int(row["pdf_page"])
            for row in csv.DictReader(stream)
            if row["status"].strip().lower() == "verified"
        }
    candidates = sorted(path for path in args.ocr_root.iterdir() if path.is_dir())
    rows = []

    for item in selected:
        page = int(item["pdf_page"])
        gold_path = args.ground_truth / f"page-{page:03d}.gt.txt"
        gold = gold_path.read_text(encoding="utf-8") if gold_path.is_file() else ""
        for candidate in candidates:
            hypothesis_path = candidate / f"page-{page:03d}.txt"
            hypothesis = hypothesis_path.read_text(encoding="utf-8") if hypothesis_path.is_file() else ""
            row = {
                "pdf_page": page,
                "printed_page": item["printed_page"],
                "feature": item["feature"],
                "candidate": candidate.name,
                "status": "",
                "gold_characters": len(gold),
                "ocr_characters": len(hypothesis),
                "raw_cer": "",
                "normalized_cer": "",
                "wer": "",
            }
            if page not in verified_pages:
                row["status"] = "draft_ground_truth" if gold.strip() else "pending_ground_truth"
            elif not gold.strip():
                row["status"] = "missing_verified_ground_truth"
            elif not hypothesis.strip():
                row["status"] = "missing_ocr"
            else:
                gold_raw, hyp_raw = raw_text(gold), raw_text(hypothesis)
                gold_norm, hyp_norm = normalized_text(gold), normalized_text(hypothesis)
                gold_words, hyp_words = gold_norm.split(), hyp_norm.split()
                row.update(
                    {
                        "status": "scored",
                        "raw_cer": f"{ratio(edit_distance(gold_raw, hyp_raw), len(gold_raw)):.6f}",
                        "normalized_cer": f"{ratio(edit_distance(gold_norm, hyp_norm), len(gold_norm)):.6f}",
                        "wer": f"{ratio(edit_distance(gold_words, hyp_words), len(gold_words)):.6f}",
                    }
                )
            rows.append(row)

    args.csv_output.parent.mkdir(parents=True, exist_ok=True)
    with args.csv_output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    md = ["# OCR benchmark", "", "Scores are generated only for pages marked `verified` in `pilot/ground_truth/review-log.csv`.", "", "| Candidate | Scored pages | Median normalized CER | Median WER |", "|---|---:|---:|---:|"]
    for candidate in candidates:
        scored = [row for row in rows if row["candidate"] == candidate.name and row["status"] == "scored"]
        if scored:
            median_cer = statistics.median(float(row["normalized_cer"]) for row in scored)
            median_wer = statistics.median(float(row["wer"]) for row in scored)
            md.append(f"| {candidate.name} | {len(scored)} | {median_cer:.2%} | {median_wer:.2%} |")
        else:
            md.append(f"| {candidate.name} | 0 | pending | pending |")
    pending = len({row["pdf_page"] for row in rows if row["status"] in {"pending_ground_truth", "draft_ground_truth"}})
    drafts = sorted({row["pdf_page"] for row in rows if row["status"] == "draft_ground_truth"})
    md.extend(["", f"Ground-truth pages still pending: {pending}.", f"Draft pages in human review: {', '.join(map(str, drafts)) or 'none'}.", ""])
    args.md_output.write_text("\n".join(md), encoding="utf-8", newline="\n")
    print(f"Wrote {len(rows)} comparison rows; {pending} ground-truth page(s) pending.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
