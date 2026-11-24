"""
Shares a month's treatment posts out between the treatments a clinic wants to
promote this month (Frances, 2026-10-10: most clinics do several treatments;
each month they say which to promote, e.g. HydraFacial and laser hair removal,
and their content is made for those).

Each month's plan is one doc for every clinic. Whole-clinic posts (quotes,
memes, the VIP list) are written once. Treatment posts are written once per
treatment type, each version starting with a line like "VERSION: Skin". Each
treatment uses the version for its type (treatment_menu.json: HydraFacial and
laser facials use the skin version, IPL hair removal the laser version), and
plan-my-month writes the post for that treatment by name. This picks which
treatment each treatment post is about:

- Shared out evenly between them (or, with --focus, a bigger share for one:
  about 4 in 10 with three treatments, and first pick of the talking heads).
- Never the same treatment on two treatment posts in a row (unless only one fits).
- Each treatment gets a mix of kinds of post (reels, carousels, talking heads).
- --not "5=Laser facial" keeps a treatment off a post whose idea doesn't fit it
  (a post about shaving only suits hair removal).
- A day with no version for any of them is reported as "none", so plan-my-month
  swaps or skips it.

    .venv/bin/python engine/share_out.py "My Content/2026-11/plan.md" \\
        --treatments "HydraFacial, Laser hair removal, Fat freezing" --out "My Content/2026-11/treatments.json"

A treatment not in the menu is given with its type: "Carbon facial=Skin". A
bare type ("Laser") still works. It prints the month (day, kind of post,
treatment) and the totals, and saves {day: treatment} as JSON with --out.
"""

import tools  # noqa: F401  (first: emoji-safe output on Windows)
import argparse
import json
import os
import re
import sys

MENU = os.path.join(os.path.dirname(os.path.abspath(__file__)), "treatment_menu.json")

# The plan's treatment versions (content-plans/plan-framework.md, section 8), and other ways of saying them.
VERSIONS = ["Laser", "Skin", "Aesthetics", "Body", "PMU", "Lash and brow", "Tattoo removal", "Hair", "Beauty salon",
            "Teeth whitening"]
OTHER_NAMES = {"aesthetic": "Aesthetics", "body contouring": "Body", "semi-permanent make-up": "PMU",
               "lash": "Lash and brow", "lashes": "Lash and brow", "brow": "Lash and brow", "brows": "Lash and brow",
               "lash and brow": "Lash and brow", "hair salon": "Hair", "teeth": "Teeth whitening",
               "tattoo": "Tattoo removal", "laser tattoo removal": "Tattoo removal"}
FOCUS_WEIGHT = 1.5      # the focus treatment's share, against 1 for each of the others

DATE = re.compile(r"^(?:#+\s*)?(?:Mon|Tues|Wednes|Thurs|Fri|Satur|Sun)day\s+(\d{1,2})(?:st|nd|rd|th)\b", re.I)


def version_name(text):
    """'laser' -> 'Laser', 'Lashes' -> 'Lash and brow'; None if it isn't one of the plan's versions."""
    text = text.strip().strip("*").strip().rstrip(":").strip()
    for name in VERSIONS:
        if text.lower() == name.lower():
            return name
    return OTHER_NAMES.get(text.lower())


def kind_of(content_type):
    """The kind of post, so each treatment gets a mix: talking head, carousel, post or reel."""
    t = content_type.lower()
    if "talking head" in t or "voiceover" in t:
        return "talking head"
    if "carousel" in t:
        return "carousel"
    if "static" in t or "quote" in t or ("post" in t and "reel" not in t):
        return "post"
    return "reel"


def read_plan(path):
    """Every treatment post in the plan: [{"day", "type", "versions"}], in date order."""
    days, current = [], None
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        date = DATE.match(line)
        if date:
            current = {"day": int(date.group(1)), "type": "", "versions": []}
            days.append(current)
            continue
        if not current:
            continue
        found = re.match(r"^\**\s*content type:?\**\s*:?\s*(.+)", line, re.I)
        if found and not current["type"]:
            current["type"] = found.group(1).strip("* ")
        found = re.match(r"^\**\s*version:?\**\s*:?\s*(.+)", line, re.I)
        if found:
            name = version_name(found.group(1))
            if name and name not in current["versions"]:
                current["versions"].append(name)
    return [d for d in days if d["versions"]]


def menu_version(name):
    """The plan version a treatment uses, from the treatment menu ("" if it isn't in the menu,
    None if the plans don't cover it yet)."""
    menu = json.load(open(MENU, encoding="utf-8"))
    for kind, items in menu.items():
        if kind == "about":
            continue
        for item in items:
            if item["name"].lower() == name.lower():
                return item["version"]
    return ""


