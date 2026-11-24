"""
Talking-head editor: pop-up words.

Frances's rules (2026-10-10, all of them, every time, for every style; captions
are separate and signed off, so this never changes them):

1. Anything that pops up on its own goes in the centre of the screen. Anything
   that follows it goes directly underneath. Never off centre.
2. No outline or shadow on the writing.
3. Colour, depth and life, like the reels she likes: two fonts that go together
   (a main font and a handwriting) and the clinic's brand colour, mixed so no two
   pop-ups look the same. But lines on the screen at the same time share one font
   (Frances, 2026-10-10): each pop-up uses one font; the next can use the other. Main lines arrive with a little movement; handwritten
   lines write themselves on with a soft pen sound.
4. Once or twice a video, a pop-up with a background in the brand colour at a
   key moment.
5. About two and a half seconds after the last line, the whole pop-up fades.
7. Pop-ups don't all come up the same way (Frances, 2026-10-10): the student's
   pop-up style leads, every other pop-up, and the other styles take turns in
   between (a speech bubble, then one written on, then a speech bubble, then one
   typed...). Never the same twice in a row. The fonts stay the same throughout.
   Claude can name a pop-up's style in notes.json ("style": "messages").
6. A soft shade darkens the top of the screen while a pop-up is showing, so the
   words read on anything (a ring light, a window) without an outline.
8. Every line of a pop-up stays on one line (Frances, 2026-10-20: "make all the
   words go in one line. Make that a rule"). Never a word left over on a second
   line: a long line is written smaller instead.

Those rules are the structure every clinic shares. What changes per clinic
(Frances: "we don't want everyone's talking heads to be exactly the same"):
the brand colour (from their profile) and the brand pack (packs.py: three
fonts that go together; the pop-ups use its headline font and its pop-up
handwriting). Sounds are picked by the content, not the pack: each kind of
line has a quiet default, and Claude can give any line its own "sound" (a
cha-ching on money...). The background shape for the key moment changes from
video to video (or Claude names one: "background": "tape").

Claude writes notes.json in the work folder for each video. Each entry is one
pop-up: one or more lines, each arriving at its own word (word numbers from
transcript.txt), stacked down the middle in the order they're said:

    [
     {"lines": [{"text": "(we've all done it)", "word": 9, "font": "hand", "colour": "accent"}]},
     {"lines": [{"text": "same concerns", "word": 60, "font": "hand"},
                {"text": "same skin", "word": 65, "font": "hand"},
                {"text": "different plan", "word": 70, "font": "main", "colour": "accent"}]},
     {"lines": [{"text": "consult first, always", "word": 95}], "background": true}
    ]

font: "main" (the pack's headline font) or "hand" (its pop-up handwriting). colour:
"light" (white, the default) or "accent" (the brand colour). The mix is how
the pop-ups stay engaging: Claude varies it from pop-up to pop-up (a main-font
statement, a handwritten aside in colour, a list that ends on a coloured
punchline...) and never uses the same mix twice in a row. Within one pop-up,
every line uses the first line's font; only the colour changes. Words: short (2 to 5 words a line), in the clinic's voice, never the
whole sentence repeated, emoji rarely, the careful-claims rules.

All fonts are OFL or Apache (see fonts/licences). finish.py --notes puts them on.
"""

import tools  # noqa: F401  (first: emoji-safe output on Windows)
import json
import os
import sys
from dataclasses import replace

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import captions  # noqa: E402
import face  # noqa: E402
import packs  # noqa: E402
import popups  # noqa: E402
from text_reel import Look, Writer, luminance, mix, popup_picture, wrap  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
W, H = captions.W, captions.H

LIGHT, INK = "#FFFFFF", captions.CHARCOAL
FRANCES_YELLOW = "#FFF3B0"    # Frances's own accent (a very light yellow), and the default

