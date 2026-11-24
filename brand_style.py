"""
The Clinic Content Engine's look on every page it makes (Frances, 2026-11-20: "brand anyone using the engine fully
out... so if they sign up to the masterclass, they go into the engine, it all feels like the same sort of
branding"). Her masterclass slides: soft off-white paper, black writing, elegant italic headings (Cormorant
Garamond), spaced capitals for labels and buttons (Montserrat), and a little touch of red. The same look as the
engine's panel in the Claude app (engine/app).

Every page builder (the post library, both lookbooks, the planner, the picks pages, the brand book) passes its
finished page through apply(), which swaps in the fonts, lays this look over the page's own (they all share the
same colour names: --ink, --quiet, --line, --page, --card, --nude, --grey, --shade, --on-ink) and puts the logo at
the top. A page's own design stays underneath, so its layout never breaks.
"""

import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))

FONTS_LINK = ('<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,500;0,600;1,400;'
              '1,500&family=Montserrat:wght@400;500;600;700&display=swap" rel="stylesheet">')
OLD_LINK = re.compile(r'<link href="https://fonts\.googleapis\.com/css2\?family=Playfair[^>]*>')

SERIF = "'Cormorant Garamond', 'Cormorant', Georgia, 'Times New Roman', serif"
SANS = "'Montserrat', system-ui, -apple-system, 'Segoe UI', sans-serif"

# The headings and labels each page uses (they're named the same way across the pages).
HEADINGS = "h1, h2, .name, .details h2, .mine h2, .notes h3, .card-in h2, .question h3, .num"
LABELS = (".tab, .tag, .ours, .pick, .copy, .save, .use button, .details h3, .chip, .film-list, .bar-text b, "
          ".step-label, .eyebrow")

