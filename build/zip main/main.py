"""
main.py - Soundpad Studio: the main program (procedural, no classes).

Run this file.  Menus:  Login -> Main menu -> Library / Audio Lab /
Projects (tracks, clips, effects, beat maker, composer, export) / Account.
"""
import os
import getpass

import mysql.connector

from db import close_connection
from auth import auth_menu, change_password, delete_account
from audio_io import (import_audio_file, list_user_files, print_library,
                      load_audio_by_id, remove_audio_file, get_audio_file,
                      play_file, play_audio, save_wav)
import editing as ed
from vizualiser import ascii_waveform, ascii_spectrum
from projects import (create_project, list_projects, get_project, rename_project,
                      set_bpm, delete_project, add_track, list_tracks,
                      set_track_volume, set_track_pan, toggle_mute, toggle_solo,
                      rename_track, delete_track, add_clip, list_clips,
                      update_clip, delete_clip, list_effects, add_clip_effect,
                      list_clip_effects, remove_clip_effect, print_project)
from render import export_project, preview_project, list_exports, EXPORT_DIR
from beats import (list_patterns, create_pattern, apply_preset, list_presets,
                   beat_editor, delete_pattern)
from synth import note_editor, ensure_extra_instruments


# ======================================================================
#  INPUT HELPERS
# ======================================================================
def ask(prompt, default=None):
    shown = " [%s]" % default if default not in (None, "") else ""
    text = input("%s%s: " % (prompt, shown)).strip()
    if text == "" and default is not None:
        return str(default)
    return text


def ask_float(prompt, default=None, lo=None, hi=None):
    """Returns a float, or None if the user leaves it blank (with no default)."""
    while True:
        text = ask(prompt, default)
        if text == "":
            return None
        try:
            value = float(text)
        except ValueError:
            print("  Please enter a number.")
            continue
        if (lo is not None and value < lo) or (hi is not None and value > hi):
            print("  Value must be between %s and %s." % (lo, hi))
            continue
        return value


def ask_int(prompt, default=None, lo=None, hi=None):
    value = ask_float(prompt, default, lo, hi)
    return None if value is None else int(value)


def confirm(prompt):
    return ask(prompt + " (y/n)").lower().startswith("y")


def pause():
    input("\nPress Enter to continue...")


def show_menu(title, options):
    """options: list of (key, label). Returns the key the user typed."""
    print("\n=== %s ===" % title)
    for key, label in options:
        print("  %s. %s" % (key, label))
    return input("Choose: ").strip().lower()


# ======================================================================
#  PICKERS
# ======================================================================
def pick_file(user_id):
    if not list_user_files(user_id):
        print("Your library is empty. Import a WAV file first.")
        return None
    print_library(user_id)
    fid = ask_int("File ID")
    if fid is None:
        return None
    row = get_audio_file(fid, user_id)
    if row is None:
        print("No such file in your library.")
    return row


def pick_track(project_id, track_type=None):
    tracks = [t for t in list_tracks(project_id)
              if track_type in (None, t["track_type"])]
    if not tracks:
        print("No %s tracks in this project yet." % (track_type or ""))
        return None
    for t in tracks:
        print("  #%-4d %-20s %s" % (t["track_id"], t["track_name"], t["track_type"]))
    tid = ask_int("Track ID")
    for t in tracks:
        if t["track_id"] == tid:
            return t
    if tid is not None:
        print("Not a valid track.")
    return None


def pick_clip(track_id):
    clips = list_clips(track_id)
    if not clips:
        print("That track has no clips.")
        return None
    for c in clips:
        print("  clip #%-4d %-24s at %.2fs" % (c["clip_id"], c["file_name"][:24],
                                              float(c["start_time"])))
    cid = ask_int("Clip ID")
    for c in clips:
        if c["clip_id"] == cid:
            return c
    if cid is not None:
        print("Not a valid clip.")
    return None


# ======================================================================
#  AUDIO LAB  (edit a single file, with undo / redo)
# ======================================================================
def lab_apply(state, new_audio):
    state["undo"].append(state["audio"])
    state["audio"] = new_audio
    state["redo"].clear()
    state["saved"] = False


def lab_info(state):
    a = state["audio"]
    peak = ed.get_peak(a)
    print("\n[ %.2f sec | %d Hz | %s | peak %.1f dB | %d edit(s) ]" % (
        ed.duration(a), a["rate"], "stereo" if len(a["channels"]) == 2 else "mono",
        ed.to_db(peak), len(state["undo"])))


