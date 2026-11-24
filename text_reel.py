"""
Text-on-video reel maker.

Takes one clip and the text from the content plan, and makes a finished reel:
the clip trimmed, lightly darkened and colour-graded, with the text popping on
where the student chose (the middle of the screen or the top third).

Give it one --text for a single piece of text. Give it two (the main text, then
the call to action) and the call to action arrives as a pop-up, with a sound,
once people have had time to read the main text. Both stay on to the end.

Everything about the look comes together as one "look", so the main text, the
pop-up, the colours, the animation and the sound always match. A brand kit
(--kit, from brand_kits.json) sets the whole look in one go, and --my-colours
fits a student's own brand colours onto it, keeping everything readable.

Example:
    python3 engine/text_reel.py \
        --clip "My Content/2026-10/clips/IMG_3182.MOV" \
        --text "Where are all the women who are DONE planning around shaving?" \
        --text "Comment LASER and we'll send you the details" \
        --kit soft-blush \
        --out "My Content/2026-10/reels/2026-10-01.mp4"

Students choose their style from previews made with their own clip:
    --preview position   compares where the text sits (then --position middle or top)
    --preview popup      compares how the pop-up looks (then --popup-style box or plain)
    --preview colours    compares a kit as designed with the kit in their colours
"""

import tools  # noqa: F401  (first: emoji-safe output on Windows)
from sdr import normal_colour
import argparse
import colorsys
import json
import os
import platform
import random
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, replace
from types import SimpleNamespace

from PIL import Image, ImageColor, ImageDraw, ImageEnhance, ImageFilter, ImageFont

# ---------------------------------------------------------------------------
# Timing and size. Change these numbers to change every reel.
# ---------------------------------------------------------------------------
SECONDS = 7               # how long a reel with one piece of text is
POPUP_AFTER = 5.5         # seconds before the call to action pops up
POPUP_STAYS = 3.5         # how long the reel carries on after it pops up
DARKNESS = 0.25           # 0 = clip as filmed, 1 = completely black
BIGGEST_TEXT = 52         # main text starts this big and shrinks until it fits
SMALLEST_TEXT = 36
POPUP_TEXT = 40
LINE_SPACING = 1.25
RIBBON_SPACING = 1.6      # ribbons need a little more room between lines
POPUP_GAP = 48            # space between the main text and the pop-up
WIDEST_ONE_LINE_POPUP = 790  # a pop-up up to this wide stays on one line rather than leaving a word behind

# How the pop-up arrives, frame by frame: (size, distance below its spot, see-through-ness).
# "wipe" is different: the pop-up is drawn on from left to right, like tape laid down or a pen stroke.
# "type" appears one letter at a time, as if it's being typed.
ANIMATIONS = {
    "bounce": [(0.5, 0, 1), (0.8, 0, 1), (1.06, 0, 1), (1.1, 0, 1), (1.04, 0, 1), (1.0, 0, 1)],
    "fade": [(1, 0, 0.12), (1, 0, 0.3), (1, 0, 0.5), (1, 0, 0.68), (1, 0, 0.84), (1, 0, 0.95), (1, 0, 1)],
    "slide-up": [(1, 46, 0.15), (1, 30, 0.4), (1, 18, 0.65), (1, 9, 0.85), (1, 3, 0.96), (1, 0, 1)],
    "drop": [(1, -70, 0.2), (1, -38, 0.6), (1, -12, 0.9), (1, 5, 1), (1, -2, 1), (1, 0, 1)],
}
WIPE_FRAMES = 10

# Reels where each line of the plan arrives in turn ("reveal"): a soft tap as each line lands,
# and how long everything stays on at the end when there's no pop-up.
BEAT_SOUND = "tap"
THEN_GAP = 14             # space between a pop-up and the one that follows it underneath
HOLD = 2.5

# A gentle colour change on the footage, per kit: (brightness and contrast
# settings for FFmpeg, then how much to turn red, green and blue up or down).
GRADES = {
    "": ("", (1.0, 1.0, 1.0)),
    "warm": ("eq=saturation=1.08", (1.04, 1.0, 0.93)),
    "cool": ("eq=saturation=0.9:brightness=0.02", (0.96, 1.0, 1.05)),
    "soft": ("eq=contrast=0.9:brightness=0.04:saturation=0.95", (1.02, 1.0, 0.99)),
    "natural": ("eq=saturation=0.92", (1.0, 1.0, 0.98)),
    "moody": ("eq=contrast=1.15:brightness=-0.04:saturation=0.85", (1.0, 1.0, 1.0)),
    "vivid": ("eq=saturation=1.3:contrast=1.06", (1.0, 1.0, 1.0)),
}

# Reels are 1080 wide and 1920 tall. Each student picks where their text sits.
# Both boxes keep the text compact so the video still shows around it, and
# clear of Instagram's top bar, the buttons down the right and the caption at
# the bottom. (left, top, right, bottom)
TEXT_POSITIONS = {
    "middle": (150, 730, 930, 1190),  # middle of the screen
    "top": (150, 300, 930, 760),      # top third, leaves the middle of the shot clear
    "lower": (150, 1000, 920, 1290),  # lower down, still above Instagram's caption and left of its buttons
}
# Frances's rule: when the lines arrive at different times, each one gets its own card or panel,
# stacked with a gap. Separate boxes need a little more room. (left, top, right, bottom)
BOXES_POSITIONS = {
    "middle": (150, 640, 930, 1250),
    "top": (150, 260, 930, 870),
    "lower": (150, 880, 920, 1300),
}
BOX_GAP = 18              # space between the separate boxes
POPUP_STYLES = {"box": "pop-up box", "plain": "plain white text"}  # the two a student is always offered
# More pop-up designs, so a month of reels doesn't repeat itself:
# (room inside sideways, room inside up and down, space round the edge for shadows and tails)
SHAPES = {
    "tape": (40, 16, 14),      # a strip of tape with torn ends
    "bubble": (34, 22, 40),    # a speech bubble with a tail
    "note": (44, 34, 26),      # a sticky note
    "outline": (34, 20, 12),   # an outlined pill
    "paper": (42, 24, 20),     # a scrap of paper, ripped on every side
}
ALL_POPUP_STYLES = list(POPUP_STYLES) + list(SHAPES) + ["underline"]  # underline: handwriting with a pen stroke under it
LOWEST_POPUP = 1450       # keep the pop-up above Instagram's caption

WIDTH, HEIGHT, FPS = 1080, 1920, 25
HERE = os.path.dirname(os.path.abspath(__file__))


@dataclass
class Look:
    """Everything about how a reel looks and sounds. The defaults are the approved standard."""
    heading_font: str = "DM Sans"      # main text
    caption_font: str = "DM Sans"      # pop-up
    text_style: str = "plain"          # plain, card, ribbon or panel
    text_case: str = "as written"      # as written, or capitals
    text_colour: str = "#FFFFFF"       # main text
    highlight: str = ""                # colour for words in CAPITALS in the main text ("" = no highlight)
    behind_text: str = ""              # the card, ribbon or panel behind the main text
    lines: str = ""                    # thin lines above and below the main text ("" = none)
    outline: str = ""                  # an outline round each letter ("" = none)
    glow: float = 0                    # a soft dark haze behind words straight on the video, instead of an outline (0 = none, 0.5 = gentle)
    shadow: bool = True                # the soft shadow under words straight on the video (False = just the words, nothing
                                       # added: Frances, 2026-10-16)
    box_colour: str = "#E0D8D0"        # pop-up box: nude, from Frances's palette
    box_text_colour: str = "#2D2E30"   # pop-up text on the box: charcoal
    grade: str = ""                    # colour change on the footage: warm, cool, soft, natural, moody or vivid
    animation: str = "bounce"          # bounce, fade, slide-up, drop, wipe or type
    sound: str = "pop"                 # a sound in engine/sounds ("" = no sounds at all: b-roll reels, Frances 2026-10-11)
    position: str = "middle"           # middle or top
    popup_style: str = "box"           # box or plain, or tape, bubble, note, outline or underline
    popup_tilt: float = 0              # degrees the pop-up leans up to the right, like a stuck-on note (0 = straight)
    popup_lower: float = 0             # extra space above the pop-up, to sit it lower on the screen
    popup_words: bool = True           # False: the pop-up's box, tape or bubble without its words (to type them on)
    popup_after: float = 0             # seconds before the pop-up arrives (0 = the standard POPUP_AFTER)
    popup_ink: str = ""                # a call to action's words straight on the video ("" = the main text colour, or white)


