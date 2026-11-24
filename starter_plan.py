"""
Picks a clinic's posts from a plan's packs and puts them on dates: their Starter Plan (their first 30 days)
and every monthly plan after it.

Both kinds of plan come in packs: 30 posts for each treatment type (Laser, Skin, Aesthetics, Body, PMU, and
later more), each post headed by its pack and number ("LASER 1" to "LASER 30") with a label block:

    LASER 1
    Content type: Reel - growth
    JOB: reach
    NEEDS NEW FILMING: no
    SUITS: all laser treatments
    DATE: 14 February                  (only on a post that must go out on that day)
    REEL TEXT ON SCREEN:
    ...
    REEL TEXT ON SCREEN (OTHER WORDING):
    ...

The Starter Plan comes inside the engine (engine/included-plan.md, starting "STARTER PLAN"). Each monthly
plan is pasted in by the clinic (it starts with its month, "FEBRUARY 2027 CONTENT PLAN").

Every clinic's month is its own (Frances, 2026-10-12 and 2026-11-18: "no matter how many people are using the
content plans in the engine, no one's content is the same"). So the posts aren't the top of each pack: they're
picked for this clinic from the whole pack, keeping the pack's balance of kinds (a fair share of its reels,
carousels, talking heads, quotes and memes), with one of each reel's two wordings, written for their own
treatments, in their own voice.

    PY engine/starter_plan.py split --types "Laser, Skin" [--posts 22] [plan]
    PY engine/starter_plan.py make <plan> --start 2027-02-01 [--until 2027-02-28] [--days-a-week 5] [--posts 20]
        --mix "Laser=12, Skin=8" --treatments "Laser hair removal (Laser), HydraFacial (Skin)"
        --record "My Content/used-posts.json" --out "My Content/2027-02"

split prints the even mix for their treatment types, and a leaning mix for each type, for the clickable
question. make writes the clinic's dated plan (plan.md), treatments.json ({date: treatment}) and a copy of the
plan it came from (source-plan.md), and records which posts they used in used-posts.json. Each month only ever uses
that month's plan: posts an earlier plan didn't use never come back (Frances, 2026-11-23: so the monthly plans stay
worth paying for). How the days are laid out:

- The dates: from --start to --until (the Starter Plan: 30 days), on the days of the week they post
  (--days-a-week 7, 6, 5, 4, 3, 2 or 1), or --posts of those days, spread out evenly.
- A post with a DATE goes out on that day (on the nearest posting day if it isn't one); a dated post whose day
  isn't in their dates is left out.
- Posts that need new filming (NEEDS NEW FILMING: yes, and every talking head) go late, every other posting day
  from the end, so they have time to film. Everything else comes first. A voiceover is a voice note over clips
  they already have, so it isn't held back unless its pack says it needs new filming.
- Exactly one client review carousel, whatever the mix.
- The packs take turns, in proportion to the mix, never the same pack two days running when there's a choice;
  no two talking heads back to back, carousels at least 5 days apart, quotes and memes spread out.
- Each treatment of that type takes turns (SUITS keeps a post off a treatment it doesn't fit).
"""

import tools  # noqa: F401  (first: emoji-safe output on Windows)
import argparse
import datetime
import hashlib
import json
import os
import random
import re
import shutil
import sys

import days

PACKS = ["Laser", "Skin", "Aesthetics", "Body", "PMU", "Lash and brow", "Tattoo removal", "Hair", "Nails", "Beauty",
         "Teeth whitening"]
OTHER_NAMES = {"aesthetic": "Aesthetics", "body contouring": "Body", "semi-permanent make-up": "PMU",
               "lash": "Lash and brow", "lashes": "Lash and brow", "brows": "Lash and brow", "brow": "Lash and brow",
               "tattoo": "Tattoo removal", "laser tattoo removal": "Tattoo removal",
               "lashes and brows": "Lash and brow", "hairdressing": "Hair", "hairdresser": "Hair", "hair salon": "Hair",
               "nail": "Nails", "nail tech": "Nails", "beauty salon": "Beauty", "beauty treatments": "Beauty",
               "teeth": "Teeth whitening"}
# Beauty businesses beyond the five packs (Frances, 2026-11-23: hairdressers, lash techs, nail techs and beauty salons
# are signing up). Until a plan has their own pack, their posts come from the closest one, and plan-my-month rewrites
# every one of them fully for their own treatments.
STAND_INS = {"Lash and brow": "PMU", "Hair": "Skin", "Nails": "Skin", "Beauty": "Skin", "Teeth whitening": "Aesthetics"}
LENGTH = 30
HEAD = re.compile(r"^(" + "|".join(re.escape(p) for p in sorted(PACKS, key=len, reverse=True)) + r")\s+(\d{1,2})\s*$", re.I)
LABEL = re.compile(r"^(?:[A-Z][A-Z0-9 /()'&-]+|Content type|Template|Example|Quote text|Optional[^:]*):", re.I)
CAPS_LABEL = re.compile(r"^[A-Z][A-Z0-9 /()'&-]+:")
PLAN_TOP = re.compile(r"^[A-Z0-9 ,.'&:()-]*\b(STARTER PLAN|CONTENT PLAN|PACK)\b[A-Z0-9 ,.'&:()-]*$")
SEASONAL = re.compile(r"\b(?:(?-i:May)|january|february|march|april|june|july|august|september|october|november|december|"
                      r"christmas|xmas|halloween|black friday|cyber monday|valentine'?s?|easter|new year|"
                      r"mother'?s day|father'?s day|bonfire|summer|winter|spring|autumn|festive|this month)\b", re.I)
