"""
Gives clinics time to film (Frances, 2026-10-10): posts that need new filming
move to the end of the month (every other day, so they don't all come at once), and posts they can make from what they've already
got move to the front, so they can get going straight away. Each post that
needs filming gets a "Film by" date (two days before it goes out), so it's
flagged from the first day of the month.

What needs new filming:
- talking heads (a new script every month), posts that need them on camera,
  and any post whose plan says "Needs new filming" (a trend with a particular shot);
- with --no-footage (they haven't got clips yet), every post that needs clips too.
Anything else is ready now.

What never moves: rest days, posts with a Moment (Bonfire Night, Black Friday,
a launch day), posts that mention a day of the week ("Friday feeling", "this
weekend"), a countdown ("Christmas is 8 weeks away") or a one-day moment
(Halloween, Black Friday), and any day given with --fixed.

    .venv/bin/python engine/film_later.py "My Content/2026-11" [--no-footage] [--fixed 26,27]
        [--film 9] [--ready 2] [--apply]

Without --apply it only shows what would move. With --apply it rewrites
posts.md (and calendar.md and treatments.json, if they're there): the dates
stay where they are and the posts move between them. Make calendar.md first:
it says which posts need them on camera.

Days are known by their full date (days.py): a Starter Plan runs 30 days from
the day a clinic starts, often into the next month. --fixed, --film and --ready
take dates (2026-12-01) or, for a plan inside one month, day numbers (26,27).

A "Film by" date is never in the past (Sonnet test, 2026-10-14: a month planned
on the 14th said "film by the 13th"): when there isn't time, it's today.
--today sets the date to count from (for tests).
"""

import tools  # noqa: F401  (first: emoji-safe output on Windows)
import days as dates
import argparse
import datetime
import json
import os
import re
import sys

HEADING = re.compile(r"^## (\w+) (\d{1,2})(st|nd|rd|th) (\w+)\s*$", re.M)
DAY_WORDS = re.compile(r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday|weekend|tonight)s?\b", re.I)
# Words that tie a post to its date: a countdown ("8 weeks away") or a day-long moment.
DATE_WORDS = re.compile(r"\b\d+\s+(weeks?|days?|sleeps?)\s+(away|to go|left|until|till)\b|\b(halloween|bonfire night|"
                        r"black friday|cyber monday|valentine'?s|mother'?s day|father'?s day|christmas eve|boxing day|"
                        r"new year'?s eve|pancake day|easter sunday)\b", re.I)
WORD_FIELDS = ("Text on screen", "Text on screen (hook)", "Script", "Caption", "Meme text", "Quote text",
               "Post writing")
FILM_BY_DAYS = 2      # filmed this many days before it goes out, so there's time to make it


def suffix(n):
    return "th" if 11 <= n <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


def read_posts(path, start):
    """[(heading, day, body)] in date order, plus whatever comes before the first day. Each day is its date
    as text (2026-12-01), from its heading; start is the (year, month) the plan starts in."""
    text = open(path, encoding="utf-8").read()
    found = list(HEADING.finditer(text))
    top = text[:found[0].start()] if found else text
    days = []
    for i, m in enumerate(found):
        end = found[i + 1].start() if i + 1 < len(found) else len(text)
        days.append((m.group(0), dates.key(dates.heading_date(m.group(4), int(m.group(2)), start)), text[m.end():end]))
    return top, days


def fields(body):
    """{label: text} from a post's body."""
    out, label = {}, None
    for line in body.splitlines():
        m = re.match(r"\*\*(.+?):\*\*\s*(.*)", line)
        if m:
            label = m.group(1).strip()
            out[label] = m.group(2).strip()
        elif label and line.startswith(">"):
            out[label] = (out[label] + "\n" + line.lstrip("> ").rstrip()).strip()
    return out


def needs_of(calendar, day):
    """What the calendar says a day needs (Clips, Talking head, Canva...), or ''. calendar: {day: row}."""
    return calendar[day]["needs"] if day in calendar else ""