def kit_look(kit, **changes):
    """The look for a brand kit from brand_kits.json, with any of the student's own choices on top."""
    with open(os.path.join(HERE, "brand_kits.json"), encoding="utf-8") as f:
        k = json.load(f)["kits"][kit]
    c = k["colours"]
    ribbon = k["text_style"] == "ribbon"
    # The b-roll kits (rebuilt 2026-10-11) are clean: no sound effects, a quick fade, nothing leaning,
    # footage as filmed. Words sit straight on the video or on highlight strips.
    look = Look(heading_font=k["fonts"]["headings"], caption_font=k["fonts"]["captions"],
                text_style=k["text_style"], text_case=k.get("text_case", "as written"),
                text_colour=c["strip_text"] if ribbon else c["text"],
                highlight=c["strip_highlight"] if ribbon else c["highlight"],
                behind_text=c["strip"] if ribbon else "", lines="", outline="",
                box_colour=c["popup_box"], box_text_colour=c["popup_text"], grade=k.get("grade", ""),
                animation=k.get("animation", "fade"), sound=k.get("sound", ""),
                popup_style=k.get("popup", "box"), popup_tilt=0)
    return replace(look, **{key: value for key, value in changes.items() if value})


def look_from(kit=None, my_colours=None, **choices):
    """A kit's look (or the standard look), fitted to the student's colours, with their choices on top."""
    choices = {key: value for key, value in choices.items() if value is not None}   # "" and 0 are real choices (no sound, no lean)
    look = kit_look(kit) if kit else Look()
    if my_colours:
        look = fit_colours(look, my_colours)
    return replace(look, **choices)


