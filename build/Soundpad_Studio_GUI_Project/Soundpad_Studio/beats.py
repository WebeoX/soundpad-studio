"""
beats.py - Beat maker (procedural, standard library only).

* Drum sounds are SYNTHESIZED in code (no sample files needed).
* Patterns live in MySQL: beat_patterns (one row per pattern) and
  pattern_steps (one row per drum hit on the step grid).
* A beat track plays its patterns in order; each pattern loops `repeats` times,
  so you can build sections (intro, verse, drop...).
* render.py calls render_beat_track() automatically for 'beat' tracks.
"""
import math
import random

from db import execute, fetch_one, fetch_all
from audio_io import load_wav, play_audio
import editing as ed

# ======================================================================
#  DRUM SYNTHESIS   (each returns a list of mono float samples)
# ======================================================================
def _noise(n, seed=1):
    rnd = random.Random(seed)            # fixed seed -> same sound every render
    return [rnd.uniform(-1.0, 1.0) for _ in range(n)]


def _highpassed_noise(n, seed=1):
    raw = _noise(n, seed)
    return [raw[i] - (raw[i - 1] if i else 0.0) for i in range(n)]


def _declick(samples, rate, ms=5):
    """Short fade at the end so the sound never ends with a pop."""
    n = min(int(rate * ms / 1000), len(samples))
    for i in range(n):
        samples[len(samples) - 1 - i] *= i / n
    return samples


def _sweep_sine(rate, seconds, f_start, f_end, sweep_speed, decay):
    """Sine wave whose pitch falls from f_start to f_end (kick / tom body)."""
    n = int(rate * seconds)
    out, phase = [], 0.0
    for i in range(n):
        t = i / rate
        f = f_end + (f_start - f_end) * math.exp(-t * sweep_speed)
        phase += 2 * math.pi * f / rate
        out.append(math.sin(phase) * math.exp(-t * decay))
    return out


def synth_kick(rate):
    return _declick([s * 0.95 for s in _sweep_sine(rate, 0.45, 150, 45, 25, 8)], rate)


def synth_snare(rate):
    n = int(rate * 0.25)
    noise = _noise(n, 2)
    out = []
    for i in range(n):
        t = i / rate
        body = math.sin(2 * math.pi * 180 * t) * math.exp(-t * 30) * 0.5
        out.append(noise[i] * math.exp(-t * 22) * 0.6 + body)
    return _declick(out, rate)


def synth_hihat_closed(rate):
    n = int(rate * 0.08)
    noise = _highpassed_noise(n, 3)
    return _declick([noise[i] * math.exp(-(i / rate) * 70) * 0.35 for i in range(n)], rate)


def synth_hihat_open(rate):
    n = int(rate * 0.4)
    noise = _highpassed_noise(n, 4)
    return _declick([noise[i] * math.exp(-(i / rate) * 10) * 0.3 for i in range(n)], rate)


def synth_clap(rate):
    n = int(rate * 0.25)
    noise = _highpassed_noise(n, 5)
    out = []
    for i in range(n):
        t = i / rate
        amp = math.exp(-t * 18) * 0.5            # tail
        for start in (0.0, 0.011, 0.022):        # three quick bursts
            if t >= start:
                amp += math.exp(-(t - start) * 120) * 0.5
        out.append(noise[i] * amp)
    return _declick(out, rate)


def synth_tom_low(rate):
    return _declick([s * 0.9 for s in _sweep_sine(rate, 0.4, 130, 80, 18, 7)], rate)


def synth_tom_high(rate):
    return _declick([s * 0.9 for s in _sweep_sine(rate, 0.35, 220, 140, 18, 8)], rate)


def synth_rimshot(rate):
    n = int(rate * 0.1)
    noise = _noise(n, 6)
    out = []
    for i in range(n):
        t = i / rate
        out.append(math.sin(2 * math.pi * 1700 * t) * math.exp(-t * 90) * 0.4
                   + math.sin(2 * math.pi * 450 * t) * math.exp(-t * 60) * 0.4
                   + noise[i] * math.exp(-t * 100) * 0.3)
    return _declick(out, rate)


DRUM_SYNTHS = {
    "Kick": synth_kick, "Snare": synth_snare,
    "Closed Hi-Hat": synth_hihat_closed, "Open Hi-Hat": synth_hihat_open,
    "Clap": synth_clap, "Low Tom": synth_tom_low,
    "High Tom": synth_tom_high, "Rimshot": synth_rimshot,
}
CATEGORY_DEFAULT = {
    "kick": synth_kick, "snare": synth_snare, "hihat": synth_hihat_closed,
    "clap": synth_clap, "tom": synth_tom_low, "perc": synth_rimshot,
    "other": synth_rimshot,
}


