"""
Makes the post library page: every post style the engine can make, with a
real example of each to swipe through, a search box and tabs.

    python3 engine/make_library.py                       # the library on its own
    python3 engine/make_library.py "My Content/2026-10"  # with that month's posts to pick designs for

With a month (Frances, 2026-10-12: "when they've got a review carousel post on
their plan, they can go in and pick which template they want... then save it,
copy it, and bring it back into Claude so you know which one to use for that
day"), the page lists the month's Canva posts at the top. They tap a post (or
open a design and tap "Use this for..."), pick a design of the right kind for
each day, then Save my picks (my-post-designs.json in Downloads) or Copy my
picks, and tell Claude "make my posts". Days they don't pick get the plan's own
template, or Claude picks one. The planner's Canva days link here (#day-7).

It reads engine/post_library.json (one entry per style), makes small copies of
each example's slides, and saves "My Content/library/index.html". Add a new
style to the JSON and run it again: the page grows with it.
"""

import tools  # noqa: F401  (first: emoji-safe output on Windows)
import brand_style  # the engine's masterclass look on every page
import datetime
import glob
import html
import json
import os
import random
import re
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)
OUT = os.path.join(PROJECT, "My Content", "library")
SLIDE_WIDTH = 720   # the copies on the page; big enough to read, small enough to load fast

