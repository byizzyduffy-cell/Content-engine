"""
Makes every text-on-video reel for the month in one go.

It reads a list of reels (reels.json) in the month's folder, for example
My Content/2026-10/reels.json, and saves each finished reel in that month's
"reels" folder, named by the date it goes out.

    python3 engine/make_reels.py "My Content/2026-10/reels.json"
    python3 engine/make_reels.py "My Content/2026-10/reels.json" --only 2026-10-01
    python3 engine/make_reels.py "My Content/2026-10/reels.json" --preview position
    python3 engine/make_reels.py "My Content/2026-10/reels.json" --preview popup

reels.json looks like this. Clip paths are inside the month's folder, and a
reel with only one piece of text just leaves out "popup". A reel whose lines
appear one by one has "title" and "lines" instead of "text" (plus "pauses": true
for a "wait a few seconds" reel), and can use several "clips" one after another.
In "style", "kit" is
optional: a brand kit from brand_kits.json sets the fonts, colours, animation
and sound together, and the other choices sit on top of it. "my_colours" fits
a student's own colours onto the look. Any other part of the look can be set
too, for example "text_colour", "popup_text_colour", "popup_font": "Caveat"
(a handwritten pop-up) and "popup_tilt": 3 (the pop-up leans a little).

Each reel can also have its own "style", on top of the month's, so a month of
reels doesn't all look the same (for example a card behind the text on one,
a ribbon on another). A one-by-one reel can say "title_time": seconds the
first line stays on its own, for a two-beat reel where the punchline arrives.
A text reel with "reveal": true shows each line of "text" (split by \n) in
turn, in any style (card, ribbon, panel...), with a soft tap as each one lands.

"vary": true in "style" is how every student's month is made now, clean and
natural, the way people make reels in Instagram itself (Frances, 2026-10-11:
"pop-ups need to be a lot cleaner... more natural Instagram vibe... take out
the sound effects... be super clear on the fonts... add their own colour
palettes"):
- No sound effects at all (they add music in Instagram).
- Their brand pack's fonts, the same as their talking heads: "pack" (and
  their own "headline" and "caption_font" picks, from packs.py) gives the
  headline font for the main words and the caption font for the call to action.
- Their own colours ("my_colours").
- Just enough difference from reel to reel (Frances, 2026-10-09): the words
  straight on the video or on Instagram-style highlight strips in their colour,
  the call to action as plain words or on a clean box, middle or top, never the
  same as the reel before. The call to action fades in once the words have been
  read, not at the same second every time. No bounces, leans, tape, notes or
  bubbles. The mix comes from the clinic's name and the month, so it's theirs.
A reel's own "style" still wins.

{
  "style": {"kit": "nude-luxe", "position": "middle", "popup_style": "box", "popup_colour": "#E0D8D0"},
  "reels": [
    {"date": "2026-10-01", "clip": "clips/IMG_3182.MOV", "start": 0,
     "text": "Where are all the women who are DONE planning around shaving?",
     "popup": "Comment LASER and we'll send you the details"}
  ]
}
"""

import tools  # noqa: F401  (first: emoji-safe output on Windows)
import argparse
import json
import os
import random
import re
import sys
from dataclasses import replace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import brand_book  # noqa: E402
import list_reel  # noqa: E402
import packs  # noqa: E402
import reel_looks  # noqa: E402
import text_reel  # noqa: E402

PREVIEW_NAMES = {"position": "text-position.png", "popup": "popup-style.png"}
STYLE_NAMES = {"popup_colour": "box_colour", "popup_text_colour": "box_text_colour", "popup_font": "caption_font",
               "font": "heading_font"}


# The clean choices "vary" mixes: words straight on the video or on highlight strips (like Instagram's own
# text backgrounds), and the call to action as plain words or on a clean box. Their own choices come up most.
LAYOUTS = ["plain", "ribbon"]
OUTLINE = "#111111"      # the thin dark outline round words with no background ("no background, with an outline")
POPUP_DESIGNS = ["plain", "box"]


