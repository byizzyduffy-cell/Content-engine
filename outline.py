"""
Finds the outline of the head and hair in a frame, so things can sit behind the
head (Frances, 2026-10-10: emojis "sitting behind the head... gives the content
a bit of depth").

It starts from where the face finder says the face is, then lets OpenCV's
GrabCut separate the head and hair from the wall by their colours. No extra
download: it's part of OpenCV (Apache 2.0). It only looks at the area around
the head, at half size, so it's quick enough to run on every frame of a short
moment.
"""

import cv2
import numpy as np

SCALE = 0.5           # work at half size
ROUNDS = 3            # GrabCut passes per frame
FEATHER = 5           # soften the edge of the outline (pixels, full size)
CROWN = 0.32          # the top of the head is never more than this much of the face's height above the face


def head_mask(frame, face, region=None):
    """How much of each pixel is head or hair (0 to 1), for a full-size frame (blue-green-red).
    face: the face box as fractions of the frame (dict with left, right, top, bottom).
    region: (top, bottom) rows to work on, to save time; the rest of the mask is 0."""
    h, w = frame.shape[:2]
    x0f, x1f = face["left"] * w, face["right"] * w
    y0f, y1f = face["top"] * h, face["bottom"] * h
    fw, fh = x1f - x0f, y1f - y0f
    # The area that could hold the head and hair, with room around it.
    top = int(max(0, y0f - fh * 0.9))
    bottom = int(min(h, y1f + fh * 0.2))
    left = int(max(0, x0f - fw * 0.9))
    right = int(min(w, x1f + fw * 0.9))
    if region:
        top, bottom = max(top, region[0]), min(bottom, region[1])
        if bottom - top < 8:
            return np.zeros((h, w), np.float32)
    crop = cv2.resize(frame[top:bottom, left:right], None, fx=SCALE, fy=SCALE)
    ch, cw = crop.shape[:2]

    def at(x, y):
        return int((x - left) * SCALE), int((y - top) * SCALE)

    mask = np.full((ch, cw), cv2.GC_PR_BGD, np.uint8)
    cx, cy = at((x0f + x1f) / 2, (y0f + y1f) / 2)
    cv2.ellipse(mask, (cx, cy), (int(fw * 0.75 * SCALE), int(fh * 0.95 * SCALE)), 0, 0, 360, cv2.GC_PR_FGD, -1)
    a, b = at(x0f + fw * 0.2, y0f + fh * 0.25)
    c, d = at(x0f + fw * 0.8, y0f + fh * 0.9)
    cv2.rectangle(mask, (a, max(0, b)), (c, d), cv2.GC_FGD, -1)
    sure_top = at(0, y0f - fh * 0.55)[1]
    if sure_top > 0:
        mask[:sure_top, :] = cv2.GC_BGD
    mask[:, :max(0, at(x0f - fw * 0.85, 0)[0])] = cv2.GC_BGD
    mask[:, at(x1f + fw * 0.85, 0)[0]:] = cv2.GC_BGD
    background, foreground = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
    try:
        cv2.grabCut(crop, mask, None, background, foreground, ROUNDS, cv2.GC_INIT_WITH_MASK)
    except cv2.error:
        pass
    found = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 1.0, 0.0).astype(np.float32)
    # Only trust it inside a generous head shape, so a patch of wall that looks like hair
    # is never counted as head.
    limit = np.zeros((ch, cw), np.float32)
    crown = at(0, y0f - fh * CROWN)[1]
    cv2.ellipse(limit, (cx, cy), (int(fw * 0.85 * SCALE), max(1, cy - crown)), 0, 0, 360, 1.0, -1)
    found *= limit
    found = cv2.resize(found, (right - left, bottom - top), interpolation=cv2.INTER_LINEAR)
    found = cv2.GaussianBlur(found, (0, 0), FEATHER)
    out = np.zeros((h, w), np.float32)
    out[top:bottom, left:right] = found
    return out
