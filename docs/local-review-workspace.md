# Local, read-only transcription review workspace

This is an internal aid for checking the pilot's human transcription. It is **not** the public bilingual reader, a second draft store, or an OCR correction system. The source scan, OCR candidates, and current human text appear in one local browser view.

From the repository root (Python 3.10+):

```powershell
python scripts/serve_review_workspace.py --page 115
```

Open the printed `http://127.0.0.1:8765/` URL, or add `--open-browser`. Use `--port 0` if 8765 is occupied; the command prints the chosen port. Press Ctrl+C to stop. Start a new command with `--page 21` or `--page 60` to inspect the verified examples. The server binds only to `127.0.0.1` and serves only the selected page's data/image and named UI assets. Do not expose it through a reverse proxy or use it as a public site.

The workspace loads `reports/review/page-NNN.json` when present. For pilot pages without a saved packet, it constructs the same packet schema **in memory** from checked-in OCR and metadata; it does not write a new report. Regenerate a saved packet if its OCR inputs change. The current review status always comes from `pilot/ground_truth/review-log.csv`. If a saved packet's recorded status differs, the view warns about it. The current `pilot/ground_truth/page-NNN.gt.txt` is shown read-only. Page 115's nonempty text remains **in review**, not verified; pages 21 and 60 are verified. No transcription, review-log entry, or OCR candidate is changed by this tool.

The local `pilot/images/page-NNN.png` is shown when it exists. If it is absent (as it will be in a fresh Git clone), the view explains that the local image is unavailable. Images remain excluded from Git. The scan can be zoomed and scrolled, but the workspace does not highlight image regions: the review packet has OCR line numbers, **not scan coordinates**.

The High, Medium, Low, and alignment-only queues come directly from the packet. Choose a queue and move among its segments, then compare every available OCR reading and its line numbers, alignment, similarity, and coverage. Token differences are highlighted relative to the *alignment anchor* only; that anchor is a coordinate choice, not the correct reading. Uncertain/unaligned readings are still displayed but are not force-diffed. Priority is inspection priority, not OCR correctness or transcription confidence. All human decisions must return to the scan and, if needed, the independent control copy.

## Try it before adding editing

Open page 115, inspect 3–5 High-priority segments, and compare this experience with switching between image, Markdown report, OCR files, and the current text. Note which movements remain difficult. There is deliberately no Save button, reviewed count, or progress persistence in this version.

Segment IDs such as `S017` are **packet-local**: an OCR/alignment change can renumber or reshape segments (page 115 has already changed once). A later progress store must include a packet/schema fingerprint and detect changes before reattaching any human decisions. The future write path is also undecided: page 115 already has one nonempty `.gt.txt` working transcription, so this tool does not create a competing draft file.