def pack_fonts(style):
    """The main-words font and call-to-action font from their brand pack and own font picks."""
    if not (style.get("pack") or style.get("headline") or style.get("caption_font")):
        return {}
    chosen = packs.own_pack(style.get("pack") or packs.DEFAULT, headline=style.get("headline"),
                            caption=style.get("caption_font"))
    return {"heading_font": chosen["headline"][0], "caption_font": chosen["caption"]}


def clinic_seed(folder):
    """The clinic's name and the month, so each clinic and each month gets its own mix."""
    name = ""
    profile = os.path.join(os.path.dirname(folder), "my-clinic.md")
    if os.path.exists(profile):
        found = re.search(r"\*\*Clinic name:\*\* (.+)", open(profile, encoding="utf-8").read())
        name = found.group(1).strip() if found else ""
    return f"{name or folder}|{os.path.basename(folder)}"


class Bag:
    """Takes the options out in a shuffled order and refills when empty, so every option gets its turn
    (the favourite goes in more than once) and the same one never comes twice in a row."""
    def __init__(self, rng, options, favourite=None, extra=1):
        self.rng, self.options = rng, list(options) + [favourite] * extra if favourite in options else list(options)
        self.left, self.last = [], None

    def take(self, allowed=None):
        for _ in range(3):
            if not self.left:
                self.left = self.options[:]
                self.rng.shuffle(self.left)
            fits = [o for o in self.left if o != self.last and (allowed is None or o in allowed)]
            if fits:
                self.left.remove(fits[0])
                self.last = fits[0]
                return fits[0]
            self.left = []
        self.last = (allowed or self.options)[0]
        return self.last


def kit_colours(kit):
    """A brand kit's colours, from brand_kits.json (or {} with no kit)."""
    if not kit:
        return {}
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "brand_kits.json"), encoding="utf-8") as f:
        return json.load(f)["kits"][kit]["colours"]


def font_settings(key):
    """The words font and call-to-action font for a Reel Lookbook font (or "brand": their brand book's)."""
    if key == "brand":
        words = brand_book.font("headings") or "Poppins"
        return {"heading_font": words, "caption_font": brand_book.font("body") or words}
    font = reel_looks.FONTS.get(key, reel_looks.FONTS["clean"])
    return {"heading_font": font["words"], "caption_font": font["cta"]}


def cta_settings(key):
    """How a Reel Lookbook call to action is drawn: on a box or as words, and how it arrives."""
    return {"popup_style": reel_looks.CTA[key]["popup_style"], "animation": reel_looks.CTA[key].get("animation", "fade")}


def lookbook_choices(style):
    """Their Reel Lookbook look (style["look"]) as reel settings: the fonts (or their brand book's), how the
    call to action appears, and a fixed position if they picked one. Always clean: no sound, a quick fade."""
    picked = dict(reel_looks.DEFAULT, **(style.get("look") or {}))
    choices = {"sound": "", "popup_tilt": 0, **font_settings(picked["font"]), **cta_settings(picked["cta"])}
    if reel_looks.POSITIONS[picked["position"]]["place"]:
        choices["position"] = reel_looks.POSITIONS[picked["position"]]["place"]
    return picked, choices


def seen_faces(clip, seen):
    """The faces in a clip, found once."""
    if clip not in seen:
        import face
        seen[clip] = face.faces(clip)
    return seen[clip]


def seen_hard(clip, start, place, ink, seen):
    """Whether words in this colour would be hard to read where they'd go on the clip, measured once."""
    key = (clip, start, place, ink)
    if key not in seen:
        seen[key] = reel_looks.hard_to_read(clip, start, place, ink)
    return seen[key]