WEEKDAYS = {7: range(7), 6: range(6), 5: range(5), 4: (0, 1, 3, 4), 3: (0, 2, 4), 2: (1, 3), 1: (2,)}


def plan_label(path):
    """The plan's name from its first line: 'STARTER PLAN', 'FEBRUARY 2027 CONTENT PLAN'."""
    for raw in open(path, encoding="utf-8"):
        line = clean(raw).strip()
        if line:
            found = re.search(r"([A-Z0-9 ]*\b(?:STARTER PLAN|CONTENT PLAN))", line.upper())
            return (found.group(1) if found else line[:60]).strip()
    return os.path.basename(path)


def pack_name(text):
    text = text.strip().strip("*").strip()
    for name in PACKS:
        if text.lower() == name.lower():
            return name
    return OTHER_NAMES.get(text.lower())


# ---------------------------------------------------------------------------
# Reading the packs
# ---------------------------------------------------------------------------

def clean(line):
    """A line without markdown dressing: '## **LASER 1**' -> 'LASER 1', '**CAPTION:**' -> 'CAPTION:'."""
    line = line.rstrip()
    line = re.sub(r"^#+\s*", "", line)
    return line.replace("**", "").replace("__", "")


def read_packs(path):
    """{pack: [post, ...]} in pick order. A post: {pack, number, id, type, job, film, suits, lines}."""
    packs, post = {}, None
    text = open(path, encoding="utf-8").read()
    if not any(HEAD.match(clean(l).strip()) for l in text.splitlines()):
        import plan_docs                     # a plan written as Google Docs ("Day One"...): read it as packs
        if plan_docs.looks_like_docs(text):
            text = plan_docs.convert(text, plan_label(path))
    for raw in text.splitlines():
        line = clean(raw)
        head = HEAD.match(line.strip())
        if head:
            post = {"pack": pack_name(head.group(1)), "number": int(head.group(2)), "lines": []}
            post["id"] = f"{post['pack']} {post['number']}"
            packs.setdefault(post["pack"], []).append(post)
            continue
        if PLAN_TOP.match(line.strip()):
            post = None                      # a plan's or a pack's top lines: not part of the post before
            continue
        if post is not None:
            post["lines"].append(line)
    for posts in packs.values():
        for post in posts:
            while post["lines"] and not post["lines"][-1].strip():
                post["lines"].pop()
            while post["lines"] and re.fullmatch(r"\s*(-{3,}|\*{3,})\s*", post["lines"][-1]):
                post["lines"].pop()
            text = "\n".join(post["lines"])
            field = lambda label: (re.search(rf"^{label}:\s*(.*)$", text, re.I | re.M) or [None, ""])[1].strip()
            post["type"] = field("Content type")
            post["job"] = field("JOB").lower()
            # A talking head always needs filming. A voiceover doesn't: it's a voice note over clips the clinic
            # already has (the Laser pack's notes, 2026-10-17), so it follows its own NEEDS NEW FILMING line.
            post["film"] = field("NEEDS NEW FILMING").lower().startswith("y") or bool(
                re.search(r"talking[- ]head", post["type"], re.I))
            post["review"] = bool(re.search(r"review", post["type"], re.I)) or any(
                re.search(r"review carousel", l, re.I) for l in post["lines"][:3])
            post["suits"] = field("SUITS")
            post["date_text"] = field("DATE") or field("MOMENT")
            post["seasonal"] = bool(post["date_text"]) or bool(SEASONAL.search(text))
        posts.sort(key=lambda p: p["number"])
    return packs


def kind_of(post):
    t = post["type"].lower().replace("talking-head", "talking head")
    if "talking head" in t:
        return "talking head"
    if "voiceover" in t:
        return "voiceover"
    if "carousel" in t:
        return "carousel"
    if "meme" in t:
        return "meme"
    if "quote" in t:
        return "quote"
    if "static" in t or ("post" in t and "reel" not in t):
        return "post"
    return "reel"


# ---------------------------------------------------------------------------
# The mix
# ---------------------------------------------------------------------------

def home(kind, packs):
    """The pack a treatment type's posts come from: its own, or its stand-in's (STAND_INS) when the plan has none."""
    if packs.get(kind):
        return kind
    stand_in = STAND_INS.get(kind)
    return stand_in if stand_in and packs.get(stand_in) else kind


def even_mix(types, total=LENGTH):
    """30 shared out evenly between their treatment types; the first named take any extra."""
    share, extra = divmod(total, len(types))
    return {t: share + (1 if i < extra else 0) for i, t in enumerate(types)}