def lab_analyse(audio):
    peak, rms = ed.get_peak(audio), ed.get_rms(audio)
    quiet = sum(1 for s in audio["channels"][0] if abs(s) < 0.001)
    print("\n  Duration    : %.3f sec" % ed.duration(audio))
    print("  Sample rate : %d Hz   Channels: %d" % (audio["rate"], len(audio["channels"])))
    print("  Peak level  : %.2f dB (%.3f)" % (ed.to_db(peak), peak))
    print("  RMS level   : %.2f dB" % ed.to_db(rms))
    print("  Clipping    : %s" % ("YES - lower the volume" if ed.is_clipping(audio) else "no"))
    print("  Silence     : %.1f%% of samples" % (100.0 * quiet / max(1, ed.length(audio))))


def lab_save(state, user_id):
    default = state["base_name"] + "_edit.wav"
    name = ask("Save as", default)
    if not name.lower().endswith(".wav"):
        name += ".wav"
    os.makedirs(EXPORT_DIR, exist_ok=True)
    path = os.path.join(EXPORT_DIR, os.path.basename(name))
    if os.path.exists(path) and not confirm("'%s' exists. Overwrite?" % os.path.basename(path)):
        return
    save_wav(path, ed.limit(state["audio"]))
    fid, msg = import_audio_file(user_id, path)
    print("Saved to %s\n%s" % (path, msg))
    state["saved"] = True


def lab_operation(state, choice, user_id):
    """Run one numbered operation on state['audio']."""
    a = state["audio"]
    total = ed.duration(a)

    if choice == "1":
        print("Playing ... (blocks until finished)")
        play_audio(ed.limit(a))
    elif choice == "2":
        print(ascii_waveform(a))
    elif choice == "3":
        lab_analyse(a)
    elif choice == "4":
        s = ask_float("Keep from (sec)", 0, 0)
        e = ask_float("Keep until (sec)", round(total, 2), 0)
        if s is not None and e is not None and e > s:
            lab_apply(state, ed.trim(a, s, e))
    elif choice == "5":
        s = ask_float("Delete from (sec)", None, 0)
        e = ask_float("Delete until (sec)", None, 0)
        if s is not None and e is not None and e > s:
            lab_apply(state, ed.cut_out(a, s, e))
    elif choice == "6":
        f = ask_float("Volume factor (1 = same, 2 = double, 0.5 = half)", 1.0, 0, 10)
        if f is not None:
            lab_apply(state, ed.change_volume(a, f))
    elif choice == "7":
        f = ask_float("Fade-in length (sec)", 1.0, 0)
        if f is not None:
            lab_apply(state, ed.fade_in(a, f))
    elif choice == "8":
        f = ask_float("Fade-out length (sec)", 1.0, 0)
        if f is not None:
            lab_apply(state, ed.fade_out(a, f))
    elif choice == "9":
        lab_apply(state, ed.reverse(a))
    elif choice == "10":
        f = ask_float("Speed factor (2 = double speed, 0.5 = half)", 1.0, 0.1, 8)
        if f is not None:
            lab_apply(state, ed.change_speed(a, f))
    elif choice == "11":
        f = ask_float("Target peak (0-1)", 0.95, 0.01, 1.0)
        if f is not None:
            lab_apply(state, ed.normalize(a, f))
    elif choice == "12":
        d = ask_float("Echo delay (sec)", 0.3, 0.02, 2)
        k = ask_float("Echo strength 0-0.95", 0.5, 0, 0.95)
        r = ask_int("Number of repeats", 3, 1, 10)
        if None not in (d, k, r):
            lab_apply(state, ed.add_echo(a, d, k, r))
    elif choice == "13":
        f = ask_float("Low-pass cutoff (Hz)", 3000, 20, a["rate"] / 2 - 1)
        if f is not None:
            lab_apply(state, ed.lowpass(a, f))
    elif choice == "14":
        f = ask_float("High-pass cutoff (Hz)", 300, 20, a["rate"] / 2 - 1)
        if f is not None:
            lab_apply(state, ed.highpass(a, f))
    elif choice == "15":
        f = ask_float("Distortion amount (1-30)", 5.0, 1, 30)
        if f is not None:
            lab_apply(state, ed.distortion(a, f))
    elif choice == "16":
        n = ask_int("Repeat how many times", 2, 1, 50)
        if n is not None:
            lab_apply(state, ed.loop_audio(a, n))
    elif choice == "17":
        at = ask_float("Insert at (sec)", 0, 0)
        sec = ask_float("Silence length (sec)", 1.0, 0.01, 60)
        if at is not None and sec is not None:
            lab_apply(state, ed.insert_silence(a, at, sec))
    elif choice == "18":
        row = pick_file(user_id)
        other = load_audio_by_id(row["file_id"], user_id) if row else None
        if other:
            lab_apply(state, ed.merge(a, other))
    elif choice == "19":
        row = pick_file(user_id)
        other = load_audio_by_id(row["file_id"], user_id) if row else None
        if other:
            at = ask_float("Start the other sound at (sec)", 0, 0)
            vol = ask_float("Its volume", 1.0, 0, 5)
            if at is not None and vol is not None:
                mixed = ed.copy_audio(a)
                ed.mix_into(mixed, other, at, vol)
                lab_apply(state, mixed)
    elif choice == "20":
        lab_apply(state, ed.to_mono(a))
    elif choice == "21":
        lab_apply(state, ed.to_stereo(a))
    elif choice == "22":
        print(ascii_spectrum(a))
    else:
        print("Unknown choice.")


