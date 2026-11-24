"""
Your reels this month, picked one at a time (Frances, 2026-10-13: "we don't want every single reel to look
the same... on this date I've picked this video, where do you want your text, and then go through the
lookbook").

Once Claude has matched each text-on-video reel to one of their clips (reels.json), this makes a page that
goes through the reels one by one: the day, the video picked for it, then where the words go, the
background and how the call to action appears. Every picture is their own clip with their own words, in
their colours, and changes as they tap. A good mix is ticked already (the engine's own pick), so they can
just press Next. At the end, Save my picks (my-reel-picks.json in their Downloads) or Copy my picks, and
Claude writes each reel's picks into reels.json as its own "look".

    .venv/bin/python engine/reel_picks.py "My Content/2026-10"

Saves My Content/<YYYY-MM>/reel-picks/index.html and its pictures. The font stays the same on every reel
(their usual reel look), so their feed still looks like them. One-by-one (list) reels and reels with a
style of their own aren't on the page.
"""

import tools  # noqa: F401  (first: emoji-safe output on Windows)
import brand_style  # the engine's masterclass look on every page
import argparse
import datetime
import html
import json
import os
import re
import sys
from dataclasses import replace

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import make_reels  # noqa: E402
import reel_looks  # noqa: E402
import text_reel  # noqa: E402
from make_lookbook import STYLE  # noqa: E402  (the lookbooks' page design)
from sdr import normal_colour  # noqa: E402

PLACES = ["top", "middle", "lower"]
BACKGROUNDS = ["bare", "plain", "outline", "strips"]
CTA_LOOK = {"box": "popup-box", "plain": "popup-words"}     # how a call to action can look in a picture
PICTURE_WIDTH = 450
SHORT = {"bare": "Just the words", "plain": "Soft shadow", "outline": "With an outline", "strips": "On a background"}


def clip_notes(folder):
    """What each clip shows, from clips/clips.md (written by make-my-reels)."""
    notes = {}
    path = os.path.join(folder, "clips", "clips.md")
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) >= 3 and re.search(r"\.(mov|mp4|m4v)$", cells[0], re.I):
                notes[cells[0]] = cells[-1]
    return notes


def day_name(date):
    d = datetime.date.fromisoformat(date)
    return f"{d.strftime('%A')} {d.day} {d.strftime('%B')}"


def save_picture(picture, path):
    small = picture.convert("RGB")
    small = small.resize((PICTURE_WIDTH, round(PICTURE_WIDTH * small.height / small.width)), text_reel.Image.LANCZOS)
    small.save(path, quality=80)