def filming_reason(f, kind_text, day, no_footage, film, ready):
    """Why this post needs new filming, or None if they can make it with what they've got."""
    if day in ready:
        return None
    if day in film:
        return "you asked"
    if "talking head" in kind_text:
        return "a new talking head"
    if "on camera" in kind_text:
        return "needs you on camera"
    if f.get("Needs new filming", "").lower().startswith("y"):
        return "the plan says it needs new filming"
    if no_footage and "clip" in kind_text:
        return "needs clips, and they haven't got any yet"
    return None


def sort_out(days, calendar, no_footage=False, fixed=(), film=(), ready=()):
    """Each day's kind (rest, fixed, film or ready), the reason, and whether it needs new filming
    (a fixed post can still need filming: it gets a "Film by" date but stays on its day)."""
    kinds = {}
    for _, day, body in days:
        f = fields(body)
        kind_text = (f.get("Content type", "") + " " + needs_of(calendar, day)).lower()
        words = " ".join(f.get(k, "") for k in WORD_FIELDS)
        reason = filming_reason(f, kind_text, day, no_footage, film, ready)
        kinds[day] = sort_one(f, day, words, fixed, reason) + (bool(reason) and "Content type" in f,)
    return kinds


def sort_one(f, day, words, fixed, reason):
    if "Content type" not in f:
        return ("rest", "")
    if day in fixed:
        return ("fixed", "you asked to keep it on its day")
    if f.get("Moment"):
        return ("fixed", "a moment on this date")
    tied = DAY_WORDS.search(words) or DATE_WORDS.search(words)
    if tied:
        return ("fixed", f'mentions "{tied.group(0)}"')
    return ("film", reason) if reason else ("ready", "")


def new_order(days, kinds):
    """{new day: old day}: film posts take the latest free days, every other one where there's room (so the
    end of the month isn't five talking heads in a row), and ready posts fill the rest from the start."""
    free = [d for _, d, _ in days if kinds[d][0] in ("ready", "film")]
    ready = [d for d in free if kinds[d][0] == "ready"]
    film = [d for d in free if kinds[d][0] == "film"]
    slots, i = [], len(free) - 1
    while len(slots) < len(film) and i >= 0:
        slots.append(i)
        i -= 2
    slots += [j for j in range(len(free) - 1, -1, -1) if j not in slots][:len(film) - len(slots)]
    slots = sorted(slots)
    order = {d: d for _, d, _ in days}
    for slot, old in zip(slots, film):
        order[free[slot]] = old
    for new, old in zip([d for j, d in enumerate(free) if j not in slots], ready):
        order[new] = old
    return order


