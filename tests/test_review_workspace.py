"""Read-only workspace data and route safety, using only temporary fixtures."""

import base64
import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from http.server import ThreadingHTTPServer

from scripts.serve_review_workspace import (
    STATIC_DIR,
    load_workspace_page,
    make_handler,
    validate_page,
)


TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ"
    "AAAADUlEQVQIHWP4z8DwHwAFgAI/ScL/nwAAAABJRU5ErkJggg=="
)


class ReviewWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name)
        for relative, contents in {
            "data/page-map.csv": (
                "pdf_page,ia_leaf,printed_label\n"
                "21,21,1\n60,60,40\n115,115,95\n114,114,94\n"
            ),
            "pilot/selection.csv": (
                "pdf_page,feature\n21,ordinary\n60,ordinary\n115,footnote\n"
            ),
            "pilot/ground_truth/review-log.csv": (
                "pdf_page,status\n21,verified\n60,verified\n115,in_review\n"
            ),
        }.items():
            self.write(relative, contents)
        for page, status in ((21, "verified"), (60, "verified"), (115, "in_review")):
            packet = {
                "schema_version": 1,
                "pdf_page": page,
                "printed_label": str(page),
                "review_status": status,
                "available_candidates": ["model"],
                "unavailable_candidates": [],
                "empty_candidates": [],
                "alignment_anchor": "model",
                "priority_counts": {
                    "high": 1, "medium": 0, "low": 0, "alignment_only": 0
                },
                "segments": [{
                    "id": "S001",
                    "anchor_line_numbers": [1],
                    "review_priority": "high",
                    "readings": {"model": {
                        "text": "Some OCR", "line_numbers": [1], "alignment": "anchor"
                    }},
                }],
            }
            self.write(
                f"reports/review/page-{page:03d}.json",
                json.dumps(packet),
            )
            self.write(
                f"pilot/ground_truth/page-{page:03d}.gt.txt",
                f"Human text on {page}\n",
            )

    def tearDown(self):
        self.folder.cleanup()

    def write(self, relative: str, contents: str) -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding="utf-8")

    def test_valid_page_with_local_image(self):
        image = self.root / "pilot/images/page-115.png"
        image.parent.mkdir(parents=True)
        image.write_bytes(TINY_PNG)
        payload = load_workspace_page("115", self.root)
        self.assertTrue(payload["image_available"])
        self.assertEqual(payload["image_url"], "/image")
        self.assertEqual(payload["packet"]["segments"][0]["id"], "S001")
        self.assertEqual(payload["transcription"], "Human text on 115\n")

    def test_valid_page_without_local_image(self):
        payload = load_workspace_page("115", self.root)
        self.assertFalse(payload["image_available"])
        self.assertIsNone(payload["image_url"])

    def test_verified_and_in_review_status_comes_from_review_log(self):
        self.assertEqual(load_workspace_page("21", self.root)["review_status"], "verified")
        self.assertEqual(load_workspace_page("60", self.root)["review_status"], "verified")
        self.assertEqual(load_workspace_page("115", self.root)["review_status"], "in_review")
        packet_path = self.root / "reports/review/page-115.json"
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
        packet["review_status"] = "verified"
        packet_path.write_text(json.dumps(packet), encoding="utf-8")
        payload = load_workspace_page("115", self.root)
        self.assertEqual(payload["review_status"], "in_review")
        self.assertTrue(payload["packet_status_outdated"])

    def test_invalid_unknown_and_path_like_page_rejected(self):
        for raw in ("0", "-1", "114", "9999", "../115", "115/../21", "115?file=x"):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                validate_page(raw, self.root)

    def test_server_exposes_only_selected_assets(self):
        image = self.root / "pilot/images/page-115.png"
        image.parent.mkdir(parents=True)
        image.write_bytes(TINY_PNG)
        payload = load_workspace_page("115", self.root)
        server = ThreadingHTTPServer(
            ("127.0.0.1", 0), make_handler(payload, self.root, STATIC_DIR)
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            with urlopen(base + "/api/page") as response:
                served = json.load(response)
                self.assertEqual(served["review_status"], "in_review")
                self.assertEqual(served["packet"]["pdf_page"], 115)
            with urlopen(base + "/image") as response:
                self.assertEqual(response.headers["Content-Type"], "image/png")
                self.assertEqual(response.read(), TINY_PNG)
            with urlopen(base + "/") as response:
                self.assertIn(b"Current transcription", response.read())
            for route in ("/%2e%2e/page-021.gt.txt", "/api/page?file=../", "/pilot/ground_truth/page-115.gt.txt"):
                with self.subTest(route=route), self.assertRaises(HTTPError) as error:
                    urlopen(base + route)
                self.assertEqual(error.exception.code, 404)
        finally:
            server.shutdown()
            thread.join(timeout=3)
            server.server_close()

    def test_missing_image_and_write_or_foreign_host_requests_are_rejected(self):
        payload = load_workspace_page("115", self.root)
        server = ThreadingHTTPServer(
            ("127.0.0.1", 0), make_handler(payload, self.root, STATIC_DIR)
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            with self.assertRaises(HTTPError) as missing:
                urlopen(base + "/image")
            self.assertEqual(missing.exception.code, 404)
            with self.assertRaises(HTTPError) as readonly:
                urlopen(Request(base + "/api/page", data=b"change"))
            self.assertEqual(readonly.exception.code, 405)
            foreign = Request(base + "/api/page", headers={"Host": "example.org"})
            with self.assertRaises(HTTPError) as rejected:
                urlopen(foreign)
            self.assertEqual(rejected.exception.code, 403)
        finally:
            server.shutdown()
            thread.join(timeout=3)
            server.server_close()


if __name__ == "__main__":
    unittest.main()