def audio_lab(user):
    uid = user["user_id"]
    row = pick_file(uid)
    if row is None:
        return
    audio = load_audio_by_id(row["file_id"], uid)
    if audio is None:
        print("Could not load that file (is it still on disk?).")
        return
    state = {"audio": audio, "undo": [], "redo": [], "saved": True,
             "base_name": os.path.splitext(row["file_name"])[0]}

    menu_text = (
        "\n  1 Play          2 Waveform       3 Analyse        22 Spectrum\n"
        "  4 Trim (keep)   5 Cut out        6 Volume         7 Fade in    8 Fade out\n"
        "  9 Reverse      10 Speed         11 Normalize     12 Echo\n"
        " 13 Low-pass     14 High-pass     15 Distortion    16 Loop      17 Insert silence\n"
        " 18 Merge another file after       19 Mix another file over\n"
        " 20 To mono      21 To stereo\n"
        "  u Undo   r Redo   s Save as new WAV   0 Back")
    print("\nAudio Lab - editing '%s'" % row["file_name"])
    while True:
        lab_info(state)
        print(menu_text)
        choice = input("lab> ").strip().lower()
        if choice == "0":
            if state["saved"] or confirm("You have unsaved edits. Leave anyway?"):
                return
        elif choice == "u":
            if state["undo"]:
                state["redo"].append(state["audio"])
                state["audio"] = state["undo"].pop()
                state["saved"] = False
            else:
                print("Nothing to undo.")
        elif choice == "r":
            if state["redo"]:
                state["undo"].append(state["audio"])
                state["audio"] = state["redo"].pop()
                state["saved"] = False
            else:
                print("Nothing to redo.")
        elif choice == "s":
            lab_save(state, uid)
        elif choice:
            lab_operation(state, choice, uid)


# ======================================================================
#  LIBRARY MENU
# ======================================================================
def library_menu(user):
    uid = user["user_id"]
    while True:
        choice = show_menu("AUDIO LIBRARY", [
            ("1", "Show my files"), ("2", "Import a WAV file"),
            ("3", "Play a file"), ("4", "Remove a file from library"),
            ("5", "Audio Lab (edit a file)"), ("0", "Back")])
        if choice == "1":
            print_library(uid)
        elif choice == "2":
            path = ask("Full path of the .wav file")
            if path:
                print(import_audio_file(uid, path)[1])
        elif choice == "3":
            row = pick_file(uid)
            if row and os.path.isfile(row["file_path"]):
                print("Playing ... (blocks until finished)")
                play_file(row["file_path"])
        elif choice == "4":
            row = pick_file(uid)
            if row and confirm("Remove '%s' from the library?" % row["file_name"]):
                print(remove_audio_file(row["file_id"], uid)[1])
        elif choice == "5":
            audio_lab(user)
        elif choice == "0":
            return


