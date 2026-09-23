#!/usr/bin/env python3
"""Build a deterministic, non-authoritative OCR comparison packet for one PDF page."""

from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIN_MATCH = 0.68
HIGH_MATCH = 0.82
FENCE = chr(96) * 3
TYPOGRAPHIC = str.maketrans(
    {"ſ": "s", "ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl"}
)
SUSPECT_SYMBOLS = set("<>[]{}^$@|")
SUSPECT_INTERNAL = SUSPECT_SYMBOLS | set(":?")
LINE_END_HYPHENS = ("-", "‐", "‑", "=")


@dataclass(frozen=True)
class Match:
    anchor_start: int
    anchor_end: int
    other_start: int
    other_end: int
    similarity: float


def comparison_text(value: str) -> str:
    """Only for comparison: NFC, selected typographic variants, case, whitespace."""
    value = unicodedata.normalize("NFC", value).translate(TYPOGRAPHIC).lower()
    return " ".join(value.split())


def alignment_key(value: str) -> str:
    """Ignore punctuation for alignment, but retain it in the OCR and flags."""
    normalized = comparison_text(value)
    return " ".join("".join(ch for ch in word if ch.isalnum()) for word in normalized.split())


def similarity(left: str, right: str) -> float:
    left_key, right_key = alignment_key(left), alignment_key(right)
    if not left_key or not right_key:
        return 0.0
    if min(len(left_key), len(right_key)) < 5 and left_key != right_key:
        return 0.0
    if min(len(left_key), len(right_key)) / max(len(left_key), len(right_key)) < 0.4:
        return 0.0
    return SequenceMatcher(None, left_key, right_key, autojunk=False).ratio()


def numbered_lines(raw: str) -> list[dict]:
    return [
        {"number": number, "text": line}
        for number, line in enumerate(raw.splitlines(), start=1)
        if line.strip()
    ]


def choose_anchor(raw_candidates: dict[str, str]) -> str:
    """Choose a central OCR output for alignment, not a preferred reading."""
    names = sorted(raw_candidates)
    if len(names) == 1:
        return names[0]
    tokens = {name: comparison_text(raw_candidates[name]).split() for name in names}
    scores = {}
    for name in names:
        scores[name] = sum(
            SequenceMatcher(None, tokens[name], tokens[other], autojunk=True).ratio()
            for other in names
            if other != name
        ) / (len(names) - 1)
    return sorted(names, key=lambda name: (-scores[name], name))[0]


def align_lines(anchor: list[dict], other: list[dict]) -> tuple[list[Match], list[int]]:
    """Monotonic dynamic programming; match 1-2 lines to 1-2 lines or leave gaps."""
    n, m = len(anchor), len(other)
    scores = [[float("-inf")] * (m + 1) for _ in range(n + 1)]
    choices: list[list[tuple | None]] = [[None] * (m + 1) for _ in range(n + 1)]
    scores[n][m] = 0.0
    for i in range(n, -1, -1):
        for j in range(m, -1, -1):
            if i == n and j == m:
                continue
            options: list[tuple[float, tuple]] = []
            if i < n:
                options.append((scores[i + 1][j] - 0.2, ("skip_anchor", 1, 0, 0.0)))
            if j < m:
                options.append((scores[i][j + 1] - 0.2, ("skip_other", 0, 1, 0.0)))
            for a_count in (1, 2):
                for b_count in (1, 2):
                    if i + a_count > n or j + b_count > m:
                        continue
                    left = " ".join(line["text"] for line in anchor[i : i + a_count])
                    right = " ".join(line["text"] for line in other[j : j + b_count])
                    ratio = similarity(left, right)
                    if ratio >= MIN_MATCH:
                        reward = 2 * ratio - 1 - 0.08 * (a_count + b_count - 2)
                        options.append(
                            (scores[i + a_count][j + b_count] + reward,
                             ("match", a_count, b_count, ratio))
                        )
            scores[i][j], choices[i][j] = max(options, key=lambda item: item[0])

    matches: list[Match] = []
    unmatched_other = set(range(m))
    i = j = 0
    while i < n or j < m:
        action, a_count, b_count, ratio = choices[i][j]
        if action == "match":
            matches.append(Match(i, i + a_count, j, j + b_count, ratio))
            unmatched_other.difference_update(range(j, j + b_count))
        i += a_count
        j += b_count
    return matches, sorted(unmatched_other)


def anchor_spans(count: int, all_matches: dict[str, list[Match]]) -> list[tuple[int, int]]:
    breaks = set(range(1, count))
    for matches in all_matches.values():
        for match in matches:
            breaks.difference_update(range(match.anchor_start + 1, match.anchor_end))
    boundaries = [0, *sorted(breaks), count]
    return list(zip(boundaries, boundaries[1:]))


