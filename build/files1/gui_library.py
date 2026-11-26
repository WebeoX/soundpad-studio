"""
gui_library.py - Audio library: import WAVs, preview waveform, play, remove,
send to the Audio Lab or onto a project track.
"""
import os
import tkinter as tk
from tkinter import ttk, filedialog

import gui_theme as T
import gui_play
from gui_state import S, uid, set_status
from audio_io import (import_audio_file, list_user_files, get_audio_file,
                      remove_audio_file)
from projects import list_tracks, add_clip, add_track

_B = {"tree": None, "canvas": None, "info": None, "sel": None}


def build(parent):
    f = tk.Frame(parent, bg=T.BG)
    head = tk.Frame(f, bg=T.BG)
    head.pack(fill="x", padx=28, pady=(24, 8))
    T.label(head, "Audio Library", T.TEXT, T.FONT_BIG, bg=T.BG).pack(side="left")
    T.button(head, "Remove", remove_selected, "normal").pack(side="right", padx=(6, 0))
    T.button(head, "Add to project", add_to_project, "normal").pack(side="right", padx=6)
    T.button(head, "Edit in Audio Lab", edit_in_lab, "normal").pack(side="right", padx=6)
    T.button(head, "\u25b6 Play", play_selected, "normal").pack(side="right", padx=6)
    T.button(head, "+  Import WAV files", import_files, "accent").pack(side="right", padx=6)

    cols = ("name", "length", "rate", "channels", "bits")
    tree = ttk.Treeview(f, columns=cols, show="headings", style="Dark.Treeview",
                        selectmode="browse", height=9)
    for c, text, w in (("name", "File", 360), ("length", "Length", 110),
                       ("rate", "Sample rate", 120), ("channels", "Channels", 100),
                       ("bits", "Bit depth", 100)):
        tree.heading(c, text=text)
        tree.column(c, width=w, anchor="w" if c == "name" else "center")
    tree.pack(fill="x", padx=28)
    tree.bind("<<TreeviewSelect>>", lambda e: on_select())
    _B["tree"] = tree

    T.title(f, "Waveform preview").pack(anchor="w", padx=30, pady=(18, 4))
    canvas = tk.Canvas(f, bg=T.PANEL, height=170, highlightthickness=1,
                       highlightbackground=T.EDGE)
    canvas.pack(fill="x", padx=28)
    canvas.bind("<Configure>", lambda e: draw_preview())
    _B["canvas"] = canvas
    _B["info"] = T.label(f, "", T.DIM, T.FONT, bg=T.BG)
    _B["info"].pack(anchor="w", padx=30, pady=8)
    return f


def show():
    S["play_fn"] = None
    S["on_playhead"] = None
    refresh()


def refresh():
    tree = _B["tree"]
    for item in tree.get_children():
        tree.delete(item)
    for r in list_user_files(uid()):
        tree.insert("", "end", iid=str(r["file_id"]), values=(
            r["file_name"], "%.2f s" % float(r["duration_sec"] or 0),
            "%s Hz" % r["sample_rate"], "stereo" if r["channels"] == 2 else "mono",
            "%s-bit" % r["bit_depth"]))
    _B["sel"] = None
    draw_preview()


def _selected_row():
    sel = _B["tree"].selection()
    if not sel:
        T.show_message("Library", "Select a file in the list first.", "info")
        return None
    return get_audio_file(int(sel[0]), uid())


def on_select():
    sel = _B["tree"].selection()
    if not sel:
        return
    row = get_audio_file(int(sel[0]), uid())
    _B["sel"] = row
    if row is None or not os.path.isfile(row["file_path"]):
        _B["info"].configure(text="File missing on disk: %s" % (row["file_path"] if row else ""))
        draw_preview()
        return
    _B["info"].configure(text=row["file_path"])
    gui_play.ensure_peaks([row["file_path"]], draw_preview)


def draw_preview():
    c = _B["canvas"]
    c.delete("all")
    w, h = c.winfo_width(), c.winfo_height()
    row = _B["sel"]
    if row is None:
        c.create_text(w / 2, h / 2, text="Select a file to see its waveform",
                      fill=T.DIM, font=T.FONT)
        return
    cached = gui_play.cached_peaks(row["file_path"])
    if cached is None:
        return
    _dur, peaks = cached
    mid, amp = h / 2, h / 2 - 12
    c.create_line(0, mid, w, mid, fill=T.EDGE)
    up, down = [], []
    for x in range(0, w, 2):
        lo, hi = peaks[min(len(peaks) - 1, int(x / max(1, w) * len(peaks)))]
        up += [x, mid - hi * amp]
        down = [x, mid - lo * amp] + down
    if up:
        c.create_polygon(up + down, fill=T.CYAN, outline="")


# ----------------------------------------------------------------- actions
def import_files():
    paths = filedialog.askopenfilenames(title="Import WAV files",
                                        filetypes=[("WAV audio", "*.wav")])
    problems, added = [], 0
    for p in paths:
        fid, msg = import_audio_file(uid(), p)
        if fid is None:
            problems.append("%s: %s" % (os.path.basename(p), msg))
        else:
            added += 1
    if problems:
        T.show_message("Some files were not imported", "\n".join(problems), "warn")
    if added:
        set_status("Imported %d file(s)" % added)
    refresh()


def play_selected():
    row = _selected_row()
    if row is None or not os.path.isfile(row["file_path"]):
        return
    if gui_play.play_file(row["file_path"]):
        dur = float(row["duration_sec"] or 0)
        c = _B["canvas"]

        def tick(t):
            c.delete("ph")
            x = c.winfo_width() * (t / dur if dur else 0)
            c.create_line(x, 0, x, c.winfo_height(), fill=T.MAGENTA, width=2, tags="ph")
            gui_play.set_time(t)
        gui_play.start_playhead(dur, tick)


def remove_selected():
    row = _selected_row()
    if row and T.confirm("Remove file", "Remove '%s' from your library?\n"
                         "The WAV file stays on disk." % row["file_name"], yes="Remove", danger=True):
        ok, msg = remove_audio_file(row["file_id"], uid())
        if not ok:
            T.show_message("Cannot remove", msg, "warn")
        refresh()


def edit_in_lab():
    row = _selected_row()
    if row:
        S["lab_open_file"] = row["file_id"]
        S["go"]("lab")


def add_to_project():
    row = _selected_row()
    if row is None:
        return
    if S["project_id"] is None:
        T.show_message("No project open", "Open a project first (Projects screen).", "info")
        return
    tracks = [t for t in list_tracks(S["project_id"]) if t["track_type"] == "audio"]
    if not tracks:
        tid, _msg = add_track(S["project_id"], uid(), "Audio 1", "audio")
        tracks = [t for t in list_tracks(S["project_id"]) if t["track_id"] == tid]
    labels = ["%s  (#%d)" % (t["track_name"], t["track_id"]) for t in tracks]
    res = T.form("Add to project", [
        {"key": "track", "label": "Audio track", "kind": "choice", "choices": labels},
        {"key": "start", "label": "Start (seconds)", "kind": "float", "default": 0, "min": 0}],
        ok="Add clip")
    if res is None:
        return
    track = tracks[labels.index(res["track"])]
    cid, msg = add_clip(track["track_id"], uid(), row["file_id"], res["start"])
    set_status(msg)
    if cid:
        S["go"]("arrange")
