"""
Review bubbles and a phone full of review notifications.

Two looks for client review carousels that show reviews as clean white
bubbles rather than full Google cards (post library: "Review bubbles"):

  bubble   a white rounded card with five gold stars and the review's exact
           words, sized to fit the words. Every bubble in a set uses the same
           text size, so they match when you swipe.
  phone    an iPhone "Notification Centre" screen full of "New review for
           <clinic>" notifications from Google, to go inside a phone frame.

    python3 engine/review_bubble.py bubble <reviews.md> "Amira K." "Sophie T." --width 632 --out <folder>
    python3 engine/review_bubble.py phone <reviews.md> "Amira K." ... --clinic "Your Clinic" --photo <photo> --out phone.png

The review's words are never changed. Bubbles are drawn at twice the size they
sit at on the slide, so they stay sharp; the file name says the size to give the
picture in Canva (e.g. bubble-01-632x184.png).
"""

import tools  # noqa: F401  (first: emoji-safe output on Windows)
import argparse
import os

from PIL import Image, ImageDraw, ImageFilter

from review_card import font, google_g, read_reviews, star_points, wrap

SCALE = 2                     # pictures are drawn at twice the size they sit at

# Bubble look (sizes at 1x, on a 1080 x 1350 slide).
PAD = 22                      # space inside the bubble
RADIUS = 22                   # rounded corners
STAR = 11                     # radius of each gold star
STAR_GAP = 4
TEXT_SIZE = 21                # the review's words
LINE = 1.36                   # line spacing
WORDS = "#333333"
STAR_GOLD = "#F5B400"
SCROLL = "#B8B8B8"            # the little scroll bar on the right, like a real screenshot


def stars(draw, x, y, r, gap):
    for i in range(5):
        cx = x + r + i * (2 * r + gap)
        draw.polygon(star_points(cx, y + r, r), fill=STAR_GOLD)


def bubble_lines(text, size, width):
    f = font(size)
    lines = []
    for para in text.split("\n"):
        lines += wrap(para, f, width) if para.strip() else [""]
    return lines


