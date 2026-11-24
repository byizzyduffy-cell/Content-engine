"""
Talking-head editor, stage 2: captions.

Puts the words on screen as they're said (above the head, under the chin or
lower down: see POSITIONS), on the tidy video
that talking_head.py made. It uses the word timings saved when the video was
cut (timeline.json), so every word lands the moment it's spoken.

    .venv/bin/python engine/captions.py "TIDY.mp4" --work "FOLDER" --out "CAPTIONED.mp4" --design pop
    .venv/bin/python engine/captions.py "TIDY.mp4" --work "FOLDER" --preview "DESIGNS.png"

Designs (see DESIGNS below):
    pop        one word at a time, popping in (Frances's method)
    highlight  a few words at a time, the word being said in a coloured box
    sentence   the whole sentence on a see-through panel, lighting up as it's said
    elegant    one word at a time in a serif font, rising gently into place
    bold       two words at a time in heavy capitals, the word being said in colour
    pills      each word lands on its own little sticker as it's said
    underline  a few words at a time, a line in the brand colour under the word being said
    build      the sentence builds up word by word, softly fading in

Any design can take another font (--font) and other colours (--colour, --accent,
--accent-text). If whisper misheard a word, Claude writes fixes.json in the work
folder, e.g. {"42": "SkinPen"}, and the caption uses the fixed word.

Built from scratch with open-source tools: Pillow draws the words, NumPy lays
them on the video, FFmpeg reads and saves the video. Fonts are OFL (see fonts/licences).
"""

import tools  # noqa: F401  (first: emoji-safe output on Windows)
import argparse
import json
import os
import re
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from text_reel import load_font  # noqa: E402
import face  # noqa: E402

W, H, FPS = 1080, 1920, 30

# ---------------------------------------------------------------------------
# Where the captions sit
# ---------------------------------------------------------------------------
CHIN = 0.61           # where the chin usually is, down the screen (0 = top, 1 = bottom), if no face is found
HEAD_TOP = 0.33       # where the top of the head usually is, down the screen, if no face is found
UNDER_CHIN = 35       # gap between the chin (at its lowest, mouth open) and the top of the captions
ABOVE_HEAD = 40       # gap between the bottom of the captions and the top of the head
HIGHEST = 270         # captions never go above this, so Instagram's top bar doesn't cover them
LOWEST = 1450         # under the chin, captions never go below this, so Instagram's caption doesn't cover them
LOW_LINE = 1560       # "Lower down": the bottom of the captions sits here, just above Instagram's name and caption

# Where the captions sit. Students pick one; under the chin is the default.
POSITIONS = {
    "above": {"name": "Above your head", "say": "Put my captions above my head",
              "about": "Your captions sit in the space above your head, so nothing is near your face.",
              "good_for": "Videos filmed with plenty of room above your head."},
    "chin": {"name": "Under your chin", "say": "Put my captions under my chin",
             "about": "Your captions sit just under your chin, right where people look.",
             "good_for": "Most talking heads. The easiest to read along with."},
    "low": {"name": "Lower down", "say": "Put my captions lower down",
            "about": "Your captions sit lower down the screen, just above where Instagram puts its own caption.",
            "good_for": "When you want your face and shoulders clear of words."},
}
# Voiceovers have no face to work around, so captions can go anywhere (Frances, 2026-10-10).
VOICEOVER_POSITIONS = {
    "middle": {"name": "In the middle", "say": "Put my voiceover captions in the middle",
               "about": "Your captions sit right in the middle of the screen, where eyes go first.",
               "good_for": "Every voiceover. The default."},
    "top": {"name": "Near the top", "say": "Put my voiceover captions near the top",
            "about": "Your captions sit near the top, and your pop-up words and emojis move lower down.",
            "good_for": "Clips with the action in the middle you don't want covered."},
    "low": {"name": "Lower down", "say": "Put my voiceover captions lower down",
            "about": "Your captions sit lower down, just above where Instagram puts its own caption.",
            "good_for": "Clips with the action in the top half."},
}
TOP_LINE = 300        # "Near the top": the top of the captions (the same line pop-ups start on)
WIDEST = 860          # captions never get wider than this

