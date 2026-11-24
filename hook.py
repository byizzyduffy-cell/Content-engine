"""
Talking-head editor: the hook.

Frances's method: the hook is one block of text above the head, on screen for
the first 7 to 10 seconds, in the brand pack's headline font. Her three hook
styles (2026-10-10), "the three strongest":

    there   already on screen from the very first frame
    type    typed onto the screen letter by letter, with a soft typing sound
    pop     pops up with a little bounce and a pop

The rules every hook follows (the same as the pop-up words): centred, no outline
or shadow, white writing with the clinic's brand colour on the key word, short
balanced lines (about 15 letters each, three lines at most) so it stays big, and
a soft shade at the top of the screen so it reads on anything. No pop-up words
appear while the hook is showing.

Claude writes hook.json in the work folder for each video:

    {"text": "Why your bestie's treatment might not suit you", "accent": ["you"], "style": "type", "seconds": 8}

"lines" (optional) says how many lines the hook goes on, e.g. "lines": 2.

"place" (top, middle or lower: PLACES) can be in it too, but it usually comes from their look
(finish.py --hook-place).

The rules Claude follows for the words: a question or statement the viewer wants
answered (curiosity), never the same as the first sentence said out loud,
starts with a capital letter, the careful-claims rules. "accent": the word or
words in the brand colour (often the last). finish.py --hook puts it on.
"""

import tools  # noqa: F401  (first: emoji-safe output on Windows)
import json
import os
import re
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import captions  # noqa: E402
import captions as captions_module  # noqa: E402  (Hook takes a "captions" argument of its own)
import face  # noqa: E402
import notes  # noqa: E402
import packs  # noqa: E402
from text_reel import Writer  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
W, H = captions.W, captions.H

STYLES = {
    "there": {"name": "Already there", "say": "Make my hooks already there",
              "about": "Your hook is on the screen from the very first frame, so people read it straight away.",
              "good_for": "Every video. The strongest way to stop the scroll."},
    "type": {"name": "Typed in", "say": "Make my hooks type in",
             "about": "Your hook types itself onto the screen letter by letter, with a soft typing sound.",
             "good_for": "Questions, secrets and 'did you know' hooks."},
    "pop": {"name": "Pops up", "say": "Make my hooks pop up",
            "about": "Your hook pops onto the screen with a little bounce and a pop.",
            "good_for": "Bold statements and lively videos."},
}
DEFAULT_STYLE = "there"

# Where the hook sits (Frances, 2026-10-13: "top of the reel, middle of the reel, lower down"). It never
# covers the face or the captions: if the spot they picked is taken, it goes to the nearest clear space
# (her choice: the captions run from the start). On a head-and-shoulders video the middle of the screen
# is the face, so "in the middle" means the middle of the space under the face.
PLACES = {
    "top": {"name": "At the top", "say": "Put my hooks at the top",
            "about": "Your hook sits at the top of the screen, above your head.",
            "good_for": "Most videos. It's the first thing people read."},
    "middle": {"name": "In the middle", "say": "Put my hooks in the middle",
               "about": "Your hook sits in the middle, in the space just under your face. Never over it.",
               "good_for": "Videos filmed with room around you."},
    "lower": {"name": "Lower down", "say": "Put my hooks lower down",
              "about": "Your hook sits lower down, just above where Instagram puts its own caption.",
              "good_for": "Videos filmed from further back, with more of you in shot."},
}
DEFAULT_PLACE = "top"
CLEAR = 30            # space kept between the hook and the captions

SECONDS = 8           # how long the hook stays (Frances: 7 to 10 seconds)
SIZE = 1.15           # the hook is a little bigger than a pop-up's headline line
LINE_CHARACTERS = 15  # aim for lines about this long...
MOST_LINES = 3        # ...and no more than this many
TOP = notes.TOP
TYPE_PER_LETTER = 0.045
TYPE_LONGEST = 1.6
POP_TIME = 0.25
FADE_OUT = 0.4
UNDER_HEAD = 20


