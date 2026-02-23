#!/usr/bin/env python3
"""
Simple HTTP server on port 8080. Self-contained (stdlib only) for easy porting.
"""
from __future__ import annotations

import http.server
import subprocess
import socketserver
from pathlib import Path
from urllib.parse import parse_qs, quote_plus, unquote_plus, urlparse

DEFAULT_PORT = 8080

PAGE_HTML = """<!DOCTYPE html>
<html>
<head><title>Scan server</title></head>
<body>
<h1>Scan server</h1>
<p>Server is running.</p>
</body>
</html>
"""


def _is_capture_lot_folder(name: str) -> bool:
    """True if name is exactly three digits followed by an underscore."""
    return len(name) >= 4 and name[:3].isdigit() and name[3] == "_"


def _get_all_capture_folders_sorted(working_dir: Path) -> list[Path]:
    """Return all folders under working_dir/Capture matching NNN_*, sorted by number (001, 002, ...)."""
    capture_dir = working_dir / "Capture"
    if not capture_dir.is_dir():
        return []
    folders = [
        child
        for child in capture_dir.iterdir()
        if child.is_dir() and _is_capture_lot_folder(child.name)
    ]
    folders.sort(key=lambda p: int(p.name[:3]))
    return folders


def _get_latest_capture_folder(working_dir: Path) -> Path | None:
    """Return the most recently created folder under working_dir/Capture matching NNN_*."""
    capture_dir = working_dir / "Capture"
    if not capture_dir.is_dir():
        return None
    candidates = []
    for child in capture_dir.iterdir():
        if child.is_dir() and _is_capture_lot_folder(child.name):
            st = child.stat()
            # Prefer creation time (macOS: st_birthtime), else ctime/mtime
            t = getattr(st, "st_birthtime", None) or st.st_ctime or st.st_mtime
            candidates.append((t, child))
    if not candidates:
        return None
    candidates.sort(key=lambda p: p[0], reverse=True)
    return candidates[0][1]


def _get_capture_folder_by_prefix(working_dir: Path, prefix: str) -> Path | None:
    """Return the folder under Capture whose name starts with prefix (e.g. '011'), or None."""
    if len(prefix) != 3 or not prefix.isdigit():
        return None
    capture_dir = working_dir / "Capture"
    if not capture_dir.is_dir():
        return None
    target = f"{prefix}_"
    for child in capture_dir.iterdir():
        if child.is_dir() and child.name.startswith(target):
            return child
    return None


def _subfolder_display_name(name: str) -> str:
    """
    Return the segment between the last '-' before '__' and the '__'.

    Examples:
      NF0A8HRZG5O-HERO__FRONT-FACING      -> HERO
      NF0A8HRZG5O-BACK__BACK-FACING      -> BACK
      NF0A8HRZG5O-DETAIL3__FABRIC-DETAIL -> DETAIL3
    """
    sep_index = name.rfind("__")
    if sep_index == -1:
        return name
    before_sep = name[:sep_index]
    dash_index = before_sep.rfind("-")
    if dash_index == -1:
        return before_sep
    return before_sep[dash_index + 1 :]


def _build_capture_page(
    current_folder: Path | None,
    working_dir: Path,
    all_folders_sorted: list[Path],
    set_error: str | None = None,
) -> str:
    """Build HTML for the capture view: dark theme, header with prev/next arrows, 2-column button grid."""
    style = """
    body { background: #000; color: #fff; font-family: sans-serif; margin: 2rem; }
    .header { display: flex; align-items: center; justify-content: center; gap: 1rem; margin-bottom: 0.5rem; }
    .header a, .header span { display: inline-flex; align-items: center; justify-content: center; width: 2.5rem; height: 2.5rem; border: 1px solid #fff; background: transparent; color: #fff; font-size: 1.25rem; text-decoration: none; }
    .header a:hover { background: rgba(255,255,255,0.1); }
    .header span { opacity: 0.3; cursor: default; }
    .header h1 { margin: 0; font-weight: normal; font-size: 1.5rem; min-width: 12rem; text-align: center; }
    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; max-width: 24rem; margin: 2rem auto; }
    .grid form { margin: 0; }
    .grid button { width: 100%; padding: 0.75rem 1rem; border: 1px solid #fff; background: transparent; color: #fff; font-size: 1rem; cursor: pointer; text-align: left; }
    .grid button:hover { background: rgba(255,255,255,0.1); }
    .set-error { margin: 1rem auto; max-width: 24rem; padding: 0.5rem; background: #400; color: #fff; font-size: 0.9rem; }
    """
    if current_folder is None:
        return f"""<!DOCTYPE html>
<html>
<head><title>Scan server</title><style>{style}</style></head>
<body>
<h1 style="text-align: center;">No Lot # folders found.</h1>
<p style="text-align: center;">Refresh after you have scanned a tag.</p>
<p style="text-align: center;"><a href="/" style="display: inline-block; padding: 0.5rem 1rem; border: 1px solid #fff; color: #fff; text-decoration: none;">Refresh</a></p>
<p style="text-align: center;"><img id="dog-image" src="" alt="A cute dog" width="400"></p>
<script>
fetch('https://dog.ceo/api/breeds/image/random')
  .then(response => response.json())
  .then(data => {{
    document.getElementById('dog-image').src = data.message;
  }})
  .catch(error => console.error('Error:', error));
</script>
</body>
</html>"""
    # Resolve prev/next by position in sorted list
    try:
        idx = next(i for i, p in enumerate(all_folders_sorted) if p == current_folder)
    except StopIteration:
        idx = -1
    prev_folder = all_folders_sorted[idx - 1] if idx > 0 else None
    # Right arrow always links to next folder number; server re-checks on request (folder may be created after load)
    next_prefix = f"{int(current_folder.name[:3]) + 1:03d}"
    left_arrow = (
        f'<a href="?folder={prev_folder.name[:3]}" title="Previous folder">&#8592;</a>'
        if prev_folder is not None
        else '<span title="No previous folder">&#8592;</span>'
    )
    right_arrow = (
        f'<a href="?folder={next_prefix}" title="Next folder (checks for new folders)">&#8594;</a>'
    )
    subdirs = sorted(
        [d for d in current_folder.iterdir() if d.is_dir()],
        key=lambda d: d.name,
    )
    buttons_html = "".join(
        f'<form method="post" action="/set">'
        f'<input type="hidden" name="path" value="{_escape_html_attr(str(d.resolve()))}">'
        f'<button type="submit">{_escape_html(_subfolder_display_name(d.name))}</button>'
        f'</form>'
        for d in subdirs
    )
    error_block = (
        f'<p class="set-error">{_escape_html(set_error)}</p>' if set_error else ""
    )
    return f"""<!DOCTYPE html>
<html>
<head><title>Scan server</title><style>{style}</style></head>
<body>
<div class="header">
{left_arrow}
<h1>{_escape_html(current_folder.name)}</h1>
{right_arrow}
</div>
{error_block}
<div class="grid">
{buttons_html}
</div>
</body>
</html>"""


