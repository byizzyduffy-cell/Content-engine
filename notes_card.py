"""
Notes app cards for the "Notes app answers" carousel (post library, recipe 18).

The template's slides show screenshots of an iPhone note, and a screenshot is a
picture, so Canva can't change its words. This draws a fresh card in the same
look with the clinic's own words: a white card, the Notes top bar (back, undo,
share and the three dots), a bold line (the question, or the title), then the
plain words under it (the answer).

    python3 engine/notes_card.py cards.json --out <folder>
    python3 engine/notes_card.py --heading "“Does it hurt?”" --words "Most people..." --out card.png

cards.json is a list, one card per slide, in order:

    [{"heading": "LASER HAIR REMOVAL FAQS", "words": "The questions you're thinking but haven't asked yet \U0001f440", "title": true},
     {"heading": "“Will I still have to shave?”", "words": "You go from shaving every few days\nto barely thinking about it."}]

"title": true keeps the words close under the heading (the first slide). A blank
line in the words starts a new paragraph. Every card in a set uses the same text
sizes, so they match when you swipe. Cards are drawn at twice the size they sit
at on the slide, so they stay sharp; the file name says the size to give the
picture in Canva (e.g. note-03-613x485.png).
"""

import tools  # noqa: F401  (first: emoji-safe output on Windows)
import argparse
import json
import os

from PIL import Image, ImageDraw, ImageFilter

from review_card import font
from text_reel import EMOJI_FONTS, split_runs
import platform

SCALE = 2                     # pictures are drawn at twice the size they sit at

# Sizes at 1x, for a card 613 wide on a 1080 x 1350 slide (measured on Frances's template).
WIDTH = 613
PAD = 31                      # left and right
BAR_Y = 58                    # middle of the top bar's buttons
BUTTON = 64                   # round buttons
HEADING_TOP = 170             # top of the first heading line
HEADING = 30                  # bold line
HEADING_STEP = 42
WORDS = 23                    # plain words
WORDS_STEP = 38
GAP = 51                      # extra space between the heading and the words
TITLE_GAP = 14                # the same on a title card
BOTTOM = 44                   # under the last line
INK = "#1C1C1E"               # icons
HEADING_INK = "#3A3A3C"
WORDS_INK = "#48484A"


class Rich:
    """Words in one font and size, emoji included (the computer's own emoji)."""

    def __init__(self, size, weight):
        self.f = font(size, weight)
        self.size = size
        path, self.render = EMOJI_FONTS.get(platform.system(), (None, None))
        self.emoji_font = None
        if path and os.path.exists(path):
            from PIL import ImageFont
            self.emoji_font = ImageFont.truetype(path, self.render)

    def emoji(self, e):
        if not self.emoji_font:
            return None
        l, t, r, b = self.emoji_font.getbbox(e)
        pic = Image.new("RGBA", (r - l, b - t))
        ImageDraw.Draw(pic).text((-l, -t), e, font=self.emoji_font, embedded_color=True)
        h = round(self.size * 1.05)
        return pic.resize((round(pic.width * h / pic.height), h), Image.LANCZOS)

    def width(self, text):
        total = 0
        for kind, piece in split_runs(text):
            if kind == "text":
                total += self.f.getlength(piece)
            else:
                pic = self.emoji(piece)
                total += pic.width + self.size * 0.08 if pic else 0
        return total

    def wrap(self, text, width):
        """Lines that fit, keeping their own line breaks; a paragraph never ends on one word on its own."""
        lines = []
        for para in text.split("\n"):
            mine, line = [], ""
            for word in para.split():
                test = f"{line} {word}".strip()
                if self.width(test) <= width or not line:
                    line = test
                else:
                    mine.append(line)
                    line = word
            mine.append(line)
            if len(mine) > 1 and " " not in mine[-1] and len(mine[-2].split()) > 2:
                head, moved = mine[-2].rsplit(" ", 1)
                if self.width(f"{moved} {mine[-1]}") <= width:
                    mine[-2], mine[-1] = head, f"{moved} {mine[-1]}"
            lines += mine
        return lines

    def draw(self, im, x, top, text, fill):
        d = ImageDraw.Draw(im)
        baseline = top + round(self.size * 0.73)
        for kind, piece in split_runs(text):
            if kind == "text":
                d.text((x, baseline), piece, font=self.f, fill=fill, anchor="ls")
                x += self.f.getlength(piece)
            else:
                pic = self.emoji(piece)
                if pic:
                    x += self.size * 0.04
                    im.alpha_composite(pic, (round(x), round(baseline - pic.height * 0.86)))
                    x += pic.width + self.size * 0.04
                    d = ImageDraw.Draw(im)


def soft_shadow(im, box, radius, s):
    """The faint glassy shadow under the Notes buttons."""
    layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
    x0, y0, x1, y1 = box
    ImageDraw.Draw(layer).rounded_rectangle((x0, y0 + 2 * s, x1, y1 + 2 * s), radius=radius, fill=(0, 0, 0, 46))
    return Image.alpha_composite(im, layer.filter(ImageFilter.GaussianBlur(10 * s)))


