"""
Talking-head editor, stage 1: the clean cut.

Takes a talking-head video straight from the phone, retakes, pauses, ums and
all, and makes a tidy version: only the good takes, no ums or ers, and no long
pauses, with the sound evened out for Instagram.

It works in two steps, with Claude in between:

1. listen: writes down every word, with the moment each one starts and ends.
       python3 engine/talking_head.py listen "VIDEO.MOV" --work "FOLDER"
   This saves words.json (every word and its timing) and transcript.txt (the
   same words laid out for reading, one line per sentence, with word numbers).

2. Claude reads transcript.txt and decides what to keep: the last good take of
   each line, never the false starts or the takes that trail off. It writes
   keep.json, a list of word-number ranges, for example [[12, 40], [58, 97]].

3. cut: makes the tidy video from keep.json, in the student's cut style.
       .venv/bin/python engine/talking_head.py cut "VIDEO.MOV" --work "FOLDER" --out "TIDY.mp4" --style glide
   Inside the kept ranges it also takes out ums and ers on its own, and
   shortens any pause longer than a breath. Every cut lands on a quiet moment,
   with a tiny fade, so there are no clicks or chopped-off words. The cut styles
   (CUT_STYLES below) decide how the pieces join and whether the camera moves.
   It also saves timeline.json: when each kept word is said in the finished
   video, for the captions (captions.py).

Built from scratch with open-source tools: whisper.cpp (MIT licence) for the
listening, FFmpeg for the cutting, OpenCV (Apache 2.0) and NumPy (BSD) for the
glides and zooms.
"""

import tools  # noqa: F401  (first: emoji-safe output on Windows)
import argparse
import array
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = os.path.join(HERE, "models", "ggml-large-v3-turbo-q5_0.bin")

# ---------------------------------------------------------------------------
# Timing. Change these numbers to change how tight every edit is.
# ---------------------------------------------------------------------------
LEAD_IN = 0.06        # seconds kept before the first sound of a piece, so it isn't clipped
TAIL = 0.12           # seconds kept after the last sound of a piece, so it can breathe out
END_HOLD = 0.5        # extra seconds kept after the very last word of the video
START_HOLD = 0.4      # extra seconds kept before the very first word, so players never swallow it
LONGEST_PAUSE = 0.30  # any pause longer than this gets shortened
MIN_CUT = 0.5         # plain cuts only: a pause is cut out only if that saves this long, and no piece is shorter
NOISE_BEFORE = 0.8    # sound this long before the first word (or after the last) isn't speech: it's left out
SNAP = 0.10           # how far a cut can move to land on a quiet moment
FADE = 0.012          # a tiny fade on every cut, so there are no clicks
LOUDNESS = -14        # how loud the finished video is (LUFS, Instagram's level)

# How the pieces join and move: the cut styles. Students pick one in the lookbook.
W, H, FPS = 1080, 1920, 30
CUT_STYLES = {
    "glide": {"name": "As filmed", "joins": "glide", "zoom": "none",
              "about": "Your framing stays exactly as you filmed it. Where you've hardly moved between "
                       "takes, the join glides smoothly; where you've moved a lot, it's a clean cut.",
              "good_for": "Calm, natural talking heads. The safest choice for every brand."},
    "push": {"name": "Slow push-in", "joins": "glide", "zoom": "push",
             "about": "The camera creeps slowly closer over the first few seconds, then holds. "
                      "Joins glide like As filmed.",
             "good_for": "Pulling people in at the start. Teaching videos and stories."},
    "punch": {"name": "Punch-in", "joins": "cut", "zoom": "punch",
              "about": "Every other piece is a little closer, so each cut looks like a second camera. "
                       "The jump is on purpose, so the cuts never look like mistakes.",
              "good_for": "Lively tips, myth-busting and anything with a lot of cuts."},
    "bounce": {"name": "Zoom bounce", "joins": "cut", "zoom": "bounce",
               "about": "Each new piece starts a little closer and eases back out, like a quick nod "
                        "to the viewer.",
               "good_for": "Fun, high-energy videos. Use it when you want to feel bold."},
    "flash": {"name": "Soft flash", "joins": "flash", "zoom": "none",
              "about": "A quick soft white flash on every join, like a camera flash. Bright and clean.",
              "good_for": "Glowy skin, before-and-after chat and launch announcements."},
    "jump": {"name": "Jump cuts", "joins": "cut", "zoom": "none",
             "about": "Straight cuts from one piece to the next, nothing added. Raw and real.",
             "good_for": "Honest, behind-the-scenes and confessional videos."},
}
FACE_AT = (0.5, 0.45) # where a face usually is (across, down): zooms aim here if the face finder finds no face
SHIFT_FRAMES = 3      # the picture's cut can sit up to this many frames either side of the sound's cut
PUSH_TO = 1.08        # Slow push-in: how close it gets (1.08 = 8% closer)...
PUSH_SECONDS = 8      # ...over this many seconds, then it holds
PUNCH = 1.15          # Punch-in: how much closer every other piece is
BOUNCE_FROM = 1.12    # Zoom bounce: each new piece starts this close...
BOUNCE_SECONDS = 0.3  # ...and eases back out over this long
FLASH = [0.25, 0.7, 0.45, 0.22, 0.08]  # Soft flash: how white each frame goes, from the frame before the join

