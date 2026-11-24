"""
Frances's two monthly codes (2026-11-20): one for the content plan (the £27 a month subscription) and one for the
design features (new fonts, pop-up styles, Canva and story templates; never promoted or sold in the engine). Fixes stay
free ("update my engine").

Each month Frances gives Claude the five niche plans (or the extras), Claude locks them with that month's code
into a file in her Dropbox (the same file each month, so its link never changes), and she posts the code in
the right members' classroom. A student types the code into their engine; it unlocks whichever it opens:

    PY engine/locker.py unlock <code>
        a plan:   saves it as My Content/<YYYY-MM>/source-plan.md, ready for plan my month
        extras:   puts them in My Content/.extras/current (with the student's own things, which updates never touch)

Frances's side (run in her working copy):

    PY engine/locker.py newcode --month 2027-01
    PY engine/locker.py plan laser.md skin.md aesthetics.md body.md pmu.md --month 2027-01 [--code ...]
        (packs, or the Google Docs downloaded as Markdown, "Day One" to "Day Thirty": plan_docs.py converts them)
    PY engine/locker.py extras "<folder with extras.json>" --month 2027-01 [--code ...]
    PY engine/locker.py list [--kind plans|extras]

A locked file keeps the last few months (3 plans, 2 extras drops), each opened only by its own code, so someone
a month behind can still unlock theirs. Codes look like JAN-ROSE-PEARL-4821 (spaces, dashes and capitals don't
matter when typing). Each month's code is noted in My Content/codes.md on Frances's computer, never online.

The lock uses only Python's own tools (so it works on every Mac and Windows engine): the code is stretched with
PBKDF2 (200,000 rounds), the contents are scrambled with a SHA-256 key stream, and a check (HMAC) means a wrong
code opens nothing rather than something broken.
"""

import tools  # noqa: F401  (first: emoji-safe output on Windows)
import argparse
import base64
import datetime
import hashlib
import hmac
import io
import json
import os
import re
import secrets
import shutil
import sys
import tempfile
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CONTENT = os.path.join(ROOT, "My Content")
EXTRAS = os.path.join(CONTENT, ".extras")
DROPBOX = os.path.expanduser("~/Dropbox/Clinic Content Engine updates")
BUNDLES = {"plans": "Clinic Content Engine plans.locked", "extras": "Clinic Content Engine extras.locked"}
KEEP = {"plans": 3, "extras": 2}
ROUNDS = 200_000
WORDS = ("ROSE PEARL SILK GLOW DEW BLOOM IVORY HONEY SATIN VELVET LINEN CREAM MAPLE CORAL AMBER OLIVE SAGE "
         "MINT PLUM FIG PEACH LEMON CHERRY CLOUD STAR MOON SUN BREEZE OCEAN RIVER MEADOW PETAL LOTUS LILY "
         "DAISY IRIS POPPY TULIP ORCHID JASMINE WILLOW CEDAR BIRCH ASPEN HAZEL ALMOND CASHMERE MARBLE "
         "CRYSTAL OPAL JADE RUBY TOPAZ GARNET COPPER BRONZE GOLD SILVER LAVENDER VANILLA COCOA TOFFEE "
         "CARAMEL BERRY MANGO KIWI CITRUS NECTAR SORBET MOCHA LATTE BISCUIT CANDLE LANTERN HARBOUR "
         "ISLAND COAST SHORE DUNE PEBBLE STONE FEATHER RIBBON VELLUM PARADE SONNET MELODY CHORUS "
         "SPARK EMBER FROST MIST RAIN SNOW SPRING SUMMER AUTUMN WINTER MORNING EVENING HALO HAVEN "
         "BLOSSOM ORBIT COMET").split()


# ---------------------------------------------------------------------------
# The lock
# ---------------------------------------------------------------------------

def plain(code):
    """A code as typed, made comparable: 'jan rose-pearl 4821' -> 'JANROSEPEARL4821'."""
    return re.sub(r"[^A-Z0-9]", "", (code or "").upper())


