"""
Makes a month planner page: a calendar of every post, what it needs, and a
play button on every reel that's already made.

    python3 engine/make_planner.py "My Content/2026-10"

It reads the month's calendar.md (from plan-my-month), checks the reels folder
for finished reels, and saves planner.html in the same folder. Run it again
whenever something changes.
"""

import tools  # noqa: F401  (first: emoji-safe output on Windows)
import brand_style  # the engine's masterclass look on every page
import days
import datetime
import html
import json
import os
import re
import sys
import zipfile

LEGEND = [("signed", "Signed off, ready to post"), ("ready", "Reel ready"), ("post", "Post ready"), ("soon", "Reel coming soon"), ("clips", "Needs clips"),
          ("film", "To film"), ("canva", "Post coming"), ("meme", "Make in CapCut"),
          ("rest", "Rest day")]

STYLE = """
  :root { --ink: #2D2E30; --quiet: #6B6A68; --line: #E4DED7; --page: #FAF8F5; --nude: #E0D8D0; --grey: #DDDDD8; }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--page); color: var(--ink); font: 14px/1.45 'DM Sans', system-ui, sans-serif; }
  .wrap { max-width: 1240px; margin: 0 auto; padding: 28px 16px 40px; }
  h1 { font: 700 30px/1.15 'Playfair Display', serif; margin: 0; }
  .sub { color: var(--quiet); margin: 4px 0 14px; }
  .summary { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 18px; }
  .days, .grid { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 8px; }
  .days div { font-weight: 700; font-size: 12px; text-transform: uppercase; letter-spacing: .06em; color: var(--quiet); padding: 0 4px 4px; }
  .cell { background: #fff; border: 1px solid var(--line); border-radius: 12px; padding: 10px; min-height: 150px; display: flex; flex-direction: column; gap: 4px; position: relative; }
  .signoff { position: absolute; top: 8px; right: 8px; width: 22px; height: 22px; cursor: pointer; }
  .signoff input { position: absolute; inset: 0; opacity: 0; margin: 0; cursor: pointer; }
  .signoff .box { display: block; width: 20px; height: 20px; border: 1.5px solid #CA3232; border-radius: 5px; background: #fff; }
  .signoff input:checked + .box { background: #CA3232; border-color: #CA3232; }
  .signoff input:checked + .box::after { content: ""; position: absolute; left: 7.5px; top: 3.5px; width: 5px; height: 10px; border: solid #fff; border-width: 0 2px 2px 0; transform: rotate(45deg); }
  .signoff input:focus-visible + .box { outline: 2px solid var(--ink); outline-offset: 2px; }
  .signed-note { display: none; font-size: 10.5px; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; color: #CA3232; }
  .cell.is-signed { border-color: var(--ink); box-shadow: inset 0 0 0 1px var(--ink); }
  .cell.is-signed .signed-note { display: block; }
  .signed-count { margin: -4px 0 14px; font-size: 13px; color: var(--quiet); }
  .offer-tag { display: inline-block; align-self: flex-start; margin: 0; font-size: 10px; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; color: #CA3232; border: 1px solid #CA3232; border-radius: 999px; padding: 1px 7px; vertical-align: middle; }
  .cell.empty { background: transparent; border: none; }
  .cell.rest { background: #F3F0EC; }
  .num { font: 700 18px/1 'Playfair Display', serif; }
  .kind { margin: 0; font-size: 11px; color: var(--quiet); }
  .pick-design { display: inline-block; border-radius: 999px; background: var(--ink); color: #fff; padding: 10px 16px; font-weight: 700; text-decoration: none; }
  .film-list { display: block; width: 100%; text-align: left; border: 1px solid var(--ink); background: #fff; color: var(--ink); border-radius: 12px; padding: 12px 16px; margin: -6px 0 14px; font: 700 14.5px/1.3 'DM Sans', sans-serif; cursor: pointer; }
  .film-list:hover { background: var(--page); }
  .notes h3 { font: 700 19px/1.25 'Playfair Display', serif; margin: 18px 0 6px; }
  .notes h4 { font-size: 14px; margin: 16px 0 4px; }
  .notes p { margin: 0 0 8px; }
  .notes ul, .notes ol { margin: 0 0 10px; padding-left: 20px; }
  .notes li { margin-bottom: 4px; }
  .notes blockquote { margin: 0 0 12px; background: var(--page); border: 1px solid var(--line); border-radius: 10px; padding: 10px 12px; font-size: 14.5px; line-height: 1.55; }
  .notes .row { font-size: 13.5px; }
  .film-note { background: #FFF6E0; border: 1px solid #F0DDB0; border-radius: 12px; padding: 10px 14px; margin: -6px 0 18px; font-size: 13.5px; }
  .treat { display: inline-block; align-self: flex-start; font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 6px; }
  .treat.whole { background: #fff; color: var(--quiet); border: 1px solid var(--line); }
  .mix { display: flex; flex-wrap: wrap; gap: 6px; width: 100%; }
  .what { margin: 0; flex: 1; font-size: 12.5px; }
  .tag { display: inline-block; align-self: flex-start; font-size: 11.5px; font-weight: 700; padding: 3px 8px; border-radius: 999px; text-decoration: none; color: var(--ink); background: var(--grey); }
  .tag.ready { background: #2D2E30; color: #FAF8F5; }
  .tag.signed { background: #3E6B4C; color: #FFFFFF; }
  a.tag.signed:hover { background: #2F5239; }
  .tag.post { background: #172D5A; color: #FAF8F5; }
  .tag.soon { background: #EFE7DC; }
  .tag.film { background: var(--nude); }
  .tag.canva { background: #E3E8EC; }
  .tag.meme { background: #ECE6F0; }
  .tag.rest { background: transparent; color: var(--quiet); padding-left: 0; }
  a.tag.ready:hover, a.tag.post:hover { background: #000; }
  .actions { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 10px; }
  .dl { font-size: 11.5px; font-weight: 700; color: var(--ink); text-decoration: underline; text-underline-offset: 2px; }
  .dl:hover { color: #000; }
  button.tag { border: none; cursor: pointer; font-family: inherit; }
  button.tag.meme:hover { background: #DCD2E3; }
  dialog.meme-card { border: none; border-radius: 18px; padding: 0; width: min(560px, calc(100% - 24px)); max-height: calc(100% - 24px); color: var(--ink); }
  dialog.meme-card::backdrop { background: rgba(45, 46, 48, .6); }
  .card-in { padding: 24px 24px 22px; display: flex; flex-direction: column; gap: 16px; position: relative; }
  .card-in h2 { font: 700 24px/1.2 'Playfair Display', serif; margin: 0; padding-right: 40px; }
  .step { display: grid; grid-template-columns: 30px minmax(0, 1fr); gap: 10px; align-items: start; }
  .step b.n { width: 26px; height: 26px; border-radius: 50%; background: var(--ink); color: #fff; display: grid; place-items: center; font-size: 13px; }
  .step p { margin: 0 0 6px; }
  .qr { display: flex; gap: 14px; align-items: center; flex-wrap: wrap; }
  .qr svg { display: block; width: 180px; height: 180px; flex: none; background: #fff; border: 1px solid var(--line); border-radius: 8px; }
  .words { background: var(--page); border: 1px solid var(--line); border-radius: 10px; padding: 12px 14px; font-size: 16px; font-weight: 600; white-space: pre-wrap; }
  .copy { border: none; border-radius: 999px; background: var(--ink); color: #fff; padding: 8px 14px; font: 700 12.5px/1 'DM Sans', sans-serif; cursor: pointer; margin-top: 6px; }
  .shut { position: absolute; top: 14px; right: 14px; width: 34px; height: 34px; border-radius: 50%; border: 1px solid var(--line); background: #fff; font-size: 18px; cursor: pointer; }
  .small { color: var(--quiet); font-size: 12.5px; margin: 0; }
  .open-day { cursor: pointer; transition: box-shadow .15s ease, transform .15s ease; }
  .open-day:hover, .open-day:focus-visible { box-shadow: 0 6px 18px rgba(45, 46, 48, .12); transform: translateY(-2px); outline: none; }
  .more { font-size: 11.5px; color: var(--quiet); font-weight: 700; margin-top: 2px; }
  .field h3 { font-size: 12px; text-transform: uppercase; letter-spacing: .07em; color: var(--quiet); margin: 0 0 6px; }
  .field .words { font-weight: 500; font-size: 15px; line-height: 1.5; }
  .field .words a { color: var(--ink); word-break: break-all; }
  .preview { display: block; margin: 0 auto; width: min(100%, 300px); max-height: 60vh; border-radius: 10px; background: #000; object-fit: contain; }
  video.preview { aspect-ratio: 9 / 16; width: auto; height: min(60vh, 480px); max-width: 100%; }
  @media (max-width: 760px) {
    .days { display: none; }
    .grid { grid-template-columns: 1fr; }
    .cell.empty { display: none; }
    .cell { min-height: 0; }
  }
"""