# How the pop-up words come up (Frances, 2026-10-10: "speech bubbles... a message coming
# up on the screen... just typed"). Students pick one; every one follows her rules.
# The student's pick leads; the others take turns in between (see Notes.turn).
POPUP_STYLES = {
    "notes": {"name": "Handwritten notes", "say": "Make my pop-ups handwritten notes",
              "about": "Headline lines rise into place and handwritten lines write themselves on, "
                       "with one special moment on a background.",
              "good_for": "Every brand. Frances's own style."},
    "typed": {"name": "Typed", "say": "Make my pop-ups typed",
              "about": "Every line types itself onto the screen letter by letter, with a soft typing sound.",
              "good_for": "Tips, facts and 'did you know' moments."},
    "bubbles": {"name": "Speech bubbles", "say": "Put my pop-ups in speech bubbles",
                "about": "Each line pops up in its own speech bubble, one under the other.",
                "good_for": "Chatty videos, questions and what clients often say."},
    "messages": {"name": "Text messages", "say": "Make my pop-ups text messages",
                 "about": "Each line arrives like a text message: typing dots first, then the message slides "
                          "in with a message sound.",
                 "good_for": "Client questions, DMs and storytelling."},
}
DEFAULT_POPUP_STYLE = "notes"

BACKGROUNDS = ["tape", "box", "bubble", "paper", "note", "outline"]   # shapes for the key moment
SOUNDS = {"main": "soft-pop", "hand": "scribble",   # quiet defaults; Claude can pick per line
          "typed": "typing", "bubble-line": "bubble", "message": "message",
          "tape": "tape", "box": "pop", "bubble": "bubble", "paper": "tape", "note": "soft-pop", "outline": "click"}

TOP = 300             # the top of every pop-up: they all start on the same line, under Instagram's bar
LINE_GAP = -6         # space between a pop-up's lines (each line has a little room of its own)
WIDEST = 900
STAYS = 2.5           # how long a pop-up stays after its last line arrives
FADE_OUT = 0.3
RISE, RISE_TIME = 18, 0.35    # main lines rise this far into place, this fast
POP_TIME = 0.22               # or pop in this fast
FADE_TIME = 0.45              # or fade in this gently
WRITE_PER_LETTER = 0.03       # handwritten lines write on this fast...
WRITE_SHORTEST, WRITE_LONGEST = 0.35, 0.8   # ...within these limits
SHAPE_FIRST = 0.12    # a background appears this long before its words
SHADE = 0.42          # how much the soft shade darkens the very top of the screen...
SHADE_IN = 0.3        # ...fading in and out this fast
UNDER_HEAD = 20       # a pop-up never comes lower than this above the top of the head
UNDER_CHIN = 50       # Below the face (when the captions are above the head): pop-ups start this far under the chin...
BELOW_LIMIT = 1620    # ...and end above this line, where Instagram's name and caption start
SMALLEST = 0.75       # a tall pop-up is written smaller (down to this) so it stays above the head
ONE_LINE_SMALLEST = 0.45   # a long line is written smaller (down to this) so it stays on one line
LIGHT_ENOUGH = 0.45   # brand colours darker than this are lightened for writing on the video
TYPE_PER_LETTER = 0.045       # Typed: seconds per letter...
TYPE_LONGEST = 1.2            # ...but never longer than this for a line
BUBBLE_TEXT = 0.95            # Speech bubbles and text messages: writing size, compared with plain lines
BUBBLE_SMALLEST = 62          # ...but never smaller than this (fonts made for spaced capitals run small)
MESSAGE_GREY = "#EFEFF1"      # Text messages: the usual message colour (brand colour for accent lines)
DOTS_FIRST = 0.5              # Text messages: the typing dots show for this long before each message
SOUND_LEVELS = {"typing": 0.3, "message": 0.45}


CAPTION_GAP = 40      # pixels between the captions and pop-ups that sit below them


def zone(below, faces, start, end):
    """Where a pop-up (or the hook) can go: (top, lowest bottom) in pixels. Frances's rule: if the
    captions are above the head, everything else moves below the face, onto the body."""
    found = [f for t, f in (faces or []) if f and start - 0.25 <= t <= end + 0.25]
    chin, head_top = face.head_and_chin(found) if found else (captions.CHIN, captions.HEAD_TOP)
    if below:
        return chin * H + UNDER_CHIN, BELOW_LIMIT
    return TOP, head_top * H - UNDER_HEAD