# Glides (the joins in As filmed and Slow push-in).
MORPH_FRAMES = 6      # frames the glide takes when the move between pieces is small (a fifth of a second)
MORPH_FRAMES_BIGGER = 4  # frames when the move is bigger, so any blur is over in a flash
MORPH_LIMIT = 16      # above this "left over difference" a glide would look messy, so it's a clean cut
MORPH_SMALL = 10      # below this, the move is small enough for the longer glide
MORPH_HANDS = 30      # the most "left over difference" allowed in any one patch of the picture: above it, something
                      # other than the face moved (a hand, mostly), a glide would smear it, so it's a clean cut

# Finding the talking in the sound.
STEP = 0.02           # the sound is measured every 20 thousandths of a second
SPEECH_LEVEL = 0.35   # how far between background hum (0) and full voice (1) counts as talking
JOIN_GAP = 0.15       # sounds closer together than this count as one stretch

# Sounds that are never words worth keeping.
FILLERS = {"um", "umm", "uh", "uhh", "er", "erm", "ah", "hmm", "mm", "mmm"}

# Whisper tidies up speech as it listens and usually leaves ums out. Starting it
# off with a few of them reminds it to write them down, so they can be cut.
LISTEN_PROMPT = "Um, so, er, I was, uh, thinking, erm, you know, hmm, okay."


def run(cmd, quiet=True):
    """Runs a command, and shows its error message if it fails."""
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(f"This step didn't work:\n{' '.join(cmd)}\n\n{result.stderr[-2000:]}")
    return result


# ---------------------------------------------------------------------------
# Step 1: listen
# ---------------------------------------------------------------------------

def extract_audio(video, wav_path):
    """The sound on its own, the way whisper likes it: one channel, 16,000 samples a second."""
    run(["ffmpeg", "-v", "error", "-y", "-i", video, "-vn", "-ac", "1", "-ar", "16000",
         "-c:a", "pcm_s16le", wav_path])


class Tripped(Exception):
    """whisper stopped on its precise-timing check: it trips over a stretch of speech only a word or two long
    now and then ('WHISPER_ASSERT ... filter_width < a->ne[2]', found 2026-10-20 on one of Frances's videos)."""


def whisper_once(wav_path, out_base, precise=True):
    """whisper on one sound file; its full answer (every token with its timing)."""
    from tools import tool
    cmd = ([tool("whisper-cli"), "-m", MODEL, "-f", wav_path, "-l", "en", "-ojf", "-of", out_base]
           + (["--dtw", "large.v3.turbo", "-nfa"] if precise else []) + ["--prompt", LISTEN_PROMPT, "-np"])
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        said = (result.stdout or "") + (result.stderr or "")
        if precise and ("WHISPER_ASSERT" in said or result.returncode in (-6, 134)):
            raise Tripped(said[-500:])
        raise SystemExit(f"This step didn't work:\n{' '.join(cmd)}\n\n{said[-2000:]}")
    with open(out_base + ".json", encoding="utf-8") as f:
        return json.load(f)


PIECE = 25.0          # seconds: how long each piece is when whisper has to listen in pieces


def transcribe_in_pieces(wav_path, work, islands):
    """whisper in pieces of about 25 seconds, each cut in a quiet moment between stretches of speech, with the
    timings moved back to where they are in the whole video. A piece that still trips is listened to with
    whisper's own (looser) timings, so the video is never stuck."""
    starts, last = [0.0], 0.0
    for (a, b), nxt in zip(islands, islands[1:]):
        if b - last >= PIECE and nxt[0] - b >= 0.25:
            last = (b + nxt[0]) / 2
            starts.append(round(last, 3))
    ends = starts[1:] + [None]
    merged, loose = {"transcription": []}, 0
    for n, (start, end) in enumerate(zip(starts, ends)):
        piece = os.path.join(work, f"piece-{n}.wav")
        run(["ffmpeg", "-v", "error", "-y", "-i", wav_path, "-ss", f"{start:.3f}"]
            + (["-to", f"{end:.3f}"] if end else []) + ["-c:a", "pcm_s16le", piece])
        base = os.path.join(work, f"piece-{n}")
        try:
            result = whisper_once(piece, base)
        except Tripped:
            result, loose = whisper_once(piece, base, precise=False), loose + 1
        ms, cs = round(start * 1000), round(start * 100)
        for seg in result.get("transcription", []):
            for thing in [seg] + seg.get("tokens", []):
                if "offsets" in thing:
                    thing["offsets"] = {k: v + ms for k, v in thing["offsets"].items()}
                if thing.get("t_dtw") is not None and thing.get("t_dtw", -1) >= 0:
                    thing["t_dtw"] += cs
            merged["transcription"].append(seg)
        for ending in (".wav", ".json"):
            if os.path.exists(base + ending):
                os.remove(base + ending)
    print(f"NOTE: listened in {len(starts)} pieces" + (f" ({loose} with looser timings)" if loose else "") + ".")
    with open(os.path.join(work, "whisper.json"), "w", encoding="utf-8") as f:
        json.dump(merged, f)
    return merged


