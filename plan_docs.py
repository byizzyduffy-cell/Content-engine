"""
Turns content plans written as Google Docs ("Day One" to "Day Thirty", one doc per treatment type, downloaded as
Markdown) into the engine's pack layout ("LASER 1" to "LASER 30" with a label block), so starter_plan.py and
plan-my-month can pick from them. Frances's content plan chat writes them this way (the Starter Plan, 2026-11-20).

A doc looks like:

    # **Laser Hair Removal \\| 30-Day Evergreen Content Plan**
    # **Day One**
    **Content type: Talking-head reel**
    **REEL TEXT ON SCREEN**
    If you shaved last night...
    **SCRIPT**
    ...
    **CAPTION**
    ...

and comes out as:

    STARTER PLAN: LASER PACK
    FILM THESE EARLY: 1, 7, 13, 19, 25

    LASER 1
    Content type: Talking head reel
    NEEDS NEW FILMING: yes
    REEL TEXT ON SCREEN:
    If you shaved last night...

    PY engine/plan_docs.py <doc.md> [<doc.md> ...] --title "STARTER PLAN" --out content-plans/starter-plan.md
        [--suits content-plans/starter-plan/suits.json]
    PY engine/plan_docs.py <docs...> --title "JANUARY 2027 CONTENT PLAN" --out <file>

starter_plan.read_packs and locker.py plan use convert() by themselves when they're given docs like these, so
this is only needed to keep a tidy copy.
"""

import tools  # noqa: F401  (first: emoji-safe output on Windows)
import argparse
import json
import re
import sys

NUMBERS = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen "
    "seventeen eighteen nineteen".split())}
TENS = {"twenty": 20, "thirty": 30, "forty": 40}
DAY = re.compile(r"^\s*#*\s*\**\s*(?:Day|Post)\s+([A-Za-z]+(?:[- ][A-Za-z]+)?|\d{1,2})\s*\**\s*$", re.I)
BOLD_LINE = re.compile(r"^\s*\*\*(.+?)\*\*\s*$")
ESCAPE = re.compile(r"\\([\\`*_{}\[\]()#+\-.!|>~])")
INTRO = "YOU DON'T NEED TO READ THIS PLAN: CLAUDE PICKS THE POSTS FOR YOUR TREATMENTS."


def number(word):
    word = word.strip().lower()
    if word.isdigit():
        return int(word)
    parts = re.split(r"[- ]", word)
    if len(parts) == 2 and parts[0] in TENS and parts[1] in NUMBERS:
        return TENS[parts[0]] + NUMBERS[parts[1]]
    if word in TENS:
        return TENS[word]
    return NUMBERS.get(word)


def pack_of(title):
    """The pack a doc's title names: 'Laser Hair Removal | 30-Day...' -> 'Laser', 'PMU Brows' -> 'PMU'."""
    t = title.lower()
    for keys, pack in ((("tattoo",), "Tattoo removal"), (("pmu", "semi-permanent", "micropigment"), "PMU"),
                       (("lash", "brow"), "Lash and brow"), (("laser", "ipl"), "Laser"),
                       (("aesthetic", "injectable", "filler"), "Aesthetics"), (("body",), "Body"),
                       (("skin", "facial"), "Skin")):
        if any(k in t for k in keys):
            return pack
    return None


def plain(line):
    line = line.rstrip().replace("**", "")            # bold first, so an escaped blank (\_\_\_) survives
    return ESCAPE.sub(r"\1", line).strip()


def looks_like_docs(text):
    return sum(1 for l in text.splitlines() if DAY.match(l)) >= 3


def split_docs(text):
    """[(pack, [(day number, [lines])])] for every doc in the text (several docs can follow one another)."""
    docs, pack, days, day = [], None, [], None
    for raw in text.splitlines():
        line = raw.rstrip()
        m = DAY.match(line)
        if m:
            n = number(m.group(1))
            if n is not None:
                day = (n, [])
                days.append(day)
                continue
        heading = re.match(r"^\s*#\s+(.*)$", line)
        if heading and pack_of(plain(heading.group(1))) and "content plan" in plain(heading.group(1)).lower():
            if pack and days:
                docs.append((pack, days))
            pack, days, day = pack_of(plain(heading.group(1))), [], None
            continue
        if day is not None:
            day[1].append(line)
    if pack and days:
        docs.append((pack, days))
    return docs