def read_mix(text):
    """'Laser=15, Skin=15' -> {'Laser': 15, 'Skin': 15}."""
    mix = {}
    for part in [p.strip() for p in text.split(",") if p.strip()]:
        name, _, count = part.partition("=")
        pack = pack_name(name)
        if not pack:
            sys.exit(f"'{name.strip()}' isn't a treatment type the Starter Plan has packs for ({', '.join(PACKS)}).")
        mix[pack] = int(count) if count.strip() else 0
    return mix


def leaning(types, total, toward):
    """A mix leaning toward one type (about three fifths of the posts when there are two types)."""
    if len(types) == 1:
        return {types[0]: total}
    big = round(total * (0.6 if len(types) == 2 else 0.5))
    rest = even_mix([t for t in types if t != toward], total - big)
    return {t: (big if t == toward else rest[t]) for t in types}


def settle(mix, packs, total=LENGTH):
    """The mix, fitted to the packs there are: a type with no pack (not written yet) or too few posts gives its
    share to the others, so they always get 30 days. Returns the mix and notes in plain words."""
    notes, mix = [], dict(mix)
    for t in list(mix):
        if not packs.get(t):
            stand_in = STAND_INS.get(t)
            if stand_in and packs.get(stand_in):
                notes.append(f"{t}: there's no {t.lower()} pack in this plan, so its posts come from the {stand_in} pack, "
                             f"rewritten fully for their {t.lower()} treatments (call them {t.lower()} posts, never "
                             f"{stand_in.lower()}).")
                mix[stand_in] = mix.get(stand_in, 0) + mix.pop(t)
                continue
            notes.append(f"{t}: there's no {t} pack in this plan, so its posts go to the others.")
            del mix[t]
    if not mix:
        sys.exit("None of their treatment types has a pack in this plan.")
    for t in mix:
        if mix[t] > len(packs[t]):
            notes.append(f"{t}: the pack has {len(packs[t])} posts, so it gives {len(packs[t])}.")
            mix[t] = len(packs[t])
    short = total - sum(mix.values())
    while short > 0:
        room = [t for t in mix if mix[t] < len(packs[t])]
        if not room:
            notes.append(f"Only {sum(mix.values())} posts in these packs, so the plan has {sum(mix.values())} posts.")
            break
        for t in sorted(room, key=lambda t: mix[t]):
            if short == 0:
                break
            mix[t] += 1
            short -= 1
    while short < 0:                                   # asked for more than there are days: trim the biggest
        t = max(mix, key=lambda t: mix[t])
        mix[t] -= 1
        short += 1
    return mix, notes


# ---------------------------------------------------------------------------
# Laying out the days
# ---------------------------------------------------------------------------

def film_slots(n_days, n_film):
    """Which days the posts that need filming go on: from the end, every other day, then any left from the end."""
    slots, i = [], n_days - 1
    while len(slots) < n_film and i >= 0:
        slots.append(i)
        i -= 2
    slots += [j for j in range(n_days - 1, -1, -1) if j not in slots][:n_film - len(slots)]
    return set(slots)


def lay_out(chosen, mix):
    """The chosen posts in day order."""
    n = sum(len(v) for v in chosen.values())
    film_days = film_slots(n, sum(1 for v in chosen.values() for p in v if p["film"]))
    queues = {"film": {t: [p for p in v if p["film"]] for t, v in chosen.items()},
              "ready": {t: [p for p in v if not p["film"]] for t, v in chosen.items()}}
    total = sum(mix.values())
    placed, counts = [], {t: 0 for t in chosen}
    # Each kind spread evenly over the posting days (posts are picked from anywhere in a pack, so pick order no
    # longer spaces them: carousels and quotes would otherwise bunch up at the end).
    ready_kinds = {}
    for v in queues["ready"].values():
        for p in v:
            ready_kinds[kind_of(p)] = ready_kinds.get(kind_of(p), 0) + 1
    n_ready = max(1, sum(ready_kinds.values()))
    done_kinds = {}
    for day in range(n):
        pool = queues["film" if day in film_days else "ready"]
        if not any(pool.values()):                       # nothing left of that sort: take from the other
            pool = queues["ready" if day in film_days else "film"]
        ready_day = sum(done_kinds.values())

        def score(t, k, post):
            s = mix[t] / total * (day + 1) - counts[t]   # how far behind its share this pack is
            s -= 0.05 * k                                # pick order only breaks a tie
            kd = kind_of(post)
            if kd in ready_kinds:                        # how far behind its even spread this kind is
                s += 1.2 * (ready_kinds[kd] / n_ready * (ready_day + 1) - done_kinds.get(kd, 0))
            if placed and placed[-1]["pack"] == t and len([x for x in pool if pool[x]]) > 1:
                s -= 3                                   # never the same pack two days running, if there's a choice
            kind = kind_of(post)
            recent = [kind_of(p) for p in placed[-4:]]
            if recent and recent[-1] == kind and kind != "reel":
                s -= 2.5                                 # no two of the same kind in a row (reels are most days)
            if kind == "talking head" and recent and recent[-1] == "talking head":
                s -= 5
            if kind == "carousel" and "carousel" in recent:
                s -= 2                                   # carousels at least 5 days apart
            if kind in ("quote", "meme") and kind in recent[-2:]:
                s -= 1.5
            if kind == "reel" and recent[-2:] == ["reel", "reel"]:
                s -= 1
            return s

        options = [(score(t, k, p), -k, t, p) for t, q in pool.items() for k, p in enumerate(q)]
        _, _, pack, post = max(options, key=lambda o: (o[0], o[1], -PACKS.index(o[2])))
        pool[pack].remove(post)
        placed.append(post)
        counts[pack] += 1
        if not post["film"]:
            done_kinds[kind_of(post)] = done_kinds.get(kind_of(post), 0) + 1
    return placed