def transcribe(wav_path, work, islands=None):
    """Runs whisper on the sound and returns its full answer (every token with its timing).
    --dtw lines each token up with the sound itself, which is far more precise than
    whisper's own timings (those stretch words across pauses). It needs flash
    attention switched off (-nfa); it still only takes seconds. If whisper trips over
    a very short stretch of speech, it listens again in pieces."""
    if not os.path.exists(MODEL):
        raise SystemExit(f"The speech model isn't downloaded yet. It should be at {MODEL}")
    try:
        return whisper_once(wav_path, os.path.join(work, "whisper"))
    except Tripped:
        if not islands:
            return whisper_once(wav_path, os.path.join(work, "whisper"), precise=False)
    return transcribe_in_pieces(wav_path, work, islands)


def token_time(tok):
    """When a token is said, in seconds (the precise time when there is one)."""
    t = tok.get("t_dtw", -1)
    return t / 100 if t is not None and t >= 0 else tok["offsets"]["from"] / 1000


def words_from_whisper(result):
    """Turns whisper's pieces of words (tokens) into whole words. A word starts when
    its first piece is said and ends when whatever comes next is said."""
    tokens = []
    for seg_no, seg in enumerate(result.get("transcription", [])):
        for tok in seg.get("tokens", []):
            text = tok.get("text", "")
            if text and not text.startswith("[_") and not text.startswith("<|"):
                tokens.append((seg_no, text, token_time(tok), tok.get("p", 0)))
    words = []
    for k, (seg_no, text, t, p) in enumerate(tokens):
        new_word = text.startswith(" ") or not words or words[-1]["segment"] != seg_no
        if new_word and re.search(r"[A-Za-z0-9]", text):
            words.append({"word": text.strip(), "start": t, "end": t, "p": round(p, 3),
                          "segment": seg_no, "last_token": k})
        elif words:
            words[-1]["word"] += text.strip() if new_word else text
            words[-1]["last_token"] = k
    for i, w in enumerate(words):
        nxt = w.pop("last_token") + 1
        w["end"] = tokens[nxt][2] if nxt < len(tokens) else w["start"] + 0.4
        w["end"] = max(w["end"], w["start"] + 0.08)
        w["i"] = i
    return words


def loudness_db(wav_path, step=STEP):
    """How loud the sound is every 20 thousandths of a second, in decibels."""
    with wave.open(wav_path, "rb") as w:
        rate = w.getframerate()
        samples = array.array("h", w.readframes(w.getnframes()))
    size = int(rate * step)
    curve = []
    for start in range(0, len(samples), size):
        chunk = samples[start:start + size]
        energy = sum(s * s for s in chunk) / max(len(chunk), 1)
        curve.append(10 * math.log10(energy + 1))
    return curve


def speech_islands(curve, step=STEP):
    """The stretches where someone is talking (or making a sound), found from the
    loudness alone: louder than the room's background by a clear margin."""
    ranked = sorted(curve)
    floor = ranked[int(len(ranked) * 0.10)]
    peak = ranked[int(len(ranked) * 0.98)]
    threshold = floor + (peak - floor) * SPEECH_LEVEL
    islands, current = [], None
    for k, level in enumerate(curve):
        t = k * step
        if level > threshold:
            if current and t - current[1] <= JOIN_GAP:
                current[1] = t + step
            else:
                if current:
                    islands.append(current)
                current = [t, t + step]
    if current:
        islands.append(current)
    return [[round(a, 3), round(b, 3)] for a, b in islands if b - a >= 0.06]


LONGEST_WORD = 1.5    # seconds: a word "lasting" longer than this is the listener's mistake (it ran on over a pause)
RAN_ON_WORD = 0.6     # ...so it's given this long instead


def place_words(words, islands):
    """Ties each word to the stretch of sound it was said in, and stops each word
    at the end of that stretch, so a word never swallows the pause after it.
    A word the listener stretched over a long pause (once, "it." lasted 17 seconds
    and dragged the silence into the edit) is cut back to a normal length."""
    for w in words:
        w["island"] = None
        for n, (a, b) in enumerate(islands):
            if a - 0.15 <= w["start"] <= b + 0.05:
                w["island"] = n
                w["end"] = min(w["end"], b)
                break
        if w["end"] - w["start"] > LONGEST_WORD:
            w["end"] = w["start"] + RAN_ON_WORD
    return words


def bare(word):
    return re.sub(r"[^a-z']", "", word.lower())


def write_transcript(words, path):
    """One line per sentence, with the time and the word numbers, for Claude to read."""
    lines = []
    for seg in sorted({w["segment"] for w in words}):
        ws = [w for w in words if w["segment"] == seg]
        text = " ".join(f"{w['word']}" for w in ws)
        lines.append(f"[{ws[0]['i']}-{ws[-1]['i']}] {ws[0]['start']:6.2f}s  {text}")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def stream_lengths(video):
    """How long the picture and the sound each last, in seconds."""
    r = run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,duration", "-of", "csv=p=0", video])
    lengths = {}
    for line in r.stdout.split():
        kind, _, seconds = line.partition(",")
        seconds = seconds.split(",")[0]       # some iPhone videos add an empty field ("video,519.69,")
        if seconds and seconds != "N/A":
            lengths[kind] = max(lengths.get(kind, 0.0), float(seconds))
    return lengths.get("video", 0.0), lengths.get("audio", 0.0)