# ---------------------------------------------------------------------------
# Colours: fitting a student's brand colours onto a kit, and keeping it readable.
# ---------------------------------------------------------------------------
def luminance(colour):
    """How light a colour looks, from 0 (black) to 1 (white)."""
    def channel(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = ImageColor.getrgb(colour)[:3]
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast(a, b):
    """The standard readability score for two colours. 4.5 or more is easy to read."""
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def mix(colour, towards, amount):
    r1, g1, b1 = ImageColor.getrgb(colour)[:3]
    r2, g2, b2 = ImageColor.getrgb(towards)[:3]
    return "#{:02X}{:02X}{:02X}".format(*(round(x + (y - x) * amount) for x, y in ((r1, r2), (g1, g2), (b1, b2))))


def colourfulness(colour):
    r, g, b = (v / 255 for v in ImageColor.getrgb(colour)[:3])
    return colorsys.rgb_to_hsv(r, g, b)[1]


def readable_on(background, preferred, needed=4.5):
    """The preferred text colour if it reads well on the background, otherwise near-black or white."""
    if contrast(preferred, background) >= needed:
        return preferred
    return max(("#1E1E1E", "#FFFFFF"), key=lambda option: contrast(option, background))


def nudge_until(colour, background, needed, towards):
    """Lighten or darken a colour, a little at a time, until it stands out from the background."""
    for step in range(11):
        candidate = mix(colour, towards, step / 10)
        if contrast(candidate, background) >= needed:
            return candidate
    return towards


def fit_colours(look, colours):
    """Put a student's brand colours into a kit's colour jobs, keeping every pairing readable."""
    colours = [c.upper() for c in colours if re.fullmatch(r"#[0-9A-Fa-f]{6}", c.strip())]
    if not colours:
        return look
    by_lightness = sorted(colours, key=luminance)
    darkest, lightest = by_lightness[0], by_lightness[-1]
    accent = max(colours, key=colourfulness)
    if colourfulness(accent) < 0.15:
        accent = None
    new = replace(look)

    if look.text_style in ("card", "ribbon"):
        new.behind_text = lightest
        new.text_colour = readable_on(lightest, darkest)
        new.highlight = nudge_until(accent or darkest, lightest, 3, "#000000")
        new.box_colour = accent if (look.text_style == "ribbon" and accent) else darkest
        new.box_text_colour = readable_on(new.box_colour, lightest)
    elif look.text_style == "panel":
        new.behind_text = darkest
        new.text_colour = readable_on(darkest, lightest)
        new.highlight = nudge_until(accent or lightest, darkest, 3, "#FFFFFF")
        new.box_colour = lightest
        new.box_text_colour = readable_on(lightest, darkest)
    else:  # words straight on the video
        light_enough = accent or lightest
        while luminance(light_enough) < 0.35:
            light_enough = mix(light_enough, "#FFFFFF", 0.15)
        new.highlight = light_enough
        new.box_colour = lightest
        new.box_text_colour = readable_on(lightest, darkest)
        if look.lines:
            new.lines = light_enough
        if look.outline:
            new.outline = darkest if luminance(darkest) < 0.15 else mix(darkest, "#000000", 0.5)
    return new


# ---------------------------------------------------------------------------
# Fonts and drawing words
# ---------------------------------------------------------------------------
# Each font family: the file in engine/fonts, its settings for the main text and
# for pop-ups, and how big it looks next to the others (some fonts run small).
FONTS = {
    "DM Sans": ("DMSans.ttf", {}, {}, 1.0),
    "Playfair Display": ("PlayfairDisplay.ttf", {"Weight": 700}, {"Weight": 600}, 1.0),
    "DM Serif Display": ("DMSerifDisplay.ttf", {}, {}, 1.05),
    "Inter": ("Inter.ttf", {"Optical size": 24, "Weight": 700}, {"Optical size": 24, "Weight": 600}, 0.95),
    "Cormorant Garamond": ("CormorantGaramond.ttf", {"Weight": 700}, {"Weight": 700}, 1.18),
    "Montserrat": ("Montserrat.ttf", {"Weight": 700}, {"Weight": 600}, 0.92),
    "Fraunces": ("Fraunces.ttf", {"Optical Size": 72, "Weight": 600, "Softness": 0, "Wonky": 0},
                 {"Optical Size": 24, "Weight": 600, "Softness": 0, "Wonky": 0}, 1.0),
    "Poppins": ("Poppins-SemiBold.ttf", {}, {}, 0.92),
    "Bodoni Moda": ("BodoniModa.ttf", {"Weight": 700, "Optical size": 28}, {"Weight": 600, "Optical size": 28}, 1.05),
    "Jost": ("Jost.ttf", {"Weight": 600}, {"Weight": 500}, 1.0),
    "Outfit": ("Outfit.ttf", {"Weight": 800}, {"Weight": 600}, 0.95),
    "Caveat": ("Caveat.ttf", {"Weight": 700}, {"Weight": 700}, 1.6),  # handwritten; runs small, so it's scaled up
    # Pop-up writing (added 2026-10-10). The last number evens out how big each one looks.
    "Special Elite": ("SpecialElite.ttf", {}, {}, 1.05),        # inky old typewriter (Apache 2.0)
    "Courier Prime": ("CourierPrime.ttf", {}, {}, 0.98),        # crisp typewriter (OFL)
    "Patrick Hand": ("PatrickHand.ttf", {}, {}, 1.12),          # neat handwriting (OFL)
    "Indie Flower": ("IndieFlower.ttf", {}, {}, 1.3),           # round, childlike "baby writing" (OFL)
    "Reenie Beanie": ("ReenieBeanie.ttf", {}, {}, 1.7),         # quick pencil scribble (OFL)
    "Permanent Marker": ("PermanentMarker.ttf", {}, {}, 1.02),  # bold felt-tip marker (Apache 2.0)
    "Shadows Into Light": ("ShadowsIntoLight.ttf", {}, {}, 1.25),  # thin, neat pen handwriting (OFL)
}
FALLBACK_FONTS = ["/System/Library/Fonts/HelveticaNeue.ttc", r"C:\Windows\Fonts\arialbd.ttf"]

# The clinic's own fonts from their brand book (My Content/brand/fonts), usable by name everywhere.
try:
    import brand_book
    for _name, _path in brand_book.font_files().items():
        FONTS.setdefault(_name, (_path, {}, {}, 1.0))
except Exception:
    pass
# Fonts from the engine extras they've unlocked (My Content/.extras: design drops unlocked with a code, part of the content plan subscription), usable by name too.
try:
    import extras
    for _name, _spec in extras.fonts().items():
        FONTS.setdefault(_name, _spec)
except Exception:
    pass
EMOJI_FONTS = {
    "Darwin": ("/System/Library/Fonts/Apple Color Emoji.ttc", 160),  # Apple's emoji only come in set sizes
    "Windows": (r"C:\Windows\Fonts\seguiemj.ttf", 109),
}

# An emoji, including skin tones and emoji joined together (like ✌🏼).
EMOJI = re.compile(
    "(?:[\U0001F1E6-\U0001F1FF]{2}"
    "|[\u2300-\u23FF\u2600-\u27BF\u2B00-\u2BFF\U0001F000-\U0001FAFF]\uFE0F?[\U0001F3FB-\U0001F3FF]?"
    "(?:\u200D[\u2600-\u27BF\U0001F000-\U0001FAFF]\uFE0F?[\U0001F3FB-\U0001F3FF]?)*)"
)


def load_font(family, size, role):
    """Open a font at a size, set to the right weight for the main text ("heading") or a pop-up ("caption")."""
    file, heading, caption, scale = FONTS.get(family, FONTS["DM Sans"])
    path = os.path.join(HERE, "fonts", file)
    if not os.path.exists(path):
        path = next(p for p in FALLBACK_FONTS if os.path.exists(p))
    font = ImageFont.truetype(path, round(size * scale))
    settings = heading if role == "heading" else caption
    if settings:
        axes = font.get_variation_axes()
        names = [a["name"].decode() if isinstance(a["name"], bytes) else a["name"] for a in axes]
        font.set_variation_by_axes([settings.get(name, axis["default"]) for name, axis in zip(names, axes)])
    return font


def split_runs(word):
    """Split a word into plain text and emoji pieces, e.g. 'autumn?👀' -> ['autumn?', '👀']."""
    runs, last = [], 0
    for match in EMOJI.finditer(word):
        if match.start() > last:
            runs.append(("text", word[last:match.start()]))
        runs.append(("emoji", match.group()))
        last = match.end()
    if last < len(word):
        runs.append(("text", word[last:]))
    return runs


def shouting(piece):
    """True for a word written in CAPITALS in the plan, like DONE or ONCE."""
    letters = [c for c in piece if c.isalpha()]
    return len(letters) >= 2 and all(c.isupper() for c in letters)


class Writer:
    """Measures and draws words in one font and size, emoji included."""

    def __init__(self, size, family="DM Sans", role="heading", capitals=False, outline=""):
        self.size = size
        self.font = load_font(family, size, role)
        self.capitals = capitals
        # Spaced-out capitals look elegant; plain capitals just get a touch of room.
        self.tracking = size * (0.1 if capitals == "spaced" else 0.02 if capitals else 0)
        self.outline = outline
        emoji_path, self.emoji_render_size = EMOJI_FONTS.get(platform.system(), (None, None))
        self.emoji_font = (
            ImageFont.truetype(emoji_path, self.emoji_render_size)
            if emoji_path and os.path.exists(emoji_path) else None
        )
        self.emoji_height = round(size * 1.05)

    def shown(self, piece):
        return piece.upper() if self.capitals else piece

    def measure(self, text):
        # Words in capitals need a wider gap between them than ordinary words.
        word_gap = self.size * 0.14 if self.capitals and text == " " else 0
        return self.font.getlength(text) + self.tracking * len(text) + word_gap

    def emoji_picture(self, emoji):
        if not self.emoji_font:
            return None
        left, top, right, bottom = self.emoji_font.getbbox(emoji)
        picture = Image.new("RGBA", (right - left, bottom - top))
        ImageDraw.Draw(picture).text((-left, -top), emoji, font=self.emoji_font, embedded_color=True)
        width = round(picture.width * self.emoji_height / picture.height)
        return picture.resize((width, self.emoji_height), Image.LANCZOS)

    def width(self, word):
        total = 0
        for kind, piece in split_runs(word):
            if kind == "text":
                total += self.measure(self.shown(piece))
            else:
                picture = self.emoji_picture(piece)
                total += picture.width if picture else 0
        return total

    def line_width(self, line):
        return sum(self.width(word) for word in line) + self.measure(" ") * (len(line) - 1)

    def put_text(self, draw, x, baseline, text, fill):
        stroke = {"stroke_width": max(2, round(self.size * 0.05)), "stroke_fill": self.outline} if self.outline else {}
        if not self.tracking:
            draw.text((x, baseline), text, font=self.font, fill=fill, anchor="ls", **stroke)
            return
        # Each letter sits where it would in the whole word (so pairs like "AY" keep their spacing), plus the extra room.
        for i, letter in enumerate(text):
            at = x + self.font.getlength(text[:i]) + self.tracking * i
            draw.text((at, baseline), letter, font=self.font, fill=fill, anchor="ls", **stroke)

    def draw_word(self, canvas, x, baseline, word, colour, shadow=None, highlight=""):
        """colour None leaves the word's space but draws nothing (a blank pop-up to type onto)."""
        for kind, piece in split_runs(word):
            if colour is None:
                if kind == "text":
                    x += self.measure(self.shown(piece))
                else:
                    picture = self.emoji_picture(piece)
                    x += picture.width if picture else 0
                continue
            if kind == "text":
                text = self.shown(piece)
                if shadow:      # a dark shadow under light words, a light one under black words
                    shade = (255, 255, 255, 110) if luminance(colour) < 0.2 else (0, 0, 0, 140)
                    self.put_text(ImageDraw.Draw(shadow), x, baseline + 2, text, shade)
                fill = highlight if highlight and shouting(piece) else colour
                self.put_text(ImageDraw.Draw(canvas), x, baseline, text, fill)
                x += self.measure(text)
            else:
                picture = self.emoji_picture(piece)
                if picture:
                    canvas.alpha_composite(picture, (round(x), round(baseline - self.emoji_height * 0.86)))
                    x += picture.width
        return x

    def draw_lines(self, canvas, lines, left, right, top, colour, shadow=None, highlight="",
                   spacing=LINE_SPACING, ribbon=""):
        """Draw wrapped lines centred between left and right, starting at top. A ribbon colour puts
        each line on its own strip of colour."""
        line_height = self.size * spacing
        space = self.measure(" ")
        y = top
        for line in lines:
            if line is None:
                y += line_height * 0.5
                continue
            line_width = self.line_width(line)
            x = left + (right - left - line_width) / 2
            baseline = y + (line_height + self.size * 0.7) / 2  # letters sit in the middle of their line
            if ribbon:
                ImageDraw.Draw(canvas).rounded_rectangle(
                    (x - 16, baseline - self.size * 0.95, x + line_width + 16, baseline + self.size * 0.33),
                    radius=round(self.size * 0.22), fill=ribbon)
            for word in line:
                x = self.draw_word(canvas, x, baseline, word, colour, shadow, highlight) + space
            y += line_height
        return y


def fill_lines(writer, words, width):
    """Each line as full as it'll go, the rest on the next."""
    lines, line = [], []
    for word in words:
        if line and writer.line_width(line + [word]) > width:
            lines.append(line)
            line = []
        line.append(word)
    if line:
        lines.append(line)
    return lines


def lone_word(lines):
    """True when a paragraph on more than one line has a line holding one word on its own."""
    return len(lines) > 1 and any(len(line) == 1 for line in lines)


def even_lines(writer, words, max_width):
    """The same number of lines as filling them up would need, but as even as they'll go, so a sentence never
    ends on one word on its own (Frances, 2026-11-02: "it needs to be uniform so it looks right... the two lines
    marry up"). Found by narrowing the width until one more line would be needed, then, if that still leaves a
    word on its own, the narrowest layout with the same number of lines that doesn't."""
    lines = fill_lines(writer, words, max_width)
    if len(lines) < 2:
        return lines
    low, high = int(max(writer.line_width([w]) for w in words)), int(max_width)
    while low < high:
        middle = (low + high) // 2
        if len(fill_lines(writer, words, middle)) <= len(lines):
            high = middle
        else:
            low = middle + 1
    even = fill_lines(writer, words, high)
    if lone_word(even):
        for width in range(high, int(max_width) + 1, 2):
            other = fill_lines(writer, words, width)
            if len(other) == len(even) and not lone_word(other):
                return other
    return even


def has_lone_word(lines):
    """For wrap()'s lines (None between paragraphs): does any paragraph leave a word on its own?"""
    paragraph = []
    for line in list(lines) + [None]:
        if line is None:
            if lone_word(paragraph):
                return True
            paragraph = []
        else:
            paragraph.append(line)
    return False


def tidy_size(make_writer, text, max_width, size, smallest=0.85):
    """The writer and lines for text at `size`, or a little smaller (down to `smallest` of it) when that's what
    it takes for no word to sit on a line of its own (Frances: "either you make the text smaller so it all fits
    on one line..."). make_writer(size) gives a Writer."""
    writer = make_writer(size)
    lines = wrap(writer, text, max_width)
    for smaller in range(size - 2, int(size * smallest) - 1, -2):
        if not has_lone_word(lines):
            break
        candidate = make_writer(smaller)
        candidate_lines = wrap(candidate, text, max_width)
        if not has_lone_word(candidate_lines):
            return candidate, candidate_lines
    return writer, lines


def wrap(writer, text, max_width):
    """Break the text into even lines that fit. A blank line in the text starts a new paragraph."""
    lines = []
    for paragraph in text.split("\n"):
        if not paragraph.strip():
            lines.append(None)  # paragraph gap
            continue
        words = []
        # Words split at ordinary spaces only, so a non-breaking space (\u00a0) keeps "15 to 20" together.
        for word in re.split(r"[ \t]+", paragraph.strip()):
            # An emoji never starts a line on its own: it stays with the word before it.
            if words and all(kind == "emoji" for kind, _ in split_runs(word)):
                words[-1] += " " + word
            else:
                words.append(word)
        lines += even_lines(writer, words, max_width)
    return lines


def block_height(writer, lines, spacing=LINE_SPACING):
    line_height = writer.size * spacing
    return sum(line_height if line else line_height * 0.5 for line in lines)


def fit_text(text, look):
    """Find the biggest size where the main text fits the position's box, and where it all sits."""
    left, top, right, bottom = TEXT_POSITIONS[look.position]
    pad_x, pad_y = {"card": (30, 24), "panel": (34, 28)}.get(look.text_style, (0, 0))
    rule_gap = 22 if look.lines else 0
    spacing = RIBBON_SPACING if look.text_style == "ribbon" else LINE_SPACING
    capitals = ("spaced" if look.lines else True) if look.text_case == "capitals" else False
    room_w = right - left - pad_x * 2
    room_h = bottom - top - pad_y * 2 - rule_gap * 2
    best = None
    for size in range(BIGGEST_TEXT, SMALLEST_TEXT - 1, -2):
        writer = Writer(size, look.heading_font, "heading", capitals, look.outline)
        lines = wrap(writer, text, room_w)
        height = block_height(writer, lines, spacing)
        if height > room_h:
            continue
        best = best or (writer, lines, height)
        # A word on a line of its own: a little smaller (no less than 85% of the biggest that fits) if that
        # puts it right (Frances, 2026-11-02).
        if not has_lone_word(lines) or size < best[0].size * 0.85:
            break
    if best and (has_lone_word(lines) or height > room_h):
        writer, lines, height = best
    total_h = height + pad_y * 2 + rule_gap * 2
    block_top = top + (bottom - top - total_h) / 2
    return SimpleNamespace(writer=writer, lines=lines, spacing=spacing, left=left, right=right, room_w=room_w,
                           pad_x=pad_x, pad_y=pad_y, rule_gap=rule_gap, total_h=total_h, block_top=block_top,
                           text_top=block_top + pad_y + rule_gap, centre_x=(left + right) / 2,
                           widest=max(writer.line_width(line) for line in lines if line))


def draw_backing(canvas, fit, look, text_height):
    """The card or panel behind the main text, sized for text_height of words (so it can grow as each
    line arrives), and the thin lines above and below."""
    block_top, widest, centre_x = fit.block_top, fit.widest, fit.centre_x
    if look.text_style in ("card", "panel"):
        draw_box(canvas, (centre_x - widest / 2 - fit.pad_x, block_top, centre_x + widest / 2 + fit.pad_x,
                          block_top + text_height + fit.pad_y * 2 + fit.rule_gap * 2), look)
    if look.lines:
        draw = ImageDraw.Draw(canvas)
        for y in (block_top, block_top + fit.total_h):
            draw.line((centre_x - widest / 2, y, centre_x + widest / 2, y), fill=look.lines, width=3)


def draw_box(canvas, box, look):
    """One card (solid, with a soft shadow) or panel (see-through) behind some words."""
    if look.text_style == "card":
        shade = Image.new("RGBA", canvas.size)
        ImageDraw.Draw(shade).rounded_rectangle((box[0], box[1] + 6, box[2], box[3] + 6), 24, fill=(0, 0, 0, 80))
        canvas.alpha_composite(shade.filter(ImageFilter.GaussianBlur(10)))
        ImageDraw.Draw(canvas).rounded_rectangle(box, 24, fill=ImageColor.getrgb(look.behind_text)[:3] + (245,))
    else:
        ImageDraw.Draw(canvas).rounded_rectangle(box, 30, fill=ImageColor.getrgb(look.behind_text)[:3] + (190,))


def separate_boxes(text, look):
    """Each line of the plan in its own card or panel, each hugging its words, stacked with a gap.
    Returns one picture per line (its box and its words) and where the last box ends."""
    left, top, right, bottom = BOXES_POSITIONS[look.position]
    pad_x, pad_y = {"card": (30, 24), "panel": (34, 28)}[look.text_style]
    capitals = ("spaced" if look.lines else True) if look.text_case == "capitals" else False
    beats = [part for part in text.split("\n") if part.strip()]
    for size in range(BIGGEST_TEXT, SMALLEST_TEXT - 1, -2):
        writer = Writer(size, look.heading_font, "heading", capitals, look.outline)
        wrapped = [wrap(writer, beat, right - left - pad_x * 2) for beat in beats]
        heights = [block_height(writer, lines) + pad_y * 2 for lines in wrapped]
        total = sum(heights) + BOX_GAP * (len(beats) - 1)
        if total <= bottom - top:
            break
    y, centre_x, layers = top + (bottom - top - total) / 2, (left + right) / 2, []
    for lines, height in zip(wrapped, heights):
        widest = max(writer.line_width(line) for line in lines if line)
        layer = Image.new("RGBA", (WIDTH, HEIGHT))
        draw_box(layer, (centre_x - widest / 2 - pad_x, y, centre_x + widest / 2 + pad_x, y + height), look)
        writer.draw_lines(layer, lines, left + pad_x, right - pad_x, y + pad_y, look.text_colour, None, look.highlight)
        layers.append(layer)
        y += height + BOX_GAP
    return layers, y - BOX_GAP


def draw_words(canvas, fit, look, lines, top):
    """Some of the main text's lines, starting at top, in the look's style."""
    shadow = Image.new("RGBA", (WIDTH, HEIGHT)) if look.text_style == "plain" and look.shadow else None
    words = Image.new("RGBA", (WIDTH, HEIGHT))
    ribbon = look.behind_text if look.text_style == "ribbon" else ""
    fit.writer.draw_lines(words, lines, fit.left + fit.pad_x, fit.right - fit.pad_x, top, look.text_colour, shadow,
                          look.highlight, fit.spacing, ribbon)
    if shadow:
        if look.glow:
            canvas.alpha_composite(haze(words, look.glow))
        canvas.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(4)))
    canvas.alpha_composite(words)


