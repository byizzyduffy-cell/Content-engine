"""
Makes the engine's sound effects from scratch with FFmpeg, so there are no
sound files to buy or license. Each one is a recipe: tones and noise shaped
to sound like a pop, a chime, a whoosh and so on.

    python3 engine/make_sounds.py

The sounds are saved in engine/sounds. To change one, change its recipe and run
this again. To use a sound you've bought or recorded instead, drop the file in
engine/sounds with the same name.
"""

import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
SOUNDS = os.path.join(HERE, "sounds")


def ping(freq, at, decay, level):
    """One short tone starting at `at` seconds, fading away."""
    return f"{level}*sin(2*PI*{freq}*(t-{at}))*exp(-{decay}*(t-{at}))*gte(t,{at})"


def bell(at, level):
    """A bright metallic strike, made of several tones that don't quite match."""
    partials = [(2093, 1.0), (2711, 0.7), (3520, 0.5), (4186, 0.4)]
    return "+".join(ping(f, at, 9, round(level * w, 3)) for f, w in partials)


# name: (seconds, sound recipe, finishing touches)
RECIPES = {
    "pop": (0.2, "0.7*sin(2*PI*(260*t+5200*t*t))*exp(-38*t)", "lowpass=f=5000"),
    "soft-pop": (0.22, "0.8*sin(2*PI*(180*t+2400*t*t))*exp(-30*t)", "lowpass=f=2500"),
    "bubble": (0.24,
               "0.6*sin(2*PI*(500*t+6000*t*t))*exp(-50*t)*lt(t,0.09)"
               "+0.6*sin(2*PI*(800*(t-0.07)+9000*(t-0.07)*(t-0.07)))*exp(-50*(t-0.07))*gte(t,0.07)",
               "lowpass=f=6000"),
    "click": (0.06, "0.8*sin(2*PI*2200*t)*exp(-400*t)+0.25*sin(2*PI*5300*t)*exp(-700*t)", "highpass=f=600"),
    "chime": (1.2,
              "0.3*(sin(2*PI*1318.5*t)+0.6*sin(2*PI*1975.5*t)+0.3*sin(2*PI*2637*t))*exp(-4.5*t)*(1-exp(-300*t))",
              "lowpass=f=8000"),
    "sparkle": (0.7, "+".join(ping(f, at, 22, 0.28) for f, at in
                              [(2637, 0), (3136, 0.05), (3951, 0.1), (4699, 0.16), (5274, 0.22)]),
                "lowpass=f=9000"),
    "cha-ching": (1.0, bell(0, 0.16) + "+" + bell(0.13, 0.22), "lowpass=f=9000"),
    "typing": (1.3, "+".join(ping(f, round(0.055 * i + 0.012 * (i % 3), 3), 320, 0.4) for i, f in
                             enumerate([2100, 2500, 1900, 2300, 2050, 2450, 1950, 2350] * 3)),
               "highpass=f=900,lowpass=f=7000"),
    "tap": (0.12, "0.8*sin(2*PI*(720*t-900*t*t))*exp(-55*t)+0.2*sin(2*PI*1450*t)*exp(-90*t)", "lowpass=f=3000"),
    # Added for stickers (2026-10-10).
    "ding": (0.9, bell(0, 0.3), "lowpass=f=9000"),
    "wrong": (0.45, "0.45*(sin(2*PI*155*t)+0.5*sin(2*PI*310*t)+0.35*sin(2*PI*465*t)+0.2*sin(2*PI*620*t))"
                    "*(lt(t,0.15)+gte(t,0.23)*lt(t,0.4))", "lowpass=f=1800,afade=out:st=0.36:d=0.06"),
    "boing": (0.6, "0.7*sin(2*PI*190*t+7*sin(2*PI*15*t)*exp(-5*t))*exp(-5*t)", "lowpass=f=2500"),
    "message": (0.42, "0.4*sin(2*PI*1046.5*t)*exp(-16*t)*lt(t,0.14)"
                      "+0.4*sin(2*PI*1568*(t-0.1))*exp(-12*(t-0.1))*gte(t,0.1)", "lowpass=f=6000"),
    "rise": (0.5, "0.5*sin(2*PI*(320*t+760*t*t))*(1-exp(-25*t))*exp(-3*t)", "lowpass=f=4000,afade=out:st=0.38:d=0.12"),
}

# Sounds made from shaped noise: (seconds, noise colour, how it's shaped).
NOISES = {
    "whoosh": (0.55, "pink", "highpass=f=350,lowpass=f=3500,afade=in:d=0.3:curve=qsin,afade=out:st=0.3:d=0.25:curve=qsin"),
    "scribble": (0.45, "white", "bandpass=f=3200:width_type=h:w=1800,tremolo=f=13:d=0.85,"
                                "afade=in:d=0.03,afade=out:st=0.3:d=0.15"),
    "tape": (0.32, "brown", "highpass=f=700,lowpass=f=6000,tremolo=f=38:d=0.9,"
                            "afade=in:d=0.02,afade=out:st=0.14:d=0.18:curve=exp"),
}


def make_noise(path, seconds, colour, shape):
    """Noise shaped into a sound: a whoosh sweeping past, a pen scribbling, tape being torn."""
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
         "-i", f"anoisesrc=d={seconds}:color={colour}:amplitude=0.6:seed=7",
         "-af", shape, "-ar", "48000", path],
        check=True,
    )


def even_out(path, loudest=-3.0):
    """Turn the sound up or down so its loudest moment matches the others."""
    result = subprocess.run(["ffmpeg", "-i", path, "-af", "volumedetect", "-f", "null", "-"],
                            capture_output=True, text=True)
    peak = float(result.stderr.split("max_volume: ")[1].split(" dB")[0])
    temp = path + ".tmp.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", path, "-af", f"volume={loudest - peak}dB", temp], check=True)
    os.replace(temp, path)


def main():
    os.makedirs(SOUNDS, exist_ok=True)
    for name, (seconds, recipe, touches) in RECIPES.items():
        path = os.path.join(SOUNDS, f"{name}.wav")
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"aevalsrc='{recipe}':s=48000:d={seconds}",
             "-af", f"afade=in:d=0.004,{touches},alimiter=limit=0.9", path],
            check=True,
        )
        even_out(path)
        print(f"Made {name}.wav")
    for name, (seconds, colour, shape) in NOISES.items():
        path = os.path.join(SOUNDS, f"{name}.wav")
        make_noise(path, seconds, colour, shape)
        even_out(path)
        print(f"Made {name}.wav")


if __name__ == "__main__":
    main()
