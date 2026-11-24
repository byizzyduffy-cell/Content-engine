"""
Talking-head editor: word pop-ups.

Little headlines at the top of the screen that say what's being said in a fresh
way (same meaning, different words), so there's always something new to look
at. They sit between Instagram's top bar and the head, and never cover the face
(the face finder checks). Each one leans a little (alternating left and right),
stays a few seconds and goes.

Every pop-up has two choices, picked in the Talking Head Lookbook:
    In a finished reel the pop-ups follow a style pack (packs.py): one font all the way
    through and two pop-up styles, a main one and an accent one every third pop-up. The
    choices below are the ingredients the packs are made from (and what a student can
    pick one by one):
    look      what it looks like (POPUP_DESIGNS): soft box, speech bubble, ripped paper...
    movement  how it arrives (MOVES): pops on, typed on, written on, slides in, fades in
    writing   an optional extra (POPUP_FONTS): typewriter, baby writing, marker pen...
              Each look comes with matching writing, typed-on pop-ups use a typewriter
              and written-on ones handwriting, unless the student picks their own.

Claude writes the words for each video in popups.json, in the work folder:

    [{"word": 51, "text": "Same look, different skin 👭"}, ...]

"word" is the word number from transcript.txt where the pop-up arrives. A pop-up
can also have its own "look", "move" and "font", to mix them within one video. The rules
Claude follows for the words: 2 to 6 words, the same meaning as what's being
said but never the same words, an emoji at the end, the careful-claims rules (no
promises or results), one every 4 to 5 seconds, and the call to action keeps its
keyword (e.g. SKIN).

The looks come from the reel maker (text_reel.py), so talking heads and b-roll
reels share one family of pop-ups. finish.py puts them on the video.
"""

import json
import os
import sys
from dataclasses import replace

import numpy as np
from PIL import Image, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import captions  # noqa: E402
import face  # noqa: E402
import packs  # noqa: E402
from text_reel import Look, Writer, popup_picture, wrap  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
W, H = captions.W, captions.H

STAYS = 2.8           # how long a pop-up stays once it's fully on (seconds)
SHORTEST = 1.2        # shortest it stays, even when the next one is close
GAP = 0.3             # breathing space before the next pop-up arrives
ENTER = 0.22          # how long the pop-in takes
LEAVE = 0.15          # how long the pop-away takes
LETTER = 0.045        # Typed on: seconds per letter...
LONGEST_TYPING = 1.6  # ...but never longer than this for the whole pop-up
SHAPE_FIRST = 0.12    # Typed and written on: the box or bubble appears this long before the words
TILT = 3              # how far each pop-up leans (degrees), alternating left and right
WIDEST = 840          # pop-ups wrap onto two lines beyond this width
UNDER_HEAD = 30       # gap between the pop-up and the top of the head
OFF_FACE = 20         # never closer than this to the face itself (over the hair is fine)
SOUND_LEVEL = 0.5     # how loud the pop-up sounds are, under the voice
GLOW = 0.6            # how dark the glow is behind words that sit straight on the video
FEATHER = 10          # Typed and written on: the soft edge where the words are appearing (pixels)

BEIGE, CHARCOAL, WHITE = captions.BEIGE, captions.CHARCOAL, captions.WHITE
PAPER = "#FBF8F2"

