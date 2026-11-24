"""
Turning a post into another kind of post (Frances, 2026-10-12): "we've got a
really good talking head video that's done amazing... we can change that into
a carousel... or the other way around, we've done a carousel and we want to
change it into a reel."

Two helpers for the turn-it-into skill:

    .venv/bin/python engine/repurpose.py words "My Content/2026-10/talking-heads/skinpen-one-session"
    .venv/bin/python engine/repurpose.py words "My Content/2026-10" --day 7        (or --day 2026-10-07)
        Everything the post says, in order, as plain text: a talking head's or
        voiceover's kept words (and its hook), a reel's words and call to
        action, a carousel's slides, a quote, and the caption.

    .venv/bin/python engine/repurpose.py stills "<video>" --count 8 --out "<folder>"
        The best stills from a video for carousel photos, cropped to 1080 x 1350
        (Instagram's portrait post size): sharp, with a face where there is one,
        and spread through the video so no two look the same.
"""

import tools  # noqa: F401  (first: emoji-safe output on Windows)
import argparse
import datetime
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


# ---------------------------------------------------------------------------
# What a post says
# ---------------------------------------------------------------------------

def spoken(folder):
    """A talking head's or voiceover's kept words, as sentences, with its hook if it has one."""
    with open(os.path.join(folder, "timeline.json"), encoding="utf-8") as f:
        timeline = json.load(f)["words"]
    fixes = {}
    if os.path.exists(os.path.join(folder, "fixes.json")):     # misheard words put right ("skin pain" = SkinPen)
        with open(os.path.join(folder, "fixes.json"), encoding="utf-8") as f:
            fixes = json.load(f)
    words = [fixes.get(str(w["i"]), w["word"]) for w in timeline]
    text = re.sub(r"\s+", " ", " ".join(words)).strip()
    lines = [f"WHAT THEY SAID (the finished video, {len(words)} words):", text]
    hook = os.path.join(folder, "hook.json")
    if os.path.exists(hook):
        with open(hook, encoding="utf-8") as f:
            lines[:0] = [f"HOOK ON SCREEN: {json.load(f).get('text', '')}"]
    finished = os.path.join(folder, "finished.mp4")
    if os.path.exists(finished):
        lines.append(f"FINISHED VIDEO: {finished}")
    return "\n".join(lines)


def planned(month_folder, day):
    """Everything posts.md and reels.json have for one day of a month. day is its date (2026-12-01) or, in a
    plan inside one month, its day number (7)."""
    sys.path.insert(0, HERE)
    import days
    from make_planner import post_fields
    if "-" not in str(day):        # a day number: that day in the month the plan's calendar has it in
        rows = days.read_calendar(month_folder) if os.path.exists(os.path.join(month_folder, "calendar.md")) else []
        found = [r["date"] for r in rows if r["day"] == int(day)]
        year, month = days.start_of(month_folder)
        day = found[0] if found else datetime.date(year, month, int(day))
    else:
        day = datetime.date.fromisoformat(day)
    with open(os.path.join(month_folder, "posts.md"), encoding="utf-8") as f:
        fields = post_fields(f.read(), day)
    lines = [f"{label.upper()}: {text}" for label, text in fields.items() if text]
    reels = os.path.join(month_folder, "reels.json")
    if os.path.exists(reels):
        with open(reels, encoding="utf-8") as f:
            for reel in json.load(f).get("reels", []):
                if reel.get("date", "") == day.isoformat():
                    for key in ("text", "title", "lines", "popup"):
                        if reel.get(key):
                            lines.append(f"REEL {key.upper()}: {reel[key]}")
    for made in (os.path.join(month_folder, "reels", f"{day}.mp4"),
                 os.path.join(month_folder, "posts", f"{day}.png"),
                 os.path.join(month_folder, "posts", f"{day}")):
        if os.path.exists(made):
            lines.append(f"FINISHED: {made}")
    return "\n".join(lines) or "Nothing found for that day."


# ---------------------------------------------------------------------------
# Stills for carousel photos
# ---------------------------------------------------------------------------

