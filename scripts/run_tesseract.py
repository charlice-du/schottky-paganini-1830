#!/usr/bin/env python3
"""Run the declared Tesseract OCR candidates over the pilot page images."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def find_tesseract(explicit: str | None) -> Path:
    candidates = []
    if explicit:
        candidates.append(explicit)
    detected = shutil.which("tesseract")
    if detected:
        candidates.append(detected)
    if os.name == "nt":
        candidates.extend(
            [
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            ]
        )
    for candidate in candidates:
        path = Path(candidate)
        if path.is_file():
            return path
    raise SystemExit("Tesseract was not found. Install it or pass --tesseract PATH.")


def load_pages(selection: Path) -> list[int]:
    with selection.open(encoding="utf-8-sig", newline="") as stream:
        return [int(row["pdf_page"]) for row in csv.DictReader(stream)]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tesseract")
    parser.add_argument("--selection", type=Path, default=ROOT / "pilot" / "selection.csv")
    parser.add_argument("--configs", type=Path, default=ROOT / "pilot" / "ocr-configs.json")
    parser.add_argument("--image-dir", type=Path, default=ROOT / "pilot" / "images")
    parser.add_argument("--output-root", type=Path, default=ROOT / "pilot" / "ocr")
    parser.add_argument("--tessdata-dir", type=Path, default=ROOT / "tools" / "tessdata_best")
    parser.add_argument("--only-config")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    executable = find_tesseract(args.tesseract)
    configs = json.loads(args.configs.read_text(encoding="utf-8"))
    if args.only_config:
        configs = [config for config in configs if config["id"] == args.only_config]
        if not configs:
            raise SystemExit(f"Unknown config: {args.only_config}")

    model_hashes = {}
    for config in configs:
        model = args.tessdata_dir / f"{config['language']}.traineddata"
        if not model.is_file():
            raise SystemExit(f"Missing model: {model}")
        model_hashes[config["language"]] = sha256(model)

    version = subprocess.run(
        [str(executable), "--version"], check=True, capture_output=True, text=True, encoding="utf-8"
    ).stdout.splitlines()[0]
    pages = load_pages(args.selection)
    runs = []

    for config in configs:
        output_dir = args.output_root / config["id"]
        output_dir.mkdir(parents=True, exist_ok=True)
        config_pages = [int(page) for page in config.get("pages", pages)]
        unknown_pages = sorted(set(config_pages) - set(pages))
        if unknown_pages:
            raise SystemExit(f"Config {config['id']} references unselected pages: {unknown_pages}")
        for page in config_pages:
            image = args.image_dir / f"page-{page:03d}.png"
            output = output_dir / f"page-{page:03d}.txt"
            if not image.is_file():
                raise SystemExit(f"Missing pilot image: {image}")
            if output.is_file() and not args.force:
                runs.append({"config": config["id"], "page": page, "status": "skipped_existing"})
                continue

            command = [
                str(executable), str(image), "stdout",
                "--tessdata-dir", str(args.tessdata_dir),
                "-l", config["language"],
                "--oem", "1",
                "--psm", str(config["psm"]),
                "--dpi", "300",
                "-c", "preserve_interword_spaces=1",
            ]
            result = subprocess.run(command, check=True, capture_output=True, text=True, encoding="utf-8")
            output.write_text(result.stdout.rstrip() + "\n", encoding="utf-8", newline="\n")
            runs.append(
                {
                    "config": config["id"],
                    "page": page,
                    "status": "completed",
                    "characters": len(result.stdout),
                    "stderr": result.stderr.strip(),
                }
            )

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tesseract": executable.name,
        "version": version,
        "tessdata_dir": args.tessdata_dir.resolve().relative_to(ROOT).as_posix() if args.tessdata_dir.resolve().is_relative_to(ROOT) else args.tessdata_dir.name,
        "model_sha256": model_hashes,
        "configs": configs,
        "runs": runs,
    }
    report_path = ROOT / "reports" / "ocr-run.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    completed = sum(run["status"] == "completed" for run in runs)
    print(f"{version}: completed {completed} OCR run(s); report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