def post_lines(lines):
    """A day's lines in the engine's layout: labels end with a colon, a talking head says it needs filming."""
    out, kind = [], ""
    for raw in lines:
        if not raw.strip() or re.fullmatch(r"\s*(-{3,}|\*{3,})\s*", raw):
            continue
        bold = BOLD_LINE.match(raw)
        text = plain(raw)
        if re.match(r"^\s*##\s", raw) and not bold:
            continue                                     # a doc's subtitle, like "Clinic Growth Collective"
        typ = re.match(r"^content type\s*:\s*(.+)$", text, re.I)
        if typ:
            kind = re.sub(r"talking[- ]head", "Talking head", typ.group(1).strip(), flags=re.I)
            out.append(f"Content type: {kind}")
            film = "yes" if re.search(r"talking head", kind, re.I) else "no"
            out.append(f"NEEDS NEW FILMING: {film}")
            continue
        if bold and len(text) <= 40 and (text.isupper() or re.fullmatch(r"slide\s+\d+", text, re.I)
                                         or text.endswith(":")):
            label = text.rstrip(":").strip()
            out.append(f"{label}:")
            continue
        if re.match(r"^(JOB|SUITS|DATE|MOMENT|NEEDS NEW FILMING)\s*:", text, re.I):
            if text.upper().startswith("NEEDS NEW FILMING"):
                out = [l for l in out if not l.startswith("NEEDS NEW FILMING:")]
            out.append(text)
            continue
        out.append(text)
    return out


def convert(text, title="STARTER PLAN", suits=None):
    """The docs in `text` as one plan in the engine's pack layout. `suits` ({pack: {number: "wood only"}}) adds a
    SUITS line to posts about one treatment, so the picker gives them to clinics that do it."""
    suits = suits or {}
    docs = split_docs(text)
    title = title.strip().upper()
    out = [title, INTRO, ""]
    for pack, days in docs:
        posts = [(n, post_lines(lines)) for n, lines in sorted(days, key=lambda d: d[0])]
        film = [str(n) for n, lines in posts if "NEEDS NEW FILMING: yes" in lines]
        out.append(f"{title}: {pack.upper()} PACK")
        if film:
            out.append("FILM THESE EARLY: " + ", ".join(film))
        out.append("")
        for n, lines in posts:
            out.append(f"{pack.upper()} {n}")
            fit = suits.get(pack, {}).get(str(n))
            if fit and not any(l.upper().startswith("SUITS:") for l in lines):
                at = next((i + 1 for i, l in enumerate(lines) if l.startswith("NEEDS NEW FILMING:")), 0)
                lines = lines[:at] + [f"SUITS: {fit}"] + lines[at:]
            out += lines
            out.append("")
    return "\n".join(out).rstrip() + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("docs", nargs="+")
    ap.add_argument("--title", default="STARTER PLAN")
    ap.add_argument("--out", required=True)
    ap.add_argument("--suits", help='a JSON file: {"Body": {"2": "wood only", ...}}')
    args = ap.parse_args()
    text = "\n\n".join(open(p, encoding="utf-8").read() for p in args.docs)
    if not looks_like_docs(text):
        sys.exit("PROBLEM: these don't look like Day One to Day Thirty plans.")
    suits = json.load(open(args.suits, encoding="utf-8")) if args.suits else None
    plan = convert(text, args.title, suits)
    open(args.out, "w", encoding="utf-8").write(plan)
    for pack, days in split_docs(text):
        nums = sorted(n for n, _ in days)
        gaps = sorted(set(range(1, max(nums) + 1)) - set(nums))
        print(f"PACK: {pack} {len(days)} posts" + (f" (missing {', '.join(map(str, gaps))})" if gaps else ""))
    print(f"SAVED: {args.out}")


if __name__ == "__main__":
    main()