def clear_spaces(blocked, low, high):
    """The stretches of the screen (top, bottom) between low and high that nothing blocked covers."""
    spaces = [(low, high)]
    for b0, b1 in blocked:
        kept = []
        for s0, s1 in spaces:
            if b1 <= s0 or b0 >= s1:
                kept.append((s0, s1))
                continue
            if b0 > s0:
                kept.append((s0, b0))
            if b1 < s1:
                kept.append((b1, s1))
        spaces = kept
    return spaces


def balanced_lines(text, lines_wanted):
    """Split the words into this many lines, as evenly as possible."""
    words = text.split()
    if lines_wanted <= 1 or len(words) <= 1:
        return [words]
    best = None
    def splits(ws, n):
        if n == 1:
            yield [ws]
            return
        for k in range(1, len(ws) - n + 2):
            for rest in splits(ws[k:], n - 1):
                yield [ws[:k]] + rest
    for option in splits(words, min(lines_wanted, len(words))):
        lengths = [len(" ".join(line)) for line in option]
        score = max(lengths) - min(lengths)
        if best is None or score < best[0]:
            best = (score, option)
    return best[1]


SIDE = 60             # the hook keeps at least this far from each side of the screen


def hook_picture(text, font, accent_words, accent_colour, scale=1.0, lines_wanted=None):
    """The hook as balanced, centred lines: white, with the accent words in the brand colour.
    Returns the picture and, for typing it in, how far each letter reaches (in order).
    lines_wanted: how many lines, when hook.json says ("lines": 2; Frances, 2026-10-20: "the hook in
    2 lines not 3"); longer lines are written a little smaller so they still fit across the screen."""
    family, size, capitals = font
    writer = Writer(round(size * SIZE * scale), family, "heading", capitals=capitals)
    lines_wanted = lines_wanted or min(MOST_LINES, max(1, round(len(text) / LINE_CHARACTERS)))
    lines = balanced_lines(text, lines_wanted)
    while max(writer.line_width(line) for line in lines) > W - SIDE * 2 and writer.size > 30:
        writer = Writer(round(writer.size * 0.95), family, "heading", capitals=capitals)
    accents = {re.sub(r"\W", "", w).lower() for w in accent_words}
    line_height = writer.size * 1.18
    room = round(writer.size * 0.35)
    height = round(line_height * len(lines)) + room * 2
    canvas = Image.new("RGBA", (W, height))
    draw_y = room
    reach = []   # (line number, x where each word ends) in reading order
    space = writer.measure(" ")
    for n, line in enumerate(lines):
        x = (W - writer.line_width(line)) / 2
        baseline = draw_y + (line_height + writer.size * 0.7) / 2
        for word in line:
            colour = accent_colour if re.sub(r"\W", "", word).lower() in accents else notes.LIGHT
            end = writer.draw_word(canvas, x, baseline, word, colour)
            reach.append((n, x, end, draw_y, draw_y + line_height))
            x = end + space
        draw_y += line_height
    return np.asarray(canvas), reach, room


