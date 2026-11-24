"""
The choices in the Reel Lookbook (Frances, 2026-10-11), for b-roll reels: the
words on a student's treatment clips. Students tick one in each section, then
save or copy their look for Claude, like the Talking Head Lookbook. These
replace the brand kits.

Every reel stays clean and natural, like text added in Instagram itself: no
sound effects, no bounces or leans, footage as filmed, and the words and call
to action kept clear of Instagram's buttons and caption.

make_reels.py turns a look into each reel's settings with reel_style().
"""

# Eight fonts for the words, each with a clean partner for the call to action.
FONTS = {
    "clean": {"name": "Clean", "words": "Poppins", "cta": "Poppins",
              "about": "Simple, modern and easy to read.", "good_for": "Every clinic."},
    "modern": {"name": "Modern", "words": "Montserrat", "cta": "Montserrat",
               "about": "Sharp and confident, a little bolder.", "good_for": "Laser, skin and medical clinics."},
    "elegant": {"name": "Elegant serif", "words": "Playfair Display", "cta": "Poppins",
                "about": "A classic, elegant serif with a clean call to action.", "good_for": "Aesthetics, PMU and luxury clinics."},
    "classic": {"name": "Classic serif", "words": "DM Serif Display", "cta": "Inter",
                "about": "A strong serif that reads well on busy footage.", "good_for": "Premium clinics."},
    "soft": {"name": "Soft serif", "words": "Fraunces", "cta": "DM Sans",
             "about": "Rounded, gentle and friendly.", "good_for": "Facials, skin health and calm brands."},
    "rounded": {"name": "Bold and rounded", "words": "Outfit", "cta": "Outfit",
                "about": "Big, friendly and punchy.", "good_for": "Body contouring, lash bars and fun brands."},
    "typewriter": {"name": "Typewriter", "words": "Courier Prime", "cta": "Courier Prime",
                   "about": "Like a typed note: honest and a bit editorial.", "good_for": "Behind-the-scenes and chatty clinics."},
    "handwritten": {"name": "Handwritten", "words": "Patrick Hand", "cta": "Poppins",
                    "about": "Neat handwriting, like a note from you.", "good_for": "Lashes, brows and personal brands."},
}

# How the call to action (comment, DM, book) appears.
CTA = {
    "popup-box": {"name": "Pops up on a box", "popup_style": "box", "always": False,
                  "about": "Fades in on a clean box in your colour once your words have been read, then stays.",
                  "good_for": "Making the call to action stand out."},
    "popup-words": {"name": "Pops up as words", "popup_style": "plain", "always": False,
                    "about": "Fades in as plain words under yours once they've been read, then stays.",
                    "good_for": "A light, natural feel."},
    "typed": {"name": "Typed onto the screen", "popup_style": "plain", "always": False, "animation": "type",
              "about": "Typed on letter by letter under your words once they've been read, then stays. No typing sound.",
              "good_for": "A personal, just-written feel."},
    "always": {"name": "There the whole time", "popup_style": "box", "always": True,
               "about": "On screen from the start, on a clean box under your words.",
               "good_for": "Short clips, so nobody misses it."},
}

# The colour of the words straight on the video (Frances, 2026-10-16: "it can be black or it can be white").
# Words on a background take whichever colour reads best on it.
COLOURS = {
    "white": {"name": "White", "ink": "#FFFFFF",
              "about": "White words, the way most reels look.", "good_for": "Darker footage and most clips."},
    "black": {"name": "Black", "ink": "#111111",
              "about": "Black words, crisp and modern.", "good_for": "Bright, light footage: white walls, towels and beds."},
}

# The background behind the words (Frances, 2026-10-11: with a background, with no background, or no
# background with a slight black outline so the words pop; 2026-10-16: and one with nothing at all, "no
# shadow, no background, no outline, it's just the font"). The key stays "words".
WORDS = {
    "bare": {"name": "Just the words", "layouts": ["plain"],
             "about": "Just your font, straight on the video: no shadow, no outline and no background. Nothing is "
                      "ever added, even on bright footage, so pick the colour that reads best on your clips.",
             "good_for": "Clean, simple brands, and clips with a plain, even background."},
    "plain": {"name": "No background, with a soft shadow", "layouts": ["plain"],
              "about": "Straight on the video with a soft shadow, the way Instagram's own text looks. "
                       "Where they'd be hard to read (white words on bright footage), they get a thin outline.",
              "good_for": "Footage you want to show off."},
    "outline": {"name": "No background, with an outline", "layouts": ["plain"],
                "about": "Straight on the video with a slight outline (black round white words, white round black "
                         "ones), so your words pop without a background.",
                "good_for": "Bright clinics and busy footage."},
    "strips": {"name": "On a background", "layouts": ["ribbon"],
               "about": "Each line on its own strip of your colour, like Instagram's text background.",
               "good_for": "When you want your words to stand out most."},
    "mix": {"name": "A mix", "layouts": ["plain", "ribbon"],
            "about": "Some reels with no background, some on a background, so your feed never looks samey.",
            "good_for": "Most clinics."},
}