def make_pictures(folder, out):
    """Every picture for the page, and what the page needs to know."""
    with open(os.path.join(folder, "reels.json"), encoding="utf-8") as f:
        plan = json.load(f)
    if not any(reel.get("look") for reel in plan["reels"]):
        plan.setdefault("style", {}).setdefault("look", {})       # an older month: start from the usual look
    style, picked, look = make_reels.month_look(plan)
    chosen = {}       # the engine's own pick for each reel (or the picks they've already made)
    make_reels.varied_looks(plan["reels"], look, style, make_reels.clinic_seed(folder), folder, picked, chosen)
    colours = style.get("my_colours") or [look.box_colour, look.box_text_colour]
    kit = {} if style.get("my_colours") else make_reels.kit_colours(style.get("kit"))
    notes = clip_notes(folder)
    seen = {}
    stills = os.path.join(out, "stills")
    os.makedirs(stills, exist_ok=True)

    reels = []
    for reel in plan["reels"]:
        if reel.get("lines") or reel.get("style") or reel["date"] not in chosen:
            continue
        date = reel["date"]
        texts = [reel["text"]] + ([reel["popup"]] if reel.get("popup") else [])
        clip = normal_colour(os.path.join(folder, reel["clip"]))
        start = reel.get("start", 0)
        # The picture comes from the same strong moment the reel will use (clip_moments.py).
        clip, start = text_reel.strong_footage(os.path.join(folder, reel["clip"]), clip, start, 9 if len(texts) > 1 else 7)
        at = start + min(3.0, max(0.1, text_reel.clip_length(clip) - start - 0.3))
        # Pictures from an earlier run are kept unless something about this reel has changed (another video,
        # new words, a new usual look).
        key = json.dumps([reel["clip"], start, texts, picked["font"], picked.get("colour"), colours, look.box_colour,
                          look.highlight])
        stamp = os.path.join(stills, f"{date}.txt")
        if not os.path.exists(stamp) or open(stamp, encoding="utf-8").read() != key:
            for old in os.listdir(stills):
                if old.startswith(date + "-"):
                    os.remove(os.path.join(stills, old))
            with open(stamp, "w", encoding="utf-8") as f:
                f.write(key)
        frame = text_reel.still_from(clip, at, look.grade)
        save_picture(frame, os.path.join(stills, f"{date}-video.jpg"))
        bright = []
        for place in PLACES:
            for words in BACKGROUNDS:
                for cta_look, cta in (CTA_LOOK.items() if reel.get("popup") else [("none", picked["cta"])]):
                    path = os.path.join(stills, f"{date}-{place}-{words}-{cta_look}.jpg")
                    own = {"position": place, "words": words, "cta": cta}
                    change, _ = make_reels.reel_changes(reel, own, look, picked, colours, kit, folder, seen)
                    if words == "plain" and change.get("outline") and place not in bright:
                        bright.append(place)        # a bright spot: no background gets the soft outline here
                    if os.path.exists(path):
                        continue
                    this = replace(look, **{k: v for k, v in change.items() if k not in ("reveal", "popup_after")})
                    save_picture(text_reel.finished_still(clip, at, texts, this, frame), path)
        suggested = dict(chosen[date])
        if suggested["position"] not in PLACES:
            suggested["position"] = "middle"
        reels.append({"date": date, "day": int(date[-2:]), "mon": f"{datetime.date.fromisoformat(date):%b}",
                      "label": day_name(date), "text": reel["text"],
                      "popup": reel.get("popup", ""), "shows": notes.get(os.path.basename(reel["clip"]), ""), "bright": bright,
                      "suggested": {k: suggested[k] for k in ("position", "words", "cta")}})
        print(f"Pictures made: {date}")

    font = picked["font"]
    font_name = reel_looks.FONTS[font]["name"] if font in reel_looks.FONTS else "your brand font"
    month = os.path.basename(os.path.normpath(folder))
    return {
        # "November", or "November and December" for a plan that runs on into the next month (days.py)
        "month": month, "month_name": " and ".join(dict.fromkeys(
            f"{datetime.date.fromisoformat(r['date']):%B}" for r in reels)) or
            datetime.date.fromisoformat(month + "-01").strftime("%B"),
        "font": font_name, "local": True, "reels": reels,
        "places": [{"key": k, "name": reel_looks.POSITIONS[k]["name"]} for k in PLACES],
        "backgrounds": [{"key": k, "name": SHORT[k], "full": reel_looks.WORDS[k]["name"]} for k in BACKGROUNDS],
        "ctas": [{"key": k, "name": c["name"], "about": c["about"],
                  "look": "box" if c["popup_style"] == "box" else "plain"} for k, c in reel_looks.CTA.items()],
    }