POPUP_DESIGNS = {
    "box": {"name": "Soft box", "style": "box", "font": "Poppins", "size": 50,
            "box": BEIGE, "ink": CHARCOAL, "sound": "pop",
            "about": "Each pop-up sits on a soft box in your brand colour.",
            "good_for": "Every brand. Clean, calm and easy to read."},
    "bubble": {"name": "Speech bubble", "style": "bubble", "font": "Patrick Hand", "size": 48,
               "box": WHITE, "ink": CHARCOAL, "sound": "bubble",
               "about": "Neat handwriting in a speech bubble, like a thought bubbling up.",
               "good_for": "Questions, myths and what clients often say."},
    "paper": {"name": "Ripped paper", "style": "paper", "font": "Special Elite", "size": 50,
              "box": PAPER, "ink": CHARCOAL, "sound": "tape",
              "about": "Typewriter words on a scrap of paper, ripped on every side, like a cutting stuck on the screen.",
              "good_for": "Bold statements and hot takes. Feels like a magazine cut-out."},
    "tape": {"name": "Torn tape", "style": "tape", "font": "Caveat", "size": 48,
             "box": BEIGE, "ink": CHARCOAL, "sound": "tape",
             "about": "Handwritten words on a strip of torn tape, like a note stuck on the screen.",
             "good_for": "Chatty, friendly videos with a personal feel."},
    "note": {"name": "Sticky note", "style": "note", "font": "Indie Flower", "size": 48,
             "box": "#F4EEE6", "ink": CHARCOAL, "sound": "soft-pop",
             "about": "Childlike handwriting on a little sticky note.",
             "good_for": "Tips, reminders and to-do style videos."},
    "outline": {"name": "Outline pill", "style": "outline", "font": "Montserrat", "size": 48,
                "box": WHITE, "ink": WHITE, "sound": "click",
                "about": "White words inside a fine white outline. Light and modern.",
                "good_for": "Sleek, minimal brands."},
    "underline": {"name": "Pen underline", "style": "underline", "font": "Permanent Marker", "size": 50,
                  "box": BEIGE, "ink": WHITE, "sound": "scribble",
                  "about": "Bold marker-pen words with a pen stroke in your brand colour underneath.",
                  "good_for": "Hot takes and bold, confident brands."},
    "plain": {"name": "Just words", "style": "plain", "font": "Poppins", "size": 52,
              "box": BEIGE, "ink": WHITE, "sound": "soft-pop",
              "about": "Just the words, with a soft shadow. Nothing behind them.",
              "good_for": "When you want the pop-ups to feel light."},
}

# The writing on pop-ups. Every look comes with a matching one (its "font" above), so this
# is an optional extra choice. "show_with" is the look used for its sample in the lookbook.
POPUP_FONTS = {
    "clean": {"name": "Clean", "font": "Poppins", "show_with": "box",
              "about": "Clean, modern letters. Easy to read on anything.", "good_for": "Every brand."},
    "typewriter": {"name": "Typewriter", "font": "Special Elite", "show_with": "paper",
                   "about": "An old typewriter with slightly uneven ink, like a note typed in a hurry.",
                   "good_for": "Secret tips, confessions and 'things nobody tells you'."},
    "crisp": {"name": "Crisp typewriter", "font": "Courier Prime", "show_with": "box",
              "about": "A clean, classic typewriter.", "good_for": "Facts and 'did you know' moments."},
    "handwriting": {"name": "Casual handwriting", "font": "Caveat", "show_with": "tape",
                    "about": "Relaxed, flowing handwriting.", "good_for": "Chatty, friendly asides."},
    "neat": {"name": "Neat handwriting", "font": "Patrick Hand", "show_with": "bubble",
             "about": "Tidy, friendly print handwriting.", "good_for": "Thoughts, questions and gentle tips."},
    "baby": {"name": "Baby writing", "font": "Indie Flower", "show_with": "note",
             "about": "Round, bubbly, childlike writing.", "good_for": "Playful, fun and cheeky moments."},
    "pencil": {"name": "Pencil scribble", "font": "Reenie Beanie", "show_with": "note",
               "about": "A quick scribble, like a thought jotted down in pencil.", "good_for": "Inner thoughts and side comments."},
    "marker": {"name": "Marker pen", "font": "Permanent Marker", "show_with": "underline",
               "about": "Bold felt-tip letters.", "good_for": "Hot takes and big statements."},
}
HANDWRITING = {"Caveat", "Patrick Hand", "Indie Flower", "Reenie Beanie", "Permanent Marker"}
TEXTURED = {"paper", "tape", "note", "underline"}