# ---------------------------------------------------------------------------
# Their treatments
# ---------------------------------------------------------------------------

def read_treatments(text):
    """'Laser hair removal (Laser), HydraFacial (Skin)' -> [('Laser hair removal', 'Laser'), ...]."""
    out = []
    for part in re.findall(r"([^,()]+?)\s*\(([^)]+)\)", text or ""):
        name, kind = part[0].strip(), pack_name(part[1]) or part[1].strip()
        out.append((name, kind))
    return out


def suits(post, name):
    """Whether a post fits one of their treatments: 'SUITS: laser hair removal only' keeps it to that one
    ('SUITS: HydraFacial or SkinPen only' to either)."""
    text = post["suits"].lower()
    if not text or text.startswith("all") or "only" not in text:
        return True
    if "machine" in text:
        # "body contouring machines only": clinics name all sorts of devices (Frances, 2026-11-20: they might do "a
        # hell of a lot more" than any list), so any body treatment that isn't hands-on counts.
        hands_on = ("wood", "lymph", "massage", "drainage")
        return not any(w in name.lower() for w in hands_on)
    wanted = re.sub(r"\bonly\b.*", "", text).strip(" ,.")
    options = [o for o in re.split(r",| or | and ", wanted) if o.strip()]
    return any(all(w in name.lower() for w in re.findall(r"[a-z0-9]+", o)) for o in options)


def assign(placed, treatments, focus=""):
    """{post id: treatment name}: each type's treatments take turns, keeping posts off treatments they don't
    suit. A post that suits none of theirs gets its type's name and a note. Their focus treatment this month
    (Frances, 2026-11-20: "what's your focus treatment this month?") gets about twice the share of its type's
    posts, and first pick of that type's talking heads."""
    focus = (focus or "").strip().lower()
    by_type, used, last, notes, out = {}, {}, {}, [], {}
    for name, kind in treatments:
        by_type.setdefault(kind, []).append(name)
        used[name] = 0
    for post in placed:
        options = by_type.get(post["pack"], [])
        fits = [n for n in options if suits(post, n)]
        if not options:
            out[post["id"]] = post["pack"]
            continue
        if not fits:
            out[post["id"]] = post["pack"]
            notes.append(f"{post['id']} ({post['suits']}) doesn't suit any of their {post['pack'].lower()} "
                         f"treatments: swap it or skip it.")
            continue
        weight = lambda n: used[n] / 2 if focus and n.lower() == focus else used[n]
        if focus and kind_of(post) == "talking head" and any(n.lower() == focus for n in fits):
            pick = next(n for n in fits if n.lower() == focus)
        else:
            pick = min(fits, key=lambda n: (weight(n), n == last.get(post["pack"]), options.index(n)))
        out[post["id"]] = pick
        used[pick] += 1
        last[post["pack"]] = pick
    return out, notes


def read_promotions(text):
    """'Chemical peels=8 until 2026-12-15; Lip fillers=4 from 2026-12-01' -> [(name, count, start, end), ...]."""
    out = []
    for part in (text or "").split(";"):
        m = re.match(r"\s*(.+?)\s*=\s*(\d+)(.*)$", part)
        if not m:
            continue
        rest = m.group(3)
        start = re.search(r"from\s+(\d{4}-\d{2}-\d{2})", rest)
        end = re.search(r"until\s+(\d{4}-\d{2}-\d{2})", rest)
        out.append((m.group(1).strip(), int(m.group(2)),
                    datetime.date.fromisoformat(start.group(1)) if start else None,
                    datetime.date.fromisoformat(end.group(1)) if end else None))
    return out


