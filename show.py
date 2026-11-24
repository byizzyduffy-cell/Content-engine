"""
Opens one of the student's pages (their planner, a lookbook, the post library) in their web browser.

Frances, 2026-10-14: the planner's Download button played the video instead of saving it. Browsers won't
save files for a page opened straight from the computer, so the pages are shown through a tiny web server
instead, one that only this computer can reach. There, Download saves the file into their Downloads with
a name they'll recognise ("Skin Survival 21 October reel.mp4"), in any browser, on a Mac or on Windows.

    PY engine/show.py "My Content/2026-10/planner.html"

The server shares only the "My Content" folder, starts the first time it's needed, and stops by itself
after a few hours with nothing asked of it. If it can't start, the page opens straight from the computer
as before (everything works except Download, which may play the video instead).
"""

import tools  # noqa: F401  (first: emoji-safe output on Windows)
import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

PORTS = range(8765, 8785)
IDLE_HOURS = 6
PING = "/__clinic_engine__"


def content_root(page):
    """The "My Content" folder the page sits in (the planner links to the library next door), else its own folder."""
    page = os.path.abspath(page)
    folder = os.path.dirname(page)
    while True:
        if os.path.basename(folder) == "My Content":
            return folder
        up = os.path.dirname(folder)
        if up == folder:
            return os.path.dirname(page)
        folder = up


class Handler(SimpleHTTPRequestHandler):
    last_seen = time.time()

    def log_message(self, *args):
        pass

    def do_GET(self):
        Handler.last_seen = time.time()
        if self.path == PING:
            body = json.dumps({"root": self.directory}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()

    def do_POST(self):
        """The planner's "fully ready to post" ticks (Frances, 2026-11-20): saved in the month's signed-off.json,
        {"days": ["2026-12-03", ...]}, so Claude and the next planner see them. Only that file, only inside
        My Content, only from this computer."""
        Handler.last_seen = time.time()
        if self.path != PING + "/signoff":
            self.send_error(404)
            return
        try:
            asked = json.loads(self.rfile.read(min(int(self.headers.get("Content-Length", 0)), 10000)) or b"{}")
            day, on = str(asked.get("day", "")), bool(asked.get("on"))
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
                raise ValueError("not a day")
            root = os.path.realpath(self.directory)
            folder = os.path.realpath(os.path.join(root, str(asked.get("folder", "")).strip("/\\")))
            if os.path.commonpath([root, folder]) != root or not os.path.isdir(folder):
                raise ValueError("not a month folder")
            path = os.path.join(folder, "signed-off.json")
            try:
                days = json.load(open(path, encoding="utf-8")).get("days", [])
            except (OSError, ValueError):
                days = []
            name = os.path.basename(folder)
            days = {f"{name}-{int(d):02d}" if re.fullmatch(r"\d+", str(d)) and re.fullmatch(r"\d{4}-\d{2}", name)
                    else str(d) for d in days}
            (days.add if on else days.discard)(day)
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"days": sorted(days)}, f, indent=1)
            body = json.dumps({"days": sorted(days)}).encode()
            self.send_response(200)
        except (ValueError, TypeError) as e:
            body = json.dumps({"problem": str(e)}).encode()
            self.send_response(400)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")    # a rebuilt planner always shows its newest version
        super().end_headers()

    def send_head(self):
        """Files with byte ranges (Safari won't play a video without them) and, with ?dl=<name>, saved as <name>."""
        path = self.translate_path(self.path)
        if os.path.isdir(path):
            if not os.path.exists(os.path.join(path, "index.html")):
                self.send_error(404)                     # no folder listings
                return None
            return super().send_head()
        if not os.path.isfile(path):
            self.send_error(404)
            return None
        size = os.path.getsize(path)
        start, end, status = 0, size - 1, 200
        asked = self.headers.get("Range", "")
        if asked.startswith("bytes="):
            first, _, last = asked[6:].split(",")[0].strip().partition("-")
            try:
                if first:
                    start, end = int(first), min(int(last) if last else size - 1, size - 1)
                else:
                    start = max(0, size - int(last))
                if start > end:
                    raise ValueError
                status = 206
            except ValueError:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.end_headers()
                return None
        f = open(path, "rb")
        f.seek(start)
        self.send_response(status)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        if status == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        name = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("dl")
        if name:
            plain = name[0].encode("ascii", "replace").decode().replace('"', "")
            self.send_header("Content-Disposition",
                             f"attachment; filename=\"{plain}\"; filename*=UTF-8''{urllib.parse.quote(name[0])}")
        self.end_headers()
        self.left = end - start + 1
        return f

    def copyfile(self, source, outputfile):
        left = getattr(self, "left", None)
        try:
            if left is None:
                return super().copyfile(source, outputfile)
            while left > 0:
                chunk = source.read(min(1 << 16, left))
                if not chunk:
                    break
                outputfile.write(chunk)
                left -= len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass                                         # the browser stopped reading (skipping through a video)


def serve(root, port):
    server = ThreadingHTTPServer(("127.0.0.1", port), lambda *a, **k: Handler(*a, directory=root, **k))

    def stop_when_idle():
        while time.time() - Handler.last_seen < IDLE_HOURS * 3600:
            time.sleep(60)
        server.shutdown()

    threading.Thread(target=stop_when_idle, daemon=True).start()
    server.serve_forever()


def running_root(port):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}{PING}", timeout=1) as answer:
            return json.load(answer).get("root")
    except Exception:
        return None


def in_use(port):
    try:
        socket.create_connection(("127.0.0.1", port), timeout=0.3).close()
        return True
    except OSError:
        return False


def same(a, b):
    try:
        return os.path.samefile(a, b)
    except OSError:
        return False


def start_server(root):
    """The port of a server sharing this "My Content" (one already running, or a new one). None if it can't start."""
    for port in PORTS:
        found = running_root(port)
        if found and same(found, root):
            return port
        if found or in_use(port):
            continue                                     # another engine copy's server, or another app: next port
        options = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
        if os.name == "nt":
            options["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            options["start_new_session"] = True          # keeps running after this command finishes
        subprocess.Popen([sys.executable, os.path.abspath(__file__), "--serve", root, str(port)], **options)
        for _ in range(50):
            time.sleep(0.1)
            found = running_root(port)
            if found:
                return port if same(found, root) else None
        # That port was taken by something else: try the next one.
    return None


def main(argv):
    if argv[:1] == ["--serve"]:
        serve(argv[1], int(argv[2]))
        return
    show = "--no-open" not in argv
    pages = [a for a in argv if a != "--no-open"]
    if len(pages) != 1 or not os.path.isfile(pages[0]):
        sys.exit("Usage: show.py <page.html> [--no-open]")
    page = os.path.abspath(pages[0])
    root = content_root(page)
    port = start_server(root)
    if port:
        address = f"http://127.0.0.1:{port}/" + urllib.parse.quote(os.path.relpath(page, root).replace(os.sep, "/"))
    else:
        address = "file://" + urllib.request.pathname2url(page) if os.name != "nt" else "file:" + urllib.request.pathname2url(page)
        print("NOTE: couldn't start the page server, so the page opens straight from the computer "
              "(Download may play videos instead of saving them).")
    if show:
        webbrowser.open(address)
    print(f"OPEN: {address}")


if __name__ == "__main__":
    main(sys.argv[1:])