HAZE_BLUR = 14            # how far the soft shade behind words spreads


def haze(words, strength, blur=HAZE_BLUR):
    """A soft dark haze in the shape of the words, to sit behind them so they read on bright footage with no
    outline (Frances, 2026-10-13: "I don't want that black outline... make it softer")."""
    shade = Image.new("RGBA", words.size)
    shade.paste((0, 0, 0, round(255 * strength)), (0, 0, *words.size), mask=words.getchannel("A"))
    return shade.filter(ImageFilter.GaussianBlur(blur))


def with_haze(picture, strength, blur=HAZE_BLUR):
    """A see-through picture of words with the soft haze behind, with room round the edge for it."""
    pad = blur * 2
    out = Image.new("RGBA", (picture.width + pad * 2, picture.height + pad * 2))
    out.paste(picture, (pad, pad))
    shade = haze(out, strength, blur)
    shade.alpha_composite(out)
    return shade


def text_layer(text, look=Look()):
    """Draw the main text on a see-through 1080 x 1920 picture, as big as fits in the position's box,
    in the look's style. Also says where the text ends, so the pop-up can go underneath."""
    fit = fit_text(text, look)
    canvas = Image.new("RGBA", (WIDTH, HEIGHT))
    draw_backing(canvas, fit, look, fit.total_h - fit.pad_y * 2 - fit.rule_gap * 2)
    draw_words(canvas, fit, look, fit.lines, fit.text_top)
    return canvas, fit.block_top + fit.total_h