def listen(video, work):
    from sdr import normal_colour
    video = normal_colour(video)        # iPhone HDR footage converted to normal colour first
    picture, sound = stream_lengths(video)
    if picture and sound - picture > 2:   # (a voice recording has no picture at all, and that's fine)
        # Happens when a video doesn't copy across fully: the picture stops, the sound carries on.
        raise SystemExit(f"PICTURE STOPS EARLY: the picture stops at {picture // 60:.0f}:{picture % 60:02.0f} "
                         f"but the sound carries on to {sound // 60:.0f}:{sound % 60:02.0f}. The video probably "
                         f"didn't copy across fully. Ask them to send it again.")
    os.makedirs(work, exist_ok=True)
    wav_path = os.path.join(work, "sound.wav")
    extract_audio(video, wav_path)
    islands = speech_islands(loudness_db(wav_path))
    words = place_words(words_from_whisper(transcribe(wav_path, work, islands)), islands)
    with open(os.path.join(work, "words.json"), "w", encoding="utf-8") as f:
        json.dump({"video": os.path.abspath(video), "islands": islands, "words": words}, f, indent=1)
    write_transcript(words, os.path.join(work, "transcript.txt"))
    print(f"Heard {len(words)} words in {len(islands)} stretches of sound. "
          f"Transcript: {os.path.join(work, 'transcript.txt')}")


# ---------------------------------------------------------------------------
# Step 3: cut
# ---------------------------------------------------------------------------

def quietest(curve, start, end, step=STEP):
    """The quietest moment between two times, so a cut never lands in a word."""
    lo = max(0, int(start / step))
    hi = min(len(curve) - 1, int(end / step))
    if hi <= lo:
        return (start + end) / 2
    return min(range(lo, hi + 1), key=lambda k: curve[k]) * step + step / 2


def pieces_to_keep(words, islands, keep_ranges, curve):
    """The stretches of video to keep, in seconds.

    Every stretch of sound that holds a chosen word is kept, from just before its
    first sound to just after its last. A stretch with no chosen words in it (an
    um, a cough, a take that was dropped) goes. When only part of a stretch is
    chosen, the cut goes in the quietest moment between the last kept word and
    the next one. Pauses up to LONGEST_PAUSE stay as they are; longer ones close up."""
    chosen = {i for first, last in keep_ranges for i in range(first, last + 1)
              if i < len(words) and bare(words[i]["word"]) not in FILLERS}
    # The speech-to-text now and then gives a word an end before its start (2026-10-16, lesson 2.3: "then"
    # 152.73 to 151.42). That made a piece run backwards and threw the picture out of step with the sound.
    words = [dict(w, end=max(w["end"], w["start"] + 0.12)) for w in words]
    spans = []  # (start, end, island number)
    for n, (a, b) in enumerate(islands):
        here = [w for w in words if w["island"] == n]
        if not any(w["i"] in chosen for w in here):
            continue
        runs, current = [], []
        for w in here:
            if w["i"] in chosen:
                current.append(w)
            elif current:
                runs.append(current)
                current = []
        if current:
            runs.append(current)
        for r in runs:
            first, last = here.index(r[0]), here.index(r[-1])
            if first == 0 and r[0]["start"] - a > NOISE_BEFORE:
                # The stretch starts with something that isn't speech (moving the phone, a rustle), so the
                # piece starts just before the first word instead (Frances, 2026-10-14).
                start = quietest(curve, r[0]["start"] - 0.4, r[0]["start"] + 0.02)
            elif first == 0:
                start = a - LEAD_IN
            else:
                before = here[first - 1]
                start = quietest(curve, before["start"] + 0.08, r[0]["start"] + 0.02)
            if last == len(here) - 1 and b - r[-1]["end"] > NOISE_BEFORE:
                end = quietest(curve, r[-1]["end"] - 0.02, r[-1]["end"] + 0.4)   # noise after the last word
            elif last == len(here) - 1:
                end = b + TAIL
            else:
                after = here[last + 1]
                end = quietest(curve, r[-1]["start"] + 0.08, after["start"] + 0.02)
            # Never into a word that was left out (Frances, 2026-10-20, video 1 at 1:10: "leave" and the dropped
            # retake's "will" ran together with no gap, so the breath kept after "leave" took the start of "will"
            # and it glitched): a piece stops before the next dropped word starts, and starts after the last one ends.
            nxt = words[r[-1]["i"] + 1] if r[-1]["i"] + 1 < len(words) else None
            if nxt is not None and nxt["i"] not in chosen and nxt["start"] < end:
                end = max(r[-1]["end"], min(end, quietest(curve, r[-1]["end"] - 0.06, nxt["start"] + 0.01)))
            prev = words[r[0]["i"] - 1] if r[0]["i"] > 0 else None
            if prev is not None and prev["i"] not in chosen and prev["end"] > start:
                start = min(r[0]["start"], max(start, quietest(curve, prev["end"] - 0.01, r[0]["start"] + 0.06)))
            spans.append((start, end, n))
    # Chosen words that fell outside any stretch of sound (said very softly) keep their own piece.
    for i in sorted(chosen):
        w = words[i]
        if w["island"] is None:
            start, end = w["start"] - LEAD_IN, w["end"] + TAIL
            # ...and never into a dropped word either side (the same rule as above).
            if i + 1 < len(words) and i + 1 not in chosen and words[i + 1]["start"] < end:
                end = max(w["end"], words[i + 1]["start"] + 0.01)
            if i > 0 and i - 1 not in chosen and words[i - 1]["end"] > start:
                start = min(w["start"], words[i - 1]["end"] - 0.01)
            spans.append((start, end, None))
    spans.sort()
    merged = []
    for start, end, n in spans:
        if merged:
            p_start, p_end, p_n = merged[-1]
            dropped_between = any(p_end < ia and ib < start + LEAD_IN
                                  for k, (ia, ib) in enumerate(islands)
                                  if k not in {x[2] for x in spans})
            if start - p_end <= LONGEST_PAUSE - LEAD_IN - TAIL and not dropped_between or start <= p_end:
                merged[-1] = (p_start, max(p_end, end), n)
                continue
        merged.append((start, end, n))
    if merged:
        # The very first piece starts with a short breath (Frances, 2026-10-28: "the first words I'm saying"
        # weren't clear when a video started a twentieth of a second before them), starting after anything
        # said before it that was left out.
        s, e, n = merged[0]
        earlier = [w["end"] for w in words if w["end"] <= s + 0.01]
        merged[0] = (min(s, max(s - START_HOLD, (max(earlier) + 0.05) if earlier else 0.0)), e, n)
        # The very last piece breathes out a little longer, so the end of the last word (a soft "s" is easy
        # to miss) is never clipped (Frances, 2026-10-16: "you've cut the sound too soon"), stopping short of
        # anything said after it.
        s, e, n = merged[-1]
        later = [w["start"] for w in words if w["start"] > e]
        merged[-1] = (s, max(e, min(e + END_HOLD, (min(later) - 0.05) if later else e + END_HOLD)), n)
    return [(max(0.0, s), e) for s, e, _ in merged if e - max(0.0, s) > 0.02]   # never a piece that runs backwards


