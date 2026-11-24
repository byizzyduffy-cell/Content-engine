"""
Makes the brand kits board: every b-roll reel kit from brand_kits.json shown on a
still from a real clip, with its fonts named clearly and the call to action fading
in. No sounds: b-roll reels have none (Frances, 2026-10-11).

    python3 engine/kit_board.py "My Content/previews"

It saves brand-kits.html in that folder and uses the photos in its kit-photos folder (one per kit,
named after the kit). Open it through the previews server (see .claude/launch.json), or
double-click it, so the fonts load.
"""

import html
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# Each kit is shown on its own photo with words for a different treatment, so the board shows
# the kits working for any clinic. Photos live in "<folder>/kit-photos/<kit>.jpg" (phone-shaped crops).
# The word in CAPITALS gets the kit's highlight colour.
EXAMPLES = {
    "nude-luxe": ("Booked my facial for Friday and suddenly the whole week feels DOABLE",
                  "Comment GLOW and we’ll send you the details"),
    "clinical-clean": ("Where are all the women who are DONE planning around shaving and want to ask about starting laser this autumn? 👀",
                       "Comment “LASER” and we’ll send you the details 💌"),
    "soft-blush": ("The one hour a month NOBODY can reach me 🤍",
                   "DM FACIAL to book yours"),
    "sage-calm": ("Telling my client her skin looks AMAZING and meaning every word",
                  "Comment SKIN and we’ll talk you through it"),
    "black-tie": ("Quiet room, good music and an hour that’s JUST for you",
                  "DM SKIN to book a consultation"),
    "bold-bright": ("Me after my LED session: completely RESET 😌",
                    "Comment LED and we’ll send you the details"),
}

WEIGHTS = {"Playfair Display": 700, "DM Serif Display": 400, "Cormorant Garamond": 700, "Fraunces": 600,
           "Bodoni Moda": 700, "Outfit": 800, "Montserrat": 600, "Jost": 600}
FONT_LINK = ("https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700&family=DM+Sans:wght@500;700"
             "&family=DM+Serif+Display&family=Inter:wght@500;600&family=Montserrat:wght@500;600"
             "&family=Fraunces:wght@600&family=Poppins:wght@500;600&family=Jost:wght@500;600"
             "&family=Outfit:wght@600;800&display=swap")
LAYOUTS = {"plain": "words straight on the video", "ribbon": "each line on a highlight strip"}
POPUPS = {"plain": "just the words", "box": "on a clean box"}


def phone(kit):
    """The kit on a still from a real clip, in its usual layout, with the call to action fading in."""
    c, fonts = kit["colours"], kit["fonts"]
    ribbon = kit["text_style"] == "ribbon"
    hook, popup = EXAMPLES[kit["id"]]
    highlight = c["strip_highlight"] if ribbon else c["highlight"]
    words = re.sub(r"\b([A-Z]{3,})\b", lambda m: f'<span style="color:{highlight}">{m.group(1)}</span>',
                   html.escape(hook), count=1)
    hook_style = [f"font-family:'{fonts['headings']}',serif", f"font-weight:{WEIGHTS.get(fonts['headings'], 600)}",
                  f"color:{c['strip_text'] if ribbon else c['text']}", "font-size:13.5px"]
    if ribbon:
        words = f'<span class="ribbon" style="background:{c["strip"]}">{words}</span>'
        hook_style.append("line-height:1.75")
    else:
        hook_style.append("text-shadow:0 1px 3px rgba(0,0,0,.45)")
    if kit["popup"] == "box":
        popup_style = (f"background:{c['popup_box']};color:{c['popup_text']};padding:5px 9px;border-radius:7px;"
                       "box-shadow:0 2px 6px rgba(0,0,0,.15)")
    else:
        popup_style = "color:#FFFFFF;text-shadow:0 1px 3px rgba(0,0,0,.5)"
    popup_style += f";font-family:'{fonts['captions']}',sans-serif"
    return f"""
    <div class="phone">
      <div class="bg" style="background-image:url('kit-photos/{kit['id']}.jpg')"></div>
      <div class="words">
        <p class="hook" style="{';'.join(hook_style)}">{words}</p>
        <p class="popup" style="{popup_style}">{html.escape(popup)}</p>
      </div>
    </div>"""