def writing_for(design, move, font=None):
    """Which font a pop-up is written in: the one asked for; otherwise one that suits the
    movement (typed on = a typewriter, written on = handwriting); otherwise the look's own."""
    if font:
        return POPUP_FONTS[font]["font"]
    if move == "type":
        return "Special Elite" if design["style"] in TEXTURED else "Courier Prime"
    if move == "write" and design["font"] not in HANDWRITING:
        return "Caveat"
    return design["font"]


# How each pop-up arrives. "sound" replaces the look's own sound; "show_with" is the
# look used for its sample in the lookbook.
MOVES = {
    "pop": {"say": "Make my pop-ups pop on", "name": "Pop", "sound": None, "show_with": "box",
            "about": "Pops up all in one go with a little bounce, stays a few seconds, then pops away.",
            "good_for": "Lively videos. The default."},
    "type": {"say": "Make my pop-ups type on", "name": "Typed on", "sound": "typing", "show_with": "plain",
             "about": "Typed onto the screen letter by letter, with a soft typing sound. "
                      "On a box, bubble or paper, the shape appears first and the words type onto it.",
             "good_for": "Facts, tips and 'did you know' moments."},
    "write": {"say": "Make my pop-ups write themselves on", "name": "Written on", "sound": "scribble", "show_with": "tape",
              "about": "Drawn on from left to right, as if it's being written while you watch, with a pen sound.",
              "good_for": "Handwritten looks: tape, sticky note and pen underline."},
    "slide": {"say": "Make my pop-ups slide in", "name": "Slide in", "sound": None, "show_with": "bubble",
              "about": "Glides gently up into place.",
              "good_for": "Smooth, polished brands."},
    "fade": {"say": "Make my pop-ups fade in", "name": "Fade in", "sound": None, "show_with": "paper",
             "about": "Softly fades in. The calmest choice.",
             "good_for": "Gentle, reassuring videos."},
}


def load_popups(work, words, name="popups.json"):
    """The pop-ups Claude wrote for this video, with the moment each one arrives. None if there aren't any."""
    path = os.path.join(work, name)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        wanted = json.load(f)
    by_number = {w["i"]: w for w in words}
    pops = []
    for p in wanted:
        w = by_number.get(p["word"])
        if w is None:
            print(f"Pop-up \"{p['text']}\" is tied to word {p['word']}, which was cut, so it's left out.")
            continue
        pops.append({"text": p["text"], "start": w["start"], "piece": w["piece"],
                     "look": p.get("look"), "move": p.get("move"), "font": p.get("font")})
    return sorted(pops, key=lambda p: p["start"])


def with_glow(picture, strength=GLOW):
    """A soft dark glow behind words that sit straight on the video, so they read on
    anything, even a bright window or a ring light."""
    margin = 24
    canvas = Image.new("RGBA", (picture.width + margin * 2, picture.height + margin * 2))
    canvas.alpha_composite(picture, (margin, margin))
    # Thicken the letters, soften them, then boost: a dark cushion that hugs the words.
    shape = canvas.getchannel("A").filter(ImageFilter.MaxFilter(15)).filter(ImageFilter.GaussianBlur(12))
    glow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    glow.putalpha(shape.point(lambda a: min(255, round(a * 1.8 * strength))))
    glow.alpha_composite(canvas)
    return glow


def text_bands(full, blank, lines, tilt=0):
    """Where the words are in a pop-up picture, line by line, so typing can sweep across
    one line, then the next. The lines lean with the pop-up (tilt, in degrees), so the
    split between lines leans too. Returns which line each pixel belongs to, and each
    line's left and right edge."""
    height, width = full.shape[:2]
    ink = np.abs(full.astype(np.int16) - blank.astype(np.int16)).sum(axis=2) > 24
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    level = yy + (xx - width / 2) * np.tan(np.radians(tilt))   # straightens the lean back out
    if not ink.any():
        return {"line_of": np.zeros((height, width), np.int32), "edges": [(0, width)]}
    top, bottom = level[ink].min(), level[ink].max()
    # Split between lines where there's least ink (the gap between them), near where it's expected.
    counts, cuts = np.histogram(level[ink], bins=max(1, int((bottom - top) / 2)), range=(top, bottom))
    inner = []
    for k in range(1, lines):
        expected = top + (bottom - top) * k / lines
        reach = (bottom - top) / lines * 0.35
        near = [b for b in range(len(counts)) if abs((cuts[b] + cuts[b + 1]) / 2 - expected) <= reach]
        best = min(near, key=lambda b: (counts[b], abs((cuts[b] + cuts[b + 1]) / 2 - expected))) if near else None
        inner.append((cuts[best] + cuts[best + 1]) / 2 if best is not None else expected)
    line_of = np.digitize(level, inner).astype(np.int32)
    edges = []
    for k in range(lines):
        cols = np.where((ink & (line_of == k)).any(axis=0))[0]
        edges.append((int(cols[0]), int(cols[-1]) + 1) if len(cols) else (0, width))
    return {"line_of": line_of, "edges": edges}


