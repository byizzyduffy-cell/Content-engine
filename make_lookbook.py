"""
Makes the talking head lookbook: every look the talking-head editor can give a
video (caption designs, cut styles, and more as they're built), each with a
short sample video to watch, tabs and a search box. Like the post library, but
for talking heads.

    .venv/bin/python engine/make_lookbook.py

The names and descriptions come from the engine itself (DESIGNS in captions.py,
CUT_STYLES in talking_head.py), so a new design shows up here as soon as it's
added there. The samples are made from one tidy talking head (SAMPLE below):
any that are missing are made, then everything is saved in "My Content/lookbook/".
Delete a sample from "My Content/lookbook/clips/" to have it made again.
"""

import tools  # noqa: F401  (first: emoji-safe output on Windows)
import brand_style  # the engine's masterclass look on every page
import html
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import captions  # noqa: E402
import finish  # noqa: E402
import hook  # noqa: E402
import notes  # noqa: E402
import packs  # noqa: E402
import talking_head  # noqa: E402
import voiceover  # noqa: E402

OUT = os.path.join(PROJECT, "My Content", "lookbook")
# Frances's own raw talking head (straight from her phone), already listened to and cut.
SAMPLE = os.path.join(PROJECT, "My Content", "talking-heads-test", "1FF8")
# Frances's laser talking head (7 October) made into a voiceover over Skin Survival's October
# laser clips: the clips match what she's saying (see voiceover.py).
VOICE_SAMPLE = os.path.join(PROJECT, "My Content", "2026-10", "voiceovers", "one-treatment-laser")
CAPTION_SECONDS = 7.5   # caption samples: the first sentence and a little more
CUT_SECONDS = 10.5      # cut samples: long enough to include a glide and a clean cut
POPUP_SECONDS = 26      # brand pack samples: long enough to reach the special moment
HOOK_SECONDS = 8.5      # hook samples: the hook and a moment after
FONT_SECONDS = 4.5      # font samples: a few seconds is enough to see a font
CLIP_WIDTH = 540        # half size: sharp on a phone, quick to load