def make_bubble(text, width, out_dir, n, size=TEXT_SIZE):
    """One bubble, `width` wide at 1x; its height fits the words."""
    s = SCALE
    w = width * s
    pad, r = PAD * s, RADIUS * s
    f = font(size * s)
    inner = w - 2 * pad - 12 * s            # leave room for the scroll bar
    lines = bubble_lines(text, size * s, inner)
    line_h = round(size * s * LINE)
    star_r = STAR * s
    h = pad + 2 * star_r + round(10 * s) + line_h * len(lines) + pad - round(size * s * (LINE - 1))
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=r, fill="#FFFFFF")
    stars(d, pad, pad, star_r, STAR_GAP * s)
    y = pad + 2 * star_r + round(10 * s)
    for line in lines:
        d.text((pad, y), line, font=f, fill=WORDS)
        y += line_h
    # A thin scroll bar near the top right, as on a phone screenshot.
    bar_top = pad + 2 * star_r + round(14 * s)
    d.rounded_rectangle((w - pad // 2 - 3 * s, bar_top, w - pad // 2, bar_top + min(h // 3, 70 * s)),
                        radius=2 * s, fill=SCROLL)
    name = f"bubble-{n:02d}-{width}x{h // s}.png"
    im.save(os.path.join(out_dir, name))
    return name, h // s


def shared_bubble_size(texts, width):
    """One text size for the whole set: as big as TEXT_SIZE, smaller only if a review is very long."""
    size = TEXT_SIZE
    while size > 16:
        if all(len(bubble_lines(t, size, width - 2 * PAD - 12)) <= 16 for t in texts):
            return size
        size -= 1
    return size


def notification_lines(text, f, width, first_indent, most=3):
    """A notification's preview: up to three lines, the first starting after the stars, "…" if cut."""
    words, lines, line = text.split(), [], ""
    for w in words:
        room = width - (first_indent if not lines else 0)
        test = (line + " " + w).strip()
        if f.getlength(test) <= room:
            line = test
            continue
        lines.append(line)
        line = w
        if len(lines) == most:
            break
    else:
        lines.append(line)
        return lines
    lines[-1] = lines[-1].rstrip(" .,!") + "…"
    return lines


# Phone look (sizes at 1x for a 453 x 955 screen).
def make_phone(reviews, clinic, photo, out, width=453, height=955):
    s = SCALE
    W, H = width * s, height * s
    if photo and os.path.exists(photo):
        bg = Image.open(photo).convert("RGB")
        k = max(W / bg.width, H / bg.height)
        bg = bg.resize((round(bg.width * k), round(bg.height * k)))
        left, top = (bg.width - W) // 2, (bg.height - H) // 2
        bg = bg.crop((left, top, left + W, top + H)).filter(ImageFilter.GaussianBlur(28 * s))
    else:
        bg = Image.new("RGB", (W, H), "#6E6A66")
    shade = Image.new("RGB", (W, H), "#1E1E1E")
    im = Image.blend(bg, shade, 0.45).convert("RGBA")
    d = ImageDraw.Draw(im)

    # Status bar and title.
    d.text((34 * s, 22 * s), "9:41", font=font(15 * s, "SemiBold"), fill="#FFFFFF")
    bx = W - 34 * s
    d.rounded_rectangle((bx - 24 * s, 26 * s, bx, 37 * s), radius=3 * s, outline="#FFFFFF", width=s)
    d.rounded_rectangle((bx - 22 * s, 28 * s, bx - 6 * s, 35 * s), radius=2 * s, fill="#FFFFFF")
    d.text((22 * s, 60 * s), "Notification Centre", font=font(21 * s, "SemiBold"), fill="#FFFFFF")
    cx, cy, cr = W - 32 * s, 72 * s, 12 * s
    glass = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(glass).ellipse((cx - cr, cy - cr, cx + cr, cy + cr), fill=(255, 255, 255, 70))
    im = Image.alpha_composite(im, glass)
    d = ImageDraw.Draw(im)
    d.line((cx - 5 * s, cy - 5 * s, cx + 5 * s, cy + 5 * s), fill="#FFFFFF", width=2 * s)
    d.line((cx - 5 * s, cy + 5 * s, cx + 5 * s, cy - 5 * s), fill="#FFFFFF", width=2 * s)

    # The notifications.
    times = ["12m ago", "1h ago", "3h ago", "5h ago", "Yesterday", "Yesterday", "2d ago", "3d ago", "4d ago"]
    y = 100 * s
    m = 12 * s
    card_w = W - 2 * m
    small, bold = font(11 * s), font(11 * s, "SemiBold")
    body = font(11 * s)
    star_w = 48 * s                      # the five little stars before the first line
    for i, (name, text) in enumerate(reviews):
        lines = notification_lines(text.replace("\n", " "), body, card_w - 66 * s, star_w)
        card_h = (36 + 15 * len(lines) + 12) * s
        if y + card_h > H - 20 * s:
            break
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        ld.rounded_rectangle((m, y, m + card_w, y + card_h), radius=16 * s, fill=(245, 245, 245, 235))
        im = Image.alpha_composite(im, layer)
        d = ImageDraw.Draw(im)
        # Google app icon.
        icon = 30 * s
        ix, iy = m + 10 * s, y + 12 * s
        d.rounded_rectangle((ix, iy, ix + icon, iy + icon), radius=8 * s, fill="#FFFFFF", outline="#E2E2E2")
        g = google_g(20 * s)
        im.alpha_composite(g, (ix + (icon - g.width) // 2, iy + (icon - g.height) // 2))
        d = ImageDraw.Draw(im)
        tx = ix + icon + 10 * s
        d.text((tx, y + 9 * s), "Google", font=small, fill="#555555")
        d.text((m + card_w - 10 * s, y + 9 * s), times[i % len(times)], font=small, fill="#777777", anchor="ra")
        d.text((tx, y + 22 * s), f"New review for {clinic}", font=bold, fill="#111111")
        sy = y + 39 * s
        stars(d, tx, sy, 4 * s, 1 * s)
        d.text((tx + star_w, sy - 3 * s), lines[0], font=body, fill="#222222")
        for k, line in enumerate(lines[1:], 1):
            d.text((tx, sy - 3 * s + 15 * s * k), line, font=body, fill="#222222")
        y += card_h + 8 * s
    im.convert("RGB").save(out)
    return out


def main():
    p = argparse.ArgumentParser(description="Review bubbles and a phone full of review notifications.")
    p.add_argument("look", choices=["bubble", "phone"])
    p.add_argument("reviews", help="the reviews.md file")
    p.add_argument("names", nargs="+", help="which reviewers, as written in reviews.md")
    p.add_argument("--width", type=int, default=632, help="bubble width on the slide (1x)")
    p.add_argument("--clinic", default="Your Clinic")
    p.add_argument("--photo", help="a clinic photo for the phone's blurred background")
    p.add_argument("--out", required=True)
    a = p.parse_args()
    all_reviews = read_reviews(a.reviews)
    picked = []
    for n in a.names:
        if n not in all_reviews:
            raise SystemExit(f"PROBLEM: no review from {n} in {a.reviews}")
        picked.append((n, all_reviews[n]))
    if a.look == "phone":
        print("SAVED:", make_phone(picked, a.clinic, a.photo, a.out))
        return
    os.makedirs(a.out, exist_ok=True)
    size = shared_bubble_size([t for _, t in picked], a.width)
    for i, (_, text) in enumerate(picked, 1):
        name, h = make_bubble(text, a.width, a.out, i, size)
        print(f"SAVED: {name} (give it {a.width} x {h} on the slide)")


if __name__ == "__main__":
    main()