def _escape_html(s: str) -> str:
    """Escape for safe use in HTML text content."""
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _escape_html_attr(s: str) -> str:
    """Escape for safe use in an HTML attribute value (e.g. value=\"...\")."""
    return _escape_html(s)


CAPTURE_ONE_SET_FOLDER_SCRIPT = '''tell application "Capture One"
	set doc to current document
	set currentCaptureFolderPOSIX to "{path}"
	tell doc
		set captures to currentCaptureFolderPOSIX
	end tell
end tell'''


def _set_capture_one_folder(posix_path: str) -> tuple[bool, str]:
    """Run AppleScript to set Capture One's current capture folder to posix_path.
    Returns (success, error_message). Only runs on macOS."""
    import sys
    if sys.platform != "darwin":
        return False, "Capture One script is only supported on macOS"
    # Escape for embedding in AppleScript string: \ -> \\, " -> \"
    escaped = posix_path.replace("\\", "\\\\").replace('"', '\\"')
    script = CAPTURE_ONE_SET_FOLDER_SCRIPT.format(path=escaped)
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return False, (result.stderr or result.stdout or "Unknown error").strip()
        return True, ""
    except subprocess.TimeoutExpired:
        return False, "AppleScript timed out"
    except FileNotFoundError:
        return False, "osascript not found"
    except Exception as e:
        return False, str(e)


class ScanHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        working_dir = getattr(self.server, "working_dir", None)
        path = urlparse(self.path).path.rstrip("/") or "/"
        if path == "/":
            query = parse_qs(urlparse(self.path).query)
            folder_param = (query.get("folder") or [None])[0]
            # If a specific folder was requested but doesn't exist (yet), redirect to /
            # so the next click sees the new folder. Must do this before sending 200.
            if working_dir is not None and folder_param:
                requested_prefix = str(folder_param).strip()[:3]
                if requested_prefix.isdigit() and len(requested_prefix) == 3:
                    current = _get_capture_folder_by_prefix(
                        working_dir, requested_prefix
                    )
                    if current is None:
                        self.send_response(303)
                        self.send_header("Location", "/")
                        self.send_header("Cache-Control", "no-store")
                        self.end_headers()
                        return
            # Normal response: build body then send headers once
            if working_dir is not None:
                all_folders = _get_all_capture_folders_sorted(working_dir)
                current = None
                if folder_param:
                    requested_prefix = str(folder_param).strip()[:3]
                    current = _get_capture_folder_by_prefix(
                        working_dir, requested_prefix
                    )
                if current is None:
                    current = _get_latest_capture_folder(working_dir)
                set_error = (query.get("set_error") or [None])[0]
                body = _build_capture_page(
                    current, working_dir, all_folders, set_error=set_error
                )
            else:
                body = PAGE_HTML
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body.encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        path = urlparse(self.path).path.rstrip("/") or "/"
        if path != "/set":
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8", errors="replace")
        form = parse_qs(body, keep_blank_values=True)
        posix_path = (form.get("path") or [None])[0]
        redirect_to = self.headers.get("Referer") or "/"
        if posix_path and posix_path.strip():
            posix_path = unquote_plus(posix_path.strip())
            ok, err = _set_capture_one_folder(posix_path)
            if not ok and err:
                sep = "&" if "?" in redirect_to else "?"
                redirect_to = redirect_to + sep + "set_error=" + quote_plus(err[:200])
        self.send_response(303)
        self.send_header("Location", redirect_to)
        self.end_headers()

    def log_message(self, format, *args):
        pass  # quiet by default; override to enable request logging


def run_server(port: int = DEFAULT_PORT, working_dir: Path | str | None = None) -> int:
    """Start the HTTP server (blocks until interrupted). Returns 0 on normal exit.
    working_dir is optional; when set, the server can use it for request handling."""
    class Server(socketserver.TCPServer):
        allow_reuse_address = True
    httpd = Server(("", port), ScanHandler)
    httpd.working_dir = Path(working_dir) if working_dir else None
    try:
        print(f"Serving at http://localhost:{port}/ (Ctrl+C to stop)")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(run_server())