def fewer_jumps(spans, words, keep_ranges):
    """For plain cuts (no glide to smooth a join). Frances, 2026-10-29, on a talking head filmed walking:
    "where it says booked out, you've like glitched it a little bit". Closing up a pause of a fifth of a
    second is a skip in the picture, not an edit, and a sliver of a word left between two cuts (the listener
    had given "are" and "350,000" no length, so only a quarter of a second of each was kept) jumps twice in a
    blink. So a pause is only cut out if that saves at least MIN_CUT, and a piece shorter than MIN_CUT joins
    the pieces either side. Never across a word that was left out (a retake, an um): that cut always stays."""
    chosen = {i for first, last in keep_ranges for i in range(first, last + 1)
              if i < len(words) and bare(words[i]["word"]) not in FILLERS}
    dropped = [(min(w["start"], w["end"]), max(w["start"], w["end"])) for i, w in enumerate(words) if i not in chosen]

    def joinable(end, start):
        return not any(a < start + 0.02 and b > end - 0.02 for a, b in dropped)

    out = [list(spans[0])] if spans else []
    for s, e in spans[1:]:
        if s - out[-1][1] < MIN_CUT and joinable(out[-1][1], s):
            out[-1][1] = e
        else:
            out.append([s, e])
    k = 0
    while k < len(out):
        if out[k][1] - out[k][0] < MIN_CUT:
            if k + 1 < len(out) and joinable(out[k][1], out[k + 1][0]):
                out[k][1] = out.pop(k + 1)[1]
            if k > 0 and joinable(out[k - 1][1], out[k][0]):
                out[k - 1][1] = out.pop(k)[1]
                continue
        k += 1
    return [tuple(p) for p in out]


def video_length(video):
    r = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", video])
    return float(r.stdout.strip())


# ---------------------------------------------------------------------------
# Making the finished video: joins and zooms
# ---------------------------------------------------------------------------
LOW_W, LOW_H = 90, 160   # the tiny copy of each frame used for comparing


def tiny_frames(video):
    """Every frame of the video, shrunk to a tiny black-and-white picture for comparing."""
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", video, "-vf",
                        f"fps={FPS},scale={LOW_W}:{LOW_H},format=gray", "-f", "rawvideo", "-"],
                       capture_output=True)
    size = LOW_W * LOW_H
    return [r.stdout[i:i + size] for i in range(0, len(r.stdout) - size + 1, size)]


def tiny_at(frames, t):
    return frames[min(len(frames) - 1, max(0, round(t * FPS)))]


# Compare the middle of the picture (where the face and body are), every other pixel.
COMPARE = [(x, y) for y in range(int(LOW_H * 0.15), int(LOW_H * 0.75), 2)
           for x in range(int(LOW_W * 0.15), int(LOW_W * 0.85), 2)]


