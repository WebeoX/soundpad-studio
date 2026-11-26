"""
test_beats.py - Try the beat maker end to end:
login -> project -> beat track -> pattern -> editor -> export -> play.
"""
from auth import auth_menu
from audio_io import play_file
from projects import create_project, add_track, print_project
from beats import create_pattern, apply_preset, beat_editor
from render import export_project


def main():
    user = auth_menu()
    if user is None:
        return
    uid = user["user_id"]

    bpm = 90
    pid, msg = create_project(uid, "Beat Test", bpm=bpm)
    print(msg)

    track_id, _ = add_track(pid, uid, "Drums", "beat")

    # Section 1: a hip-hop groove, 4 loops.  Section 2: a trap pattern, 2 loops.
    p1, _ = create_pattern(track_id, "Verse groove", total_steps=16, swing=0.2, repeats=4)
    apply_preset(p1, "hiphop")
    p2, _ = create_pattern(track_id, "Trap drop", total_steps=16, repeats=2)
    apply_preset(p2, "trap")

    print("\nEdit the first pattern (type h for help, q when done):")
    beat_editor(p1, bpm)

    print_project(pid, uid)
    print("\nRendering ...")
    out, msg = export_project(pid, uid)
    print(msg)
    if out:
        print("Playing ...")
        play_file(out)


if __name__ == "__main__":
    main()