"""
Review cards: a client's Google review drawn to look like it does on Google.

A white card with the reviewer's initial in a coloured circle, their name, the
Google "G", five gold stars and their exact words in Google's grey. Every card
in a set uses the same text size, so they match when you swipe through a
carousel.

    python3 engine/review_card.py "My Content/2026-10/reviews.md" "Nidhi B." "Senali S." ... --out <folder>

The review's words are never changed, line breaks included.
"""

import tools  # noqa: F401  (first: emoji-safe output on Windows)
import argparse
import os
import re

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONT = os.path.join(HERE, "fonts", "Inter.ttf")

# ---------------------------------------------------------------------------
# The look. Sizes are for a 1220 x 1128 card (it sits in a 610 x 564 frame).
# ---------------------------------------------------------------------------
WIDTH, HEIGHT = 1220, 1128
PADDING = 76
AVATAR = 116                  # the circle with the reviewer's initial
GOOGLE_G = 88                 # the Google "G" in the top right corner
NAME_SIZE = 46
STAR = 50                     # each gold star
BIGGEST_TEXT, SMALLEST_TEXT = 58, 30
FOOTER_SIZE = 34            # the small "Posted on Google" line at the bottom
LINE_SPACING = 1.45

CARD = "#FFFFFF"
NAME = "#202124"              # Google's near-black for names
WORDS = "#3C4043"             # Google's grey for review text
QUIET = "#70757A"             # Google's lighter grey for small print
STAR_GOLD = "#FBBC04"
AVATAR_COLOURS = ["#7B1FA2", "#1976D2", "#00897B", "#E64A19", "#5D4037", "#C2185B", "#3949AB", "#689F38"]
G_BLUE, G_RED, G_YELLOW, G_GREEN = "#4285F4", "#EA4335", "#FBBC05", "#34A853"


def font(size, weight="Regular"):
    f = ImageFont.truetype(FONT, size)
    f.set_variation_by_name(weight)
    return f


def google_g(size):
    """The Google "G", drawn large and shrunk down so the edges are smooth."""
    big = size * 4
    c, outer = big / 2, big / 2
    thick = outer * 0.38
    g = Image.new("RGBA", (big, big))
    d = ImageDraw.Draw(g)
    box = (0, 0, big - 1, big - 1)
    # Angles go clockwise from 3 o'clock. The gap is at the top right.
    for colour, start, end in [(G_BLUE, 0, 45), (G_GREEN, 45, 148), (G_YELLOW, 148, 212), (G_RED, 212, 318)]:
        d.pieslice(box, start, end, fill=colour)
    hole = Image.new("L", (big, big), 255)
    inner = outer - thick
    ImageDraw.Draw(hole).ellipse((c - inner, c - inner, c + inner, c + inner), fill=0)
    g.putalpha(Image.composite(g.getchannel("A"), hole, hole))
    d = ImageDraw.Draw(g)
    d.rectangle((c - outer * 0.04, c - thick * 0.42, big - 1, c + thick * 0.5), fill=G_BLUE)
    return g.resize((size, size), Image.LANCZOS)


def star_points(cx, cy, r):
    import math
    points = []
    for i in range(10):
        radius = r if i % 2 == 0 else r * 0.45
        angle = math.radians(-90 + i * 36)
        points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    return points


def wrap(text, f, width):
    """Split the review into lines that fit, keeping the reviewer's own line breaks. A paragraph never ends on
    one word on its own (Frances, 2026-11-02): the line above gives it a word to keep it company."""
    lines = []
    for paragraph in text.split("\n"):
        mine, line = [], ""
        for word in paragraph.split():
            test = f"{line} {word}".strip()
            if f.getlength(test) <= width or not line:
                line = test
            else:
                mine.append(line)
                line = word
        mine.append(line)
        if len(mine) > 1 and " " not in mine[-1] and len(mine[-2].split()) > 2:
            head, moved = mine[-2].rsplit(" ", 1)
            if f.getlength(f"{moved} {mine[-1]}") <= width:
                mine[-2], mine[-1] = head, f"{moved} {mine[-1]}"
        lines += mine
    return lines


