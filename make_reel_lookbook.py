"""
Makes the Reel Lookbook (Frances, 2026-10-11): like the Talking Head Lookbook,
but for b-roll reels. Students tick a font, how their call to action appears,
how their words sit and where they go, then press Save my look (or Copy my
choices) and tell Claude "make my reels". It replaces the brand kits.

    .venv/bin/python engine/make_reel_lookbook.py

Saves My Content/reel-lookbook/index.html (on their computer: it can save the
look file to Downloads) and share.html (for a claude.ai link: copy only), with
short sample videos made from Skin Survival's October laser clips. The choices
themselves live in reel_looks.py.
"""

import tools  # noqa: F401  (first: emoji-safe output on Windows)
import brand_style  # the engine's masterclass look on every page
import html
import json
import os
import sys
from dataclasses import replace

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import make_lookbook as thl  # noqa: E402  (the Talking Head Lookbook: same page design)
import reel_looks  # noqa: E402
import text_reel  # noqa: E402
from make_reels import lookbook_choices  # noqa: E402

OUT = os.path.join(PROJECT, "My Content", "reel-lookbook")
CLIPS = os.path.join(PROJECT, "My Content", "2026-10", "clips")
TEXT = "Where are all the women who are DONE planning around shaving and want to ask about starting laser this autumn? 👀"
CTA_TEXT = "Comment “LASER” and we’ll send you the details 💌"
COLOURS = ["#E0D8D0", "#DDDDD8", "#2D2E30"]            # Frances's palette, standing in for the student's own
# Skin Survival's October laser clips only. The grey wall at the top of IMG_3175 is where plain white words read
# best (font, call to action and background samples); the laser clips also show the positions.
LASER_CLIP, FACE_CLIP = ("IMG_3182.MOV", 0.0), ("IMG_3175.MOV", 0.5)
DARK_CLIP = FACE_CLIP
SECONDS = 7

SECTIONS = [
    {"group": "Font", "prefix": "font", "choice": "font", "default": reel_looks.DEFAULT["font"], "name": "Font",
     "say": 'Use the "{name}" font on my reels',
     "lead": "The font for the words on your reels, with a clean partner for your call to action. "
             "Got your own brand fonts? Add them to your brand book and tell Claude \"use my brand fonts on my reels\".",
     "looks": reel_looks.FONTS},
    {"group": "Font colour", "prefix": "colour", "choice": "colour", "default": reel_looks.DEFAULT["colour"],
     "name": "Font colour", "say": 'Make the words on my reels {name}',
     "lead": "White or black words. Pick the one that reads best on most of your clips: white on darker footage, "
             "black on bright, light footage. You can change it for any single reel too.",
     "looks": reel_looks.COLOURS},
    {"group": "Call to action", "prefix": "cta", "choice": "cta", "default": reel_looks.DEFAULT["cta"],
     "name": "Call to action", "say": 'My call to action: "{name}"',
     "lead": "How the line asking people to comment, DM or book appears. It's always under your words, "
             "in your colours, with no sound effects.",
     "looks": reel_looks.CTA},
    {"group": "Background", "prefix": "words", "choice": "words", "default": reel_looks.DEFAULT["words"],
     "name": "Background", "say": 'My background: "{name}"',
     "lead": "Whether your words have anything behind them. Just the words is your font and nothing else. With a "
             "soft shadow or a slight outline they still sit straight on your video, but pop a little more. With "
             "a soft shadow or A mix, your words always stay readable: if they'd be hard to read somewhere, like "
             "white words on a white towel, the engine adds a thin outline (or a strip, with A mix).",
     "looks": reel_looks.WORDS},
    {"group": "Position", "prefix": "position", "choice": "position", "default": reel_looks.DEFAULT["position"],
     "name": "Where your words go", "say": 'Put my words: "{name}"',
     "lead": "Instagram puts its own buttons down the right and your caption along the bottom, so your words "
             "always stay clear of them (the faint shapes in these samples). Pick a spot, or let the engine "
             "find the space on each clip.",
     "looks": reel_looks.POSITIONS},
]
PICKED_FOR_YOU = ("No sound effects on your reels: add a trending sound in Instagram when you post. Your colours "
                  "come from your brand book, and each reel is a little different so your feed never looks samey.")


def instagram_guides():
    """A see-through picture of where Instagram's buttons and caption sit, laid on the position samples."""
    from PIL import Image, ImageDraw
    guide = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
    draw = ImageDraw.Draw(guide)
    shade = (0, 0, 0, 70)
    draw.rounded_rectangle((40, 70, 1040, 200), 26, fill=shade)                 # the top bar
    draw.rounded_rectangle((950, 1120, 1050, 1760), 40, fill=shade)              # likes, comments, share
    draw.rounded_rectangle((40, 1560, 900, 1860), 26, fill=shade)                # name, caption, sound
    font = text_reel.load_font("Poppins", 34, "caption")
    for xy, words in (((70, 113), "Instagram's top bar"), ((70, 1600), "Your name and caption show here")):
        draw.text(xy, words, font=font, fill=(255, 255, 255, 190))
    return guide