def beat_numbers(text, writer, max_width):
    """Which beat (line of the plan) each wrapped line belongs to. A gap counts with the line before it."""
    numbers, beat = [], -1
    for paragraph in text.split("\n"):
        if not paragraph.strip():
            numbers.append(max(beat, 0))
            continue
        beat += 1
        numbers += [beat] * len(wrap(writer, paragraph, max_width))
    return numbers


def beat_layers(text, look=Look()):
    """For a reel where each line of the plan arrives in turn: a picture of what sits behind the words
    at each step (the thin lines; None when there's nothing), a picture of each line's words, and where
    the whole text ends. Cards and panels: each line gets its own box (Frances's rule)."""
    if look.text_style in ("card", "panel"):  # each line arrives in its own box
        layers, bottom = separate_boxes(text, look)
        return [None] * len(layers), layers, bottom
    fit = fit_text(text, look)
    numbers = beat_numbers(text, fit.writer, fit.room_w)
    backings, words = [], []
    for beat in range(max(numbers) + 1):
        first = numbers.index(beat)
        after = len(numbers) - numbers[::-1].index(beat)
        backing = None
        if look.text_style in ("card", "panel") or look.lines:
            backing = Image.new("RGBA", (WIDTH, HEIGHT))
            draw_backing(backing, fit, look, block_height(fit.writer, fit.lines[:after], fit.spacing))
        backings.append(backing)
        layer = Image.new("RGBA", (WIDTH, HEIGHT))
        top = fit.text_top + block_height(fit.writer, fit.lines[:first], fit.spacing)
        draw_words(layer, fit, look, fit.lines[first:after], top)
        words.append(layer)
    return backings, words, fit.block_top + fit.total_h


def read_time(text):
    """Roughly how long a line takes to read, in seconds."""
    return min(3.2, max(1.4, 0.32 * len(text.split()) + 0.6))


def popup_picture(text, look=Look(), max_width=700, size=POPUP_TEXT):
    """The call to action, either on its own coloured box or as plain text in the main text colour.
    A tilt leans the whole pop-up a little, for a fun, handwritten feel. size: the text size
    (talking heads use bigger pop-ups than b-roll reels)."""
    picture = straight_popup(text, look, max_width, size)
    if look.popup_tilt:
        picture = picture.rotate(look.popup_tilt, resample=Image.BICUBIC, expand=True)
    return picture


def straight_popup(text, look, max_width, size=POPUP_TEXT):
    plain = look.popup_style in ("plain", "underline")
    writer = Writer(size, look.caption_font, "caption", outline=look.outline if plain else "")
    if "\n" not in text and len(wrap(writer, text, WIDEST_ONE_LINE_POPUP)) == 1:
        max_width = WIDEST_ONE_LINE_POPUP  # just a little too wide: keep it on one line
    lines = wrap(writer, text, max_width)
    if look.popup_style in ("plain", "underline"):
        room = round(writer.font.size * 0.6)  # headroom, so tall handwritten letters are never clipped at the top
        height = round(block_height(writer, lines)) + 16 + room
        canvas = Image.new("RGBA", (max_width + 24, height))
        shadow = Image.new("RGBA", canvas.size)
        writer.draw_lines(canvas, lines, 12, 12 + max_width, room, ink_on_video(look) if look.popup_words else None,
                          shadow if look.shadow else None)
        shadow = shadow.filter(ImageFilter.GaussianBlur(4))
        shadow.alpha_composite(canvas)
        if not look.popup_words:  # nothing but the space the words would take
            box = writer.line_width(max(lines, key=lambda line: writer.line_width(line) if line else 0))
            picture = Image.new("RGBA", (round(box) + 8, height))
        else:
            picture = shadow.crop(shadow.getbbox())
            if look.glow:
                picture = with_haze(picture, look.glow)
        return underline(picture, look) if look.popup_style == "underline" else picture
    if look.popup_style in SHAPES:
        return shaped_popup(text, writer, lines, look)
    pad_x, pad_y = 32, 22
    widest = max(writer.line_width(line) for line in lines if line)
    box_w = round(widest + pad_x * 2)
    box_h = round(block_height(writer, lines) + pad_y * 2 - writer.size * (LINE_SPACING - 1))
    margin = 12  # room for the soft shadow
    picture = Image.new("RGBA", (box_w + margin * 2, box_h + margin * 2))
    shade = Image.new("RGBA", picture.size)
    ImageDraw.Draw(shade).rounded_rectangle((margin, margin + 4, margin + box_w, margin + box_h + 4), 26, fill=(0, 0, 0, 70))
    picture.alpha_composite(shade.filter(ImageFilter.GaussianBlur(6)))
    ImageDraw.Draw(picture).rounded_rectangle((margin, margin, margin + box_w, margin + box_h), 26,
                                              fill=ImageColor.getrgb(look.box_colour)[:3] + (240,))
    writer.draw_lines(picture, lines, margin, margin + box_w, margin + pad_y - writer.size * (LINE_SPACING - 1) / 2,
                      look.box_text_colour if look.popup_words else None)
    return picture


def ink_on_video(look):
    """Pop-up writing that sits straight on the video: the main text colour when that's on the video
    too; kits with cards keep white."""
    return look.popup_ink or (look.text_colour if look.text_style == "plain" else "#FFFFFF")


def underline(picture, look):
    """A hand-drawn pen stroke under the pop-up's writing, in the pop-up colour, rising a little at the end."""
    width = 13
    canvas = Image.new("RGBA", (picture.width + 24, picture.height + 46))
    base = picture.height + 12
    points = []
    for i in range(41):
        u = i / 40
        x = 12 + picture.width * (0.04 + 0.92 * u)
        points.append((x, base + 11 * (1 - (2 * u - 1) ** 2) - 18 * u ** 3))
    stroke = Image.new("RGBA", canvas.size)
    draw = ImageDraw.Draw(stroke)
    draw.line(points, fill=look.box_colour, width=width, joint="curve")
    for x, y in (points[0], points[-1]):  # round pen ends
        draw.ellipse((x - width / 2, y - width / 2, x + width / 2, y + width / 2), fill=look.box_colour)
    shade = Image.new("RGBA", canvas.size)
    shade.paste((0, 0, 0, 110), mask=stroke.getchannel("A"))
    canvas.alpha_composite(shade.filter(ImageFilter.GaussianBlur(4)), (0, 2))
    canvas.alpha_composite(stroke)
    canvas.alpha_composite(picture, (12, 0))
    return canvas