def promote(by_date, treatments, promotions, kinds):
    """The posts that carry each offer (Frances, 2026-11-20: "how many posts for the month would you like to promote
    your promotion?"): as many as they asked for, inside the offer's dates, spread out. The offer's treatment gets
    posts of its own type moved over to it if it hasn't enough (only posts that suit it). {post id: name}, notes."""
    marked, notes = {}, []
    dates = sorted(by_date)
    for name, count, start, end in promotions:
        window = [d for d in dates if (not start or d >= start) and (not end or d <= end)]
        mine = [d for d in window if treatments[by_date[d]["id"]].lower() == name.lower()]
        kind = kinds.get(name.lower())       # its treatment type, from this month's treatments
        if kind is None:
            notes.append(f"{name} isn't in this month's treatments, so no posts are about it: add it (with its type) and make the month again.")
            continue
        if len(mine) < count and kind:
            others = [d for d in window if d not in mine and by_date[d]["pack"] == kind and suits(by_date[d], name)
                      and by_date[d]["id"] not in marked]
            # take from the other treatments of the same type, the busiest first, so none is left out
            share = {}
            for d in others:
                share.setdefault(treatments[by_date[d]["id"]], []).append(d)
            while len(mine) < count and any(share.values()):
                busiest = max((t for t in share if share[t]), key=lambda t: len(share[t]))
                d = share[busiest].pop(0)
                treatments[by_date[d]["id"]] = name
                mine.append(d)
            mine.sort()
        if len(mine) < count:
            notes.append(f"Only {len(mine)} posts in the offer's dates can be about {name}: the offer is on all of them.")
        step = len(mine) / count if count and len(mine) > count else 1
        chosen = [mine[int(i * step)] for i in range(min(count, len(mine)))]
        for d in chosen:
            marked[by_date[d]["id"]] = name
    return marked, notes


# ---------------------------------------------------------------------------
# One wording for each reel
# ---------------------------------------------------------------------------

def one_wording(lines, seed):
    """A post's lines with one of its two on-screen wordings (picked for this clinic, so clinics with the same
    post say it differently), under the usual REEL TEXT ON SCREEN label."""
    starts = [i for i, l in enumerate(lines) if re.match(r"^\s*REEL TEXT ON SCREEN( \(OTHER WORDING\))?:", l, re.I)]
    if len(starts) < 2:
        return lines
    blocks = []
    for i in starts:
        end = next((j for j in range(i + 1, len(lines)) if CAPS_LABEL.match(lines[j].strip())
                    or re.match(r"^\s*(Content type|Template|Example):", lines[j], re.I)), len(lines))
        blocks.append((i, end))
    keep = int(hashlib.sha256(seed.encode()).hexdigest(), 16) % 2
    out, skip = [], set()
    for n, (i, end) in enumerate(blocks[:2]):
        if n != keep:
            skip |= set(range(i, end))
    for i, l in enumerate(lines):
        if i in skip:
            continue
        out.append("REEL TEXT ON SCREEN:" + l.split(":", 1)[1] if i == blocks[keep][0] else l)
    return out


# ---------------------------------------------------------------------------

def clinic_name(folder):
    profile = os.path.join(os.path.dirname(os.path.abspath(folder)), "my-clinic.md")
    if os.path.exists(profile):
        found = re.search(r"\*\*Clinic name:\*\* (.+)", open(profile, encoding="utf-8").read())
        if found:
            return found.group(1).strip()
    return ""


def one_review(chosen, packs, mix):
    """Exactly one client review carousel in their 30 days (the Laser pack's notes: every pack has one, so a
    clinic mixing packs could get none or several). Extras swap for the next carousel down the same pack (or
    the next post); with none, the biggest pack's review carousel comes in for its lowest-placed carousel."""
    notes = []
    reviews = [(t, p) for t, ps in chosen.items() for p in ps if p["review"]]
    keep = min(reviews, key=lambda tp: (-mix[tp[0]], tp[1]["number"])) if reviews else None
    for t, p in reviews:
        if (t, p) == keep:
            continue
        used = {q["id"] for q in chosen[t]}
        spare = ([q for q in packs[t] if q["id"] not in used and kind_of(q) == "carousel" and not q["review"]]
                 or [q for q in packs[t] if q["id"] not in used and not q["review"]])
        if spare:
            chosen[t][chosen[t].index(p)] = spare[0]
            notes.append(f"{p['id']} (a second review carousel) swapped for {spare[0]['id']}.")
    if not reviews:
        for t in sorted(chosen, key=lambda t: -mix[t]):
            review = next((q for q in packs[t] if q["review"]), None)
            if not review:
                continue
            out = [q for q in chosen[t] if kind_of(q) == "carousel"] or chosen[t]
            chosen[t][chosen[t].index(out[-1])] = review
            chosen[t].sort(key=lambda q: q["number"])
            notes.append(f"{review['id']} (the review carousel) brought in for {out[-1]['id']}.")
            break
    return notes


# ---------------------------------------------------------------------------
# Picking for this clinic
# ---------------------------------------------------------------------------