STYLE = """
  /* A browsable shelf of post styles: a card grid, and a pop-up viewer to swipe each example. */
  :root { --ink: #2D2E30; --quiet: #6B6A68; --line: #E4DED7; --page: #FAF8F5; --card: #FFFFFF; --nude: #E0D8D0; --grey: #DDDDD8; --shade: rgba(45, 46, 48, .62); --on-ink: #FAF8F5; }
  @media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { --ink: #ECE7E1; --quiet: #A9A39C; --line: #3A3836; --page: #1D1C1B; --card: #262524; --nude: #4A423B; --grey: #33312F; --shade: rgba(0, 0, 0, .7); --on-ink: #1D1C1B; color-scheme: dark; } }
  :root[data-theme="dark"] { --ink: #ECE7E1; --quiet: #A9A39C; --line: #3A3836; --page: #1D1C1B; --card: #262524; --nude: #4A423B; --grey: #33312F; --shade: rgba(0, 0, 0, .7); --on-ink: #1D1C1B; color-scheme: dark; }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--page); color: var(--ink); font: 15px/1.5 'DM Sans', system-ui, sans-serif; }
  .wrap { max-width: 1180px; margin: 0 auto; padding: 32px 16px 56px; }
  h1 { font: 700 34px/1.12 'Playfair Display', serif; margin: 0; }
  .intro { color: var(--quiet); margin: 8px 0 14px; max-width: 640px; }
  .note { background: var(--nude); color: var(--ink); border-radius: 12px; padding: 12px 16px; margin: 0 0 22px; max-width: 640px; }
  .tools { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; margin-bottom: 22px; }
  .search { flex: 1 1 260px; max-width: 380px; padding: 11px 14px; border: 1px solid var(--line); border-radius: 999px; font: inherit; background: var(--card); color: var(--ink); }
  .search:focus, .tab:focus-visible, .copy:focus-visible, .arrow:focus-visible, .close:focus-visible { outline: 2px solid var(--ink); outline-offset: 2px; }
  .tabs { display: flex; flex-wrap: wrap; gap: 8px; }
  .tab { border: 1px solid var(--line); background: var(--card); color: var(--ink); border-radius: 999px; padding: 8px 14px; font: 600 13.5px/1 'DM Sans', sans-serif; cursor: pointer; }
  .tab[aria-pressed="true"] { background: var(--ink); color: var(--on-ink); border-color: var(--ink); }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: 20px; }
  .card { background: var(--card); border: 1px solid var(--line); border-radius: 14px; overflow: hidden; cursor: pointer; text-align: left; padding: 0; font: inherit; color: inherit; display: flex; flex-direction: column; transition: transform .15s ease, box-shadow .15s ease; }
  .card[hidden] { display: none; }
  .card { position: relative; cursor: default; }
  .card[data-other="true"] .tick { display: none; }
  .card .ours { position: absolute; top: 10px; left: 10px; background: var(--card); color: var(--ink); font: 700 11px/1 'DM Sans', sans-serif; padding: 5px 8px; border-radius: 999px; box-shadow: 0 1px 4px rgba(0,0,0,.15); pointer-events: none; }
  .open { all: unset; cursor: pointer; display: flex; flex-direction: column; }
  .open:focus-visible { outline: 2px solid var(--ink); outline-offset: -2px; border-radius: 14px; }
  .tick { position: absolute; top: 10px; right: 10px; width: 40px; height: 40px; border-radius: 50%; border: 2px solid #FFFFFF; background: rgba(45, 46, 48, .35); color: #FFFFFF; font: 700 20px/1 'DM Sans', sans-serif; cursor: pointer; display: grid; place-items: center; }
  .card[data-picked="true"] { border: 3px solid var(--ink); }
  .card[data-picked="true"] .tick { background: var(--ink); border-color: var(--ink); color: var(--on-ink); }
  .pick { align-self: flex-start; border: none; border-radius: 999px; background: var(--ink); color: var(--on-ink); padding: 11px 20px; font: 700 15px/1 'DM Sans', sans-serif; cursor: pointer; }
  .pick.done { background: var(--nude); color: var(--ink); }
  .card:hover, .card:focus-visible { transform: translateY(-3px); box-shadow: 0 10px 26px rgba(45, 46, 48, .12); outline: none; }
  .cover { aspect-ratio: 4 / 5; width: 100%; object-fit: cover; display: block; background: var(--grey); }
  .meta { padding: 14px 16px 16px; display: flex; flex-direction: column; gap: 6px; }
  .tag { align-self: flex-start; font-size: 11.5px; font-weight: 700; padding: 3px 9px; border-radius: 999px; background: var(--nude); }
  .name { font: 700 18px/1.25 'Playfair Display', serif; margin: 0; }
  .count { color: var(--quiet); font-size: 13px; margin: 0; }
  .empty { color: var(--quiet); padding: 30px 0; display: none; }
  dialog { border: none; border-radius: 18px; padding: 0; width: min(1000px, calc(100% - 24px)); max-height: calc(100% - 24px); background: var(--card); color: var(--ink); }
  dialog::backdrop { background: var(--shade); }
  .pop { display: grid; grid-template-columns: minmax(0, 1.05fr) minmax(0, 1fr); }
  .viewer { background: #1F2022; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 18px; gap: 12px; position: relative; }
  .viewer img { width: 100%; max-width: 440px; aspect-ratio: 4 / 5; object-fit: contain; border-radius: 6px; background: #000; user-select: none; }
  .nav { display: flex; align-items: center; gap: 14px; color: #FAF8F5; font-size: 13px; }
  .arrow { width: 38px; height: 38px; border-radius: 50%; border: 1px solid rgba(250, 248, 245, .4); background: transparent; color: #FAF8F5; font-size: 18px; cursor: pointer; }
  .arrow:disabled { opacity: .3; cursor: default; }
  .details { padding: 26px 26px 24px; display: flex; flex-direction: column; gap: 14px; overflow-y: auto; max-height: calc(100vh - 24px); }
  .details h2 { font: 700 26px/1.15 'Playfair Display', serif; margin: 0; }
  .details h3 { font-size: 12px; text-transform: uppercase; letter-spacing: .07em; color: var(--quiet); margin: 0 0 3px; }
  .details p { margin: 0; }
  .say { background: var(--page); border: 1px solid var(--line); border-radius: 12px; padding: 14px; display: flex; flex-direction: column; gap: 10px; }
  .say q { font-weight: 700; }
  .copy { align-self: flex-start; border: none; border-radius: 999px; background: var(--ink); color: var(--on-ink); padding: 9px 16px; font: 600 13.5px/1 'DM Sans', sans-serif; cursor: pointer; }
  .close { position: absolute; top: 10px; right: 10px; width: 36px; height: 36px; border-radius: 50%; border: none; background: rgba(250, 248, 245, .92); color: #2D2E30; font-size: 20px; cursor: pointer; z-index: 2; }
  .small { color: var(--quiet); font-size: 13px; }
  .mine { background: var(--card); border: 1px solid var(--line); border-radius: 14px; padding: 16px 18px; margin: 0 0 24px; }
  .mine h2 { font: 700 20px/1.2 'Playfair Display', serif; margin: 0 0 4px; }
  .mine > p { color: var(--quiet); margin: 0 0 12px; font-size: 14px; }
  .posts { display: flex; flex-wrap: wrap; gap: 8px; }
  .post { border: 1px solid var(--line); background: var(--page); color: var(--ink); border-radius: 12px; padding: 9px 12px; font: 500 13px/1.35 'DM Sans', sans-serif; cursor: pointer; text-align: left; }
  .post b { display: block; font-weight: 700; }
  .post i { font-style: normal; color: var(--quiet); }
  .post[data-picked="true"] i { color: var(--ink); font-weight: 700; }
  .post[aria-pressed="true"] { border: 2px solid var(--ink); }
  .picking { margin: 12px 0 0; font-size: 14px; font-weight: 600; }
  .use { display: flex; flex-wrap: wrap; gap: 8px; }
  .use button { border: none; border-radius: 999px; background: var(--ink); color: var(--on-ink); padding: 10px 16px; font: 700 13.5px/1 'DM Sans', sans-serif; cursor: pointer; }
  .use button.done { background: var(--nude); color: var(--ink); }
  .bar { position: fixed; left: 0; right: 0; bottom: 0; background: var(--card); border-top: 1px solid var(--line); padding: 12px 16px calc(12px + env(safe-area-inset-bottom, 0px)); box-shadow: 0 -6px 20px rgba(45, 46, 48, .08); z-index: 5; }
  .bar-in { max-width: 1180px; margin: 0 auto; display: flex; flex-wrap: wrap; gap: 10px 16px; align-items: center; }
  .bar-text { flex: 1 1 320px; min-width: 0; font-size: 14px; margin: 0; }
  .bar-buttons { display: flex; gap: 8px; flex-wrap: wrap; }
  .save { border: none; border-radius: 999px; background: var(--ink); color: var(--on-ink); padding: 11px 18px; font: 700 14px/1 'DM Sans', sans-serif; cursor: pointer; }
  .save.quiet { background: transparent; color: var(--ink); border: 1px solid var(--line); }
  .save[hidden], .bar[hidden], .mine[hidden] { display: none; }
  .saved-note { font-size: 13px; color: var(--quiet); width: 100%; margin: 0; }
  .wrap { padding-bottom: 170px; }
  @media (max-width: 760px) {
    .pop { grid-template-columns: 1fr; }
    .details { max-height: none; }
    h1 { font-size: 28px; }
    .grid { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
    .meta { padding: 10px 12px 12px; }
    .name { font-size: 15.5px; }
    .viewer img { max-width: 300px; }
  }
"""