# ---------------------------------------------------------------------------
# Timing
# ---------------------------------------------------------------------------
LINGER = 0.35         # a caption stays this long after its last word when a pause follows
BRIDGE = 0.7          # a pause shorter than this keeps the caption up until the next one
BREAK_AT_PAUSE = 0.45 # a pause this long always starts a new caption

# ---------------------------------------------------------------------------
# Colours (Frances's brand). A student's own colours replace these.
# ---------------------------------------------------------------------------
WHITE = "#FFFFFF"
CREAM = "#FBF8F4"
BEIGE = "#E0D8D0"
CHARCOAL = "#2D2E30"

DESIGNS = {
    "pop": {
        "name": "One word pop", "font": "Poppins", "size": 88, "words": 1,
        "colour": WHITE, "entrance": "pop",
        "about": "One word at a time, popping in the moment you say it.",
        "good_for": "Teaching and tips. Easy to follow with the sound off.",
    },
    "highlight": {
        "name": "Highlighted word", "font": "Poppins", "size": 66, "words": 3, "chars": 20,
        "colour": WHITE, "accent": BEIGE, "accent_text": CHARCOAL, "box": True, "entrance": "pop",
        "about": "Three words at a time. The word you're saying sits in a box in your brand colour.",
        "good_for": "Lively talking heads. Keeps eyes moving along with you.",
    },
    "sentence": {
        "name": "Whole sentence", "font": "Poppins", "size": 54, "words": 8, "chars": 44, "lines": 2,
        "colour": WHITE, "dim": 0.45, "panel": CHARCOAL, "punctuation": True, "entrance": "fade",
        "about": "The whole line on a see-through panel. Each word lights up as you say it.",
        "good_for": "Longer explanations and anyone who reads along.",
    },
    "elegant": {
        "signature": True, "name": "Elegant word", "font": "Playfair Display", "size": 92, "words": 1,
        "colour": CREAM, "entrance": "rise",
        "about": "One word at a time in a classic serif font, rising gently into place.",
        "good_for": "Luxury, calm and premium brands.",
    },
    "bold": {
        "signature": True, "name": "Bold capitals", "font": "Outfit", "size": 88, "words": 2, "chars": 14, "capitals": True,
        "colour": WHITE, "accent": BEIGE, "outline": CHARCOAL, "entrance": "pop",
        "about": "Two words at a time in heavy capitals. The word you're saying changes colour.",
        "good_for": "Hot takes, myth-busting and anything that needs punch.",
    },
    "pills": {
        "name": "Word stickers", "font": "Poppins", "size": 62, "words": 3, "chars": 20,
        "colour": CHARCOAL, "pill": WHITE, "reveal": True, "word_fade": 0.08, "entrance": "pop",
        "about": "Each word lands on its own little sticker as you say it, up to three at a time.",
        "good_for": "Friendly, playful brands. Lashes, brows and beauty chat.",
    },
    "underline": {
        "signature": True, "name": "Underlined word", "font": "Montserrat", "size": 64, "words": 3, "chars": 20,
        "colour": WHITE, "accent": BEIGE, "underline": True, "word_fade": 0.06, "entrance": "fade",
        "about": "Three words at a time, with a line in your brand colour under the word you're saying.",
        "good_for": "Clean, modern clinics. Smart without shouting.",
    },
    "build": {
        "signature": True, "name": "Soft build", "font": "Jost", "size": 66, "words": 8, "chars": 40, "lines": 2,
        "colour": CREAM, "reveal": True, "word_fade": 0.12, "entrance": "fade",
        "about": "The sentence builds up word by word as you speak, softly fading in.",
        "good_for": "Gentle, reassuring videos. Skin journeys and aftercare.",
    },
}


def rgba(colour, alpha=255):
    colour = colour.lstrip("#")
    return tuple(int(colour[k:k + 2], 16) for k in (0, 2, 4)) + (alpha,)


# ---------------------------------------------------------------------------
# The words
# ---------------------------------------------------------------------------

