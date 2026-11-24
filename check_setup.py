"""
Checks that everything the engine needs is on this computer and working, and
says so in plain words. "set me up" runs it after installing, and any time
something seems wrong.

    python3 engine/check_setup.py           # what's there and what's missing
    python3 engine/check_setup.py --test    # also makes a tiny test reel and listens to a test sentence

Each line starts with OK or MISSING (or CHECK, for something worth a look),
then plain words, so Claude can read it and fix what's missing. It ends with
"ALL SET" when everything works.
"""

import argparse
import importlib
import os
import platform
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from tools import tool  # noqa: E402

MODEL = os.path.join(HERE, "models", "ggml-large-v3-turbo-q5_0.bin")
FACE_MODEL = os.path.join(HERE, "models", "face_detection_yunet_2023mar.onnx")
PACKAGES = {"numpy": "numpy", "cv2": "opencv-python-headless", "PIL": "pillow", "segno": "segno"}
FONTS = ["DMSans.ttf", "PlayfairDisplay.ttf", "Poppins-SemiBold.ttf", "Caveat.ttf"]   # if the full list can't be read
EMOJI_FONTS = {"Darwin": "/System/Library/Fonts/Apple Color Emoji.ttc",
               "Windows": os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", "seguiemj.ttf")}

results = []


def report(ok, words, level=None):
    results.append(ok or level == "CHECK")
    print(f"{level or ('OK' if ok else 'MISSING')}  {words}")


def version_of(path, flag="-version"):
    try:
        out = subprocess.run([path, flag], capture_output=True, text=True, timeout=30)
        return (out.stdout or out.stderr).splitlines()[0][:60]
    except Exception:
        return ""


def check():
    system = platform.system()
    print(f"This computer: {'Mac' if system == 'Darwin' else system} ({platform.machine()}), Python {platform.python_version()}")

    own = os.path.realpath(os.path.join(ROOT, ".venv"))    # the all-in-one download's Python lives there itself
    in_venv = (sys.prefix != getattr(sys, "base_prefix", sys.prefix)
               or os.path.realpath(sys.prefix).startswith(own))
    report(in_venv, "the engine's own Python space (.venv)" if in_venv
           else "the engine's own Python space (.venv): run this with the .venv's Python")
    for module, name in PACKAGES.items():
        try:
            importlib.import_module(module)
            report(True, f"Python helper: {name}")
        except Exception:
            report(False, f"Python helper: {name}")

    for name in ("ffmpeg", "ffprobe"):
        path = tool(name)
        found = os.path.isfile(path) or shutil.which(path)
        report(bool(found), f"{name} (video tool): {version_of(path)}" if found else f"{name} (video tool)")
    whisper = tool("whisper-cli")
    found = os.path.isfile(whisper) or shutil.which(whisper)
    report(bool(found), "whisper (listens to talking heads)" if found else "whisper (listens to talking heads)")

    size = os.path.getsize(MODEL) / 1e6 if os.path.exists(MODEL) else 0
    report(size > 500, f"speech model ({size:.0f} MB)" if size else "speech model (about 550 MB to download)")
    report(os.path.exists(FACE_MODEL), "face finder")

    fonts = os.path.join(HERE, "fonts")
    try:
        import text_reel
        needed = sorted({entry[0] for entry in text_reel.FONTS.values()})
    except Exception:
        needed = FONTS
    missing = [f for f in needed if not os.path.exists(os.path.join(fonts, f))]
    report(not missing, "fonts" if not missing else f"fonts: {', '.join(missing)}")

    emoji = EMOJI_FONTS.get(system)
    if emoji:
        report(os.path.exists(emoji), "emoji font" if os.path.exists(emoji) else f"emoji font ({emoji})",
               None if system == "Darwin" or not os.path.exists(emoji) else "CHECK")
        if system == "Windows" and os.path.exists(emoji):
            print("        Windows emoji look a little different from iPhone ones: check a sticker on a test reel.")

    free = shutil.disk_usage(ROOT).free / 1e9
    report(free > 3, f"space on the computer ({free:.0f} GB free)" if free > 3
           else f"space on the computer: only {free:.1f} GB free, 3 GB or more is needed")
    if "downloads" in ROOT.lower():
        report(False, "the engine is in Downloads, which often gets tidied away: move it to Documents", "CHECK")


def test():
    """A tiny reel and a test sentence, to prove the tools really work together."""
    import text_reel
    with tempfile.TemporaryDirectory() as tmp:
        clip = os.path.join(tmp, "clip.mp4")
        subprocess.run([tool("ffmpeg"), "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=0xb9a99a:s=1080x1920:d=3",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", clip], check=True)
        out = os.path.join(tmp, "reel.mp4")
        try:
            text_reel.make_reel(clip, ["Your engine is working 👀"], out, 0)
            report(os.path.getsize(out) > 1000, "test reel made")
        except Exception as e:
            report(False, f"test reel: {str(e)[:200]}")

        try:   # the face finder loads and runs
            import cv2
            import numpy as np
            finder = cv2.FaceDetectorYN.create(FACE_MODEL, "", (320, 320))
            finder.detect(np.zeros((320, 320, 3), dtype=np.uint8))
            report(True, "face finder runs")
        except Exception as e:
            report(False, f"face finder: {str(e)[:200]}")

        if not os.path.exists(MODEL):
            return
        voice = os.path.join(tmp, "voice.wav")
        made = False
        if platform.system() == "Darwin":
            aiff = os.path.join(tmp, "voice.aiff")
            made = subprocess.run(["say", "-o", aiff, "Hello, this is my content engine."]).returncode == 0
            if made:
                subprocess.run([tool("ffmpeg"), "-v", "error", "-y", "-i", aiff, "-ac", "1", "-ar", "16000", voice], check=True)
        elif platform.system() == "Windows":
            script = ("Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                      f"$s.SetOutputToWaveFile('{voice}'); $s.Speak('Hello, this is my content engine.'); $s.Dispose()")
            made = subprocess.run(["powershell", "-NoProfile", "-Command", script]).returncode == 0
        if not made:
            return
        base = os.path.join(tmp, "heard")
        run = subprocess.run([tool("whisper-cli"), "-m", MODEL, "-f", voice, "-l", "en", "-otxt", "-of", base, "-np"],
                             capture_output=True, text=True)
        heard = open(base + ".txt", encoding="utf-8").read().strip() if os.path.exists(base + ".txt") else ""
        report("content engine" in heard.lower(), f'listening test: heard "{heard}"' if heard
               else f"listening test: {run.stderr.strip()[-200:]}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--test", action="store_true", help="also make a tiny test reel and listen to a test sentence")
    args = ap.parse_args()
    check()
    if args.test and all(results):
        test()
    print("\nALL SET" if all(results) else "\nNOT YET: install what's MISSING above, then check again.")


if __name__ == "__main__":
    main()