SCRIPT = """
const data = JSON.parse(document.getElementById('library').textContent);
const grid = document.getElementById('grid');
const search = document.getElementById('search');
const empty = document.getElementById('empty');
const dialog = document.getElementById('pop');
let tab = 'All', open = null, slide = 0;

function cards() {
  const words = search.value.toLowerCase().trim().split(/\\s+/).filter(Boolean);
  let shown = 0;
  for (const card of grid.children) {
    const style = data.styles[card.dataset.i];
    const text = [style.name, style.category, style.about, style.good_for, style.keywords].join(' ').toLowerCase();
    const show = (tab === 'All' || style.category === tab) && words.every(w => text.includes(w));
    card.hidden = !show;
    shown += show;
  }
  empty.style.display = shown ? 'none' : 'block';
}

function show(i) {
  open = data.styles[i]; slide = 0;
  document.getElementById('p-name').textContent = open.name;
  document.getElementById('p-tag').textContent = open.category + ' · ' + open.slides;
  document.getElementById('p-about').textContent = open.about;
  document.getElementById('p-good').textContent = open.good_for;
  document.getElementById('p-needs').textContent = open.needs;
  document.getElementById('p-example').textContent = 'This is a sample. Yours will use your own words, photos, reviews and colours.';
  document.getElementById('p-say').textContent = 'Make my posts in the ' + open.name.split(':')[0] + ' style';
  document.getElementById('copy').textContent = 'Copy';
  draw();
  useButtons();
  dialog.showModal();
}

function draw() {
  const img = document.getElementById('p-img');
  img.src = open.slides_src[slide];
  img.alt = open.name + ', slide ' + (slide + 1);
  const n = open.slides_src.length;
  document.getElementById('count').textContent = n > 1 ? (slide + 1) + ' of ' + n : '';
  document.getElementById('prev').disabled = slide === 0;
  document.getElementById('next').disabled = slide === n - 1;
  document.getElementById('prev').style.visibility = document.getElementById('next').style.visibility = n > 1 ? 'visible' : 'hidden';
}

function step(d) {
  const n = open.slides_src.length;
  slide = Math.max(0, Math.min(n - 1, slide + d));
  draw();
}

data.styles.forEach((style, i) => {
  const card = document.createElement('div');
  card.className = 'card'; card.dataset.i = i;
  card.innerHTML = '<button class="open" type="button"><img class="cover" loading="lazy" alt=""><div class="meta">' +
    '<span class="tag"></span><p class="name"></p><p class="count"></p></div></button>' +
    '<button class="tick" type="button" aria-pressed="false"></button>';
  card.querySelector('.cover').src = style.slides_src[0];
  card.querySelector('.tag').textContent = style.category;
  card.querySelector('.name').textContent = style.name;
  card.querySelector('.count').textContent = style.slides;
  card.querySelector('.tick').setAttribute('aria-label', 'Pick ' + style.name);
  card.querySelector('.open').addEventListener('click', () => show(i));
  card.querySelector('.tick').addEventListener('click', () => active ? tickDay(style) : tickGroup(style));
  grid.appendChild(card);
});

const tabs = document.getElementById('tabs');
['All', ...data.categories].forEach(name => {
  const b = document.createElement('button');
  b.className = 'tab'; b.type = 'button'; b.textContent = name;
  b.setAttribute('aria-pressed', name === tab);
  b.addEventListener('click', () => {
    tab = name;
    for (const t of tabs.children) t.setAttribute('aria-pressed', t === b);
    cards();
  });
  tabs.appendChild(b);
});

search.addEventListener('input', cards);
document.getElementById('prev').addEventListener('click', () => step(-1));
document.getElementById('next').addEventListener('click', () => step(1));
document.getElementById('close').addEventListener('click', () => dialog.close());
dialog.addEventListener('click', e => { if (e.target === dialog) dialog.close(); });
document.addEventListener('keydown', e => {
  if (!dialog.open) return;
  if (e.key === 'ArrowLeft') step(-1);
  if (e.key === 'ArrowRight') step(1);
});
let touchX = null;
const viewer = document.querySelector('.viewer');
viewer.addEventListener('touchstart', e => { touchX = e.touches[0].clientX; }, {passive: true});
viewer.addEventListener('touchend', e => {
  if (touchX === null) return;
  const dx = e.changedTouches[0].clientX - touchX;
  if (Math.abs(dx) > 40) step(dx < 0 ? 1 : -1);
  touchX = null;
});
document.getElementById('copy').addEventListener('click', async () => {
  const words = document.getElementById('p-say').textContent;
  try { await navigator.clipboard.writeText(words); document.getElementById('copy').textContent = 'Copied'; }
  catch (e) { document.getElementById('copy').textContent = 'Select the words above to copy them'; }
});

// ---- Picking designs, like the lookbooks (Frances, 2026-10-12) ----
// Without a month, a tick on a design makes it their favourite for that kind of post.
// With a planned month, every post has a design of its own, picked one post at a time, with our pick ticked
// already (Frances, 2026-10-15: "it's not one carousel fits all for the month"). Quote posts all share one.
const QUOTES = 'Quote posts';
const month = data.month;
const STORE = 'post-designs';
let picks = {groups: {}, days: {}}, active = null;
try {
  const kept = JSON.parse(localStorage.getItem(STORE) || '{}');
  picks.groups = kept.groups || {};
  if (month && kept.month === month.key) picks.days = kept.days || {};
} catch (e) {}
// Forget any remembered pick that doesn't suit its post (a carousel design ticked for a quote post).
const kindOf = id => (data.styles.find(x => x.id === id) || {}).category;
for (const g of Object.keys(picks.groups)) if (kindOf(picks.groups[g]) !== g) delete picks.groups[g];
if (month) for (const d of Object.keys(picks.days)) {
  const post = month.posts.find(p => String(p.day) === String(d));
  if (!post || kindOf(picks.days[d]) !== post.kind) delete picks.days[d];
}
if (month) document.body.classList.add('picking-month');
function remember() {
  try { localStorage.setItem(STORE, JSON.stringify({groups: picks.groups, days: picks.days, month: month ? month.key : null})); } catch (e) {}
}
function styleName(id) { const st = data.styles.find(x => x.id === id); return st ? st.name : ''; }
function postFor(day) { return month.posts.find(p => p.day === day); }
function kindWord(kind) { return kind.toLowerCase().replace(/s$/, ''); }

function designFor(p) {
  if (p.kind === QUOTES) return picks.groups[QUOTES] || p.suggested || '';
  return picks.days[p.day] || p.suggested || '';
}
function tickGroup(style) {
  if (picks.groups[style.category] === style.id) delete picks.groups[style.category];
  else picks.groups[style.category] = style.id;
  remember(); paint();
}

// Picking for one post (Frances, 2026-10-14: three carousels can have three different designs): while a post
// is chosen, a tick is just for that post.
function tickDay(style) {
  const p = postFor(active);
  if (style.category !== p.kind) {          // a quote post gets a quote design, a review carousel a review design...
    document.getElementById('picking').textContent = "That design is for " + style.category.toLowerCase() +
      ". For this post, tick one of the " + p.kind.toLowerCase() + ".";
    tab = p.kind;
    for (const t of tabs.children) t.setAttribute('aria-pressed', t.textContent === tab);
    cards();
    return;
  }
  if (p.kind === QUOTES) { picks.groups[QUOTES] = style.id; remember(); paint(); return; }
  if (picks.days[active] === style.id) delete picks.days[active];
  else picks.days[active] = style.id;
  remember(); paint();
}

function summary() {
  if (month && month.posts.length) return month.posts.map(p => p.date + ': ' + styleName(designFor(p))).join(' · ');
  return data.categories.filter(c => picks.groups[c]).map(c => c + ': ' + styleName(picks.groups[c])).join(' · ');
}

function paint() {
  for (const card of grid.children) {
    const st = data.styles[card.dataset.i];
    const ap = active && postFor(active);
    const on = ap ? designFor(ap) === st.id : picks.groups[st.category] === st.id;
    card.dataset.picked = on;
    card.dataset.other = !!(ap && st.category !== ap.kind);   // not for this post: its tick is hidden
    const t = card.querySelector('.tick');
    t.setAttribute('aria-pressed', on); t.textContent = on ? '✓' : '';
    let badge = card.querySelector('.ours');
    if (ap && ap.suggested === st.id && ap.kind !== QUOTES) {
      if (!badge) { badge = document.createElement('span'); badge.className = 'ours'; badge.textContent = 'Our pick'; card.appendChild(badge); }
    } else if (badge) badge.remove();
  }
  if (month) {
    for (const b of document.querySelectorAll('.post')) {
      const p = postFor(b.dataset.day);
      const design = designFor(p);
      b.dataset.picked = !!design;
      b.setAttribute('aria-pressed', active === p.day);
      b.querySelector('i').textContent = design ? '✓ ' + styleName(design) : 'Pick a design';
    }
    const p = active && postFor(active);
    document.getElementById('picking').textContent = !p ? '' : p.kind === QUOTES
      ? 'Your quote posts all share one design, so they match on your grid. Tick the one you want.'
      : 'Picking the design for ' + p.date + ' (' + kindWord(p.kind) + '). Our pick is ticked: tick another if you\\'d like it instead.';
    const last = p && month.posts[month.posts.length - 1] === p;
    document.getElementById('done-day').hidden = !p;
    document.getElementById('done-day').textContent = last ? "That's all of them" : 'Next post';
  }
  document.getElementById('bar-summary').textContent = summary() || 'Tick a design for each kind of post. Any you leave, Claude picks for you.';
  document.querySelectorAll('.card .tick').forEach(t => t.title = '');
  if (open) useButtons();
}

function choose(day, scroll = true) {
  active = day;
  tab = postFor(day).kind;
  for (const t of tabs.children) t.setAttribute('aria-pressed', t.textContent === tab);
  cards(); paint();
  if (scroll) document.querySelector('.mine').scrollIntoView({behavior: 'smooth', block: 'start'});
}

function useButtons() {
  const pick = document.getElementById('p-pick');
  const on = picks.groups[open.category] === open.id;
  pick.textContent = on ? '✓ My design for ' + open.category.toLowerCase() : 'Pick this for my ' + open.category.toLowerCase();
  pick.className = on ? 'pick done' : 'pick';
  // With a month, only quote posts share a design; everything else is picked post by post.
  pick.hidden = !!(month && month.posts.length && open.category !== QUOTES);
  const box = document.getElementById('p-use');
  box.innerHTML = '';
  const fits = month ? month.posts.filter(p => p.kind === open.category && p.kind !== QUOTES) : [];
  box.parentElement.hidden = !fits.length;
  for (const p of fits) {
    const b = document.createElement('button');
    b.type = 'button';
    const mine = designFor(p) === open.id;
    b.className = mine ? 'done' : '';
    b.textContent = mine ? '✓ Using for ' + p.date : 'Use for ' + p.date;
    b.addEventListener('click', () => {
      if (picks.days[p.day] === open.id) delete picks.days[p.day]; else picks.days[p.day] = open.id;
      remember(); paint();
    });
    box.appendChild(b);
  }
}
document.getElementById('p-pick').addEventListener('click', () => { if (open) tickGroup(open); });
const doneDay = document.getElementById('done-day');
if (doneDay) doneDay.addEventListener('click', () => {
  const i = month.posts.findIndex(p => p.day === active);
  if (i >= 0 && i < month.posts.length - 1) { choose(month.posts[i + 1].day); return; }
  active = null; paint();
  document.getElementById('saved-note').textContent = 'All picked. Press Save my picks, then tell Claude: make my posts';
  document.querySelector('.bar').scrollIntoView({behavior: 'smooth', block: 'end'});
});

if (month) {
  const list = document.getElementById('posts');
  for (const p of month.posts) {
    const b = document.createElement('button');
    b.className = 'post'; b.type = 'button'; b.dataset.day = p.day;
    b.innerHTML = '<b></b><span></span><br><i></i>';
    b.querySelector('b').textContent = p.date;
    b.querySelector('span').textContent = p.kind.replace(/s$/, '') + (p.what ? ': ' + p.what : '');
    b.addEventListener('click', () => choose(p.day));
    list.appendChild(b);
  }
  // The planner links to a post by its date (#day-2026-12-01); older pages by its day number (#day-7).
  const fromLink = (location.hash.match(/^#day-([\\d-]+)$/) || [])[1];
  const linked = fromLink && month.posts.find(p => p.day === fromLink || Number(p.day.slice(8)) === Number(fromLink));
  if (linked) choose(linked.day);
  else if (month.posts.length) choose(month.posts[0].day, false);     // start them on their first post
}

const saveButton = document.getElementById('save');
saveButton.hidden = !data.local;
saveButton.addEventListener('click', () => {
  const days = {}, groups = Object.assign({}, picks.groups);
  if (month) for (const p of month.posts) {
    if (p.kind === QUOTES) groups[QUOTES] = designFor(p); else if (designFor(p)) days[p.day] = designFor(p);
  }
  const file = {what: 'my post designs', saved: new Date().toISOString(), groups,
                month: month ? month.key : null, days, in_words: summary()};
  try {
    const blob = new Blob([JSON.stringify(file, null, 1)], {type: 'application/json'});
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob); a.download = 'my-post-designs.json';
    document.body.appendChild(a); a.click(); a.remove();
    document.getElementById('saved-note').textContent = 'Saved. Now tell Claude: make my posts';
  } catch (e) {
    document.getElementById('saved-note').textContent = "That didn't save. Tap Copy my picks and paste them to Claude instead.";
  }
});
document.getElementById('copy-picks').addEventListener('click', async () => {
  const words = 'My post designs: ' + (summary() || 'none picked yet');
  try { await navigator.clipboard.writeText(words); document.getElementById('saved-note').textContent = 'Copied. Paste it to Claude and say: make my posts'; }
  catch (e) { document.getElementById('saved-note').textContent = words; }
});
paint();
cards();
"""


