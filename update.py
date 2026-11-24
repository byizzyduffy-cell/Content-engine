"""
Puts a new version of the engine in place, keeping everything the student has made (Frances's promise in
lesson 3.5: "everything you've made stays exactly as it is: your look, your brand and your months").

    PY engine/update.py check                  # is there a newer version online? (Frances's Dropbox)
    PY engine/update.py online                 # fetch the newest version from there and put it in place
    PY engine/update.py find                   # the newest engine download in Downloads, and both versions
    PY engine/update.py apply "<zip or folder>"

Online updates (Frances, 2026-10-29: students "just say update and it updates without me having to get them
to download the new engine every time"): engine/update_links.json holds two share links from her Dropbox, one
to a small file with the newest version number and one to the update itself. When she adds new designs she
makes a new update (make_package.py --update) and drops it into the same Dropbox folder in place of the old
one; Dropbox keeps the links, so every engine finds it.

Slim updates (2026-11-02, so a whole membership updating on one day stays inside Dropbox's daily limit for
shared links): the update itself is the engine, about 4 MB. The engine's sample pages (the lookbooks' videos
and the post library's pictures, about 67 MB) are a separate file in the same Dropbox folder, rebuilt only
when they change, with its own link ("samples"). Every update carries engine/samples-manifest.json, a list of
every sample file and its fingerprint; after updating, the engine checks its own files against it and fetches
the samples file only when something is missing or out of date, so a student who skipped an update still
catches up.

    PY engine/update.py samples                # check the sample pages, and fetch them if they're out of date

Every download has engine/version.txt (written by make_package.py). "apply" first copies the old engine
(engine/, .claude/, the notes) into My Content/.engine-backups/<date>/, so nothing is ever lost, then copies
the new engine over. My Content stays as it is, apart from the engine's own sample pages (the lookbooks and
post library), which are refreshed. The engine's Python, video tools and speech model are only replaced
when the download brings them (the all-in-one Mac download) and theirs are older or missing.
"""

import tools  # noqa: F401  (first: emoji-safe output on Windows)
import datetime
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TOP = "Clinic Content Engine"
SAMPLE_PAGES = ("lookbook", "reel-lookbook", "library")       # in My Content, but made by the engine
NOTES = ("CLAUDE.md", "START HERE.txt")


LINKS = os.path.join(HERE, "update_links.json")


