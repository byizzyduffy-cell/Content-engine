"""
The page where a student picks the look for ONE talking head (Frances, 2026-10-15: "prompt them to pick a
different talking head design from each single post... It's not, let's make everything look the same").

Their fonts and brand colour stay the same on every video (their brand); everything else is picked for this
video: the caption style and where the captions sit, how the pop-up words come up, how the hook arrives and
where it sits, and the cuts. The captions, pop-ups and hook are shown on stills of their own video, with
their own words; the hook's arrival and the cuts move, so those show the lookbook's sample videos.
A good mix is ticked already ("Our pick"): their usual look comes up most, but never everything the same
as their last video.

Run it after the cut, once hook.json and notes.json are written:

    PY engine/th_picks.py "<work folder>" --pack elegant --accent "#B8AFA4" --captions pop --position chin
        --popup-style notes --hook there --hook-place top --cut glide [--headline ...] [--writing ...]
        [--caption-font ...] [--plain-captions] [--caption-scale 0.75] [--popups-below] [--palette "..."]
        [--popup-scale 0.85] [--hook-lines 2]

The --captions ... --cut options are their usual look ("## My talking head look" in their profile). It
writes <work>/picks.json (our pick) and <work>/picks/index.html. Their picks come back as
my-talking-head-picks.json in Downloads, or pasted: "My talking head picks for <name>: ...".
"""

import tools  # noqa: F401  (first: emoji-safe output on Windows)
import brand_style  # the engine's masterclass look on every page
import argparse
import glob
import html
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image  # noqa: E402

import captions  # noqa: E402
import hook as hooks  # noqa: E402
import notes as handwritten  # noqa: E402
import packs  # noqa: E402
import talking_head  # noqa: E402

TILE = 300          # each picture's width on the page

# What's picked for each video, in the page's order: (key, heading, options {key: name}, shown on).
SECTIONS = [
    ("captions", "Caption style", {k: d["name"] for k, d in captions.DESIGNS.items()}, "still"),
    ("position", "Where your captions sit", {k: p["name"] for k, p in captions.POSITIONS.items()}, "still"),
    ("popup_style", "How your pop-up words come up", {k: p["name"] for k, p in handwritten.POPUP_STYLES.items()}, "still"),
    ("hook", "How your hook arrives", {k: s["name"] for k, s in hooks.STYLES.items()}, "sample"),
    ("hook_place", "Where your hook sits", {k: p["name"] for k, p in hooks.PLACES.items()}, "still"),
    ("cut", "Your cuts", {k: c["name"] for k, c in talking_head.CUT_STYLES.items()}, "sample"),
]
SAMPLE_NAMES = {"hook": "hook-{}", "cut": "cut-{}"}     # the lookbook's sample videos
GENTLE_CUTS = ("glide", "push", "punch")


def content_root(path):
    folder = os.path.abspath(path)
    while os.path.basename(folder) != "My Content":
        up = os.path.dirname(folder)
        if up == folder:
            return None
        folder = up
    return folder


def last_picks(work):
    """The picks for their most recent other talking head, or {}."""
    root = content_root(work)
    found = [p for p in glob.glob(os.path.join(root or work, "*", "talking-heads", "*", "picks.json"))
             if os.path.dirname(os.path.abspath(p)) != os.path.abspath(work)]
    if not found:
        return {}
    newest = max(found, key=os.path.getmtime)
    return json.load(open(newest, encoding="utf-8")).get("picks", {})


def our_pick(usual, previous, seed):
    """Their usual look comes up most (three times as likely as any other option), never the same as their
    last video's choice, so no two videos in a row look alike. Each video gets its own mix."""
    rng = random.Random(seed)
    out = {}
    for key, _, options, _ in SECTIONS:
        if key == "cut":      # only the gentler cuts are suggested (Frances found jump cuts "harsh"), unless theirs
            options = [o for o in options if o in GENTLE_CUTS or o == usual.get(key)]
        weighted = [o for o in options for _ in range(3 if o == usual.get(key) else 1)]
        fresh = [o for o in weighted if o != previous.get(key)] or weighted
        out[key] = rng.choice(fresh)
    return out


def caption_design(key, fonts, caption_font, args=None):
    design = dict(captions.DESIGNS[key])
    if caption_font:
        design["font"] = packs.CAPTION_FONTS[caption_font]["font"]
    elif not design.get("signature"):
        design["font"] = fonts["caption"]
    if args is not None:        # their extras, exactly as finish.py draws them
        if args.plain_captions:
            design["plain"] = True
        if args.caption_scale != 1.0:
            design["size"] = round(design["size"] * args.caption_scale)
        if args.palette:
            design["colour"] = args.palette["light"]
    return design