def top_bar(im, s):
    w = im.width
    r = BUTTON * s // 2
    cy = BAR_Y * s
    back = (PAD * s + r - 12 * s, cy)                # matches the template: the button sits close to the edge
    undo = (396 * s, cy)
    pill = (445 * s, cy - r, 595 * s, cy + r)
    for cx, _ in (back, undo):
        im = soft_shadow(im, (cx - r, cy - r, cx + r, cy + r), r, s)
    im = soft_shadow(im, pill, r, s)
    d = ImageDraw.Draw(im)
    for cx, _ in (back, undo):
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill="#FFFFFF")
    d.rounded_rectangle(pill, radius=r, fill="#FFFFFF")
    lw = round(2.9 * s)
    k = 1.3 * s
    # Back: a chevron.
    bx = back[0]
    d.line([(bx + 5 * k, cy - 10 * k), (bx - 5 * k, cy), (bx + 5 * k, cy + 10 * k)], fill=INK, width=lw, joint="curve")
    # Undo: a U-turn arrow pointing left.
    ux = undo[0]
    d.line([(ux - 8 * k, cy - 5 * k), (ux + 2 * k, cy - 5 * k)], fill=INK, width=lw)
    d.arc((ux - 4 * k, cy - 5 * k, ux + 8 * k, cy + 7 * k), -90, 90, fill=INK, width=lw)
    d.line([(ux + 2 * k, cy + 7 * k), (ux - 3 * k, cy + 7 * k)], fill=INK, width=lw)
    d.line([(ux - 4 * k, cy - 9 * k), (ux - 8 * k, cy - 5 * k), (ux - 4 * k, cy - 1 * k)], fill=INK, width=lw, joint="curve")
    # Share: an open box with an arrow out of the top.
    sx = pill[0] + 36 * s
    d.line([(sx - 4 * k, cy - 3 * k), (sx - 8 * k, cy - 3 * k), (sx - 8 * k, cy + 11 * k),
            (sx + 8 * k, cy + 11 * k), (sx + 8 * k, cy - 3 * k), (sx + 4 * k, cy - 3 * k)], fill=INK, width=lw, joint="curve")
    d.line([(sx, cy + 4 * k), (sx, cy - 12 * k)], fill=INK, width=lw)
    d.line([(sx - 4 * k, cy - 8 * k), (sx, cy - 12 * k), (sx + 4 * k, cy - 8 * k)], fill=INK, width=lw, joint="curve")
    # The three dots.
    dx = pill[0] + 116 * s
    for i in (-1, 0, 1):
        cx = dx + i * 8 * k
        d.ellipse((cx - 2.1 * k, cy - 2.1 * k, cx + 2.1 * k, cy + 2.1 * k), fill=INK)
    return im


def make_card(heading, words, out, title=False, width=WIDTH):
    s = SCALE
    inner = (width - 2 * PAD) * s
    head = Rich(HEADING * s, "Bold")
    body = Rich(WORDS * s, "Regular")
    head_lines = head.wrap(heading, inner - 60 * s) if heading else []
    body_lines = body.wrap(words, inner - 30 * s) if words else []
    y = HEADING_TOP * s
    h = y + HEADING_STEP * s * len(head_lines)
    if body_lines:
        h += (TITLE_GAP if title else GAP) * s + WORDS_STEP * s * len(body_lines) - (WORDS_STEP - WORDS) * s
    else:
        h -= (HEADING_STEP - HEADING) * s
    h += BOTTOM * s
    im = Image.new("RGBA", (width * s, h), "#FFFFFF")
    im = top_bar(im, s)
    for line in head_lines:
        head.draw(im, PAD * s, y, line, HEADING_INK)
        y += HEADING_STEP * s
    if body_lines:
        y += (TITLE_GAP if title else GAP) * s
        for line in body_lines:
            if line:
                body.draw(im, PAD * s, y, line, WORDS_INK)
            y += WORDS_STEP * s
    im.convert("RGB").save(out)
    return h // s


def main():
    p = argparse.ArgumentParser(description="Notes app cards for the Notes app answers carousel.")
    p.add_argument("cards", nargs="?", help="a cards.json list (one card per slide)")
    p.add_argument("--heading", help="one card: the bold line")
    p.add_argument("--words", default="", help="one card: the plain words under it")
    p.add_argument("--title", action="store_true", help="one card: keep the words close under the heading")
    p.add_argument("--width", type=int, default=WIDTH, help="card width on the slide (1x)")
    p.add_argument("--out", required=True, help="a folder (for cards.json) or a .png (for one card)")
    a = p.parse_args()
    if a.cards:
        with open(a.cards, encoding="utf-8") as f:
            cards = json.load(f)
        os.makedirs(a.out, exist_ok=True)
        for n, c in enumerate(cards, 1):
            tmp = os.path.join(a.out, "note.png")
            h = make_card(c.get("heading", ""), c.get("words", ""), tmp, c.get("title", False), a.width)
            name = f"note-{n:02d}-{a.width}x{h}.png"
            os.replace(tmp, os.path.join(a.out, name))
            print(f"SAVED: {name} (give it {a.width} x {h} on the slide)")
        return
    if not a.heading:
        raise SystemExit("PROBLEM: give a cards.json file, or --heading for one card")
    h = make_card(a.heading, a.words, a.out, a.title, a.width)
    print(f"SAVED: {a.out} (give it {a.width} x {h} on the slide)")


if __name__ == "__main__":
    main()
