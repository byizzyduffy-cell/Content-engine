"""
New designs and features a student has unlocked with a code (locker.py unlock; part of the £27 content plan
subscription since 2026-11-20, never sold separately): new fonts, Canva post designs
and their recipes, and, as Frances makes them, pop-up styles and story templates.

They live in My Content/.extras/current, with the student's own things, so a free "update my engine" never
touches them. Each drop holds everything released so far, so the newest one is all that's kept. Its
extras.json says what's inside:

    {
      "label": "January 2027",
      "whats_new": "Three new fonts and two story templates",
      "fonts": [{"name": "Sunday Script", "file": "fonts/SundayScript.ttf", "scale": 1.2,
                 "kind": "handwriting"}],
      "library": [ { ...a post_library.json style..., "images": ["library/<id>-*.jpg"] } ],
      "recipes": "recipes.md",
      "categories": ["Story templates"]
    }

The engine reads them here: text_reel registers the fonts (usable by name everywhere), make_library adds the
designs to the post library, make-my-posts reads the recipes.

    PY engine/extras.py                  # what's unlocked
    PY engine/extras.py rebuild          # remake the post library so new designs show
"""

import tools  # noqa: F401  (first: emoji-safe output on Windows)
import glob
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CURRENT = os.path.join(os.path.dirname(HERE), "My Content", ".extras", "current")


def info():
    try:
        return json.load(open(os.path.join(CURRENT, "extras.json"), encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def fonts():
    """{font name: (font file, {}, {}, how big it looks)} in text_reel's FONTS shape."""
    out = {}
    for f in info().get("fonts", []):
        path = os.path.join(CURRENT, f.get("file", ""))
        if f.get("name") and os.path.isfile(path):
            out[f["name"]] = (path, f.get("main", {}), f.get("popup", {}), float(f.get("scale", 1.0)))
    return out


def library_styles():
    """The extras' post designs, with their sample pictures found inside the drop."""
    styles = []
    for style in info().get("library", []):
        style = dict(style)
        style["images"] = [os.path.join(CURRENT, p) for p in style.get("images", [])]
        style["extra"] = True
        styles.append(style)
    return styles


def categories():
    return list(info().get("categories", []))


def recipes():
    name = info().get("recipes")
    path = os.path.join(CURRENT, name) if name else ""
    return open(path, encoding="utf-8").read() if path and os.path.isfile(path) else ""


def main(argv):
    data = info()
    if not data:
        print("EXTRAS: none unlocked yet.")
        return
    print(f"EXTRAS: {data.get('label', 'unlocked')}: {data.get('whats_new', '')}")
    print(f"FONTS: {', '.join(fonts()) or 'none'}")
    print(f"DESIGNS: {', '.join(s.get('name', s.get('id', '?')) for s in library_styles()) or 'none'}")
    if argv[:1] == ["rebuild"]:
        months = sorted(glob.glob(os.path.join(os.path.dirname(HERE), "My Content", "20??-??", "posts.md")))
        target = [os.path.dirname(months[-1])] if months else []
        subprocess.run([sys.executable, os.path.join(HERE, "make_library.py")] + target, check=False)


if __name__ == "__main__":
    main(sys.argv[1:])