def use_landscape():
    """Course videos (Frances, 2026-10-12: filmed on her phone on its side) keep the wide shape they were
    filmed in, 1920 x 1080, instead of being cropped to an upright reel."""
    global W, H, LOW_W, LOW_H, COMPARE
    W, H, LOW_W, LOW_H = 1920, 1080, 160, 90
    COMPARE = [(x, y) for y in range(int(LOW_H * 0.15), int(LOW_H * 0.75), 2)
               for x in range(int(LOW_W * 0.15), int(LOW_W * 0.85), 2)]


def difference(a, b):
    """How different two tiny frames look, in the middle of the picture."""
    return sum(abs(a[y * LOW_W + x] - b[y * LOW_W + x]) for x, y in COMPARE)


def best_shift(frames, a_end, b_start):
    """For one cut: which frame to switch the picture on, up to SHIFT_FRAMES either
    side of the sound's cut, so the face is as close as possible to the same place."""
    costs = []
    for shift in range(-SHIFT_FRAMES, SHIFT_FRAMES + 1):
        a = tiny_at(frames, a_end + shift / FPS)
        b = tiny_at(frames, b_start + shift / FPS)
        costs.append((difference(a, b) * (1 + 0.03 * abs(shift)), shift))
    return min(costs)[1]


def smoothstep(p):
    p = min(1.0, max(0.0, p))
    return p * p * (3 - 2 * p)


def read_frames(video, start, count):
    """`count` full-size frames from `start` seconds, one at a time.

    The frames are counted from the first one at or after `start` (setpts). Without that, a piece starting
    between two frames showed one frame twice and skipped the next, over and over, and a piece starting on a
    frame showed its first frame twice (Frances, 2026-10-29, lesson 12.1: "around about 2 seconds in, it
    glitches a bit")."""
    proc = subprocess.Popen(["ffmpeg", "-v", "error", "-ss", f"{max(0.0, start):.4f}", "-i", video,
                             "-vf", f"setpts=PTS-STARTPTS,fps={FPS},"
                                    f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}",
                             "-frames:v", str(count), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    size = W * H * 3
    last = None
    for _ in range(count):
        buf = proc.stdout.read(size)
        if len(buf) < size:
            buf = last  # ran out at the very end of the video: hold the last frame
        last = buf
        yield buf
    proc.stdout.close()
    proc.wait()


def make_sound(video, spans, n_frames, path, clean_up=""):
    """The finished sound: each kept piece with a tiny fade at both ends, joined,
    evened out for Instagram, and exactly as long as the picture. clean_up: extra
    FFmpeg sound filters (voiceovers use a gentle hum and hiss clean-up)."""
    graph = [f"[0:a]asplit={len(spans)}" + "".join(f"[s{n}]" for n in range(len(spans)))]
    for n, (s, e) in enumerate(spans):
        graph.append(f"[s{n}]atrim=start={s:.4f}:end={e:.4f},asetpts=PTS-STARTPTS,"
                     f"afade=t=in:d={FADE},afade=t=out:st={max(0, e - s - FADE):.4f}:d={FADE}[a{n}]")
    # A second of silence goes on before the evening-out, so it never swallows the end of the last word
    # (found 2026-10-16: the last "is" in lesson 2.3 was cut short).
    graph.append("".join(f"[a{n}]" for n in range(len(spans))) +
                 f"concat=n={len(spans)}:v=0:a=1,{clean_up + ',' if clean_up else ''}apad=pad_dur=1,"
                 f"loudnorm=I={LOUDNESS}:TP=-1.5:LRA=11,"
                 f"aresample=48000,apad,atrim=end={n_frames / FPS:.4f}[aout]")
    run(["ffmpeg", "-v", "error", "-y", "-i", video, "-filter_complex", ";".join(graph),
         "-map", "[aout]", "-c:a", "pcm_s16le", path])


# Glides: draw the frames in between, so one piece flows into the next (OpenCV and NumPy).

def frame_at(video, t):
    """One full-size frame (as numbers, blue-green-red) at t seconds."""
    import numpy as np
    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{max(0.0, t):.4f}", "-i", video, "-vf",
                        f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}",
                        "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], capture_output=True)
    return np.frombuffer(r.stdout, np.uint8).reshape(H, W, 3)


def motion(a, b):
    """How every pixel moves from frame a to frame b (optical flow), worked out at half
    size for speed and smoothed so the face moves as one piece."""
    import cv2
    small = (W // 2, H // 2)
    ga = cv2.cvtColor(cv2.resize(a, small), cv2.COLOR_BGR2GRAY)
    gb = cv2.cvtColor(cv2.resize(b, small), cv2.COLOR_BGR2GRAY)
    f = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM).calc(ga, gb, None)
    return cv2.resize(cv2.GaussianBlur(f, (0, 0), 2), (W, H)) * 2