def candidate_reading(
    start: int, end: int, lines: list[dict], matches: list[Match]
) -> dict:
    relevant = [
        match for match in matches
        if start <= match.anchor_start and match.anchor_end <= end
    ]
    indices = sorted({
        index
        for match in relevant
        for index in range(match.other_start, match.other_end)
    })
    covered = {
        index
        for match in relevant
        for index in range(match.anchor_start, match.anchor_end)
    }
    if not relevant:
        quality = "unaligned"
    elif covered == set(range(start, end)) and all(
        match.similarity >= HIGH_MATCH for match in relevant
    ):
        quality = "aligned"
    else:
        quality = "uncertain"
    return {
        "line_numbers": [lines[index]["number"] for index in indices],
        "text": "\n".join(lines[index]["text"] for index in indices),
        "alignment": quality,
        "similarity": round(min((match.similarity for match in relevant), default=0.0), 3),
        "anchor_coverage": round(len(covered) / (end - start), 3),
    }


def difference_examples(readings: dict[str, dict], limit: int = 6) -> list[str]:
    trusted = [
        (name, comparison_text(item["text"]).split())
        for name, item in readings.items()
        if item["alignment"] in {"anchor", "aligned"}
    ]
    examples = []
    pairs = [
        (left_name, left_tokens, right_name, right_tokens)
        for index, (left_name, left_tokens) in enumerate(trusted)
        for right_name, right_tokens in trusted[index + 1 :]
    ]
    pairs.sort(
        key=lambda pair: (
            -SequenceMatcher(None, pair[1], pair[3], autojunk=False).ratio(),
            pair[0],
            pair[2],
        )
    )
    for left_name, left_tokens, right_name, right_tokens in pairs:
        matcher = SequenceMatcher(None, left_tokens, right_tokens, autojunk=False)
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                continue
            left = " ".join(left_tokens[i1:i2])[:45] or "∅"
            right = " ".join(right_tokens[j1:j2])[:45] or "∅"
            item = f"{left_name}: {left} / {right_name}: {right}"
            if item not in examples:
                examples.append(item)
            if len(examples) >= limit:
                return examples
    return examples


def suspicious_tokens(readings: dict[str, dict]) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {
        "possible_ocr_artifact": [],
        "suspicious_internal_symbol": [],
        "possible_digit_letter_confusion": [],
    }
    for name, item in readings.items():
        for token in re.findall(r"\S+", item["text"]):
            label = f"{name}: {token}"
            if any(char in SUSPECT_SYMBOLS for char in token):
                found["possible_ocr_artifact"].append(label)
            if any(
                char in SUSPECT_INTERNAL
                and position > 0
                and position + 1 < len(token)
                and token[position - 1].isalpha()
                and token[position + 1].isalpha()
                for position, char in enumerate(token)
            ):
                found["suspicious_internal_symbol"].append(label)
            if any(
                (left.isalpha() and right.isdigit())
                or (left.isdigit() and right.isalpha())
                for left, right in zip(token, token[1:])
            ):
                found["possible_digit_letter_confusion"].append(label)
    return found


def segment_flags(readings: dict[str, dict]) -> tuple[str, list[dict]]:
    trusted = [
        item["text"] for item in readings.values()
        if item["alignment"] in {"anchor", "aligned"}
    ]
    normalized = [comparison_text(text) for text in trusted]
    if len(trusted) >= 2 and len(set(normalized)) > 1:
        agreement = "low"
    elif len(trusted) >= 2 and all(
        item["alignment"] in {"anchor", "aligned"} for item in readings.values()
    ):
        agreement = "high"
    else:
        agreement = "uncertain"

    flags = []
    if agreement == "low":
        flags.append({
            "category": "candidate_disagreement",
            "examples": difference_examples(readings),
        })
        without_punctuation = [alignment_key(text) for text in normalized]
        if len(set(without_punctuation)) == 1:
            flags.append({"category": "punctuation_disagreement", "examples": []})
    hyphen_states = {
        any(line.rstrip().endswith(LINE_END_HYPHENS) for line in item["text"].splitlines())
        for item in readings.values()
        if item["alignment"] in {"anchor", "aligned"} and item["text"]
    }
    if len(hyphen_states) > 1:
        flags.append({"category": "line_end_hyphen_disagreement", "examples": []})
    suspicious = suspicious_tokens(readings)
    for category, examples in suspicious.items():
        if examples:
            flags.append({
                "category": category,
                "count": len(examples),
                "examples": examples[:8],
            })
    if any(item["alignment"] == "unaligned" for item in readings.values()):
        flags.append({"category": "unaligned", "examples": []})
    elif any(item["alignment"] == "uncertain" for item in readings.values()):
        flags.append({"category": "uncertain_alignment", "examples": []})
    return agreement, flags


