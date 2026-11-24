"""
Where a student is up to, in plain lines, so Claude can pick up where they left off ("carry on where I left
off", "what was I doing?", or after the Claude app was closed and opened again).

    PY engine/status.py [--month 2026-10]

It reads their profile and their newest planned month (or the one given) and says what's made, what's
waiting for filming or for them, and the next thing to do. Claude reads it and tells them in a sentence or two.
"""

import tools  # noqa: F401  (first: emoji-safe output on Windows)
import argparse
import datetime
import glob
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
CONTENT = os.path.join(os.path.dirname(HERE), "My Content")


def months():
    return sorted(os.path.basename(os.path.dirname(p)) for p in glob.glob(os.path.join(CONTENT, "20??-??", "posts.md")))


def days_made(folder, sub):
    path = os.path.join(folder, sub)
    if not os.path.isdir(path):
        return set()
    return {f[:10] for f in os.listdir(path) if re.match(r"\d{4}-\d{2}-\d{2}", f)}


REMINDERS = os.path.join(CONTENT, "reminders.json")


def read_json(path):
    try:
        return json.load(open(path, encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def newest_drop(today):
    """The newest monthly plan Frances has dropped by today, and the day it dropped: each plan (and each month's
    new designs) drops on the membership's drop_day of the month before it (the January plan on 23 December)."""
    drop_day = int(read_json(os.path.join(HERE, "membership.json")).get("drop_day", 23) or 23)
    year, month = (today.year, today.month)
    if today.day >= drop_day:                                # this month's drop has happened: it's next month's plan
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
        dropped = datetime.date(today.year, today.month, min(drop_day, 28))
    else:                                                    # it's this month's plan, dropped last month
        last = (today.replace(day=1) - datetime.timedelta(days=1))
        dropped = datetime.date(last.year, last.month, min(drop_day, 28))
    return datetime.date(year, month, 1), dropped


def before_first_plan(month_start):
    """Whether that month comes before the first monthly plan (membership.json's first_monthly_plan: January 2027,
    Frances, 2026-11-23: there's no December plan, the Starter Plan's 30 days carry everyone to January's drop)."""
    first = str(read_json(os.path.join(HERE, "membership.json")).get("first_monthly_plan") or "")
    return bool(first) and f"{month_start:%Y-%m}" < first


def has_plan_for(month_start):
    """Whether they've pasted the plan for that month (a source-plan.md whose first line names it)."""
    name = f"{month_start:%B %Y}".upper()
    for path in glob.glob(os.path.join(CONTENT, "20??-??", "source-plan.md")):
        try:
            first = next((l for l in open(path, encoding="utf-8") if l.strip()), "")
        except OSError:
            continue
        if name in first.upper():
            return True
    return False


def unlocked(kind):
    """{month: ...} they've unlocked with a code (locker.py notes it), for "plans" or "extras"."""
    return read_json(os.path.join(CONTENT, "unlocked.json")).get(kind, {})


def subscribed(kind, today):
    """Whether they look like a member: they've unlocked that kind with a code for this month, last month or
    next month (codes only come to members)."""
    near = {f"{d:%Y-%m}" for d in (today.replace(day=1) - datetime.timedelta(days=1), today,
                                   (today.replace(day=28) + datetime.timedelta(days=4)))}
    return bool(near & set(unlocked(kind)))


def plan_promo(today, rows):
    """From the 20th (promo_day) to the day before the drop (the 23rd), anyone who isn't signed up hears once that
    next month's content plan goes live on the 23rd and can be joined now (Frances, 2026-11-20:
    "on the 20th, you need to start promoting them on the engine")."""
    m = read_json(os.path.join(HERE, "membership.json"))
    promo_day, drop_day = int(m.get("promo_day", 20) or 20), int(m.get("drop_day", 23) or 23)
    if not promo_day <= today.day < drop_day:
        return
    coming = (today.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
    if before_first_plan(coming):
        return
    key = f"{coming:%Y-%m}"
    if key in read_json(REMINDERS).get("promoted", {}):
        return
    if rows and (today - rows[0]["date"]).days < 7:
        return                                               # their first week on a new plan: no selling yet
    # Only the £27 content plan subscription is promoted (Frances, 2026-11-20: the design features are part of it now).
    if subscribed("plans", today):
        return
    drop = datetime.date(today.year, today.month, drop_day)
    print(f"PROMO: the {coming:%B} content plan goes live on {drop:%A} {drop.day} {drop:%B}, and they can join now. They "
          f"aren't on the content plan subscription (membership.json: name, price, what_they_get, checkout_link). Once, "
          f"after helping with what they came for, warm and short: tell them it's dropping on the "
          f"{drop.day}{'rd' if drop.day in (3, 23) else 'th'} and ask if they'd like to join, with clickable options; on a "
          f"yes give them its checkout link. Then run status.py --promoted {key}, so it's once a month.")


def plan_offer(today, rows):
    """From the day a new plan drops, if they haven't got it, Claude asks them once whether they'd like the
    monthly plans (Frances, 2026-11-18: "can you prompt them? And if they say yeah, you send the checkout link")."""
    month_start, dropped = newest_drop(today)
    key = f"{month_start:%Y-%m}"
    if before_first_plan(month_start):
        return
    if has_plan_for(month_start):
        return
    if not rows:
        return                                               # nothing planned yet: a new buyer starts with the Starter
                                                             # Plan, so they're never asked for a code on day one
    if dropped < rows[0]["date"]:
        return                                               # it dropped before they started this plan (a new buyer
                                                             # on their Starter Plan is first offered the next drop)
    if rows and rows[-1]["date"] >= month_start + datetime.timedelta(days=27):
        return                                               # their current plan already covers that month
    if key in read_json(REMINDERS).get("asked", {}):
        return
    print(f"OFFER: the {month_start:%B} plan's code went up in the members' classroom on {dropped:%A} {dropped.day} "
          f"{dropped:%B}, and they haven't unlocked it. Once, after helping with what they came for: ask if they've got "
          f"their {month_start:%B} code. If they have, they type it in (use-my-code). If not, offer the monthly plans in "
          f"the words of engine/membership.json, and on a yes give them its checkout_link. Then run status.py "
          f"--asked {key}, so it's once a drop.")


def plan_name(folder, rows):
    """'Your Starter Plan' or 'Your December plan', from the month's plan.md (or its dates)."""
    try:
        first = open(os.path.join(folder, "plan.md"), encoding="utf-8").readline().upper()
    except OSError:
        first = ""
    if "STARTER PLAN" in first:
        return "Your Starter Plan"
    when = rows[len(rows) // 2]["date"] if rows else None
    return f"Your {when:%B} plan" if when else "Your plan"


def card():
    """The side panel's card (the Clinic Content Engine app, engine/app): where they're up to, in a student's
    words, as JSON. Never says file names or commands."""
    out = {"clinic": "", "title": "", "lines": [], "next": None}
    profile = os.path.join(CONTENT, "my-clinic.md")
    if not os.path.exists(profile):
        out.update(title="Welcome", lines=["Let's get your first 30 days planned. It only takes a few minutes."],
                   next={"label": "Plan my month", "phrase": "plan my month"})
        return out
    name = re.search(r"\*\*Clinic name:\*\* (.+)", open(profile, encoding="utf-8").read())
    out["clinic"] = name.group(1).strip() if name else ""
    planned = months()
    if not planned:
        out.update(title="Ready when you are", lines=["Your Starter Plan is waiting: 30 days of posts for your treatments."],
                   next={"label": "Plan my month", "phrase": "plan my month"})
        return out
    folder = os.path.join(CONTENT, planned[-1])
    import make_planner
    rows = make_planner.read_calendar(folder) if os.path.exists(os.path.join(folder, "calendar.md")) else []
    posts = open(os.path.join(folder, "posts.md"), encoding="utf-8").read()
    reels, pictures = days_made(folder, "reels"), days_made(folder, "posts")
    today = datetime.date.today()
    todo = {"reel": 0, "talking": 0, "canva": 0, "meme": 0}
    made = total = 0
    film = []
    for row in rows:
        kind = (row["type"] + " " + row["needs"]).lower()
        if "rest" in kind:
            continue
        total += 1
        if row["key"] in reels or row["key"] in pictures:
            made += 1
            continue
        fields = make_planner.post_fields(posts, row["date"])
        if fields.get("Film by"):
            film.append(fields["Film by"])
        if "meme" in kind:
            todo["meme"] += 1
        elif "talking head" in kind or "voiceover" in kind or fields.get("Script"):
            todo["talking"] += 1
        elif "canva" in kind or "carousel" in kind or "quote" in kind or "static" in kind:
            todo["canva"] += 1
        else:
            todo["reel"] += 1
    out["title"] = plan_name(folder, rows)
    if not rows:                     # posts written but no calendar yet: planning was stopped partway
        out["lines"] = ["Your month is only partly planned. Say plan my month to finish it."]
        out["next"] = {"label": "Plan my month", "phrase": "plan my month"}
        return out
    out["made"], out["total"] = made, total
    if rows:
        first, end = rows[0]["date"], rows[-1]["date"]
        out["dates"] = f"{first.day} {first:%B} to {end.day} {end:%B}"
        out["lines"].append(f"{first.day} {first:%b} to {end.day} {end:%b}")
        # The week strip: this week while the plan runs, else its first or last week.
        pick = min(max(today, first), end)
        monday = pick - datetime.timedelta(days=pick.weekday())
        by_date = {r["date"]: r for r in rows}
        week = []
        for i in range(7):
            day = monday + datetime.timedelta(days=i)
            row = by_date.get(day)
            kind, state = "", "none"
            if row and "rest" not in (row["type"] + row["needs"]).lower():
                t = (row["type"] + " " + row["needs"]).lower()
                kind = ("Talking" if "talking head" in t else "Voice" if "voiceover" in t else
                        "Carousel" if "carousel" in t else "Quote" if "quote" in t else "Meme" if "meme" in t else
                        "Post" if "static" in t or "canva" in t else "Reel")
                if row["key"] in reels or row["key"] in pictures:
                    state = "ready"
                else:
                    fields = make_planner.post_fields(posts, row["date"])
                    state = "film" if kind in ("Talking", "Voice") or fields.get("Film by") else "todo"
            week.append({"letter": "MTWTFSS"[i], "day": day.day, "kind": kind, "state": state,
                         "today": day == today})
        out["week"] = week
    out["lines"].append(f"{made} of {total} posts ready")
    ready_to_post = len([r for r in rows if r["key"] in make_planner.signed_off(folder)])
    out["fully_ready"] = ready_to_post
    if ready_to_post:
        out["lines"].append(f"{ready_to_post} of {total} fully ready to post")
    if film:
        out["lines"].append(f"Film your talking heads by {film[0]}")
    if rows and rows[-1]["date"] < today:
        out["lines"].append("This plan has finished: your next one comes with a code")
        out["next"] = {"label": "I've got my code", "phrase": "I've got my code"}
        return out
    steps = [("reel", "Make my reels"), ("talking", "Make my talking heads"), ("canva", "Make my posts"),
             ("meme", "Make my memes")]
    for key, label in steps:
        if todo[key]:
            out["next"] = {"label": label, "phrase": label.lower()}
            break
    else:
        out["next"] = {"label": "Show me my planner", "phrase": "show me my planner"}
        out["lines"].append("Everything's made: post it from your planner")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--month", help="the month to look at, e.g. 2026-10 (normally their newest)")
    ap.add_argument("--asked", metavar="YYYY-MM", help="note that they've been asked about this month's plan (so it's once a drop)")
    ap.add_argument("--promoted", metavar="YYYY-MM", help="note that they've heard about next month's drop (so it's once a month)")
    ap.add_argument("--card", action="store_true", help="the side panel's card, as JSON")
    args = ap.parse_args()
    if args.card:
        print(json.dumps(card(), ensure_ascii=False))
        return
    if args.asked or args.promoted:
        record = read_json(REMINDERS)
        which, month = ("asked", args.asked) if args.asked else ("promoted", args.promoted)
        record.setdefault(which, {})[month] = datetime.date.today().isoformat()
        with open(REMINDERS, "w", encoding="utf-8") as f:
            json.dump(record, f, indent=1)
        print(f"NOTED: {which} about the {month} drop.")
        return

    profile = os.path.join(CONTENT, "my-clinic.md")
    if not os.path.exists(profile):
        print("PROFILE: none yet. They haven't planned a month. Next: plan my month.")
        return
    name = re.search(r"\*\*Clinic name:\*\* (.+)", open(profile, encoding="utf-8").read())
    print(f"PROFILE: {name.group(1).strip() if name else 'saved'}")
    planned = months()
    if not planned:
        print("MONTH: none planned yet. Next: plan my month.")
        return
    month = args.month or planned[-1]
    folder = os.path.join(CONTENT, month)
    print(f"MONTH: {month} (months planned: {', '.join(planned)})")

    import make_planner   # the planner's own reader, so this agrees with what the planner shows
    rows = make_planner.read_calendar(folder) if os.path.exists(os.path.join(folder, "calendar.md")) else []
    posts = open(os.path.join(folder, "posts.md"), encoding="utf-8").read()
    reels, pictures = days_made(folder, "reels"), days_made(folder, "posts")
    today = datetime.date.today()
    # Days by their number, or "20 Nov" when the plan runs on into the next month (a Starter Plan).
    one_month = len({(r["date"].year, r["date"].month) for r in rows}) <= 1
    named = {r["key"]: str(r["day"]) if one_month else f"{r['day']} {r['date']:%b}" for r in rows}
    waiting = {"reel from clips": [], "talking head or voiceover": [], "Canva post": [], "meme": [], "other": []}
    made, film_by = [], []
    for row in rows:
        day, kind = row["key"], (row["type"] + " " + row["needs"]).lower()
        if "rest" in kind:
            continue
        if day in reels or day in pictures:
            made.append(day)
            continue
        fields = make_planner.post_fields(posts, row["date"])
        if fields.get("Film by"):
            film_by.append((day, fields["Film by"]))
        if "meme" in kind:
            waiting["meme"].append(day)
        elif "talking head" in kind or "voiceover" in kind or fields.get("Script"):
            waiting["talking head or voiceover"].append(day)
        elif "canva" in kind or "carousel" in kind or "quote" in kind or "static" in kind:
            waiting["Canva post"].append(day)
        elif "reel" in kind or "clip" in kind:
            waiting["reel from clips"].append(day)
        else:
            waiting["other"].append(day)
    total = sum(1 for r in rows if "rest" not in (r["type"] + r["needs"]).lower())
    print(f"POSTS: {total} in the {'month' if one_month else 'plan'}, {len(made)} made" + (f" (days {', '.join(named[d] for d in sorted(made))})" if made else ""))
    for kind, days in waiting.items():
        if days:
            print(f"WAITING ({kind}): days {', '.join(named[d] for d in days)}")
    if film_by:
        print("FILM BY: " + "; ".join(f"day {named[d]}: {when}" for d, when in film_by))

    # The picks pages: saved picks mean they've chosen, and the next step is making.
    extras = []
    if os.path.exists(os.path.join(folder, "reels.json")):
        plan = json.load(open(os.path.join(folder, "reels.json"), encoding="utf-8"))
        own = sum(1 for r in plan.get("reels", []) if r.get("look"))
        extras.append(f"reels.json has {len(plan.get('reels', []))} reels, {own} with their own picked look")
    clips = os.path.join(folder, "clips")
    if os.path.isdir(clips):
        extras.append(f"{len([f for f in os.listdir(clips) if f.lower().endswith(('.mov', '.mp4', '.m4v'))])} clips saved")
    heads = sorted(glob.glob(os.path.join(folder, "talking-heads", "*", "raw.*")))
    for raw in heads:
        work = os.path.dirname(raw)
        stage = ("finished" if glob.glob(os.path.join(work, "finished.mp4")) else
                 "look picked, ready to finish" if os.path.exists(os.path.join(work, "picks.json")) else
                 "cut, waiting for its look" if os.path.exists(os.path.join(work, "tidy.mp4")) else
                 "listened to, waiting to be cut" if os.path.exists(os.path.join(work, "transcript.txt")) else "copied in")
        extras.append(f"talking head {os.path.basename(work)}: {stage}")
    for line in extras:
        print("ALSO: " + line)

    # Every month (Frances, 2026-11-18): remind them to paste their new plan as this one runs out, and if they
    # haven't got one, tell them about the monthly plans (engine/membership.json).
    if rows:
        end = rows[-1]["date"]
        left = (end - today).days
        print(f"PLAN ENDS: {end:%A} {end.day} {end:%B}" + (f" (in {left} days)" if left > 0 else " (today)" if left == 0
                                                          else f" ({-left} days ago)"))
        if left <= 5:
            print("REMIND: their plan " + ("has run out" if left < 0 else "is nearly finished") + ". Once, warmly: "
                  "each month's content plan code goes up in the members' classroom on the 23rd, and they type it in "
                  "here. If they're not on the monthly plans, tell them about them in the words of engine/membership.json.")
    if rows and rows[-1]["date"] < today:
        print("NOTE: this month is over. If they've a new plan code, next is to type it in (use-my-code), then plan my month.")
    plan_promo(today, rows)
    plan_offer(today, rows)
    if waiting["reel from clips"]:
        nxt = "make my reels"
    elif waiting["talking head or voiceover"]:
        nxt = "film and send their talking heads, then make my talking heads (or voiceovers)"
    elif waiting["Canva post"]:
        nxt = "make my posts"
    elif waiting["meme"]:
        nxt = "make my memes"
    else:
        nxt = "everything's made: send it to their phone and post it from the planner"
    print(f"NEXT: {nxt}")


if __name__ == "__main__":
    main()