class Morpher:
    """Draws the frames in between two frames, so one glides into the other."""

    def __init__(self):
        import numpy as np
        self.gx, self.gy = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32))

    def warp(self, frame, flow, amount):
        import cv2
        return cv2.remap(frame, self.gx - amount * flow[..., 0], self.gy - amount * flow[..., 1],
                         cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)

    def left_over(self, a, b, ab):
        """How different b still looks from a once a has been moved along the flow: low
        means the morph will look clean, high means a straight cut is better."""
        import numpy as np
        face = (slice(int(H * 0.15), int(H * 0.63)), slice(int(W * 0.18), int(W * 0.82)))
        moved = self.warp(a, ab, 1.0)
        return float(np.mean(np.abs(moved[face].astype(np.int16) - b[face].astype(np.int16))))

    def worst_patch(self, a, b, ab):
        """The same, for the worst of 64 patches across the whole picture. The face can glide cleanly while a
        hand moving lower down smears (Frances, 2026-10-28: "you're making me hands like go all weird")."""
        import numpy as np
        d = np.abs(self.warp(a, ab, 1.0).astype(np.int16) - b.astype(np.int16)).mean(axis=2)
        ph, pw = H // 8, W // 8
        return float(max(d[y * ph:(y + 1) * ph, x * pw:(x + 1) * pw].mean() for y in range(8) for x in range(8)))

    def between(self, a, b, ab, ba, count):
        import cv2
        frames = []
        for j in range(1, count + 1):
            t = j / (count + 1)
            t = t * t * (3 - 2 * t)   # ease in and out
            frames.append(cv2.addWeighted(self.warp(a, ab, t), 1 - t, self.warp(b, ba, 1 - t), t, 0))
        return frames


def zoom_frame(frame, zoom, centre=FACE_AT):
    """The frame drawn `zoom` times bigger around the face (centre, as fractions across
    and down). Zooming in around a point inside the picture never shows an edge."""
    import cv2
    import numpy as np
    if abs(zoom - 1) < 1e-4:
        return frame
    ax, ay = centre[0] * W, centre[1] * H
    m = np.float32([[zoom, 0, ax * (1 - zoom)], [0, zoom, ay * (1 - zoom)]])
    return cv2.warpAffine(frame, m, (W, H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)


def zoom_for(style, n, piece, piece_from):
    """How zoomed in output frame n is, for a frame in `piece`, which starts at frame piece_from."""
    zoom = 1.0
    if style["zoom"] == "push":
        zoom *= 1 + (PUSH_TO - 1) * smoothstep(n / (PUSH_SECONDS * FPS))
    elif style["zoom"] == "punch" and piece % 2:
        zoom *= PUNCH
    elif style["zoom"] == "bounce" and piece > 0:
        p = (n - piece_from) / (BOUNCE_SECONDS * FPS)
        if p < 1:
            zoom *= 1 + (BOUNCE_FROM - 1) * (1 - p) ** 3
    return zoom


def render_style(video, spans, out, style_name="glide"):
    """Saves the finished video in one of the CUT_STYLES.

    The sound is always cut the same way: at the quiet moments, with a tiny fade.
    The picture switches on the frame near each cut where the face is most in the
    same place either side. Then, depending on the style: a glide where the move is
    small (a clean cut where it's big), a slow push-in, every other piece closer, a
    bounce on each new piece, a soft flash, or a plain cut."""
    import numpy as np
    style = CUT_STYLES[style_name]
    centre = FACE_AT
    if style["zoom"] != "none":
        import face
        spot = face.where(video)
        if spot:
            centre = spot["centre"]
    durations = [e - s for s, e in spans]
    joins_at, total = [], 0.0
    for d in durations:
        total += d
        joins_at.append(total)
    n_frames = round(total * FPS)
    tiny = tiny_frames(video)
    morpher = Morpher() if style["joins"] == "glide" else None
    plans = []
    for k in range(len(spans) - 1):
        switch = round(joins_at[k] * FPS) + best_shift(tiny, spans[k][1], spans[k + 1][0])
        frames, left_over = 0, None
        if morpher:
            # Measure the move using the frames either side of a short glide.
            half = MORPH_FRAMES_BIGGER // 2
            a_time = spans[k][0] + ((switch - half - 1) / FPS - (joins_at[k - 1] if k else 0.0))
            b_time = spans[k + 1][0] + ((switch + half) / FPS - joins_at[k])
            a, b = frame_at(video, a_time), frame_at(video, b_time)
            ab = motion(a, b)
            left_over = round(morpher.left_over(a, b, ab), 1)
            worst = round(morpher.worst_patch(a, b, ab), 1)
            frames = MORPH_FRAMES if left_over <= MORPH_SMALL else MORPH_FRAMES_BIGGER if left_over <= MORPH_LIMIT else 0
            if worst > MORPH_HANDS:
                frames = 0
        plans.append({"switch": switch, "glide_frames": frames, "left_over": left_over}
                     | ({"worst_patch": worst} if morpher else {}))
    tmp = tempfile.mkdtemp(prefix="talking-head-")
    try:
        sound = os.path.join(tmp, "sound.wav")
        make_sound(video, spans, n_frames, sound)
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        writer = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24",
                                   "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", sound,
                                   "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "medium",
                                   "-crf", "16", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                                   "-movflags", "+faststart", out], stdin=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL)
        flashes = {}
        if style["joins"] == "flash":
            for plan in plans:
                for j, strength in enumerate(FLASH):
                    flashes[plan["switch"] - 1 + j] = strength
        written = 0

        def emit(frame, piece, piece_from):
            nonlocal written
            frame = zoom_frame(frame, zoom_for(style, written, piece, piece_from), centre)
            if written in flashes:
                frame = (frame * (1 - flashes[written]) + 255 * flashes[written]).astype(np.uint8)
            writer.stdin.write(frame.tobytes())
            written += 1

        previous = None   # the last frame written, to glide from
        for k, (s, e) in enumerate(spans):
            glide_in = plans[k - 1]["glide_frames"] if k else 0
            glide_out = plans[k]["glide_frames"] if k < len(plans) else 0
            start = 0 if k == 0 else plans[k - 1]["switch"] + glide_in // 2
            end = n_frames if k == len(spans) - 1 else plans[k]["switch"] - glide_out // 2
            piece_from = 0 if k == 0 else plans[k - 1]["switch"] - glide_in // 2
            piece_starts = joins_at[k - 1] if k else 0.0
            source_start = s + (start / FPS - piece_starts)
            for j, buf in enumerate(read_frames(video, source_start, end - start)):
                frame = np.ascontiguousarray(np.frombuffer(buf, np.uint8).reshape(H, W, 3)[..., ::-1])
                if j == 0 and glide_in:
                    for g in morpher.between(previous, frame, motion(previous, frame), motion(frame, previous),
                                             glide_in):
                        emit(g, k, piece_from)
                emit(frame, k, piece_from)
                previous = frame
        writer.stdin.close()
        if writer.wait() != 0:
            raise SystemExit("Saving the finished video didn't work.")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return plans


