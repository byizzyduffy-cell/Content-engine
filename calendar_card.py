"""
Calendar booking cards for "The important meeting" carousel (post library, recipe 23).

Each slide of the template shows a calendar with one blue booking on it (the
"meeting" is a treatment). The calendar is a picture, so Canva can't change it:
this draws a fresh one with the clinic's own treatment, a little emoji and a
one-hour time, in the same look (a white rounded card, the hours down the side,
the booking in blue).

    python3 engine/calendar_card.py meetings.json --out <folder>
    python3 engine/calendar_card.py --treatment "HydraFacial" --emoji "\U0001fae7" --start 12:00 --out card.png

meetings.json is a list, one card per slide, in order:

    [{"treatment": "Laser Hair Removal", "emoji": "⚡", "start": "10:00"},
     {"treatment": "HydraFacial", "emoji": "\U0001fae7", "start": "12:00"}]

Cards are drawn at twice the size they sit at on the slide (700 x 280), so they
stay sharp.
"""

import tools  # noqa: F401  (first: emoji-safe output on Windows)
import argparse
import json
import os

from PIL import Image, ImageDraw

from notes_card import Rich

SCALE = 2
W, H = 700, 280               # on the slide (measured on Frances's template)
RADIUS = 34
BORDER = "#E4E4E4"
HOUR_INK = "#8E8E93"
LINE = "#ECECEC"
BLUE = "#2DB2F6"
HOUR_X = 107                  # hour labels end here
LINE_X0, LINE_X1 = 125, 673
FIRST_LINE, STEP = 35, 72.3   # the four hour lines
EVENT_X0, EVENT_X1 = 136, 652


def hour(text, add=0):
    h, m = (int(x) for x in text.split(":"))
    return f"{(h + add) % 24:02d}:{m:02d}"


def make_card(treatment, emoji, start, out):
    s = SCALE
    im = Image.new("RGBA", (W * s, H * s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, W * s - 1, H * s - 1), radius=RADIUS * s, fill="#FFFFFF", outline=BORDER, width=s)
    labels = Rich(19 * s, "Regular")
    for i in range(4):
        y = (FIRST_LINE + STEP * i) * s
        d.line((LINE_X0 * s, y, LINE_X1 * s, y), fill=LINE, width=round(1.5 * s))
        text = hour(start, i - 1)
        labels.draw(im, HOUR_X * s - labels.width(text), y - round(19 * s * 0.37), text, HOUR_INK)
        d = ImageDraw.Draw(im)
    # The booking: from just under the start line to just above the next one.
    top, bottom = (FIRST_LINE + STEP) * s + 4 * s, (FIRST_LINE + 2 * STEP) * s - 2 * s
    d.rounded_rectangle((EVENT_X0 * s, top, EVENT_X1 * s, bottom), radius=7 * s, fill=BLUE)
    name = Rich(19.5 * s, "SemiBold")
    name.draw(im, 156 * s, top + 9 * s, f"{treatment} {emoji}".strip(), "#FFFFFF")
    d = ImageDraw.Draw(im)
    # A little clock, then the time.
    cx, cy, r = 163 * s, top + 40 * s, 7 * s
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline="#FFFFFF", width=round(1.6 * s))
    d.line((cx, cy - 4 * s, cx, cy, cx + 3 * s, cy + 2 * s), fill="#FFFFFF", width=round(1.6 * s), joint="curve")
    times = Rich(18 * s, "Regular")
    times.draw(im, 175 * s, cy - round(18 * s * 0.37), f"{start} – {hour(start, 1)}", "#FFFFFF")
    im.save(out)


def main():
    p = argparse.ArgumentParser(description="Calendar booking cards for The important meeting carousel.")
    p.add_argument("meetings", nargs="?", help="a meetings.json list (one card per slide)")
    p.add_argument("--treatment", help="one card: the treatment's name")
    p.add_argument("--emoji", default="", help="one card: a little emoji after the name")
    p.add_argument("--start", default="10:00", help="one card: the start time, e.g. 10:00")
    p.add_argument("--out", required=True, help="a folder (for meetings.json) or a .png (for one card)")
    a = p.parse_args()
    if a.meetings:
        with open(a.meetings, encoding="utf-8") as f:
            meetings = json.load(f)
        os.makedirs(a.out, exist_ok=True)
        for n, m in enumerate(meetings, 1):
            name = f"meeting-{n:02d}-{W}x{H}.png"
            make_card(m["treatment"], m.get("emoji", ""), m.get("start", "10:00"), os.path.join(a.out, name))
            print(f"SAVED: {name} (give it {W} x {H} on the slide)")
        return
    if not a.treatment:
        raise SystemExit("PROBLEM: give a meetings.json file, or --treatment for one card")
    make_card(a.treatment, a.emoji, a.start, a.out)
    print(f"SAVED: {a.out} (give it {W} x {H} on the slide)")


if __name__ == "__main__":
    main()
