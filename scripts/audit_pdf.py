#!/usr/bin/env python3
"""Audit the local primary PDF without modifying it."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PDF = ROOT / "1830年版朱利叶斯版传记.pdf"
DEFAULT_SOURCES = ROOT / "data" / "sources.json"
DEFAULT_REPORT = ROOT / "reports" / "local-pdf-audit.json"


def file_hash(path: Path, algorithm: str) -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", type=Path, default=DEFAULT_PDF)
    parser.add_argument("--sources", type=Path, default=DEFAULT_SOURCES)
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    pdf = args.pdf.resolve()
    if not pdf.is_file():
        raise SystemExit(f"PDF not found: {pdf}")

    expected = json.loads(args.sources.read_text(encoding="utf-8"))["local_primary"]
    reader = PdfReader(str(pdf))
    sizes: Counter[str] = Counter()
    text_chars = 0
    whitespace_chars = 0
    pages_with_text = 0

    for page in reader.pages:
        box = page.mediabox
        key = f"{float(box.width):.3f}x{float(box.height):.3f}pt"
        sizes[key] += 1
        text = page.extract_text() or ""
        if text:
            pages_with_text += 1
            text_chars += len(text)
            whitespace_chars += sum(char.isspace() for char in text)

    observed = {
        "bytes": pdf.stat().st_size,
        "pdf_pages": len(reader.pages),
        "md5": file_hash(pdf, "md5"),
        "sha1": file_hash(pdf, "sha1"),
        "sha256": file_hash(pdf, "sha256"),
    }
    comparisons = {
        key: observed[key] == expected[key]
        for key in ("bytes", "pdf_pages", "md5", "sha1", "sha256")
    }

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pdf": pdf.relative_to(ROOT).as_posix() if pdf.is_relative_to(ROOT) else pdf.name,
        "observed": observed,
        "matches_sources_json": comparisons,
        "exact_primary_match": all(comparisons.values()),
        "pdf_metadata": {str(k): str(v) for k, v in (reader.metadata or {}).items()},
        "page_size_counts": dict(sizes),
        "embedded_text": {
            "pages_with_text": pages_with_text,
            "characters": text_chars,
            "whitespace_characters": whitespace_chars,
            "whitespace_ratio": (whitespace_chars / text_chars) if text_chars else 0,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["observed"], ensure_ascii=False, indent=2))
    print(f"Exact IA primary match: {report['exact_primary_match']}")
    print(f"Wrote {args.output}")
    return 0 if report["exact_primary_match"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