def make(name, look, clip, reveal=False, guides=False):
    """One sample: a reel, made smaller, with its poster picture."""
    target = os.path.join(OUT, "clips", f"{name}.mp4")
    if os.path.exists(target):
        return
    full = os.path.join(OUT, "work", f"{name}.mp4")
    os.makedirs(os.path.dirname(full), exist_ok=True)
    text_reel.make_reel(os.path.join(CLIPS, clip[0]), [TEXT, CTA_TEXT], full, clip[1], look, reveal)
    if guides:
        path = os.path.join(OUT, "work", "guides.png")
        if not os.path.exists(path):
            instagram_guides().save(path)
        laid = full.replace(".mp4", "-guides.mp4")
        thl.run(["ffmpeg", "-v", "error", "-y", "-i", full, "-i", path, "-filter_complex", "[0:v][1:v]overlay=0:0",
                 "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", laid])
        full = laid
    thl.run(["ffmpeg", "-v", "error", "-y", "-i", full, "-t", f"{SECONDS}", "-vf", f"scale={thl.CLIP_WIDTH}:-2",
             "-c:v", "libx264", "-preset", "slow", "-crf", "27", "-pix_fmt", "yuv420p", "-an",
             "-movflags", "+faststart", target])
    thl.run(["ffmpeg", "-v", "error", "-y", "-ss", "5.5", "-i", target, "-frames:v", "1", "-q:v", "4",
             target.replace(".mp4", ".jpg")])
    print(f"Sample made: {name}")


def base(look=None, **changes):
    """A reel look from a lookbook look, in Frances's colours, with any changes on top."""
    picked, choices = lookbook_choices({"look": look or {}})
    made = text_reel.look_from(None, COLOURS, **choices)
    return replace(made, **changes), picked


def strips(look):
    fitted = text_reel.fit_colours(replace(look, text_style="ribbon"), COLOURS)
    return replace(look, text_style="ribbon", behind_text=fitted.behind_text, text_colour=fitted.text_colour,
                   highlight=fitted.highlight)


def make_samples():
    os.makedirs(os.path.join(OUT, "clips"), exist_ok=True)
    for key in reel_looks.FONTS:
        look, _ = base({"font": key, "position": "top"}, popup_after=3.5)
        make(f"font-{key}", look, DARK_CLIP)                  # straight on the video, over the darker wall
    white, _ = base({"position": "top"}, popup_after=3.5)          # both over the same grey wall, to compare
    make("colour-white", white, DARK_CLIP)
    make("colour-black", replace(white, text_colour="#111111", popup_ink="#111111", highlight=""), DARK_CLIP)
    for key, cta in reel_looks.CTA.items():
        look, _ = base({"cta": key, "position": "top"}, popup_after=0.05 if cta["always"] else 3.5)
        make(f"cta-{key}", look, DARK_CLIP)
    plain, _ = base({"position": "top"}, popup_after=3.5)    # over the darker wall, where white words read
    make("words-bare", replace(plain, shadow=False), DARK_CLIP)   # just the font: no shadow, outline or background
    make("words-plain", plain, DARK_CLIP)
    on_bright, _ = base({"position": "middle"}, popup_after=3.5)   # the outline matters most on bright footage
    make("words-outline", replace(on_bright, outline="#111111"), LASER_CLIP)
    make("words-strips", strips(plain), DARK_CLIP)
    mix = os.path.join(OUT, "clips", "words-mix.mp4")
    if not os.path.exists(mix):       # a mix: one reel straight on the video, then the next on strips
        halves = []
        for n, (look, clip) in enumerate([(plain, DARK_CLIP), (strips(plain), FACE_CLIP)]):
            half = os.path.join(OUT, "work", f"mix-{n}.mp4")
            os.makedirs(os.path.dirname(half), exist_ok=True)
            text_reel.make_reel(os.path.join(CLIPS, clip[0]), [TEXT], half, clip[1], look)
            halves.append(half)
        thl.run(["ffmpeg", "-v", "error", "-y", "-t", "3.5", "-i", halves[0], "-t", "3.5", "-i", halves[1],
                 "-filter_complex", f"[0:v]scale={thl.CLIP_WIDTH}:-2,setsar=1[a];[1:v]scale={thl.CLIP_WIDTH}:-2,setsar=1[b];"
                 "[a][b]concat=n=2:v=1:a=0[v]", "-map", "[v]", "-c:v", "libx264", "-preset", "slow", "-crf", "27",
                 "-pix_fmt", "yuv420p", "-movflags", "+faststart", mix])
        thl.run(["ffmpeg", "-v", "error", "-y", "-ss", "1.5", "-i", mix, "-frames:v", "1", "-q:v", "4",
                 mix.replace(".mp4", ".jpg")])
        print("Sample made: words-mix")
    for key, spot in reel_looks.POSITIONS.items():
        place = spot["place"] or "top"          # "find the space": on this clip the face is in the middle, so top
        look, _ = base({"position": key if spot["place"] else "top"}, popup_after=3.5)
        make(f"position-{key}", strips(replace(look, position=place)), FACE_CLIP if not spot["place"] else LASER_CLIP,
             guides=True)


