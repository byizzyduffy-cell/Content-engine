"""
The dates of a plan's days (2026-10-17, for the Starter Plan).

A month's folder is named by the month it starts in (My Content/2026-11), but a plan can run on into the
next month: the Starter Plan is 30 days from the day a clinic starts, say 20 November to 19 December. So
every day is known by its full date, and the engine's tools look a day up by its date, not its day number
(a plan starting on 1 February even has two 1sts).

- calendar.md rows give the day as "Thu 20th". The month is the folder's, moving on to the next month when
  the day number drops ("Tue 1st" after "Mon 30th"). A month name in the cell wins ("Tue 1st Dec").
- posts.md headings already say the month ("## Tuesday 1st December"); the year is the folder's, or the
  next one when the month comes before the folder's month (a plan from December into January).
- Finished reels and posts are already named by their date (reels/2026-12-01.mp4), and pages link to a day
  as #day-2026-12-01.
"""

import calendar
import datetime
import os
import re

MONTHS = {name.lower(): n for n, name in enumerate(calendar.month_name) if name}
MONTHS.update({name.lower(): n for n, name in enumerate(calendar.month_abbr) if name})
MONTHS["sept"] = 9
CELL = re.compile(r"^[A-Z][a-z]{2}\w* (\d{1,2})(?:st|nd|rd|th)?(?: ([A-Za-z]+))?")


def start_of(folder):
    """(year, month) the folder's plan starts in, from its name: My Content/2026-11 -> (2026, 11)."""
    year, month = (int(x) for x in os.path.basename(os.path.normpath(folder)).split("-")[:2])
    return year, month


def suffix(n):
    return "th" if 11 <= n <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


def heading(date):
    """The day as posts.md writes it: 'Tuesday 1st December'."""
    return f"{date:%A} {date.day}{suffix(date.day)} {date:%B}"


def short(date):
    """The day as calendar.md writes it: 'Tue 1st'."""
    return f"{date:%a} {date.day}{suffix(date.day)}"


def key(date):
    """How files and links name a day: '2026-12-01'."""
    return date.isoformat()


def year_for(month, start):
    """The year a month falls in, for a plan that starts in start (year, month)."""
    return start[0] + 1 if month < start[1] else start[0]


def read_calendar(folder):
    """Every row of the folder's calendar.md: [{day, date, key, label, type, what, needs}], in order."""
    start = start_of(folder)
    year, month, last = start[0], start[1], 0
    rows = []
    for line in open(os.path.join(folder, "calendar.md"), encoding="utf-8"):
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        found = CELL.match(cells[0]) if len(cells) == 4 else None
        if not found:
            continue
        day, named = int(found.group(1)), (found.group(2) or "").lower()
        if named in MONTHS:
            month = MONTHS[named]
            year = year_for(month, start)
        elif day < last:                       # into the next month
            year, month = (year + 1, 1) if month == 12 else (year, month + 1)
        last = day
        date = datetime.date(year, month, day)
        rows.append({"day": day, "date": date, "key": key(date), "label": cells[0], "type": cells[1],
                     "what": cells[2].strip('"'), "needs": cells[3]})
    return rows


def section(posts, date):
    """A day's section of posts.md (its heading to the next), or ''. Older months' headings without the
    month still match on the day number."""
    found = (re.search(rf"## \w+ {date.day}(st|nd|rd|th) {date:%B}\b.*?(?=\n## |\Z)", posts, re.S)
             or re.search(rf"## \w+ {date.day}(st|nd|rd|th)[ \t]*\n.*?(?=\n## |\Z)", posts, re.S))
    return found.group(0) if found else ""


def heading_date(month_name, day, start):
    """The date of a posts.md heading ('December', 1), for a plan that starts in start (year, month)."""
    month = MONTHS.get(month_name.lower(), start[1])
    return datetime.date(year_for(month, start), month, day)


def month_names(rows):
    """'November' for a plan inside one month, 'November and December' when it runs on into the next."""
    names = list(dict.fromkeys(f"{row['date']:%B}" for row in rows))
    return " and ".join(names)