class Hook:
    """Draws the hook from hook.json onto the first seconds of the video."""

    def __init__(self, work, name="hook.json", faces=None, pack=packs.DEFAULT, accent=None, style=None,
                 fonts=None, below=False, place=None, captions=None, lines=None):
        """below: the captions are above the head, so the hook goes below the face (Frances's rule).
        place: where they want it (PLACES). captions: the Captioner, so the hook keeps clear of them.
        lines: how many lines their hooks go on (their look's Extras: Frances's are 2), unless hook.json says."""
        with open(os.path.join(work, name), encoding="utf-8") as f:
            wanted = json.load(f)
        self.text = wanted["text"]
        self.style = style or wanted.get("style", DEFAULT_STYLE)
        self.seconds = float(wanted.get("seconds", SECONDS))
        if lines and not wanted.get("lines"):
            wanted["lines"] = lines
        writing, _, _ = notes.brand_colours(accent or notes.FRANCES_YELLOW)
        font = (fonts or packs.PACKS[pack])["headline"]
        place = place or wanted.get("place", DEFAULT_PLACE)
        found = [f for t, f in (faces or []) if f and -0.25 <= t <= self.seconds + 0.25]
        chin, head_top = face.head_and_chin(found) if found else (captions_module.CHIN, captions_module.HEAD_TOP)
        # Nothing over the face (or anywhere above it, when the captions are above the head), nor the captions.
        blocked = [(TOP if below else head_top * H - notes.UNDER_HEAD, chin * H + notes.UNDER_CHIN)]
        band = captions.band(0.0, self.seconds) if captions else None
        if band:
            blocked.append((band[0] - CLEAR, band[1] + CLEAR))
        best = None
        for s0, s1 in clear_spaces(blocked, TOP, notes.BELOW_LIMIT):
            scale = 1.0
            while True:
                picture, reach, room = hook_picture(self.text, font, wanted.get("accent", []), writing, scale, wanted.get("lines"))
                height = picture.shape[0] - room
                if height <= s1 - s0 or scale < 0.7:
                    break
                scale *= 0.93
            if height > s1 - s0:
                continue
            want = {"top": TOP, "lower": notes.BELOW_LIMIT - height,
                    "middle": (chin * H + notes.UNDER_CHIN + notes.BELOW_LIMIT - height) / 2}[place]
            at = min(max(want, s0), s1 - height)
            score = (abs(at - want), -scale)
            if best is None or score < best[0]:
                best = (score, picture, reach, room, at)
        if best:
            _, picture, reach, room, top = best
        else:       # no clear space big enough: above the head (or below the face), a little smaller
            top, lowest = notes.zone(below, faces, 0.0, self.seconds)
            scale = 1.0
            while True:
                picture, reach, room = hook_picture(self.text, font, wanted.get("accent", []), writing, scale, wanted.get("lines"))
                if top + picture.shape[0] - room <= lowest or scale < 0.7:
                    break
                scale *= 0.93
        self.picture, self.reach, self.room = picture, reach, room
        self.top = top
        self.y = top - room / 2
        self.bottom = self.y + picture.shape[0]
        self.end = self.seconds
        letters = len(self.text.replace(" ", ""))
        self.type_time = min(TYPE_LONGEST, letters * TYPE_PER_LETTER)
        self.cache = {}
        sound = {"there": None, "type": "typing", "pop": "pop"}[self.style]
        self.sounds = [(0.15 if self.style == "pop" else 0.0, os.path.join(HERE, "sounds", f"{sound}.wav"), 0.45)] \
            if sound else []

    def typed(self, amount):
        """The hook with `amount` (0 to 1) of its words typed, word by word, letter by letter."""
        key = round(amount * 200)
        if key in self.cache:
            return self.cache[key]
        out = np.zeros_like(self.picture)
        total = sum(end - start for _, start, end, _, _ in self.reach)
        left = amount * total
        last_line = self.reach[-1][0]
        for line, start, end, top, bottom in self.reach:
            width = end - start
            show = min(width, max(0.0, left))
            left -= width
            if show <= 0:
                break
            # Only this line's own band (plus the spare room above the first and below the last).
            y0 = int(max(0, top - (self.room if line == 0 else 0)))
            y1 = int(min(out.shape[0], bottom + (self.room if line == last_line else 0)))
            x0, x1 = int(start) - 4, int(start + show) + (8 if show >= width else 0)
            out[y0:y1, x0:x1] = self.picture[y0:y1, x0:x1]
        self.cache[key] = out
        return out

    def draw_on(self, frame, t):
        if t >= self.end:
            return frame
        alpha = min(1.0, (self.end - t) / FADE_OUT)
        picture, scale = self.picture, 1.0
        if self.style == "type":
            if t < self.type_time:
                picture = self.typed(t / self.type_time)
        elif self.style == "pop":
            since = t - 0.15
            if since < 0:
                picture = None
            else:
                p = min(1.0, since / POP_TIME)
                scale = 0.7 + 0.3 * captions.ease_out_back(p)
                alpha *= min(1.0, since / 0.06)
        notes.shade_band(frame, self.top, self.bottom - self.room, alpha)
        if picture is None:
            return frame
        y = self.y
        if abs(scale - 1) > 1e-3:
            img = Image.fromarray(picture, "RGBA")
            img = img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))), Image.BILINEAR)
            y += (picture.shape[0] - img.height) / 2
            picture = np.asarray(img)
        captions.lay_on(frame, picture, W / 2, y, alpha)
        return frame
