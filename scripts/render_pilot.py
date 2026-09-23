#!/usr/bin/env python3
"""Render selected PDF pages to local 300 dpi PNG files with Poppler."""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def find_pdftoppm(explicit: str | None) -> Path:
    candidates = []
    if explicit:
        candidates.append(explicit)
    detected = shutil.which("pdftoppm")
    if detected:
        candidates.append(detected)
    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            # Codex's Windows runtime exposes a .cmd shim. Prefer the real
            # Poppler executable so Unicode source/output paths survive intact.
            if path.suffix.lower() in {".cmd", ".bat"} and len(path.parents) >= 3:
                runtime_exe = path.parents[2] / "native" / "poppler" / "Library" / "bin" / "pdftoppm.exe"
                if runtime_exe.is_file():
                    return runtime_exe
            return path
    raise SystemExit("pdftoppm was not found. Install Poppler or pass --pdftoppm PATH.")


def load_pages(selection: Path) -> list[int]:
    with selection.open(encoding="utf-8-sig", newline="") as stream:
        return [int(row["pdf_page"]) for row in csv.DictReader(stream)]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", type=Path, default=ROOT / "1830年版朱利叶斯版传记.pdf")
    parser.add_argument("--selection", type=Path, default=ROOT / "pilot" / "selection.csv")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "pilot" / "images")
    parser.add_argument("--dpi", type=int, default=300)
    parser.add_argument("--pdftoppm")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    pdf = args.pdf.resolve()
    if not pdf.is_file():
        raise SystemExit(f"PDF not found: {pdf}")
    tool = find_pdftoppm(args.pdftoppm)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    rendered = []
    skipped = []
    for page in load_pages(args.selection):
        prefix = args.output_dir / f"page-{page:03d}"
        output = prefix.with_suffix(".png")
        if output.exists() and not args.force:
            skipped.append(page)
            continue
        command = [
            str(tool), "-f", str(page), "-l", str(page), "-r", str(args.dpi),
            "-png", "-singlefile", str(pdf), str(prefix),
        ]
        if os.name == "nt" and tool.suffix.lower() in {".cmd", ".bat"}:
            command = [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", *command]
        subprocess.run(command, check=True)
        if not output.is_file():
            raise SystemExit(f"Renderer did not create {output}")
        rendered.append(page)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pdf": pdf.relative_to(ROOT).as_posix() if pdf.is_relative_to(ROOT) else pdf.name,
        "renderer": tool.name,
        "dpi": args.dpi,
        "rendered": rendered,
        "skipped_existing": skipped,
    }
    report_path = ROOT / "reports" / "pilot-render.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Rendered {len(rendered)} page(s); skipped {len(skipped)} existing page(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