def card(kit):
    c, fonts = kit["colours"], kit["fonts"]
    swatch_roles = [("text", "Words"), ("highlight", "Highlight"), ("strip", "Strips"), ("popup_box", "Call to action box")]
    swatches = "".join(
        f'<div class="sw"><span style="background:{c[role]}"></span><b>{label}</b></div>'
        for role, label in swatch_roles if c.get(role))
    same = fonts["headings"] == fonts["captions"]
    font_words = (f"<b>{fonts['headings']}</b> for everything" if same else
                  f"<b>{fonts['headings']}</b> for the words, <b>{fonts['captions']}</b> for the call to action")
    return f"""
  <article class="card">{phone(kit)}
    <h2>{html.escape(kit['name'])}</h2>
    <p class="vibe">{html.escape(kit['vibe'])}</p>
    <div class="swatches">{swatches}</div>
    <dl>
      <dt>Fonts</dt><dd>{font_words}</dd>
      <dt>Look</dt><dd>Mostly {LAYOUTS[kit['text_style']]}, call to action {POPUPS[kit['popup']]}. Each reel is a little different.</dd>
      <dt>Suits</dt><dd>{html.escape(kit['suits'])}</dd>
    </dl>
  </article>"""


STYLE = """
  :root { --ink: #2D2E30; --quiet: #6B6A68; --line: #E4DED7; --page: #FAF8F5; --card: #FFFFFF; }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--page); color: var(--ink); font: 15px/1.5 'DM Sans', system-ui, sans-serif; }
  header { max-width: 1180px; margin: 0 auto; padding: 32px 16px 8px; }
  h1 { font: 700 30px/1.2 'Playfair Display', serif; margin: 0 0 6px; }
  header p { margin: 0; color: var(--quiet); max-width: 680px; }
  .grid { max-width: 1180px; margin: 0 auto; padding: 16px; display: grid; gap: 20px; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); }
  .card { background: var(--card); border: 1px solid var(--line); border-radius: 14px; padding: 16px; }
  .phone { position: relative; width: 270px; aspect-ratio: 9 / 16; margin: 0 auto 14px; border-radius: 18px; overflow: hidden; }
  .bg { position: absolute; inset: 0; background: center / cover no-repeat; }
  .bg::after { content: ''; position: absolute; inset: 0; background: rgba(0,0,0,.25); }
  .words { position: absolute; left: 34px; right: 34px; top: 175px; height: 130px; display: flex; flex-direction: column; justify-content: center; align-items: center; }
  .hook { margin: 0; line-height: 1.3; text-align: center; }
  .ribbon { padding: 3px 7px; border-radius: 5px; -webkit-box-decoration-break: clone; box-decoration-break: clone; }
  .popup { margin: 10px 0 0; font-size: 10px; font-weight: 600; line-height: 1.3; text-align: center; animation: fade 5s infinite; }
  .note { max-width: 1180px; margin: 0 auto; padding: 0 16px; }
  .note p { background: #fff; border: 1px solid var(--line); border-radius: 12px; padding: 12px 16px; margin: 8px 0 0; max-width: 760px; }
  @keyframes fade { 0%, 30% { opacity: 0; } 36%, 94% { opacity: 1; } 100% { opacity: 0; } }
  h2 { font: 700 20px/1.2 'Playfair Display', serif; margin: 0; }
  .vibe { margin: 2px 0 12px; color: var(--quiet); }
  .swatches { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; margin-bottom: 12px; }
  .sw { font-size: 10.5px; line-height: 1.3; }
  .sw span { display: block; height: 30px; border-radius: 8px; border: 1px solid var(--line); margin-bottom: 4px; }
  .sw b { display: block; font-weight: 600; }
  .sw i { font-style: normal; color: var(--quiet); }
  dl { margin: 0; display: grid; grid-template-columns: 70px 1fr; gap: 6px 10px; font-size: 13.5px; }
  dt { color: var(--quiet); }
  dd { margin: 0; }
"""


def main(folder):
    with open(os.path.join(HERE, "brand_kits.json"), encoding="utf-8") as f:
        kits = json.load(f)["kits"]
    page = f"""<!doctype html>
<html lang="en-GB">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Brand Kits for Reels</title>
<link href="{FONT_LINK}" rel="stylesheet">
<style>{STYLE}</style>
</head>
<body>
<header>
  <h1>Brand kits for your reels</h1>
  <p>These are for your <b>reels and b-roll content</b>: the words that go over your treatment clips. Pick the one that feels most like you, and the engine makes every b-roll reel in it, in the same fonts every time. Each reel comes out a little different, so your feed never looks samey.</p>
</header>
<div class="note"><p><b>Got your own brand colours?</b> Any kit can be made in your colours instead. Just tell Claude: <i>"use the Sage Calm kit in my own colours"</i>, and send a screenshot of your colours or paste your colour codes.</p>
<p>Your talking heads have their own look, picked in the Talking Head Lookbook.</p></div>
<main class="grid">{''.join(card(dict(k, id=kid)) for kid, k in kits.items())}
</main>
</body>
</html>
"""
    out = os.path.join(folder, "brand-kits.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(page)
    print(out)


if __name__ == "__main__":
    main(sys.argv[1])
