"""
Voiceovers: the clinic's voice over their own clips.

Frances (2026-10-10): a voiceover is simple: their voice script, laid over their
video, then captions, in the place they choose. That's all: no hook, pop-up
words or emojis (those are for talking heads). The cut (pauses, ums and retakes
out) works as for talking heads. And the clips must show what the voice is
talking about: never a laser clip under talk about a skin treatment. What's
different from a talking head:

- The voice can come from anything with sound: a Voice Memos recording, or a
  video they filmed while talking. Only the voice is used.
- Their clips play under their voice, as filmed, changing on the beat of their
  words. Claude picks which clip goes where (shots.json), and only clips that
  show what's being said. The clips' own sound is muted.
- With no face to work around, captions can sit in the middle, near the top or
  lower down (captions.VOICEOVER_POSITIONS). The face finder is switched off, so
  clients' faces in treatment clips are never mistaken for the speaker's.
- A gentle clean-up takes out low hum and room hiss, common on phone recordings.

Steps, with Claude in between (as for talking heads):

    .venv/bin/python engine/talking_head.py listen "VOICE.m4a" --work FOLDER
        (Claude writes keep.json: the last good take of each line)
    .venv/bin/python engine/voiceover.py cut "VOICE.m4a" --work FOLDER
        (saves voice.wav and timeline.json; Claude writes shots.json)
    .venv/bin/python engine/voiceover.py montage --work FOLDER --out tidy.mp4
    .venv/bin/python engine/finish.py tidy.mp4 --work FOLDER --voiceover --position middle --captions pop \
        --pack <pack> --popups none        (captions only)

shots.json: which clip plays from which word, e.g.
    [{"clip": "My Content/2026-10/clips/IMG_3173.MOV", "start": 1.0, "word": 0},
     {"clip": "My Content/2026-10/clips/IMG_3182.MOV", "start": 0.5, "word": 51}, ...]
The first shot starts at the beginning, each shot runs until the next one's word,
and the last runs to the end. "start" is where in the clip to begin (skip any
wobble). Claude's rules: change shot every 2 to 4 seconds, at the start of a
sentence or a phrase; match the clip to what's said; spread the clips round and
never show the same moment of a clip twice; the strongest shot first. A clip that
runs out before its shot ends starts again from the beginning.
"""

import tools  # noqa: F401  (first: emoji-safe output on Windows)
import argparse
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import talking_head as th  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)
W, H, FPS = th.W, th.H, th.FPS

CLEAN_UP = "highpass=f=80,afftdn=nr=10:nf=-40"   # gentle: hum and hiss down, voice untouched

# How the clips move. As filmed (straight cuts) is the default; the others are kept
# in case Frances wants them back, but students aren't offered them (her rule: keep it simple).
MOVEMENTS = {
    "cuts": {"name": "As filmed", "say": "Use my voiceover clips as filmed",
             "about": "The clips play as you filmed them, changing on the beat of your words.",
             "good_for": "Every voiceover. The default."},
    "push": {"name": "Slow push-in", "say": "Make my voiceover clips slowly push in",
             "about": "Every clip creeps slowly closer while it plays, so the picture never sits still.",
             "good_for": "Voiceovers with very still clips."},
    "fade": {"name": "Soft fades", "say": "Use soft fades on my voiceovers",
             "about": "Each clip melts gently into the next.",
             "good_for": "Calm, dreamy voiceovers. Aftercare and skin journeys."},
}
PUSH_TO = 1.08        # Slow push-in: how close each clip gets by the end of its shot
FADE_FRAMES = 9       # Soft fades: how long each melt takes (frames)


def cut(voice, work):
    """The tidy voice (pauses, ums and retakes out, cleaned up) and the timeline of kept words."""
    with open(os.path.join(work, "words.json"), encoding="utf-8") as f:
        listened = json.load(f)
    with open(os.path.join(work, "keep.json"), encoding="utf-8") as f:
        keep = json.load(f)
    curve = th.loudness_db(os.path.join(work, "sound.wav"))
    _, length = th.stream_lengths(voice)
    spans = [(s, min(e, length)) for s, e in th.pieces_to_keep(listened["words"], listened["islands"], keep, curve)]
    total = sum(e - s for s, e in spans)
    n_frames = round(total * FPS)
    th.make_sound(voice, spans, n_frames, os.path.join(work, "voice.wav"), CLEAN_UP)
    with open(os.path.join(work, "timeline.json"), "w", encoding="utf-8") as f:
        json.dump({"voice": os.path.abspath(voice), "seconds": round(n_frames / FPS, 3),
                   "words": th.finished_words(listened["words"], keep, spans)}, f, indent=1)
    with open(os.path.join(work, "cut-summary.json"), "w", encoding="utf-8") as f:
        json.dump({"before_seconds": round(length, 1), "after_seconds": round(total, 1), "pieces": len(spans),
                   "spans": [[round(s, 2), round(e, 2)] for s, e in spans]}, f, indent=1)
    print(f"{length:.0f}s of voice down to {total:.0f}s, in {len(spans)} pieces. Saved {work}/voice.wav")