def reel_changes(reel, own, look, picked, colours, kit, folder, seen, layout=None):
    """How one reel differs from the month's look, from its Reel Lookbook picks: the month's (picked) with
    this reel's own on top (own, e.g. {"position": "top", "words": "strips"}; Frances, 2026-10-13: "we can't
    just assume that they want everything to look the same"). layout: "plain" or "ribbon", when the month's
    mix has chosen one. Gives the changes and the picks the reel ended up with."""
    picks = dict(picked, **own)
    listing = bool(reel.get("lines"))
    popup = reel.get("popup") or ""
    change = {}
    if "font" in own:
        change.update(font_settings(picks["font"]))
    if "cta" in own:
        change.update(cta_settings(picks["cta"]))
    popup_style = change.get("popup_style", look.popup_style)
    if listing:
        layout = "plain"
    elif picks["words"] != "mix" or not layout:
        layout = reel_looks.WORDS[picks["words"]]["layouts"][0]
    # The font colour (white or black) and its outline: black round white words, white round black ones.
    ink = reel_looks.COLOURS.get(picks.get("colour"), reel_looks.COLOURS["white"])["ink"]
    dark_ink = reel_looks.text_is_dark(ink)
    ring = "#FFFFFF" if dark_ink else OUTLINE
    bare = picks["words"] == "bare"         # "just the words": no shadow, no outline, nothing ever added
    outline = ring if picks["words"] == "outline" else ""
    clip = os.path.join(folder, reel["clip"]) if folder and not listing else None
    if not listing:
        place = reel_looks.POSITIONS[picks["position"]]["place"]
        if not place and clip:          # "find the space for me": where this clip has no face
            place = reel_looks.clear_place(seen_faces(clip, seen), reel.get("start", 0), 9 if popup else 7)
        if place:
            change["position"] = place
    if clip and not outline and not bare and (layout == "plain" or popup_style == "plain"):
        # Plain white words don't read on bright footage (a white towel, a bright wall), nor black words on dark
        # footage. With "no background" they get a thin outline there; otherwise they go on a strip (and a plain
        # call to action on a box). "Just the words" is left exactly as they picked it.
        if seen_hard(clip, reel.get("start", 0), change.get("position", look.position), ink, seen):
            if picks["words"] == "plain":
                outline = ring
            else:
                layout = "ribbon"
                if popup_style == "plain" and popup:
                    change["popup_style"] = "box"
    change.update(popup_ink=ink, shadow=not bare)   # a call to action straight on the video is in their colour too
    if layout == "ribbon" and kit:          # the kit's own highlight strips
        change.update(text_style="ribbon", behind_text=kit["strip"], text_colour=kit["strip_text"],
                      highlight=kit["strip_highlight"])
    elif layout == "ribbon":                # strips in their own colours, kept readable
        fitted = text_reel.fit_colours(replace(look, text_style="ribbon"), colours)
        change.update(text_style="ribbon", behind_text=fitted.behind_text, text_colour=fitted.text_colour,
                      highlight=fitted.highlight)
    else:
        highlight = kit.get("highlight", look.highlight)
        if dark_ink and highlight and text_reel.luminance(highlight) > 0.3:
            highlight = ""                  # a light highlight would vanish where black words read
        change.update(text_style="plain", text_case="as written", lines="", behind_text="", outline=outline,
                      text_colour=ink, highlight=highlight)
    ended = {"font": picks["font"], "colour": picks.get("colour", "white"), "cta": picks["cta"],
             "words": "strips" if layout == "ribbon" else (picks["words"] if picks["words"] in ("outline", "bare")
                                                           else "plain"),
             "position": change.get("position", look.position)}
    return change, ended


