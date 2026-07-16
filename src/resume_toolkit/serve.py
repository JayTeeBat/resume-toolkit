"""Live-reloading browser preview.

Deliberately dependency-free: the stdlib HTTP server plus a mtime poll is enough,
and it keeps a websocket/watchdog dependency out of the project for what is only
a convenience during CSS iteration.
"""

from __future__ import annotations

import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .model import ValidationFailed, load_resume
from .paths import RESUME_JSON
from .render import UnknownTheme, render_html, theme_dir
from .variants import Variant, apply_variant
from .version import build_stamp


class PortInUse(Exception):
    pass


# Polled by the injected script; a changed value triggers location.reload().
_RELOAD_SCRIPT = """
<script>
setInterval(async () => {
  try {
    const r = await fetch('/__stamp');
    const s = await r.text();
    if (window.__stamp && window.__stamp !== s) location.reload();
    window.__stamp = s;
  } catch (e) { /* server restarting; ignore */ }
}, 500);
</script>
"""


def _watched(theme: str) -> list[Path]:
    paths = [RESUME_JSON]
    try:
        paths.extend(sorted(theme_dir(theme).rglob("*")))
    except UnknownTheme:
        pass
    return [p for p in paths if p.is_file()]


def _stamp(theme: str) -> str:
    return str(max((p.stat().st_mtime_ns for p in _watched(theme)), default=0))


def _error_page(message: str) -> str:
    from html import escape

    return (
        "<!doctype html><meta charset='utf-8'>"
        "<body style=\"font:14px ui-monospace,monospace;padding:2rem;"
        'background:#2b2b2b;color:#f88">'
        f"<h2>Build error</h2><pre style='white-space:pre-wrap'>{escape(message)}</pre>"
        f"{_RELOAD_SCRIPT}</body>"
    )


def serve_preview(variant: Variant, *, theme: str = "classic", port: int = 8000) -> None:
    def current_html() -> str:
        try:
            resume = load_resume()
        except ValidationFailed as exc:
            return _error_page("resume.json does not satisfy the schema:\n\n" + "\n".join(exc.errors))
        except (OSError, ValueError) as exc:
            return _error_page(f"could not read resume.json:\n\n{exc}")
        try:
            html = render_html(
                apply_variant(resume, variant),
                theme=theme,
                variant=variant.name,
                stamp=build_stamp(),
            )
        except Exception as exc:  # noqa: BLE001 - show it in the page, don't kill the server
            return _error_page(f"{type(exc).__name__}: {exc}")
        return html.replace("</body>", _RELOAD_SCRIPT + "</body>")

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - stdlib naming
            if self.path == "/__stamp":
                body = _stamp(theme).encode()
                ctype = "text/plain"
            else:
                body = current_html().encode("utf-8")
                ctype = "text/html; charset=utf-8"
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args) -> None:
            pass  # the poll would otherwise spam a line every 500ms

    class Server(ThreadingHTTPServer):
        # HTTPServer defaults this to 1. On Windows, SO_REUSEADDR lets a second
        # socket bind a port that is already taken rather than refusing: both
        # then listen, the incumbent keeps answering, and the preview silently
        # serves whatever else is on the port. Refuse instead, so a busy port is
        # a clear error rather than a confusing 404 from someone else's app.
        allow_reuse_address = False

    url = f"http://127.0.0.1:{port}/"
    try:
        server = Server(("127.0.0.1", port), Handler)
    except OSError as exc:
        raise PortInUse(
            f"port {port} is already in use, so the preview cannot start.\n"
            f"  Try a different one:  resume serve --port {port + 1}"
        ) from exc
    print(f"preview: {url}  (variant: {variant.name}, theme: {theme})")
    print("watching resume.json and themes/ — edit and the page reloads. Ctrl+C to stop.")
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        server.server_close()