# Soft colours for each treatment's label (a clinic with several treatments sees which day promotes which).
TREATMENT_COLOURS = [("#DCEFE7", "#1F5A45"), ("#E6E3F7", "#3C3489"), ("#F7E1D8", "#712B13"),
                     ("#F5EBD3", "#633806"), ("#E1EAF4", "#0C447C"), ("#E5EDDA", "#3B5A1C")]


def read_calendar(folder):
    """Every day in calendar.md: {day, date, key, label, type, what, needs} (days.py: a plan can run on into
    the next month, so each day has its full date, and key names it in files and links: 2026-12-01)."""
    return days.read_calendar(folder)


def day_section(posts, day):
    """A day's section of posts.md, by its date (or, for older callers, its day number)."""
    if isinstance(day, datetime.date):
        return days.section(posts, day)
    found = re.search(rf"## \w+ {day}(st|nd|rd|th) .*?(?=\n## |\Z)", posts, re.S)
    return found.group(0) if found else ""


def carousel_sheet(slides_folder):
    """One picture of every slide in a carousel, side by side, so the planner can show it in one click."""
    from PIL import Image, ImageDraw, ImageFont
    slides = sorted(f for f in os.listdir(slides_folder) if re.match(r"slide-\d+\.png$", f))
    if not slides:
        return None
    out = os.path.join(slides_folder, "all-slides.png")
    newest = max(os.path.getmtime(os.path.join(slides_folder, f)) for f in slides)
    if os.path.exists(out) and os.path.getmtime(out) >= newest:
        return out
    w, h, gap, label = 432, 540, 24, 48
    across = min(5, len(slides))
    down = -(-len(slides) // across)
    sheet = Image.new("RGB", (across * (w + gap) + gap, down * (h + label + gap) + gap), "#FAF8F5")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.truetype(os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", "DMSans.ttf"), 26)
    for i, f in enumerate(slides):
        x = gap + (i % across) * (w + gap)
        y = gap + (i // across) * (h + label + gap)
        draw.text((x, y + 8), f"Slide {i + 1}", fill="#2D2E30", font=font)
        sheet.paste(Image.open(os.path.join(slides_folder, f)).convert("RGB").resize((w, h)), (x, y + label))
    sheet.save(out)
    return out


def carousel_zip(slides_folder):
    """All of a carousel's slides in one zipped folder, so they download in one click."""
    slides = sorted(f for f in os.listdir(slides_folder) if re.match(r"slide-\d+\.png$", f))
    out = os.path.join(slides_folder, "slides.zip")
    newest = max(os.path.getmtime(os.path.join(slides_folder, f)) for f in slides)
    if not os.path.exists(out) or os.path.getmtime(out) < newest:
        with zipfile.ZipFile(out, "w", zipfile.ZIP_STORED) as z:
            for f in slides:
                z.write(os.path.join(slides_folder, f), f)
    return out


def meme_details(posts, day):
    """The meme words, caption and CapCut template (link and name) for a day (its date), from posts.md."""
    text = day_section(posts, day)

    def quoted(label):
        found = re.search(rf"\*\*{label}:\*\*\s*\n((?:>.*\n?)+)", text)
        return "\n".join(re.sub(r"^>\s?", "", l).rstrip() for l in found.group(1).splitlines()) if found else ""
    template = re.search(r"\*\*CapCut template:\*\*\s*(https?://\S+)\s*(?:\((.+?)\))?", text)
    return {"words": quoted("Meme text") or quoted("Text on screen"), "caption": quoted("Caption"),
            "link": template.group(1) if template else "", "name": (template.group(2) or "") if template else ""}


# How each kind of detail is shown on a day's card: (heading, has a Copy button), in this order.
FIELD_ORDER = [
    ("Film by", ("Film by", False)),
    ("Text on screen (hook)", ("Hook (the words on screen)", False)),
    ("Text on screen", ("Words on screen", False)),
    ("Meme text", ("Meme words", True)),
    ("Quote text", ("Quote", True)),
    ("Post writing", ("Words on the post", False)),
    ("Script", ("Script", True)),
    ("What to film", ("What to film", False)),
    ("What to do", ("What to do", False)),
    ("Caption", ("Caption to post with it", True)),
    ("Canva template", ("Canva template", False)),
    ("CapCut template", ("CapCut template", False)),
    ("Template", ("Template", False)),
    ("Example", ("An example to look at", False)),
]


def post_fields(posts, day):
    """Every detail of a day's post (its date) in posts.md, as {label: text}."""
    fields, label = {}, None
    for line in day_section(posts, day).splitlines()[1:]:
        found = re.match(r"\*\*(.+?):\*\*\s*(.*)", line) or re.match(r"\*\*(Slide \d+)\*\*\s*(.*)", line)
        if found:
            label = found.group(1).strip()
            fields[label] = found.group(2).strip()
        elif label and line.startswith(">"):
            fields[label] = (fields[label] + "\n" + re.sub(r"^>\s?", "", line).rstrip()).strip()
        elif not line.strip() or line.startswith("---"):
            label = None if not line.strip() and label and fields.get(label) else label
    return fields


def linked(text):
    """Text with any web addresses turned into links that open in a new tab."""
    parts = re.split(r"(https?://\S+)", text)
    return "".join(f'<a href="{html.escape(p, quote=True)}" target="_blank">{html.escape(p)}</a>'
                   if p.startswith("http") else html.escape(p) for p in parts)


def page_from_notes(text):
    """A month's filming list (filming-day.md) as simple HTML for the planner: headings, lists, quotes and bold."""
    def inline(line):
        line = html.escape(line)
        return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", line)
    out, listing, quote = [], None, []

    def close():
        nonlocal listing, quote
        if listing:
            out.append(f"</{listing}>")
            listing = None
        if quote:
            out.append('<blockquote>' + "<br>".join(quote) + '</blockquote>')
            quote = []
    for raw in text.splitlines():
        line = raw.rstrip()
        bullet = re.match(r"^\s*[-*] (.*)", line)
        number = re.match(r"^\s*\d+\. (.*)", line)
        if line.startswith(">"):
            if listing:
                out.append(f"</{listing}>")
                listing = None
            quote.append(inline(line.lstrip("> ").rstrip()))
            continue
        if bullet or number:
            kind = "ul" if bullet else "ol"
            if quote or listing != kind:
                close()
                out.append(f"<{kind}>")
                listing = kind
            out.append(f"<li>{inline((bullet or number).group(1))}</li>")
            continue
        close()
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if all(set(c) <= set("-: ") for c in cells):
                continue
            out.append("<p class='row'>" + " · ".join(inline(c) for c in cells if c) + "</p>")
        elif line.startswith("### "):
            out.append(f"<h4>{inline(line[4:])}</h4>")
        elif line.startswith("## "):
            out.append(f"<h3>{inline(line[3:])}</h3>")
        elif line.startswith("# ") or line.strip() == "---" or not line.strip():
            continue
        else:
            out.append(f"<p>{inline(line)}</p>")
    close()
    return "".join(out)


def qr_svg(link):
    """A QR code for a link, to scan with a phone camera (segno, BSD licence). None if segno isn't there."""
    try:
        import segno
    except ImportError:
        return None
    # omitsize: the code scales to fit its box (a fixed size squeezed into a smaller box gets cut off).
    return segno.make(link, error="m").svg_inline(scale=1, dark="#000000", light="#FFFFFF", border=3,
                                                  omitsize=True)


def meme_steps(meme):
    """How to make a meme from its CapCut template, step by step, with a QR code for the phone."""
    qr = qr_svg(meme["link"])
    link = html.escape(meme["link"], quote=True)
    scan = (f'<div class="qr">{qr}<p class="small">Point your phone camera at this square and tap the link '
            f'that appears. Or <a href="{link}" target="_blank">open the template here</a>.</p></div>'
            if qr else f'<p><a href="{link}" target="_blank">Open the template</a> on your phone.</p>')
    name = f' ({html.escape(meme["name"])})' if meme["name"] else ""
    return f"""<div class="step"><b class="n">1</b><div><p>Open the CapCut template{name} on your phone.</p>{scan}</div></div>
    <div class="step"><b class="n">2</b><div><p>Tap <b>Use template</b> and add a plain photo of your clinic: your reception or your treatment room.</p></div></div>
    <div class="step"><b class="n">3</b><div><p>Tap the words on the screen and type these, exactly:</p>
      <div class="words">{html.escape(meme["words"])}</div><button class="copy" type="button">Copy the words</button></div></div>
    <div class="step"><b class="n">4</b><div><p>Tap <b>Export</b>, then post it on Instagram with this caption:</p>
      <div class="words">{html.escape(meme["caption"])}</div><button class="copy" type="button">Copy the caption</button></div></div>
    <p class="small">On a Mac and iPhone with the same Apple ID, what you copy here can be pasted on your phone.</p>"""


def day_card(day, date_name, row_type, fields, made=None, picture=None, meme=None, download=None, treatment="",
             design=None, design_label="🎨 Pick your design for this post"):
    """Everything about one day's post in a pop-up card: the finished reel or post (when it's made),
    then the hook, script, words, what to film and the caption, each with a Copy button where useful."""
    parts = []
    if made:
        parts.append(f'<video class="preview" src="{made}" controls playsinline preload="metadata"></video>')
    elif picture:
        parts.append(f'<img class="preview" src="{picture}" alt="">')
    if download:
        parts.append(download)
    if design:   # a Canva post not made yet: pick its design in the post library
        parts.append(f'<p><a class="pick-design" href="{design}" target="_blank">{design_label}</a></p>')
    if meme and meme["link"] and not made:
        parts.append(meme_steps(meme))
    else:
        slides = sorted((k for k in fields if re.fullmatch(r"Slide \d+", k)), key=lambda k: int(k.split()[1]))
        if slides:
            parts.append('<div class="field"><h3>The slides</h3>' + "".join(
                f'<div class="words"><b>{html.escape(k)}</b><br>{linked(fields[k])}</div>' for k in slides) + '</div>')
        for key, (heading, copy) in FIELD_ORDER:
            text = fields.get(key, "").strip()
            if not text or ("emplate" in key and "http" not in text):   # "no template for this one" isn't worth showing
                continue
            button = f'<button class="copy" type="button">Copy</button>' if copy else ""
            parts.append(f'<div class="field"><h3>{heading}</h3><div class="words">{linked(text)}</div>{button}</div>')
    return f"""<dialog class="meme-card" id="day-{day}">
  <div class="card-in">
    <button class="shut" type="button" aria-label="Close">×</button>
    <h2>{html.escape(date_name)}</h2>
    <p class="small">{html.escape(row_type)}{treatment}</p>
    {''.join(parts)}
  </div>
</dialog>"""


def status(row, made, pictures=None):
    """What this day needs, in plain words, and a link if its reel is ready."""
    needs = row["needs"].lower()
    if "rest" in needs:
        return "rest", "Rest day", None
    if row["key"] in made:
        return "ready", "Reel ready", f"reels/{row['key']}.mp4"
    if row["key"] in (pictures or {}):
        return "post", "Post ready", pictures[row["key"]]
    if "talking head" in needs:
        return "film", "Film talking head", None
    if "canva" in needs:
        return "canva", "Post coming", None
    if "meme" in needs or "capcut" in needs:
        return "meme", "Make in CapCut", None
    if row.get("one_by_one"):  # pictures appearing under labels (cut-outs): the engine can't make these yet
        return "soon", "Coming soon", None
    return "clips", "Needs clips", None


def signed_off(folder):
    """The days the clinic has signed off (checked and happy to post), from signed-off.json in the month:
    {"days": ["2026-10-13", "2026-10-16"]} (older ones say [13, 16]: days in the folder's month). Claude adds
    a day when they say it's signed off."""
    path = os.path.join(folder, "signed-off.json")
    if not os.path.exists(path):
        return set()
    year, month = days.start_of(folder)
    with open(path, encoding="utf-8") as f:
        return {str(day) if "-" in str(day) else f"{year}-{month:02d}-{int(day):02d}"
                for day in json.load(f).get("days", [])}


def main(folder):
    rows = read_calendar(folder)
    reels = os.path.join(folder, "reels")
    # Finished reels (and talking heads) are named by their date, e.g. 2026-10-03.mp4; anything else is ignored.
    made = ({f[:10] for f in os.listdir(reels) if re.fullmatch(r"\d{4}-\d{2}-\d{2}\.mp4", f)}
            if os.path.isdir(reels) else set())
    # Finished posts: a single picture (posts/2026-10-05.png) or a carousel, a folder of slides (posts/2026-10-21/).
    posts_folder = os.path.join(folder, "posts")
    pictures, downloads = {}, {}
    for f in sorted(os.listdir(posts_folder)) if os.path.isdir(posts_folder) else []:
        if re.match(r"\d{4}-\d{2}-\d{2}\.png$", f):
            pictures[f[:10]] = f"posts/{f}"
            downloads[f[:10]] = (f"posts/{f}", "post.png")
        elif re.match(r"\d{4}-\d{2}-\d{2}$", f) and carousel_sheet(os.path.join(posts_folder, f)):
            pictures[f] = f"posts/{f}/all-slides.png"
            carousel_zip(os.path.join(posts_folder, f))
            downloads[f] = (f"posts/{f}/slides.zip", "carousel.zip")
    for day in made:
        downloads[day] = (f"reels/{day}.mp4", "reel.mp4")

    clinic = "My"
    profile = os.path.join(os.path.dirname(os.path.normpath(folder)), "my-clinic.md")
    if os.path.exists(profile):
        found = re.search(r"\*\*Clinic name:\*\* (.+)", open(profile, encoding="utf-8").read())
        clinic = found.group(1).strip() if found else clinic
    month_name = days.month_names(rows)      # "November", or "November and December" for a plan that runs on
    one_month = " and " not in month_name

    # Reels whose look they pick one at a time (reel_picks.py), when that page has been made.
    to_pick = set()
    if os.path.exists(os.path.join(folder, "reel-picks", "index.html")):
        picked = re.search(r'id="reels-data">(.*?)</script>', open(os.path.join(folder, "reel-picks", "index.html"),
                                                                 encoding="utf-8").read(), re.S)
        to_pick = {r["date"] for r in json.loads(picked.group(1).replace("<\\/", "</"))["reels"]} if picked else set()

    # Reels the engine can't make yet (cut-outs: pictures appearing under labels). Lines appearing one by one
    # are made by list_reel.py (since 2026-10-09), so those just need clips like any other reel.
    posts = open(os.path.join(folder, "posts.md"), encoding="utf-8").read()
    for row in rows:
        text = days.section(posts, row["date"])
        row["one_by_one"] = bool(re.search(r"cut-outs", text))

    # Which treatment each post promotes (plan-my-month writes "Treatment:" on treatment posts). Labels only show
    # when the month covers more than one treatment; the rest are whole-clinic posts.
    treatments = {row["key"]: post_fields(posts, row["date"]).get("Treatment", "").strip() for row in rows}
    names = list(dict.fromkeys(t for t in treatments.values() if t))
    if len(names) < 2:
        treatments, names = {}, []
    colours = {t: TREATMENT_COLOURS[i % len(TREATMENT_COLOURS)] for i, t in enumerate(names)}

    def treatment_label(day):
        t = treatments.get(day)
        if not t:
            return ""
        back, ink = colours[t]
        return f'<span class="treat" style="background:{back};color:{ink}">{html.escape(t)}</span>'

    # Posts that need new filming carry a "Film by" date (film_later.py): shown on the day, and the first one
    # still to film goes in a note at the top, so they know from day one.
    film_by = {row["key"]: post_fields(posts, row["date"]).get("Film by", "").strip() for row in rows}
    to_film = [row["key"] for row in rows if film_by.get(row["key"]) and row["key"] not in made
               and row["key"] not in pictures]

    # A plan can start partway through the month, so line the grid up from its first day.
    signed = signed_off(folder)
    counts, cells = {}, ['<div class="cell empty"></div>'] * rows[0]["date"].weekday()
    cards = []
    for i, row in enumerate(rows):
        day, date = row["key"], row["date"]
        # Days they don't post (on 5 or 3 days a week, 2026-11-18) keep their place in the week: a faint number,
        # no post, so every post sits under its own weekday.
        if i:
            for gap in range(1, (date - rows[i - 1]["date"]).days):
                off = rows[i - 1]["date"] + datetime.timedelta(days=gap)
                cells.append(f'<div class="cell empty"><div class="num" style="opacity:.3">{off.day}</div></div>')
        # The 1st of a month that isn't the plan's first month says which month it is ("1 Dec").
        number = f"{date.day} {date:%b}" if date.day == 1 and i else str(date.day)
        key, label, link = status(row, made, pictures)
        if day in to_film and key in ("film", "clips", "soon"):
            key = "film"
            label = "Film by " + re.sub(r"^(\w{3})\w* (\d+\w+).*", r"\1 \2", film_by[day])
        meme = meme_details(posts, date) if key == "meme" else None
        if meme and not meme["link"]:
            key, label = "soon", "Meme coming"   # no template: the engine makes it (make my memes)
        shown = key                                # the tag's colour; key still decides what the day's card shows
        counts[shown] = counts.get(shown, 0) + 1
        # A day that carries the clinic's offer this month (plan-my-month: **Promotion:**) gets a small red Offer label.
        offer = ('<span class="offer-tag">Offer</span>'
                 if key != "rest" and post_fields(posts, date).get("Promotion") else "")
        kind = "" if key == "rest" else f'{treatment_label(day)}{offer}<p class="kind">{html.escape(row["type"])}</p>'
        what = "" if key == "rest" else f'<p class="what">{html.escape(row["what"])}</p>'
        tag = (f'<a class="tag {shown}" href="{link}" target="_blank">{"" if shown == "signed" else "▶ "}{label}</a>' if link
               else f'<span class="tag {shown}">{label}</span>')
        if meme and meme["link"]:
            tag = f'<button class="tag meme" type="button" data-card="day-{day}">📱 {label}</button>'
        download = ""
        if link and day in downloads:
            # A download button, saving the file with a name they'll recognise, e.g. "Skin Survival 21 October carousel.zip".
            path, ending = downloads[day]
            name = html.escape(f"{clinic} {date.day} {date:%B} {ending}", quote=True)
            download = f'<a class="dl" href="{path}" download="{name}">⬇ Download</a>'
            tag = f'<div class="actions">{tag}{download}</div>'
        if key == "rest":
            cells.append(f'<div class="cell {key}"><div class="num">{number}</div>{kind}{what}{tag}</div>')
            continue
        date_name = f"{date:%A} {date.day} {date:%B}"
        cards.append(day_card(day, date_name, row["type"], post_fields(posts, date),
                              made=link if key == "ready" else None,
                              picture=link if key == "post" else None, meme=meme,
                              download=f'<p>{download}</p>' if download else None,
                              treatment=f" · {html.escape(treatments[day])}" if treatments.get(day) else "",
                              design=(f"../library/index.html#day-{day}"
                                      if "canva" in row["needs"].lower() and key != "post" else
                                      f"reel-picks/index.html#day-{day}"
                                      if day in to_pick and key != "ready" else None),
                              design_label=("🎨 Pick the look for this reel" if day in to_pick
                                            else "🎨 Pick your design for this post")))
        more = '<span class="more">See everything ›</span>'
        # Frances, 2026-11-20: "a tick box on each day on the calendar when it's been checked and signed off":
        # "reel ready means it's been made, and the tick box means all amendments have been made and it's fully ready".
        tick = (f'<label class="signoff" title="Tick when all the changes are done and it’s fully ready to post">'
                f'<input type="checkbox" data-sign="{day}"{" checked" if day in signed else ""} '
                f'aria-label="Fully ready to post: {html.escape(date_name, quote=True)}"><span class="box"></span></label>')
        cells.append(f'<div class="cell {key} open-day{" is-signed" if day in signed else ""}" data-card="day-{day}" '
                     f'tabindex="0" role="button" aria-label="See everything for {html.escape(date_name, quote=True)}">'
                     f'{tick}<div class="num">{number}</div><span class="signed-note">✓ Fully ready to post</span>'
                     f'{kind}{what}{tag}{more}</div>')

    posts_count = sum(v for k, v in counts.items() if k != "rest")
    # The month's filming list (what to film, the scripts, the directions), from plan-my-month.
    filming = ""
    notes = os.path.join(folder, "filming-day.md")
    if os.path.exists(notes):
        filming = ('<button class="film-list" type="button" data-card="filming">🎬 Your filming list: '
                   'what to film, scripts and directions</button>')
        cards.append(f"""<dialog class="meme-card" id="filming">
  <div class="card-in">
    <button class="shut" type="button" aria-label="Close">×</button>
    <h2>What to film{" this month" if one_month else ""}</h2>
    <div class="notes">{page_from_notes(open(notes, encoding="utf-8").read())}</div>
  </div>
</dialog>""")

    film_note = ""
    if to_film:
        first = film_by[min(to_film)]
        film_note = (f'<p class="film-note">🎬 <b>{len(to_film)} {"post needs" if len(to_film) == 1 else "posts need"} '
                     f'new filming{" this month" if one_month else ""}.</b> The first is needed by {html.escape(first)}. '
                     f'They\'re as late{" in the month" if one_month else ""} as they can go, to give you time. '
                     f'Everything to film is on your filming list.</p>')
    summary = "".join(f'<span class="tag {k}">{counts[k]} · {l}</span>' for k, l in LEGEND if counts.get(k))
    if names:   # the balance of treatments this month, e.g. "Skin 5 · Laser 3 · Body 3 · Whole clinic 15"
        whole = sum(1 for row in rows if row["type"] and not treatments.get(row["key"]) and "rest" not in row["needs"].lower())
        mix = [f'<span class="treat" style="background:{colours[t][0]};color:{colours[t][1]}">'
               f'{html.escape(t)} · {sum(1 for v in treatments.values() if v == t)}</span>' for t in names]
        if whole:
            mix.append(f'<span class="treat whole">Whole clinic · {whole}</span>')
        summary += f'<div class="mix">{"".join(mix)}</div>'

    page = f"""<!doctype html>
<html lang="en-GB">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{month_name} Planner</title>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600;700&family=DM+Sans:wght@400;500;700&display=swap" rel="stylesheet">
<style>{STYLE}</style>
</head>
<body>
<div class="wrap">
  <h1>{html.escape(clinic)} · {month_name} planner</h1>
  <p class="sub">{posts_count} posts{f" and {counts['rest']} rest days" if counts.get('rest') else ""}. Tap any day to see everything for it: the hook, the script, what to film and the caption to copy. Press "Download" to save a finished reel or post.</p>
  <div class="summary">{summary}</div>
  <p class="signed-count" aria-live="polite">{len([r for r in rows if r["key"] in signed])} fully ready to post</p>
  {filming}
  {film_note}
  <div class="days"><div>Mon</div><div>Tue</div><div>Wed</div><div>Thu</div><div>Fri</div><div>Sat</div><div>Sun</div></div>
  <div class="grid">{''.join(cells)}</div>
</div>
{''.join(cards)}
<script>
document.querySelectorAll('[data-card]').forEach(b => {{
  const open = e => {{
    if (e.target.closest('a, .signoff')) return;   // "Reel ready", "Download" and the tick box work as before
    e.stopPropagation();
    document.getElementById(b.dataset.card).showModal();
  }};
  b.addEventListener('click', open);
  b.addEventListener('keydown', e => {{ if (e.key === 'Enter' || e.key === ' ') {{ e.preventDefault(); open(e); }} }});
}});
document.querySelectorAll('dialog').forEach(d => d.addEventListener('close', () =>
  d.querySelectorAll('video').forEach(v => v.pause())));
document.querySelectorAll('dialog.meme-card').forEach(d => {{
  d.addEventListener('click', e => {{ if (e.target === d) d.close(); }});
  d.querySelector('.shut').addEventListener('click', () => d.close());
}});
document.querySelectorAll('.copy').forEach(b => b.addEventListener('click', async () => {{
  const words = b.previousElementSibling.innerText;
  try {{ await navigator.clipboard.writeText(words); b.textContent = 'Copied'; }}
  catch (e) {{ b.textContent = 'Select the words above to copy them'; }}
}}));
// The sign-off ticks: saved in the month's signed-off.json through show.py's little server (so Claude and the
// next planner know), or in this browser when the page was opened straight from the computer.
const boxes = [...document.querySelectorAll('input[data-sign]')];
const signKey = 'cce-signed:' + location.pathname;
const folder = decodeURIComponent(location.pathname).replace(/\\/[^\\/]*$/, '');
function paintSigned() {{
  boxes.forEach(b => b.closest('.cell').classList.toggle('is-signed', b.checked));
  const n = boxes.filter(b => b.checked).length;
  document.querySelectorAll('.signed-count').forEach(el => el.textContent = n + ' of ' + boxes.length + ' fully ready to post (ticked once all the changes are done)');
}}
async function saveSigned(day, on) {{
  if (location.protocol.startsWith('http')) {{
    try {{
      const r = await fetch('/__clinic_engine__/signoff', {{ method: 'POST', headers: {{ 'Content-Type': 'application/json' }},
                                                          body: JSON.stringify({{ folder, day, on }}) }});
      if (r.ok) return;
    }} catch (e) {{}}
  }}
  try {{ localStorage.setItem(signKey, JSON.stringify(boxes.filter(b => b.checked).map(b => b.dataset.sign))); }} catch (e) {{}}
}}
boxes.forEach(b => b.addEventListener('change', () => {{ paintSigned(); saveSigned(b.dataset.sign, b.checked); }}));
(async () => {{
  let days = null;
  if (location.protocol.startsWith('http')) {{
    try {{ const r = await fetch('signed-off.json', {{ cache: 'no-store' }}); if (r.ok) days = (await r.json()).days || []; }} catch (e) {{}}
  }}
  if (days === null) {{ try {{ days = JSON.parse(localStorage.getItem(signKey) || 'null'); }} catch (e) {{}} }}
  if (days) {{
    const month = (folder.match(/(\\d{{4}}-\\d{{2}})$/) || [])[1];
    const set = new Set(days.map(d => /^\\d+$/.test(String(d)) && month ? month + '-' + String(d).padStart(2, '0') : String(d)));
    boxes.forEach(b => b.checked = set.has(b.dataset.sign));
  }}
  paintSigned();
}})();
// Shown through show.py's little server, Download asks it to save the file under its friendly name
// (opened straight from the computer, browsers often play the video instead).
document.addEventListener('click', e => {{
  const a = e.target.closest('a[download]');
  if (!a || !location.protocol.startsWith('http')) return;
  const u = new URL(a.getAttribute('href'), location.href);
  u.searchParams.set('dl', a.getAttribute('download'));
  a.href = u.href;
}}, true);
</script>
</body>
</html>
"""
    out = os.path.join(folder, "planner.html")
    open(out, "w", encoding="utf-8").write(brand_style.apply(page))
    print(out)


if __name__ == "__main__":
    main(sys.argv[1])