def small_copies(style):
    """Small copies of the example's slides, in order, ready for the page."""
    files = []
    for pattern in style["images"]:
        files += sorted(glob.glob(os.path.join(PROJECT, pattern)))
    if not files:
        # A student's engine has only the small copies that came with it (the full-size samples stay on
        # Frances's computer), so use those as they are.
        return [f"img/{os.path.basename(p)}" for p in sorted(glob.glob(os.path.join(OUT, "img", f"{style['id']}-*.jpg")))]
    out = []
    for n, path in enumerate(files, 1):
        name = f"{style['id']}-{n:02d}.jpg"
        target = os.path.join(OUT, "img", name)
        if not os.path.exists(target) or os.path.getmtime(target) < os.path.getmtime(path):
            picture = Image.open(path).convert("RGB")
            picture = picture.resize((SLIDE_WIDTH, round(picture.height * SLIDE_WIDTH / picture.width)), Image.LANCZOS)
            picture.save(target, quality=86)
        out.append(f"img/{name}")
    return out


# Sale words. Not "offer" on its own: "the treatments you offer" isn't a sale (Sonnet test, 2026-10-14).
SALE = re.compile(r"\b(sale|black friday|cyber monday|waitlist|wait list|vip list|special offer|offer ends|"
                  r"limited offer|discount|\d+% off)\b", re.I)