def varied_looks(reels, look, style, seed, folder=None, picked=None, chosen=None):
    """{date: style changes} for every reel without a style of its own, so no two in a row look alike.
    picked: their Reel Lookbook look, which decides what's mixed (the words) and what isn't (font, call to
    action, a fixed position); a reel's own "look" (picked reel by reel) wins over it. "Find the space for
    me" puts each reel's words where its clip has no face. chosen: filled with the picks each reel ended up
    with ({date: {"font", "cta", "words", "position"}}), for the page where they pick reel by reel."""
    rng = random.Random(seed)
    colours = style.get("my_colours") or [look.box_colour, look.box_text_colour]
    kit = {} if style.get("my_colours") else kit_colours(style.get("kit"))
    seen = {}                                     # each clip's faces and brightness, found once
    out = {}
    if picked:
        mixed = Bag(rng, reel_looks.WORDS["mix"]["layouts"])
        # Frances, 2026-10-15: every reel gets its own look, picked reel by reel ("it's not, let's make every
        # reel look the same"). So the engine's own pick changes from reel to reel too: their usual position,
        # background and call to action come up most, never the same twice in a row, and the words go where the
        # clip has no face. The font stays theirs on every reel.
        fixed = lambda key, options: picked[key] if picked[key] in options else None
        places = Bag(rng, reel_looks.SPACE_ORDER, fixed("position", reel_looks.SPACE_ORDER))
        # "Just the words" is only suggested to clinics who picked it: on bright or busy footage it can be hard
        # to read, so it's never handed to anyone who didn't ask for it.
        options = ["plain", "outline", "strips"] + (["bare"] if picked["words"] == "bare" else [])
        backgrounds = Bag(rng, options, fixed("words", options))
        ctas = Bag(rng, list(reel_looks.CTA), fixed("cta", reel_looks.CTA))
        for reel in reels:
            if reel.get("style"):
                continue
            own = {key: value for key, value in (reel.get("look") or {}).items() if value}
            listing = bool(reel.get("lines"))
            popup = reel.get("popup") or ""
            if not listing:
                # Always take from every bag, so one reel's own picks never shift the others' suggestions.
                clip = os.path.join(folder, reel["clip"]) if folder else None
                clear = reel_looks.clear_places(seen_faces(clip, seen), reel.get("start", 0), 9 if popup else 7) \
                    if clip else []
                suggestion = {"position": places.take(clear or None), "words": backgrounds.take()}
                if picked["words"] == "mix":
                    del suggestion["words"]         # "a mix" already changes from reel to reel
                if popup:
                    suggestion["cta"] = ctas.take()
                own = dict(suggestion, **own)
            layout = mixed.take() if own.get("words", picked["words"]) == "mix" and not listing else None
            change, ended = reel_changes(reel, own, look, picked, colours, kit, folder, seen, layout)
            if popup and not listing:
                always = reel_looks.CTA[own.get("cta", picked["cta"])]["always"]
                words = text_reel.read_time(reel.get("text", "")) + 1.0 + rng.uniform(-0.4, 0.8)
                change["popup_after"] = 0.05 if always else round(min(7.0, max(3.5, words)), 2)
            if not listing and reel.get("text", "").count("\n") >= 1 and rng.random() < 0.4:
                change["reveal"] = True
            out[reel["date"]] = change
            if chosen is not None and not listing:
                chosen[reel["date"]] = ended
        return out

    # Months made before the Reel Lookbook: the old clean mix.
    favourite_popup = style.get("popup_style") or look.popup_style
    favourite_place = style.get("position") or look.position
    layouts = Bag(rng, LAYOUTS)
    places = Bag(rng, ["middle", "top"], favourite_place, 2)
    designs = Bag(rng, POPUP_DESIGNS, favourite_popup if favourite_popup in POPUP_DESIGNS else None)
    for reel in reels:
        if reel.get("style"):
            continue
        listing = bool(reel.get("lines"))
        popup = reel.get("popup") or ""
        change = {}
        layout = "plain" if listing else layouts.take()
        if layout == "ribbon" and kit:
            change.update(text_style="ribbon", behind_text=kit["strip"], text_colour=kit["strip_text"],
                          highlight=kit["strip_highlight"])
        elif layout == "ribbon":
            fitted = text_reel.fit_colours(replace(look, text_style="ribbon"), colours)
            change.update(text_style="ribbon", behind_text=fitted.behind_text, text_colour=fitted.text_colour,
                          highlight=fitted.highlight)
        else:
            change.update(text_style="plain", text_case="as written", lines="", behind_text="", outline="",
                          text_colour=kit.get("text", "#FFFFFF"), highlight=kit.get("highlight", look.highlight))
        places.last = None                  # top or middle can come twice in a row
        change["position"] = places.take()
        change["popup_style"] = designs.take()
        if popup and not listing:
            words = text_reel.read_time(reel.get("text", "")) + 1.0 + rng.uniform(-0.4, 0.8)
            change["popup_after"] = round(min(7.0, max(3.5, words)), 2)
        if not listing and reel.get("text", "").count("\n") >= 1 and rng.random() < 0.4:
            change["reveal"] = True
        out[reel["date"]] = change
    return out