def revealed(full, blank, bands, amount):
    """The pop-up with `amount` (0 to 1) of its words showing, line by line from the left,
    over its blank box (or nothing)."""
    if amount >= 1:
        return full
    widths = [right - left for left, right in bands["edges"]]
    to_show = amount * sum(widths)
    xs = np.arange(full.shape[1], dtype=np.float32)
    weights = []
    for (left, right), width in zip(bands["edges"], widths):
        cut = left + min(width, max(0.0, to_show))
        to_show -= width
        weights.append(np.clip((cut - xs) / FEATHER + 0.5, 0, 1) if cut > left else np.zeros_like(xs))
    w = np.stack(weights)[bands["line_of"], np.arange(full.shape[1])[None, :]][..., None]
    return (blank.astype(np.float32) * (1 - w) + full.astype(np.float32) * w).astype(np.uint8)


class Popper:
    """Draws the pop-ups onto each frame, and lists the sound for each one."""

    def __init__(self, pops, look="box", move="pop", faces=None, captions_above=False, font=None, pack=None):
        """pack: a style pack (packs.PACKS). With one, every pop-up is in the pack's one pop-up
        font, in its main style, with its accent style every third pop-up (Frances's rule: one
        font and two pop-up styles). Without one, every pop-up has the same look and movement."""
        self.pops = pops
        self.sounds = []
        for n, p in enumerate(pops):
            if pack:
                own_look, own_move = packs.turn(pack, n)
                design = POPUP_DESIGNS[p.get("look") or own_look]
                p["move"] = p.get("move") or own_move
                writing = pack["popups"]   # one font for every pop-up in the reel, whatever popups.json says
            else:
                design = POPUP_DESIGNS[p.get("look") or look]
                p["move"] = p.get("move") or move
                writing = writing_for(design, p["move"], p.get("font") or font)
            moving = MOVES[p["move"]]
            on_video = design["style"] in ("plain", "underline", "outline")
            style = Look(popup_style=design["style"], caption_font=writing, box_colour=design["box"],
                         box_text_colour=design["ink"], text_colour=design["ink"] if on_video else WHITE,
                         popup_tilt=TILT if n % 2 == 0 else -TILT)
            full = popup_picture(p["text"], style, WIDEST, design["size"])
            p["reveal"] = 0.0
            if p["move"] in ("type", "write"):
                # Plain words and the pen underline have nothing to show first; the rest show their shape.
                if design["style"] in ("plain", "underline"):
                    blank = Image.new("RGBA", full.size)
                else:
                    blank = popup_picture(p["text"], replace(style, popup_words=False), WIDEST, design["size"])
                lines = len(wrap(Writer(design["size"], writing, "caption"), p["text"], WIDEST))
                p["full"], p["blank"] = np.asarray(full), np.asarray(blank)
                p["glow"], p["cache"] = on_video, {}
                if on_video:   # the glow is added as the words appear, so it grows with them
                    full = with_glow(full)
                p["bands"] = text_bands(p["full"], p["blank"], max(1, lines), style.popup_tilt)
                letters = len(p["text"])
                p["reveal"] = (min(LONGEST_TYPING, letters * LETTER) if p["move"] == "type"
                               else min(1.4, max(0.6, letters * 0.035)))
                p["first"] = 0.0 if design["style"] in ("plain", "underline") else SHAPE_FIRST
            elif on_video:
                full = with_glow(full)
            p["picture"] = full
            sound = moving["sound"] or design["sound"]
            self.sounds.append((p["start"], os.path.join(HERE, "sounds", f"{sound}.wav")))
            if p["move"] == "write" and p["reveal"] > 0.7:   # a second stroke of the pen for longer lines
                self.sounds.append((p["start"] + 0.45, os.path.join(HERE, "sounds", "scribble.wav")))
        for n, p in enumerate(pops):
            following = pops[n + 1]["start"] - GAP if n + 1 < len(pops) else p["start"] + 99
            stays = STAYS + p["reveal"] * 0.6
            p["end"] = max(p["start"] + SHORTEST, min(p["start"] + stays, following))
            p["centre_y"] = self.centre_for(p, faces, captions_above)

    def centre_for(self, pop, faces, captions_above):
        """Where the middle of the pop-up goes, up and down: in the space between Instagram's
        top bar and the head, over the hair if it has to be, never on the face."""
        height = pop["picture"].height
        head_top, face_top = captions.HEAD_TOP, captions.HEAD_TOP + 0.05
        if faces:
            found = [f for t, f in faces if f and pop["start"] - 0.25 <= t <= pop["end"] + 0.25]
            if found:
                _, head_top = face.head_and_chin(found)
                face_top = float(np.percentile([f["top"] for f in found], 10))
        top_limit = captions.HIGHEST
        if captions_above or head_top * H - UNDER_HEAD - top_limit < height:
            # No room between the top bar and the head (or the captions are there): as high as Instagram allows.
            centre = top_limit + height / 2
        else:
            centre = (top_limit + head_top * H - UNDER_HEAD) / 2
        if centre + height / 2 > face_top * H - OFF_FACE:
            print(f"Not much room above the face for \"{pop['text']}\": it sits as high as Instagram allows.")
        return centre

    def draw_on(self, frame, t):
        for p in self.pops:
            if p["start"] <= t < p["end"]:
                break
        else:
            return frame
        since, left = t - p["start"], p["end"] - t
        scale, alpha, nudge = 1.0, 1.0, 0.0
        picture = p["picture"]
        if p["move"] == "pop":
            scale = 0.55 + 0.45 * captions.ease_out_back(min(1.0, since / ENTER))
            alpha = min(1.0, since / 0.05)
        elif p["move"] == "slide":
            eased = 1 - (1 - min(1.0, since / 0.3)) ** 3
            nudge, alpha = 44 * (1 - eased), min(1.0, since / 0.2)
        elif p["move"] == "fade":
            alpha = min(1.0, since / 0.35)
        else:  # typed or written on: the shape fades in, then the words appear from the left
            alpha = min(1.0, since / 0.08) if p["first"] else 1.0
            progress = (since - p["first"]) / p["reveal"]
            if progress < 1:
                if p["move"] == "type":   # letter by letter
                    letters = len(p["text"])
                    amount = np.floor(max(0.0, progress) * letters) / letters
                else:                     # one smooth stroke, quick at first then easing
                    amount = 1 - (1 - max(0.0, progress)) ** 2
                key = round(amount * 80)
                if key not in p["cache"]:
                    picture = Image.fromarray(revealed(p["full"], p["blank"], p["bands"], key / 80), "RGBA")
                    p["cache"][key] = with_glow(picture) if p["glow"] else picture
                picture = p["cache"][key]
        if left < LEAVE:
            q = left / LEAVE
            alpha *= q
            scale *= 0.9 + 0.1 * q
        if abs(scale - 1) > 1e-3:
            picture = picture.resize((max(1, round(picture.width * scale)), max(1, round(picture.height * scale))),
                                     Image.BILINEAR)
        captions.lay_on(frame, np.asarray(picture), W / 2, p["centre_y"] - picture.height / 2 + nudge, alpha)
        return frame
