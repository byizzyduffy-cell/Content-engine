"""
Memes the engine makes itself, for meme posts that come without a CapCut template
(Frances, 2026-10-10: when there's no template, the engine makes it).

The look (Frances, 2026-10-10): the words sit over the picture, in the top part
of the screen, white with a soft shadow, the picture very lightly darkened so
they read. ("bar" puts them on a white bar above the picture instead.) Frances's rule (2026-10-10): a meme is always a still picture, nine
times out of ten of the clinic itself, and plain: the reception area, the
treatment room. The meme words never change (her rule), emoji included. It's
silent: they add a trending sound when they post it on Instagram.

    .venv/bin/python engine/meme.py --photo "My Content/photos/reception.jpg" \\
        --text "Nothing scarier than..." --out "My Content/2026-10/reels/2026-10-18.mp4"

With no photo, a still taken from one of their clips of the clinic room works
too: --clip "My Content/2026-10/clips/IMG_3173.MOV" --start 0.5 (the frame at 0.5s).

Memes WITH a CapCut template are made by the student in the CapCut app (the
planner shows them how, with a QR code that opens the template on their phone).
"""

import tools  # noqa: F401  (first: emoji-safe output on Windows)
import argparse
import os
import subprocess
import sys
import tempfile

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from text_reel import Writer, block_height, tidy_size  # noqa: E402

W, H, FPS = 1080, 1920, 30
FONT, SIZE = "Poppins", 58      # clean and bold, the way meme captions look
INK, BAR = "#111111", "#FFFFFF"
WHITE = "#FFFFFF"
WORDS_TOP = 330       # "over": the words start here, under Instagram's top bar
HIGHEST = 270         # "over": the highest they go ("move the words up a bit"), clear of Instagram's top 14%
DARKEN = 0.18         # "over": how much the picture is darkened so white words read
SIDE = 70                        # space either side of the words
PAD = 64                         # space above and below the words in the bar
TOP_ROOM = 120                   # extra room at the very top, under Instagram's bar
SECONDS = 7


def bar_picture(text):
    """The white bar with the meme words, and how tall it is."""
    writer, lines = tidy_size(lambda size: Writer(size, FONT, "caption"), text, W - SIDE * 2, SIZE)
    words_height = block_height(writer, lines)
    bar = round(TOP_ROOM + PAD + words_height + PAD)
    picture = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    picture.paste(Image.new("RGBA", (W, bar), BAR), (0, 0))
    writer.draw_lines(picture, lines, SIDE, W - SIDE, TOP_ROOM + PAD, INK)
    return picture, bar


def words_over_picture(text, top=WORDS_TOP):
    """The meme words, white with a soft shadow, to lay over the picture, starting top pixels down."""
    from PIL import ImageFilter
    writer, lines = tidy_size(lambda size: Writer(size, FONT, "caption"), text, W - SIDE * 2, SIZE)
    words = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    writer.draw_lines(words, lines, SIDE, W - SIDE, max(HIGHEST, top), WHITE, shadow)
    shadow = shadow.filter(ImageFilter.GaussianBlur(6))
    shadow.alpha_composite(words)
    return shadow


def make(clip, text, out, start=0.5, seconds=SECONDS, photo=None, layout="over", top=WORDS_TOP):
    """photo: a still picture (the usual way). clip and start: a still frame taken from a clip.
    layout: "over" (the words over the picture, the default) or "bar" (a white bar above it).
    top: with "over", how far down the words start (out of 1920), never higher than HIGHEST."""
    from sdr import normal_colour
    clip = normal_colour(clip) if clip else clip
    if layout == "bar":
        picture, bar = bar_picture(text)
    else:
        picture, bar = words_over_picture(text, top), 0
    below = H - bar
    tmp = tempfile.mkdtemp(prefix="meme-")
    try:
        overlay = os.path.join(tmp, "bar.png")
        picture.save(overlay)
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        still = os.path.join(tmp, "still.png")
        if photo:   # the phone's photo turned the right way up
            from PIL import ImageOps
            ImageOps.exif_transpose(Image.open(photo)).convert("RGB").save(still)
        else:
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{start:.2f}", "-i", clip, "-frames:v", "1",
                            still], check=True)
        dim = "" if layout == "bar" else f",colorchannelmixer=rr={1 - DARKEN}:gg={1 - DARKEN}:bb={1 - DARKEN}"
        graph = (f"[0:v]scale={W}:{below}:force_original_aspect_ratio=increase,crop={W}:{below}{dim},"
                 f"pad={W}:{H}:0:{bar}:white,fps={FPS}[v];[v][1:v]overlay=0:0,format=yuv420p[out]")
        result = subprocess.run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-framerate", str(FPS),
                                 "-t", f"{seconds:.2f}", "-i", still, "-i", overlay, "-f", "lavfi", "-t", f"{seconds:.2f}",
                                 "-i", "anullsrc=r=48000:cl=stereo", "-filter_complex", graph,
                                 "-map", "[out]", "-map", "2:a", "-c:v", "libx264", "-crf", "18", "-c:a", "aac",
                                 "-shortest", "-movflags", "+faststart", out], capture_output=True, text=True)
        if result.returncode != 0:
            raise SystemExit(f"Making the meme didn't work:\n{result.stderr[-1500:]}")
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"Meme saved {out}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--photo", help="a still picture of the clinic (the usual way)")
    ap.add_argument("--clip", help="or a clip to take a still frame from")
    ap.add_argument("--text", required=True, help="the meme words, exactly as in the plan")
    ap.add_argument("--out", required=True)
    ap.add_argument("--start", type=float, default=0.5, help="with --clip: which moment to take the still from")
    ap.add_argument("--seconds", type=float, default=SECONDS)
    ap.add_argument("--layout", choices=["over", "bar"], default="over",
                    help="the words over the picture (default) or on a white bar above it")
    ap.add_argument("--top", type=int, default=WORDS_TOP,
                    help=f"with the words over the picture: how far down they start, out of 1920 "
                         f"(default {WORDS_TOP}; lower numbers move them up, to {HIGHEST} at most)")
    args = ap.parse_args()
    if not args.photo and not args.clip:
        raise SystemExit("Say which picture to use: --photo, or --clip and --start.")
    make(args.clip, args.text, args.out, args.start, args.seconds, args.photo, args.layout, args.top)


if __name__ == "__main__":
    main()
