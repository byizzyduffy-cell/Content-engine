"""
Talking-head editor: stickers (emojis) and sound effects.

Frances's rules (2026-10-10). The engine picks them from what's being said;
students never choose them ("it'll be too messy then picking"):

- Emojis are small, used sparingly, and only one pops up at a time on its own,
  beside the face (never on it).
- When there are three, they're always three of the same emoji, and they go
  where a pop-up would go, taking that pop-up's place:
    above   in a row above the head, the middle one bigger, for depth
    behind  rising up from behind the head, which stays in front of them
- Each comes with a sound that matches it.

Claude writes stickers.json in the work folder for each video:

    [
     {"emoji": "📱", "word": 14},
     {"trio": "🔍", "word": 103, "place": "above"},
     {"trio": "🙋‍♀️", "word": 125, "place": "behind"}
    ]

"word" is the word number from transcript.txt where it pops up. The rules Claude
follows: an emoji matches a word or idea being said, literally (📱 on
"Instagram", 💷 on money, 🔍 on "identify", 📅 on "diary"); never a wave 👋 (or any
greeting) when they say their name or introduce themselves (Frances, 2026-10-13:
"never do that"); objects they mention are what stickers are for; only where it adds something, so
at most one sticker moment every 6 to 8 seconds; a trio goes in a gap between
pop-ups (never while a pop-up or the hook is showing; the engine leaves out any
that would clash); nothing that could look like a result or a promise, and
nothing that could offend; check each emoji means what you think (👯‍♀️ is
dancers in bunny ears). A moment can say "sound" to choose its sound;
otherwise the engine picks it (SOUND_FOR below).

The look: each emoji as a small die-cut sticker (a white border and a soft
shadow), popping in with a little bounce and twist, floating gently, then
popping away. The emoji are drawn with the computer's own emoji font.
finish.py --stickers puts them on the video.
"""

import tools  # noqa: F401  (first: emoji-safe output on Windows)
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import captions  # noqa: E402
from text_reel import Writer  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
W, H = captions.W, captions.H

SIZE = 112            # a single sticker (pixels across)
TRIO = [92, 118, 92]  # a trio: the middle one bigger, for depth
TRIO_GAP = 175        # space between the middles of a trio's stickers
TRIO_STAGGER = 0.12   # a trio's stickers pop in this far apart (left, middle, right)
TRIO_TOP = 300        # "above": the trio sits where a pop-up would (the same line as pop-ups)
BEHIND_SHOW = 0.6     # "behind": how much of each sticker shows above the head
RISE = 90             # "behind": how far the stickers rise up from behind the head
CROWN_ABOVE = 0.22    # "behind": the top of the head is about this much of the face's height above the face
BORDER = 9            # the white die-cut border
GAP = 30              # space between a single sticker and the face
EDGE = 30             # ...and the side of the screen
STAYS = 1.6           # how long a single sticker stays
TRIO_STAYS = 2.2      # how long a trio stays after its last sticker arrives
POP_TIME = 0.25
LEAVE = 0.18
FLOAT = 5             # how far stickers bob up and down (pixels)
TILTS = [-9, 7, -5]
FIRST_LEVEL, FOLLOW_LEVEL = 0.5, 0.3   # the matched sound, then softer pops for the rest of a trio

# Which sound goes with which sticker. Anything not listed gets a pop.
SOUND_FOR = {
    "cha-ching": "💷💰💸🤑🪙💳",
    "sparkle": "✨🌟💫⭐🪄💎",
    "wrong": "❌🚫🙅⛔👎🛑",
    "ding": "💡✅☑✔👍🔔🎯",
    "boing": "😱😳🤯😮😲🙈🤭😂🤣",
    "rise": "🚀📈🔥💪🏆🎉🥳",
    "bubble": "❤💛💚💙🤍🥰😍💕💖🫶",
    "click": "📱💻📸🤳📷⌚",
    "whoosh": "💨🏃⏰⌛⏳",
    "chime": "🌸🌿🌱🧘💆🛁🧖",
}


