"""
test_render.py - End-to-end check: login -> import a WAV -> build a project
with two tracks and effects -> render -> export -> play.
Run it from the folder that contains all the project files.
"""
from auth import auth_menu
from audio_io import import_audio_file, play_file
from projects import (create_project, add_track, add_clip, add_clip_effect,
                      set_track_pan, print_project)
from render import export_project


def main():
    user = auth_menu()
    if user is None:
        return
    uid = user["user_id"]

    path = input("\nPath to a short .wav file to test with: ")
    file_id, msg = import_audio_file(uid, path)
    print(msg)
    if file_id is None:
        return

    pid, msg = create_project(uid, "Test Mix", bpm=120)
    print(msg)

    # Track 1: the original sound, starting at 0s
    t1, _ = add_track(pid, uid, "Original", "audio")
    add_clip(t1, uid, file_id, start_time=0.0, fade_out=0.5)
    set_track_pan(t1, -0.5)

    # Track 2: reversed + echo version starting at 1 second, panned right
    t2, _ = add_track(pid, uid, "Reversed echo", "audio")
    c2, _ = add_clip(t2, uid, file_id, start_time=1.0, volume=0.7, fade_in=0.3)
    add_clip_effect(c2, "reverse")
    add_clip_effect(c2, "echo", 0.25, 0.5)
    set_track_pan(t2, 0.5)

    print_project(pid, uid)

    print("\nRendering ...")
    out, msg = export_project(pid, uid)
    print(msg)
    if out:
        print("Playing ...")
        play_file(out)


if __name__ == "__main__":
    main()