def varied_pick(posts, n, seed, take=None):
    """n posts from a pack, picked for this clinic: the pack's own balance of kinds (a fair share of its reels,
    carousels, talking heads, quotes and memes), but different posts for different clinics. `take` ({kind:
    count}, from month_kinds) sets the kinds when the whole month has been balanced across packs."""
    if n >= len(posts):
        return sorted(posts, key=lambda p: p["number"])
    rng = random.Random(seed)
    by_kind = {}
    for p in posts:
        by_kind.setdefault(kind_of(p), []).append(p)
    if take is None:
        quota = {k: n * len(v) / len(posts) for k, v in by_kind.items()}
        take = {k: int(q) for k, q in quota.items()}
        for k in sorted(quota, key=lambda k: (quota[k] - take[k], rng.random()), reverse=True)[:n - sum(take.values())]:
            take[k] += 1
    take = {k: min(take.get(k, 0), len(v)) for k, v in by_kind.items()}
    chosen = []
    for k, v in by_kind.items():
        pool = list(v)
        rng.shuffle(pool)
        chosen += pool[:take[k]]
        by_kind[k] = pool[take[k]:]
    spare = [p for v in by_kind.values() for p in v]     # a kind ran short: top up from the rest
    rng.shuffle(spare)
    chosen += spare[:n - len(chosen)]
    return sorted(chosen, key=lambda p: p["number"])


def month_kinds(pools, needs, seed):
    """{pack: {kind: count}}: how many of each kind to take from each pack so the whole month keeps the plan's
    balance (a five-way mix of 6 posts a pack still gets its quotes: rounding pack by pack would lose them)."""
    rng = random.Random(seed)
    quota, take, room = {}, {}, {}
    for t, posts in pools.items():
        n = min(needs.get(t, 0), len(posts))
        kinds = {}
        for p in posts:
            kinds[kind_of(p)] = kinds.get(kind_of(p), 0) + 1
        quota[t] = {k: n * c / len(posts) for k, c in kinds.items()} if posts else {}
        take[t] = {k: int(q) for k, q in quota[t].items()}
        room[t] = {k: kinds[k] - take[t][k] for k in kinds}
        needs = dict(needs, **{t: n})
    month_q, month_t = {}, {}
    for t in pools:
        for k, q in quota[t].items():
            month_q[k] = month_q.get(k, 0) + q
            month_t[k] = month_t.get(k, 0) + take[t][k]
    left = {t: needs[t] - sum(take[t].values()) for t in pools}
    while any(v > 0 for v in left.values()):
        options = [(month_q[k] - month_t[k] + 0.3 * (quota[t][k] - take[t][k]) + rng.random() * 0.01, t, k)
                   for t in pools if left[t] > 0 for k in quota[t] if room[t][k] > 0]
        if not options:
            break
        _, t, k = max(options)
        take[t][k] += 1
        room[t][k] -= 1
        month_t[k] += 1
        left[t] -= 1
    return take


# ---------------------------------------------------------------------------
# The dates
# ---------------------------------------------------------------------------

def posting_dates(start, until, days_a_week=7, posts=0):
    """The days they post: every date from start to until on their posting days of the week (Monday to Friday
    for 5, Monday, Wednesday and Friday for 3...), or just posts of those, spread out evenly."""
    weekdays = set(WEEKDAYS.get(days_a_week, range(7)))
    dates = [start + datetime.timedelta(days=d) for d in range((until - start).days + 1)]
    dates = [d for d in dates if d.weekday() in weekdays]
    if posts and posts < len(dates):
        if posts == 1:
            return [dates[0]]
        step = (len(dates) - 1) / (posts - 1)
        dates = [dates[round(i * step)] for i in range(posts)]
    return dates


def date_of(text, first, last):
    """A post's DATE ('14 February', 'February 14th', '2027-02-14') as a date in the plan's dates, or None."""
    text = (text or "").lower()
    found = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
    if found:
        return datetime.date(*map(int, found.groups()))
    found = (re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s+([a-z]+)", text) or
             re.search(r"([a-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?", text))
    if not found:
        return None
    a, b = found.groups()
    day, month = (a, b) if a.isdigit() else (b, a)
    month = days.MONTHS.get(month)
    if not month:
        return None
    for year in (first.year, last.year):
        try:
            date = datetime.date(year, month, int(day))
        except ValueError:
            continue
        if first <= date <= last:
            return date
    return datetime.date(first.year, month, int(day)) if month else None


# ---------------------------------------------------------------------------
# What they've used, and what's left over
# ---------------------------------------------------------------------------

