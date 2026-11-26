"""
synth.py - Music composer (procedural, standard library only).

* Instruments (waveform + ADSR envelope) and notes are stored in MySQL
  (tables: instruments, notes).
* Helpers for scales, chords, chord progressions, arpeggios, bass lines and a
  random melody generator.
* render_instrument_track() is called by render.py for 'instrument' tracks.

Notes use MIDI numbers: 60 = middle C (C4), 69 = A4 = 440 Hz.
Time is measured in BEATS; the project's BPM turns beats into seconds.
"""
import math
import random
import re

from db import execute, fetch_one, fetch_all
from audio_io import play_audio
import editing as ed

# ======================================================================
#  NOTE NAMES AND MUSIC THEORY
# ======================================================================
NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
_BASE = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def midi_to_freq(midi):
    return 440.0 * 2 ** ((midi - 69) / 12.0)


def midi_to_name(midi):
    return NOTE_NAMES[midi % 12] + str(midi // 12 - 1)


def note_to_midi(text, default_octave=4):
    """'C4' -> 60, 'F#3' -> 54, 'Bb2' -> 46. Octave is optional."""
    m = re.fullmatch(r"([A-Ga-g])([#b]?)(-?\d)?", text.strip())
    if not m:
        raise ValueError("Bad note name: %s" % text)
    letter, acc, octv = m.groups()
    octave = default_octave if octv is None else int(octv)
    midi = (octave + 1) * 12 + _BASE[letter.upper()] + (1 if acc == "#" else -1 if acc == "b" else 0)
    if not 0 <= midi <= 127:
        raise ValueError("Note out of range: %s" % text)
    return midi


SCALES = {
    "major": [0, 2, 4, 5, 7, 9, 11],
    "minor": [0, 2, 3, 5, 7, 8, 10],
    "harmonic_minor": [0, 2, 3, 5, 7, 8, 11],
    "major_pentatonic": [0, 2, 4, 7, 9],
    "minor_pentatonic": [0, 3, 5, 7, 10],
    "blues": [0, 3, 5, 6, 7, 10],
    "dorian": [0, 2, 3, 5, 7, 9, 10],
    "mixolydian": [0, 2, 4, 5, 7, 9, 10],
    "chromatic": list(range(12)),
}

CHORDS = {
    "major": [0, 4, 7], "minor": [0, 3, 7], "dim": [0, 3, 6], "aug": [0, 4, 8],
    "sus2": [0, 2, 7], "sus4": [0, 5, 7],
    "maj7": [0, 4, 7, 11], "min7": [0, 3, 7, 10], "dom7": [0, 4, 7, 10],
}

# (semitones above the key's root, chord type).  Root = the key's tonic.
PROGRESSIONS = {
    "pop":  [(0, "major"), (7, "major"), (9, "minor"), (5, "major")],      # I V vi IV
    "50s":  [(0, "major"), (9, "minor"), (5, "major"), (7, "major")],      # I vi IV V
    "jazz": [(2, "min7"), (7, "dom7"), (0, "maj7"), (0, "maj7")],          # ii V I
    "sad":  [(0, "minor"), (8, "major"), (3, "major"), (10, "major")],     # i VI III VII
    "epic": [(0, "minor"), (10, "major"), (8, "major"), (10, "major")],    # i VII VI VII
}


def scale_midi(root_midi, scale="major", octaves=2):
    """All notes of a scale starting at root_midi, spanning `octaves` octaves."""
    notes = [root_midi + 12 * o + iv for o in range(octaves) for iv in SCALES[scale]]
    notes.append(root_midi + 12 * octaves)
    return [n for n in notes if n <= 127]


def chord_midi(root_midi, chord_type):
    return [root_midi + iv for iv in CHORDS[chord_type] if root_midi + iv <= 127]


# ======================================================================
#  SOUND GENERATION
# ======================================================================
WAVE_FUNCS = {
    "sine":     lambda f: math.sin(2 * math.pi * f),
    "square":   lambda f: 1.0 if f < 0.5 else -1.0,
    "sawtooth": lambda f: 2.0 * f - 1.0,
    "triangle": lambda f: 4.0 * abs(f - 0.5) - 1.0,
}
WAVE_GAIN = {"sine": 0.5, "square": 0.3, "sawtooth": 0.35, "triangle": 0.45}


def _hold_level(t, a, d, s):
    """ADSR level while the key is held: attack -> decay -> sustain."""
    if t < a:
        return t / a
    if t < a + d:
        return 1.0 - (1.0 - s) * ((t - a) / d)
    return s


def render_note(instr, midi, length_sec, velocity, rate):
    """One note as a mono list of samples. `instr` is an instruments row.
    The release stage plays AFTER the note's length, so the note rings out."""
    a = max(0.002, float(instr["attack"]))
    d = max(0.0, float(instr["decay"]))
    s = float(instr["sustain"])
    r = max(0.005, float(instr["release_t"]))
    wave = instr["waveform"]

    note_n = max(1, int(length_sec * rate))
    rel_n = max(1, int(r * rate))
    inc = midi_to_freq(midi) / rate
    shape = WAVE_FUNCS[wave]
    gain = WAVE_GAIN[wave] * velocity / 127.0
    level_end = _hold_level((note_n - 1) / rate, a, d, s)

    out = [0.0] * (note_n + rel_n)
    for i in range(note_n):
        out[i] = shape((i * inc) % 1.0) * _hold_level(i / rate, a, d, s) * gain
    for j in range(rel_n):
        out[note_n + j] = (shape(((note_n + j) * inc) % 1.0)
                           * level_end * (1.0 - j / rel_n) * gain)
    return out


# ======================================================================
#  INSTRUMENT DATABASE FUNCTIONS
# ======================================================================
EXTRA_INSTRUMENTS = [
    # name, waveform, attack, decay, sustain, release
    ("Pluck", "sawtooth", 0.002, 0.250, 0.00, 0.100),
    ("Organ", "square", 0.010, 0.000, 1.00, 0.050),
    ("Sub Bass", "sine", 0.010, 0.100, 0.90, 0.100),
    ("Bell", "sine", 0.001, 1.200, 0.00, 0.800),
    ("Warm Pad", "triangle", 0.400, 0.300, 0.80, 0.800),
    ("Chiptune", "square", 0.001, 0.050, 0.60, 0.050),
]


def ensure_extra_instruments():
    """Add the extra starter instruments (safe to call repeatedly)."""
    for row in EXTRA_INSTRUMENTS:
        execute("""INSERT IGNORE INTO instruments
                   (name, waveform, attack, decay, sustain, release_t)
                   VALUES (%s,%s,%s,%s,%s,%s)""", row)


def list_instruments():
    return fetch_all("SELECT * FROM instruments ORDER BY instrument_id")


def get_instrument(instrument_id):
    return fetch_one("SELECT * FROM instruments WHERE instrument_id = %s", (instrument_id,))


def get_instrument_by_name(name):
    return fetch_one("SELECT * FROM instruments WHERE name = %s", (name,))


def add_instrument(name, waveform, attack, decay, sustain, release):
    """Create your own instrument. Returns (instrument_id, message)."""
    if waveform not in WAVE_FUNCS:
        return None, "Waveform must be sine, square, sawtooth or triangle."
    if not (0 <= attack <= 9 and 0 <= decay <= 9 and 0 <= release <= 9 and 0 <= sustain <= 1):
        return None, "Times must be 0-9 seconds and sustain 0-1."
    if fetch_one("SELECT 1 AS ok FROM instruments WHERE name = %s", (name,)):
        return None, "An instrument with that name already exists."
    iid = execute("""INSERT INTO instruments (name, waveform, attack, decay, sustain, release_t)
                     VALUES (%s,%s,%s,%s,%s,%s)""",
                  (name, waveform, attack, decay, sustain, release))
    return iid, "Instrument '%s' created." % name


def print_instruments():
    print("%-4s %-14s %-9s %6s %6s %6s %6s" % ("ID", "Name", "Wave", "Att", "Dec", "Sus", "Rel"))
    for i in list_instruments():
        print("%-4d %-14s %-9s %6.3f %6.3f %6.2f %6.3f" % (
            i["instrument_id"], i["name"], i["waveform"], float(i["attack"]),
            float(i["decay"]), float(i["sustain"]), float(i["release_t"])))


# ======================================================================
#  NOTE DATABASE FUNCTIONS
# ======================================================================
def _check(track_id, instrument_id):
    """Return an error message if the track/instrument can't be used, else None."""
    t = fetch_one("SELECT track_type FROM tracks WHERE track_id = %s", (track_id,))
    if t is None or t["track_type"] != "instrument":
        return "Notes can only be added to an instrument track."
    if get_instrument(instrument_id) is None:
        return "Instrument not found."
    return None


def _insert_note(track_id, instrument_id, midi, start_beat, length_beats, velocity):
    return execute(
        """INSERT INTO notes (track_id, instrument_id, midi_number, start_beat,
                              length_beats, velocity) VALUES (%s,%s,%s,%s,%s,%s)""",
        (track_id, instrument_id, int(midi), round(start_beat, 3),
         round(length_beats, 3), int(velocity)))


def add_note(track_id, instrument_id, midi, start_beat, length_beats, velocity=100):
    """Returns (note_id, message)."""
    err = _check(track_id, instrument_id)
    if err:
        return None, err
    if not 0 <= midi <= 127:
        return None, "MIDI note must be 0-127."
    if start_beat < 0 or length_beats <= 0:
        return None, "Start must be >= 0 and length > 0."
    if not 1 <= velocity <= 127:
        return None, "Velocity must be 1-127."
    return _insert_note(track_id, instrument_id, midi, start_beat, length_beats, velocity), "Note added."


def list_notes(track_id):
    return fetch_all(
        """SELECT n.note_id, n.midi_number, n.start_beat, n.length_beats, n.velocity,
                  n.instrument_id, i.name AS instrument_name
           FROM notes n JOIN instruments i ON n.instrument_id = i.instrument_id
           WHERE n.track_id = %s ORDER BY n.start_beat, n.midi_number""", (track_id,))


def delete_note(note_id):
    execute("DELETE FROM notes WHERE note_id = %s", (note_id,))


def clear_notes(track_id):
    execute("DELETE FROM notes WHERE track_id = %s", (track_id,))


def transpose_track(track_id, semitones):
    """Shift every note up/down. Returns (ok, message)."""
    row = fetch_one("SELECT MIN(midi_number) AS lo, MAX(midi_number) AS hi "
                    "FROM notes WHERE track_id = %s", (track_id,))
    if row is None or row["lo"] is None:
        return False, "No notes to transpose."
    if row["lo"] + semitones < 0 or row["hi"] + semitones > 127:
        return False, "That would push notes out of range."
    execute("UPDATE notes SET midi_number = midi_number + %s WHERE track_id = %s",
            (semitones, track_id))
    return True, "Transposed by %+d semitones." % semitones


# ======================================================================
#  COMPOSING HELPERS
# ======================================================================
def add_chord(track_id, instrument_id, root_midi, chord_type, start_beat,
              length_beats, velocity=90):
    err = _check(track_id, instrument_id)
    if err:
        return 0
    notes = chord_midi(root_midi, chord_type)
    for m in notes:
        _insert_note(track_id, instrument_id, m, start_beat, length_beats, velocity)
    return len(notes)


def add_progression(track_id, instrument_id, root_midi, name, start_beat=0.0,
                    beats_per_chord=4.0, repeats=1, velocity=85):
    """Lay down a chord progression. Returns the number of notes added."""
    prog = PROGRESSIONS[name]
    count, beat = 0, start_beat
    for _ in range(repeats):
        for offset, ctype in prog:
            count += add_chord(track_id, instrument_id, root_midi + offset, ctype,
                               beat, beats_per_chord, velocity)
            beat += beats_per_chord
    return count


def add_bass_line(track_id, instrument_id, root_midi, name, start_beat=0.0,
                  beats_per_chord=4.0, repeats=1, velocity=105):
    """Bass that plays each chord's root note (an octave below the chords),
    with a simple root-root-root-root pulse every beat."""
    err = _check(track_id, instrument_id)
    if err:
        return 0
    count, beat = 0, start_beat
    for _ in range(repeats):
        for offset, _ctype in PROGRESSIONS[name]:
            note = root_midi + offset - 12
            b = 0.0
            while b < beats_per_chord:
                _insert_note(track_id, instrument_id, note, beat + b,
                             min(0.9, beats_per_chord - b), velocity)
                count += 1
                b += 1.0
            beat += beats_per_chord
    return count


def add_arpeggio(track_id, instrument_id, root_midi, chord_type, start_beat,
                 total_beats, step_beats=0.5, pattern="up", velocity=90):
    """Play a chord's notes one after another. pattern: up, down or updown."""
    err = _check(track_id, instrument_id)
    if err:
        return 0
    notes = chord_midi(root_midi, chord_type)
    notes = notes + [notes[0] + 12]                  # include the octave
    if pattern == "down":
        notes = notes[::-1]
    elif pattern == "updown":
        notes = notes + notes[-2:0:-1]
    count, beat, i = 0, start_beat, 0
    while beat < start_beat + total_beats - 1e-9:
        _insert_note(track_id, instrument_id, notes[i % len(notes)], beat,
                     min(step_beats, start_beat + total_beats - beat), velocity)
        beat += step_beats
        i += 1
        count += 1
    return count


def random_melody(track_id, instrument_id, root_midi, scale="major_pentatonic",
                  start_beat=0.0, bars=4, beats_per_bar=4, seed=None):
    """Generate a melody by a random walk along a scale (small steps, mixed
    rhythms, a few rests) that always ends on the root note."""
    err = _check(track_id, instrument_id)
    if err:
        return 0
    rnd = random.Random(seed)
    pool = scale_midi(root_midi, scale, octaves=2)
    idx = 0
    beat, end = start_beat, start_beat + bars * beats_per_bar
    rhythms = [0.5, 0.5, 1.0, 1.0, 1.0, 1.5, 2.0]
    events = []
    while beat < end - 1e-9:
        length = min(rnd.choice(rhythms), end - beat)
        if rnd.random() >= 0.15:                       # 15% chance of a rest
            idx = max(0, min(len(pool) - 1, idx + rnd.choice([-2, -1, -1, 0, 1, 1, 2])))
            events.append([pool[idx], beat, length, rnd.randint(80, 105)])
        beat += length
    if events:
        events[-1][0] = root_midi                       # resolve to the root
    for midi, b, length, vel in events:
        _insert_note(track_id, instrument_id, midi, b, length, vel)
    return len(events)


# ======================================================================
#  DISPLAY
# ======================================================================
def print_notes(track_id):
    notes = list_notes(track_id)
    if not notes:
        print("No notes on this track yet.")
        return
    print("%-6s %-5s %8s %8s %4s  %s" % ("ID", "Note", "Start", "Length", "Vel", "Instrument"))
    for n in notes:
        print("%-6d %-5s %8.2f %8.2f %4d  %s" % (
            n["note_id"], midi_to_name(n["midi_number"]), float(n["start_beat"]),
            float(n["length_beats"]), n["velocity"], n["instrument_name"]))


def print_piano_roll(track_id, from_beat=0, beats=16):
    """Text piano roll: '#' = note starts, '-' = note held, '.' = silence.
    Each beat is 2 cells wide (half-beat resolution)."""
    notes = [n for n in list_notes(track_id)
             if float(n["start_beat"]) < from_beat + beats
             and float(n["start_beat"]) + float(n["length_beats"]) > from_beat]
    if not notes:
        print("(no notes between beat %d and %d)" % (from_beat, from_beat + beats))
        return
    cols = beats * 2
    pitches = sorted({n["midi_number"] for n in notes}, reverse=True)[:24]

    ruler = "".join("|%d " % ((from_beat + b) % 10) for b in range(beats))
    print("\n     " + ruler + "|")
    for p in pitches:
        row = ["."] * cols
        for n in notes:
            if n["midi_number"] != p:
                continue
            s, ln = float(n["start_beat"]), float(n["length_beats"])
            c0 = int((s - from_beat) * 2)
            c1 = int(math.ceil((s + ln - from_beat) * 2))
            for c in range(max(0, c0), min(cols, max(c1, c0 + 1))):
                row[c] = "-"
            if 0 <= c0 < cols:
                row[c0] = "#"
        line = "".join(("|" if c % 2 == 0 else "") + row[c] for c in range(cols))
        print("%-4s %s|" % (midi_to_name(p), line))


# ======================================================================
#  PREVIEW AND RENDERING
# ======================================================================
def preview_note(instrument_id, note_text="C4", seconds=1.0, rate=44100):
    instr = get_instrument(instrument_id)
    if instr is None:
        print("Instrument not found.")
        return
    samples = render_note(instr, note_to_midi(note_text), seconds, 100, rate)
    play_audio({"rate": rate, "channels": [samples, list(samples)]})


def render_instrument_track(track_id, bpm, rate=44100):
    """Called by render.py. Returns stereo audio of all the track's notes."""
    notes = fetch_all(
        """SELECT n.midi_number, n.start_beat, n.length_beats, n.velocity,
                  i.instrument_id, i.waveform, i.attack, i.decay, i.sustain, i.release_t
           FROM notes n JOIN instruments i ON n.instrument_id = i.instrument_id
           WHERE n.track_id = %s""", (track_id,))
    if not notes:
        return None

    beat_sec = 60.0 / bpm
    buf = []
    cache = {}                                   # identical notes are rendered once
    for n in notes:
        length_sec = float(n["length_beats"]) * beat_sec
        key = (n["instrument_id"], n["midi_number"], round(length_sec, 3), n["velocity"])
        if key not in cache:
            cache[key] = render_note(n, n["midi_number"], length_sec, n["velocity"], rate)
        samples = cache[key]
        offset = int(float(n["start_beat"]) * beat_sec * rate)
        if len(buf) < offset + len(samples):
            buf.extend([0.0] * (offset + len(samples) - len(buf)))
        for i, v in enumerate(samples):
            buf[offset + i] += v
    return {"rate": rate, "channels": [buf, list(buf)]}


# ======================================================================
#  INTERACTIVE NOTE EDITOR
# ======================================================================
def note_editor(track_id, bpm=120, rate=44100):
    """Console composer for an instrument track. Type 'h' for help."""
    ensure_extra_instruments()
    instruments = list_instruments()
    current = instruments[0]["instrument_id"]
    help_text = (
        "\n  n <note> <start> <len> [vel]       add a note         n C4 0 1\n"
        "  c <root> <type> <start> <len>       add a chord        c C3 major 0 4\n"
        "  a <root> <type> <start> <len> [pattern]  arpeggio      a C3 major 0 4 updown\n"
        "  g <root> <prog> <start> [x]         chord progression  g C3 pop 0 2\n"
        "  b <root> <prog> <start> [x]         bass line          b C3 pop 0 2\n"
        "  m <root> <scale> <start> <bars>     random melody      m C4 major_pentatonic 0 4\n"
        "  i                                   list/choose instrument\n"
        "  d <note_id>                         delete a note\n"
        "  t <semitones>                       transpose the track\n"
        "  c! / clear                          delete all notes\n"
        "  roll [from_beat]                    piano roll view\n"
        "  list                                list notes\n"
        "  play                                play this track\n"
        "  q                                   finish\n"
        "  chord types: %s\n  progressions: %s\n  scales: %s\n"
        % (", ".join(CHORDS), ", ".join(PROGRESSIONS), ", ".join(SCALES)))
    print(help_text)

    while True:
        name = get_instrument(current)["name"]
        parts = input("\nnotes [%s]> " % name).strip().split()
        if not parts:
            continue
        cmd, a = parts[0].lower(), parts[1:]
        try:
            if cmd == "q":
                return
            elif cmd == "h":
                print(help_text)
            elif cmd == "n" and len(a) >= 3:
                vel = int(a[3]) if len(a) > 3 else 100
                print(add_note(track_id, current, note_to_midi(a[0]),
                               float(a[1]), float(a[2]), vel)[1])
            elif cmd == "c" and len(a) == 4:
                print("%d notes added." % add_chord(track_id, current, note_to_midi(a[0], 3),
                                                    a[1], float(a[2]), float(a[3])))
            elif cmd == "a" and len(a) >= 4:
                pat = a[4] if len(a) > 4 else "up"
                print("%d notes added." % add_arpeggio(track_id, current, note_to_midi(a[0], 3),
                                                       a[1], float(a[2]), float(a[3]), 0.5, pat))
            elif cmd == "g" and len(a) >= 3:
                rep = int(a[3]) if len(a) > 3 else 1
                print("%d notes added." % add_progression(track_id, current, note_to_midi(a[0], 3),
                                                          a[1], float(a[2]), 4.0, rep))
            elif cmd == "b" and len(a) >= 3:
                rep = int(a[3]) if len(a) > 3 else 1
                print("%d notes added." % add_bass_line(track_id, current, note_to_midi(a[0], 3),
                                                        a[1], float(a[2]), 4.0, rep))
            elif cmd == "m" and len(a) == 4:
                print("%d notes added." % random_melody(track_id, current, note_to_midi(a[0], 4),
                                                        a[1], float(a[2]), int(a[3])))
            elif cmd == "i":
                print_instruments()
                pick = input("Instrument ID (Enter to keep): ").strip()
                if pick and get_instrument(int(pick)):
                    current = int(pick)
            elif cmd == "d" and a:
                delete_note(int(a[0]))
            elif cmd == "t" and a:
                print(transpose_track(track_id, int(a[0]))[1])
            elif cmd in ("clear", "c!"):
                clear_notes(track_id)
            elif cmd == "roll":
                print_piano_roll(track_id, int(a[0]) if a else 0)
            elif cmd == "list":
                print_notes(track_id)
            elif cmd == "play":
                audio = render_instrument_track(track_id, bpm, rate)
                if audio is None:
                    print("No notes yet.")
                else:
                    play_audio(ed.limit(ed.normalize(audio, 0.9)))
            else:
                print("Unknown command or wrong arguments. Type h for help.")
        except (ValueError, KeyError) as e:
            print("Input problem: %s" % e)