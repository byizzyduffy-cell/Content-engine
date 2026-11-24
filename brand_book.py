"""
A clinic's own brand book (Frances, 2026-10-11): "if the clinic is very
established, they'll have their own fonts, colours. So make their own brand
book that will automatically just update into the content."

It lives in the student's My Content/brand folder:
    brand-book.json   their clinic name, handle, colours and fonts
    fonts/            their own font files (only fonts they own the licence for;
                      they stay on their computer and are never shared)
    logo.png          their logo, if they have one

    {"clinic": "Glow & Co", "handle": "@glowandco",
     "colours": {"main": "#C9A9A6", "light": "#F4ECE8", "dark": "#2E2A29", "accent": "#8C6E5A"},
     "fonts": {"headings": {"name": "Their Heading Font", "file": "Heading.ttf"},
               "body": {"name": "Their Body Font", "file": "Body.otf"}},
     "logo": "logo.png"}

Everything reads it on its own: their fonts are added to the engine's fonts
(so reels, talking heads and captions can use them by name), packs.py offers
them as "My brand fonts", and reels and posts use their colours. Change the
brand book and the next thing made follows it.

    .venv/bin/python engine/brand_book.py page     # makes My Content/brand/brand-book.html to look at
"""

import tools  # noqa: F401  (first: emoji-safe output on Windows)
import brand_style  # the engine's masterclass look on every page
import html
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FOLDER = os.path.join(os.path.dirname(HERE), "My Content", "brand")
PATH = os.path.join(FOLDER, "brand-book.json")


def load():
    """The brand book, or {} if they haven't got one yet."""
    try:
        with open(PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def font_files():
    """{font name: full path} for each of their own fonts that's really there."""
    found = {}
    for role, font in (load().get("fonts") or {}).items():
        if isinstance(font, dict) and font.get("name") and font.get("file"):
            path = os.path.join(FOLDER, "fonts", font["file"])
            if os.path.exists(path):
                found[font["name"]] = path
    return found


def font(role):
    """The name of their headings or body font, if they have one ("" if not)."""
    name = ((load().get("fonts") or {}).get(role) or {}).get("name", "")
    return name if name in font_files() else ""


def colours():
    """Their colours as a list, lightest first is not promised: main, light, dark, accent (whichever they have)."""
    c = load().get("colours") or {}
    return [c[k] for k in ("main", "light", "dark", "accent") if c.get(k)]


def page():
    """A simple page showing their brand book: colours, fonts written in their fonts, logo and handle."""
    book = load()
    if not book:
        raise SystemExit("There's no brand book yet.")
    faces, samples = [], []
    for role, label in (("headings", "Headings"), ("body", "Body text")):
        f = (book.get("fonts") or {}).get(role)
        if f and f.get("file"):
            faces.append(f"@font-face {{ font-family: '{f['name']}'; src: url('fonts/{f['file']}'); }}")
            samples.append(f'<div class="font"><h3>{label}: {html.escape(f["name"])}</h3>'
                           f'<p style="font-family:\'{f["name"]}\'">Your skin, your plan, your clinic</p></div>')
    swatches = "".join(f'<div class="sw"><span style="background:{v}"></span><b>{html.escape(k.title())}</b><i>{v}</i></div>'
                       for k, v in (book.get("colours") or {}).items())
    logo = f'<img class="logo" src="{html.escape(book["logo"])}" alt="">' if book.get("logo") else ""
    out = os.path.join(FOLDER, "brand-book.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(brand_style.apply(f"""<!doctype html><html lang="en-GB"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>My Brand Book</title>
<style>{''.join(faces)}
body {{ margin: 0; background: #FAF8F5; color: #2D2E30; font: 15px/1.5 system-ui, sans-serif; }}
.wrap {{ max-width: 760px; margin: 0 auto; padding: 32px 16px 48px; }}
h1 {{ font: 700 30px/1.2 Georgia, serif; margin: 0 0 4px; }} .handle {{ color: #6B6A68; margin: 0 0 24px; }}
.logo {{ max-width: 160px; max-height: 120px; display: block; margin-bottom: 20px; }}
h2 {{ font-size: 13px; text-transform: uppercase; letter-spacing: .08em; color: #6B6A68; margin: 28px 0 10px; }}
.swatches {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); gap: 12px; }}
.sw span {{ display: block; height: 70px; border-radius: 12px; border: 1px solid #E4DED7; margin-bottom: 6px; }}
.sw b {{ display: block; }} .sw i {{ font-style: normal; color: #6B6A68; font-size: 13px; }}
.font {{ background: #fff; border: 1px solid #E4DED7; border-radius: 12px; padding: 14px 16px; margin-bottom: 10px; }}
.font h3 {{ margin: 0 0 6px; font-size: 13px; color: #6B6A68; font-weight: 600; }} .font p {{ margin: 0; font-size: 30px; }}
.note {{ color: #6B6A68; font-size: 14px; margin-top: 26px; }}
</style></head><body><div class="wrap">{logo}
<h1>{html.escape(book.get('clinic', 'My brand book'))}</h1><p class="handle">{html.escape(book.get('handle', ''))}</p>
<h2>Colours</h2><div class="swatches">{swatches}</div>
<h2>Fonts</h2>{''.join(samples) or '<p>No fonts of your own yet: the engine uses the fonts you picked in your lookbooks.</p>'}
<p class="note">Your reels, talking heads and posts all use these automatically. To change anything, just tell Claude, e.g. "update my brand book: my main colour is now sage green".</p>
</div></body></html>""", with_logo=False))
    return out


if __name__ == "__main__":
    if sys.argv[1:] == ["page"]:
        print(page())
    else:
        print(json.dumps(load(), indent=1, ensure_ascii=False) or "No brand book yet.")