def shaped_popup(text, writer, lines, look):
    """The call to action on torn tape, in a speech bubble, on a sticky note or in an outlined pill."""
    style = look.popup_style
    pad_x, pad_y, margin = SHAPES[style]
    widest = max(writer.line_width(line) for line in lines if line)
    box_w = round(widest + pad_x * 2)
    box_h = round(block_height(writer, lines) + pad_y * 2 - writer.size * (LINE_SPACING - 1))
    picture = Image.new("RGBA", (box_w + margin * 2, box_h + margin * 2))
    x0, y0, x1, y1 = margin, margin, margin + box_w, margin + box_h
    fill = ImageColor.getrgb(look.box_colour)[:3]
    shape = Image.new("RGBA", picture.size)
    draw = ImageDraw.Draw(shape)
    ink, shadow_offset, shadow_blur, shadow_strength = look.box_text_colour, (0, 4), 6, 70

    if style == "tape":
        # Torn ends: the left and right edges zig-zag a little, the same way every time for the same words.
        rng, steps = random.Random(text), 8
        right_edge = [(x1 + rng.uniform(-7, 7), y0 + box_h * i / steps) for i in range(steps + 1)]
        left_edge = [(x0 + rng.uniform(-7, 7), y1 - box_h * i / steps) for i in range(steps + 1)]
        draw.polygon(right_edge + left_edge, fill=fill + (228,))
        shadow_offset, shadow_blur, shadow_strength = (0, 3), 4, 55
    elif style == "bubble":
        draw.rounded_rectangle((x0, y0, x1, y1), 30, fill=fill + (245,))
        tail_x = x0 + box_w * 0.18
        draw.polygon([(tail_x, y1 - 2), (tail_x - 14, y1 + 28), (tail_x + 34, y1 - 2)], fill=fill + (245,))
    elif style == "paper":
        # Ripped on every side: little irregular bites all the way round, the same for the same words.
        rng, step, bite = random.Random(text + "paper"), 11, 4.5
        outline = []
        for (ax, ay), (bx, by) in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
            n = max(2, round(max(abs(bx - ax), abs(by - ay)) / step))
            for i in range(n):
                u = i / n
                jitter = rng.uniform(-bite, bite)
                outline.append((ax + (bx - ax) * u + (jitter if ax == bx else 0),
                                ay + (by - ay) * u + (jitter if ay == by else 0)))
        draw.polygon(outline, fill=fill + (252,))
        draw.line(outline + outline[:1], fill=ImageColor.getrgb(mix(look.box_colour, "#000000", 0.07)), width=2)
        shadow_offset, shadow_blur, shadow_strength = (0, 5), 7, 85
    elif style == "note":
        draw.rounded_rectangle((x0, y0, x1, y1), 8, fill=fill + (250,))
        band = ImageColor.getrgb(mix(look.box_colour, "#000000", 0.08))
        draw.rounded_rectangle((x0, y0, x1, y0 + 24), 8, fill=band)  # the sticky strip along the top
        draw.rectangle((x0, y0 + 12, x1, y0 + 24), fill=fill + (250,))
        shadow_offset, shadow_blur, shadow_strength = (6, 10), 10, 95
    else:  # outline: a pill drawn in the pop-up colour, lightly shaded inside so the words read on any video
        draw.rounded_rectangle((x0, y0, x1, y1), box_h / 2, fill=(0, 0, 0, 70), outline=fill + (255,), width=4)
        ink, shadow_strength = ink_on_video(look), 0

    if shadow_strength:
        shade = Image.new("RGBA", picture.size)
        shade.paste((0, 0, 0, shadow_strength), mask=shape.getchannel("A"))
        picture.alpha_composite(shade.filter(ImageFilter.GaussianBlur(shadow_blur)), shadow_offset)
    picture.alpha_composite(shape)
    words_top = y0 + pad_y - writer.size * (LINE_SPACING - 1) / 2 + (6 if style == "note" else 0)
    if not look.popup_words:
        return picture
    if style == "outline":
        words, shadow = Image.new("RGBA", picture.size), Image.new("RGBA", picture.size)
        writer.draw_lines(words, lines, x0, x1, words_top, ink, shadow)
        picture.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(4)))
        picture.alpha_composite(words)
    else:
        writer.draw_lines(picture, lines, x0, x1, words_top, ink)
    return picture


def popup_frames(text, below, folder, look=Look()):
    """Save the pop-up's arrival as a few full-frame pictures; the last one stays on screen."""
    picture = popup_picture(text, look)
    centre_y = min(below + POPUP_GAP + look.popup_lower + picture.height / 2, LOWEST_POPUP - picture.height / 2)
    if look.animation == "type" and look.popup_style == "plain":
        typed = typed_lines(text, look)
        if len(typed) > 1:
            return typed_frames(typed, below, folder, look)
    if look.animation in ("wipe", "type"):
        place = (round(WIDTH / 2 - picture.width / 2), round(centre_y - picture.height / 2))
        if look.animation == "wipe":  # drawn on smoothly: quick at first, then easing in
            cuts = [round(picture.width * (1 - (1 - (i + 1) / WIPE_FRAMES) ** 2)) for i in range(WIPE_FRAMES)]
        else:  # typed: one more letter each frame
            writer = Writer(POPUP_TEXT, look.caption_font, "caption")
            whole = writer.width(text)
            cuts = [min(picture.width, round(picture.width * writer.width(text[:i]) / whole) + 6)
                    for i in range(1, len(text) + 1)]
            cuts[-1] = picture.width
        for i, cut in enumerate(cuts):
            shown = picture.copy()
            alpha = shown.getchannel("A")
            ImageDraw.Draw(alpha).rectangle((cut, 0, picture.width, picture.height), fill=0)
            shown.putalpha(alpha)
            frame = Image.new("RGBA", (WIDTH, HEIGHT))
            frame.alpha_composite(shown, place)
            frame.save(os.path.join(folder, f"popup_{i:03d}.png"))
        return os.path.join(folder, "popup_%03d.png"), len(cuts)
    for i, (scale, drop, opacity) in enumerate(ANIMATIONS[look.animation]):
        frame = Image.new("RGBA", (WIDTH, HEIGHT))
        size = (max(1, round(picture.width * scale)), max(1, round(picture.height * scale)))
        sized = picture.resize(size, Image.LANCZOS)
        if opacity < 1:
            sized.putalpha(sized.getchannel("A").point(lambda a: round(a * opacity)))
        frame.alpha_composite(sized, (round(WIDTH / 2 - size[0] / 2), round(centre_y - size[1] / 2 + drop)))
        frame.save(os.path.join(folder, f"popup_{i:03d}.png"))
    return os.path.join(folder, "popup_%03d.png"), len(ANIMATIONS[look.animation])


def typed_lines(text, look):
    """The lines a plain call to action wraps onto, so a typed one can type each line in turn."""
    writer = Writer(POPUP_TEXT, look.caption_font, "caption", outline=look.outline)
    if "\n" not in text and len(wrap(writer, text, WIDEST_ONE_LINE_POPUP)) == 1:
        return [text]
    return [" ".join(line) for line in wrap(writer, text, 700) if line]


def typed_frames(lines, below, folder, look):
    """A plain call to action on two or more lines, typed one letter at a time: the first line, then the
    next underneath it, like someone typing."""
    pictures = [popup_picture(line, look) for line in lines]
    gap = round(POPUP_TEXT * 0.12)
    pad = HAZE_BLUR * 2 if look.glow else 0   # a soft shade's room round each line overlaps, so lines sit close
    height = sum(p.height - 2 * pad for p in pictures) + gap * (len(pictures) - 1)
    top = round(min(below + POPUP_GAP + look.popup_lower, LOWEST_POPUP - height))
    places, y = [], top
    for picture in pictures:
        places.append((round(WIDTH / 2 - picture.width / 2), y - pad))
        y += picture.height - 2 * pad + gap
    count = 0
    for n, (line, picture) in enumerate(zip(lines, pictures)):
        writer = Writer(POPUP_TEXT, look.caption_font, "caption")
        whole = writer.width(line) or 1
        for i in range(1, len(line) + 1):
            frame = Image.new("RGBA", (WIDTH, HEIGHT))
            for done in range(n):
                frame.alpha_composite(pictures[done], places[done])
            cut = picture.width if i == len(line) else min(picture.width, round(picture.width * writer.width(line[:i]) / whole) + 6)
            shown = picture.copy()
            alpha = shown.getchannel("A")
            ImageDraw.Draw(alpha).rectangle((cut, 0, picture.width, picture.height), fill=0)
            shown.putalpha(alpha)
            frame.alpha_composite(shown, places[n])
            frame.save(os.path.join(folder, f"popup_{count:03d}.png"))
            count += 1
    return os.path.join(folder, "popup_%03d.png"), count