SUMMARY = """
function summary() {
  return ['font ' + nameOf('font', picks.font), 'font colour ' + nameOf('colour', picks.colour),
          'call to action ' + nameOf('cta', picks.cta),
          'background ' + nameOf('words', picks.words), 'position ' + nameOf('position', picks.position)].join(' · ');
}
"""


def script():
    """The Talking Head Lookbook's script, for reels: its own saved file, words and phrase."""
    s = thl.SCRIPT
    start = s.index("function summary() {")
    end = s.index("function paint() {")
    s = s[:start] + SUMMARY.strip() + "\n\n" + s[end:]
    for old, new in [("'talking-head-look'", "'reel-look'"), ("'my talking head look'", "'my reel look'"),
                     ("'my-talking-head-look.json'", "'my-reel-look.json'"),
                     ("make my talking heads", "make my reels"), ("'My talking head look: '", "'My reel look: '")]:
        assert old in s, old
        s = s.replace(old, new)
    return s


def main():
    make_samples()
    sections = []
    for section in SECTIONS:
        prefix = section["prefix"]
        looks = [{"key": key, "name": look["name"], "good_for": look["good_for"], "say": "",
                  "about": look["about"],
                  "clip": f"clips/{prefix}-{key}.mp4", "poster": f"clips/{prefix}-{key}.jpg"}
                 for key, look in section["looks"].items()]
        sections.append({"group": section["group"], "name": section["name"], "say": section["say"],
                         "lead": section["lead"], "looks": looks, "choice": section["choice"],
                         "default": section["default"]})
    data = {"sections": sections, "local": True}
    head = """<title>Reel Lookbook</title>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600;700&family=DM+Sans:wght@400;500;700&display=swap" rel="stylesheet">
<style>""" + thl.STYLE + "</style>\n"
    body = f"""<div class="wrap">
  <p class="eyebrow">Clinic Content Engine</p>
  <h1>Reel Lookbook</h1>
  <p class="intro">How the words look on your reels: your b-roll, with words over your treatment clips. Tap a video to watch it, and tick the ones you want. The good ones are ticked already, so you only change what you care about. Then press Save my look and tell Claude "make my reels". This is your usual look: when your reels are made, you'll pick where the words go and how they look on each one, so no two reels look the same. You can change your mind any time.</p>
  <div class="tools">
    <input id="search" class="search" type="search" placeholder="Search, e.g. elegant, top, box" aria-label="Search the looks">
    <div id="tabs" class="tabs" role="group" aria-label="Kinds of look"></div>
  </div>
  <div id="sections"></div>
  <p id="empty" class="empty">Nothing matches that yet. Try another word, or tap All.</p>
  <div class="coming"><strong>Done for you:</strong> {html.escape(PICKED_FOR_YOU)}</div>
</div>
<div class="bar"><div class="bar-in">
  <p class="bar-text"><strong>Your reel look:</strong> <span id="bar-summary"></span></p>
  <div class="bar-buttons">
    <button id="save" class="save" type="button">Save my look</button>
    <button id="copy-look" class="save quiet" type="button">Copy my choices</button>
  </div>
  <p id="saved-note" class="saved-note">Tick one in each section (the good ones are ticked already), then save.</p>
</div></div>
<dialog id="pop" aria-labelledby="p-name">
  <button id="close" class="close" type="button" aria-label="Close">×</button>
  <div class="pop">
    <div class="viewer"><video id="p-video" controls loop playsinline></video></div>
    <div class="details">
      <span id="p-tag" class="letter"></span>
      <h2 id="p-name"></h2>
      <p id="p-about"></p>
      <div><h3>Great for</h3><p id="p-good"></p></div>
      <button id="p-pick" class="pick" type="button">Pick this</button>
      <div class="say"><h3>Or tell Claude</h3><q id="p-say"></q><button id="copy" class="copy" type="button">Copy</button></div>
      <p class="small">These samples use Skin Survival's laser clips and Frances's colours. Yours will use your clips, your words and your colours.</p>
    </div>
  </div>
</dialog>
<script type="application/json" id="lookbook">@@DATA@@</script>
<script>{script()}</script>
"""
    page = f"""<!doctype html>
<html lang="en-GB">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{head}</head>
<body>
{body}</body>
</html>
"""

    def with_data(text, local):
        return text.replace("@@DATA@@", json.dumps(dict(data, local=local), ensure_ascii=False).replace("</", "<\\/"))
    with open(os.path.join(OUT, "index.html"), "w", encoding="utf-8") as f:
        f.write(brand_style.apply(with_data(page, True)))
    with open(os.path.join(OUT, "share.html"), "w", encoding="utf-8") as f:
        f.write(brand_style.apply(with_data(head + body, False)))
    print(os.path.join(OUT, "index.html"))


if __name__ == "__main__":
    main()
