"""
Brand packs for talking heads: three fonts that go together, and nothing else.

Frances (2026-10-10): "each brand pack should have them three fonts that all
align and match with each other": a headline font (for the hook and the main
pop-up lines), a pop-up font (the handwriting) and a caption font. No sounds,
no stickers, no colours: those are decided by each piece of content (stickers
and sounds by what's being said, colours by the clinic's own brand).

A student picks one pack once (from an A/B on their own video), and it's used
the whole way through every video. With no choice, Claude picks the pack that
suits their brand; Frances's own is "elegant".

Fonts are (font, size, capitals) for the headline and pop-up fonts, and a font
name for captions. Caption designs with a font of their own (Elegant word, Bold
capitals, Underlined word, Soft build) keep it, because the font is the design.
All fonts are OFL or Apache (see fonts/licences).
"""

PACKS = {
    "elegant": {"name": "Elegant", "headline": ("Playfair Display", 74, False), "popup": ("Caveat", 52, False),
                "caption": "Poppins",
                "about": "An elegant serif, relaxed handwriting and clean captions.",
                "good_for": "Every brand. Frances's own pack."},
    "clean": {"name": "Clean", "headline": ("Montserrat", 62, False), "popup": ("Patrick Hand", 72, False),
              "caption": "Montserrat",
              "about": "Sharp modern letters, neat handwriting and crisp captions.",
              "good_for": "Clinical, medical and skin-science brands."},
    "luxe": {"name": "Luxe", "headline": ("Cormorant Garamond", 56, "spaced"),
             "popup": ("Shadows Into Light", 72, False), "caption": "Playfair Display",
             "about": "Spaced-out capitals, thin pen writing and elegant serif captions.",
             "good_for": "Luxury, aesthetics and premium clinics."},
    "playful": {"name": "Playful", "headline": ("Outfit", 70, False), "popup": ("Indie Flower", 60, False),
                "caption": "Patrick Hand",
                "about": "Round, friendly letters, bubbly writing and handwritten captions.",
                "good_for": "Lashes, brows, nails and fun, chatty brands."},
    "soft": {"name": "Soft", "headline": ("Fraunces", 66, False), "popup": ("Reenie Beanie", 78, False),
             "caption": "Fraunces",
             "about": "A soft serif, pencil writing and soft serif captions.",
             "good_for": "Calm, reassuring videos. Skin journeys and aftercare."},
    "bold": {"name": "Bold", "headline": ("Outfit", 64, True), "popup": ("Permanent Marker", 56, False),
             "caption": "Outfit",
             "about": "Heavy capitals, marker-pen writing and heavy captions.",
             "good_for": "Hot takes, myth-busting and confident brands."},
}
DEFAULT = "elegant"


# ---------------------------------------------------------------------------
# Build your own (Frances, 2026-10-10): "they can pick their own... each individual
# part... so they can make their own brand package". A student can swap any of the
# three fonts for one of these (their friendly names are all they ever see).
# ---------------------------------------------------------------------------
HEADLINES = {
    "elegant-serif": {"name": "Elegant serif", "font": ("Playfair Display", 74, False)},
    "spaced-capitals": {"name": "Spaced capitals", "font": ("Cormorant Garamond", 56, "spaced")},
    "soft-serif": {"name": "Soft serif", "font": ("Fraunces", 66, False)},
    "classic-serif": {"name": "Classic serif", "font": ("DM Serif Display", 70, False)},
    "fashion-serif": {"name": "Fashion serif", "font": ("Bodoni Moda", 64, False)},
    "modern": {"name": "Modern", "font": ("Montserrat", 62, False)},
    "rounded": {"name": "Rounded", "font": ("Outfit", 70, False)},
    "bold-capitals": {"name": "Bold capitals", "font": ("Outfit", 64, True)},
    "geometric": {"name": "Geometric", "font": ("Jost", 68, False)},
}
POPUP_WRITING = {
    "casual": {"name": "Casual handwriting", "font": ("Caveat", 52, False)},
    "neat": {"name": "Neat handwriting", "font": ("Patrick Hand", 72, False)},
    "baby": {"name": "Baby writing", "font": ("Indie Flower", 60, False)},
    "thin-pen": {"name": "Thin pen", "font": ("Shadows Into Light", 72, False)},
    "pencil": {"name": "Pencil", "font": ("Reenie Beanie", 78, False)},
    "marker": {"name": "Marker pen", "font": ("Permanent Marker", 56, False)},
    "typewriter": {"name": "Typewriter", "font": ("Special Elite", 60, False)},
    "crisp-typewriter": {"name": "Crisp typewriter", "font": ("Courier Prime", 60, False)},
    "clean": {"name": "Clean", "font": ("Poppins", 56, False)},
}
CAPTION_FONTS = {   # clearly different from each other (Frances, 2026-10-10: the first six looked the same)
    "clean": {"name": "Clean", "font": "Poppins"},
    "elegant-serif": {"name": "Elegant serif", "font": "Playfair Display"},
    "fashion": {"name": "Fashion serif", "font": "Bodoni Moda"},
    "soft-serif": {"name": "Soft serif", "font": "Fraunces"},
    "handwriting": {"name": "Neat handwriting", "font": "Patrick Hand"},
    "typewriter": {"name": "Typewriter", "font": "Courier Prime"},
    "heavy": {"name": "Heavy", "font": "Outfit"},
    "marker": {"name": "Marker pen", "font": "Permanent Marker"},
}


# The clinic's own fonts from their brand book, offered as "My brand fonts" (Frances, 2026-10-11).
try:
    import brand_book as _brand
    if _brand.font("headings"):
        HEADLINES["brand"] = {"name": "My brand font", "font": (_brand.font("headings"), 66, False)}
    if _brand.font("body") or _brand.font("headings"):
        CAPTION_FONTS["brand"] = {"name": "My brand font", "font": _brand.font("body") or _brand.font("headings")}
except Exception:
    pass


def own_pack(pack=DEFAULT, headline=None, popup=None, caption=None):
    """A brand pack with any of its three fonts swapped for the student's own picks."""
    chosen = dict(PACKS[pack])
    if headline:
        chosen["headline"] = HEADLINES[headline]["font"]
    if popup:
        chosen["popup"] = POPUP_WRITING[popup]["font"]
    if caption:
        chosen["caption"] = CAPTION_FONTS[caption]["font"]
    return chosen
