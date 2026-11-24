"""
Finds the face in a talking head, so the captions (and later the pop-ups and
stickers) know where the head and chin are, and the zooms know where to aim.

    .venv/bin/python engine/face.py "VIDEO.mp4"

It looks twice a second through the whole video and sums up where the face
goes: the lowest the chin gets, the highest the top of the head gets, and
where the face usually is. Captions under the chin go below the lowest chin;
captions above the head go above the highest head, so they never touch the face
even when the person leans in or sits up.

Uses YuNet, a small open-source face finder (MIT licence, see
models/licences/YuNet-MIT.txt), through OpenCV.
"""

import tools  # noqa: F401  (first: emoji-safe output on Windows)
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = os.path.join(HERE, "models", "face_detection_yunet_2023mar.onnx")

EVERY = 0.5           # look for the face this often (seconds)
LOOK_WIDTH = 540      # frames are shrunk to this width to look (quicker, and plenty for a face)
SURE = 0.6            # how sure the finder must be that it's a face (0 to 1)
HAIR = 0.2            # the top of the head is this much of the face's height above the face box, for hair
FOUND_ENOUGH = 0.3    # a face in fewer than this share of the looks means there's no face to work around


def video_size(video):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=width,height:stream_side_data=rotation", "-of", "json", video],
                       capture_output=True, text=True)
    stream = json.loads(r.stdout)["streams"][0]
    width, height = stream["width"], stream["height"]
    rotation = next((abs(int(d.get("rotation", 0))) for d in stream.get("side_data_list", [])), 0)
    return (height, width) if rotation in (90, 270) else (width, height)


def faces(video, every=EVERY):
    """Every look at the video: (seconds, face), where face is a dict of fractions of the
    frame (top, bottom, left, right, eyes), or None when no face was found."""
    import cv2
    import numpy as np
    width, height = video_size(video)
    w = LOOK_WIDTH
    h = round(height * w / width / 2) * 2
    finder = cv2.FaceDetectorYN.create(MODEL, "", (w, h), SURE, 0.3, 5000)
    reader = subprocess.Popen(["ffmpeg", "-v", "error", "-i", video, "-vf", f"fps={1 / every:g},scale={w}:{h}",
                               "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], stdout=subprocess.PIPE)
    looks, n = [], 0
    while True:
        buf = reader.stdout.read(w * h * 3)
        if len(buf) < w * h * 3:
            break
        frame = np.frombuffer(buf, np.uint8).reshape(h, w, 3)
        _, found = finder.detect(frame)
        face = None
        if found is not None and len(found):
            x, y, fw, fh = max(found, key=lambda f: f[2] * f[3])[:4]   # the biggest face is the speaker
            eyes = max(found, key=lambda f: f[2] * f[3])[5:8:2]
            face = {"top": y / h, "bottom": (y + fh) / h, "left": x / w, "right": (x + fw) / w,
                    "eyes": float(np.mean(eyes)) / h}
        looks.append((round(n * every, 2), face))
        n += 1
    reader.wait()
    return looks


def head_and_chin(found):
    """From the faces found in a stretch of video: (chin, head_top), the lowest the chin
    gets and the highest the top of the head gets, ignoring the odd stray look."""
    import numpy as np
    tops = [f["top"] - HAIR * (f["bottom"] - f["top"]) for f in found]
    return (round(float(np.percentile([f["bottom"] for f in found], 85)), 3),
            round(max(0.0, float(np.percentile(tops, 10))), 3))


def where(video):
    """Where the face goes over the whole video, or None if there's no face to speak of.
    chin: the lowest the chin gets. head_top: the highest the top of the head gets.
    centre: where the face usually is (across, down). All as fractions of the frame."""
    import numpy as np
    looks = faces(video)
    found = [f for _, f in looks if f]
    if not looks or len(found) < FOUND_ENOUGH * len(looks):
        return None
    chin, head_top = head_and_chin(found)
    return {
        "chin": chin,
        "head_top": head_top,
        "centre": [round(float(np.median([(f["left"] + f["right"]) / 2 for f in found])), 3),
                   round(float(np.median([(f["top"] + f["bottom"]) / 2 for f in found])), 3)],
        "found": round(len(found) / len(looks), 2),
    }


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit('Say which video: .venv/bin/python engine/face.py "VIDEO.mp4"')
    print(json.dumps(where(sys.argv[1]), indent=1))
