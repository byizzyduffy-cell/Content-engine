"""
List reels: reels where the lines appear one by one.

A title shows first, then each line appears on its own, giving people time to
read it, with a soft click as it lands. Numbered lists line up neatly down the
left; other lines are centred. A reel can also end with the call-to-action
pop-up, and can use several clips one after another.

Used for posts like "Hills I'll die on" (a numbered list), "laser edition"
(labels with a line under each) and "Christmas is 8 weeks away" (lines with a
pause between them).
"""

import tools  # noqa: F401  (first: emoji-safe output on Windows)
import os
import re
import subprocess
import tempfile

from PIL import Image, ImageFilter

import text_reel as tr

# ---------------------------------------------------------------------------
# Timing and look. Change these numbers to change every list reel.
# ---------------------------------------------------------------------------
TITLE_ALONE = 1.8      # seconds the title is on screen before the first line
PAUSE = 2.5            # seconds between lines in a "wait a few seconds" reel
HOLD = 2.5             # seconds everything stays on screen at the end
DARKNESS = 0.38        # lists carry more words, so the clip is a little darker
BIGGEST_TEXT = 50
SMALLEST_TEXT = 30
LINE_SOUND = "click"   # the soft sound as each line lands
TITLE_SIZE = 1.15      # the title is a touch bigger than the lines, so it reads as a heading

# Lists need more room than a single line of text. (left, top, right, bottom)
LIST_BOXES = {
    "middle": (140, 420, 940, 1420),
    "top": (140, 260, 940, 1260),
}
ROOM_FOR_POPUP = 210   # space kept free underneath when the reel ends with a pop-up

NUMBERED = re.compile(r"^(\d+[.)])\s+(.*)$", re.S)


def layout(title, lines, look, popup):
    """Find the biggest text size where the title and every line fit in the box."""
    left, top, right, bottom = LIST_BOXES.get(look.position, LIST_BOXES["middle"])   # "lower" lists sit in the middle
    if popup:
        bottom -= ROOM_FOR_POPUP
    width = right - left
    numbered = bool(lines) and all(NUMBERED.match(line) for line in lines)
    capitals = ("spaced" if look.lines else True) if look.text_case == "capitals" else False
    for size in range(BIGGEST_TEXT, SMALLEST_TEXT - 1, -2):
        writer = tr.Writer(size, look.heading_font, "heading", capitals, look.outline)
        title_writer = tr.Writer(round(size * TITLE_SIZE), look.heading_font, "heading", capitals, look.outline)
        line_height = size * tr.LINE_SPACING
        title_lines = tr.wrap(title_writer, title, width)
        blocks = []
        for line in lines:
            if numbered:
                number, rest = NUMBERED.match(line).groups()
                indent = writer.measure(number + " ")
                blocks.append((number, indent, tr.wrap(writer, rest, width - indent)))
            else:
                blocks.append((None, 0, tr.wrap(writer, line, width)))
        height = (tr.block_height(title_writer, title_lines) + line_height * 0.6
                  + sum(tr.block_height(writer, b[2]) for b in blocks) + line_height * 0.35 * (len(blocks) - 1))
        if height <= bottom - top:
            break
    return writer, title_writer, title_lines, blocks, numbered, (left, top, right, bottom), height


def draw_layer(draw):
    """A see-through full-frame picture with soft shadows under the words."""
    words = Image.new("RGBA", (tr.WIDTH, tr.HEIGHT))
    shadow = Image.new("RGBA", (tr.WIDTH, tr.HEIGHT))
    draw(words, shadow)
    layer = shadow.filter(ImageFilter.GaussianBlur(4))
    layer.alpha_composite(words)
    return layer


def put_lines(writer, words, shadow, lines, x_left, width, y, look, centred):
    line_height = writer.size * tr.LINE_SPACING
    for line in lines:
        if line is None:
            y += line_height * 0.5
            continue
        x = x_left + (width - writer.line_width(line)) / 2 if centred else x_left
        baseline = y + (line_height + writer.size * 0.7) / 2
        for word in line:
            x = writer.draw_word(words, x, baseline, word, look.text_colour, shadow if look.shadow else None,
                                 look.highlight) + writer.measure(" ")
        y += line_height
    return y


def layers(title, lines, look, popup):
    """The title picture, one picture per line, and where the text ends."""
    writer, title_writer, title_lines, blocks, numbered, (left, top, right, bottom), height = layout(title, lines, look, popup)
    width = right - left
    line_height = writer.size * tr.LINE_SPACING
    y = top + (bottom - top - height) / 2

    title_end = y + tr.block_height(title_writer, title_lines)
    title_layer = draw_layer(lambda w, s: put_lines(title_writer, w, s, title_lines, left, width, y, look, True))
    y = title_end + line_height * 0.6

    # A numbered list is lined up on the left, with the whole list centred on screen.
    widest = max((indent + max(writer.line_width(l) for l in ls if l) for _, indent, ls in blocks), default=0)
    list_left = left + (width - widest) / 2

    line_layers = []
    for number, indent, block_lines in blocks:
        def draw(w, s, number=number, indent=indent, block_lines=block_lines, y=y):
            if number:
                put_lines(writer, w, s, [[number]], list_left, width, y, look, False)
                put_lines(writer, w, s, block_lines, list_left + indent, width, y, look, False)
            else:
                put_lines(writer, w, s, block_lines, left, width, y, look, True)
        line_layers.append(draw_layer(draw))
        y += tr.block_height(writer, block_lines) + line_height * 0.35
    return title_layer, line_layers, y - line_height * 0.35