# ======================================================================
#  PROJECT SCREENS
# ======================================================================
EFFECT_PARAMS = {
    "gain": [("Volume factor (1 = same)", 1.0)],
    "fade_in": [("Fade length (sec)", 1.0)],
    "fade_out": [("Fade length (sec)", 1.0)],
    "reverse": [],
    "speed": [("Speed factor (2 = double)", 1.0)],
    "normalize": [("Target peak 0-1", 0.95)],
    "echo": [("Delay (sec)", 0.3), ("Strength 0-0.95", 0.5)],
    "lowpass": [("Cutoff (Hz)", 5000)],
    "highpass": [("Cutoff (Hz)", 200)],
    "distortion": [("Amount 1-30", 5.0)],
}


def screen_add_track(project_id, user_id):
    name = ask("Track name", "New track")
    kind = show_menu("TRACK TYPE", [("1", "audio  (place your WAV files)"),
                                    ("2", "beat   (drum machine)"),
                                    ("3", "instrument (synth / composer)")])
    track_type = {"1": "audio", "2": "beat", "3": "instrument"}.get(kind)
    if track_type is None:
        return
    tid, msg = add_track(project_id, user_id, name, track_type)
    print(msg)
    if tid and track_type == "beat":
        print("Tip: use 'Beat maker' to create patterns for this track.")
    if tid and track_type == "instrument":
        print("Tip: use 'Music composer' to add notes to this track.")


def screen_add_clip(project_id, user_id):
    track = pick_track(project_id, "audio")
    if track is None:
        return
    row = pick_file(user_id)
    if row is None:
        return
    start = ask_float("Start on timeline (sec)", 0, 0)
    trim_start = ask_float("Cut this many seconds off the start of the file", 0, 0)
    trim_end = ask_float("End at this point in the file (blank = play to the end)")
    vol = ask_float("Clip volume", 1.0, 0, 5)
    f_in = ask_float("Fade-in (sec)", 0, 0)
    f_out = ask_float("Fade-out (sec)", 0, 0)
    if None in (start, trim_start, vol, f_in, f_out):
        print("Cancelled.")
        return
    cid, msg = add_clip(track["track_id"], user_id, row["file_id"], start,
                        trim_start, trim_end, vol, f_in, f_out)
    print(msg)


def screen_edit_clip(project_id):
    track = pick_track(project_id, "audio")
    clip = pick_clip(track["track_id"]) if track else None
    if clip is None:
        return
    fields = {"1": ("start_time", "Start time (sec)"), "2": ("trim_start", "Trim start (sec)"),
              "3": ("trim_end", "Trim end (sec, blank = end)"), "4": ("volume", "Volume"),
              "5": ("fade_in", "Fade-in (sec)"), "6": ("fade_out", "Fade-out (sec)")}
    choice = show_menu("EDIT CLIP '%s'" % clip["file_name"],
                       [(k, v[1]) for k, v in fields.items()] + [("7", "Delete clip"), ("0", "Back")])
    if choice in fields:
        value = ask_float(fields[choice][1], None, 0)
        if value is None and choice != "3":
            print("Cancelled.")
            return
        print(update_clip(clip["clip_id"], **{fields[choice][0]: value})[1])
    elif choice == "7" and confirm("Delete this clip?"):
        delete_clip(clip["clip_id"])
        print("Clip deleted.")


def screen_effects(project_id):
    track = pick_track(project_id, "audio")
    clip = pick_clip(track["track_id"]) if track else None
    if clip is None:
        return
    while True:
        fx_list = list_clip_effects(clip["clip_id"])
        print("\nEffects on clip #%d (%s), applied in this order:" % (clip["clip_id"], clip["file_name"]))
        if not fx_list:
            print("  (none)")
        for f in fx_list:
            print("  #%-4d %-11s %s %s" % (f["ce_id"], f["effect_name"],
                                          f["param1"] if f["param1"] is not None else "",
                                          f["param2"] if f["param2"] is not None else ""))
        choice = show_menu("CLIP EFFECTS", [("1", "Add effect"), ("2", "Remove effect"), ("0", "Back")])
        if choice == "1":
            effects = list_effects()
            for i, e in enumerate(effects, start=1):
                print("  %2d. %-11s %s" % (i, e["effect_name"], e["description"]))
            n = ask_int("Effect number", None, 1, len(effects))
            if n is None:
                continue
            name = effects[n - 1]["effect_name"]
            params = []
            for label, default in EFFECT_PARAMS.get(name, []):
                params.append(ask_float(label, default))
            params += [None] * (2 - len(params))
            print(add_clip_effect(clip["clip_id"], name, params[0], params[1])[1])
        elif choice == "2":
            ce = ask_int("Effect ID to remove")
            if ce is not None:
                remove_clip_effect(ce)
        elif choice == "0":
            return