PAGE_STYLE = """
  .dots { display: flex; flex-wrap: wrap; gap: 6px; margin: 0 0 22px; }
  .dot { border: 1px solid var(--line); background: var(--card); color: var(--ink); border-radius: 999px; padding: 7px 12px; font: 600 12.5px/1 'DM Sans', sans-serif; cursor: pointer; }
  .dot[aria-current="step"] { background: var(--ink); color: var(--on-ink); border-color: var(--ink); }
  .dot:focus-visible, .chip:focus-visible, .save:focus-visible, .mini:focus-visible { outline: 2px solid var(--ink); outline-offset: 2px; }
  .reel { display: grid; grid-template-columns: minmax(0, 330px) minmax(0, 1fr); gap: 32px; align-items: start; }
  .reel[hidden], #done[hidden] { display: none; }
  .stage { position: sticky; top: calc(16px + env(safe-area-inset-top, 0px)); display: flex; flex-direction: column; gap: 10px; }
  .big { width: 100%; max-width: 100%; aspect-ratio: 9 / 16; object-fit: cover; border-radius: 14px; display: block; background: var(--grey); }
  .steps { display: flex; flex-direction: column; gap: 22px; min-width: 0; }
  .count { font-size: 12px; letter-spacing: .12em; text-transform: uppercase; color: var(--quiet); margin: 0 0 4px; }
  .steps h2 { font-size: 28px; }
  .video-pick { display: flex; gap: 14px; align-items: center; background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 10px 14px 10px 10px; }
  .video-pick img { width: 54px; aspect-ratio: 9 / 16; object-fit: cover; border-radius: 6px; flex: none; }
  .video-pick p { margin: 0; font-size: 14px; min-width: 0; }
  .question h3 { font: 700 18px/1.3 'Playfair Display', serif; margin: 0 0 12px; display: flex; gap: 10px; align-items: center; }
  .n { flex: none; width: 26px; height: 26px; border-radius: 50%; background: var(--nude); display: grid; place-items: center; font: 700 12.5px/1 'DM Sans', sans-serif; }
  .options { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; max-width: 500px; }
  .option { all: unset; cursor: pointer; display: flex; flex-direction: column; gap: 7px; position: relative; min-width: 0; }
  .option img { width: 100%; max-width: 100%; aspect-ratio: 9 / 16; object-fit: cover; border-radius: 10px; border: 3px solid transparent; display: block; background: var(--grey); }
  .option[aria-pressed="true"] img { border-color: var(--ink); }
  .option:focus-visible img { outline: 2px solid var(--ink); outline-offset: 2px; }
  .option .label { font-weight: 600; font-size: 13.5px; line-height: 1.3; }
  .option[aria-pressed="true"] .label::before { content: "✓ "; }
  .ours { position: absolute; top: 9px; left: 9px; background: var(--card); color: var(--ink); font: 700 11px/1 'DM Sans', sans-serif; padding: 5px 8px; border-radius: 999px; }
  .chips { display: flex; flex-wrap: wrap; gap: 8px; }
  .chip { border: 1px solid var(--line); background: var(--card); color: var(--ink); border-radius: 999px; padding: 10px 15px; font: 600 14px/1 'DM Sans', sans-serif; cursor: pointer; }
  .chip[aria-pressed="true"] { background: var(--ink); color: var(--on-ink); border-color: var(--ink); }
  .about { color: var(--quiet); font-size: 14px; margin: 10px 0 0; }
  .nav { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
  .skip { all: unset; cursor: pointer; color: var(--quiet); font-size: 14px; text-decoration: underline; text-underline-offset: 3px; margin-left: 6px; }
  .skip:focus-visible { outline: 2px solid var(--ink); outline-offset: 2px; }
  .all { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 18px; margin-top: 16px; }
  .mini { all: unset; cursor: pointer; display: flex; flex-direction: column; gap: 6px; min-width: 0; }
  .mini img { width: 100%; max-width: 100%; aspect-ratio: 9 / 16; object-fit: cover; border-radius: 10px; display: block; background: var(--grey); }
  .mini strong { font-size: 14px; }
  .mini span { color: var(--quiet); font-size: 12.5px; line-height: 1.35; }
  @media (max-width: 760px) {
    .reel { grid-template-columns: 1fr; gap: 20px; }
    .stage { position: static; max-width: 250px; width: 100%; margin: 0 auto; }
    .options { gap: 8px; }
    .steps h2 { font-size: 24px; }
  }
"""