def sound_for(emoji):
    for sound, emojis in SOUND_FOR.items():
        if any(ch in emojis for ch in emoji if ord(ch) > 0x2000 and ch not in "‍️"):
            return sound
    return "pop"


def sticker_picture(emoji, size=SIZE):
    """The emoji as a die-cut sticker: a white border round its shape and a soft shadow."""
    writer = Writer(round(size / 1.05))
    picture = writer.emoji_picture(emoji)
    if picture is None:
        return None
    margin = BORDER + 12
    canvas = Image.new("RGBA", (picture.width + margin * 2, picture.height + margin * 2))
    canvas.alpha_composite(picture, (margin, margin))
    shape = canvas.getchannel("A").point(lambda a: 255 if a > 40 else 0)
    border = shape.filter(ImageFilter.MaxFilter(BORDER * 2 + 1)).filter(ImageFilter.GaussianBlur(1.2))
    shadow = Image.new("RGBA", canvas.size)
    shadow.paste((0, 0, 0, 65), mask=border.filter(ImageFilter.GaussianBlur(7)))
    out = Image.new("RGBA", canvas.size)
    out.alpha_composite(shadow, (0, 4))
    white = Image.new("RGBA", canvas.size, (255, 255, 255, 0))
    white.putalpha(border)
    out.alpha_composite(white)
    out.alpha_composite(canvas)
    return out


def faces_near(faces, start, end):
    return [f for t, f in (faces or []) if f and start - 0.25 <= t <= end + 0.25]


def face_box(faces, start, end):
    """Where the face is around these times, as fractions of the frame (left, right, top, bottom)."""
    found = faces_near(faces, start, end)
    if not found:
        return 0.35, 0.65, 0.33, 0.62
    return (float(np.percentile([f["left"] for f in found], 10)),
            float(np.percentile([f["right"] for f in found], 90)),
            float(np.median([f["top"] for f in found])),
            float(np.median([f["bottom"] for f in found])))


def head_top_near(faces, start, end):
    import face
    found = faces_near(faces, start, end)
    return face.head_and_chin(found)[1] if found else captions.HEAD_TOP