# Where the words go. All three keep clear of Instagram's top bar, buttons and caption.
POSITIONS = {
    "space": {"name": "Find the space for me", "place": None,
              "about": "The engine looks at each clip and puts your words where there's room, so they don't cover a face.",
              "good_for": "Most clinics: it changes with each clip."},
    "top": {"name": "At the top", "place": "top",
            "about": "In the top third, under Instagram's top bar.", "good_for": "Clips with space above, like a ceiling or wall."},
    "middle": {"name": "In the middle", "place": "middle",
               "about": "Right in the middle of the screen.", "good_for": "Close-ups of hands, machines and products."},
    "lower": {"name": "Lower down", "place": "lower",
              "about": "Lower down, kept above Instagram's caption and clear of its buttons.",
              "good_for": "Clips where the face or treatment is near the top."},
}

DEFAULT = {"font": "clean", "colour": "white", "cta": "popup-box", "words": "mix", "position": "space"}
SPACE_ORDER = ["middle", "top", "lower"]          # with "find the space for me", the first that's clear wins
ZONES = {"top": (300, 760), "middle": (730, 1190), "lower": (1000, 1450)}   # up and down, out of 1920


def summary(look):
    """The look in plain words, e.g. 'font Clean · call to action Pops up on a box · ...'."""
    look = dict(DEFAULT, **{k: v for k, v in look.items() if v})
    return " · ".join([f"font {FONTS[look['font']]['name'] if look['font'] in FONTS else 'My brand fonts'}",
                       f"font colour {COLOURS[look['colour']]['name']}",
                       f"call to action {CTA[look['cta']]['name']}",
                       f"background {WORDS[look['words']]['name']}",
                       f"position {POSITIONS[look['position']]['name']}"])


def clear_place(found, start, length, prefer=SPACE_ORDER):
    """With "find the space for me": the first position whose band doesn't cover a face in this stretch of
    the clip (found: face.faces() looks). If every band has a face, the one that covers least."""
    boxes = [f for t, f in found if f and start <= t <= start + length]
    if not boxes:
        return prefer[0]

    def covered(place):
        top, bottom = (z / 1920 for z in ZONES[place])
        return sum(max(0.0, min(bottom, b["bottom"]) - max(top, b["top"])) for b in boxes)

    for place in prefer:
        if covered(place) == 0:
            return place
    return min(prefer, key=covered)


def clear_places(found, start, length):
    """Every position whose band covers no face in this stretch of the clip, in SPACE_ORDER."""
    boxes = [f for t, f in found if f and start <= t <= start + length]
    out = []
    for place in SPACE_ORDER:
        top, bottom = (z / 1920 for z in ZONES[place])
        if not any(min(bottom, b["bottom"]) > max(top, b["top"]) for b in boxes):
            out.append(place)
    return out


BRIGHT = 0.62     # behind plain white words: if the brighter parts (the top quarter) of the footage are lighter
                  # than this (0 black to 1 white), white words won't read well, so they go on a strip
DARK = 0.38       # behind plain black words: if the darkest parts (the darkest tenth: hair, a machine, a dark
                  # top) are darker than this, black words won't read well there


def hard_to_read(clip, start, place, ink):
    """True when words in this colour, straight on the video, would be hard to read here: white words on
    bright footage, black words on dark footage."""
    if text_is_dark(ink):
        return brightness(clip, start, place, dark=True) < DARK
    return brightness(clip, start, place) > BRIGHT


def text_is_dark(ink):
    r, g, b = (int(ink.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b < 100


def brightness(clip, start, place, moments=(1.0, 3.5, 6.0), dark=False):
    """How bright the clip is where the words would go (0 to 1): the brighter parts of that band, at a few
    moments through the reel, taking the brightest moment (footage moves). dark: the darkest parts instead,
    taking the darkest moment (for black words, which get lost on even a small dark patch)."""
    import subprocess
    import numpy as np
    w, h = 108, 192
    top, bottom = (round(z / 1920 * h) for z in ZONES[place])
    brightest = 1.0 if dark else 0.0
    for at in moments:
        out = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{start + at:.2f}", "-i", clip, "-frames:v", "1",
                              "-vf", f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}",
                              "-f", "rawvideo", "-pix_fmt", "gray", "-"], capture_output=True).stdout
        if len(out) < w * h:
            continue
        band = (np.frombuffer(out[:w * h], np.uint8).reshape(h, w) / 255)[top:bottom, round(w * 0.14):round(w * 0.86)]
        if dark:
            brightest = min(brightest, float(np.percentile(band, 10)))
        else:
            brightest = max(brightest, float(np.percentile(band, 75)))
    return brightest
