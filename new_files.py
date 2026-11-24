"""
Lists the videos, photos or voice recordings that have just arrived in their Downloads (AirDropped from
their phone, or downloaded), newest first, so Claude finds them for the student without asking.

    PY engine/new_files.py videos [--days 7] [--min-seconds 10]
    PY engine/new_files.py photos [--days 7]
    PY engine/new_files.py voice  [--days 7]
    (--folder "<somewhere else>" looks in another folder instead of Downloads)

"Arrived" is when the file landed in the folder, not when it was filmed: a video filmed a fortnight ago
and AirDropped today counts as today (Sonnet test, 2026-10-14: clips filmed 8 days earlier were missed when
going by the file's own date).
"""

import tools  # noqa: F401  (first: emoji-safe output on Windows)
import argparse
import datetime
import os
import subprocess
import time

KINDS = {
    "videos": (".mov", ".mp4", ".m4v"),
    "photos": (".jpg", ".jpeg", ".heic", ".png", ".webp"),
    "voice": (".m4a", ".wav", ".mp3", ".aac", ".mov", ".mp4", ".m4v"),
}


def downloads():
    home = os.path.expanduser("~")
    for folder in (os.path.join(home, "Downloads"), os.path.join(home, "OneDrive", "Downloads")):
        if os.path.isdir(folder):
            return folder
    return os.path.join(home, "Downloads")


def arrived(path):
    """When the file landed here. AirDrop and downloads keep the filming date as the file's own date, but
    the moment it was written into the folder shows in its change time (Mac) or creation time (Windows)."""
    info = os.stat(path)
    return max(info.st_mtime, info.st_ctime)


def seconds(path):
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                             capture_output=True, text=True, timeout=30).stdout.strip()
        return float(out)
    except (ValueError, OSError, subprocess.SubprocessError):
        return None


def main():
    ask = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ask.add_argument("kind", choices=KINDS)
    ask.add_argument("--days", type=float, default=7)
    ask.add_argument("--min-seconds", type=float, default=0)
    ask.add_argument("--folder", default=None)
    a = ask.parse_args()
    folder = a.folder or downloads()
    since = time.time() - a.days * 86400
    found = []
    for name in os.listdir(folder) if os.path.isdir(folder) else []:
        path = os.path.join(folder, name)
        if name.startswith(".") or not os.path.isfile(path) or not name.lower().endswith(KINDS[a.kind]):
            continue
        when = arrived(path)
        if when < since:
            continue
        length = seconds(path) if a.kind != "photos" else None
        if a.min_seconds and (length is None or length < a.min_seconds):
            continue
        found.append((when, length, path))
    if not found:
        print(f"NONE: no {a.kind} arrived in {folder} in the last {a.days:g} days.")
        return
    for when, length, path in sorted(found, reverse=True):
        stamp = datetime.datetime.fromtimestamp(when).strftime("%a %d %b %H:%M")
        size = f"{length:6.1f}s" if length is not None else ""
        print(f"{stamp}  {size}  {path}".replace("   ", "  "))


if __name__ == "__main__":
    main()
