"""
Photos for carousels and single posts, with nobody's face under the words (Frances, 2026-11-02: "when we're
doing the carousels, you're putting the text over people's faces... not ever put text over faces").

A carousel's words sit in the middle of each slide (her rule), so the photo behind them is cropped to keep
every face above or below the words: a client on the couch, a therapist, anyone. When that can't be done, it
says so, and the photo goes on another slide or a different one is used.

    PY engine/post_photos.py still CLIP SECONDS OUT [--zone middle] [--size 1080x1350]
    PY engine/post_photos.py photo PHOTO OUT [--zone middle] [--size 1080x1350]
    PY engine/post_photos.py scan CLIP [--zone middle] [--from S] [--to S]
    PY engine/post_photos.py sheet CLIP FOLDER [--count 6] [--zone middle]

still: a frame from a clip at SECONDS. photo: one of their photos. Both are cropped to the slide's shape and
saved as OUT, and print one line: CLEAR (no face where the words go), NO FACE, or FACE IN THE WAY (try
another moment or photo). scan: the moments in a clip (every half second) where faces can be kept clear.
sheet CLIP FOLDER [--count 6]: candidate photos from a clip's clear moments, plus one picture of them all with
the words' area outlined, for Claude to look at: a photo is only used if it clearly shows the treatment.
--no-zoom on still: the whole picture, never zoomed in (when zooming in loses the treatment).

--zone is where the words go on the slide: middle (the usual, centred words), top (designs with the words at
the top, like "Words at the top"), bottom, or four fractions "left,top,right,bottom". --size is the photo
frame's shape in Canva (a full slide is 1080x1350).
"""

import tools  # noqa: F401  (first: emoji-safe output on Windows)
import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = os.path.join(HERE, "models", "face_detection_yunet_2023mar.onnx")

ZONES = {                                  # where the words go, as fractions of the slide
    "middle": (0.08, 0.27, 0.92, 0.73),
    "top": (0.08, 0.04, 0.92, 0.48),
    "bottom": (0.08, 0.52, 0.92, 0.96),
}
SURE = 0.35         # much lower than for talking heads: a client in laser goggles, half-turned, still counts
HAIR = 0.25         # room above the face box for hair, and a little either side
LOOKS = (480, 800)  # pictures are shrunk to these widths to look for faces (small faces show up better in one)
AROUND = 1.0        # for a still from a clip, faces seen this many seconds either side count too
EVERY = 0.25        # ...looked for this often


def zone_of(text):
    if text in ZONES:
        return ZONES[text]
    values = tuple(float(v) for v in text.split(","))
    if len(values) != 4:
        raise SystemExit("--zone is middle, top, bottom or four fractions: left,top,right,bottom")
    return values


def read_frame(clip, seconds):
    """One frame of a clip as a picture (blue-green-red numbers), the right way up, in normal colour."""
    import cv2
    import numpy as np
    from sdr import normal_colour
    clip = normal_colour(clip)
    data = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{max(0.0, seconds):.3f}", "-i", clip,
                           "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True).stdout
    if not data:
        raise SystemExit(f"Couldn't read a frame at {seconds}s from {clip}")
    return cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)


def read_photo(path):
    import cv2
    from PIL import Image, ImageOps
    import numpy as np
    picture = ImageOps.exif_transpose(Image.open(path)).convert("RGB")      # phone photos stored on their side
    return cv2.cvtColor(np.array(picture), cv2.COLOR_RGB2BGR)


def detect(picture):
    """Every face in the picture, as boxes in fractions of it (left, top, right, bottom), with room for hair.
    The face finder misses a face now and then (laser goggles hide the eyes), so it looks at two sizes."""
    import cv2
    h, w = picture.shape[:2]
    boxes = []
    for look in LOOKS:
        scale = look / w
        small = cv2.resize(picture, (look, round(h * scale)))
        finder = cv2.FaceDetectorYN.create(MODEL, "", (small.shape[1], small.shape[0]), SURE, 0.3, 5000)
        _, found = finder.detect(small)
        for f in (found if found is not None else []):
            x, y, fw, fh = (float(v) for v in f[:4])
            sw, sh = small.shape[1], small.shape[0]
            boxes.append(((x - fw * HAIR / 2) / sw, (y - fh * HAIR) / sh,
                          (x + fw * (1 + HAIR / 2)) / sw, (y + fh * 1.05) / sh))
    return boxes