# Each tab (group) holds one or more sections of looks.
SECTIONS = [
    {"group": "Captions", "prefix": "captions", "choice": "captions", "default": "pop", "name": "Caption designs",
     "say": 'Use the "{name}" captions on my talking heads',
     "lead": "First, how your words appear on screen as you speak.", "looks": captions.DESIGNS},
    {"group": "Captions", "prefix": "captionfont", "choice": "caption_font", "default": None, "name": "Caption font",
     "say": 'Use the "{name}" caption font', "lead": "Then the font for your captions. Leave it unticked to use your brand pack's.",
     "looks": {k: dict(v, about="", good_for="") for k, v in packs.CAPTION_FONTS.items()}},
    {"group": "Captions", "prefix": "position", "choice": "position", "default": "chin", "name": "Caption position", "say": "",
     "lead": "Then where they sit. If you pick above your head, your hook, pop-up words and emojis move below "
             "your face, so nothing piles up at the top.",
     "looks": captions.POSITIONS},
    {"group": "Brand packs", "prefix": "brandpack", "choice": "pack", "default": "elegant", "name": "Brand packs",
     "say": 'Use the "{name}" brand pack on my talking heads',
     "lead": "Three fonts that go together: one for your hook, one for your pop-up words and one for your "
             "captions. They stay the same all the way through, in your own brand colour. Prefer to choose "
             "each one yourself? See Build your own.",
     "looks": packs.PACKS},
    {"group": "Build your own", "prefix": "popupstyle", "choice": "popup_style", "default": "notes", "name": "Pop-up style",
     "say": "", "lead": "Your main way for pop-up words to come up. It leads, and the others take turns in between, "
                        "so no two pop-ups in a row look the same. Works with any brand pack or your own fonts.",
     "looks": notes.POPUP_STYLES},
    {"group": "Build your own", "prefix": "headline", "choice": "headline", "default": None, "name": "Headline font",
     "say": 'Use the "{name}" headline font', "lead": "Optional. For your hook and the main pop-up lines. Leave it unticked to use your brand pack's.",
     "looks": {k: dict(v, about="", good_for="") for k, v in packs.HEADLINES.items()}},
    {"group": "Build your own", "prefix": "writing", "choice": "writing", "default": None, "name": "Pop-up font",
     "say": 'Use the "{name}" pop-up font', "lead": "Optional. For the handwritten (or typed) pop-up lines. Leave it unticked to use your brand pack's.",
     "looks": {k: dict(v, about="", good_for="") for k, v in packs.POPUP_WRITING.items()}},
    {"group": "Hooks", "prefix": "hook", "choice": "hook", "default": "there", "name": "Hooks",
     "say": "", "lead": "How your hook arrives. It stays on screen for the first 7 to 10 seconds.",
     "looks": hook.STYLES},
    {"group": "Hooks", "prefix": "hookplace", "choice": "hook_place", "default": hook.DEFAULT_PLACE,
     "name": "Hook position", "say": "",
     "lead": "Then where your hook sits. It never covers your face or your captions: if the spot you pick is "
             "taken, it moves to the nearest clear space. On most talking heads, the middle and lower down only "
             "have room when your captions are above your head.",
     "looks": hook.PLACES},
    {"group": "Voiceovers", "prefix": "voposition", "choice": "vo_position", "default": "middle",
     "name": "Voiceover caption position", "say": "",
     "lead": "Your voice over your clips, with captions: that's all a voiceover needs (no hook, pop-ups or "
             "emojis). Your captions use the same design and font as your talking heads; with no face, they "
             "can go in the middle.",
     "looks": captions.VOICEOVER_POSITIONS},
    {"group": "Cuts and zooms", "prefix": "cut", "choice": "cut", "default": "glide", "name": "Cuts and zooms",
     "say": 'Use the "{name}" cut on my talking heads',
     "lead": "How the edit joins your takes together, and whether the camera moves.",
     "looks": talking_head.CUT_STYLES},
]
PICKED_FOR_YOU = ("Stickers and sound effects are picked for you in every video, to match what you're "
                  "saying, so you never have to choose them.")

