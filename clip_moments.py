"""
The strongest part of each clip (Frances, 2026-11-02: "you're not cutting it while they're still lasering,
you're cutting it when they've took the gun away... it needs to be clean cuts... identify the strongest part
of the clip and use the clips like that together").

Claude looks at each new clip's contact sheet (a picture every half second, with the time on each) and marks
its strong moments: the stretches where the treatment is really happening (the laser gun gliding on the skin,
the SkinPen working, cream being properly applied, the machine shown steadily), never the in-between bits
(the gun lifting off, hands moving into place, the camera wobbling, a half-hearted dab). They're saved beside
the clip in moments.json, so they're there next month too.

Reels, one-by-one reels and voiceovers then only ever use footage from inside a strong moment, and every cut
lands inside one. When a reel needs longer than any one moment, two (or more) are joined with a clean cut.
A clip with no moments marked is used as before.

    PY engine/clip_moments.py sheet CLIP [OUT.jpg]
    PY engine/clip_moments.py mark CLIP "1.5-6.0 gun gliding on the underarm" "8.0-11.5 second pass"
    PY engine/clip_moments.py show CLIP_OR_FOLDER
    PY engine/clip_moments.py check REELS_JSON_OR_SHOTS_JSON

sheet: the contact sheet to look at (saved in a .moments folder beside the clip unless OUT is given).
mark: saves the clip's strong moments (replacing any marked before). show: what's marked. check: says
whether every reel or shot in the file fits inside a strong moment (the engine fixes any that don't anyway).
"""

import tools  # noqa: F401  (first: emoji-safe output on Windows)
import json
import os
import re
import subprocess
import sys

EVERY = 0.5          # the contact sheet shows a picture this often
COLUMNS = 8
SHORTEST = 1.2       # a strong moment used in a reel is at least this long (shorter pieces flicker)
NAME = "moments.json"


def length_of(clip):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", clip],
                         capture_output=True, text=True).stdout.strip().split(",")[0]
    return float(out or 0)


def store_for(clip):
    return os.path.join(os.path.dirname(os.path.abspath(clip)), NAME)


def load_all(folder):
    path = os.path.join(folder, NAME)
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def moments(clip):
    """The clip's strong moments as [(from, to, what)], or None when none are marked yet."""
    marked = load_all(os.path.dirname(os.path.abspath(clip))).get(os.path.basename(clip))
    if not marked:
        return None
    return sorted((float(m["from"]), float(m["to"]), m.get("what", "")) for m in marked)


def mark(clip, spans):
    """spans: ["1.5-6.0 what it shows", ...]."""
    folder = os.path.dirname(os.path.abspath(clip))
    everything = load_all(folder)
    total = length_of(clip)
    found = []
    for text in spans:
        m = re.match(r"\s*([\d.]+)\s*[-–to]+\s*([\d.]+)\s*(.*)", text)
        if not m:
            raise SystemExit(f"Couldn't read \"{text}\": write it like \"1.5-6.0 gun gliding on the underarm\".")
        a, b = float(m.group(1)), min(float(m.group(2)), total)
        if b - a < SHORTEST:
            raise SystemExit(f"\"{text}\" is under {SHORTEST} seconds: too short to use in a reel.")
        found.append({"from": round(a, 2), "to": round(b, 2), "what": m.group(3).strip()})
    everything[os.path.basename(clip)] = sorted(found, key=lambda x: x["from"])
    with open(os.path.join(folder, NAME), "w", encoding="utf-8") as f:
        json.dump(everything, f, ensure_ascii=False, indent=1)
    return everything[os.path.basename(clip)]