def faces_in(picture, extra=()):
    """The faces in the picture (and any `extra` boxes in fractions, from moments either side), in its pixels."""
    h, w = picture.shape[:2]
    return [(l * w, t * h, r * w, b * h) for l, t, r, b in list(detect(picture)) + list(extra)]


def clip_frames(clip, start, end, every=EVERY, width=800):
    """(seconds, small picture) through a stretch of a clip, read in one go."""
    import numpy as np
    from face import video_size
    from sdr import normal_colour
    clip = normal_colour(clip)
    vw, vh = video_size(clip)
    h = round(vh * width / vw / 2) * 2
    reader = subprocess.Popen(["ffmpeg", "-v", "error", "-ss", f"{max(0.0, start):.3f}", "-i", clip,
                               "-t", f"{max(0.1, end - start):.3f}", "-vf",
                               f"setpts=PTS-STARTPTS,fps={1 / every:g},scale={width}:{h}",
                               "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], stdout=subprocess.PIPE)
    n = 0
    while True:
        buf = reader.stdout.read(width * h * 3)
        if len(buf) < width * h * 3:
            break
        yield round(max(0.0, start) + n * every, 2), np.frombuffer(buf, np.uint8).reshape(h, width, 3)
        n += 1
    reader.wait()


def faces_near(clip, seconds, around=AROUND):
    """Every face seen in the clip from `around` seconds before to after, in fractions: the client lying on
    the couch hardly moves, so a face the finder misses in one frame shows up in the next."""
    found = []
    for _, picture in clip_frames(clip, seconds - around, seconds + around):
        found += detect(picture)
    return found


ZOOMS = (1.0, 0.85, 0.72, 0.6)   # how much of the picture a crop may keep: closer in on the treatment drops a face


def busy_map(picture):
    """How much is going on across the picture (edges: hands, the device, skin, the machine), as a running
    total, so a crop of the treatment beats a crop of a plain wall or towel."""
    import cv2
    import numpy as np
    h, w = picture.shape[:2]
    small = cv2.resize(picture, (200, max(1, round(h * 200 / w))))
    edges = cv2.Canny(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY), 60, 160).astype(np.float64) / 255
    return cv2.integral(edges), 200 / w


def busy(totals, scale, left, top, cw, ch):
    x0, y0 = int(left * scale), int(top * scale)
    x1, y1 = max(x0 + 1, int((left + cw) * scale)), max(y0 + 1, int((top + ch) * scale))
    x1, y1 = min(x1, totals.shape[1] - 1), min(y1, totals.shape[0] - 1)
    total = totals[y1, x1] - totals[y0, x1] - totals[y1, x0] + totals[y0, x0]
    return total / max(1, (x1 - x0) * (y1 - y0))


def best_crop(picture, faces, size, zone, real_width=None):
    """The crop of the picture to the slide's shape where every face is clear of the words' zone and no face is
    sliced by the edge (each one wholly in the photo, above or below the words, or wholly out of it). Of
    those, the widest (zooming in on the treatment only if it must), then the busiest (the treatment, not a
    wall). Returns (left, top, width, height in the picture's pixels, overlap): overlap 0 means every face
    is clear. real_width: the source's own width, when `picture` is a small copy of it (to judge when a
    closer crop would go soft)."""
    h, w = picture.shape[:2]
    sharpness = (real_width or w) / w
    totals, scale = busy_map(picture)
    out_w, out_h = size
    full_w, full_h = (w, round(w * out_h / out_w)) if w / h < out_w / out_h else (round(h * out_w / out_h), h)
    full_w, full_h = min(full_w, w), min(full_h, h)
    zl, zt, zr, zb = zone
    best = None
    for zoom in ZOOMS:
        crop_w, crop_h = round(full_w * zoom), round(full_h * zoom)
        if crop_w * sharpness < out_w * 0.9 and zoom < 1:      # never so close it goes soft
            break
        step = max(4, (max(w - crop_w, h - crop_h)) // 60)
        for left in range(0, w - crop_w + 1, step) if w > crop_w else [0]:
            for top in range(0, h - crop_h + 1, step) if h > crop_h else [0]:
                words = (left + zl * crop_w, top + zt * crop_h, left + zr * crop_w, top + zb * crop_h)
                overlap, sliced = 0.0, 0.0
                for fl, ft, fr, fb in faces:
                    area = max(1.0, (fr - fl) * (fb - ft))
                    dx = min(fr, words[2]) - max(fl, words[0])
                    dy = min(fb, words[3]) - max(ft, words[1])
                    if dx > 0 and dy > 0:
                        overlap += dx * dy / area
                    ix = min(fr, left + crop_w) - max(fl, left)
                    iy = min(fb, top + crop_h) - max(ft, top)
                    inside = max(0.0, ix) * max(0.0, iy) / area
                    if 0.03 < inside < 0.95:      # any part of a face cut off by the edge of the photo
                        sliced += 1
                score = (overlap >= 0.02, sliced, round(overlap, 2), -busy(totals, scale, left, top, crop_w, crop_h))
                if best is None or score < best[0]:
                    best = (score, (left, top, crop_w, crop_h, overlap, sliced))
        if not best[0][0] and not best[0][1]:
            break
    return best[1]


def save_crop(picture, crop, size, out):
    import cv2
    left, top, cw, ch = crop[:4]
    piece = cv2.resize(picture[top:top + ch, left:left + cw], size, interpolation=cv2.INTER_AREA)
    os.makedirs(os.path.dirname(os.path.abspath(out)) or ".", exist_ok=True)
    cv2.imwrite(out, piece, [cv2.IMWRITE_JPEG_QUALITY, 92])


def verdict(faces, crop, full_width):
    if not faces:
        return "NO FACE"
    if crop[4] >= 0.02 or crop[5]:
        return ("FACE IN THE WAY: no crop keeps every face clear of the words without cutting one off at the edge. "
                "Use another moment or another photo")
    closer = crop[2] < full_width * 0.99
    return "CLEAR" + (", zoomed in on the treatment to keep the face out (check it still shows the treatment)"
                      if closer else ": every face is above or below the words")


def scan_clip(clip, size, zone, start=0.0, end=None):
    """Every half second of the clip, sorted into (clear in the whole picture, clear only zoomed in, face in the
    way). Faces seen a second either side count, as for a still."""
    import numpy as np
    from face import video_size
    length = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                   clip], capture_output=True, text=True).stdout.strip().split(",")[0])
    end = min(end or length, length - 0.1)
    real_width = video_size(clip)[0]
    seen, shape = [], None
    for t, picture in clip_frames(clip, start, end + 0.01):
        seen.append((t, detect(picture)))
        shape = picture.shape
    clear, closer, blocked = [], [], []
    for t, _ in seen:
        if round(t * 2) != t * 2:        # every half second
            continue
        near = [box for s, boxes in seen if abs(s - t) <= AROUND for box in boxes]
        faces = [(l * shape[1], tp * shape[0], r * shape[1], b * shape[0]) for l, tp, r, b in near]
        crop = best_crop(np.zeros(shape, "uint8"), faces, size, zone, real_width)
        full = min(shape[1], round(shape[0] * size[0] / size[1]))
        group = blocked if crop[4] >= 0.02 or crop[5] else clear if crop[2] >= full * 0.99 else closer
        group.append(round(t, 1))
    return clear, closer, blocked