def month_look(plan):
    """The month's style, their Reel Lookbook look (or None for older months) and the month's reel look."""
    style = plan.get("style", {})
    # Any other style setting is a part of the look, under the friendlier names in STYLE_NAMES.
    choices = {STYLE_NAMES.get(key, key): value for key, value in style.items()
               if key not in ("kit", "my_colours", "vary", "pack", "headline", "caption_font", "look")}
    choices.update(pack_fonts(style))
    picked = None
    if "look" in style or any(reel.get("look") for reel in plan["reels"]):
        # Their Reel Lookbook look, and their brand book's colours if they haven't given any.
        picked, from_lookbook = lookbook_choices(style)
        choices = dict(from_lookbook, **choices)
        style = dict(style, vary=True, my_colours=style.get("my_colours") or brand_book.colours() or None)
    if style.get("vary"):   # clean b-roll: no sound effects, a quick fade, nothing leaning
        choices.setdefault("sound", "")
        choices.setdefault("animation", "fade")
        choices.setdefault("popup_tilt", 0)
    return style, picked, text_reel.look_from(style.get("kit"), style.get("my_colours"), **choices)


def main():
    parser = argparse.ArgumentParser(description="Make the month's text-on-video reels.")
    parser.add_argument("reels_json", help="the month's reels.json")
    parser.add_argument("--only", nargs="+", help="just these dates, e.g. 2026-10-01")
    parser.add_argument("--preview", choices=list(PREVIEW_NAMES),
                        help="instead of reels, save the side-by-side picture for this style choice")
    args = parser.parse_args()

    folder = os.path.dirname(os.path.abspath(args.reels_json))
    with open(args.reels_json, encoding="utf-8") as f:
        plan = json.load(f)
    style, picked, look = month_look(plan)
    reels = plan["reels"]
    varied = varied_looks(reels, look, style, clinic_seed(folder), folder, picked) if style.get("vary") else {}

    if args.preview:
        # Use the student's own first reel (one with a pop-up, for the pop-up choice).
        reel = next((r for r in reels if not r.get("lines") and (args.preview != "popup" or r.get("popup"))), reels[0])
        texts = [reel["text"]] + ([reel["popup"]] if reel.get("popup") else [])
        out = os.path.join(os.path.dirname(folder), "previews", PREVIEW_NAMES[args.preview])
        text_reel.preview(args.preview, os.path.join(folder, reel["clip"]), texts, out,
                          reel.get("start", 0), look)
        print(out)
        return

    used = {}        # each clip's strong moments used so far, so reels don't all show the same seconds
    for reel in reels:
        if args.only and reel["date"] not in args.only:
            continue
        out = os.path.join(folder, "reels", f"{reel['date']}.mp4")
        # A reel can have its own "style" on top of the month's, so the reels don't all look alike.
        own = dict(varied.get(reel["date"], {}))
        reveal = own.pop("reveal", reel.get("reveal", False))
        own.update({STYLE_NAMES.get(key, key): value for key, value in reel.get("style", {}).items()})
        this_look = replace(look, **own)
        if reel.get("lines"):
            clips = reel.get("clips") or [{"clip": reel["clip"], "start": reel.get("start", 0)}]
            segments = [(os.path.join(folder, c["clip"]), c.get("start", 0)) for c in clips]
            list_reel.make_list_reel(segments, reel["title"], reel["lines"], out, this_look,
                                     reel.get("popup"), reel.get("pauses", False), reel.get("title_time"), used)
        else:
            texts = [reel["text"]] + ([reel["popup"]] if reel.get("popup") else [])
            # "then": more pop-ups after the first, e.g. [{"text": "DM me AUDIT", "after": 2, "style": {...}}]
            then = [(extra["text"], replace(this_look, **{STYLE_NAMES.get(k, k): v for k, v in extra.get("style", {}).items()}),
                     extra.get("after", 2.0)) for extra in reel.get("then", [])]
            text_reel.make_reel(os.path.join(folder, reel["clip"]), texts, out, reel.get("start", 0), this_look,
                                reveal, then, reel.get("popup_delay"), used)
        print(f"Made {reel['date']}: {os.path.relpath(out)}"
              + (f"  ({', '.join(f'{k}={v}' for k, v in varied[reel['date']].items() if k in ('text_style', 'position', 'popup_style', 'popup_after', 'reveal'))})"
                 if reel["date"] in varied else ""))


if __name__ == "__main__":
    main()