# Before and after posts (Frances, 2026-10-28: their own group in the library).
BEFORE_AFTER = re.compile(r"\b(before (and|&) after|before/after|client results|results carousel)\b", re.I)

# A Canva post by its type, even when the calendar's "Needs" says "photos" instead of "Canva": that's written
# fresh by Claude each month, and a carousel missing from the list left a student with nothing to pick
# (Frances, 2026-11-02).
CANVA_TYPE = re.compile(r"\b(carousel|quote|static|single post|picture post|graphic|canva)\b", re.I)
NOT_CANVA = re.compile(r"\b(reel|meme|talking head|voiceover|capcut|rest day)\b", re.I)


def is_canva_post(row):
    if "canva" in row["needs"].lower():
        return True
    kind = row["type"] + " " + row["needs"]
    return bool(CANVA_TYPE.search(kind)) and not NOT_CANVA.search(kind)


def month_posts(folder):
    """The month's Canva posts: [{day (its date, 2026-12-01), date (in words), kind (the library's group), what}],
    from its calendar and posts. A plan can run on into the next month (days.py)."""
    sys.path.insert(0, HERE)
    import days
    from make_planner import post_fields, read_calendar
    year, month = days.start_of(folder)
    posts = open(os.path.join(folder, "posts.md"), encoding="utf-8").read()
    rows, found = read_calendar(folder), []
    for row in rows:
        if not is_canva_post(row):
            continue
        fields = post_fields(posts, row["date"])
        words = " ".join([row["type"], row["what"], row["needs"]] +
                         [v for k, v in fields.items() if k != "What to do"]).lower()   # not Claude's own notes
        kind_text = (row["type"] + " " + row["needs"] + " " + row["what"]).lower()
        if "quote" in kind_text:
            kind = "Quote posts"
        elif BEFORE_AFTER.search(kind_text):
            kind = "Before and after carousels"
        elif "review" in kind_text:
            kind = "Review carousels"
        elif "carousel" in kind_text:
            kind = "Sale carousels" if SALE.search(words) else "Treatment carousels"
        else:
            kind = "Single posts"
        date = row["date"]
        found.append({"day": row["key"], "date": f"{date:%a} {date.day} {date:%B}", "kind": kind,
                      "what": row["what"].strip('"…. ')[:40]})
    return {"key": f"{year}-{month:02d}", "name": days.month_names(rows) if rows else datetime.date(year, month, 1).strftime("%B"),
            "posts": found}