def load_words(work):
    """The kept words with their times in the finished video, with any fixes applied."""
    path = os.path.join(work, "timeline.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            words = json.load(f)["words"]
    else:  # made before timeline.json existed: work it out from the cut
        from talking_head import finished_words
        with open(os.path.join(work, "words.json"), encoding="utf-8") as f:
            heard = json.load(f)["words"]
        with open(os.path.join(work, "keep.json"), encoding="utf-8") as f:
            keep = json.load(f)
        with open(os.path.join(work, "cut-summary.json"), encoding="utf-8") as f:
            spans = json.load(f)["spans"]
        words = finished_words(heard, keep, spans)
    fixes_path = os.path.join(work, "fixes.json")
    if os.path.exists(fixes_path):
        with open(fixes_path, encoding="utf-8") as f:
            fixes = {int(k): v for k, v in json.load(f).items()}
        for w in words:
            if w["i"] in fixes:
                w["word"] = fixes[w["i"]]
    return words


def shown(word, design):
    """The word as it appears: no full stops or commas (captions read cleaner without),
    question marks kept only in the sentence design, capitals if the design uses them."""
    text = word.strip().strip("\"“”‘(")
    text = re.sub(r"[\"”’),.;:…]+$", "", text)
    if not design.get("punctuation"):
        text = re.sub(r"[?!]+$", "", text)
    return text.upper() if design.get("capitals") else text


def ends_sentence(word):
    return bool(re.search(r"[.?!…]$", word.strip()))


def group_words(words, design):
    """Splits the words into captions: never more than the design allows, and always
    a new caption after a sentence ends, at a comma (once a sentence caption has a
    few words), at a long pause or a cut."""
    groups, current = [], []
    limit_words, limit_chars = design["words"], design.get("chars", 99)
    for w in words:
        if current:
            last = current[-1]
            chars = sum(len(x["word"]) + 1 for x in current) + len(w["word"])
            if (len(current) >= limit_words or chars > limit_chars
                    or ends_sentence(last["word"]) or (last["word"].strip().endswith(",") and
                                                       (limit_words < 8 or len(current) >= 3))
                    or w["start"] - last["end"] > BREAK_AT_PAUSE or w["piece"] != last["piece"]):
                groups.append(current)
                current = []
        current.append(w)
    if current:
        groups.append(current)
    timed = []
    for n, g in enumerate(groups):
        start = g[0]["start"]
        end = g[-1]["end"] + LINGER
        if n + 1 < len(groups):
            following = groups[n + 1][0]["start"]
            end = following if following - g[-1]["end"] < BRIDGE else min(end, following)
        timed.append({"words": g, "start": start, "end": end})
    return timed


# ---------------------------------------------------------------------------
# Drawing one caption
# ---------------------------------------------------------------------------

class Caption:
    """Draws a caption (a few words) with one word marked as the one being said."""

    def __init__(self, design):
        self.d = design
        self.font = load_font(design["font"], design["size"], "heading")
        size = design["size"]
        self.tracking = size * 0.03 if design.get("capitals") else 0
        self.space = self.font.getlength(" ") + (size * 0.12 if design.get("capitals") else 0)
        if design.get("box"):
            self.space += size * 0.2   # room for the coloured box, so it never touches the next word
        if design.get("pill"):
            self.space += size * 0.5   # stickers need a little gap between them
        top, bottom = self.font.getbbox("HÅgy", anchor="ls")[1::2]
        self.above, self.below = -top, bottom      # how far letters reach above and below the line
        self.line_height = round((self.above + self.below) * 1.12)
        self.pad = round(size * 0.6)               # room around the words for boxes, outlines and shadow

    def width(self, text):
        return self.font.getlength(text) + self.tracking * max(len(text) - 1, 0)

    def line_width(self, line):
        return sum(self.width(t) for _, t in line) + self.space * (len(line) - 1)

    def lines(self, texts):
        """Wraps the words into lines no wider than WIDEST. Two lines are balanced, so a
        word is never left on its own underneath."""
        words = list(enumerate(texts))
        if self.line_width(words) <= WIDEST or len(words) < 2:
            return [words]
        best = min(range(1, len(words)),
                   key=lambda k: max(self.line_width(words[:k]), self.line_width(words[k:])))
        first, rest = words[:best], words[best:]
        if self.line_width(rest) <= WIDEST:
            return [first, rest]
        lines, current = [first], []
        for item in rest:
            if current and self.line_width(current + [item]) > WIDEST:
                lines.append(current)
                current = []
            current.append(item)
        return lines + [current]

    def put(self, draw, x, baseline, text, fill, outline=None):
        stroke = {"stroke_width": max(3, round(self.d["size"] * 0.07)), "stroke_fill": outline} if outline else {}
        if not self.tracking:
            draw.text((x, baseline), text, font=self.font, fill=fill, anchor="ls", **stroke)
            return
        for i, letter in enumerate(text):
            at = x + self.font.getlength(text[:i]) + self.tracking * i
            draw.text((at, baseline), letter, font=self.font, fill=fill, anchor="ls", **stroke)

    def draw(self, texts, said):
        """texts: the words of this caption. said: how many of them have been said so far
        (the last one said is the one being said now)."""
        d = self.d
        lines = self.lines(texts)
        widths = [self.line_width(line) for line in lines]
        canvas_w = round(max(widths) + self.pad * 2)
        canvas_h = round(self.line_height * len(lines) + self.pad * 2)
        canvas = Image.new("RGBA", (canvas_w, canvas_h))
        shadow = Image.new("RGBA", canvas.size)
        boxes = ImageDraw.Draw(canvas)
        if d.get("panel"):
            inset = self.pad * 0.45
            boxes.rounded_rectangle((inset, inset, canvas_w - inset, canvas_h - inset),
                                    radius=round(d["size"] * 0.45), fill=rgba(d["panel"], 160))
        words_layer = Image.new("RGBA", canvas.size)
        draw = ImageDraw.Draw(words_layer)
        shade = ImageDraw.Draw(shadow)
        now = said - 1
        for n, line in enumerate(lines):
            # Words that build up start from the left, like typing; the rest are centred.
            x = (canvas_w - max(widths)) / 2 if d.get("reveal") else (canvas_w - widths[n]) / 2
            baseline = self.pad + self.line_height * n + (self.line_height + self.above - self.below) / 2
            for k, text in line:
                w = self.width(text)
                if d.get("reveal") and k > now:   # not said yet: its place is kept, but it isn't shown
                    x += w + self.space
                    continue
                colour = rgba(d["colour"])
                grow = d["size"] * 0.16
                if d.get("pill"):
                    pill = (x - grow * 1.3, baseline - self.above - grow * 0.7,
                            x + w + grow * 1.3, baseline + self.below + grow * 0.7)
                    shade.rounded_rectangle(tuple(v + (d["size"] * 0.06 if i % 2 else 0) for i, v in enumerate(pill)),
                                            radius=round(d["size"] * 0.5), fill=(0, 0, 0, 110))
                    boxes.rounded_rectangle(pill, radius=round(d["size"] * 0.5), fill=rgba(d["pill"]))
                if k == now and d.get("underline"):
                    bar_top = baseline + self.below * 0.35
                    boxes.rounded_rectangle((x - 2, bar_top, x + w + 2, bar_top + d["size"] * 0.13),
                                            radius=round(d["size"] * 0.065), fill=rgba(d["accent"]))
                    colour = rgba(d["colour"])
                elif k == now and d.get("box"):
                    grow = d["size"] * 0.16
                    boxes.rounded_rectangle((x - grow, baseline - self.above - grow * 0.6,
                                             x + w + grow, baseline + self.below + grow * 0.6),
                                            radius=round(d["size"] * 0.2), fill=rgba(d["accent"]))
                    colour = rgba(d["accent_text"])
                elif k == now and d.get("accent") and not d.get("underline"):
                    colour = rgba(d["accent"])
                elif d.get("dim") and k > now:
                    colour = rgba(d["colour"], round(255 * d["dim"]))
                # "plain" (Frances, 2026-10-20: "no shadows or no outlines on the text. Just the plainest text
                # possible"): just the letters, with no soft shadow behind them and no outline round them.
                if not d.get("panel") and not d.get("pill") and not (k == now and d.get("box")) and not d.get("plain"):
                    self.put(shade, x, baseline + d["size"] * 0.04, text, (0, 0, 0, 170), (0, 0, 0, 170))
                outline = rgba(d["outline"]) if d.get("outline") and not d.get("plain") else None
                self.put(draw, x, baseline, text, colour, outline)
                x += w + self.space
        if not d.get("panel"):
            shadow = shadow.filter(ImageFilter.GaussianBlur(d["size"] * (0.14 if d.get("pill") else 0.09)))
            canvas = Image.alpha_composite(shadow, canvas)
        canvas = Image.alpha_composite(canvas, words_layer)
        return canvas


# ---------------------------------------------------------------------------
# Movement
# ---------------------------------------------------------------------------

def ease_out_back(p):
    c = 1.6
    return 1 + (c + 1) * (p - 1) ** 3 + c * (p - 1) ** 2


def entrance(kind, seconds):
    """How a caption comes on: (size, see-through amount, nudge down in pixels) at a
    moment after it starts."""
    if kind == "pop":
        p = min(1.0, seconds / 0.16)
        return 0.72 + 0.28 * ease_out_back(p), min(1.0, seconds / 0.05), 0
    if kind == "rise":
        p = min(1.0, seconds / 0.22)
        eased = 1 - (1 - p) ** 3
        return 1.0, p, round(22 * (1 - eased))
    p = min(1.0, seconds / 0.12)  # fade
    return 1.0, p, 0


def lay_on(frame, picture, centre_x, top, alpha=1.0):
    """Lays a see-through picture onto a video frame (both as numbers)."""
    ph, pw = picture.shape[:2]
    x0, y0 = round(centre_x - pw / 2), round(top)
    fx0, fy0, fx1, fy1 = max(0, x0), max(0, y0), min(W, x0 + pw), min(H, y0 + ph)
    if fx1 <= fx0 or fy1 <= fy0:
        return
    part = picture[fy0 - y0:fy1 - y0, fx0 - x0:fx1 - x0].astype(np.float32)
    a = part[..., 3:4] / 255.0 * alpha
    region = frame[fy0:fy1, fx0:fx1].astype(np.float32)
    frame[fy0:fy1, fx0:fx1] = (region * (1 - a) + part[..., :3] * a).astype(np.uint8)


class Captioner:
    """Works out what's on screen at any moment and draws it onto the frame."""

    def __init__(self, words, design, position="chin", chin=CHIN, head_top=HEAD_TOP, looks=None):
        """looks: where the face is through the video (from face.faces). With them, each
        kept piece of the video gets captions placed for where the face is in that piece,
        so they move only at a cut, never mid-sentence. Without them, chin and head_top
        are used throughout."""
        self.design = design
        self.caption = Caption(design)
        self.groups = group_words(words, design)
        self.cache = {}
        tallest = max(self.picture(g, len(g["words"])).height for g in self.groups) - self.caption.pad * 2
        spots = {}
        if looks:
            for piece in {w["piece"] for w in words}:
                here = [w for w in words if w["piece"] == piece]
                start, end = here[0]["start"] - 0.25, here[-1]["end"] + 0.25
                found = [f for t, f in looks if f and start <= t <= end]
                if found:
                    spots[piece] = face.head_and_chin(found)
        for g in self.groups:
            piece_chin, piece_head = spots.get(g["words"][0]["piece"], (chin, head_top))
            # Under the chin, captions hang from a line. Above the head and lower down they
            # stand on a line, so one-line and two-line captions both stay clear of the head
            # (or of Instagram's caption).
            if position == "middle":   # voiceovers
                g["anchor"], g["edge"] = "middle", H / 2
            elif position == "top":    # voiceovers
                g["anchor"], g["edge"] = "top", TOP_LINE
            elif position == "above":
                g["anchor"], g["edge"] = "bottom", max(piece_head * H - ABOVE_HEAD, HIGHEST + tallest)
            elif position == "low":
                g["anchor"], g["edge"] = "bottom", LOW_LINE
            else:
                g["anchor"], g["edge"] = "top", min(piece_chin * H + UNDER_CHIN, LOWEST - tallest)

    def band(self, start, end):
        """How far up and down the screen the captions reach between start and end seconds, or None.
        The hook uses it to keep clear of them."""
        reach = None
        for g in self.groups:
            if g["end"] <= start or g["start"] >= end:
                continue
            height = self.picture(g, len(g["words"])).height - self.caption.pad * 2
            top = {"top": g["edge"], "middle": g["edge"] - height / 2}.get(g["anchor"], g["edge"] - height)
            reach = (top, top + height) if reach is None else (min(reach[0], top), max(reach[1], top + height))
        return reach

    def picture(self, group, said):
        key = (id(group), said)
        if key not in self.cache:
            texts = [shown(w["word"], self.design) for w in group["words"]]
            self.cache[key] = self.caption.draw(texts, said)
        return self.cache[key]

    def at(self, t):
        """The caption showing at t seconds, and how many of its words have been said."""
        for g in self.groups:
            if g["start"] <= t < g["end"]:
                said = sum(1 for w in g["words"] if w["start"] <= t + 0.01)
                return g, max(1, said)
        return None, 0

    def draw_on(self, frame, t):
        group, said = self.at(t)
        if not group:
            return frame
        picture = self.picture(group, said)
        fade = self.design.get("word_fade")
        if fade and said > 1:
            # The newest word (or the moved underline) fades in over the last picture.
            p = (t - group["words"][said - 1]["start"]) / fade
            if p < 1:
                before = np.asarray(self.picture(group, said - 1)).astype(np.float32)
                after = np.asarray(picture).astype(np.float32)
                picture = Image.fromarray((before + (after - before) * max(0.0, p)).astype(np.uint8), "RGBA")
        scale, alpha, nudge = entrance(self.design.get("entrance", "fade"), t - group["start"])
        if scale != 1.0:
            size = (max(1, round(picture.width * scale)), max(1, round(picture.height * scale)))
            picture = picture.resize(size, Image.BILINEAR)
        # Grow and shrink around the caption's middle, so a pop doesn't drift up or down.
        height = self.picture(group, said).height - self.caption.pad * 2   # the words, without the spare room
        words_top = {"top": group["edge"], "middle": group["edge"] - height / 2}.get(group["anchor"],
                                                                                   group["edge"] - height)
        top = words_top + height / 2 - picture.height / 2 + nudge
        lay_on(frame, np.asarray(picture), W / 2, top, alpha)
        return frame


# ---------------------------------------------------------------------------
# Making the video and the comparison sheet
# ---------------------------------------------------------------------------

def frames_in(video):
    reader = subprocess.Popen(["ffmpeg", "-v", "error", "-i", video, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                              stdout=subprocess.PIPE)
    size = W * H * 3
    while True:
        buf = reader.stdout.read(size)
        if len(buf) < size:
            break
        yield np.frombuffer(buf, np.uint8).reshape(H, W, 3).copy()
    reader.wait()


def find_face(video, chin=None, head_top=None):
    """Where the face is, for placing the captions. Given chin and head_top are used as
    they are; otherwise the face finder looks through the video."""
    if chin is not None or head_top is not None:
        return {"chin": chin if chin is not None else CHIN,
                "head_top": head_top if head_top is not None else HEAD_TOP}
    looks = face.faces(video)
    share = sum(1 for _, f in looks if f) / max(len(looks), 1)
    if share < face.FOUND_ENOUGH:
        print("No face found, so the captions go where a face usually is.")
        return {}
    return {"looks": looks}


def make_video(video, words, design, out, position="chin", chin=None, head_top=None):
    """position: "above", "chin" or "low". chin and head_top: where they are (0 to 1 down
    the screen), only when they've been measured by hand; normally the face finder works it out."""
    captioner = Captioner(words, design, position, **find_face(video, chin, head_top))
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    writer = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                               "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", video,
                               "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "medium",
                               "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "copy",
                               "-movflags", "+faststart", out], stdin=subprocess.PIPE)
    for n, frame in enumerate(frames_in(video)):
        writer.stdin.write(captioner.draw_on(frame, n / FPS).tobytes())
    writer.stdin.close()
    if writer.wait() != 0:
        raise SystemExit("Saving the captioned video didn't work.")
    print(f"Captions ({design['name']}): {len(captioner.groups)} captions. Saved {out}")