def unaligned_blocks(lines: list[dict], indices: list[int], name: str) -> list[dict]:
    blocks = []
    for index in indices:
        if blocks and index == blocks[-1]["last_index"] + 1:
            blocks[-1]["last_index"] = index
            blocks[-1]["line_numbers"].append(lines[index]["number"])
            blocks[-1]["text"] += "\n" + lines[index]["text"]
        else:
            blocks.append({
                "candidate": name,
                "last_index": index,
                "line_numbers": [lines[index]["number"]],
                "text": lines[index]["text"],
                "reason": "unaligned",
            })
    for block in blocks:
        del block["last_index"]
    return blocks


def metadata_row(path: Path, page: int) -> dict:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return next(
            (row for row in csv.DictReader(stream) if int(row["pdf_page"]) == page),
            {},
        )


def build_packet(page: int, root: Path = ROOT) -> dict:
    if page < 1:
        raise ValueError("PDF page must be positive")
    page_map = metadata_row(root / "data" / "page-map.csv", page)
    if not page_map:
        raise ValueError(f"PDF page {page} is absent from data/page-map.csv")
    review = metadata_row(root / "pilot" / "ground_truth" / "review-log.csv", page)
    selection = metadata_row(root / "pilot" / "selection.csv", page)

    raw_candidates, unavailable = {}, []
    for directory in sorted((root / "pilot" / "ocr").iterdir()):
        if not directory.is_dir():
            continue
        path = directory / f"page-{page:03d}.txt"
        if path.is_file():
            raw_candidates[directory.name] = path.read_text(encoding="utf-8-sig")
        else:
            unavailable.append(directory.name)
    if not raw_candidates:
        raise ValueError(f"No OCR candidates available for PDF page {page}")

    anchor_name = choose_anchor(raw_candidates)
    lines = {name: numbered_lines(raw) for name, raw in raw_candidates.items()}
    anchor = lines[anchor_name]
    matches_by_candidate = {}
    unaligned = []
    for name in sorted(raw_candidates):
        if name == anchor_name:
            continue
        matches, unmatched = align_lines(anchor, lines[name])
        matches_by_candidate[name] = matches
        unaligned.extend(unaligned_blocks(lines[name], unmatched, name))

    segments = []
    for number, (start, end) in enumerate(
        anchor_spans(len(anchor), matches_by_candidate), start=1
    ):
        readings = {}
        for name in sorted(raw_candidates):
            if name == anchor_name:
                selected = anchor[start:end]
                readings[name] = {
                    "line_numbers": [line["number"] for line in selected],
                    "text": "\n".join(line["text"] for line in selected),
                    "alignment": "anchor",
                    "similarity": 1.0,
                    "anchor_coverage": 1.0,
                }
            else:
                readings[name] = candidate_reading(
                    start, end, lines[name], matches_by_candidate[name]
                )
        agreement, flags = segment_flags(readings)
        segments.append({
            "id": f"S{number:03d}",
            "anchor_line_numbers": [line["number"] for line in anchor[start:end]],
            "agreement": agreement,
            "readings": readings,
            "flags": flags,
        })

    counts = Counter(segment["agreement"] for segment in segments)
    return {
        "schema_version": 1,
        "pdf_page": page,
        "printed_label": page_map["printed_label"] or None,
        "ia_leaf": int(page_map["ia_leaf"]) if page_map["ia_leaf"] else None,
        "review_status": review.get("status") or "not_started",
        "selected_feature": selection.get("feature") or None,
        "alignment_anchor": anchor_name,
        "available_candidates": sorted(raw_candidates),
        "unavailable_candidates": unavailable,
        "comparison_normalization": (
            "Unicode NFC; long s and selected ligatures expanded; lowercase; "
            "whitespace collapsed. Punctuation is ignored only for alignment."
        ),
        "agreement_counts": {
            name: counts[name] for name in ("high", "low", "uncertain")
        },
        "segments": segments,
        "unaligned_candidate_lines": unaligned,
        "raw_candidates": raw_candidates,
    }


def short(value: str, limit: int = 100) -> str:
    value = " ".join(value.split()).replace("|", "\\|")
    return value if len(value) <= limit else value[: limit - 1] + "…"


