"""
Finds the engine's outside tools (FFmpeg, ffprobe and whisper's listener), so
the engine works the same on a Mac (Homebrew puts them on the PATH) and on
Windows (set me up unzips whisper into engine/bin/whisper).
"""

import os
import shutil
import sys

# On Windows, output going to Claude is often not UTF-8, so printing an emoji or a curly quote would crash.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
BIN = os.path.join(HERE, "bin")

# The all-in-one download keeps FFmpeg, ffprobe and whisper in engine/bin, so every part of the
# engine that calls "ffmpeg" by name finds them there first, with nothing installed on the computer.
if os.path.isdir(BIN):
    os.environ["PATH"] = BIN + os.pathsep + os.environ.get("PATH", "")


def tool(name):
    """The full path to a tool: engine/bin first (and the folders inside it), then the computer's PATH.
    Falls back to the bare name, so the error says which tool is missing."""
    names = [name, name + ".exe"] + (["main", "main.exe"] if name == "whisper-cli" else [])
    if os.path.isdir(BIN):
        for folder, _, files in os.walk(BIN):
            for candidate in names:
                if candidate in files:
                    return os.path.join(folder, candidate)
    for candidate in names:
        found = shutil.which(candidate)
        if found:
            return found
    return name