# ---------------------------------------------------------------------------
# Footage, previews and the finished reel
# ---------------------------------------------------------------------------
def clip_length(clip):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", clip],
        capture_output=True, text=True, check=True,
    )
    return float(result.stdout.strip())


def timings(has_popup, start, available, popup_after=0):
    """When the pop-up appears, how long the reel is, and where in the clip to start."""
    after = popup_after or POPUP_AFTER
    popup_at = after if has_popup else None
    # A call to action that's there the whole time (it arrives at once) doesn't make the reel shorter.
    length = max(after, POPUP_AFTER if after < 1 else 0) + POPUP_STAYS if has_popup else SECONDS
    if start + length > available:
        start = max(0.0, available - length)
    if length > available:  # clip too short: squeeze the timings to fit
        if popup_at is not None:
            popup_at = popup_at * available / length
        length = available
    return popup_at, length, start


def sound_file(name):
    """The pop-up sound, made by make_sounds.py if it isn't there yet."""
    path = os.path.join(HERE, "sounds", f"{name}.wav")
    if not os.path.exists(path):
        subprocess.run([sys.executable, os.path.join(HERE, "make_sounds.py")], check=True, capture_output=True)
    return path


def grade_still(picture, grade):
    """The same colour change as the reel, for preview pictures."""
    settings, (r, g, b) = GRADES.get(grade, GRADES[""])
    values = dict(part.split("=") for part in settings[3:].split(":")) if settings else {}
    picture = ImageEnhance.Color(picture).enhance(float(values.get("saturation", 1)))
    picture = ImageEnhance.Contrast(picture).enhance(float(values.get("contrast", 1)))
    lift = round(float(values.get("brightness", 0)) * 255)
    keep = 1 - DARKNESS
    red, green, blue = picture.split()
    return Image.merge("RGB", [band.point(lambda v, m=m: round((v + lift) * m * keep))
                               for band, m in ((red, r), (green, g), (blue, b))])


def still_from(clip, seconds, grade=""):
    """One frame of the clip, filled to the reel shape, graded and darkened like the reel."""
    with tempfile.TemporaryDirectory() as tmp:
        frame = os.path.join(tmp, "frame.png")
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-ss", str(seconds), "-i", clip, "-frames:v", "1",
             "-vf", f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,crop={WIDTH}:{HEIGHT}", frame],
            check=True,
        )
        return grade_still(Image.open(frame).convert("RGB"), grade).convert("RGBA")


def finished_still(clip, seconds, texts, look, frame=None):
    """What the reel looks like once everything is on screen. frame: the clip's still, already taken
    (still_from), when making many pictures of the same moment."""
    still = frame.copy() if frame is not None else still_from(clip, seconds, look.grade)
    main, below = text_layer(texts[0], look)
    still.alpha_composite(main)
    if len(texts) > 1:
        with tempfile.TemporaryDirectory() as tmp:
            _, count = popup_frames(texts[1], below, tmp, look)
            still.alpha_composite(Image.open(os.path.join(tmp, f"popup_{count - 1:03d}.png")))
    return still


def preview(choice, clip, texts, out, start=0.0, look=Look(), my_colours=None):
    """Side-by-side stills from the student's own clip, one per option, so they can pick.
    choice is "position" (where the text sits), "popup" (how the call to action looks)
    or "colours" (a kit as designed, or in their own colours)."""
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    if choice == "position":
        options = [(replace(look, position="middle"), "middle of the screen"), (replace(look, position="top"), "top third")]
        texts = texts[:1]
    elif choice == "popup":
        options = [(replace(look, popup_style=name), label) for name, label in POPUP_STYLES.items()]
    else:
        options = [(look, "as designed"), (fit_colours(look, my_colours or []), "in your colours")]

    label_font = load_font("DM Sans", 22, "heading")
    small_w, small_h = WIDTH // 3, HEIGHT // 3
    sheet = Image.new("RGB", (len(options) * (small_w + 16), small_h + 44), "white")
    for i, (option, label) in enumerate(options):
        still = finished_still(clip, start + 2, texts, option)
        x = i * (small_w + 16)
        sheet.paste(still.convert("RGB").resize((small_w, small_h), Image.LANCZOS), (x, 0))
        ImageDraw.Draw(sheet).text((x + 4, small_h + 10), f"{'AB'[i]}: {label}", fill="black", font=label_font)
    sheet.save(out)
    return out


def footage_filter(look):
    """Fill the 1080 x 1920 frame, give it the look's colour change, then darken it.
    Red, green and blue are turned down by the same amount, so the clip keeps its colour."""
    keep = 1 - DARKNESS
    settings, (r, g, b) = GRADES.get(look.grade, GRADES[""])
    grade = f"{settings}," if settings else ""
    return (f"[0:v]scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,"
            f"crop={WIDTH}:{HEIGHT},setsar=1,{grade}format=gbrp,"
            f"colorchannelmixer=rr={r * keep:.3f}:gg={g * keep:.3f}:bb={b * keep:.3f}[clip]")


def strong_footage(original, clip, start, length, used=None):
    """The footage for the reel from the clip's strong moments, never across the gun lifting off (Frances,
    2026-11-02; clip_moments.py): (path, start). As it was when the clip has no moments marked."""
    import clip_moments
    if clip_moments.moments(original) is None:
        return clip, start
    return clip_moments.footage(original, start, length, used=used)


def make_reel(clip, texts, out, start=0.0, look=Look(), reveal=False, then=(), first_after=None, used=None):
    """reveal: each line of the main text (each piece between line breaks) arrives in turn.
    then and first_after: more pop-ups after the first, for a reel whose lines arrive in turn
    (see make_reveal_reel). used: what's been used of each clip already this month (clip_moments.py)."""
    original = clip
    clip = normal_colour(clip)          # iPhone HDR footage converted to normal colour first
    if (reveal or then) and sum(1 for part in texts[0].split("\n") if part.strip()) > 1:
        return make_reveal_reel(clip, texts, out, start, look, then, first_after, original, used)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    has_popup = len(texts) > 1
    popup_at, length, start = timings(has_popup, start, clip_length(clip), look.popup_after)
    clip, start = strong_footage(original, clip, start, length, used)

    with tempfile.TemporaryDirectory() as tmp:
        main_text, text_bottom = text_layer(texts[0], look)
        main_png = os.path.join(tmp, "main.png")
        main_text.save(main_png)

        inputs = ["-ss", str(start), "-t", str(length), "-i", clip,
                  "-loop", "1", "-t", str(length), "-i", main_png]
        # The footage, then the main text fades on straight away.
        steps = [
            footage_filter(look),
            "[1:v]format=rgba,fade=in:st=0:d=0.2:alpha=1[main]",
            "[clip][main]overlay=0:0:format=gbrp[v1]",
        ]
        last, sound = "v1", []
        if has_popup:
            # The call to action arrives at its time and stays there,
            # with its sound at the same moment.
            frames, _ = popup_frames(texts[1], text_bottom, tmp, look)
            inputs += ["-framerate", str(FPS), "-i", frames]
            steps += [
                f"[2:v]format=rgba,setpts=PTS+{popup_at}/TB[popup]",
                "[v1][popup]overlay=0:0:format=gbrp:eof_action=repeat[v2]",
            ]
            last = "v2"
            if look.sound:
                inputs += ["-i", sound_file(look.sound)]
                delay = round(popup_at * 1000)
                steps.append(f"[3:a]adelay={delay}|{delay},apad[sound]")
                sound = ["-map", "[sound]", "-c:a", "aac", "-b:a", "160k"]
        steps.append(f"[{last}]scale=out_color_matrix=bt709:out_range=tv,format=yuv420p[reel]")

        # Music gets added in CapCut, under the pop-up sound.
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", *inputs,
             "-filter_complex", ";".join(steps), "-map", "[reel]", *(sound or ["-an"]),
             "-t", str(length),
             "-c:v", "libx264", "-preset", "medium", "-crf", "18",
             "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
             "-movflags", "+faststart", out],
            check=True,
        )
    return out