def sheet(clip, out=None):
    """A picture every half second of the clip, in rows, each with its time, to choose the strong moments from."""
    from PIL import Image, ImageDraw
    from sdr import normal_colour
    source = normal_colour(clip)
    total = length_of(source)
    out = out or os.path.join(os.path.dirname(os.path.abspath(clip)), ".moments",
                              os.path.splitext(os.path.basename(clip))[0] + "-sheet.jpg")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    w = 180
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", source, "-vf",
                          f"fps={1 / EVERY:g},scale={w}:-2", "-f", "image2pipe", "-vcodec", "png", "-"],
                         capture_output=True).stdout
    frames, i = [], 0
    from io import BytesIO
    while True:                      # split the stream of PNGs
        start = raw.find(b"\x89PNG", i)
        if start < 0:
            break
        end = raw.find(b"\x89PNG", start + 8)
        frames.append(Image.open(BytesIO(raw[start:end if end > 0 else len(raw)])).convert("RGB"))
        i = end if end > 0 else len(raw)
    if not frames:
        raise SystemExit(f"Couldn't read {clip}")
    fh = frames[0].height
    rows = (len(frames) + COLUMNS - 1) // COLUMNS
    picture = Image.new("RGB", (COLUMNS * (w + 4), rows * (fh + 4)), "white")
    draw = ImageDraw.Draw(picture)
    for n, frame in enumerate(frames):
        x, y = (n % COLUMNS) * (w + 4), (n // COLUMNS) * (fh + 4)
        picture.paste(frame, (x, y))
        draw.rectangle((x, y, x + 46, y + 18), fill=(0, 0, 0))
        draw.text((x + 4, y + 3), f"{n * EVERY:.1f}s", fill=(255, 255, 255))
    picture.save(out, quality=86)
    return out, total


def free(spans, used):
    """The parts of spans not already used (used: [(from, to)])."""
    left = []
    for a, b, what in spans:
        pieces = [(a, b)]
        for ua, ub in used:
            pieces = [p for s, e in pieces for p in ((s, min(e, ua)), (max(s, ub), e)) if p[1] - p[0] > 0.05]
        left += [(s, e, what) for s, e in pieces]
    return left


def fit(clip, start, length, used=None):
    """The footage for `length` seconds of the clip, from its strong moments: [(from, to)]. Starts at `start`
    when that's inside a moment with room; otherwise in the moment that holds it best. When no one moment is
    long enough, moments are joined with clean cuts, every piece at least SHORTEST long where the moments
    allow, each moment shown once before any is shown again. Parts already used this month (`used`) are left
    for others where possible. None when the clip has no moments marked."""
    spans = moments(clip)
    if not spans:
        return None
    used = used or []
    span_len = lambda m: m[1] - m[0]
    whole = [m for m in spans if span_len(m) >= SHORTEST] or spans
    fresh = [m for m in free(whole, used) if span_len(m) >= SHORTEST]
    for pool in (fresh, whole):                    # the asked-for start, if it fits inside a moment
        for a, b, _ in pool:
            if a - 0.01 <= start and start + length <= b + 0.01:
                return [(start, start + length)]
    for pool in (fresh, whole):                    # one moment it fits inside: a touch in, past any wobble
        for a, b, _ in sorted(pool, key=lambda m: -span_len(m)):
            if span_len((a, b)) >= length:
                s = min(a + 0.3, b - length)
                return [(s, s + length)]
    # Join moments: fresh ones first (longest first), then ones used already, then round again if the clip
    # simply hasn't enough strong footage (Claude says so: a longer clip next time).
    def overlaps(m, others):
        return any(m[0] < o[1] and o[0] < m[1] for o in others)
    first_lap = sorted(fresh, key=lambda m: -span_len(m))
    first_lap += [m for m in sorted(whole, key=lambda m: -span_len(m)) if not overlaps(m, first_lap)]
    chosen, total, lap = [], 0.0, 0
    while total < length - 0.01 and lap < 20:
        for m in (first_lap if lap == 0 else sorted(whole, key=lambda m: -span_len(m))):
            if total >= length - 0.01:
                break
            chosen.append((lap, m[0], m[1]))
            total += m[1] - m[0]
        lap += 1
    excess = total - length                         # shave what's over, spread across the pieces
    sizes = [b - a for _, a, b in chosen]
    floors = [min(SHORTEST, x) for x in sizes]
    room = sum(x - f for x, f in zip(sizes, floors))
    pieces = []
    for (lp, a, b), x, f in zip(chosen, sizes, floors):
        cut = (x - f) / room * excess if room > 0 else excess * x / total
        pieces.append((lp, a, a + x - cut))
    return [(a, b) for _, a, b in sorted(pieces)]


def footage(clip, start, length, work=None, used=None, tag="reel"):
    """(path, start) to use for `length` seconds, in normal colour: the clip with its start moved into a
    strong moment, or a joined copy of several strong moments (saved in `work`, beside the clip unless given,
    starting at 0). The clip as it was when it has no moments marked. used: {clip: [(from, to)]} across a
    month's reels or a voiceover's shots, so the same moment isn't used twice where it can be helped."""
    from sdr import normal_colour
    mine = None if used is None else used.setdefault(os.path.abspath(clip), [])
    pieces = fit(clip, start, length, mine)
    if not pieces:
        return normal_colour(clip), start
    if mine is not None:
        mine += pieces
    strong = sum(b - a for a, b, _ in moments(clip))
    if strong < length - 0.05:
        print(f"NOTE: {os.path.basename(clip)} has {strong:.1f}s of strong footage and this needs {length:.1f}s, so "
              f"a moment shows twice. A clip with more strong footage would look better (or film a longer one).")
    if len(pieces) == 1:
        return normal_colour(clip), pieces[0][0]
    work = work or os.path.join(os.path.dirname(os.path.abspath(clip)), ".moments", "joined")
    os.makedirs(work, exist_ok=True)
    source = normal_colour(clip)
    out = os.path.join(work, f"{tag}-{os.path.splitext(os.path.basename(clip))[0]}-"
                             f"{'-'.join(f'{a:.1f}' for a, _ in pieces)}.mp4")
    if not os.path.exists(out):
        graph = "".join(f"[0:v]trim={a:.3f}:{b:.3f},setpts=PTS-STARTPTS[p{k}];" for k, (a, b) in enumerate(pieces))
        graph += "".join(f"[p{k}]" for k in range(len(pieces))) + f"concat=n={len(pieces)}:v=1:a=0[v]"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", source, "-filter_complex", graph, "-map", "[v]",
                        "-c:v", "libx264", "-crf", "14", "-preset", "medium", "-pix_fmt", "yuv420p", out], check=True)
    return out, 0.0