def spread(moments, count, gap=1.5):
    """Up to `count` of the moments, at least `gap` seconds apart, spread through them."""
    picked = []
    for t in moments[::max(1, len(moments) // max(1, count))] + moments:
        if len(picked) < count and all(abs(t - p) >= gap for p in picked):
            picked.append(t)
    return sorted(picked)


def plain(path):
    """True when a photo is mostly wall, couch or towel, with nothing of the treatment in it (measured on the
    saved photo: how much detail and contrast it has; the good ones from her clips had 5 to 30 times more)."""
    import cv2
    small = cv2.cvtColor(cv2.resize(cv2.imread(path), (200, 250)), cv2.COLOR_BGR2GRAY)
    return (cv2.Canny(small, 60, 160) > 0).mean() < 0.03 or float(small.std()) < 25


def make_still(clip, seconds, out, size, zone, zoom=True):
    picture = read_frame(clip, seconds)
    faces = faces_in(picture, faces_near(clip, seconds))
    global ZOOMS
    keep, ZOOMS = ZOOMS, (ZOOMS if zoom else (1.0,))
    try:
        crop = best_crop(picture, faces, size, zone)
    finally:
        ZOOMS = keep
    save_crop(picture, crop, size, out)
    full = min(picture.shape[1], round(picture.shape[0] * size[0] / size[1]))
    result = verdict(faces, crop, full)
    if result.startswith("CLEAR") and plain(out):
        result = "PLAIN: mostly wall, couch or towel, nothing of the treatment. Use another moment or photo"
    return result


def contact_sheet(paths, labels, zone, out):
    """The candidate photos side by side, with the words' area outlined, for Claude to look at and choose."""
    from PIL import Image, ImageDraw
    tiles = []
    for path, label in zip(paths, labels):
        im = Image.open(path).convert("RGB")
        im.thumbnail((300, 375))
        d = ImageDraw.Draw(im)
        w, h = im.size
        zl, zt, zr, zb = zone
        d.rectangle((zl * w, zt * h, zr * w, zb * h), outline=(0, 200, 255), width=3)
        d.rectangle((0, 0, w, 22), fill=(0, 0, 0))
        d.text((6, 4), label, fill=(255, 255, 255))
        tiles.append(im)
    sheet = Image.new("RGB", (sum(t.width + 6 for t in tiles), max(t.height for t in tiles)), (255, 255, 255))
    x = 0
    for t in tiles:
        sheet.paste(t, (x, 0))
        x += t.width + 6
    sheet.save(out, quality=88)


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["still", "photo", "scan", "sheet"])
    ap.add_argument("source")
    ap.add_argument("more", nargs="*")
    ap.add_argument("--zone", default="middle")
    ap.add_argument("--size", default="1080x1350")
    ap.add_argument("--from", dest="start", type=float, default=0.0)
    ap.add_argument("--to", dest="end", type=float)
    ap.add_argument("--count", type=int, default=6)
    ap.add_argument("--no-zoom", action="store_true", help="still: the whole picture, never zoomed in")
    a = ap.parse_args(argv)
    size = tuple(int(v) for v in a.size.lower().split("x"))
    zone = zone_of(a.zone)
    if a.what == "still":
        seconds, out = float(a.more[0]), a.more[1]
        print(f"{make_still(a.source, seconds, out, size, zone, not a.no_zoom)}. Saved {out}")
        return 0
    if a.what == "photo":
        out = a.more[0]
        picture = read_photo(a.source)
        faces = faces_in(picture)
        crop = best_crop(picture, faces, size, zone)
        save_crop(picture, crop, size, out)
        full = min(picture.shape[1], round(picture.shape[0] * size[0] / size[1]))
        print(f"{verdict(faces, crop, full)}. Saved {out}")
        return 0
    clear, closer, blocked = scan_clip(a.source, size, zone, a.start, a.end)
    if a.what == "scan":
        print(f"CLEAR (the whole picture) at: {', '.join(map(str, clear)) or 'none'}")
        print(f"CLEAR ONLY ZOOMED IN at: {', '.join(map(str, closer)) or 'none'}")
        print(f"FACE IN THE WAY at: {', '.join(map(str, blocked)) or 'none'}")
        return 0
    # sheet: candidate photos from the clip's clear moments, whole-picture ones first, and one picture of them all
    folder = a.more[0]
    os.makedirs(folder, exist_ok=True)
    name = os.path.splitext(os.path.basename(a.source))[0]
    picks = spread(clear, a.count)
    picks += spread([t for t in closer if all(abs(t - p) >= 1.5 for p in picks)], a.count - len(picks))
    if not picks:
        print("NONE: every moment in this clip has a face in the way. Use another clip or photo.")
        return 0
    paths, labels = [], []
    for t in sorted(picks):
        out = os.path.join(folder, f"{name}-{t:.1f}.jpg")
        result = make_still(a.source, t, out, size, zone)
        print(f"{t:.1f}s: {result}" + (f". Saved {out}" if result.startswith("CLEAR") else ""))
        if not result.startswith("CLEAR"):
            os.remove(out)
            continue
        paths.append(out)
        labels.append(f"{name} {t:.1f}s" + (" zoomed" if "zoomed" in result else ""))
    if not paths:
        print("NONE: no photo from this clip keeps every face clear and still shows the treatment. Use another clip "
              "or photo, or ask them for one.")
        return 0
    sheet = os.path.join(folder, f"{name}-sheet.jpg")
    contact_sheet(paths, labels, zone, sheet)
    print(f"SHEET: {sheet} (look at it: use only photos that clearly show the treatment, with no face inside the "
          f"blue box and no face cut off at an edge)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