STYLE = """
  :root { --ink: #2D2E30; --quiet: #6B6A68; --line: #E4DED7; --page: #FAF8F5; --card: #FFFFFF; --nude: #E0D8D0; --grey: #DDDDD8; --shade: rgba(45, 46, 48, .62); --on-ink: #FAF8F5; }
  @media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { --ink: #ECE7E1; --quiet: #A9A39C; --line: #3A3836; --page: #1D1C1B; --card: #262524; --nude: #4A423B; --grey: #33312F; --shade: rgba(0, 0, 0, .7); --on-ink: #1D1C1B; color-scheme: dark; } }
  :root[data-theme="dark"] { --ink: #ECE7E1; --quiet: #A9A39C; --line: #3A3836; --page: #1D1C1B; --card: #262524; --nude: #4A423B; --grey: #33312F; --shade: rgba(0, 0, 0, .7); --on-ink: #1D1C1B; color-scheme: dark; }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--page); color: var(--ink); font: 15px/1.5 'DM Sans', system-ui, sans-serif; }
  .wrap { max-width: 1180px; margin: 0 auto; padding-inline: 16px; padding-block: 32px 56px; }
  .eyebrow { font-size: 12px; letter-spacing: .12em; text-transform: uppercase; color: var(--quiet); margin: 0 0 6px; }
  h1 { font: 700 34px/1.12 'Playfair Display', serif; margin: 0; text-wrap: balance; }
  .intro { color: var(--quiet); margin: 8px 0 22px; max-width: 640px; }
  .tools { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; margin-bottom: 22px; }
  .search { flex: 1 1 260px; max-width: 380px; padding: 11px 14px; border: 1px solid var(--line); border-radius: 999px; font: inherit; background: var(--card); color: var(--ink); }
  .search:focus, .tab:focus-visible, .copy:focus-visible, .close:focus-visible { outline: 2px solid var(--ink); outline-offset: 2px; }
  .tabs { display: flex; flex-wrap: wrap; gap: 8px; }
  .tab { border: 1px solid var(--line); background: var(--card); color: var(--ink); border-radius: 999px; padding: 8px 14px; font: 600 13.5px/1 'DM Sans', sans-serif; cursor: pointer; }
  .tab[aria-pressed="true"] { background: var(--ink); color: var(--on-ink); border-color: var(--ink); }
  section { margin-top: 30px; }
  section[hidden] { display: none; }
  h2 { font: 700 22px/1.2 'Playfair Display', serif; margin: 0 0 4px; }
  .lead { color: var(--quiet); margin: 0 0 16px; font-size: 14px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 18px; }
  .card { background: var(--card); border: 1px solid var(--line); border-radius: 14px; overflow: hidden; cursor: pointer; text-align: left; padding: 0; font: inherit; color: inherit; display: flex; flex-direction: column; transition: transform .15s ease, box-shadow .15s ease; }
  .card[hidden] { display: none; }
  .card:hover, .card:focus-visible { transform: translateY(-3px); box-shadow: 0 10px 26px rgba(45, 46, 48, .12); outline: none; }
  .cover { aspect-ratio: 9 / 16; width: 100%; max-width: 100%; display: block; background: var(--grey) center / cover no-repeat; }
  .cover video { width: 100%; height: 100%; object-fit: cover; display: block; }
  .meta { padding: 12px 14px 14px; display: flex; flex-direction: column; gap: 5px; }
  .letter { align-self: flex-start; font-size: 11.5px; font-weight: 700; padding: 3px 9px; border-radius: 999px; background: var(--nude); }
  .name { font: 700 17px/1.25 'Playfair Display', serif; margin: 0; }
  .good { color: var(--quiet); font-size: 13px; margin: 0; }
  .empty { color: var(--quiet); padding: 30px 0; display: none; }
  .coming { margin-top: 34px; background: var(--grey); border-radius: 12px; padding: 16px 18px; font-size: 14px; }
  .coming strong { font-weight: 700; }
  dialog { border: none; border-radius: 18px; padding: 0; width: min(900px, calc(100% - 24px)); max-height: calc(100% - 24px); background: var(--card); color: var(--ink); }
  dialog::backdrop { background: var(--shade); }
  .pop { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.1fr); }
  .viewer { background: #1F2022; display: flex; align-items: center; justify-content: center; padding: 18px; position: relative; }
  .viewer video { width: 100%; max-width: 340px; aspect-ratio: 9 / 16; border-radius: 8px; background: #000; }
  .details { padding: 26px 26px 24px; display: flex; flex-direction: column; gap: 14px; overflow-y: auto; max-height: calc(100vh - 24px); }
  .details h2 { font-size: 26px; }
  .details h3 { font-size: 12px; text-transform: uppercase; letter-spacing: .07em; color: var(--quiet); margin: 0 0 3px; }
  .details p { margin: 0; }
  .say { background: var(--page); border: 1px solid var(--line); border-radius: 12px; padding: 14px; display: flex; flex-direction: column; gap: 10px; }
  .say q { font-weight: 700; }
  .copy { align-self: flex-start; border: none; border-radius: 999px; background: var(--ink); color: var(--on-ink); padding: 9px 16px; font: 600 13.5px/1 'DM Sans', sans-serif; cursor: pointer; }
  .close { position: absolute; top: 10px; right: 10px; width: 36px; height: 36px; border-radius: 50%; border: none; background: rgba(250, 248, 245, .92); color: #2D2E30; font-size: 20px; cursor: pointer; z-index: 2; }
  .small { color: var(--quiet); font-size: 13px; }
  .card { position: relative; cursor: default; }
  .open { all: unset; cursor: pointer; display: flex; flex-direction: column; }
  .open:focus-visible { outline: 2px solid var(--ink); outline-offset: -2px; border-radius: 14px; }
  .tick { position: absolute; top: 10px; right: 10px; width: 40px; height: 40px; border-radius: 50%; border: 2px solid #FFFFFF; background: rgba(45, 46, 48, .35); color: #FFFFFF; font: 700 20px/1 'DM Sans', sans-serif; cursor: pointer; display: grid; place-items: center; }
  .tick:focus-visible { outline: 3px solid var(--ink); outline-offset: 2px; }
  .card[data-picked="true"] { border: 3px solid var(--ink); }
  .card[data-picked="true"] .tick { background: var(--ink); border-color: var(--ink); color: var(--on-ink); }
  .pick { align-self: flex-start; border: none; border-radius: 999px; background: var(--ink); color: var(--on-ink); padding: 11px 20px; font: 700 15px/1 'DM Sans', sans-serif; cursor: pointer; }
  .bar { position: fixed; left: 0; right: 0; bottom: 0; background: var(--card); border-top: 1px solid var(--line); padding: 12px 16px calc(12px + env(safe-area-inset-bottom, 0px)); box-shadow: 0 -6px 20px rgba(45, 46, 48, .08); z-index: 5; }
  .bar-in { max-width: 1180px; margin: 0 auto; display: flex; flex-wrap: wrap; gap: 10px 16px; align-items: center; }
  .bar-text { flex: 1 1 320px; min-width: 0; font-size: 14px; }
  .bar-text strong { font-weight: 700; }
  .bar-buttons { display: flex; gap: 8px; flex-wrap: wrap; }
  .save { border: none; border-radius: 999px; background: var(--ink); color: var(--on-ink); padding: 11px 18px; font: 700 14px/1 'DM Sans', sans-serif; cursor: pointer; }
  .save.quiet { background: transparent; color: var(--ink); border: 1px solid var(--line); }
  .save[hidden] { display: none; }
  .saved-note { font-size: 13px; color: var(--quiet); width: 100%; }
  .wrap { padding-bottom: 150px; }
  @media (max-width: 760px) {
    .pop { grid-template-columns: 1fr; }
    .details { max-height: none; }
    .viewer video { max-width: 260px; }
    h1 { font-size: 28px; }
    .grid { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
    .meta { padding: 10px 12px 12px; }
    .name { font-size: 15px; }
  }
"""