def with_film_by(body, date):
    """The post's body with its "Film by" line (replacing an old one), straight after the content type."""
    body = re.sub(r"\n\*\*Film by:\*\*.*\n", "\n", body)
    when = dates.heading(date)
    return re.sub(r"(\*\*Content type:\*\*.*\n)", rf"\1\n**Film by:** {when}\n", body, count=1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder", help="the month's folder, e.g. My Content/2026-11")
    ap.add_argument("--no-footage", action="store_true", help="they haven't got clips yet, so clip posts need filming too")
    ap.add_argument("--fixed", default="", help="days that must stay where they are, e.g. 26,27 or 2026-12-01")
    ap.add_argument("--film", default="", help="days that need new filming, as well as the ones found")
    ap.add_argument("--ready", default="", help="days they can make now (e.g. a talking head they've already filmed)")
    ap.add_argument("--apply", action="store_true", help="rewrite the month (otherwise just show what would move)")
    ap.add_argument("--today", default="", help="the date to count from, e.g. 2026-10-14 (normally today)")
    args = ap.parse_args()

    folder = args.folder
    start = dates.start_of(folder)
    posts_path = os.path.join(folder, "posts.md")
    calendar_path = os.path.join(folder, "calendar.md")
    calendar = {r["key"]: r for r in dates.read_calendar(folder)} if os.path.exists(calendar_path) else {}
    if not calendar:
        print("NOTE: no calendar.md yet, so posts that need them on camera can't be spotted. Make the calendar first.")
    today = datetime.date.fromisoformat(args.today) if args.today else datetime.date.today()

    top, days = read_posts(posts_path, start)
    if not days:
        sys.exit("No days found in posts.md.")
    one_month = len({d[:7] for _, d, _ in days}) == 1

    def as_days(text):
        """'26,27' (day numbers, in the month of the post that has them) or '2026-12-01' -> {'2026-...'}."""
        out = set()
        for part in [p.strip() for p in text.split(",") if p.strip()]:
            out |= {part} if "-" in part else {d for _, d, _ in days if int(d[8:]) == int(part)}
        return out

    def name(day):          # how a day is shown: "26th", or "1st Dec" in a plan that runs on into the next month
        date = datetime.date.fromisoformat(day)
        return f"{date.day}{suffix(date.day)}" + ("" if one_month else f" {date:%b}")

    # The earliest a "Film by" date can be: the plan's first day, or today if the plan has already started.
    soonest = max(datetime.date.fromisoformat(days[0][1]), today)
    kinds = sort_out(days, calendar, args.no_footage, as_days(args.fixed), as_days(args.film), as_days(args.ready))
    order = new_order(days, kinds)

    for _, day, _ in days:
        kind, why, filming = kinds[order[day]]
        if kind == "rest":
            continue
        kind = "fixed, film" if kind == "fixed" and filming else kind
        moved = f"(was the {name(order[day])})" if order[day] != day else ""
        print(f"{name(day):>8}  {kind:<11} {moved:<20} {why}")
    film_days = sorted(d for d in order if kinds[order[d]][2])
    if film_days:
        first = max(datetime.date.fromisoformat(film_days[0]) - datetime.timedelta(days=FILM_BY_DAYS), soonest)
        when = f"{first:%A} {first.day}{suffix(first.day)}" if one_month else dates.heading(first)
        print(f"\n{len(film_days)} posts need new filming; the first is needed by {when}.")

    if not args.apply:
        return
    # Never move a post that's already been made: its reel or picture is named by its date.
    made = set()
    for sub in ("reels", "posts"):
        path = os.path.join(folder, sub)
        made |= {f[:10] for f in os.listdir(path) if re.match(r"\d{4}-\d{2}-\d{2}", f)} if os.path.isdir(path) else set()
    clash = sorted(d for d in order if order[d] != d and (d in made or order[d] in made))
    if clash:
        sys.exit(f"Not moved: days {', '.join(clash)} already have a finished reel or post. Use --fixed for them.")

    bodies = {day: body for _, day, body in days}
    out = [top]
    for heading, day, _ in days:
        body = bodies[order[day]]
        if kinds[order[day]][2]:
            date = max(datetime.date.fromisoformat(day) - datetime.timedelta(days=FILM_BY_DAYS), soonest)
            body = with_film_by(body, date)
        else:
            body = re.sub(r"\n\*\*Film by:\*\*.*\n", "\n", body)
        out.append(heading + body)
    open(posts_path, "w", encoding="utf-8").write("".join(out))

    if calendar:   # move each row's post, keeping its date (rows are matched to lines in order, as days.py reads them)
        lines, rows = open(calendar_path, encoding="utf-8").read().splitlines(), list(calendar.values())
        cells_of = {r["key"]: None for r in rows}
        found = []
        for i, line in enumerate(lines):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) == 4 and dates.CELL.match(cells[0]):
                found.append((i, cells))
        for (i, cells), row in zip(found, rows):
            cells_of[row["key"]] = cells
        for (i, cells), row in zip(found, rows):
            old = cells_of.get(order.get(row["key"], row["key"])) or cells
            lines[i] = "| " + " | ".join([cells[0]] + old[1:]) + " |"
        open(calendar_path, "w", encoding="utf-8").write("\n".join(lines) + "\n")

    treatments_path = os.path.join(folder, "treatments.json")
    if os.path.exists(treatments_path):
        # Kept by date (the Starter Plan) or, in older months, by day number.
        old = json.load(open(treatments_path, encoding="utf-8"))
        by_date = any("-" in k for k in old)
        k = (lambda d: d) if by_date else (lambda d: str(int(d[8:])))
        new = {k(d): old[k(order[d])] for d in order if k(order[d]) in old}
        json.dump(new, open(treatments_path, "w", encoding="utf-8"), indent=1)
    print("Moved.")


if __name__ == "__main__":
    main()