def read_used(path, label, but_not=""):
    """The posts of one plan a clinic has used, from used-posts.json ({plan: {month folder: [post ids]}}),
    leaving out the folder being made now (so planning the same month again gives the same posts back)."""
    if not path or not os.path.exists(path):
        return set()
    try:
        record = json.load(open(path, encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return set()
    return {pid for folder, ids in record.get(label, {}).items() if folder != but_not for pid in ids}


def record_used(path, folder, used):
    """Note which posts this month used ({plan label: [ids]}), replacing anything noted for this folder."""
    record = {}
    if os.path.exists(path):
        try:
            record = json.load(open(path, encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            record = {}
    for label in record:
        record[label].pop(folder, None)
    for label, ids in used.items():
        record.setdefault(label, {})[folder] = sorted(ids, key=lambda i: (i.split()[0], int(i.split()[-1])))
    record = {k: v for k, v in record.items() if v}
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=1)


def make(args):
    packs = read_packs(args.plan)
    if not packs:
        sys.exit("No packs found in this plan (posts headed like 'LASER 1').")
    label = plan_label(args.plan)
    folder = os.path.basename(os.path.normpath(args.out))
    start = datetime.date.fromisoformat(args.start)
    until = datetime.date.fromisoformat(args.until) if args.until else start + datetime.timedelta(days=LENGTH - 1)
    dates = posting_dates(start, until, args.days_a_week, args.posts)
    if not dates:
        sys.exit("No posting days between those dates.")
    first, last = dates[0], dates[-1]
    clinic = args.clinic or clinic_name(args.out)
    notes = []

    # Posts tied to a day outside their dates can't be used; nor can posts they've used before from this plan.
    used = read_used(args.record, label, folder)
    for t in list(packs):
        keep = []
        for p in packs[t]:
            p["source"] = label
            when = date_of(p["date_text"], first, last) if p["date_text"] else None
            if p["date_text"] and not (when and first <= when <= last):
                notes.append(f"{p['id']} is for {p['date_text']}, outside their dates: left out.")
                continue
            p["when"] = when
            if p["id"] in used:
                continue
            keep.append(p)
        packs[t] = keep

    mix = read_mix(args.mix) if args.mix else even_mix([pack_name(t) or t for t in args.types.split(",") if t.strip()],
                                                        len(dates))
    mix, more = settle(mix, {t: v for t, v in packs.items() if v}, len(dates))
    notes += more

    their = [(name, home(kind, packs)) for name, kind in read_treatments(args.treatments)]
    names = {}
    for name, kind in their:
        names.setdefault(kind, []).append(name)

    def fits(p):
        """Whether a post suits at least one of this month's treatments of its type."""
        return not names.get(p["pack"]) or any(suits(p, n) for n in names[p["pack"]])

    extra = {t: [] for t in mix}     # only this month's plan: an earlier plan's unused posts never come back
    chosen, goods, needs, pins = {}, {}, {}, {}
    for t, n in mix.items():
        if not n:
            continue
        own = n - len(extra[t])
        pins[t] = [p for p in packs[t] if p["when"]][:own]
        needs[t] = max(0, own - len(pins[t]))
        # Posts that suit this month's treatments first (a "facials only" post isn't picked for a SkinPen month
        # while there are others), topped up from the rest only if the pack runs short.
        goods[t] = [p for p in packs[t] if not p["when"] and fits(p)]
    kinds = month_kinds(goods, needs, f"{clinic}|{label}|kinds")
    for t, n in mix.items():
        if not n:
            continue
        pinned, need = pins[t], needs[t]
        pool = [p for p in packs[t] if not p["when"]]
        good = goods[t]
        picked = varied_pick(good, need, f"{clinic}|{label}|{t}", kinds.get(t))
        if len(picked) < need:
            picked += varied_pick([p for p in pool if p not in good], need - len(picked), f"{clinic}|{label}|{t}|more")
        chosen[t] = sorted(pinned + picked, key=lambda p: p["number"]) + extra[t]
    notes += one_review(chosen, packs, mix)

    # Dated posts on their days (the nearest posting day if it isn't one), the rest laid out around them.
    by_date = {}
    for t, ps in chosen.items():
        for p in [q for q in ps if q.get("when")]:
            spare = [d for d in dates if d not in by_date]
            # On its day, or the posting day before it (a Valentine's post goes out before Valentine's, not after).
            before = [d for d in spare if d <= p["when"]]
            day = max(before) if before else min(spare)
            by_date[day] = p
    rest = {t: [p for p in ps if not p.get("when")] for t, ps in chosen.items()}
    open_dates = [d for d in dates if d not in by_date]
    for day, post in zip(open_dates, lay_out(rest, mix)):
        by_date[day] = post
    placed = [by_date[d] for d in sorted(by_date)]
    treatments, more_notes = assign(placed, their, args.focus)
    notes += more_notes
    offers = read_promotions(args.promote)
    kinds = {n.lower(): k for n, k in their}
    on_offer, more_notes = promote(by_date, treatments, offers, kinds) if offers else ({}, [])
    notes += more_notes

    starter = label.startswith("STARTER PLAN")
    title = (f"STARTER PLAN: {len(placed)} DAYS" if starter else f"{label}: {len(placed)} POSTS")
    out = [f"{title}, {days.heading(first).upper()} TO {days.heading(last).upper()}",
           "YOU DON'T NEED TO READ THIS PLAN: CLAUDE PICKS THE POSTS FOR YOUR TREATMENTS.",
           "MIX: " + ", ".join(f"{t} {n}" for t, n in mix.items() if n), ""]
    treat_by_date, used_now = {}, {}
    for date in sorted(by_date):
        post = by_date[date]
        lines = one_wording(post["lines"], f"{clinic}|{post['id']}")
        body = [l for l in lines if not re.match(r"^\s*(Content type|JOB|NEEDS NEW FILMING|SUITS|DATE|MOMENT):", l, re.I)]
        source = "" if post["source"] == label else f" (unused, from {post['source'].title()})"
        out += [days.heading(date), f"Content type: {post['type']}", f"FROM: {post.get('orig_id', post['id'])}{source}"]
        out += [f"JOB: {post['job']}"] if post["job"] else []
        out += [f"NEEDS NEW FILMING: {'yes' if post['film'] else 'no'}",
                f"TREATMENT: {treatments[post['id']]}"]
        out += [f"PROMOTION: {on_offer[post['id']]} (their offer: promotions.md)"] if post["id"] in on_offer else []
        out += body + [""]
        treat_by_date[days.key(date)] = treatments[post["id"]]
        used_now.setdefault(post["source"], set()).add(post.get("orig_id", post["id"]))
    os.makedirs(args.out, exist_ok=True)
    expected = f"{first:%Y-%m}"
    if folder != expected:
        notes.append(f"The folder should be named by the month it starts in: {expected}.")
    with open(os.path.join(args.out, "plan.md"), "w", encoding="utf-8") as f:
        f.write(re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip() + "\n")
    with open(os.path.join(args.out, "treatments.json"), "w", encoding="utf-8") as f:
        json.dump(treat_by_date, f, indent=1)
    source_copy = os.path.join(args.out, "source-plan.md")
    if os.path.abspath(args.plan) != os.path.abspath(source_copy):
        shutil.copyfile(args.plan, source_copy)
    if args.record:
        record_used(args.record, folder, used_now)

    for date in sorted(by_date):
        post = by_date[date]
        print(f"{date:%a %d %b}  {post['id']:<28} {kind_of(post):<13} {'film' if post['film'] else 'ready':<6} "
              f"{treatments[post['id']]}")
    print("\nMIX: " + ", ".join(f"{t} {n}" for t, n in mix.items() if n))
    print(f"DATES: {len(placed)} posts, {days.heading(first)} to {days.heading(last)}")
    for name in sorted(set(on_offer.values())):
        on = sorted(d for d in by_date if on_offer.get(by_date[d]["id"]) == name)
        print(f"OFFER: {name} on {len(on)} posts: " + ", ".join(f"{d.day} {d:%b}" for d in on))
    film = [d for d in sorted(by_date) if by_date[d]["film"]]
    if film:
        print(f"FILM: {len(film)} posts need new filming, the first on {days.heading(film[0])}.")
    for note in notes:
        print("NOTE: " + note)
    print(f"SAVED: {os.path.join(args.out, 'plan.md')}, treatments.json and source-plan.md")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)
    s = sub.add_parser("split", help="the even mix, and a leaning mix for each type, for the clickable question")
    s.add_argument("--types", required=True, help='the treatment types this month is about, e.g. "Laser, Skin"')
    s.add_argument("--posts", type=int, default=LENGTH, help="how many posts this month (normally 30)")
    s.add_argument("plan", nargs="?", help="the plan, to check which packs it has")
    m = sub.add_parser("make", help="their dated plan")
    m.add_argument("plan", help="the plan: engine/included-plan.md (the Starter Plan) or this month's source-plan.md")
    m.add_argument("--start", required=True, help="the first day, e.g. 2027-02-01")
    m.add_argument("--until", default="", help="the last day it can run to (normally the month's end; the Starter Plan: 30 days)")
    m.add_argument("--days-a-week", type=int, default=7, choices=sorted(WEEKDAYS), help="how many days a week they post")
    m.add_argument("--posts", type=int, default=0, help="how many posts, spread over their posting days (normally one each)")
    m.add_argument("--mix", help='how many from each pack, e.g. "Laser=15, Skin=15"')
    m.add_argument("--types", default="", help="or just the treatment types, shared out evenly")
    m.add_argument("--treatments", default="", help='this month\'s treatments, e.g. "Laser hair removal (Laser), HydraFacial (Skin)"')
    m.add_argument("--focus", default="", help="their focus treatment this month (one of --treatments): more of its type's posts")
    m.add_argument("--promote", default="", help='their offers and how many posts carry each: "Chemical peels=8 until 2026-12-15" ("; " between offers)')
    m.add_argument("--record", default="", help="used-posts.json, where the posts they use are noted")
    m.add_argument("--clinic", default="", help="their clinic's name (normally read from their profile)")
    m.add_argument("--out", required=True, help='the folder, named by the month it starts in, e.g. "My Content/2027-02"')
    args = ap.parse_args()
    if args.command == "split":
        types = [pack_name(t) or t.strip() for t in args.types.split(",") if t.strip()]
        packs = read_packs(args.plan) if args.plan else None
        mix = even_mix(types, args.posts)
        if packs:
            mix, notes = settle(mix, packs, args.posts)
            for note in notes:
                print("NOTE: " + note)
            types = list(mix)
        print("MIX: " + ", ".join(f"{t}={n}" for t, n in mix.items()))
        if len(types) > 1:
            for t in types:
                lean = leaning(types, sum(mix.values()), t)
                print(f"MORE {t}: " + ", ".join(f"{x}={n}" for x, n in lean.items()))
    else:
        if not args.mix and not args.types:
            sys.exit("Give --mix or --types.")
        make(args)


if __name__ == "__main__":
    main()
