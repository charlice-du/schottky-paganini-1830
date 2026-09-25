"""Serve one pilot page in a local, read-only human-review workspace."""

import argparse
import json
import re
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

if __package__:
    from .build_review_packet import ROOT, build_packet, metadata_row
else:
    from build_review_packet import ROOT, build_packet, metadata_row


STATIC_DIR = ROOT / "web" / "review-workspace"
STATIC_ROUTES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.css": ("app.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
}
SECURITY_HEADERS = {
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": (
        "default-src 'none'; connect-src 'self'; img-src 'self'; "
        "script-src 'self'; style-src 'self'; base-uri 'none'; "
        "frame-ancestors 'none'"
    ),
}


def validate_page(raw: str, root: Path = ROOT) -> int:
    """Accept only selected, mapped pilot PDF pages; never a path fragment."""
    if not re.fullmatch(r"[1-9][0-9]{0,3}", raw):
        raise ValueError("PDF page must be a positive decimal page number")
    page = int(raw)
    if not metadata_row(root / "data" / "page-map.csv", page):
        raise ValueError(f"PDF page {page} is absent from the page map")
    if not metadata_row(root / "pilot" / "selection.csv", page):
        raise ValueError(f"PDF page {page} is not a selected pilot page")
    return page


def within(path: Path, directory: Path) -> bool:
    """Reject symlinks that lead outside an explicitly allowed directory."""
    return path.resolve().is_relative_to(directory.resolve())


def load_workspace_page(raw_page: str, root: Path = ROOT) -> dict:
    """Load a saved packet, or build the same schema in memory if absent."""
    page = validate_page(raw_page, root)
    packet_dir = root / "reports" / "review"
    packet_path = packet_dir / f"page-{page:03d}.json"
    if packet_path.is_file():
        if not within(packet_path, packet_dir) or not within(packet_path, root):
            raise ValueError("Packet path escapes the review-report directory")
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
    else:
        packet = build_packet(page, root)
    if (
        not isinstance(packet, dict)
        or packet.get("schema_version") != 1
        or packet.get("pdf_page") != page
    ):
        raise ValueError(f"Invalid review packet for PDF page {page}")

    review = metadata_row(root / "pilot" / "ground_truth" / "review-log.csv", page)
    status = review.get("status") or "not_started"
    transcription_dir = root / "pilot" / "ground_truth"
    transcription_path = transcription_dir / f"page-{page:03d}.gt.txt"
    if transcription_path.is_file():
        if not within(transcription_path, transcription_dir) or not within(transcription_path, root):
            raise ValueError("Transcription path escapes the ground-truth directory")
        transcription = transcription_path.read_text(encoding="utf-8-sig")
    else:
        transcription = ""

    image_dir = root / "pilot" / "images"
    image_path = image_dir / f"page-{page:03d}.png"
    image_available = (
        image_path.is_file()
        and within(image_path, image_dir)
        and within(image_path, root)
    )
    return {
        "packet": packet,
        "review_status": status,
        "packet_status_outdated": packet.get("review_status") != status,
        "transcription": transcription,
        "image_available": image_available,
        "image_url": "/image" if image_available else None,
    }


def make_handler(payload: dict, root: Path = ROOT, static_dir: Path = STATIC_DIR):
    """Expose only this page's scan, packet data, and three named UI assets."""
    page = payload["packet"]["pdf_page"]
    image_dir = root / "pilot" / "images"
    image_path = image_dir / f"page-{page:03d}.png"

    class ReviewHandler(BaseHTTPRequestHandler):
        def respond(self, status: int, content: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            for name, value in SECURITY_HEADERS.items():
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(content)

        def do_GET(self) -> None:
            allowed_hosts = {
                f"127.0.0.1:{self.server.server_port}",
                f"localhost:{self.server.server_port}",
            }
            host = self.headers.get("Host")
            if host and host not in allowed_hosts:
                self.respond(403, b"Invalid local Host header\n", "text/plain; charset=utf-8")
                return
            if self.path in STATIC_ROUTES:
                filename, content_type = STATIC_ROUTES[self.path]
                self.respond(200, (static_dir / filename).read_bytes(), content_type)
            elif self.path == "/api/page":
                content = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.respond(200, content, "application/json; charset=utf-8")
            elif self.path == "/image" and payload["image_available"]:
                if (
                    image_path.is_file()
                    and within(image_path, image_dir)
                    and within(image_path, root)
                ):
                    self.respond(200, image_path.read_bytes(), "image/png")
                else:
                    self.respond(404, b"Local page image unavailable\n", "text/plain; charset=utf-8")
            else:
                self.respond(404, b"Not found\n", "text/plain; charset=utf-8")

        def do_POST(self) -> None:
            self.respond(405, b"Read-only workspace\n", "text/plain; charset=utf-8")

    return ReviewHandler


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--page", default="115", help="selected physical PDF page, e.g. 115")
    parser.add_argument("--port", type=int, default=8765, help="local port (0 chooses a free port)")
    parser.add_argument("--open-browser", action="store_true", help="open the local URL")
    args = parser.parse_args()
    if not 0 <= args.port <= 65535:
        parser.error("port must be between 0 and 65535")
    try:
        payload = load_workspace_page(args.page)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))

    try:
        server = ThreadingHTTPServer(
            ("127.0.0.1", args.port), make_handler(payload)
        )
    except OSError as exc:
        parser.error(f"could not start the local server: {exc}")
    url = f"http://127.0.0.1:{server.server_port}/"
    print(f"Read-only review workspace: {url}", flush=True)
    print("Press Ctrl+C to stop. The server never writes transcriptions or status.", flush=True)
    if args.open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