CSS = f"""
  /* The masterclass look (engine/brand_style.py), laid over the page's own design. */
  :root {{ --ink: #111111; --quiet: #6B6A67; --line: #E1E0E0; --page: #F5F4F1; --card: #FDFCFB; --nude: #ECEAE6;
          --grey: #E1E0E0; --shade: rgba(17, 17, 17, .6); --on-ink: #F5F4F1; --red: #CA3232; }}
  @media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{ --ink: #F2F0EC; --quiet: #A9A49C;
          --line: #3A3A3B; --page: #1B1B1C; --card: #232324; --nude: #2E2E2F; --grey: #2A2A2B; --shade: rgba(0, 0, 0, .7);
          --on-ink: #1B1B1C; --red: #E05A55; color-scheme: dark; }} }}
  :root[data-theme="dark"] {{ --ink: #F2F0EC; --quiet: #A9A49C; --line: #3A3A3B; --page: #1B1B1C; --card: #232324;
          --nude: #2E2E2F; --grey: #2A2A2B; --shade: rgba(0, 0, 0, .7); --on-ink: #1B1B1C; --red: #E05A55; color-scheme: dark; }}
  body {{ font-family: {SANS}; background: var(--page); color: var(--ink); letter-spacing: .005em; }}
  input, textarea, select, button {{ font-family: {SANS}; }}

  /* Headings: the masterclass italic. */
  {HEADINGS} {{ font-family: {SERIF} !important; font-style: italic; font-weight: 500 !important; letter-spacing: 0; }}
  h1 {{ font-size: clamp(38px, 5.2vw, 56px) !important; line-height: 1.02 !important; text-wrap: balance; }}
  h1::after {{ content: ""; display: block; width: 56px; height: 1px; background: var(--red); margin-top: 16px; }}
  h2 {{ font-size: clamp(24px, 3vw, 32px) !important; line-height: 1.1 !important; text-transform: none !important; letter-spacing: 0 !important; color: var(--ink) !important; }}
  .name {{ font-size: 21px !important; line-height: 1.15 !important; }}

  /* Labels and buttons: spaced capitals. */
  {LABELS} {{ font-family: {SANS} !important; text-transform: uppercase; letter-spacing: .14em;
             font-weight: 600 !important; font-size: 11px !important; line-height: 1.2 !important; }}
  .pick, .copy, .save, .use button {{ padding: 12px 20px !important; }}
  .tick, .post, .dot, .n {{ font-family: {SANS} !important; }}

  /* A little touch of red. */
  .ours {{ color: var(--red) !important; }}
  .note {{ background: var(--card) !important; border: 1px solid var(--line); border-left: 2px solid var(--red); border-radius: 4px !important; padding: 12px 16px !important; }}
  :focus-visible {{ outline-color: var(--red) !important; }}
  a {{ color: inherit; text-decoration-color: var(--red); text-underline-offset: 3px; }}

  /* Calmer cards, like the slides: paper on paper. */
  .card {{ border-radius: 10px; box-shadow: none; }}
  .card:hover, .card:focus-visible {{ box-shadow: 0 10px 26px rgba(17, 17, 17, .08); }}

  /* The planner's day boxes and labels, in her palette (no navy, yellow or pastels). */
  .cell {{ background: var(--card) !important; }}
  .cell.rest {{ background: var(--nude) !important; }}
  .cell.empty {{ background: transparent !important; border-color: transparent !important; }}
  .tag.ready {{ background: var(--ink) !important; color: var(--on-ink) !important; }}
  .tag.post {{ background: transparent !important; color: var(--ink) !important; box-shadow: inset 0 0 0 1px var(--ink); }}
  a.tag.post:hover {{ background: var(--ink) !important; color: var(--on-ink) !important; }}
  .tag.soon, .tag.canva, .tag.meme {{ background: var(--nude) !important; color: var(--ink) !important; }}
  .film-note {{ background: var(--card) !important; border: 1px solid var(--line) !important; border-left: 2px solid var(--red) !important; border-radius: 4px !important; }}
  .film-list {{ background: var(--card) !important; color: var(--ink) !important; border-radius: 4px !important; }}
  .pick-design {{ color: var(--on-ink) !important; text-transform: uppercase; letter-spacing: .14em; font-size: 11px; }}

  /* The planner's "fully ready to post" tick box. */
  .signoff .box {{ background: var(--card) !important; border-color: var(--red) !important; }}
  .signoff input:checked + .box {{ background: var(--red) !important; border-color: var(--red) !important; }}
  .signoff input:checked + .box::after {{ border-color: #FFFFFF !important; }}
  .signoff input:focus-visible + .box {{ outline-color: var(--red) !important; }}
  .signed-note {{ color: var(--red) !important; font-family: {SANS} !important; }}
  .cell.is-signed {{ border-color: var(--ink) !important; }}

  /* The logo at the top of each page. */
  .cce-top {{ display: flex; align-items: center; gap: 14px; margin: 0 0 26px; }}
  .cce-top svg {{ width: 190px; max-width: 50vw; height: auto; display: block; }}
  .cce-i {{ fill: var(--ink); }}
  .cce-r {{ fill: var(--red); }}
"""


def logo():
    try:
        return open(os.path.join(HERE, "brand_logo.svg"), encoding="utf-8").read().strip()
    except OSError:
        return ""


def apply(html, with_logo=True):
    """The page in the engine's look: the masterclass fonts, the look laid over its own, the logo above the title."""
    if "cce-brand" in html:
        return html
    if OLD_LINK.search(html):
        html = OLD_LINK.sub(FONTS_LINK, html, count=1)
    else:
        html = html.replace("<style>", FONTS_LINK + "\n<style>", 1)
    end = html.rfind("</style>")
    style = f'<style id="cce-brand">{CSS}</style>'
    html = html[:end + len("</style>")] + "\n" + style + html[end + len("</style>"):] if end >= 0 else style + html
    mark = logo()
    if with_logo and mark:
        # the logo says it now: drop a page's own small "Clinic Content Engine" line above the title
        html = re.sub(r'\s*<p class="eyebrow">Clinic Content Engine</p>', "", html, count=1)
        m = re.search(r"<h1[\s>]", html)
        if m:
            html = html[:m.start()] + f'<div class="cce-top">{mark}</div>\n' + html[m.start():]
    return html