QUOTES = "Quote posts"


def give_every_post_designs(posts, styles):
    """A post whose kind has no designs yet (Before and after, until its sample is made) is picked from the
    treatment carousels instead, so the picker is never empty (Frances, 2026-11-02: a student "went into the
    carousels and there was no designs available for her to pick")."""
    kinds = {s["category"] for s in styles}
    for post in posts:
        if post["kind"] in kinds:
            continue
        fallback = "Treatment carousels" if post["kind"].endswith("carousels") else "Single posts"
        post["kind"] = fallback if fallback in kinds else next(iter(sorted(kinds)), post["kind"])


def check_line(styles, month):
    """One line for Claude to read after every build, so an empty library is caught before a student sees it."""
    if not styles:
        return ("PROBLEM: no designs on the page: the library's sample pictures (My Content/library/img) are "
                "missing. Put them back (\"update my engine\" brings them) before opening it.")
    line = f"LIBRARY: {len(styles)} designs"
    if month is not None:
        posts = month["posts"]
        kinds = {s["category"] for s in styles}
        empty = [p["date"] for p in posts if p["kind"] not in kinds]
        if empty:
            return line + f". PROBLEM: no designs to pick for {', '.join(empty)}."
        line += (f", and {len(posts)} of this month's posts to pick a design for, each with designs to choose from"
                 if posts else ". CHECK: no Canva posts found in this month's calendar (no carousels, quotes or "
                               "single posts), so there's nothing to pick for yet")
    return line + "."