SCRIPT = """
const data = JSON.parse(document.getElementById('lookbook').textContent);
const search = document.getElementById('search');
const empty = document.getElementById('empty');
const dialog = document.getElementById('pop');
const big = document.getElementById('p-video');
let tab = 'All';

// Sample videos play only while they're on screen, so the page stays light on phones.
const watcher = new IntersectionObserver(entries => {
  for (const e of entries) {
    if (e.isIntersecting) e.target.play().catch(() => {}); else e.target.pause();
  }
}, {threshold: 0.4});

// Ticks: one choice per section (the optional font sections can be left unticked).
const STORE = 'talking-head-look';
let picks = {};
for (const section of data.sections) picks[section.choice] = section.default;
try { Object.assign(picks, JSON.parse(localStorage.getItem(STORE) || '{}')); } catch (e) {}
let open = null;

function remember() { try { localStorage.setItem(STORE, JSON.stringify(picks)); } catch (e) {} }

function pick(section, look) {
  const optional = section.default === null;
  picks[section.choice] = (optional && picks[section.choice] === look.key) ? null : look.key;
  remember();
  paint();
}

function nameOf(choice, key) {
  const section = data.sections.find(s => s.choice === choice);
  const look = section && section.looks.find(l => l.key === key);
  return look ? look.name : null;
}

function summary() {
  const parts = ['brand pack ' + nameOf('pack', picks.pack)];
  if (picks.headline) parts.push('headline font ' + nameOf('headline', picks.headline));
  if (picks.writing) parts.push('pop-up font ' + nameOf('writing', picks.writing));
  if (picks.caption_font) parts.push('caption font ' + nameOf('caption_font', picks.caption_font));
  parts.push('pop-ups ' + nameOf('popup_style', picks.popup_style));
  parts.push('captions ' + nameOf('captions', picks.captions) + ', ' + nameOf('position', picks.position).toLowerCase());
  parts.push('hook ' + nameOf('hook', picks.hook) + ', ' + nameOf('hook_place', picks.hook_place).toLowerCase());
  parts.push('cuts ' + nameOf('cut', picks.cut));
  parts.push('voiceover captions ' + nameOf('vo_position', picks.vo_position).toLowerCase());
  return parts.join(' · ');
}

function paint() {
  for (const card of document.querySelectorAll('.card')) {
    const on = picks[card.dataset.choice] === card.dataset.key;
    card.dataset.picked = on;
    const tick = card.querySelector('.tick');
    tick.setAttribute('aria-pressed', on);
    tick.textContent = on ? '✓' : '';
  }
  document.getElementById('bar-summary').textContent = summary();
  if (open) {
    const on = picks[open.section.choice] === open.look.key;
    document.getElementById('p-pick').textContent = on ? (open.section.default === null ? 'Picked (tap to untick)' : 'Picked ✓') : 'Pick this';
  }
}

function show(section, look) {
  open = {section, look};
  document.getElementById('p-tag').textContent = section.group + ' · ' + section.name;
  document.getElementById('p-name').textContent = look.name;
  document.getElementById('p-about').textContent = look.about;
  document.getElementById('p-good').textContent = look.good_for;
  document.getElementById('p-say').textContent = look.say || section.say.replace('{name}', look.name);
  document.getElementById('copy').textContent = 'Copy';
  big.src = look.clip;
  big.muted = false;
  paint();
  dialog.showModal();
  big.play().catch(() => { big.muted = true; big.play().catch(() => {}); });
}

for (const section of data.sections) {
  const sec = document.createElement('section');
  sec.dataset.group = section.group;
  sec.innerHTML = '<h2></h2><p class="lead"></p><div class="grid"></div>';
  sec.querySelector('h2').textContent = section.name;
  sec.querySelector('.lead').textContent = section.lead;
  const grid = sec.querySelector('.grid');
  section.looks.forEach((look, n) => {
    const card = document.createElement('div');
    card.className = 'card';
    card.dataset.choice = section.choice; card.dataset.key = look.key;
    card.dataset.search = [look.name, look.about, look.good_for, section.name].join(' ').toLowerCase();
    card.innerHTML = '<button class="open" type="button"><div class="cover"><video muted loop playsinline preload="none"></video></div>' +
      '<div class="meta"><span class="letter"></span><p class="name"></p><p class="good"></p></div></button>' +
      '<button class="tick" type="button" aria-pressed="false"></button>';
    card.querySelector('.tick').setAttribute('aria-label', 'Pick ' + look.name);
    card.querySelector('.tick').addEventListener('click', () => pick(section, look));
    // The still sits behind the video, so the card is never blank while the video loads.
    card.querySelector('.cover').style.backgroundImage = 'url("' + look.poster + '")';
    const v = card.querySelector('video');
    v.muted = true; v.src = look.clip; v.poster = look.poster;
    card.querySelector('.letter').textContent = String.fromCharCode(65 + n);
    card.querySelector('.name').textContent = look.name;
    card.querySelector('.good').textContent = look.good_for;
    card.querySelector('.open').addEventListener('click', () => show(section, look));
    grid.appendChild(card);
    watcher.observe(v);
  });
  document.getElementById('sections').appendChild(sec);
}

function filter() {
  const words = search.value.toLowerCase().trim().split(/\\s+/).filter(Boolean);
  let shown = 0;
  for (const sec of document.querySelectorAll('section')) {
    let here = 0;
    for (const card of sec.querySelectorAll('.card')) {
      const ok = words.every(w => card.dataset.search.includes(w));
      card.hidden = !ok; here += ok;
    }
    sec.hidden = !here || (tab !== 'All' && sec.dataset.group !== tab);
    shown += sec.hidden ? 0 : here;
  }
  empty.style.display = shown ? 'none' : 'block';
}

const tabs = document.getElementById('tabs');
['All', ...new Set(data.sections.map(s => s.group))].forEach(name => {
  const b = document.createElement('button');
  b.className = 'tab'; b.type = 'button'; b.textContent = name;
  b.setAttribute('aria-pressed', name === tab);
  b.addEventListener('click', () => {
    tab = name;
    for (const t of tabs.children) t.setAttribute('aria-pressed', t === b);
    filter();
  });
  tabs.appendChild(b);
});

search.addEventListener('input', filter);
document.getElementById('close').addEventListener('click', () => dialog.close());
dialog.addEventListener('click', e => { if (e.target === dialog) dialog.close(); });
dialog.addEventListener('close', () => { big.pause(); });
document.getElementById('copy').addEventListener('click', async () => {
  const words = document.getElementById('p-say').textContent;
  try { await navigator.clipboard.writeText(words); document.getElementById('copy').textContent = 'Copied'; }
  catch (e) { document.getElementById('copy').textContent = 'Select the words above to copy them'; }
});
document.getElementById('p-pick').addEventListener('click', () => { if (open) pick(open.section, open.look); });

// Save my look: a small file in Downloads, which Claude finds when they say "make my talking heads".
const saveButton = document.getElementById('save');
saveButton.hidden = !data.local;
saveButton.addEventListener('click', () => {
  const look = Object.assign({what: 'my talking head look', saved: new Date().toISOString()}, picks,
                             {in_words: summary()});
  try {
    const blob = new Blob([JSON.stringify(look, null, 1)], {type: 'application/json'});
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob); a.download = 'my-talking-head-look.json';
    document.body.appendChild(a); a.click(); a.remove();
    document.getElementById('saved-note').textContent = 'Saved. Now tell Claude: make my talking heads';
  } catch (e) {
    document.getElementById('saved-note').textContent = "That didn't save. Tap Copy my choices and paste them to Claude instead.";
  }
});
document.getElementById('copy-look').addEventListener('click', async () => {
  const words = 'My talking head look: ' + summary();
  try {
    await navigator.clipboard.writeText(words);
    document.getElementById('saved-note').textContent = 'Copied. Paste it to Claude and say: make my talking heads';
  } catch (e) {
    document.getElementById('saved-note').textContent = words;
  }
});
paint();
filter();
"""