def clip_frames(clip, start, count):
    """`count` frames of a clip from `start` seconds, filling the upright frame, starting again
    from the beginning if the clip runs out. Counted from the first frame at or after `start` (setpts), so
    no frame shows twice (the same fix as talking_head.read_frames, 2026-10-29)."""
    import numpy as np
    proc = subprocess.Popen(["ffmpeg", "-v", "error", "-stream_loop", "-1", "-ss", f"{max(0.0, start):.3f}",
                             "-i", clip, "-an", "-vf",
                             f"setpts=PTS-STARTPTS,fps={FPS},"
                             f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}",
                             "-frames:v", str(count), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    size = W * H * 3
    last = None
    for _ in range(count):
        buf = proc.stdout.read(size)
        if len(buf) < size:
            buf = last
        last = buf
        yield np.frombuffer(buf, np.uint8).reshape(H, W, 3)
    proc.stdout.close()
    proc.wait()


def zoomed(frame, zoom):
    import cv2
    import numpy as np
    if abs(zoom - 1) < 1e-4:
        return frame
    m = np.float32([[zoom, 0, W / 2 * (1 - zoom)], [0, zoom, H / 2 * (1 - zoom)]])
    return cv2.warpAffine(frame, m, (W, H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)


def montage(work, out, movement="cuts", shots_name="shots.json"):
    """The clips laid under the tidy voice, changing on the words in shots.json."""
    import numpy as np
    with open(os.path.join(work, "timeline.json"), encoding="utf-8") as f:
        timeline = json.load(f)
    with open(os.path.join(work, shots_name), encoding="utf-8") as f:
        shots = json.load(f)
    times = {w["i"]: w["start"] for w in timeline["words"]}
    n_frames = round(timeline["seconds"] * FPS)
    starts = []
    for k, shot in enumerate(shots):
        t = 0.0 if k == 0 else times.get(shot["word"])
        if t is None:
            raise SystemExit(f"Shot {k + 1} is tied to word {shot['word']}, which was cut. Pick another word.")
        # Change on the beat: a few frames before the word, so the new picture lands with it.
        starts.append(0 if k == 0 else max(0, round(t * FPS) - 2))
    starts.append(n_frames)
    fade = FADE_FRAMES if movement == "fade" else 0
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    writer = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                               "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", os.path.join(work, "voice.wav"),
                               "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "medium", "-crf", "17",
                               "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
                               out], stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
    carry = []   # the end of the last shot, to melt into the start of this one
    used = {}    # each clip's strong moments used so far (clip_moments.py)
    import clip_moments
    for k, shot in enumerate(shots):
        first, last = starts[k], starts[k + 1]
        length = last - first
        extra = fade if k < len(shots) - 1 else 0
        clip = shot["clip"] if os.path.isabs(shot["clip"]) else os.path.join(PROJECT, shot["clip"])
        # From the clip's strong moments, never across the gun lifting off (Frances, 2026-11-02), in normal
        # colour (iPhone HDR footage converted first).
        clip, begin = clip_moments.footage(clip, shot.get("start", 0.5), (length + extra) / FPS, used=used,
                                           tag=f"shot{k + 1}")
        new_carry = []
        for j, frame in enumerate(clip_frames(clip, begin, length + extra)):
            if movement == "push":
                frame = zoomed(frame, 1 + (PUSH_TO - 1) * (j / max(1, length + extra - 1)))
            if j >= length:
                new_carry.append(frame)
                continue
            if j < len(carry):
                w = (j + 1) / (len(carry) + 1)
                frame = (frame.astype(np.float32) * w + carry[j].astype(np.float32) * (1 - w)).astype(np.uint8)
            writer.stdin.write(np.ascontiguousarray(frame).tobytes())
        carry = new_carry
    writer.stdin.close()
    if writer.wait() != 0:
        raise SystemExit("Saving the voiceover didn't work.")
    print(f"{len(shots)} shots under {timeline['seconds']:.0f}s of voice ({MOVEMENTS[movement]['name']}). Saved {out}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="step", required=True)
    a = sub.add_parser("cut", help="tidy the voice from keep.json")
    a.add_argument("voice")
    a.add_argument("--work", required=True)
    b = sub.add_parser("montage", help="lay the clips under the voice from shots.json")
    b.add_argument("--work", required=True)
    b.add_argument("--out", required=True)
    b.add_argument("--movement", choices=list(MOVEMENTS), default="cuts")
    b.add_argument("--shots", default="shots.json")
    args = ap.parse_args()
    if args.step == "cut":
        cut(args.voice, args.work)
    else:
        montage(args.work, args.out, args.movement, args.shots)


if __name__ == "__main__":
    main()