def pause_times(timeline_path):
    """Moments just after someone finishes a sentence (a pause between words): natural faces, mouths closed."""
    with open(timeline_path, encoding="utf-8") as f:
        words = json.load(f)["words"]
    return [round((a["end"] + b["start"]) / 2, 2) for a, b in zip(words, words[1:])
            if b["start"] - a["end"] >= 0.2 or a["word"].rstrip().endswith((".", "?", "!"))]


def stills(video, count, out_folder, width=1080, height=1350, timeline=None):
    """The best frame from each of `count` stretches of the video: sharp, with a face if there is one,
    cropped to Instagram's portrait post shape around the face. With a talking head's timeline, only
    moments between sentences are considered, so faces look natural."""
    import cv2
    import numpy as np
    import face
    from sdr import normal_colour
    video = normal_colour(video)
    w0, h0 = face.video_size(video)
    look_w = 540
    look_h = round(h0 * look_w / w0 / 2) * 2
    every = 0.25
    reader = subprocess.Popen(["ffmpeg", "-v", "error", "-i", video, "-vf", f"fps={1 / every:g},scale={look_w}:{look_h}",
                               "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], stdout=subprocess.PIPE)
    finder = cv2.FaceDetectorYN.create(face.MODEL, "", (look_w, look_h), face.SURE, 0.3, 5000)
    scored = []
    n = 0
    while True:
        buf = reader.stdout.read(look_w * look_h * 3)
        if len(buf) < look_w * look_h * 3:
            break
        frame = np.frombuffer(buf, np.uint8).reshape(look_h, look_w, 3)
        sharp = cv2.Laplacian(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var()
        _, found = finder.detect(frame)
        centre = None
        if found is not None and len(found):
            x, y, fw, fh = max(found, key=lambda f: f[2] * f[3])[:4]
            centre = ((y + fh / 2) / look_h)
        scored.append((n * every, sharp * (1.6 if centre is not None else 1.0), centre))
        n += 1
    reader.wait()
    if timeline and os.path.exists(timeline):
        pauses = pause_times(timeline)
        near = [s for s in scored if any(abs(s[0] - p) <= every / 2 for p in pauses)]
        scored = near if len(near) >= count else scored
    if not scored:
        raise SystemExit("Couldn't read that video.")
    os.makedirs(out_folder, exist_ok=True)
    picked, size = [], len(scored) / count
    for k in range(count):
        part = scored[int(k * size):max(int((k + 1) * size), int(k * size) + 1)]
        if part:
            picked.append(max(part, key=lambda s: s[1]))
    saved = []
    for k, (t, _, centre) in enumerate(picked, 1):
        # Crop to 4:5 around the face (its middle about 40% of the way down), or the middle of the frame.
        out = os.path.join(out_folder, f"still-{k:02d}.jpg")
        scale_h = round(h0 * width / w0)
        top = 0 if centre is None else max(0, min(scale_h - height, round(centre * scale_h - 0.4 * height)))
        if centre is None:
            top = max(0, (scale_h - height) // 2)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", video, "-frames:v", "1",
                        "-vf", f"scale={width}:-2,crop={width}:{height}:0:{top}", "-q:v", "2", out], check=True)
        saved.append(out)
    return saved


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="job", required=True)
    w = sub.add_parser("words", help="everything a post says")
    w.add_argument("source", help="a talking head or voiceover folder, or a month folder with --day")
    w.add_argument("--day", help="the day: its date (2026-12-01) or, in a plan inside one month, its number (7)")
    s = sub.add_parser("stills", help="the best stills from a video for carousel photos")
    s.add_argument("video")
    s.add_argument("--count", type=int, default=8)
    s.add_argument("--out", required=True)
    s.add_argument("--timeline", help="a talking head's timeline.json: pick moments between sentences")
    args = ap.parse_args()
    if args.job == "words":
        if args.day:
            print(planned(args.source, args.day))
        elif os.path.exists(os.path.join(args.source, "timeline.json")):
            print(spoken(args.source))
        else:
            raise SystemExit("Give a talking head or voiceover folder, or a month folder with --day.")
    else:
        for path in stills(args.video, args.count, args.out, timeline=args.timeline):
            print(path)


if __name__ == "__main__":
    main()