def render_markdown(packet: dict) -> str:
    lines = [
        f"# OCR review packet — PDF page {packet['pdf_page']}",
        "",
        f"Printed page: {packet['printed_label'] or 'not recorded'}",
        f"IA leaf: {packet['ia_leaf'] if packet['ia_leaf'] is not None else 'not recorded'}",
        f"Review status: {packet['review_status']}",
        f"Selected feature: {packet['selected_feature'] or 'not recorded'}",
        "",
        "**Comparison aid only.** OCR candidates are not verified transcription. "
        "No candidate is designated correct; check the scan and control copy "
        "before changing any gold-standard text.",
        "",
        f"Candidates available: {', '.join(packet['available_candidates'])}",
        f"Candidates without this page: {', '.join(packet['unavailable_candidates']) or 'none'}",
        f"Alignment anchor (not a quality ranking): {packet['alignment_anchor']}",
        f"Comparison normalization: {packet['comparison_normalization']}",
        "",
        "## Summary",
        "",
        f"- High agreement: {packet['agreement_counts']['high']} segment(s)",
        f"- Low agreement: {packet['agreement_counts']['low']} segment(s)",
        f"- Uncertain agreement: {packet['agreement_counts']['uncertain']} segment(s)",
        f"- Unaligned candidate blocks: {len(packet['unaligned_candidate_lines'])}",
        "",
        "## Review targets",
        "",
        "| Segment | Agreement | Flag categories | Examples |",
        "|---|---|---|---|",
    ]
    priority = [
        segment for segment in packet["segments"]
        if segment["agreement"] != "high" or segment["flags"]
    ]
    for segment in priority:
        categories = ", ".join(flag["category"] for flag in segment["flags"]) or "none"
        examples = [
            example for flag in segment["flags"]
            for example in flag.get("examples", [])[:2]
        ]
        lines.append(
            f"| {segment['id']} | {segment['agreement']} | "
            f"{short(categories, 110)} | {short('; '.join(examples), 140)} |"
        )
    if not priority:
        lines.append("| — | — | No flagged segments | — |")

    lines.extend(["", "## Candidate readings for review targets", ""])
    for segment in priority:
        numbers = ", ".join(str(number) for number in segment["anchor_line_numbers"])
        lines.extend([
            f"### {segment['id']} · anchor OCR line(s) {numbers}",
            "",
            f"Agreement: {segment['agreement']}; flags: "
            f"{', '.join(flag['category'] for flag in segment['flags']) or 'none'}",
            "",
        ])
        for name, item in segment["readings"].items():
            numbers = ", ".join(str(number) for number in item["line_numbers"]) or "none"
            lines.extend([
                f"**{name}** — lines {numbers}; alignment: {item['alignment']}"
                f" (similarity {item['similarity']:.3f}; "
                f"anchor coverage {item['anchor_coverage']:.0%})",
                "",
                f"{FENCE}text",
                item["text"] or "[no confidently aligned text]",
                FENCE,
                "",
            ])

    lines.extend([
        "## Lower-priority aligned segments",
        "",
        "Full original OCR strings for every candidate are retained in the JSON packet.",
        "",
        "| Segment | Anchor OCR line(s) | Anchor excerpt |",
        "|---|---|---|",
    ])
    for segment in packet["segments"]:
        if segment in priority:
            continue
        anchor = segment["readings"][packet["alignment_anchor"]]
        numbers = ", ".join(str(number) for number in segment["anchor_line_numbers"])
        lines.append(f"| {segment['id']} | {numbers} | {short(anchor['text'], 120)} |")
    if len(priority) == len(packet["segments"]):
        lines.append("| — | — | None |")

    lines.extend(["", "## Unaligned candidate lines", ""])
    for block in packet["unaligned_candidate_lines"]:
        numbers = ", ".join(str(number) for number in block["line_numbers"])
        lines.extend([
            f"### {block['candidate']} · OCR line(s) {numbers}",
            "",
            f"{FENCE}text",
            block["text"],
            FENCE,
            "",
        ])
    if not packet["unaligned_candidate_lines"]:
        lines.append("None.")
    lines.extend([
        "",
        "Alignment is monotonic and compares one or two OCR lines against one or two "
        "lines using punctuation-insensitive text similarity. Weak matches are "
        "marked uncertain; skipped lines are unaligned. The anchor is selected "
        "by cross-candidate similarity, not assumed accuracy. Flags are prompts "
        "for human inspection, not corrections.",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf_page", type=int, help="physical PDF page number")
    parser.add_argument(
        "--output-dir", type=Path, default=ROOT / "reports" / "review",
        help="directory for page-NNN.md and page-NNN.json",
    )
    args = parser.parse_args()
    try:
        packet = build_packet(args.pdf_page)
    except ValueError as exc:
        parser.error(str(exc))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    base = args.output_dir / f"page-{args.pdf_page:03d}"
    base.with_suffix(".json").write_text(
        json.dumps(packet, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    base.with_suffix(".md").write_text(
        render_markdown(packet), encoding="utf-8", newline="\n"
    )
    print(
        f"Wrote {base.with_suffix('.md')} and {base.with_suffix('.json')} "
        f"({len(packet['segments'])} segments, "
        f"{packet['agreement_counts']['low']} low agreement, "
        f"{packet['agreement_counts']['uncertain']} uncertain)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