def keys(code, salt):
    key = hashlib.pbkdf2_hmac("sha256", plain(code).encode(), salt, ROUNDS, dklen=64)
    return key[:32], key[32:]


def scramble(key, nonce, data):
    """XOR with a SHA-256 key stream (the same call locks and unlocks)."""
    out, chunk = bytearray(), 1 << 20
    counter = 0
    for start in range(0, len(data), chunk):
        piece = data[start:start + chunk]
        blocks = (len(piece) + 31) // 32
        stream = b"".join(hashlib.sha256(key + nonce + (counter + i).to_bytes(8, "big")).digest() for i in range(blocks))
        counter += blocks
        out += (int.from_bytes(piece, "big") ^ int.from_bytes(stream[:len(piece)], "big")).to_bytes(len(piece), "big")
    return bytes(out)


def seal(code, data):
    salt, nonce = os.urandom(16), os.urandom(16)
    enc, mac = keys(code, salt)
    sealed = scramble(enc, nonce, data)
    tag = hmac.new(mac, salt + nonce + sealed, hashlib.sha256).digest()
    b = lambda x: base64.b64encode(x).decode()
    return {"salt": b(salt), "nonce": b(nonce), "tag": b(tag), "data": b(sealed)}


def open_entry(code, entry):
    """The entry's contents if the code is right, otherwise None."""
    d = lambda k: base64.b64decode(entry[k])
    salt, nonce, tag, sealed = d("salt"), d("nonce"), d("tag"), d("data")
    enc, mac = keys(code, salt)
    if not hmac.compare_digest(tag, hmac.new(mac, salt + nonce + sealed, hashlib.sha256).digest()):
        return None
    return scramble(enc, nonce, sealed)


def new_code(month):
    year, mon = (int(x) for x in month.split("-"))
    words = secrets.SystemRandom().sample(WORDS, 2)
    return f"{datetime.date(year, mon, 1):%b}".upper() + f"-{words[0]}-{words[1]}-{secrets.randbelow(10000):04d}"


# ---------------------------------------------------------------------------
# Locked files
# ---------------------------------------------------------------------------

def read_bundle(path):
    try:
        return json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError):
        return {"engine": "Clinic Content Engine", "entries": []}


def add_entry(kind, month, label, code, data, bundle_path):
    bundle = read_bundle(bundle_path)
    bundle["kind"] = kind
    entries = [e for e in bundle.get("entries", []) if e.get("month") != month]
    entries.append(dict(month=month, label=label, locked=datetime.date.today().isoformat(), **seal(code, data)))
    bundle["entries"] = sorted(entries, key=lambda e: e["month"])[-KEEP[kind]:]
    os.makedirs(os.path.dirname(os.path.abspath(bundle_path)), exist_ok=True)
    tmp = bundle_path + ".writing"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(bundle, f)
    os.replace(tmp, bundle_path)                       # written whole, then swapped in, so the link never serves half
    return bundle


def note_code(kind, month, label, code):
    """Frances's own record of the codes (My Content is never uploaded)."""
    path = os.path.join(CONTENT, "codes.md")
    lines = open(path, encoding="utf-8").read().splitlines() if os.path.exists(path) else [
        "# Subscription codes", "", "Each month's code, to post in the members' classroom. Never put this file online.", ""]
    stamp = f"- **{label}** ({'content plan' if kind == 'plans' else 'engine extras'}): `{code}`"
    lines = [l for l in lines if not l.startswith(f"- **{label}** ({'content plan' if kind == 'plans' else 'engine extras'})")]
    lines.append(stamp)
    os.makedirs(CONTENT, exist_ok=True)
    open(path, "w", encoding="utf-8").write("\n".join(lines) + "\n")