def links():
    try:
        return json.load(open(LINKS, encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def direct(url):
    """A Dropbox share link that downloads the file itself, instead of opening Dropbox's page."""
    if "dropbox.com" in url:
        url = re.sub(r"([?&])dl=0", r"\1dl=1", url)
        if not re.search(r"[?&]dl=1", url):
            url += ("&" if "?" in url else "?") + "dl=1"
    return url


def fetch(url, target):
    """Downloads with curl (built into Macs and Windows 10 and later, and it trusts the computer's own
    security certificates), or Python's own downloader when curl isn't there."""
    curl = shutil.which("curl")
    if curl and subprocess.run([curl, "-fsSL", "--retry", "2", "-o", target, direct(url)]).returncode == 0:
        return
    import urllib.request
    urllib.request.urlretrieve(direct(url), target)


def latest():
    """The newest version number online, or None when online updates aren't set up or can't be reached."""
    link = links().get("version")
    if not link:
        return None
    target = tempfile.mktemp(suffix=".txt")
    try:
        fetch(link, target)
        text = open(target, encoding="utf-8").read().strip()
        return text if re.match(r"\d{4}-\d{2}-\d{2}", text) else None     # not Dropbox's error page
    except Exception:
        return None
    finally:
        if os.path.exists(target):
            os.remove(target)


def newer(online, theirs):
    if not online or online == theirs:
        return False
    return not re.match(r"\d{4}-\d{2}-\d{2}", theirs) or online >= theirs


def check():
    theirs, online = version(ROOT), latest()
    print(f"THEIRS: {theirs}")
    if online is None:
        print("ONLINE: can't check (no internet, or online updates aren't set up): look in Downloads instead.")
        return
    print(f"ONLINE: {online}")
    print("NEWER: yes" if newer(online, theirs) else "NEWER: no, they're up to date")


def online_update():
    link, online = links().get("update"), latest()
    if not link or online is None:
        raise SystemExit("The online update can't be reached. Check the internet, or look in Downloads instead.")
    if not newer(online, version(ROOT)):
        print(f"UP TO DATE: {version(ROOT)}")
        return
    scratch = tempfile.mkdtemp(prefix="engine-download-")
    try:
        zip_path = os.path.join(scratch, "update.zip")
        print("DOWNLOADING: the newest engine (a minute or two)")
        fetch(link, zip_path)
        if not zipfile.is_zipfile(zip_path):
            raise SystemExit("The download didn't come through properly. Try again in a minute.")
        apply(zip_path)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    refresh_samples()


def fingerprint(path):
    import hashlib
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def stale_samples():
    """The sample files (paths under the engine's folder) that are missing or out of date, from the list in
    engine/samples-manifest.json. None when the engine has no list."""
    path = os.path.join(HERE, "samples-manifest.json")
    if not os.path.exists(path):
        return None
    files = json.load(open(path, encoding="utf-8"))["files"]
    stale = []
    for name, want in files.items():
        mine = os.path.join(ROOT, *name.split("/"))
        if not os.path.exists(mine) or fingerprint(mine) != want:
            stale.append(name)
    return stale


def refresh_samples():
    """Fetches the sample pages when any are missing or out of date (see the top of this file)."""
    stale = stale_samples()
    if stale is None:
        return
    if not stale:
        print("SAMPLES: up to date")
        return
    link = links().get("samples")
    if not link:
        print(f"SAMPLES: {len(stale)} sample files are out of date, and there's no link to fetch them from.")
        return
    scratch = tempfile.mkdtemp(prefix="engine-samples-")
    try:
        zip_path = os.path.join(scratch, "samples.zip")
        changed = f"{len(stale)} file has" if len(stale) == 1 else f"{len(stale)} files have"
        print(f"DOWNLOADING: the newest sample pages ({changed} changed; a minute or two)")
        fetch(link, zip_path)
        if not zipfile.is_zipfile(zip_path):
            print("SAMPLES: the download didn't come through properly. Say \"update my engine\" again later.")
            return
        with zipfile.ZipFile(zip_path) as z:
            extract(z, scratch)
        new = os.path.join(scratch, TOP) if os.path.isdir(os.path.join(scratch, TOP)) else scratch
        for page in SAMPLE_PAGES:
            source = os.path.join(new, "My Content", page)
            if os.path.isdir(source):
                copy_tree(source, os.path.join(ROOT, "My Content", page))
        left = stale_samples() or []
        print("SAMPLES: refreshed" if not left else f"SAMPLES: refreshed, but {len(left)} files still differ")
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def version(folder):
    path = os.path.join(folder, "engine", "version.txt")
    return open(path, encoding="utf-8").read().strip() if os.path.exists(path) else "older than version numbers"


def downloads():
    home = os.path.expanduser("~")
    for folder in (os.path.join(home, "Downloads"), os.path.join(home, "OneDrive", "Downloads")):
        if os.path.isdir(folder):
            return folder
    return os.path.join(home, "Downloads")


def candidates():
    """Engine downloads in Downloads, newest first: zips and unzipped folders with an engine inside."""
    found = []
    for path in glob.glob(os.path.join(downloads(), "Clinic Content Engine*")):
        if os.path.abspath(path) == ROOT or "samples" in os.path.basename(path).lower():
            continue
        if path.lower().endswith(".zip") or os.path.isdir(os.path.join(path, "engine")) \
                or os.path.isdir(os.path.join(path, TOP, "engine")):
            found.append(path)
    return sorted(found, key=lambda p: max(os.stat(p).st_mtime, os.stat(p).st_ctime), reverse=True)


def unpacked(path, scratch):
    """The folder holding the new engine (it has engine/ inside)."""
    if path.lower().endswith(".zip"):
        with zipfile.ZipFile(path) as z:
            extract(z, scratch)
        path = scratch
    for folder in (path, os.path.join(path, TOP)):
        if os.path.isdir(os.path.join(folder, "engine")):
            return folder
    raise SystemExit("That download doesn't have an engine inside. Check it's the Clinic Content Engine download.")


def extract(z, scratch):
    """Unzip like the Mac's own unzipping does: Python's extractall drops the "can run" mark on the engine's
    tools and turns the shortcuts inside .venv (python -> python3.14) into plain text files, so the
    updated engine's Python wouldn't start (found 2026-10-16)."""
    import stat
    for info in z.infolist():
        mode = info.external_attr >> 16
        target = os.path.join(scratch, info.filename)
        if stat.S_ISLNK(mode):
            os.makedirs(os.path.dirname(target), exist_ok=True)
            if os.path.lexists(target):
                os.remove(target)
            os.symlink(z.read(info).decode("utf-8"), target)
            continue
        z.extract(info, scratch)
        if mode & 0o777 and not info.is_dir():
            os.chmod(target, mode & 0o777)


def copy_tree(source, target, skip=()):
    for base, dirs, names in os.walk(source):
        rel = os.path.relpath(base, source)
        dirs[:] = [d for d in dirs if os.path.normpath(os.path.join(rel, d)) not in skip]
        os.makedirs(os.path.join(target, rel), exist_ok=True)
        for name in names:
            if os.path.normpath(os.path.join(rel, name)) in skip:
                continue
            shutil.copy2(os.path.join(base, name), os.path.join(target, rel, name))


def backup():
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H.%M")
    keep = os.path.join(ROOT, "My Content", ".engine-backups", stamp)
    n = 2
    while os.path.exists(keep):        # two updates in the same minute: never mix one backup into another
        keep = os.path.join(ROOT, "My Content", ".engine-backups", f"{stamp} ({n})")
        n += 1
    os.makedirs(keep)
    big = {os.path.join("models"), os.path.join("bin")}        # too big to copy, and only replaced when newer
    copy_tree(HERE, os.path.join(keep, "engine"), skip=big)
    if os.path.isdir(os.path.join(ROOT, ".claude")):
        copy_tree(os.path.join(ROOT, ".claude"), os.path.join(keep, ".claude"))
    for name in NOTES:
        if os.path.exists(os.path.join(ROOT, name)):
            shutil.copy2(os.path.join(ROOT, name), keep)
    return keep


def apply(path):
    scratch = tempfile.mkdtemp(prefix="engine-update-")
    try:
        new = unpacked(path, scratch)
        old_version, new_version = version(ROOT), version(new)
        kept = backup()
        print(f"BACKUP: the old engine is kept in {kept}")
        # The engine itself. Their speech model and video tools stay unless the download brings new ones.
        skip = set()
        if not os.path.isdir(os.path.join(new, "engine", "bin")):
            skip.add("bin")
        copy_tree(os.path.join(new, "engine"), HERE, skip=skip)
        if os.path.isdir(os.path.join(new, ".claude")):
            copy_tree(os.path.join(new, ".claude"), os.path.join(ROOT, ".claude"))
        for name in NOTES:
            if os.path.exists(os.path.join(new, name)):
                shutil.copy2(os.path.join(new, name), ROOT)
        # The engine's own sample pages in My Content (never their months, profile, brand or photos).
        for page in SAMPLE_PAGES:
            source = os.path.join(new, "My Content", page)
            if os.path.isdir(source):
                copy_tree(source, os.path.join(ROOT, "My Content", page))
        # The engine's Python: replaced only when the download packs one in (the all-in-one Mac download).
        if os.path.isdir(os.path.join(new, ".venv")):
            old_venv = os.path.join(ROOT, ".venv")
            if os.path.isdir(old_venv):
                shutil.move(old_venv, os.path.join(kept, ".venv"))
            shutil.copytree(os.path.join(new, ".venv"), old_venv, symlinks=True)
            print("PYTHON: replaced with the one in the download")
        print(f"UPDATED: {old_version} -> {new_version}")
        print("NEXT: run check_setup.py --test with the engine's Python, then rebuild this month's planner and library.")
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def main(argv):
    if argv[:1] == ["check"]:
        check()
    elif argv[:1] == ["online"]:
        online_update()
    elif argv[:1] == ["find"]:
        print(f"THEIRS: {version(ROOT)}")
        found = candidates()
        if not found:
            print("NONE: no engine download in Downloads.")
        for path in found[:3]:
            if path.lower().endswith(".zip"):
                with zipfile.ZipFile(path) as z:
                    name = next((n for n in z.namelist() if n.endswith("engine/version.txt")), None)
                    v = z.read(name).decode().strip() if name else "no version number"
            else:
                v = version(path if os.path.isdir(os.path.join(path, "engine")) else os.path.join(path, TOP))
            print(f"FOUND: {path} (version {v})")
    elif argv[:1] == ["apply"] and len(argv) == 2:
        apply(argv[1])
        refresh_samples()
    elif argv[:1] == ["samples"]:
        refresh_samples()
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