def sample_audio(drum, rate, cache):
    """Stereo audio for a drum_samples row (custom file, else synthesized)."""
    key = (drum["sample_id"], rate)
    if key in cache:
        return cache[key]
    audio = None
    if drum["file_id"] is not None:
        f = fetch_one("SELECT file_path FROM audio_files WHERE file_id = %s",
                      (drum["file_id"],))
        if f:
            try:
                audio = ed.resample(load_wav(f["file_path"]), rate)
            except (OSError, ValueError):
                audio = None
    if audio is None:
        maker = DRUM_SYNTHS.get(drum["name"]) or CATEGORY_DEFAULT[drum["category"]]
        audio = {"rate": rate, "channels": [maker(rate)]}
    cache[key] = ed.to_stereo(audio)
    return cache[key]


# ======================================================================
#  DATABASE FUNCTIONS
# ======================================================================
_schema_checked = False


def ensure_schema():
    """Older databases lack beat_patterns.repeats - add it once if missing."""
    global _schema_checked
    if _schema_checked:
        return
    if fetch_one("SHOW COLUMNS FROM beat_patterns LIKE 'repeats'") is None:
        execute("ALTER TABLE beat_patterns ADD COLUMN repeats INT DEFAULT 4")
    _schema_checked = True


def list_drum_samples():
    return fetch_all("SELECT * FROM drum_samples ORDER BY sample_id")


def add_custom_drum(name, category, file_id):
    """Use one of your imported WAVs as a drum sound. Returns (sample_id, msg)."""
    if category not in ("kick", "snare", "hihat", "clap", "tom", "perc", "other"):
        return None, "Invalid category."
    if fetch_one("SELECT 1 AS ok FROM drum_samples WHERE name = %s", (name,)):
        return None, "A drum with that name already exists."
    sid = execute("INSERT INTO drum_samples (name, category, file_id) VALUES (%s,%s,%s)",
                  (name, category, file_id))
    return sid, "Drum '%s' added." % name


def create_pattern(track_id, name, total_steps=16, swing=0.0, repeats=4):
    """Returns (pattern_id, message). The track must be a 'beat' track."""
    ensure_schema()
    t = fetch_one("SELECT track_type FROM tracks WHERE track_id = %s", (track_id,))
    if t is None or t["track_type"] != "beat":
        return None, "Patterns can only be added to a beat track."
    if total_steps not in (8, 16, 24, 32):
        return None, "Steps must be 8, 16, 24 or 32."
    if not 0 <= swing <= 1:
        return None, "Swing must be between 0 and 1."
    if not 1 <= repeats <= 64:
        return None, "Repeats must be between 1 and 64."
    pid = execute(
        """INSERT INTO beat_patterns (track_id, pattern_name, total_steps, swing, repeats)
           VALUES (%s,%s,%s,%s,%s)""",
        (track_id, name.strip() or "Pattern", total_steps, swing, repeats))
    return pid, "Pattern created."


def list_patterns(track_id):
    ensure_schema()
    return fetch_all(
        "SELECT * FROM beat_patterns WHERE track_id = %s ORDER BY pattern_id", (track_id,))


def get_pattern(pattern_id):
    ensure_schema()
    return fetch_one("SELECT * FROM beat_patterns WHERE pattern_id = %s", (pattern_id,))


def get_steps(pattern_id):
    return fetch_all(
        "SELECT sample_id, step_no, velocity FROM pattern_steps WHERE pattern_id = %s",
        (pattern_id,))


def set_step(pattern_id, sample_id, step_no, velocity=100):
    """Put (or replace) a drum hit on a step (step_no counts from 0)."""
    pat = get_pattern(pattern_id)
    if pat is None or not 0 <= step_no < pat["total_steps"]:
        return False
    clear_step(pattern_id, sample_id, step_no)
    execute("INSERT INTO pattern_steps (pattern_id, sample_id, step_no, velocity) "
            "VALUES (%s,%s,%s,%s)", (pattern_id, sample_id, step_no, velocity))
    return True


def clear_step(pattern_id, sample_id, step_no):
    execute("DELETE FROM pattern_steps WHERE pattern_id=%s AND sample_id=%s AND step_no=%s",
            (pattern_id, sample_id, step_no))


