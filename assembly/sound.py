"""
Tiny Lawn Tales - Sound maker (free, made by ffmpeg, no downloads, no licence).

Makes cartoon sound effects and a soft music bed from maths, so nothing is
downloaded and nothing can be claimed by anybody on YouTube.

Better sounds later, with no code change: put a file with the same name in
assets/sfx/ (for example assets/sfx/boing.wav) or put any music file in
assets/music/ (mp3, wav or ogg). Files there win over the made sounds.

Each shot in shot_list may carry a "sound" text such as "boing, ow squeak".
sounds_for_shot() turns that text into effect names. Words that mean music
(it contains "music") are skipped, the music bed covers them. Unknown words
are skipped with a printed note and never stop the video.

"""
import glob
import os
import random
import subprocess

SR = 44100

NOISE = "anoisesrc=d={d}:c={c}:a={a}:r=44100"
EFFECTS = {
    "boing": "aevalsrc='0.7*sin(2*PI*(260+240*sin(2*PI*5*t))*t)*exp(-4*t)':d=0.7",
    "pop": "aevalsrc='0.8*sin(2*PI*(700+900*exp(-20*t))*t)*exp(-18*t)':d=0.2",
    "drip": "aevalsrc='0.6*sin(2*PI*(1800-1200*t)*t)*exp(-14*t)':d=0.3",
    "squeak": "aevalsrc='0.5*sin(2*PI*(1400+500*sin(2*PI*14*t))*t)*exp(-6*t)':d=0.35",
    "gulp": "aevalsrc='0.7*sin(2*PI*(220-480*t)*t)*exp(-9*t)':d=0.3",
    "bonk": "aevalsrc='0.8*sin(2*PI*(180-300*t)*t)*exp(-12*t)':d=0.3",
    "tick": "aevalsrc='0.7*sin(2*PI*1800*t)*exp(-70*t)':d=0.12",
    "peck": "aevalsrc='0.8*sin(2*PI*900*t)*exp(-40*t)':d=0.12",
    "chirp": "aevalsrc='0.5*sin(2*PI*(2600+900*sin(2*PI*9*t))*t)*exp(-9*t)':d=0.3",
    "ding": "aevalsrc='0.6*sin(2*PI*1568*t)*exp(-4*t)':d=0.9",
    "sparkle": "aevalsrc='0.22*(sin(2*PI*2093*t)+sin(2*PI*2637*t)+sin(2*PI*3136*t))"
               "*exp(-3*t)*(0.6+0.4*sin(2*PI*18*t))':d=0.9",
    "slide_whistle": "aevalsrc='0.45*sin(2*PI*(2200-1700*t)*t)':d=1.0",
    "trombone": "aevalsrc='0.3*(2*mod((220-40*t)*t,1)-1)*exp(-0.8*t)':d=1.4",
    "zip": "aevalsrc='0.4*sin(2*PI*(400+8000*t)*t)':d=0.25",
    "wobble": "aevalsrc='0.5*sin(2*PI*(300+60*sin(2*PI*6*t))*t)*exp(-1.5*t)':d=1.0",
    "kazoo": "aevalsrc='0.3*(2*mod(500*t+0.05*sin(2*PI*6*t),1)-1)*exp(-1.2*t)':d=0.8",
    "western": "aevalsrc='0.4*sin(2*PI*(900+300*sin(2*PI*0.8*t))*t)*(1-exp(-8*t))':d=1.8",
    "beeps": "aevalsrc='0.4*sin(2*PI*880*t)*lt(mod(t,0.5),0.1)':d=1.5",
    "splat": NOISE.format(d=0.35, c="brown", a=0.9) + ",lowpass=f=700,afade=t=out:st=0.05:d=0.3",
    "thud": NOISE.format(d=0.3, c="brown", a=0.9) + ",lowpass=f=300,afade=t=out:st=0.05:d=0.25",
    "whoosh": NOISE.format(d=0.9, c="pink", a=0.6) + ",bandpass=f=900:t=h:w=700,afade=t=in:d=0.45,afade=t=out:st=0.45:d=0.45",
    "gasp": NOISE.format(d=0.5, c="white", a=0.5) + ",bandpass=f=1800:t=h:w=1200,afade=t=in:d=0.2,afade=t=out:st=0.25:d=0.25",
    "sigh": NOISE.format(d=1.0, c="pink", a=0.35) + ",bandpass=f=600:t=h:w=500,afade=t=in:d=0.3,afade=t=out:st=0.4:d=0.6",
    "record_scratch": NOISE.format(d=0.45, c="white", a=0.6) + ",bandpass=f=2500:t=h:w=2000,afade=t=in:d=0.05,afade=t=out:st=0.2:d=0.25",
    "drum_roll": NOISE.format(d=1.5, c="brown", a=0.9) + ",lowpass=f=400,tremolo=f=22:d=0.9,afade=t=in:d=0.3",
    "crunch": NOISE.format(d=0.25, c="white", a=0.6) + ",bandpass=f=3000:t=h:w=2500,tremolo=f=30:d=1,afade=t=out:st=0.1:d=0.15",
    "rolling": NOISE.format(d=1.5, c="brown", a=0.8) + ",lowpass=f=500,tremolo=f=8:d=0.8",
}