def finished_words(words, keep_ranges, spans):
    """Every kept word with the moment it's said in the finished video (not the
    original), for the captions and pop-ups. "piece" says which kept piece it's in."""
    chosen = sorted({i for first, last in keep_ranges for i in range(first, last + 1)
                     if i < len(words) and bare(words[i]["word"]) not in FILLERS})
    piece_starts, total = [], 0.0
    for s, e in spans:
        piece_starts.append(total)
        total += e - s
    timeline = []
    for i in chosen:
        w = words[i]
        for k, (s, e) in enumerate(spans):
            if s - 0.15 <= w["start"] <= e:
                start = piece_starts[k] + max(0.0, w["start"] - s)
                end = piece_starts[k] + min(e - s, w["end"] - s)
                timeline.append({"i": i, "word": w["word"], "start": round(start, 3),
                                 "end": round(max(end, start + 0.08), 3), "piece": k})
                break
    return timeline


def cut(video, work, out, style="glide"):
    from sdr import normal_colour
    video = normal_colour(video)        # the same normal-colour copy listen() used
    with open(os.path.join(work, "words.json"), encoding="utf-8") as f:
        listened = json.load(f)
    words, islands = listened["words"], listened["islands"]
    with open(os.path.join(work, "keep.json"), encoding="utf-8") as f:
        keep_ranges = json.load(f)
    curve = loudness_db(os.path.join(work, "sound.wav"))
    before = video_length(video)
    spans = [(s, min(e, before)) for s, e in pieces_to_keep(words, islands, keep_ranges, curve)]
    if CUT_STYLES[style]["joins"] != "glide":
        spans = fewer_jumps(spans, words, keep_ranges)
    plans = render_style(video, spans, out, style)
    after = video_length(out)
    kept_words = sum(1 for a, b in keep_ranges for w in words[a:b + 1] if bare(w["word"]) not in FILLERS)
    summary = {"before_seconds": round(before, 1), "after_seconds": round(after, 1),
               "pieces": len(spans), "style": style, "words_kept": kept_words, "words_heard": len(words),
               "spans": [[round(s, 2), round(e, 2)] for s, e in spans], "join_plans": plans}
    with open(os.path.join(work, "cut-summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=1)
    with open(os.path.join(work, "timeline.json"), "w", encoding="utf-8") as f:
        json.dump({"video": os.path.abspath(out), "seconds": round(after, 3),
                   "words": finished_words(words, keep_ranges, spans)}, f, indent=1)
    print(f"{before:.0f}s down to {after:.0f}s, in {len(spans)} pieces ({CUT_STYLES[style]['name']}). Saved {out}")


def main():
    global START_HOLD
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="step", required=True)
    a = sub.add_parser("listen", help="write down every word with its timing")
    a.add_argument("video")
    a.add_argument("--work", required=True, help="folder for this video's working files")
    b = sub.add_parser("cut", help="make the tidy video from keep.json")
    b.add_argument("video")
    b.add_argument("--work", required=True)
    b.add_argument("--out", required=True)
    b.add_argument("--style", choices=list(CUT_STYLES), default="glide",
                   help="how the pieces join and move: " +
                        "; ".join(f"{k} ({v['name']})" for k, v in CUT_STYLES.items()))
    b.add_argument("--landscape", action="store_true",
                   help="keep a wide video wide (1920 x 1080), for course videos, instead of an upright reel")
    b.add_argument("--start-hold", type=float,
                   help=f"seconds of breath before the first word (default {START_HOLD}); less when there's a "
                        f"mouth click or the end of a word just before it")
    args = ap.parse_args()
    if args.step == "listen":
        listen(args.video, args.work)
    else:
        if args.landscape:
            use_landscape()
        if args.start_hold is not None:
            START_HOLD = args.start_hold
        cut(args.video, args.work, args.out, args.style)


if __name__ == "__main__":
    main()