def text_top():
    return PADDING + AVATAR + 34 + STAR + 44


def fits(text, size):
    f = font(size)
    lines = wrap(text, f, WIDTH - 2 * PADDING)
    return text_top() + len(lines) * size * LINE_SPACING <= HEIGHT - PADDING - FOOTER_SIZE - 40


def shared_size(texts):
    """The biggest text size where every review in the set fits."""
    for size in range(BIGGEST_TEXT, SMALLEST_TEXT - 1, -1):
        if all(fits(t, size) for t in texts):
            return size
    return SMALLEST_TEXT


def make_card(name, text, out, size):
    card = Image.new("RGB", (WIDTH, HEIGHT), CARD)
    d = ImageDraw.Draw(card)

    # The reviewer's initial in a coloured circle, like a Google profile picture.
    x, y = PADDING, PADDING
    colour = AVATAR_COLOURS[sum(map(ord, name)) % len(AVATAR_COLOURS)]
    d.ellipse((x, y, x + AVATAR, y + AVATAR), fill=colour)
    initial = font(int(AVATAR * 0.46), "Medium")
    d.text((x + AVATAR / 2, y + AVATAR / 2), name[0].upper(), fill="#FFFFFF", font=initial, anchor="mm")

    # Their name beside it, and the Google "G" in the corner.
    d.text((x + AVATAR + 30, y + AVATAR / 2), name, fill=NAME, font=font(NAME_SIZE, "SemiBold"), anchor="lm")
    g = google_g(GOOGLE_G)
    card.paste(g, (WIDTH - PADDING - GOOGLE_G, int(y + (AVATAR - GOOGLE_G) / 2)), g)

    # Five gold stars.
    stars_y = y + AVATAR + 34 + STAR / 2
    for i in range(5):
        d.polygon(star_points(PADDING + STAR / 2 + i * STAR * 1.12, stars_y, STAR / 2), fill=STAR_GOLD)

    # Their exact words.
    f = font(size)
    line_y = text_top()
    for line in wrap(text, f, WIDTH - 2 * PADDING):
        d.text((PADDING, line_y), line, fill=WORDS, font=f)
        line_y += size * LINE_SPACING

    # A small line at the bottom saying where the review came from.
    d.text((PADDING, HEIGHT - PADDING), "Posted on Google", fill=QUIET, font=font(FOOTER_SIZE), anchor="ls")

    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    card.save(out)
    return out


def read_reviews(path):
    """Reviews from a reviews.md file: a **Name** line, then the review as > quote lines."""
    reviews, name = {}, None
    for line in open(path, encoding="utf-8"):
        found = re.match(r"\s*\d+\.\s+\*\*(.+?)\*\*", line)
        if found:
            name = found.group(1)
            reviews[name] = []
        elif name and re.match(r"\s*> ?", line):
            reviews[name].append(re.sub(r"^\s*> ?", "", line.rstrip("\n")))
        elif name and line.startswith("## "):
            name = None
    return {n: "\n".join(lines).strip() for n, lines in reviews.items() if lines}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Make Google-style review cards.")
    parser.add_argument("reviews", help="the reviews.md file")
    parser.add_argument("names", nargs="+", help="which reviewers, as written in reviews.md")
    parser.add_argument("--out", required=True, help="folder for the cards")
    args = parser.parse_args()

    reviews = read_reviews(args.reviews)
    chosen = {n: reviews[n] for n in args.names}
    size = shared_size(list(chosen.values()))
    for n, text in chosen.items():
        slug = re.sub(r"[^a-z]+", "-", n.lower()).strip("-").split("-")[0]
        print(make_card(n, text, os.path.join(args.out, f"review-{slug}.png"), size))