# first match wins, so more specific words come first
SYNONYMS = [
    ("slide whistle", "slide_whistle"), ("dizzy", "slide_whistle"), ("western", "western"),
    ("record scratch", "record_scratch"), ("trombone", "trombone"), ("drum roll", "drum_roll"),
    ("boing", "boing"), ("wobble", "wobble"), ("squeak", "squeak"), ("strain", "squeak"),
    ("splat", "splat"), ("thud", "thud"), ("thump", "thud"), ("thunk", "thud"),
    ("bonk", "bonk"), ("pop", "pop"), ("drip", "drip"), ("gulp", "gulp"),
    ("gasp", "gasp"), ("sigh", "sigh"), ("whoosh", "whoosh"), ("flutter", "whoosh"),
    ("zip", "zip"), ("sparkle", "sparkle"), ("cheer", "sparkle"), ("petals", "sparkle"),
    ("ding", "ding"), ("chirp", "chirp"), ("tweet", "chirp"), ("tick", "tick"),
    ("peck", "peck"), ("tap", "peck"), ("beep", "beeps"), ("crunch", "crunch"),
    ("kazoo", "kazoo"), ("rolling", "rolling"),
]

GAIN_DB = {"whoosh": 12, "sigh": 14, "gasp": 6, "rolling": 3, "splat": 3, "thud": 6}

NOTES = [262, 330, 392, 330, 440, 392, 330, 294, 262, 330, 392, 523, 440, 392, 330, 294]
STEP = 0.5  # seconds per music note


def _ffmpeg(args):
    subprocess.run(["ffmpeg", "-y", "-v", "error"] + args, check=True)


def sounds_for_shot(sound_text):
    """'boing, ow squeak' -> ['boing', 'squeak']. Never raises."""
    if not sound_text:
        return []
    if isinstance(sound_text, (list, tuple)):
        sound_text = ", ".join(str(s) for s in sound_text)
    found = []
    for token in str(sound_text).lower().replace(";", ",").split(","):
        token = token.strip()
        if not token or "music" in token:
            continue
        for key, name in SYNONYMS:
            if key in token:
                found.append(name)
                break
        else:
            print(f"  Sound word not known, skipped: {token!r}")
    return found


def make_effect(name, tmp_dir):
    """Path to a wav/mp3 for this effect: assets/sfx/<name>.* first, else made."""
    for path in glob.glob(f"assets/sfx/{name}.*"):
        return path
    out = os.path.join(tmp_dir, f"sfx_{name}.wav")
    if not os.path.exists(out):
        _ffmpeg(["-f", "lavfi", "-i", EFFECTS[name], "-af", f"volume={GAIN_DB.get(name, 0)}dB",
                 "-ar", str(SR), "-ac", "1", out])
    return out


def make_music(duration, tmp_dir):
    """A soft music bed exactly `duration` seconds long (fades in and out)."""
    out = os.path.join(tmp_dir, "music_bed.wav")
    fade = f"afade=t=in:d=1,afade=t=out:st={max(duration - 2, 0):.2f}:d=2"
    files = glob.glob("assets/music/*.mp3") + glob.glob("assets/music/*.wav") + glob.glob("assets/music/*.ogg")
    if files:
        _ffmpeg(["-stream_loop", "-1", "-i", random.choice(files), "-t", f"{duration:.2f}",
                 "-af", "volume=0.9," + fade, "-ar", str(SR), "-ac", "1", out])
        return out
    freq = "0"
    for i in reversed(range(len(NOTES))):
        freq = f"if(eq(mod(floor(t/{STEP}),{len(NOTES)}),{i}),{NOTES[i]},{freq})"
    expr = (f"0.45*(sin(2*PI*({freq})*t)+0.3*sin(4*PI*({freq})*t))*exp(-5*mod(t,{STEP}))"
            f"+0.25*sin(2*PI*131*t)*exp(-1.2*mod(t,2))")
    _ffmpeg(["-f", "lavfi", "-i", f"aevalsrc='{expr}':d={duration:.2f}:s={SR}",
             "-af", fade, "-ac", "1", out])
    return out