def run(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(f"This step didn't work:\n{' '.join(cmd)}\n\n{result.stderr[-1500:]}")


def small_clip(source, seconds, target):
    """A half-size copy of the start of a video, with its poster picture."""
    run(["ffmpeg", "-v", "error", "-y", "-i", source, "-t", f"{seconds}", "-vf", f"scale={CLIP_WIDTH}:-2",
         "-c:v", "libx264", "-preset", "slow", "-crf", "27", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", target])
    run(["ffmpeg", "-v", "error", "-y", "-ss", "1.6", "-i", target, "-frames:v", "1", "-q:v", "4",
         target.replace(".mp4", ".jpg")])


def make_samples():
    """Makes any sample that's missing: the tidy video in each cut style, then each
    caption design on the As filmed version."""
    with open(os.path.join(SAMPLE, "words.json"), encoding="utf-8") as f:
        source = json.load(f)["video"]
    clips = os.path.join(OUT, "clips")
    os.makedirs(clips, exist_ok=True)
    styles = os.path.join(SAMPLE, "styles")
    os.makedirs(styles, exist_ok=True)
    for key in talking_head.CUT_STYLES:
        target = os.path.join(clips, f"cut-{key}.mp4")
        if os.path.exists(target):
            continue
        full = os.path.join(styles, f"{key}.mp4")
        if not os.path.exists(full):
            talking_head.cut(source, SAMPLE, full, key)
        small_clip(full, CUT_SECONDS, target)
        print(f"Sample made: {talking_head.CUT_STYLES[key]['name']}")
    words = captions.load_words(SAMPLE)
    start = os.path.join(SAMPLE, "styles", "glide-start.mp4")
    # Each caption design under the chin, then the One word pop design in each position.
    wanted = [(f"captions-{key}", design, "chin", design["name"]) for key, design in captions.DESIGNS.items()]
    wanted += [(f"position-{key}", captions.DESIGNS["pop"], key, place["name"])
               for key, place in captions.POSITIONS.items()]
    for name, design, position, label in wanted:
        target = os.path.join(clips, f"{name}.mp4")
        if os.path.exists(target):
            continue
        if not os.path.exists(start):
            run(["ffmpeg", "-v", "error", "-y", "-i", os.path.join(styles, "glide.mp4"), "-t", f"{CAPTION_SECONDS}",
                 "-c:v", "libx264", "-crf", "14", "-pix_fmt", "yuv420p", "-c:a", "copy", start])
        full = os.path.join(SAMPLE, "styles", f"{name}.mp4")
        captions.make_video(start, words, design, full, position=position)
        small_clip(full, CAPTION_SECONDS, target)
        print(f"Sample made: {label}")
    # Each brand pack (hook, pop-ups and captions), on the first 26 seconds, in Frances's yellow.
    longer = os.path.join(SAMPLE, "styles", "glide-26.mp4")
    if not os.path.exists(longer):
        run(["ffmpeg", "-v", "error", "-y", "-i", os.path.join(styles, "glide.mp4"), "-t", f"{POPUP_SECONDS}",
             "-c:v", "libx264", "-crf", "14", "-pix_fmt", "yuv420p", "-c:a", "copy", longer])
    for key, pack in packs.PACKS.items():
        target = os.path.join(clips, f"brandpack-{key}.mp4")
        if os.path.exists(target):
            continue
        full = os.path.join(SAMPLE, "brand-packs", f"{key}.mp4")
        finish.make(longer, SAMPLE, full, "pop", "chin", "none", notes="notes.json", pack=key,
                    accent=notes.FRANCES_YELLOW, hook="hook.json", hook_style="there")
        small_clip(full, POPUP_SECONDS, target)
        print(f"Sample made: {pack['name']} brand pack")
    # Each pop-up style, on the first 26 seconds.
    for key, style in notes.POPUP_STYLES.items():
        target = os.path.join(clips, f"popupstyle-{key}.mp4")
        if os.path.exists(target):
            continue
        full = os.path.join(SAMPLE, "popup-styles", f"{key}.mp4")
        finish.make(longer, SAMPLE, full, "pop", "chin", "none", notes="notes.json", accent=notes.FRANCES_YELLOW,
                    popup_style=key)
        small_clip(full, POPUP_SECONDS, target)
        print(f"Sample made: {style['name']} pop-ups")
    # Each font on its own, on the first few seconds: headlines as the hook, pop-up fonts as a
    # pop-up (notes-sample.json), caption fonts as One word pop captions.
    short = os.path.join(SAMPLE, "styles", "glide-6.mp4")
    if not os.path.exists(short):
        run(["ffmpeg", "-v", "error", "-y", "-i", os.path.join(styles, "glide.mp4"), "-t", "6",
             "-c:v", "libx264", "-crf", "14", "-pix_fmt", "yuv420p", "-c:a", "copy", short])
    jobs = [(f"headline-{k}", dict(hook="hook.json", hook_style="there", headline=k), v["name"])
            for k, v in packs.HEADLINES.items()]
    jobs += [(f"writing-{k}", dict(notes="notes-sample.json", writing=k), v["name"])
             for k, v in packs.POPUP_WRITING.items()]
    jobs += [(f"captionfont-{k}", dict(caption_font=k), v["name"]) for k, v in packs.CAPTION_FONTS.items()]
    for name, choices, label in jobs:
        target = os.path.join(clips, f"{name}.mp4")
        if os.path.exists(target):
            continue
        full = os.path.join(SAMPLE, "fonts", f"{name}.mp4")
        finish.make(short, SAMPLE, full, "pop", "chin", "none", accent=notes.FRANCES_YELLOW, **choices)
        small_clip(full, FONT_SECONDS, target)
        print(f"Sample made: {label}")
    # Voiceovers: each caption position (captions only, clips as filmed).
    if os.path.exists(os.path.join(VOICE_SAMPLE, "shots.json")):
        for key, place in captions.VOICEOVER_POSITIONS.items():
            target = os.path.join(clips, f"voposition-{key}.mp4")
            if os.path.exists(target):
                continue
            tidy = os.path.join(VOICE_SAMPLE, "tidy-cuts.mp4")
            if not os.path.exists(tidy):
                voiceover.montage(VOICE_SAMPLE, tidy, "cuts")
            full = os.path.join(VOICE_SAMPLE, f"position-{key}.mp4")
            finish.make(tidy, VOICE_SAMPLE, full, "pop", key, "none", voiceover=True)
            small_clip(full, CAPTION_SECONDS, target)
            print(f"Sample made: voiceover captions {place['name'].lower()}")
    # Each hook style, on the first 8.5 seconds.
    for key, style in hook.STYLES.items():
        target = os.path.join(clips, f"hook-{key}.mp4")
        if os.path.exists(target):
            continue
        full = os.path.join(SAMPLE, "styles", f"hook-{key}.mp4")
        finish.make(longer, SAMPLE, full, "pop", "chin", "none", accent=notes.FRANCES_YELLOW,
                    hook="hook.json", hook_style=key)
        small_clip(full, HOOK_SECONDS, target)
        print(f"Sample made: {style['name']} hook")
    # Each hook position, on the first 8.5 seconds. Under the chin is the captions' spot, so the middle and
    # lower down samples have their captions above the head (where those two have room on this video).
    for key, spot in hook.PLACES.items():
        target = os.path.join(clips, f"hookplace-{key}.mp4")
        if os.path.exists(target):
            continue
        full = os.path.join(SAMPLE, "styles", f"hookplace-{key}.mp4")
        finish.make(longer, SAMPLE, full, "pop", "chin" if key == "top" else "above", "none",
                    accent=notes.FRANCES_YELLOW, hook="hook.json", hook_style="there", hook_place=key)
        small_clip(full, HOOK_SECONDS, target)
        print(f"Sample made: hook {spot['name'].lower()}")


def main():
    make_samples()
    sections = []
    for section in SECTIONS:
        prefix = section["prefix"]
        looks = [{"key": key, "name": look["name"], "good_for": look["good_for"], "say": look.get("say", ""),
                  "about": look["about"],
                  "clip": f"clips/{prefix}-{key}.mp4", "poster": f"clips/{prefix}-{key}.jpg"}
                 for key, look in section["looks"].items()]
        sections.append({"group": section["group"], "name": section["name"], "say": section["say"],
                         "lead": section["lead"], "looks": looks, "choice": section["choice"],
                         "default": section["default"]})
    data = {"sections": sections, "local": True}
    head = """<title>Talking Head Lookbook</title>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600;700&family=DM+Sans:wght@400;500;700&display=swap" rel="stylesheet">
<style>""" + STYLE + "</style>\n"
    body = f"""<div class="wrap">
  <p class="eyebrow">Clinic Content Engine</p>
  <h1>Talking Head Lookbook</h1>
  <p class="intro">Every look your talking heads can have. Tap a video to watch it with sound, and tick the ones you want. The good ones are ticked already, so you only change what you care about. Then press Save my look and tell Claude "make my talking heads". You can change your mind any time.</p>
  <div class="tools">
    <input id="search" class="search" type="search" placeholder="Search, e.g. calm, bold, luxury" aria-label="Search the looks">
    <div id="tabs" class="tabs" role="group" aria-label="Kinds of look"></div>
  </div>
  <div id="sections"></div>
  <p id="empty" class="empty">Nothing matches that yet. Try another word, or tap All.</p>
  <div class="coming"><strong>Picked for you:</strong> {html.escape(PICKED_FOR_YOU)}</div>
</div>
<div class="bar"><div class="bar-in">
  <p class="bar-text"><strong>Your look:</strong> <span id="bar-summary"></span></p>
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
      <p class="small">This sample uses Frances's own video. Yours will use your video, your words and your brand colours.</p>
    </div>
  </div>
</dialog>
<script type="application/json" id="lookbook">@@DATA@@</script>
<script>{SCRIPT}</script>
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
    # On the student's own computer the page can save a file to Downloads.
    with open(os.path.join(OUT, "index.html"), "w", encoding="utf-8") as f:
        f.write(brand_style.apply(with_data(page, True)))
    # The shareable link can't save files, so it only offers Copy my choices.
    with open(os.path.join(OUT, "share.html"), "w", encoding="utf-8") as f:
        f.write(brand_style.apply(with_data(head + body, False)))
    print(os.path.join(OUT, "index.html"))


if __name__ == "__main__":
    main()