def read_treatments(text):
    """'HydraFacial, Carbon facial=Skin, Laser' -> {name: version}, plus the ones the plans don't cover yet."""
    treatments, not_covered = {}, []
    for part in [p.strip() for p in text.split(",") if p.strip()]:
        name, _, given = part.partition("=")
        name = name.strip()
        version = version_name(given) if given else menu_version(name)
        if version == "" and version_name(name):         # a bare type, e.g. "Laser"
            name, version = version_name(name), version_name(name)
        if version is None:
            not_covered.append(name)
        elif not version:
            sys.exit(f"'{name}' isn't in the treatment menu. Give its type, e.g. \"{name}=Skin\" "
                     f"(types: {', '.join(VERSIONS)}).")
        else:
            treatments[name] = version
    return treatments, not_covered


def share_out(posts, treatments, focus=None, avoid=()):
    """{day: treatment or None}, sharing the treatment posts out between the clinic's treatments.
    treatments: {name: plan version}; avoid: {(day, name)} pairs that don't fit."""
    versions = treatments
    treatments = list(treatments)
    weights = {t: (FOCUS_WEIGHT if t == focus else 1.0) for t in treatments}
    total = sum(weights.values())
    counts = {t: 0 for t in treatments}
    kinds = {t: set() for t in treatments}
    last_used = {t: -1 for t in treatments}
    heads = {t: 0 for t in treatments}       # talking heads and voiceovers each has so far
    chosen, previous, n = {}, None, 0
    for post in posts:
        options = [t for t in treatments if versions[t] in post["versions"] and (post["day"], t) not in avoid]
        if not options:
            chosen[post["day"]] = None
            continue
        kind = kind_of(post["type"])

        def score(t):
            s = weights[t] / total * (n + 1) - counts[t]          # how far behind its fair share it is
            if t == previous and len(options) > 1:
                s -= 10                                           # never twice in a row
            if kind == "talking head" and t == focus and heads[t] <= max(heads[o] for o in options if o != t):
                s += 0.6                                          # the focus gets first pick of talking heads
            if kind not in kinds[t]:
                s += 0.3                                          # a mix of kinds of post for each treatment
            return (s, -last_used[t], -treatments.index(t))

        pick = max(options, key=score)
        chosen[post["day"]] = pick
        counts[pick] += 1
        kinds[pick].add(kind)
        heads[pick] += kind == "talking head"
        last_used[pick] = n
        previous, n = pick, n + 1
    return chosen


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plan", help="the month's plan, as pasted in (plan.md)")
    ap.add_argument("--treatments", required=True,
                    help='the treatments to promote this month, e.g. "HydraFacial, Laser hair removal"')
    ap.add_argument("--focus", help="one of them to get a bigger share (optional)")
    ap.add_argument("--not", dest="avoid", default="", help='posts a treatment doesn\'t fit, e.g. "5=Laser facial, 12=HydraFacial"')
    ap.add_argument("--out", help="save {day: treatment} here as JSON")
    args = ap.parse_args()

    treatments, not_covered = read_treatments(args.treatments)
    for name in not_covered:
        print(f"{name}: the plans don't cover it yet, so it gets no treatment posts this month.")
    if not treatments:
        sys.exit("None of these treatments are in the plans yet.")
    focus = next((t for t in treatments if args.focus and t.lower() == args.focus.strip().lower()), None)
    if args.focus and not focus:
        sys.exit(f"The focus '{args.focus}' isn't one of the treatments: {', '.join(treatments)}")
    avoid = set()
    for part in [p.strip() for p in args.avoid.split(",") if p.strip()]:
        day, _, name = part.partition("=")
        avoid.add((int(day), next((t for t in treatments if t.lower() == name.strip().lower()), name.strip())))

    posts = read_plan(args.plan)
    if not posts:
        print("This plan has no treatment versions (no VERSION lines): it's written for one treatment type.")
        return
    chosen = share_out(posts, treatments, focus, avoid)
    for post in posts:
        print(f"{post['day']:>2}  {kind_of(post['type']):<13} {chosen[post['day']] or 'none (no version for their treatments)'}")
    totals = {t: sum(1 for v in chosen.values() if v == t) for t in treatments}
    print("\nTreatment posts: " + ", ".join(f"{t} {c}" for t, c in totals.items())
          + (f" (focus: {focus})" if focus else ""))
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump({str(d): t for d, t in chosen.items()}, f, indent=1)


if __name__ == "__main__":
    main()