def screen_track_settings(project_id):
    track = pick_track(project_id)
    if track is None:
        return
    tid = track["track_id"]
    choice = show_menu("TRACK '%s'" % track["track_name"], [
        ("1", "Volume"), ("2", "Pan (left/right)"), ("3", "Mute on/off"),
        ("4", "Solo on/off"), ("5", "Rename"), ("6", "Delete track"), ("0", "Back")])
    if choice == "1":
        v = ask_float("Volume (1 = normal, 0-4)", float(track["volume"]), 0, 4)
        if v is not None:
            print(set_track_volume(tid, v)[1])
    elif choice == "2":
        p = ask_float("Pan (-1 left ... 0 centre ... 1 right)", float(track["pan"]), -1, 1)
        if p is not None:
            print(set_track_pan(tid, p)[1])
    elif choice == "3":
        toggle_mute(tid)
        print("Mute toggled.")
    elif choice == "4":
        toggle_solo(tid)
        print("Solo toggled.")
    elif choice == "5":
        name = ask("New name", track["track_name"])
        if name:
            rename_track(tid, name)
    elif choice == "6" and confirm("Delete track '%s' and everything on it?" % track["track_name"]):
        delete_track(tid)
        print("Track deleted.")


def screen_beats(project):
    track = pick_track(project["project_id"], "beat")
    if track is None:
        return
    tid = track["track_id"]
    while True:
        patterns = list_patterns(tid)
        print("\nPatterns on '%s' (they play in this order):" % track["track_name"])
        if not patterns:
            print("  (none yet)")
        for p in patterns:
            print("  #%-4d %-20s %2d steps  swing %.2f  repeats x%d" % (
                p["pattern_id"], p["pattern_name"], p["total_steps"],
                float(p["swing"]), p["repeats"]))
        choice = show_menu("BEAT MAKER", [("1", "New pattern"), ("2", "Edit a pattern"),
                                          ("3", "Delete a pattern"), ("0", "Back")])
        if choice == "1":
            name = ask("Pattern name", "Groove")
            steps = ask_int("Steps (8, 16, 24 or 32)", 16)
            swing = ask_float("Swing 0-1", 0.0, 0, 1)
            reps = ask_int("Repeat how many times", 4, 1, 64)
            if None in (steps, swing, reps):
                continue
            pid, msg = create_pattern(tid, name, steps, swing, reps)
            print(msg)
            if pid:
                print("Presets: " + ", ".join(list_presets()))
                preset = ask("Start from a preset (blank = empty)")
                if preset:
                    print(apply_preset(pid, preset)[1])
                beat_editor(pid, project["bpm"], project["sample_rate"])
        elif choice == "2":
            pid = ask_int("Pattern ID")
            if pid is not None and any(p["pattern_id"] == pid for p in patterns):
                beat_editor(pid, project["bpm"], project["sample_rate"])
            elif pid is not None:
                print("Not a pattern on this track.")
        elif choice == "3":
            pid = ask_int("Pattern ID to delete")
            if pid is not None and any(p["pattern_id"] == pid for p in patterns) \
                    and confirm("Delete pattern %d?" % pid):
                delete_pattern(pid)
        elif choice == "0":
            return


def screen_composer(project):
    track = pick_track(project["project_id"], "instrument")
    if track is not None:
        note_editor(track["track_id"], project["bpm"], project["sample_rate"])


def screen_export(project_id, user_id):
    name = ask("File name (blank = project name)")
    if name and not name.lower().endswith(".wav"):
        name += ".wav"
    print("Rendering ... this can take a few seconds.")
    path, msg = export_project(project_id, user_id, name or None)
    print(msg)
    if path and confirm("Play it now?"):
        play_file(path)