def still(video, t):
    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", video, "-frames:v", "1",
                        "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True)
    return np.frombuffer(r.stdout, np.uint8).reshape(H, W, 3).copy()


def make_preview(video, words, choices, out, chin=None, head_top=None):
    """One still from the video with each choice on it, side by side, labelled A, B, C...
    choices: (label, design, position) for each picture."""
    # A moment in the middle of a run of words, so every design has a few words to show.
    t = next((w["start"] + 0.3 for k, w in enumerate(words[2:], 2)
              if w["piece"] == words[k - 2]["piece"] and len(w["word"]) > 3), words[0]["start"] + 0.3)
    base = still(video, t)
    where = find_face(video, chin, head_top)
    tile_w, tile_h, label_h, gap = 360, 640, 70, 24
    across = min(4, len(choices))
    rows = (len(choices) + across - 1) // across
    sheet = Image.new("RGB", (across * (tile_w + gap) + gap, rows * (tile_h + label_h + gap) + gap), "#F4F0EC")
    label_font = load_font("Poppins", 30, "caption")
    draw = ImageDraw.Draw(sheet)
    for n, (label, design, position) in enumerate(choices):
        frame = Captioner(words, design, position, **where).draw_on(base.copy(), t)
        tile = Image.fromarray(frame).resize((tile_w, tile_h), Image.LANCZOS)
        x = gap + (n % across) * (tile_w + gap)
        y = gap + (n // across) * (tile_h + label_h + gap)
        sheet.paste(tile, (x, y))
        draw.text((x + tile_w / 2, y + tile_h + label_h / 2), f"{chr(65 + n)}  {label}",
                  font=label_font, fill=CHARCOAL, anchor="mm")
    sheet.save(out)
    print(f"Preview of {len(choices)} choices saved {out}")


def design_from(args):
    design = dict(DESIGNS[args.design])
    for field in ("font", "colour", "accent", "accent_text"):
        value = getattr(args, field)
        if value:
            design[field] = value
    return design


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video", help="the tidy video from talking_head.py")
    ap.add_argument("--work", required=True, help="the same working folder used for the cut")
    ap.add_argument("--out", help="where to save the captioned video")
    ap.add_argument("--design", choices=list(DESIGNS), default="pop")
    ap.add_argument("--preview", help="instead of a video, save a picture comparing designs")
    ap.add_argument("--designs", help="which designs to compare, e.g. pop,highlight (default: all)")
    ap.add_argument("--font", help="another font, e.g. \"Montserrat\"")
    ap.add_argument("--colour", help="the words' colour")
    ap.add_argument("--accent", help="the colour that marks the word being said")
    ap.add_argument("--accent-text", dest="accent_text", help="the word's colour inside the coloured box")
    ap.add_argument("--position", choices=list(POSITIONS), default="chin",
                    help="where the captions sit: above the head, under the chin, or lower down")
    ap.add_argument("--positions", action="store_true",
                    help="with --preview: compare the three positions (in the chosen --design) instead of designs")
    ap.add_argument("--chin", type=float, help="where the chin is, down the screen (0 to 1), "
                                               "if the face finder gets it wrong")
    ap.add_argument("--head-top", dest="head_top", type=float,
                    help="where the top of the head is, down the screen (0 to 1), if the face finder gets it wrong")
    args = ap.parse_args()
    words = load_words(args.work)
    where = {"chin": args.chin, "head_top": args.head_top}
    if args.preview and args.positions:
        design = design_from(args)
        choices = [(p["name"], design, key) for key, p in POSITIONS.items()]
        make_preview(args.video, words, choices, args.preview, **where)
    elif args.preview:
        keys = args.designs.split(",") if args.designs else list(DESIGNS)
        choices = [(DESIGNS[k]["name"], DESIGNS[k], args.position) for k in keys]
        make_preview(args.video, words, choices, args.preview, **where)
    elif args.out:
        make_video(args.video, words, design_from(args), args.out, position=args.position, **where)
    else:
        raise SystemExit("Say where to save it with --out, or ask for a --preview.")


if __name__ == "__main__":
    main()