PAGE_SCRIPT = """
const data = JSON.parse(document.getElementById('reels-data').textContent);
const STORE = 'reel-picks-' + data.month;
const KEYS = {position: data.places, words: data.backgrounds, cta: data.ctas};
const picks = {};
for (const r of data.reels) picks[r.date] = Object.assign({}, r.suggested);
try {
  const saved = JSON.parse(localStorage.getItem(STORE) || '{}');
  for (const r of data.reels) for (const k in KEYS)
    if (saved[r.date] && KEYS[k].some(o => o.key === saved[r.date][k])) picks[r.date][k] = saved[r.date][k];
} catch (e) {}
function remember() { try { localStorage.setItem(STORE, JSON.stringify(picks)); } catch (e) {} }

const $ = id => document.getElementById(id);
let at = 0;     // which reel is showing (data.reels.length = the end)

function nameOf(k, key) { return KEYS[k].find(o => o.key === key).name; }
function ctaLook(r, cta) { return r.popup ? KEYS.cta.find(o => o.key === cta).look : 'none'; }
function picture(r, p) { return 'stills/' + r.date + '-' + p.position + '-' + p.words + '-' + ctaLook(r, p.cta) + '.jpg'; }
function inWords(r) {
  const p = picks[r.date];
  return r.label + ': ' + nameOf('position', p.position) + ' · ' + KEYS.words.find(o => o.key === p.words).full
    + (r.popup ? ' · call to action ' + nameOf('cta', p.cta).toLowerCase() : '');
}

function optionButton(r, k, option) {
  const b = document.createElement('button');
  b.type = 'button'; b.className = 'option';
  b.innerHTML = '<img alt=""><span class="label"></span>';
  b.querySelector('.label').textContent = option.name;
  if (r.suggested[k] === option.key) {
    const ours = document.createElement('span'); ours.className = 'ours'; ours.textContent = 'Our pick'; b.appendChild(ours);
  }
  b.addEventListener('click', () => { picks[r.date][k] = option.key; remember(); paint(); });
  b.dataset.key = option.key;
  return b;
}

function show(n) {
  at = Math.max(0, Math.min(n, data.reels.length));
  const done = at === data.reels.length;
  $('reel').hidden = done; $('done').hidden = !done;
  if (!done) {
    const r = data.reels[at];
    $('count').textContent = 'Reel ' + (at + 1) + ' of ' + data.reels.length;
    $('date').textContent = r.label;
    $('video').src = 'stills/' + r.date + '-video.jpg';
    $('shows').textContent = r.shows || 'your clip for this reel';
    $('change').textContent = 'Want a different video? Just tell Claude, for example "use a different video for the '
      + r.day + ordinal(r.day) + '".';
    for (const k of ['position', 'words']) {
      const box = $(k === 'position' ? 'places' : 'backgrounds');
      box.replaceChildren(...KEYS[k].map(o => optionButton(r, k, o)));
    }
    $('cta-q').hidden = !r.popup;
    $('ctas').replaceChildren(...KEYS.cta.map(o => {
      const b = document.createElement('button');
      b.type = 'button'; b.className = 'chip'; b.textContent = o.name; b.dataset.key = o.key;
      b.addEventListener('click', () => { picks[r.date].cta = o.key; remember(); paint(); });
      return b;
    }));
    $('back').hidden = at === 0;
    $('next').textContent = at === data.reels.length - 1 ? 'See all my reels' : 'Next reel';
    // Every picture for this reel, loaded now so tapping is instant.
    for (const place of KEYS.position) for (const w of KEYS.words) for (const c of ['popup-box', 'popup-words'])
      new Image().src = picture(r, {position: place.key, words: w.key, cta: c});
  } else {
    $('all').replaceChildren(...data.reels.map((r, i) => {
      const b = document.createElement('button');
      b.type = 'button'; b.className = 'mini';
      b.innerHTML = '<img alt=""><strong></strong><span></span>';
      b.querySelector('img').src = picture(r, picks[r.date]);
      b.querySelector('img').alt = 'Your reel for ' + r.label;
      b.querySelector('strong').textContent = r.label;
      b.querySelector('span').textContent = inWords(r).split(': ')[1] + ' · tap to change';
      b.addEventListener('click', () => show(i));
      return b;
    }));
  }
  for (const d of $('dots').children) {
    if (Number(d.dataset.n) === at) d.setAttribute('aria-current', 'step'); else d.removeAttribute('aria-current');
  }
  paint();
  window.scrollTo({top: 0, behavior: 'smooth'});
}

function ordinal(n) { return (n % 10 === 1 && n !== 11) ? 'st' : (n % 10 === 2 && n !== 12) ? 'nd' : (n % 10 === 3 && n !== 13) ? 'rd' : 'th'; }

function paint() {
  if (at < data.reels.length) {
    const r = data.reels[at], p = picks[r.date];
    $('big').src = picture(r, p);
    $('big').alt = 'How your reel for ' + r.label + ' will look: ' + r.text + (r.popup ? ' ' + r.popup : '');
    for (const [k, id] of [['position', 'places'], ['words', 'backgrounds']]) {
      for (const b of $(id).children) {
        b.querySelector('img').src = picture(r, Object.assign({}, p, {[k]: b.dataset.key}));
        b.setAttribute('aria-pressed', p[k] === b.dataset.key);
      }
    }
    for (const b of $('ctas').children) b.setAttribute('aria-pressed', p.cta === b.dataset.key);
    $('bright-note').hidden = !r.bright.includes(p.position);
    $('cta-about').textContent = KEYS.cta.find(o => o.key === p.cta).about;
  }
  $('bar-summary').textContent = data.reels.length + ' reels, each with its own look';
}

data.reels.forEach((r, i) => {
  const d = document.createElement('button');
  d.type = 'button'; d.className = 'dot'; d.dataset.n = i; d.textContent = r.day + ' ' + r.mon;
  d.addEventListener('click', () => show(i));
  $('dots').appendChild(d);
});
const end = document.createElement('button');
end.type = 'button'; end.className = 'dot'; end.dataset.n = data.reels.length; end.textContent = 'All done ✓';
end.addEventListener('click', () => show(data.reels.length));
$('dots').appendChild(end);

$('next').addEventListener('click', () => show(at + 1));
$('back').addEventListener('click', () => show(at - 1));
$('skip').addEventListener('click', () => show(data.reels.length));

function picksInWords() {
  return 'My reel picks for ' + data.month_name + ':\\n' + data.reels.map(inWords).join('\\n');
}
const saveButton = $('save');
saveButton.hidden = !data.local;
saveButton.addEventListener('click', () => {
  const chosen = {};
  for (const r of data.reels) chosen[r.date] = picks[r.date];
  const file = {what: 'my reel picks', month: data.month, saved: new Date().toISOString(), reels: chosen,
                in_words: picksInWords()};
  try {
    const blob = new Blob([JSON.stringify(file, null, 1)], {type: 'application/json'});
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob); a.download = 'my-reel-picks.json';
    document.body.appendChild(a); a.click(); a.remove();
    $('saved-note').textContent = "Saved. Now go back to Claude and say: I've saved my picks";
  } catch (e) {
    $('saved-note').textContent = "That didn't save. Tap Copy my picks and paste them to Claude instead.";
  }
});
$('copy-picks').addEventListener('click', async () => {
  const words = picksInWords();
  try {
    await navigator.clipboard.writeText(words);
    $('saved-note').textContent = 'Copied. Paste it to Claude and your reels get made.';
  } catch (e) {
    $('saved-note').textContent = words;
  }
});

// The planner links to a reel by its date (#day-2026-12-01); older links by its day number (#day-1).
const fromLink = /^#day-([\\d-]+)$/.exec(location.hash);
const linked = fromLink ? data.reels.findIndex(r => r.date === fromLink[1] || r.day === Number(fromLink[1])) : -1;
show(linked >= 0 ? linked : 0);
"""