def project_menu(user, project_id):
    uid = user["user_id"]
    while True:
        project = get_project(project_id, uid)
        if project is None:
            return
        choice = show_menu("PROJECT: %s  (%s BPM)" % (project["name"], project["bpm"]), [
            ("1", "Show project"), ("2", "Add track"), ("3", "Add audio clip"),
            ("4", "Edit / delete a clip"), ("5", "Clip effects"),
            ("6", "Track settings (volume, pan, mute, solo)"),
            ("7", "Beat maker"), ("8", "Music composer"), ("9", "Change BPM"),
            ("10", "Preview (play the mix)"), ("11", "Export to WAV"),
            ("12", "Export history"), ("0", "Back")])
        if choice == "1":
            print_project(project_id, uid)
        elif choice == "2":
            screen_add_track(project_id, uid)
        elif choice == "3":
            screen_add_clip(project_id, uid)
        elif choice == "4":
            screen_edit_clip(project_id)
        elif choice == "5":
            screen_effects(project_id)
        elif choice == "6":
            screen_track_settings(project_id)
        elif choice == "7":
            screen_beats(project)
        elif choice == "8":
            screen_composer(project)
        elif choice == "9":
            bpm = ask_int("New BPM", project["bpm"], 20, 300)
            if bpm is not None:
                print(set_bpm(project_id, uid, bpm)[1])
        elif choice == "10":
            print("Rendering ... this can take a few seconds.")
            preview_project(project_id, uid)
        elif choice == "11":
            screen_export(project_id, uid)
        elif choice == "12":
            exports = list_exports(project_id)
            if not exports:
                print("No exports yet.")
            for e in exports:
                print("  %s  %s" % (e["exported_on"], e["output_path"]))
        elif choice == "0":
            return


def projects_menu(user):
    uid = user["user_id"]
    while True:
        projects = list_projects(uid)
        print("\nYour projects:")
        if not projects:
            print("  (none yet)")
        for p in projects:
            print("  #%-4d %-24s %3d BPM   last edited %s" % (
                p["project_id"], p["name"], p["bpm"], p["modified_at"]))
        choice = show_menu("PROJECTS", [("1", "New project"), ("2", "Open a project"),
                                        ("3", "Rename a project"), ("4", "Delete a project"),
                                        ("0", "Back")])
        if choice == "1":
            name = ask("Project name")
            bpm = ask_int("Tempo (BPM)", 120, 20, 300)
            if name and bpm:
                pid, msg = create_project(uid, name, bpm)
                print(msg)
                if pid:
                    project_menu(user, pid)
        elif choice == "2":
            pid = ask_int("Project ID")
            if pid is not None:
                if get_project(pid, uid):
                    project_menu(user, pid)
                else:
                    print("Project not found.")
        elif choice == "3":
            pid = ask_int("Project ID")
            new = ask("New name") if pid is not None else ""
            if new:
                print(rename_project(pid, uid, new)[1])
        elif choice == "4":
            pid = ask_int("Project ID to delete")
            if pid is not None and confirm("Delete project %d and all its tracks?" % pid):
                print(delete_project(pid, uid)[1])
        elif choice == "0":
            return


# ======================================================================
#  ACCOUNT AND MAIN MENU
# ======================================================================
def account_menu(user):
    """Returns True if the account was deleted (so the user is logged out)."""
    uid = user["user_id"]
    while True:
        choice = show_menu("ACCOUNT (%s)" % user["username"],
                           [("1", "Change password"), ("2", "Delete my account"), ("0", "Back")])
        if choice == "1":
            old = getpass.getpass("Current password: ")
            new = getpass.getpass("New password: ")
            print(change_password(uid, old, new)[1])
        elif choice == "2":
            if ask("Type DELETE to confirm") == "DELETE":
                ok, msg = delete_account(uid, getpass.getpass("Password: "))
                print(msg)
                if ok:
                    return True
        elif choice == "0":
            return False


def main_menu(user):
    """Returns True to exit the program, False to go back to the login screen."""
    while True:
        choice = show_menu("SOUNDPAD STUDIO - welcome, %s" % user["username"], [
            ("1", "Projects (mix, beats, music)"),
            ("2", "Audio library & Audio Lab"),
            ("3", "Account"), ("4", "Log out"), ("0", "Exit")])
        if choice == "1":
            projects_menu(user)
        elif choice == "2":
            library_menu(user)
        elif choice == "3":
            if account_menu(user):
                return False
        elif choice == "4":
            return False
        elif choice == "0":
            return True


def main():
    try:
        ensure_extra_instruments()
        while True:
            user = auth_menu()
            if user is None or main_menu(user):
                break
    except mysql.connector.Error as e:
        print("\nDatabase problem: %s" % e)
        print("Check that MySQL is running and the settings in db.py are correct.")
    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        close_connection()
    print("Goodbye!")


if __name__ == "__main__":
    main()