def shade_band(frame, top, bottom, strength):
    """Softly darken the screen behind words. At the top of the screen (the usual place) it's
    darkest at the very top and fades out just below the words; lower down (below the face) it's a
    band that fades in above the words and out below them."""
    if strength <= 0:
        return
    edge = 140
    hi = int(min(H, bottom + edge))
    if top <= TOP + 1:
        lo = 0
        rows = np.arange(lo, hi, dtype=np.float32)
        weight = np.clip((hi - rows) / max(1.0, hi - top), 0, 1) ** 1.4
    else:
        lo = int(max(0, top - edge))
        rows = np.arange(lo, hi, dtype=np.float32)
        weight = np.clip(np.minimum((rows - (top - edge)) / edge, (hi - rows) / edge), 0, 1) ** 1.4
    keep = 1 - strength * SHADE * weight
    frame[lo:hi] = (frame[lo:hi].astype(np.float32) * keep[:, None, None]).astype(np.uint8)


def word_times(words):
    return {w["i"]: (w["start"], w["end"]) for w in words}


# A clinic's whole palette, when it gives one (Frances, 2026-10-20: only her own colours, nothing else):
# set by use_palette(), and then every colour on the hook and pop-ups comes from it.
OWN_COLOURS = None


def use_palette(light, accent, background):
    """Only these colours: light for the writing (and the boxes and message bubbles), accent for the
    coloured lines and the hook's key word, exactly as given, and background for the key moment, with
    light (or charcoal, on a light background) writing on it."""
    global LIGHT, MESSAGE_GREY, OWN_COLOURS, INK
    LIGHT = MESSAGE_GREY = light
    if luminance(background) < 0.4:
        INK = background            # their own dark colour for writing on the light boxes and bubbles too
    OWN_COLOURS = (accent, background, INK if luminance(background) >= 0.4 else light)


def brand_colours(accent):
    """From one brand colour: the colour for coloured writing on the video (lightened if the
    brand colour is too dark to read on the shade), the background colour for the key
    moment, and the writing on that background (charcoal on light colours, white on dark).
    With a clinic's own palette (use_palette), its colours exactly."""
    if OWN_COLOURS:
        return OWN_COLOURS
    writing = accent
    for step in range(11):
        writing = mix(accent, "#FFFFFF", step / 10)
        if luminance(writing) >= LIGHT_ENOUGH:
            break
    on_background = INK if luminance(accent) >= 0.4 else LIGHT
    return writing, accent, on_background


def line_picture(text, font, colour, scale=1.0):
    """One line of words, centred in its own picture, with no outline or shadow.
    font: (font name, size, capitals)."""
    family, size, capitals = font
    writer = Writer(round(size * scale), family, "heading", capitals=capitals)
    lines = wrap(writer, text, WIDEST)
    room = round(writer.size * 0.3)   # headroom, so tall letters are never clipped
    height = round(writer.size * 1.2 * len(lines)) + room * 2
    canvas = Image.new("RGBA", (WIDEST + 40, height))
    writer.draw_lines(canvas, lines, 20, 20 + WIDEST, room, colour)
    left, _, right, _ = canvas.getbbox() or (0, 0, canvas.width, 0)
    pad = 10
    return np.asarray(canvas.crop((max(0, left - pad), 0, min(canvas.width, right + pad), height)))


def background_pictures(text, font, shape, fill, ink, scale=1.0):
    """A line of handwriting on a background in the brand colour, and the background
    alone (to write the words onto)."""
    family, size, _ = font
    look = Look(popup_style=shape, caption_font=family, box_colour=fill,
                box_text_colour=ink, text_colour=LIGHT)
    size = round(size * scale * 1.1)
    full = popup_picture(text, look, WIDEST, size)
    blank = popup_picture(text, replace(look, popup_words=False), WIDEST, size)
    return np.asarray(full), np.asarray(blank)