def picture(video, work, words, where, look, args, fonts, t, hook=False, notes=False):
    """A still of their video at t seconds, finished in this look (only the parts asked for)."""
    frame = captions.still(video, t)
    captioner = captions.Captioner(words, caption_design(look["captions"], fonts, args.caption_font, args),
                                   look["position"], **where)
    below = look["position"] == "above" or args.popups_below
    if hook:
        frame = hooks.Hook(work, "hook.json", faces=where.get("looks"), pack=args.pack, accent=args.accent,
                           style="there", fonts=fonts, below=below, place=look["hook_place"],
                           captions=captioner, lines=args.hook_lines).draw_on(frame, t)
    if notes:
        frame = handwritten.Notes(work, words, "notes.json", faces=where.get("looks"),
                                  still=lambda s: captions.still(video, s), seed=os.path.basename(work),
                                  pack=args.pack, accent=args.accent, not_before=0.0, style=look["popup_style"],
                                  fonts=fonts, below=below, captions=captioner,
                                  size=args.popup_scale).draw_on(frame, t)
    frame = captioner.draw_on(frame, t)
    small = Image.fromarray(frame).resize((TILE, round(TILE * captions.H / captions.W)), Image.LANCZOS)
    return small


def moments(work, words, video, where, look, args, fonts):
    """When to take each kind of still: mid-sentence for the captions, a pop-up fully on screen, the hook."""
    hook_end = json.load(open(os.path.join(work, "hook.json"), encoding="utf-8")).get("seconds", 8)
    later = [w for w in words if w["start"] > hook_end + 0.5] or words
    mid = later[len(later) // 3]
    caption_t = mid["start"] + 0.25
    first = handwritten.Notes(work, words, "notes.json", faces=where.get("looks"),
                              still=lambda s: captions.still(video, s), seed=os.path.basename(work),
                              pack=args.pack, accent=args.accent, not_before=hook_end, style=look["popup_style"],
                              fonts=fonts).popups
    popup_t = (first[0]["start"] + min(2.0, (first[0]["end"] - first[0]["start"]) * 0.6)) if first else caption_t
    return {"captions": caption_t, "position": caption_t, "popup_style": popup_t, "hook_place": 1.5}


def build(args):
    work = os.path.abspath(args.work)
    video = os.path.join(work, "tidy.mp4")
    words = captions.load_words(work)
    where = captions.find_face(video)
    fonts = packs.own_pack(args.pack, args.headline, args.writing, args.caption_font)
    if args.palette:            # only their own colours (finish.py --palette)
        handwritten.use_palette(args.palette["light"], args.palette["accent"], args.palette["background"])
        args.accent = args.palette["accent"]
    usual = {"captions": args.captions, "position": args.position, "popup_style": args.popup_style,
             "hook": args.hook, "hook_place": args.hook_place, "cut": args.cut}
    suggested = our_pick(usual, last_picks(work), os.path.basename(work))
    json.dump({"video": os.path.basename(work), "picks": suggested, "ours": True},
              open(os.path.join(work, "picks.json"), "w", encoding="utf-8"), indent=1)

    out = os.path.join(work, "picks")
    os.makedirs(os.path.join(out, "stills"), exist_ok=True)
    when = moments(work, words, video, where, suggested, args, fonts)
    sections = []
    root = content_root(work)
    for key, heading, options, shown in SECTIONS:
        tiles = []
        for option, name in options.items():
            if shown == "still":
                look = dict(suggested, **{key: option})
                path = os.path.join(out, "stills", f"{key}-{option}.jpg")
                picture(video, work, words, where, look, args, fonts, when[key],
                        hook=(key == "hook_place"), notes=(key == "popup_style")).convert("RGB").save(path, quality=82)
                tiles.append({"key": option, "name": name, "img": f"stills/{key}-{option}.jpg"})
            else:
                sample = os.path.join(root or "", "lookbook", "clips", SAMPLE_NAMES[key].format(option))
                rel = os.path.relpath(sample, out).replace(os.sep, "/") if root else ""
                tiles.append({"key": option, "name": name, "video": rel + ".mp4", "poster": rel + ".jpg"})
        sections.append({"key": key, "heading": heading, "tiles": tiles,
                         "note": "These move, so they're shown on Frances's sample video." if shown == "sample" else ""})
        print(f"Pictures made: {heading}")

    page = {"video": os.path.basename(work), "picks": suggested, "sections": sections}
    with open(os.path.join(out, "index.html"), "w", encoding="utf-8") as f:
        f.write(brand_style.apply(PAGE.replace("@@DATA@@", json.dumps(page, ensure_ascii=False).replace("</", "<\\/"))
                .replace("@@NAME@@", html.escape(args.name or "this talking head"))))
    print(os.path.join(out, "index.html"))


PAGE = """<!doctype html>
<html lang="en-GB">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Talking Head Picks</title>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600;700&family=DM+Sans:wght@400;500;700&display=swap" rel="stylesheet">
<style>
  :root { --ink: #2D2E30; --quiet: #6B6A68; --line: #E4DED7; --page: #FAF8F5; --card: #FFFFFF; --nude: #E0D8D0; }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--page); color: var(--ink); font: 15px/1.5 'DM Sans', system-ui, sans-serif; }
  .wrap { max-width: 1100px; margin: 0 auto; padding: 28px 16px 160px; }
  h1 { font: 700 30px/1.15 'Playfair Display', serif; margin: 0 0 6px; text-wrap: balance; }
  .intro { color: var(--quiet); max-width: 62ch; margin: 0 0 26px; }
  section { margin: 0 0 30px; }
  h2 { font: 700 20px/1.2 'Playfair Display', serif; margin: 0 0 4px; }
  .note { color: var(--quiet); font-size: 13px; margin: 0 0 10px; }
  .tiles { display: flex; gap: 12px; overflow-x: auto; padding: 4px 2px 10px; }
  .tile { flex: 0 0 auto; width: 170px; border: 2px solid transparent; border-radius: 14px; background: var(--card);
          padding: 6px; cursor: pointer; text-align: left; font: inherit; color: inherit; position: relative; }
  .tile img, .tile video { width: 100%; aspect-ratio: 9 / 16; object-fit: cover; border-radius: 10px; display: block; background: #ddd; }
  .tile span { display: block; font-weight: 700; font-size: 13px; margin: 6px 2px 2px; }
  .tile[aria-pressed="true"] { border-color: var(--ink); }
  .tile[aria-pressed="true"] span::before { content: '✓ '; }
  .ours { position: absolute; top: 12px; left: 12px; background: var(--card); font: 700 11px/1 'DM Sans', sans-serif;
          padding: 5px 8px; border-radius: 999px; box-shadow: 0 1px 4px rgba(0,0,0,.15); }
  .bar { position: fixed; left: 0; right: 0; bottom: 0; background: var(--card); border-top: 1px solid var(--line);
         padding: 12px 16px calc(12px + env(safe-area-inset-bottom, 0px)); }
  .bar-in { max-width: 1100px; margin: 0 auto; display: flex; flex-wrap: wrap; gap: 10px 16px; align-items: center; }
  .bar p { margin: 0; flex: 1 1 320px; min-width: 0; font-size: 14px; }
  .btn { border: 0; border-radius: 999px; padding: 11px 18px; font: 700 14px 'DM Sans', sans-serif; cursor: pointer;
         background: var(--ink); color: #fff; }
  .btn.quiet { background: var(--nude); color: var(--ink); }
  .said { flex-basis: 100%; color: var(--quiet); font-size: 13px; margin: 0; }
</style>
</head>
<body>
<div class="wrap">
  <h1>Pick the look for @@NAME@@</h1>
  <p class="intro">Every talking head can look different. Your fonts and colours stay the same, so it still looks
  like you. Everything else is up to you for this video. We've ticked a good mix already: if you like it,
  just press Save my picks.</p>
  <div id="sections"></div>
</div>
<div class="bar"><div class="bar-in">
  <p id="summary"></p>
  <button id="save" class="btn" type="button">Save my picks</button>
  <button id="copy" class="btn quiet" type="button">Copy my picks</button>
  <p id="said" class="said">Then tell Claude: I've saved my picks</p>
</div></div>
<script type="application/json" id="data">@@DATA@@</script>
<script>
const data = JSON.parse(document.getElementById('data').textContent);
const ours = Object.assign({}, data.picks);
const STORE = 'th-picks-' + data.video;
let picks = Object.assign({}, data.picks);
try { Object.assign(picks, JSON.parse(localStorage.getItem(STORE) || '{}')); } catch (e) {}
const holder = document.getElementById('sections');
for (const s of data.sections) {
  const sec = document.createElement('section');
  sec.innerHTML = '<h2></h2><p class="note"></p><div class="tiles"></div>';
  sec.querySelector('h2').textContent = s.heading;
  sec.querySelector('.note').textContent = s.note;
  const row = sec.querySelector('.tiles');
  for (const t of s.tiles) {
    const b = document.createElement('button');
    b.type = 'button'; b.className = 'tile'; b.dataset.section = s.key; b.dataset.key = t.key;
    if (t.img) { const i = document.createElement('img'); i.src = t.img; i.alt = ''; i.loading = 'lazy'; b.appendChild(i); }
    else {
      const v = document.createElement('video'); v.src = t.video; v.poster = t.poster; v.muted = true; v.loop = true;
      v.playsInline = true; v.preload = 'none'; b.appendChild(v);
      b.addEventListener('mouseenter', () => v.play().catch(() => {}));
      b.addEventListener('mouseleave', () => v.pause());
    }
    const n = document.createElement('span'); n.textContent = t.name; b.appendChild(n);
    if (ours[s.key] === t.key) { const o = document.createElement('i'); o.className = 'ours'; o.textContent = 'Our pick'; b.appendChild(o); }
    b.addEventListener('click', () => {
      picks[s.key] = t.key;
      const v = b.querySelector('video'); if (v) v.play().catch(() => {});
      try { localStorage.setItem(STORE, JSON.stringify(picks)); } catch (e) {}
      paint();
    });
    row.appendChild(b);
  }
  holder.appendChild(sec);
}
function nameOf(section, key) {
  const s = data.sections.find(x => x.key === section); const t = s && s.tiles.find(x => x.key === key);
  return t ? t.name : key;
}
const LABELS = {captions: 'captions', position: 'captions sit', popup_style: 'pop-ups', hook: 'hook', hook_place: 'hook sits', cut: 'cuts'};
function words() {
  return data.sections.map(s => LABELS[s.key] + ' ' + nameOf(s.key, picks[s.key])).join(' · ');
}
function paint() {
  for (const b of document.querySelectorAll('.tile')) b.setAttribute('aria-pressed', picks[b.dataset.section] === b.dataset.key);
  document.getElementById('summary').textContent = 'This video: ' + words();
}
document.getElementById('save').addEventListener('click', () => {
  const file = {what: 'my talking head picks', video: data.video, saved: new Date().toISOString(), picks, in_words: words()};
  try {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([JSON.stringify(file, null, 1)], {type: 'application/json'}));
    a.download = 'my-talking-head-picks.json'; document.body.appendChild(a); a.click(); a.remove();
    document.getElementById('said').textContent = "Saved. Now tell Claude: I've saved my picks";
  } catch (e) { document.getElementById('said').textContent = "That didn't save. Tap Copy my picks and paste them to Claude instead."; }
});
document.getElementById('copy').addEventListener('click', async () => {
  const text = 'My talking head picks for ' + data.video + ': ' + words();
  try { await navigator.clipboard.writeText(text); document.getElementById('said').textContent = 'Copied. Paste it to Claude.'; }
  catch (e) { document.getElementById('said').textContent = text; }
});
paint();
</script>
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("work", help="the talking head's work folder (after the cut, with hook.json and notes.json)")
    ap.add_argument("--name", help="what to call the video on the page, e.g. \"Monday 19th's talking head\"")
    ap.add_argument("--pack", choices=list(packs.PACKS), default=packs.DEFAULT)
    ap.add_argument("--accent", help="their brand colour for the pop-ups and hook")
    ap.add_argument("--headline", choices=list(packs.HEADLINES))
    ap.add_argument("--writing", choices=list(packs.POPUP_WRITING))
    ap.add_argument("--caption-font", dest="caption_font", choices=list(packs.CAPTION_FONTS))
    ap.add_argument("--captions", choices=list(captions.DESIGNS), default="pop")
    ap.add_argument("--position", choices=list(captions.POSITIONS), default="chin")
    ap.add_argument("--popup-style", dest="popup_style", choices=list(handwritten.POPUP_STYLES),
                    default=handwritten.DEFAULT_POPUP_STYLE)
    ap.add_argument("--hook", choices=list(hooks.STYLES), default=hooks.DEFAULT_STYLE)
    ap.add_argument("--hook-place", dest="hook_place", choices=list(hooks.PLACES), default=hooks.DEFAULT_PLACE)
    ap.add_argument("--cut", choices=list(talking_head.CUT_STYLES), default="glide")
    # Their extras ("Extras" in their talking head look), the same as finish.py's.
    ap.add_argument("--palette", help='only these colours: "light=#DDDDD8,accent=#AAAAAA,background=#2D2E30"')
    ap.add_argument("--plain-captions", dest="plain_captions", action="store_true")
    ap.add_argument("--caption-scale", dest="caption_scale", type=float, default=1.0)
    ap.add_argument("--popups-below", dest="popups_below", action="store_true")
    ap.add_argument("--popup-scale", dest="popup_scale", type=float, default=1.0)
    ap.add_argument("--hook-lines", dest="hook_lines", type=int)
    args = ap.parse_args()
    args.palette = dict(part.split("=") for part in args.palette.replace(" ", "").split(",")) if args.palette else None
    build(args)


if __name__ == "__main__":
    main()
