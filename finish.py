"""
Talking-head editor, the finishing step: puts everything on the tidy video in
one go (captions and pop-ups now; emoji stickers and the hook as they're
built) and mixes in the sound for each graphic.

    .venv/bin/python engine/finish.py "TIDY.mp4" --work "FOLDER" --out "FINISHED.mp4" \\
        --pack elegant --accent "#FFF3B0" --captions pop --position chin \\
        --hook hook.json --notes notes.json --stickers stickers.json --popups none

The tidy video comes from talking_head.py (cut), the word timings from its
timeline.json, and the pop-up words from popups.json (written by Claude).
Any part can be left off with "none". The student's choices come from the
Talking Head Lookbook.
"""

import tools  # noqa: F401  (first: emoji-safe output on Windows)
import argparse
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import captions  # noqa: E402
import packs  # noqa: E402
import popups  # noqa: E402
import hook as hooks  # noqa: E402
import notes as handwritten  # noqa: E402
import stickers as sticking  # noqa: E402

W, H, FPS = captions.W, captions.H, captions.FPS


def run(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(f"This step didn't work:\n{' '.join(cmd)}\n\n{result.stderr[-1500:]}")


def mix_sounds(video, sounds, path):
    """The video's own sound with each graphic's sound laid in at its moment, a little
    under the voice, and a limiter so nothing ever clips."""
    if not sounds:
        run(["ffmpeg", "-v", "error", "-y", "-i", video, "-vn", "-c:a", "pcm_s16le", path])
        return
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", video]
    for sound in sounds:
        cmd += ["-i", sound[1]]
    fmt = "aformat=sample_rates=48000:channel_layouts=stereo"
    graph = [f"[0:a]{fmt}[voice]"]
    for k, sound in enumerate(sounds):
        t, level = sound[0], (sound[2] if len(sound) > 2 else popups.SOUND_LEVEL)
        ms = max(0, round(t * 1000))
        graph.append(f"[{k + 1}:a]{fmt},volume={level},adelay={ms}|{ms}[s{k}]")
    graph.append("[voice]" + "".join(f"[s{k}]" for k in range(len(sounds))) +
                 f"amix=inputs={len(sounds) + 1}:normalize=0:duration=first,alimiter=limit=0.95[out]")
    run(cmd + ["-filter_complex", ";".join(graph), "-map", "[out]", "-c:a", "pcm_s16le", path])


def make(video, work, out, caption_design="pop", position="chin", popup_design=None, chin=None, head_top=None,
         popup_move="pop", popup_words="popups.json", popup_font=None, pack=packs.DEFAULT, notes=None,
         accent=None, stickers=None, hook=None, hook_style=None, popup_style=handwritten.DEFAULT_POPUP_STYLE,
         headline=None, writing=None, caption_font=None, voiceover=False, hook_place=None, caption_colour=None,
         plain_captions=False, palette=None, popups_below=False, caption_scale=1.0, popup_scale=1.0,
         hook_lines=None):
    """The finished talking head, in the clinic's brand pack (packs.PACKS: the headline,
    pop-up and caption fonts) and brand colour (accent).
    hook: the file in the work folder with the hook (hook.py); hook_style overrides its style, and
    hook_place says where it sits (hook.PLACES: top, middle or lower, always clear of the face and captions).
    notes: the file with the pop-up words (notes.py), Frances's approved pop-ups.
    stickers: the file with the stickers (stickers.py), each with its matching sound.
    popup_design (and popup_move, popup_font, popup_words): the older pop-up looks from
    popups.py, retired from the lookbook; leave as None or "none".
    popup_style: how the pop-up words come up (notes.POPUP_STYLES).
    headline, writing, caption_font: the student's own font picks, replacing the pack's
    (packs.HEADLINES, packs.POPUP_WRITING, packs.CAPTION_FONTS).
    caption_colour: the colour that marks the word being said (its box, or the word itself), when a brighter
    look is wanted than the signed-off beige (Frances, 2026-10-20: "quite bright, bold"). Left out, the
    captions are exactly as signed off.
    plain_captions: the captions' letters with no shadow and no outline (Frances, 2026-10-20: "just the plainest
    text possible").
    palette: {"light", "accent", "background"}: a clinic's own colours, and no others, for the captions' writing,
    the hook and the pop-ups (notes.use_palette).
    popups_below: the hook, pop-ups and emoji trios go below the face, under the captions, even with the captions
    under the chin (Frances, 2026-10-20: "some of the pop-ups are going over my head"; her car videos frame her
    head high, with no room above it). caption_scale: smaller (or bigger) captions, e.g. 0.75.
    popup_scale: smaller (or bigger) pop-up words, e.g. 0.85. hook_lines: how many lines the hook goes on
    (Frances, 2026-10-20: "the hook in 2 lines not 3"); hook.json's own "lines" wins."""
    the_pack = packs.own_pack(pack, headline, writing, caption_font)
    if palette:
        handwritten.use_palette(palette["light"], palette["accent"], palette["background"])
        accent = palette["accent"]
    words = captions.load_words(work)
    # A voiceover has no speaker's face (and clients' faces in the clips mustn't be followed).
    where = {} if voiceover else captions.find_face(video, chin, head_top)
    # Frances's rule: if the captions are above the head, the hook, pop-ups and emojis go below the face.
    below = (caption_design != "none" and position in ("above", "top")) or popups_below
    layers, hook_end = [], 0.0
    captioner = None
    if caption_design != "none":
        design = dict(captions.DESIGNS[caption_design])
        if caption_font:   # a caption font they picked themselves always wins
            design["font"] = packs.CAPTION_FONTS[caption_font]["font"]
        elif not design.get("signature"):
            design["font"] = the_pack["caption"]   # the brand pack's caption font
        if plain_captions:
            design["plain"] = True
        if caption_scale != 1.0:
            design["size"] = round(design["size"] * caption_scale)
        if palette:
            design["colour"] = palette["light"]
        if caption_colour:
            design["accent"] = caption_colour
            if design.get("accent_text"):        # the word inside a coloured box: dark on light, white on dark
                r, g, b = (int(caption_colour.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
                design["accent_text"] = captions.CHARCOAL if 0.299 * r + 0.587 * g + 0.114 * b > 150 else captions.WHITE
        captioner = captions.Captioner(words, design, position, **where)
    if hook:
        the_hook = hooks.Hook(work, hook, faces=where.get("looks"), pack=pack, accent=accent, style=hook_style,
                              fonts=the_pack, below=below, place=hook_place, captions=captioner, lines=hook_lines)
        layers.append(the_hook)
        hook_end = the_hook.end + 0.3
    busy = [(0.0, hook_end)] if hook else []
    if notes:
        layers.append(handwritten.Notes(work, words, notes, faces=where.get("looks"),
                                        still=lambda t: captions.still(video, t), seed=os.path.basename(work),
                                        pack=pack, accent=accent, not_before=hook_end, style=popup_style,
                                        fonts=the_pack, below=below, captions=captioner, size=popup_scale))
    if notes:
        busy += [(p["start"], p["end"]) for p in layers[-1].popups]
    if stickers:
        single_y = None
        if voiceover:   # single stickers sit clear of the captions
            single_y = {"middle": 0.68, "low": 0.5, "top": 0.5}.get(position, 0.68)
        layers.append(sticking.Stickers(work, words, stickers, faces=where.get("looks"), busy=busy, below=below,
                                        single_y=single_y))
    if captioner:
        layers.append(captioner)
    pops = popups.load_popups(work, words, popup_words) if popup_design != "none" else None
    if pops:
        layers.append(popups.Popper(pops, popup_design or "box", popup_move, faces=where.get("looks"), font=popup_font,
                                    pack=None,
                                    captions_above=(caption_design != "none" and position == "above")))
    sounds = [s for layer in layers for s in getattr(layer, "sounds", [])]
    tmp = tempfile.mkdtemp(prefix="finish-")
    try:
        sound = os.path.join(tmp, "sound.wav")
        mix_sounds(video, sounds, sound)
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        writer = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                                   "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", sound,
                                   "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "medium",
                                   "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                                   "-movflags", "+faststart", out], stdin=subprocess.PIPE)
        for n, frame in enumerate(captions.frames_in(video)):
            for layer in layers:
                frame = layer.draw_on(frame, n / FPS)
            writer.stdin.write(frame.tobytes())
        writer.stdin.close()
        if writer.wait() != 0:
            raise SystemExit("Saving the finished video didn't work.")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    parts = [f"captions: {captions.DESIGNS[caption_design]['name']}" if caption_design != "none" else "no captions",
             (f"{len(pops)} pop-ups: {popups.POPUP_DESIGNS[popup_design]['name']}, "
              f"{popups.MOVES[popup_move]['name'].lower()}" if popup_design else
              f"{len(pops)} pop-ups taking turns") if pops else "no pop-ups",
             f"{the_pack['name']} pack"]
    print(f"Finished ({', '.join(parts)}). Saved {out}")


def preview_popups(video, work, out, keys, caption_design="pop", position="chin", compare="looks"):
    """One still with each pop-up design on it, side by side, labelled A, B, C..., for
    the student to pick from (made from their own video)."""
    from PIL import Image, ImageDraw
    words = captions.load_words(work)
    pops = popups.load_popups(work, words)
    if not pops:
        raise SystemExit("There's no popups.json yet: Claude writes the pop-up words first.")
    where = captions.find_face(video)
    pick = pops[min(1, len(pops) - 1)]
    t = pick["start"] + 0.6   # fully popped in
    base = captions.still(video, t)
    if compare == "fonts":   # each writing style on the look that suits it
        choices = [(popups.POPUP_FONTS[k]["name"], popups.POPUP_FONTS[k]["show_with"], k) for k in keys]
    else:
        choices = [(popups.POPUP_DESIGNS[k]["name"], k, None) for k in keys]
    tile_w, tile_h, label_h, gap = 360, 640, 70, 24
    across = min(4, len(choices))
    rows = (len(choices) + across - 1) // across
    sheet = Image.new("RGB", (across * (tile_w + gap) + gap, rows * (tile_h + label_h + gap) + gap), "#F4F0EC")
    label_font = captions.load_font("Poppins", 30, "caption")
    draw = ImageDraw.Draw(sheet)
    for n, (label, key, font) in enumerate(choices):
        frame = base.copy()
        if caption_design != "none":
            frame = captions.Captioner(words, captions.DESIGNS[caption_design], position, **where).draw_on(frame, t)
        fresh = [dict(p) for p in pops]
        frame = popups.Popper(fresh, key, "pop", faces=where.get("looks"), font=font,
                              captions_above=(position == "above")).draw_on(frame, t)
        tile = Image.fromarray(frame).resize((tile_w, tile_h), Image.LANCZOS)
        x = gap + (n % across) * (tile_w + gap)
        y = gap + (n // across) * (tile_h + label_h + gap)
        sheet.paste(tile, (x, y))
        draw.text((x + tile_w / 2, y + tile_h + label_h / 2), f"{chr(65 + n)}  {label}",
                  font=label_font, fill=captions.CHARCOAL, anchor="mm")
    sheet.save(out)
    print(f"Preview of {len(choices)} pop-up designs saved {out}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video", help="the tidy video from talking_head.py")
    ap.add_argument("--work", required=True, help="the same working folder used for the cut")
    ap.add_argument("--out", help="where to save the finished video")
    ap.add_argument("--preview", help="instead of a video, save a picture comparing pop-up designs")
    ap.add_argument("--compare", help="with --preview: which pop-up looks, e.g. box,tape (default: all)")
    ap.add_argument("--compare-fonts", dest="compare_fonts", action="store_true",
                    help="with --preview: compare the pop-up writing styles instead of the looks")
    ap.add_argument("--captions", choices=list(captions.DESIGNS) + ["none"], default="pop")
    ap.add_argument("--position", choices=list(captions.POSITIONS) + list(captions.VOICEOVER_POSITIONS),
                    default=None, help="where the captions sit (talking heads: above, chin, low; "
                                       "voiceovers: middle, top, low)")
    ap.add_argument("--voiceover", action="store_true",
                    help="a voiceover: no face finder, captions in the middle unless told otherwise")
    ap.add_argument("--pack", choices=list(packs.PACKS), default=packs.DEFAULT,
                    help="the brand pack: the headline, pop-up and caption fonts")
    ap.add_argument("--popups", choices=list(popups.POPUP_DESIGNS) + ["none"],
                    help="one fixed look for every pop-up instead of the pack's (or none)")
    ap.add_argument("--move", choices=list(popups.MOVES), default="pop", help="how the pop-ups arrive")
    ap.add_argument("--notes", help="the file in the work folder with the pop-up words (e.g. notes.json)")
    ap.add_argument("--hook", help="the file in the work folder with the hook (e.g. hook.json)")
    ap.add_argument("--hook-style", dest="hook_style", choices=list(hooks.STYLES),
                    help="how the hook arrives, if not the one in hook.json")
    ap.add_argument("--hook-place", dest="hook_place", choices=list(hooks.PLACES),
                    help="where the hook sits: top (the default), middle or lower")
    ap.add_argument("--accent", help="the clinic's brand colour for the pop-ups, e.g. #FFF3B0")
    ap.add_argument("--caption-colour", dest="caption_colour",
                    help="the colour that marks the word being said, e.g. #22D3EE (normally the signed-off beige)")
    ap.add_argument("--palette", help='only these colours: "light=#DDDDD8,accent=#AAAAAA,background=#2D2E30"')
    ap.add_argument("--popups-below", dest="popups_below", action="store_true",
                    help="the hook, pop-ups and emoji trios below the face, under the captions")
    ap.add_argument("--caption-scale", dest="caption_scale", type=float, default=1.0,
                    help="smaller or bigger captions, e.g. 0.75")
    ap.add_argument("--hook-lines", dest="hook_lines", type=int, help="how many lines the hook goes on, e.g. 2")
    ap.add_argument("--popup-scale", dest="popup_scale", type=float, default=1.0,
                    help="smaller or bigger pop-up words, e.g. 0.85")
    ap.add_argument("--plain-captions", dest="plain_captions", action="store_true",
                    help="captions with no shadow and no outline, just the letters")
    ap.add_argument("--stickers", help="the file in the work folder with the stickers (e.g. stickers.json)")
    ap.add_argument("--popup-style", dest="popup_style", choices=list(handwritten.POPUP_STYLES),
                    default=handwritten.DEFAULT_POPUP_STYLE, help="how the pop-up words come up")
    ap.add_argument("--headline", choices=list(packs.HEADLINES), help="the student's own headline font")
    ap.add_argument("--writing", choices=list(packs.POPUP_WRITING), help="the student's own pop-up font")
    ap.add_argument("--caption-font", dest="caption_font", choices=list(packs.CAPTION_FONTS),
                    help="the student's own caption font")
    ap.add_argument("--font", choices=list(popups.POPUP_FONTS), help="the pop-ups' writing, if not the look's own")
    ap.add_argument("--popup-words", dest="popup_words", default="popups.json",
                    help="the file in the work folder with the pop-up words (default popups.json)")
    ap.add_argument("--chin", type=float, help="where the chin is (0 to 1 down the screen), if the face finder gets it wrong")
    ap.add_argument("--head-top", dest="head_top", type=float, help="where the top of the head is, if the face finder gets it wrong")
    args = ap.parse_args()
    if args.position is None:
        args.position = "middle" if args.voiceover else "chin"
    if args.preview:
        if args.compare_fonts:
            keys = args.compare.split(",") if args.compare else list(popups.POPUP_FONTS)
            preview_popups(args.video, args.work, args.preview, keys, args.captions, args.position, "fonts")
        else:
            keys = args.compare.split(",") if args.compare else list(popups.POPUP_DESIGNS)
            preview_popups(args.video, args.work, args.preview, keys, args.captions, args.position)
        return
    if not args.out:
        raise SystemExit("Say where to save it with --out, or ask for a --preview.")
    make(args.video, args.work, args.out, args.captions, args.position, args.popups, args.chin, args.head_top,
         args.move, args.popup_words, args.font, args.pack, args.notes, args.accent, args.stickers,
         args.hook, args.hook_style, args.popup_style, args.headline, args.writing, args.caption_font,
         args.voiceover, args.hook_place, args.caption_colour, args.plain_captions,
         dict(part.split("=") for part in args.palette.replace(" ", "").split(",")) if args.palette else None,
         args.popups_below, args.caption_scale, args.popup_scale, args.hook_lines)


if __name__ == "__main__":
    main()