def message_picture(text, font, fill, ink, scale=1.0):
    """A line as a text message: a rounded bubble with a little tail, the words inside."""
    from PIL import ImageDraw, ImageFilter
    family, size, capitals = font
    writer = Writer(round(max(size, BUBBLE_SMALLEST) * scale * BUBBLE_TEXT), family, "heading", capitals=capitals)
    lines = wrap(writer, text, 720)
    pad_x, pad_y, margin = 36, 22, 20
    line_height = writer.size * 1.25
    width = max(writer.line_width(line) for line in lines if line) + pad_x * 2
    height = line_height * len(lines) + pad_y * 2
    canvas = Image.new("RGBA", (round(width + margin * 2), round(height + margin * 2 + 12)))
    x0, y0, x1, y1 = margin, margin, margin + width, margin + height
    shape = Image.new("RGBA", canvas.size)
    draw = ImageDraw.Draw(shape)
    draw.rounded_rectangle((x0, y0, x1, y1), radius=min(height / 2, 44), fill=fill)
    draw.polygon([(x1 - 34, y1 - 18), (x1 + 8, y1 + 10), (x1 - 8, y1 - 8)], fill=fill)   # the tail
    shadow = Image.new("RGBA", canvas.size)
    shadow.paste((0, 0, 0, 55), mask=shape.getchannel("A"))
    canvas.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(8)), (0, 4))
    canvas.alpha_composite(shape)
    writer.draw_lines(canvas, lines, x0, x1, y0 + pad_y, ink, spacing=1.25)
    return np.asarray(canvas)


def dots_pictures():
    """The 'someone is typing' bubble, three times: each with a different dot darker."""
    from PIL import ImageDraw
    out = []
    for lit in range(3):
        canvas = Image.new("RGBA", (150, 86))
        draw = ImageDraw.Draw(canvas)
        draw.rounded_rectangle((12, 10, 138, 74), radius=32, fill=MESSAGE_GREY)
        for k in range(3):
            shade = 120 if k == lit else 185
            cx = 48 + k * 27
            draw.ellipse((cx - 9, 33, cx + 9, 51), fill=(shade, shade, shade + 4, 255))
        out.append(np.asarray(canvas))
    return out