def zip_bytes(files):
    """{name in zip: path or bytes} -> zip bytes."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, src in files.items():
            if isinstance(src, (bytes, str)) and not (isinstance(src, str) and os.path.isfile(src)):
                z.writestr(name, src)
            else:
                z.write(src, name)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Frances's side
# ---------------------------------------------------------------------------

def month_label(month):
    year, mon = (int(x) for x in month.split("-"))
    return f"{datetime.date(year, mon, 1):%B %Y}"


def lock_plan(args):
    import starter_plan
    label = month_label(args.month)
    title = f"{label.upper()} CONTENT PLAN"
    text = ""
    for path in args.files:
        part = open(path, encoding="utf-8").read().strip()
        text += part + "\n\n"
    import plan_docs
    if plan_docs.looks_like_docs(text):            # Google Docs ("Day One"...): into packs ("LASER 1"...)
        text = plan_docs.convert(text, title)
    first = next((l for l in text.splitlines() if l.strip()), "")
    if title not in first.upper():
        text = f"{title}\nYOU DON'T NEED TO READ THIS PLAN: CLAUDE PICKS THE POSTS FOR YOUR TREATMENTS.\n\n" + text
    with tempfile.TemporaryDirectory() as scratch:
        check = os.path.join(scratch, "plan.md")
        open(check, "w", encoding="utf-8").write(text)
        packs = starter_plan.read_packs(check)
    if not packs:
        sys.exit("PROBLEM: no packs found (each post needs a heading like 'LASER 1').")
    for name, posts in packs.items():
        kinds = {}
        for p in posts:
            kinds[starter_plan.kind_of(p)] = kinds.get(starter_plan.kind_of(p), 0) + 1
        print(f"PACK: {name} {len(posts)} posts ({', '.join(f'{k} {n}' for k, n in sorted(kinds.items()))})")
    missing = [p for p in ("Laser", "Skin", "Aesthetics", "Body", "PMU") if p not in packs]
    if missing:
        print("CHECK: no pack for " + ", ".join(missing))
    code = args.code or new_code(args.month)
    bundle = args.bundle or os.path.join(DROPBOX, BUNDLES["plans"])
    kept = add_entry("plans", args.month, label, code, zip_bytes({"plan.md": text.encode()}), bundle)
    note_code("plans", args.month, label, code)
    print(f"LOCKED: the {label} content plan, in {bundle}")
    print("HOLDS: " + ", ".join(e["label"] for e in kept["entries"]))
    print(f"CODE: {code}")


def lock_extras(args):
    folder = args.folder
    info = os.path.join(folder, "extras.json")
    if not os.path.exists(info):
        sys.exit("PROBLEM: the extras folder needs an extras.json (what's in it and what's new).")
    files = {}
    for base, _dirs, names in os.walk(folder):
        for name in names:
            path = os.path.join(base, name)
            files[os.path.relpath(path, folder).replace(os.sep, "/")] = path
    label = month_label(args.month)
    code = args.code or new_code(args.month)
    bundle = args.bundle or os.path.join(DROPBOX, BUNDLES["extras"])
    kept = add_entry("extras", args.month, label, code, zip_bytes(files), bundle)
    note_code("extras", args.month, label, code)
    print(f"LOCKED: the {label} engine extras ({len(files)} files), in {bundle}")
    print("HOLDS: " + ", ".join(e["label"] for e in kept["entries"]))
    print(f"CODE: {code}")


# ---------------------------------------------------------------------------
# The student's side
# ---------------------------------------------------------------------------

def fetch_bundle(kind, scratch, local=None):
    """The locked file: a path given for testing, or downloaded from its link (engine/update_links.json)."""
    if local:
        return local if os.path.exists(local) else None
    import update
    url = update.links().get(kind)
    if not url:
        return None
    target = os.path.join(scratch, BUNDLES[kind])
    try:
        update.fetch(url, target)
    except Exception:
        return None
    return target if os.path.exists(target) else None


def remember(kind, month, label):
    path = os.path.join(CONTENT, "unlocked.json")
    try:
        record = json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError):
        record = {}
    record.setdefault(kind, {})[month] = {"label": label, "unlocked": datetime.date.today().isoformat()}
    os.makedirs(CONTENT, exist_ok=True)
    json.dump(record, open(path, "w", encoding="utf-8"), indent=1)


def unlock(args):
    if len(plain(args.code)) < 8:
        sys.exit("CODE: that doesn't look like a code (they look like JAN-ROSE-PEARL-4821).")
    with tempfile.TemporaryDirectory() as scratch:
        tried = []
        for kind in ("plans", "extras"):
            bundle = fetch_bundle(kind, scratch, getattr(args, kind))
            if not bundle:
                continue
            tried.append(kind)
            for entry in reversed(read_bundle(bundle).get("entries", [])):
                data = open_entry(args.code, entry)
                if data is None:
                    continue
                z = zipfile.ZipFile(io.BytesIO(data))
                if kind == "plans":
                    folder = os.path.join(CONTENT, entry["month"])
                    os.makedirs(folder, exist_ok=True)
                    target = os.path.join(folder, "source-plan.md")
                    with open(target, "wb") as f:
                        f.write(z.read("plan.md"))
                    remember("plans", entry["month"], entry["label"])
                    print(f"UNLOCKED PLAN: {entry['label']}")
                    print(f"SAVED: {target}")
                    print("NEXT: plan my month, Step 2s, with this source-plan.md.")
                else:
                    new = os.path.join(EXTRAS, "new")
                    shutil.rmtree(new, ignore_errors=True)
                    z.extractall(new)
                    current = os.path.join(EXTRAS, "current")
                    old = os.path.join(EXTRAS, "previous")
                    shutil.rmtree(old, ignore_errors=True)
                    if os.path.exists(current):
                        os.replace(current, old)
                    os.replace(new, current)
                    remember("extras", entry["month"], entry["label"])
                    try:
                        info = json.load(open(os.path.join(current, "extras.json"), encoding="utf-8"))
                    except (OSError, ValueError):
                        info = {}
                    print(f"UNLOCKED EXTRAS: {entry['label']}")
                    print(f"WHATS NEW: {info.get('whats_new', 'new extras for your engine')}")
                    print("NEXT: remake their lookbooks and post library so the new extras show (extras.py rebuild).")
                return
        if not tried:
            print("CODE: can't check codes right now (no internet, or the code files aren't set up yet). Try again later.")
        else:
            print("CODE: not recognised. Check it's this month's code from the members' classroom, typed as it's written.")


def list_bundles(args):
    for kind in ([args.kind] if args.kind else ["plans", "extras"]):
        path = os.path.join(DROPBOX, BUNDLES[kind])
        bundle = read_bundle(path)
        months = ", ".join(f"{e['label']} (locked {e.get('locked', '?')})" for e in bundle.get("entries", [])) or "nothing yet"
        print(f"{kind.upper()}: {months}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)
    u = sub.add_parser("unlock", help="a student's code: unlocks this month's plan or extras")
    u.add_argument("code")
    u.add_argument("--plans", help="a locked plans file to use instead of the online one (testing)")
    u.add_argument("--extras", help="a locked extras file to use instead of the online one (testing)")
    n = sub.add_parser("newcode", help="a fresh code for a month")
    n.add_argument("--month", required=True)
    p = sub.add_parser("plan", help="lock a month's content plan (the five niche plans)")
    p.add_argument("files", nargs="+")
    p.add_argument("--month", required=True, help="the month the plan is for, e.g. 2027-01")
    p.add_argument("--code", help="the code to use (normally a fresh one)")
    p.add_argument("--bundle", help="the locked file (normally in the Dropbox updates folder)")
    e = sub.add_parser("extras", help="lock a month's engine extras")
    e.add_argument("folder")
    e.add_argument("--month", required=True)
    e.add_argument("--code")
    e.add_argument("--bundle")
    ls = sub.add_parser("list", help="which months the locked files hold")
    ls.add_argument("--kind", choices=["plans", "extras"])
    args = ap.parse_args()
    {"unlock": unlock, "plan": lock_plan, "extras": lock_extras, "list": list_bundles,
     "newcode": lambda a: print(new_code(a.month))}[args.command](args)


if __name__ == "__main__":
    main()