def toggle_step(pattern_id, sample_id, step_no):
    exists = fetch_one(
        "SELECT 1 AS ok FROM pattern_steps WHERE pattern_id=%s AND sample_id=%s AND step_no=%s",
        (pattern_id, sample_id, step_no))
    if exists:
        clear_step(pattern_id, sample_id, step_no)
    else:
        set_step(pattern_id, sample_id, step_no)


def clear_pattern(pattern_id):
    execute("DELETE FROM pattern_steps WHERE pattern_id = %s", (pattern_id,))


def delete_pattern(pattern_id):
    execute("DELETE FROM beat_patterns WHERE pattern_id = %s", (pattern_id,))


def set_swing(pattern_id, swing):
    execute("UPDATE beat_patterns SET swing = %s WHERE pattern_id = %s",
            (max(0.0, min(1.0, swing)), pattern_id))


def set_repeats(pattern_id, repeats):
    execute("UPDATE beat_patterns SET repeats = %s WHERE pattern_id = %s",
            (max(1, min(64, int(repeats))), pattern_id))


# ======================================================================
#  PRESETS  ('x' = normal hit, 'o' = soft hit, '.' = silence)
# ======================================================================
PRESETS = {
    "rock": {
        "Kick":          "x.......x.x.....",
        "Snare":         "....x.......x...",
        "Closed Hi-Hat": "x.x.x.x.x.x.x.x.",
    },
    "hiphop": {
        "Kick":          "x.....x..x......",
        "Snare":         "....x.......x...",
        "Closed Hi-Hat": "x.x.x.x.x.x.x.x.",
    },
    "house": {
        "Kick":          "x...x...x...x...",
        "Clap":          "....x.......x...",
        "Open Hi-Hat":   "..x...x...x...x.",
        "Closed Hi-Hat": "o.o.o.o.o.o.o.o.",
    },
    "trap": {
        "Kick":          "x.......x..x....",
        "Snare":         "........x.......",
        "Closed Hi-Hat": "x.x.x.xxx.x.x.xx",
        "Open Hi-Hat":   "..............x.",
    },
    "lofi": {
        "Kick":          "x.....x...x.....",
        "Snare":         "....x.......x...",
        "Closed Hi-Hat": "o.o.o.o.o.o.o.o.",
        "Rimshot":       "...........o....",
    },
}


def list_presets():
    return list(PRESETS.keys())


def apply_preset(pattern_id, preset_name):
    """Replace the pattern's hits with a preset. Returns (ok, message)."""
    preset = PRESETS.get(preset_name.lower())
    if preset is None:
        return False, "Unknown preset. Try: " + ", ".join(PRESETS)
    pat = get_pattern(pattern_id)
    if pat is None:
        return False, "Pattern not found."
    ids = {d["name"]: d["sample_id"] for d in list_drum_samples()}
    clear_pattern(pattern_id)
    for drum_name, row in preset.items():
        if drum_name not in ids:
            continue
        for step, ch in enumerate(row[:pat["total_steps"]]):
            if ch in ("x", "o"):
                set_step(pattern_id, ids[drum_name], step, 100 if ch == "x" else 55)
    return True, "Preset '%s' loaded." % preset_name