class Notes:
    """Draws the pop-ups from notes.json onto each frame, and lists their sounds.
    pack: the clinic's brand pack (packs.PACKS); accent: its brand colour; seed: makes each
    video's background shape different; not_before: no pop-ups while the hook is showing."""

    def __init__(self, work, words, name="notes.json", faces=None, still=None, seed="",
                 pack=packs.DEFAULT, accent=None, not_before=0.0, style=DEFAULT_POPUP_STYLE, fonts=None,
                 below=False, captions=None, size=1.0):
        """style: how the pop-up words come up (POPUP_STYLES). fonts: a pack with the student's
        own font picks (packs.own_pack), instead of one of the ready-made packs. captions: the
        captions (captions.Captioner), so pop-ups below the face sit under them, never on them.
        size: smaller (or bigger) pop-ups, e.g. 0.85 (Frances, 2026-10-20: "a little bit smaller")."""
        with open(os.path.join(work, name), encoding="utf-8") as f:
            wanted = json.load(f)
        self.style = style
        self.dots = dots_pictures()
        chosen = fonts or packs.PACKS[pack]
        self.fonts = {"main": chosen["headline"], "hand": chosen["popup"]}
        self.shape = BACKGROUNDS[sum(map(ord, seed)) % len(BACKGROUNDS)]
        self.writing, self.fill, self.on_fill = brand_colours(accent or FRANCES_YELLOW)
        times = word_times(words)
        self.popups, self.sounds = [], []
        for entry in wanted:
            lines = [ln for ln in entry["lines"] if ln["word"] in times]
            if not lines:
                continue
            starts = [times[ln["word"]][0] for ln in lines]
            if starts[0] < not_before:
                print(f"The pop-up \"{lines[0]['text']}\" arrives while the hook is showing, so it's left out.")
                continue
            end = starts[-1] + STAYS
            top, lowest = zone(below, faces, starts[0], end)
            reach = captions.band(starts[0], end) if (below and captions) else None
            if reach and reach[1] > top - UNDER_CHIN and reach[0] < lowest:
                top = max(top, reach[1] + CAPTION_GAP)      # under the captions, in the space on the body
            pop_style = entry.get("style") or self.turn(len(self.popups))
            scale = size
            while True:
                pictures = self.draw(entry, lines, scale, pop_style)
                height = sum(p[0].shape[0] for p in pictures) + LINE_GAP * (len(pictures) - 1)
                # Frances's rule (2026-10-20): every line of a pop-up stays on one line, never with a word left
                # over on a second line; if it's too long, the whole pop-up is written smaller instead.
                one_line = self.one_line_each(entry, lines, pictures, scale, pop_style)
                if (top + height <= lowest or scale <= SMALLEST * size) and (one_line or scale <= ONE_LINE_SMALLEST):
                    break
                scale *= 0.92
            y, items = top, []
            for ln, start, (full, blank, kind) in zip(lines, starts, pictures):
                arrive = self.arrival(kind, pop_style)
                if arrive == "type":
                    write = min(TYPE_LONGEST, max(0.3, len(ln["text"]) * TYPE_PER_LETTER))
                else:
                    write = min(WRITE_LONGEST, max(WRITE_SHORTEST, len(ln["text"]) * WRITE_PER_LETTER))
                items.append({"start": start, "full": full, "blank": blank, "kind": kind, "y": y,
                              "arrive": arrive, "letters": max(1, len(ln["text"])),
                              "bands": popups.text_bands(full, blank, 1) if arrive in ("write", "type") else None,
                              "write": write, "cache": {}})
                sound = ln.get("sound") or SOUNDS[self.shape_of(entry) if kind == "background" else kind]
                if sound and sound != "none":
                    self.sounds.append((start, os.path.join(HERE, "sounds", f"{sound}.wav"),
                                        SOUND_LEVELS.get(sound, popups.SOUND_LEVEL)))
                y += full.shape[0] + LINE_GAP
            first_shows = starts[0] - (DOTS_FIRST if pop_style == "messages" else 0.0)
            self.popups.append({"start": first_shows, "end": end, "items": items, "top": top, "bottom": y})
        # A pop-up always goes before the next one arrives.
        for here, following in zip(self.popups, self.popups[1:]):
            here["end"] = min(here["end"], following["start"] - 0.15)

    def turn(self, n):
        """Frances's rule: pop-ups don't all come up the same way. The student's style leads
        (every other pop-up), and the other styles take turns in between, so no two pop-ups in
        a row match. The fonts never change."""
        if n % 2 == 0:
            return self.style
        others = [k for k in POPUP_STYLES if k != self.style]
        return others[(n // 2) % len(others)]

    def shape_of(self, entry):
        named = entry.get("background")
        return named if isinstance(named, str) else self.shape

    def arrival(self, kind, style):
        """How a line comes on, for this pop-up style and kind of line."""
        if style == "typed":
            return "type"
        if style == "bubbles":
            return "pop"
        if style == "messages":
            return "message"
        return "rise" if kind == "main" else "write"

    def one_line_each(self, entry, lines, pictures, scale, style):
        """Whether every line came out as a single line: each picture no taller than the same line drawn
        with just one short word."""
        short = self.draw(entry, [dict(ln, text="Hg") for ln in lines], scale, style)
        return all(p[0].shape[0] <= r[0].shape[0] * 1.3 for p, r in zip(pictures, short))

    def draw(self, entry, lines, scale, style):
        """(picture, blank picture, kind) for each line of a pop-up. Frances's rule: lines on the
        screen together share one font, so the whole pop-up takes its first line's font."""
        out = []
        kind = "hand" if lines[0].get("font", "hand") == "hand" else "main"   # "serif" or "bold" mean main
        for ln in lines:
            accent = entry.get("background") or ln.get("colour") == "accent"
            font = self.fonts[kind]
            if style == "bubbles":
                look = Look(popup_style="bubble", caption_font=font[0],
                            box_colour=self.fill if accent else LIGHT, box_text_colour=self.on_fill if accent else INK)
                full = np.asarray(popup_picture(ln["text"], look, WIDEST,
                                                round(max(font[1], BUBBLE_SMALLEST) * scale * BUBBLE_TEXT)))
                out.append((full, np.zeros_like(full), "bubble-line"))
                continue
            if style == "messages":
                full = message_picture(ln["text"], font, self.fill if accent else MESSAGE_GREY,
                                       self.on_fill if accent else INK, scale)
                out.append((full, np.zeros_like(full), "message"))
                continue
            if style == "typed" and not entry.get("background"):
                colour = self.writing if ln.get("colour") == "accent" else LIGHT
                full = line_picture(ln["text"], font, colour, scale)
                out.append((full, np.zeros_like(full), "typed"))
                continue
            if entry.get("background"):
                full, blank = background_pictures(ln["text"], self.fonts["hand"], self.shape_of(entry),
                                                  self.fill, self.on_fill, scale)
                out.append((full, blank, "background"))
                continue
            colour = self.writing if ln.get("colour") == "accent" else LIGHT
            full = line_picture(ln["text"], self.fonts[kind], colour, scale)
            out.append((full, np.zeros_like(full), kind))
        return out

    def draw_on(self, frame, t):
        for pop in self.popups:
            if not pop["start"] <= t < pop["end"]:
                continue
            fade = min(1.0, (pop["end"] - t) / FADE_OUT)
            shade_band(frame, pop["top"], pop["bottom"], min(1.0, (t - pop["start"]) / SHADE_IN) * fade)
            for item in pop["items"]:
                since = t - item["start"]
                arrive = item["arrive"]
                if since < 0:
                    if arrive == "message" and since >= -DOTS_FIRST:   # someone is typing...
                        dots = self.dots[int((since + DOTS_FIRST) / 0.12) % 3]
                        captions.lay_on(frame, dots, W / 2, item["y"] + (item["full"].shape[0] - dots.shape[0]) / 2,
                                        fade * min(1.0, (since + DOTS_FIRST) / 0.08))
                    continue
                picture, alpha, rise = item["full"], fade, 0.0
                if arrive == "message":
                    p = min(1.0, since / 0.22)
                    alpha *= p
                    rise = 26 * (1 - p) ** 3
                elif arrive == "type":
                    progress = since / item["write"]
                    if progress < 1:
                        amount = int(progress * item["letters"]) / item["letters"]
                        if amount not in item["cache"]:
                            item["cache"][amount] = popups.revealed(item["full"], item["blank"],
                                                                    item["bands"], amount)
                        picture = item["cache"][amount]
                    if item["kind"] == "background":
                        alpha *= min(1.0, since / SHAPE_FIRST)
                elif arrive == "rise":
                    p = min(1.0, since / RISE_TIME)
                    alpha *= p
                    rise = RISE * (1 - p) ** 3
                elif arrive == "fade":
                    alpha *= min(1.0, since / FADE_TIME)
                elif arrive == "pop":
                    p = min(1.0, since / POP_TIME)
                    alpha *= min(1.0, since / 0.06)
                    scale = 0.7 + 0.3 * captions.ease_out_back(p)
                    if abs(scale - 1) > 1e-3:
                        img = Image.fromarray(picture, "RGBA")
                        picture = np.asarray(img.resize((max(1, round(img.width * scale)),
                                                         max(1, round(img.height * scale))), Image.BILINEAR))
                        rise = (item["full"].shape[0] - picture.shape[0]) / 2
                else:   # written on
                    first = SHAPE_FIRST if item["kind"] == "background" else 0.0
                    if first:
                        alpha *= min(1.0, since / first)
                    progress = (since - first) / item["write"]
                    if progress < 1:
                        amount = round((1 - (1 - max(0.0, progress)) ** 2) * 60) / 60
                        if amount not in item["cache"]:
                            item["cache"][amount] = popups.revealed(item["full"], item["blank"],
                                                                    item["bands"], amount)
                        picture = item["cache"][amount]
                captions.lay_on(frame, picture, W / 2, item["y"] + rise, alpha)
        return frame