class Stickers:
    """Draws the stickers from stickers.json onto each frame, and lists their sounds.
    busy: (start, end) times when the top of the screen is taken (the hook, pop-ups), so
    trios never clash with them."""

    def __init__(self, work, words, name="stickers.json", faces=None, busy=(), below=False, single_y=None):
        """below: the captions are above the head, so trios go below the face (Frances's rule).
        single_y: for voiceovers (no face), how far down the screen single stickers sit (0 to 1);
        they go to the left and right in turn, clear of the captions."""
        self.below = below
        self.single_y = single_y
        with open(os.path.join(work, name), encoding="utf-8") as f:
            wanted = json.load(f)
        times = {w["i"]: w["start"] for w in words}
        self.faces = faces or []
        self.items, self.sounds = [], []
        self.mask_cache = {}
        side = 0
        for moment in wanted:
            if "stickers" in moment:   # the older format: only the first emoji, on its own
                first = moment["stickers"][0]
                moment = first if isinstance(first, dict) else {"emoji": first, "word": moment.get("word")}
            start = times.get(moment.get("word"))
            if start is None:
                continue
            if "trio" in moment:
                end = start + TRIO_STAGGER * 2 + TRIO_STAYS
                if any(s < end and start < e for s, e in busy):
                    print(f"The {moment['trio']} stickers would clash with a pop-up or the hook, so they're left out.")
                    continue
                self.add_trio(moment, start, end)
            else:
                self.add_single(moment, start, side)
                side = 1 - side
        # One sticker moment at a time: each goes before the next one arrives.
        self.items.sort(key=lambda i: i["start"])
        for item in self.items:
            later = [j["start"] for j in self.items if j["moment"] != item["moment"] and j["start"] > item["start"]]
            if later:
                item["end"] = min(item["end"], min(later) - 0.1)

    def add_single(self, moment, start, side):
        end = start + STAYS
        if self.single_y is not None:   # a voiceover: no face, so a set height, left or right in turn
            picture = sticker_picture(moment["emoji"], SIZE)
            if picture is None:
                print(f"There's no emoji font on this computer, so the {moment['emoji']} sticker is left out.")
                return
            x = W * (0.24 if side == 0 else 0.76)
            self.items.append({"moment": id(moment), "start": start, "end": end, "picture": picture, "x": x,
                               "y": self.single_y * H, "tilt": TILTS[0] * (1 if side else -1), "phase": 0.0,
                               "behind": False, "cache": {}})
            sound = moment.get("sound") or sound_for(moment["emoji"])
            self.sounds.append((start, os.path.join(HERE, "sounds", f"{sound}.wav"), FIRST_LEVEL))
            return
        left, right, top, bottom = face_box(self.faces, start, end)
        room = {0: left * W - GAP - EDGE, 1: W - right * W - GAP - EDGE}
        if room[side] < SIZE * 0.8 and room[1 - side] > room[side]:
            side = 1 - side
        size = max(80, min(SIZE, room[side]))
        picture = sticker_picture(moment["emoji"], size)
        if picture is None:
            print(f"There's no emoji font on this computer, so the {moment['emoji']} sticker is left out.")
            return
        x = (left * W - GAP - size / 2) if side == 0 else (right * W + GAP + size / 2)
        x = min(W - EDGE - size / 2, max(EDGE + size / 2, x))
        y = (top + (bottom - top) * 0.45) * H
        self.items.append({"moment": id(moment), "start": start, "end": end, "picture": picture, "x": x, "y": y,
                           "tilt": TILTS[0] * (1 if side else -1), "phase": 0.0, "behind": False, "cache": {}})
        sound = moment.get("sound") or sound_for(moment["emoji"])
        self.sounds.append((start, os.path.join(HERE, "sounds", f"{sound}.wav"), FIRST_LEVEL))

    def add_trio(self, moment, start, end):
        place = "below" if self.below else moment.get("place", "above")
        if place == "behind" and not self.faces:
            place = "above"   # no head to go behind (a voiceover)
        emoji = moment["trio"]
        import notes
        below_top, _ = notes.zone(True, self.faces, start, end)
        head_top = head_top_near(self.faces, start, end) * H
        order = [0, 2, 1] if place == "above" else [1, 0, 2]   # above: sides first, then the big one
        for rank, k in enumerate(order):
            size = TRIO[k]
            picture = sticker_picture(emoji, size)
            if picture is None:
                print(f"There's no emoji font on this computer, so the {emoji} stickers are left out.")
                return
            x = W / 2 + (k - 1) * TRIO_GAP
            if place == "behind":
                # Placed against the head in every frame (see draw_on): across from the middle of
                # the face, and down so only the top part shows above the crown.
                x = (k - 1) * TRIO_GAP * 0.85
                lift = 14 if k == 1 else 0   # the middle one peeks up a little higher
                y = picture.height * (0.5 - BEHIND_SHOW) - lift
            elif place == "below":   # in a row on the body, under the chin
                y = below_top + picture.height / 2 + (0 if k == 1 else 14)
            else:
                y = TRIO_TOP + picture.height / 2 + (0 if k == 1 else 14)   # the smaller ones sit a touch lower
            t = start + rank * TRIO_STAGGER
            self.items.append({"moment": id(moment), "start": t, "end": end, "picture": picture, "x": x, "y": y,
                               "tilt": TILTS[k] * (0.6 if k == 1 else 1), "phase": k * 1.1,
                               "behind": place == "behind", "cache": {}})
            sound = (moment.get("sound") or sound_for(emoji)) if rank == 0 else "pop"
            self.sounds.append((t, os.path.join(HERE, "sounds", f"{sound}.wav"),
                                FIRST_LEVEL if rank == 0 else FOLLOW_LEVEL))

    def face_at(self, t):
        """The face at t, as fractions of the frame, between the face finder's looks."""
        found = [(s, f) for s, f in self.faces if f]
        if not found:
            return None
        before = [x for x in found if x[0] <= t]
        after = [x for x in found if x[0] > t]
        if not before or not after:
            return (before or after)[-1 if before else 0][1]
        (t0, a), (t1, b) = before[-1], after[0]
        if t1 - t0 > 1.0:
            return a if t - t0 < t1 - t else b
        u = (t - t0) / (t1 - t0)
        return {k: a[k] + (b[k] - a[k]) * u for k in ("left", "right", "top", "bottom")}

    def head_mask_at(self, frame, t):
        """The head and hair outline at t. It needs to see the whole head to work, so it's traced
        every other frame and reused for the one in between (a head barely moves in that time)."""
        import outline
        key = int(t * 15)
        if key not in self.mask_cache:
            here = self.face_at(t)
            self.mask_cache = {key: None if here is None else
                               outline.head_mask(np.ascontiguousarray(frame[..., ::-1]), here)}
        return self.mask_cache[key]

    def draw_on(self, frame, t):
        showing = [i for i in self.items if i["start"] <= t < i["end"]]
        if not showing:
            return frame
        behind = [i for i in showing if i["behind"]]
        target = frame.copy() if behind else None   # behind stickers go on a copy; the head is laid back on top
        mask = self.head_mask_at(frame, t) if behind else None
        for item in showing:
            since, left = t - item["start"], item["end"] - t
            p = min(1.0, since / POP_TIME)
            scale = captions.ease_out_back(p) if p < 1 else 1.0
            turn = item["tilt"] * (1.8 - 0.8 * p)   # twists into place
            alpha = min(1.0, since / 0.05)
            rise = 0.0
            if item["behind"]:
                eased = 1 - (1 - min(1.0, since / 0.4)) ** 3
                rise = RISE * (1 - eased)   # comes up from behind the head
                scale = 0.75 + 0.25 * eased
                alpha = min(1.0, since / 0.08)
            if left < LEAVE:
                q = left / LEAVE
                scale *= 0.6 + 0.4 * q
                alpha *= q
            bob = FLOAT * math.sin((since + item["phase"]) * 2 * math.pi / 1.4)
            key = (round(max(scale, 0.05), 2), round(turn))
            if key not in item["cache"]:
                picture = item["picture"]
                sized = picture.resize((max(1, round(picture.width * key[0])), max(1, round(picture.height * key[0]))),
                                       Image.BILINEAR)
                item["cache"][key] = np.asarray(sized.rotate(key[1], resample=Image.BICUBIC, expand=True))
            picture = item["cache"][key]
            where = target if item["behind"] else frame
            x, y = item["x"], item["y"]
            if item["behind"]:   # follows the head: across from the middle of the face, down to the hair
                here = self.face_at(t) or {"left": 0.35, "right": 0.65, "top": 0.33, "bottom": 0.62}
                x = (here["left"] + here["right"]) / 2 * W + item["x"]
                crown = (here["top"] - CROWN_ABOVE * (here["bottom"] - here["top"])) * H
                if mask is not None:   # where the hair actually starts, right under this sticker
                    half = item["picture"].width * 0.2
                    columns = mask[:, int(max(0, x - half)):int(min(W, x + half))]
                    rows = np.where(columns.max(axis=1) > 0.5)[0]
                    if len(rows):
                        crown = float(rows[0])
                item["crown"] = crown if "crown" not in item else item["crown"] * 0.7 + crown * 0.3   # steady
                y = item["crown"] + item["y"]
            top = y - picture.shape[0] / 2 + bob + rise
            captions.lay_on(where, picture, x, top, alpha)
        if behind:
            if mask is None:
                frame[:] = target
            else:
                m = mask[..., None]
                frame[:] = (frame.astype(np.float32) * m + target.astype(np.float32) * (1 - m)).astype(np.uint8)
        return frame