def popup_bottom(text, below, look):
    """Where a pop-up placed under `below` ends, so another can sit underneath it."""
    picture = popup_picture(text, look)
    centre_y = min(below + POPUP_GAP + look.popup_lower + picture.height / 2, LOWEST_POPUP - picture.height / 2)
    return centre_y + picture.height / 2


def make_reveal_reel(clip, texts, out, start=0.0, look=Look(), then=(), first_after=None, original=None, used=None):
    """A reel where each line of the main text arrives in turn, with a soft tap, giving people time to
    read each one. A card or panel grows as the lines arrive. Then the pop-up, if there is one.
    then: more pop-ups after it, each (text, look, seconds after the one before), stacked underneath
    (Frances, 2026-10-13: "Want to know why?" on a nude box, then two seconds later "DM me the word
    AUDIT" as plain words). first_after: seconds from the last line to the first pop-up (otherwise the
    last line's reading time)."""
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    beats = [part for part in texts[0].split("\n") if part.strip()]
    popup = texts[1] if len(texts) > 1 else None
    times = [0.0]
    for beat in beats[:-1]:
        times.append(times[-1] + read_time(beat))
    popup_at = times[-1] + (first_after if first_after is not None else read_time(beats[-1]))
    then_at = []
    for _, _, delay in then if popup else ():
        then_at.append((then_at[-1] if then_at else popup_at) + delay)
    length = (then_at[-1] if then_at else popup_at) + (POPUP_STAYS if popup else HOLD)
    available = clip_length(clip)
    if start + length > available:
        start = max(0.0, available - length)
    if length > available:  # clip too short: squeeze the timings to fit
        squeeze = available / length
        times, popup_at, length = [t * squeeze for t in times], popup_at * squeeze, available
        then_at = [t * squeeze for t in then_at]
    clip, start = strong_footage(original or clip, clip, start, length, used)

    with tempfile.TemporaryDirectory() as tmp:
        backings, words, text_bottom = beat_layers(texts[0], look)
        inputs = ["-ss", str(start), "-t", f"{length:.3f}", "-i", clip]
        steps, last, n, sounds = [footage_filter(look)], "clip", 1, []

        def add_picture(picture, name):
            path = os.path.join(tmp, f"{name}.png")
            picture.save(path)
            inputs.extend(["-loop", "1", "-t", f"{length:.3f}", "-i", path])

        # The card or panel at each step, swapped for the next one as each line arrives.
        for k, picture in enumerate(backings):
            if picture is None:
                continue
            add_picture(picture, f"backing{k}")
            fade = ",fade=in:st=0:d=0.2:alpha=1" if k == 0 else ""
            until = f"*lt(t,{times[k + 1]:.3f})" if k + 1 < len(times) else ""
            steps.append(f"[{n}:v]format=rgba{fade}[b{k}]")
            steps.append(f"[{last}][b{k}]overlay=0:0:format=gbrp:enable='gte(t,{times[k]:.3f}){until}'[vb{k}]")
            last, n = f"vb{k}", n + 1
        # Each line's words fade on at their time and stay. A line in its own box also rises
        # gently into place, like a little pop-up.
        boxes = look.text_style in ("card", "panel")
        for k, picture in enumerate(words):
            add_picture(picture, f"words{k}")
            steps.append(f"[{n}:v]format=rgba,fade=in:st={times[k]:.3f}:d=0.25:alpha=1[w{k}]")
            rise = f"'if(lt(t,{times[k] + 0.3:.3f}),26*(1-(t-{times[k]:.3f})/0.3),0)':eval=frame" if boxes else "0"
            steps.append(f"[{last}][w{k}]overlay=0:{rise}:format=gbrp[vw{k}]")
            last, n = f"vw{k}", n + 1
            if k and look.sound:
                sounds.append((sound_file(BEAT_SOUND), times[k]))
        if popup:
            below = text_bottom
            stack = [(popup, look, popup_at)] + [(text, own, at) for (text, own, _), at in zip(then, then_at)]
            for k, (text, own, at) in enumerate(stack):
                folder = os.path.join(tmp, f"popup{k}")
                os.makedirs(folder)
                frames, _ = popup_frames(text, below, folder, own)
                inputs += ["-framerate", str(FPS), "-i", frames]
                steps.append(f"[{n}:v]format=rgba,setpts=PTS+{at:.3f}/TB[popup{k}]")
                steps.append(f"[{last}][popup{k}]overlay=0:0:format=gbrp:eof_action=repeat[vp{k}]")
                last, n = f"vp{k}", n + 1
                if own.sound:
                    sounds.append((sound_file(own.sound), at))
                below = popup_bottom(text, below, own) - POPUP_GAP + THEN_GAP   # the next one sits just underneath

        for path, at in sounds:
            inputs += ["-i", path]
            delay = round(at * 1000)
            steps.append(f"[{n}:a]adelay={delay}|{delay}[a{n}]")
            n += 1
        if sounds:
            mix = "".join(f"[a{k}]" for k in range(n - len(sounds), n))
            steps.append(f"{mix}amix=inputs={len(sounds)}:normalize=0,apad[sound]")
        steps.append(f"[{last}]scale=out_color_matrix=bt709:out_range=tv,format=yuv420p[reel]")

        # Music gets added in CapCut or Instagram, under these sounds.
        audio = ["-map", "[sound]", "-c:a", "aac", "-b:a", "160k"] if sounds else ["-an"]
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", *inputs,
             "-filter_complex", ";".join(steps), "-map", "[reel]", *audio,
             "-t", f"{length:.3f}", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
             "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
             "-movflags", "+faststart", out],
            check=True,
        )
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Make a text-on-video reel.")
    parser.add_argument("--clip", required=True, help="the video clip to use")
    parser.add_argument("--text", required=True, action="append",
                        help="text on screen; use it twice for main text then the call-to-action pop-up (\\n starts a new line)")
    parser.add_argument("--out", required=True, help="where to save the finished reel")
    parser.add_argument("--start", type=float, default=0.0, help="seconds into the clip to start from")
    parser.add_argument("--kit", help="a brand kit from brand_kits.json, e.g. soft-blush")
    parser.add_argument("--my-colours", help="the student's brand colours, e.g. '#E8C4C0,#5A3E36,#F7EFE9'")
    parser.add_argument("--position", choices=list(TEXT_POSITIONS), help="where the text sits")
    parser.add_argument("--popup-style", choices=ALL_POPUP_STYLES, help="how the call-to-action pop-up looks")
    parser.add_argument("--popup-colour", help="the pop-up box colour, as a colour code like #E0D8D0")
    parser.add_argument("--preview", choices=["position", "popup", "colours"],
                        help="instead of a reel, save a picture comparing the options for this choice")
    args = parser.parse_args()
    texts = [text.replace("\\n", "\n") for text in args.text]
    my_colours = [c.strip() for c in args.my_colours.split(",")] if args.my_colours else None
    if args.preview == "colours":
        base = look_from(args.kit, position=args.position, popup_style=args.popup_style)
        print(preview("colours", args.clip, texts, args.out, args.start, base, my_colours))
    else:
        look = look_from(args.kit, my_colours, position=args.position, popup_style=args.popup_style,
                         box_colour=args.popup_colour)
        if args.preview:
            print(preview(args.preview, args.clip, texts, args.out, args.start, look))
        else:
            print(make_reel(args.clip, texts, args.out, args.start, look))
