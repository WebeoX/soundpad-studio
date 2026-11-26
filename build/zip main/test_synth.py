"""
test_synth.py - Builds a complete little song with the composer and beat maker:
drums + chords + bass + melody, then exports and plays it.
"""
from auth import auth_menu
from audio_io import play_file
from projects import create_project, add_track, set_track_volume, print_project
from beats import create_pattern, apply_preset
from synth import (ensure_extra_instruments, get_instrument_by_name, note_to_midi,
                   add_progression, add_bass_line, random_melody, note_editor,
                   print_piano_roll)
from render import export_project


def main():
    user = auth_menu()
    if user is None:
        return
    uid = user["user_id"]
    ensure_extra_instruments()

    bpm = 100
    pid, msg = create_project(uid, "Synth Test Song", bpm=bpm)
    print(msg)

    key = note_to_midi("C3")                 # song is in C major
    pad = get_instrument_by_name("Warm Pad")["instrument_id"]
    bass = get_instrument_by_name("Sub Bass")["instrument_id"]
    lead = get_instrument_by_name("Pluck")["instrument_id"]

    # Drums: 8 loops of a hip-hop groove = 32 beats
    drums, _ = add_track(pid, uid, "Drums", "beat")
    p, _ = create_pattern(drums, "Groove", total_steps=16, swing=0.15, repeats=8)
    apply_preset(p, "hiphop")
    set_track_volume(drums, 0.8)

    # Chords: pop progression (I-V-vi-IV), 2 times = 32 beats
    chords, _ = add_track(pid, uid, "Chords", "instrument")
    add_progression(chords, pad, key, "pop", start_beat=0, beats_per_chord=4, repeats=2)
    set_track_volume(chords, 0.7)

    # Bass: follows the chord roots
    bass_track, _ = add_track(pid, uid, "Bass", "instrument")
    add_bass_line(bass_track, bass, key, "pop", start_beat=0, beats_per_chord=4, repeats=2)

    # Lead melody: random walk on the C major pentatonic scale, 8 bars
    lead_track, _ = add_track(pid, uid, "Lead", "instrument")
    n = random_melody(lead_track, lead, note_to_midi("C4"), "major_pentatonic",
                      start_beat=0, bars=8, seed=7)
    print("\nMelody has %d notes. First 16 beats:" % n)
    print_piano_roll(lead_track, 0, 16)

    if input("\nOpen the note editor on the Lead track? (y/n): ").strip().lower() == "y":
        note_editor(lead_track, bpm)

    print_project(pid, uid)
    print("\nRendering (this can take a few seconds) ...")
    out, msg = export_project(pid, uid)
    print(msg)
    if out:
        print("Playing ...")
        play_file(out)


if __name__ == "__main__":
    main()