def build(folder):
    folder = os.path.abspath(folder)
    out = os.path.join(folder, "reel-picks")
    data = make_pictures(folder, out)
    if not data["reels"]:
        raise SystemExit("There are no text-on-video reels in this month's reels.json to pick looks for.")
    month = html.escape(data["month_name"])
    font = html.escape(data["font"])
    page = f"""<!doctype html>
<html lang="en-GB">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Your {month} Reels</title>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600;700&family=DM+Sans:wght@400;500;700&display=swap" rel="stylesheet">
<style>{STYLE}{PAGE_STYLE}</style>
</head>
<body>
<main class="wrap">
  <p class="eyebrow">Clinic Content Engine</p>
  <h1>Your {month} reels</h1>
  <p class="intro">Let's make each reel yours, one at a time. For each one I've picked the video that fits its words best. Tap where you want your words and how they look: the big picture changes as you tap. I've ticked a good one for each already, so if you like it, just press Next.</p>
  <nav id="dots" class="dots" aria-label="Your reels"></nav>

  <section id="reel" class="reel" aria-live="polite">
    <div class="stage">
      <img id="big" class="big" alt="">
      <p class="small">Your font stays the same on every reel ({font}), so your feed always looks like you.</p>
    </div>
    <div class="steps">
      <div>
        <p id="count" class="count"></p>
        <h2 id="date"></h2>
      </div>
      <div class="video-pick">
        <img id="video" alt="">
        <p><strong>The video I picked:</strong> <span id="shows"></span><br><span id="change" class="small"></span></p>
      </div>
      <div class="question">
        <h3><span class="n">1</span> Where do you want your words?</h3>
        <div id="places" class="options"></div>
      </div>
      <div class="question">
        <h3><span class="n">2</span> Your background</h3>
        <div id="backgrounds" class="options"></div>
        <p id="bright-note" class="about" hidden>Your words would be hard to read in this spot, so with a soft shadow they get a thin outline too. It keeps them easy to read.</p>
      </div>
      <div id="cta-q" class="question">
        <h3><span class="n">3</span> Your call to action</h3>
        <div id="ctas" class="chips" role="group" aria-label="How your call to action appears"></div>
        <p id="cta-about" class="about"></p>
      </div>
      <div class="nav">
        <button id="back" class="save quiet" type="button">Back</button>
        <button id="next" class="save" type="button">Next reel</button>
        <button id="skip" class="skip" type="button">Happy with the rest? Skip to the end</button>
      </div>
    </div>
  </section>

  <section id="done" hidden>
    <h2>All your {month} reels</h2>
    <p class="lead">Here's how each one will look. Tap one to change it. Happy? Press Save my picks below, then go back to Claude and say "I've saved my picks".</p>
    <div id="all" class="all"></div>
  </section>
</main>
<div class="bar"><div class="bar-in">
  <p class="bar-text"><strong>Your reels:</strong> <span id="bar-summary"></span></p>
  <div class="bar-buttons">
    <button id="save" class="save" type="button">Save my picks</button>
    <button id="copy-picks" class="save quiet" type="button">Copy my picks</button>
  </div>
  <p id="saved-note" class="saved-note">Go through your reels, or skip to the end, then save.</p>
</div></div>
<script type="application/json" id="reels-data">{json.dumps(data, ensure_ascii=False).replace("</", "<\\/")}</script>
<script>{PAGE_SCRIPT}</script>
</body>
</html>
"""
    path = os.path.join(out, "index.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(brand_style.apply(page))
    print(path)
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Make the page where they pick each reel's look.")
    parser.add_argument("month", help='the month\'s folder, e.g. "My Content/2026-10"')
    build(parser.parse_args().month)