def make_list_reel(segments, title, lines, out, look=tr.Look(), popup=None, pauses=False, title_time=None,
                   used=None):
    """segments: the clips to use, in order, as [(clip, start), ...]. title_time: seconds the title
    is on its own, for a long first line (a two-beat reel where the punchline arrives second).
    used: what's been used of each clip already this month (clip_moments.py)."""
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    originals = list(segments)
    segments = [(tr.normal_colour(clip), start) for clip, start in segments]   # iPhone HDR to normal colour
    title_alone = title_time or TITLE_ALONE
    gaps = [PAUSE if pauses else tr.read_time(line) for line in lines]
    times = [title_alone + sum(gaps[:i]) for i in range(len(lines))]
    after_last = times[-1] + gaps[-1] if lines else title_alone
    popup_at = after_last if popup else None
    length = popup_at + tr.POPUP_STAYS if popup else after_last + HOLD

    keep = 1 - DARKNESS
    grade, (r, g, b) = tr.GRADES.get(look.grade, tr.GRADES[""])
    each = length / len(segments)
    # Each clip's turn comes from its strong moments, never across the gun lifting off (2026-11-02).
    segments = [tr.strong_footage(orig, clip, start, each, used)
                for (orig, _), (clip, start) in zip(originals, segments)]

    with tempfile.TemporaryDirectory() as tmp:
        title_layer, line_layers, text_bottom = layers(title, lines, look, popup)
        inputs, steps = [], []

        # The clips, one after another, each looping if it's shorter than its turn.
        for k, (clip, start) in enumerate(segments):
            start = max(0.0, min(start, tr.clip_length(clip) - each))
            inputs += ["-stream_loop", "-1", "-ss", str(start), "-t", f"{each:.3f}", "-i", clip]
            # setpts before fps, so a start between two frames never shows a frame twice (2026-10-29).
            steps.append(f"[{k}:v]setpts=PTS-STARTPTS,scale={tr.WIDTH}:{tr.HEIGHT}:force_original_aspect_ratio=increase,"
                         f"crop={tr.WIDTH}:{tr.HEIGHT},setsar=1,fps={tr.FPS},format=yuv420p[s{k}]")
        joined = "".join(f"[s{k}]" for k in range(len(segments)))
        steps.append(f"{joined}concat=n={len(segments)}:v=1:a=0,{grade + ',' if grade else ''}format=gbrp,"
                     f"colorchannelmixer=rr={r * keep:.3f}:gg={g * keep:.3f}:bb={b * keep:.3f}[v0]")

        # The title fades on straight away, then each line at its time, with a click.
        pictures = [(title_layer, 0.0)] + list(zip(line_layers, times))
        n = len(segments)
        last, sounds = "v0", []
        for i, (picture, at) in enumerate(pictures):
            path = os.path.join(tmp, f"layer{i}.png")
            picture.save(path)
            inputs += ["-loop", "1", "-t", f"{length:.3f}", "-i", path]
            steps.append(f"[{n}:v]format=rgba,fade=in:st={at:.3f}:d=0.25:alpha=1[t{i}]")
            steps.append(f"[{last}][t{i}]overlay=0:0:format=gbrp[v{i + 1}]")
            last, n = f"v{i + 1}", n + 1
            if i > 0 and look.sound:
                sounds.append((tr.sound_file(LINE_SOUND), at))

        if popup:
            frames, _ = tr.popup_frames(popup, text_bottom, tmp, look)
            inputs += ["-framerate", str(tr.FPS), "-i", frames]
            steps.append(f"[{n}:v]format=rgba,setpts=PTS+{popup_at:.3f}/TB[popup]")
            steps.append(f"[{last}][popup]overlay=0:0:format=gbrp:eof_action=repeat[vp]")
            last, n = "vp", n + 1
            if look.sound:
                sounds.append((tr.sound_file(look.sound), popup_at))

        for path, at in sounds:
            inputs += ["-i", path]
            delay = round(at * 1000)
            steps.append(f"[{n}:a]adelay={delay}|{delay}[a{n}]")
            n += 1
        if sounds:
            mix = "".join(f"[a{k}]" for k in range(n - len(sounds), n))
            steps.append(f"{mix}amix=inputs={len(sounds)}:normalize=0,apad[sound]")
        steps.append(f"[{last}]scale=out_color_matrix=bt709:out_range=tv,format=yuv420p[reel]")

        audio = ["-map", "[sound]", "-c:a", "aac", "-b:a", "160k"] if sounds else ["-an"]
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", *inputs,
             "-filter_complex", ";".join(steps), "-map", "[reel]", *audio,
             "-t", f"{length:.3f}", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
             "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
             "-movflags", "+faststart", out],
            check=True,
        )
    return out
