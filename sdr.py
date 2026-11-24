"""
Turns iPhone HDR videos into normal colour before the engine uses them.

Most iPhones film in HDR by default (Settings, Camera, Record Video, HDR Video).
Used as it is, that footage comes out about a quarter too bright and flat
(tested 2026-10-12 on Frances's clip IMG_4552). So every video the engine reads
goes through normal_colour() first: normal videos are used as they are; HDR
ones are converted once, and the converted copy is kept next to the original
(in a ".normal-colour" folder) for next time.

- On a Mac: Apple's own converter (avconvert, built into every Mac), which
  gives the same colours the Mac itself shows. 1080 x 1920, like the reels.
- On Windows: FFmpeg's tone mapping (zscale and tonemap, in the FFmpeg that
  set me up installs). Not yet tested on a real Windows laptop.
- If neither is there, the video is used as it is, with a note.
"""

import os
import platform
import shutil
import subprocess

HDR_CURVES = {"arib-std-b67", "smpte2084"}     # HLG (iPhone HDR) and PQ (other HDR)
FOLDER = ".normal-colour"


def is_hdr(video):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=color_transfer", "-of", "csv=p=0", video], capture_output=True, text=True)
    return out.stdout.strip().split(",")[0] in HDR_CURVES    # (iPhone videos add a trailing comma)


def _ffmpeg_has(name):
    out = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True)
    return f" {name} " in out.stdout


def normal_colour(video):
    """The video in normal colour: the original when it already is, otherwise a converted copy."""
    if not video or not os.path.exists(video) or not is_hdr(video):
        return video
    folder = os.path.join(os.path.dirname(os.path.abspath(video)), FOLDER)
    out = os.path.join(folder, os.path.splitext(os.path.basename(video))[0] + ".mov")
    if os.path.exists(out) and os.path.getmtime(out) >= os.path.getmtime(video):
        return out
    os.makedirs(folder, exist_ok=True)
    if platform.system() == "Darwin" and shutil.which("avconvert"):
        done = subprocess.run(["avconvert", "--source", video, "--preset", "Preset1920x1080", "--output", out,
                               "--replace"], capture_output=True, text=True)
    elif _ffmpeg_has("zscale") and _ffmpeg_has("tonemap"):
        chain = ("zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=tonemap=hable:desat=0,"
                 "zscale=t=bt709:m=bt709:r=tv,format=yuv420p,scale=1080:1920:force_original_aspect_ratio=decrease")
        done = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", video, "-vf", chain, "-c:v", "libx264", "-crf", "16",
                               "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
                               "-c:a", "aac", "-b:a", "192k", out], capture_output=True, text=True)
    else:
        print("Note: this video was filmed in HDR and can't be converted on this computer, so its colours may look a little light.")
        return video
    if done.returncode != 0 or not os.path.exists(out):
        print("Note: couldn't convert this HDR video, so its colours may look a little light.")
        return video
    return out