def randomize_pattern(pattern_id, density=0.25):
    """Fill the grid with a random but musical beat: kick on the downbeat,
    snare on the backbeat, everything else random."""
    pat = get_pattern(pattern_id)
    if pat is None:
        return
    steps = pat["total_steps"]
    ids = {d["name"]: d["sample_id"] for d in list_drum_samples()}
    clear_pattern(pattern_id)
    set_step(pattern_id, ids["Kick"], 0)
    set_step(pattern_id, ids["Snare"], steps // 4)
    set_step(pattern_id, ids["Snare"], (3 * steps) // 4)
    for s in range(steps):
        if random.random() < density:
            set_step(pattern_id, ids["Kick"], s, 90)
        if random.random() < density * 2:
            set_step(pattern_id, ids["Closed Hi-Hat"], s, random.choice((55, 80, 100)))
        if random.random() < density * 0.4:
            set_step(pattern_id, random.choice((ids["Clap"], ids["Rimshot"], ids["Low Tom"])), s, 70)


# ======================================================================
#  DISPLAY AND RENDERING
# ======================================================================
def print_pattern(pattern_id):
    """Text view of the step grid.  X = normal hit, o = soft hit."""
    pat = get_pattern(pattern_id)
    if pat is None:
        print("Pattern not found.")
        return
    n = pat["total_steps"]
    hits = {}
    for s in get_steps(pattern_id):
        hits[(s["sample_id"], s["step_no"])] = s["velocity"]

    print("\nPattern: %s   steps: %d   swing: %.2f   repeats: %d"
          % (pat["pattern_name"], n, float(pat["swing"]), pat["repeats"]))
    header = "".join(("%-4d" % (i + 1)) if i % 4 == 0 else "" for i in range(n))
    print("    %-14s  %s" % ("", header))
    for idx, d in enumerate(list_drum_samples(), start=1):
        row = ""
        for i in range(n):
            if i % 4 == 0:
                row += "|"
            v = hits.get((d["sample_id"], i))
            row += "." if v is None else ("X" if v >= 80 else "o")
        print("%2d  %-14s %s|" % (idx, d["name"], row))


def render_pattern(pattern_id, bpm, rate=44100, cache=None):
    """Render ONE loop of a pattern (a seamless stereo loop: drum tails that
    run past the end wrap round to the start)."""
    if cache is None:
        cache = {}
    pat = get_pattern(pattern_id)
    step_sec = 60.0 / bpm / 4                       # 16th-note length
    loop_len = int(round(pat["total_steps"] * step_sec * rate))
    drums = {d["sample_id"]: d for d in list_drum_samples()}
    swing = float(pat["swing"])

    loop = ed.make_audio(rate, 2, 0)
    for s in get_steps(pattern_id):
        drum = drums.get(s["sample_id"])
        if drum is None:
            continue
        t = s["step_no"] * step_sec
        if s["step_no"] % 2 == 1:
            t += swing * step_sec * 0.5              # delay off-beats = swing
        ed.mix_into(loop, sample_audio(drum, rate, cache), t, s["velocity"] / 127.0)

    for ch in loop["channels"]:
        if len(ch) < loop_len:
            ch.extend([0.0] * (loop_len - len(ch)))
        else:
            for i, v in enumerate(ch[loop_len:]):    # wrap the tail
                ch[i % loop_len] += v
            del ch[loop_len:]
    return loop


def render_beat_track(track_id, bpm, rate=44100):
    """Called by render.py: patterns play in order, each repeated `repeats` times."""
    cache = {}
    result = None
    for pat in list_patterns(track_id):
        loop = render_pattern(pat["pattern_id"], bpm, rate, cache)
        section = ed.loop_audio(loop, pat["repeats"])
        result = section if result is None else ed.merge(result, section)
    return result


# ======================================================================
#  INTERACTIVE EDITOR
# ======================================================================
def beat_editor(pattern_id, bpm=120, rate=44100):
    """Console beat editor. Type 'h' for help."""
    help_text = (
        "\n  t <drum#> <step#>   toggle a hit        (e.g. t 1 5)\n"
        "  p <preset>          load a preset         (%s)\n"
        "  r                   randomize\n"
        "  c                   clear the pattern\n"
        "  s <0-1>             set swing             (e.g. s 0.4)\n"
        "  x <n>               set repeats           (e.g. x 4)\n"
        "  l                   play the loop twice\n"
        "  q                   finish\n" % ", ".join(PRESETS))
    print(help_text)
    drums = list_drum_samples()
    while True:
        print_pattern(pattern_id)
        parts = input("\nbeat> ").strip().split()
        if not parts:
            continue
        cmd, args = parts[0].lower(), parts[1:]
        try:
            if cmd == "q":
                return
            elif cmd == "h":
                print(help_text)
            elif cmd == "t" and len(args) == 2:
                d, s = int(args[0]), int(args[1])
                if 1 <= d <= len(drums) and 1 <= s <= get_pattern(pattern_id)["total_steps"]:
                    toggle_step(pattern_id, drums[d - 1]["sample_id"], s - 1)
                else:
                    print("Drum or step number out of range.")
            elif cmd == "p" and args:
                print(apply_preset(pattern_id, args[0])[1])
            elif cmd == "r":
                randomize_pattern(pattern_id)
            elif cmd == "c":
                clear_pattern(pattern_id)
            elif cmd == "s" and args:
                set_swing(pattern_id, float(args[0]))
            elif cmd == "x" and args:
                set_repeats(pattern_id, int(args[0]))
            elif cmd == "l":
                loop = render_pattern(pattern_id, bpm, rate)
                play_audio(ed.limit(ed.loop_audio(loop, 2)))
            else:
                print("Unknown command. Type h for help.")
        except ValueError:
            print("Please enter numbers where needed.")