def check(path):
    """Does every reel (reels.json) or shot (shots.json) sit inside a strong moment?"""
    data = json.load(open(path, encoding="utf-8"))
    folder = os.path.dirname(os.path.abspath(path))
    problems, checked = [], 0
    if isinstance(data, dict) and "reels" in data:
        for reel in data["reels"]:
            clips = reel.get("clips") or [{"clip": reel.get("clip"), "start": reel.get("start", 0)}]
            # About how long each clip is on screen: 9 seconds with a call to action, 7 without, shared out
            # between a one-by-one reel's clips.
            each = (9 if reel.get("popup") else 7) / len(clips)
            for c in clips:
                if not c.get("clip"):
                    continue
                clip = os.path.join(folder, c["clip"])
                spans = moments(clip)
                checked += 1
                s = c.get("start", 0)
                if spans is None:
                    problems.append(f"{reel['date']}: {c['clip']} has no strong moments marked")
                elif not any(a - 0.01 <= s and s + each <= b + 0.01 for a, b, _ in spans):
                    problems.append(f"{reel['date']}: {s}s to {s + each:.1f}s of {c['clip']} isn't inside one strong "
                                    f"moment ({', '.join(f'{a}-{b}' for a, b, _ in spans)}); the engine will move "
                                    f"or join it, but better to pick a start inside one")
    else:
        for shot in data:
            spans = moments(shot["clip"])
            checked += 1
            if spans is None:
                problems.append(f"word {shot['word']}: {shot['clip']} has no strong moments marked")
            elif not any(a - 0.01 <= shot.get("start", 0.5) < b for a, b, _ in spans):
                problems.append(f"word {shot['word']}: starts at {shot.get('start', 0.5)}s, outside the strong "
                                f"moments of {os.path.basename(shot['clip'])}")
    return checked, problems


def main(argv):
    if len(argv) < 2 or argv[0] not in ("sheet", "mark", "show", "check"):
        print(__doc__)
        return 1
    what, target = argv[0], argv[1]
    if what == "sheet":
        out, total = sheet(target, argv[2] if len(argv) > 2 else None)
        print(f"SHEET: {out} ({total:.1f}s, a picture every {EVERY}s). Look at it and mark the strong moments.")
    elif what == "mark":
        for m in mark(target, argv[2:]):
            print(f"MARKED: {m['from']}-{m['to']}s {m['what']}")
    elif what == "show":
        if os.path.isdir(target):
            for name, marked in load_all(target).items():
                print(f"{name}: " + "; ".join(f"{m['from']}-{m['to']}s {m['what']}" for m in marked))
        else:
            spans = moments(target)
            print("NONE MARKED" if not spans else "\n".join(f"{a}-{b}s {w}" for a, b, w in spans))
    else:
        checked, problems = check(target)
        print("\n".join(f"OUTSIDE: {p}" for p in problems) if problems else f"ALL INSIDE: {checked} checked.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