def suggest_designs(posts, styles, folder):
    """Our pick for each of the month's posts (Frances, 2026-10-15: "it's not one carousel fits all for the
    month"): each kind of post takes turns through its designs, so no two carousels in a row look the same,
    in a different order for each clinic and month. Quote posts all share one design (her rule: uniform)."""
    name = ""
    profile = os.path.join(os.path.dirname(os.path.abspath(folder)), "my-clinic.md")
    if os.path.exists(profile):
        found = re.search(r"\*\*Clinic name:\*\* (.+)", open(profile, encoding="utf-8").read())
        name = found.group(1).strip() if found else ""
    rng = random.Random(f"{name}|{os.path.basename(os.path.normpath(folder))}")
    turns = {}
    for kind in dict.fromkeys(p["kind"] for p in posts):
        options = [s["id"] for s in styles if s["category"] == kind]
        rng.shuffle(options)
        turns[kind] = options
    for n, post in enumerate(p for p in posts):
        options = turns.get(post["kind"]) or []
        if not options:
            continue
        if post["kind"] == QUOTES:
            post["suggested"] = options[0]
        else:
            done = sum(1 for q in posts[:n] if q["kind"] == post["kind"])
            post["suggested"] = options[done % len(options)]


def main(month_folder=None, write=True):
    data = json.load(open(os.path.join(HERE, "post_library.json"), encoding="utf-8"))
    # Designs from the engine extras they've unlocked (My Content/.extras: design drops unlocked with a code, part of the content plan subscription).
    try:
        import extras
        data["styles"] += extras.library_styles()
        data["categories"] += [c for c in extras.categories() if c not in data["categories"]]
    except Exception:
        pass
    os.makedirs(os.path.join(OUT, "img"), exist_ok=True)
    styles = []
    for style in data["styles"]:
        # A design taken off the page for now (Frances, 2026-11-02: designs whose slides have no photos come off
        # until her designer's versions, with photos placed, are ready), kept here so it can come back.
        if style.get("hidden"):
            continue
        style["slides_src"] = small_copies(style)
        if style["slides_src"]:
            styles.append(style)
        else:
            print(f"No example pictures yet for {style['name']}, so it's left off the page.")
    data["styles"] = styles
    # A group with no designs yet (Before and after, until its sample is made) stays off the page.
    data["categories"] = [c for c in data["categories"] if any(s["category"] == c for s in styles)]
    data["month"] = month_posts(month_folder) if month_folder else None
    if data["month"]:
        give_every_post_designs(data["month"]["posts"], styles)
        suggest_designs(data["month"]["posts"], styles, month_folder)

    head = f"""<title>Clinic Post Library</title>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600;700&family=DM+Sans:wght@400;500;700&display=swap" rel="stylesheet">
<style>{STYLE}</style>
"""
    body = f"""<div class="wrap">
  <h1>{html.escape(data["title"])}</h1>
  <p class="intro">{html.escape(data["intro"])}</p>
  <p class="note">{html.escape(data["note"])}</p>
  @@MINE@@
  <div class="tools">
    <input id="search" class="search" type="search" placeholder="Search, e.g. reviews, quote, lashes" aria-label="Search the post styles">
    <div id="tabs" class="tabs" role="group" aria-label="Post types"></div>
  </div>
  <div id="grid" class="grid"></div>
  <p id="empty" class="empty">Nothing matches that yet. Try another word, or tap All.</p>
</div>
<dialog id="pop" aria-labelledby="p-name">
  <button id="close" class="close" type="button" aria-label="Close">×</button>
  <div class="pop">
    <div class="viewer">
      <img id="p-img" alt="">
      <div class="nav">
        <button id="prev" class="arrow" type="button" aria-label="Previous slide">‹</button>
        <span id="count"></span>
        <button id="next" class="arrow" type="button" aria-label="Next slide">›</button>
      </div>
    </div>
    <div class="details">
      <span id="p-tag" class="tag"></span>
      <h2 id="p-name"></h2>
      <p id="p-about"></p>
      <div><h3>Great for</h3><p id="p-good"></p></div>
      <div><h3>What you'll need</h3><p id="p-needs"></p></div>
      <button id="p-pick" class="pick" type="button">Pick this</button>
      <div hidden><h3>Or just for one post this month</h3><div id="p-use" class="use"></div></div>
      <div class="say"><h3>To use this style, tell Claude</h3><q id="p-say"></q><button id="copy" class="copy" type="button">Copy</button></div>
      <p id="p-example" class="small"></p>
    </div>
  </div>
</dialog>
@@BAR@@
<script type="application/json" id="library">@@DATA@@</script>
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
    def fill(text, month, local):
        bar = ('<div class="bar"><div class="bar-in"><p class="bar-text"><strong>Your post designs:</strong> '
               '<span id="bar-summary"></span></p><div class="bar-buttons">'
               '<button id="save" class="save" type="button">Save my picks</button>'
               '<button id="copy-picks" class="save quiet" type="button">Copy my picks</button></div>'
               '<p id="saved-note" class="saved-note">Then tell Claude: make my posts</p></div></div>')
        mine = ""
        if month:
            when = ("for " if " and " in month["name"] else "this ") + month["name"]   # "for November and December"
            mine = (f'<section class="mine"><h2>Your posts {html.escape(when)}</h2>'
                    '<p>Every post gets its own design, so your grid never looks samey. Go through them one at a '
                    'time: tick the design you want for each post. We\'ve ticked a good one already, so if you like '
                    'it, just press Next post. Your quote posts all share one design, so they match.</p>'
                    '<div id="posts" class="posts"></div>'
                    '<p id="picking" class="picking"></p><button id="done-day" class="save quiet" type="button" hidden>'
                    'Next post</button></section>')
        payload = json.dumps(dict(data, month=month, local=local), ensure_ascii=False).replace("</", "<\\/")
        return text.replace("@@MINE@@", mine).replace("@@BAR@@", bar).replace("@@DATA@@", payload)

    pages = {"index.html": fill(page, data["month"], True),     # on their computer, with their month's posts
             "share.html": fill(head + body, None, False),       # the shareable link: the library on its own
             "plain.html": fill(page, None, True)}               # the course download: no month yet
    if write:
        for name, text in pages.items():
            with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
                f.write(brand_style.apply(text))
        print(os.path.join(OUT, "index.html"))
        print(check_line(styles, data["month"]))
    return pages


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
