"""
gui_piano.py - Piano roll composer. Click to add notes, drag to move, drag the
right edge to resize, right-click to delete. Scale highlighting + lock, chord
progressions, arpeggios, bass lines, a random-melody generator, an instrument
designer (ADSR) and a QWERTY keyboard you can play live.
"""
import math
import tkinter as tk
from tkinter import ttk

import gui_theme as T
import gui_play
import gui_data
import editing as ed
import synth
from gui_state import S, uid, set_status, current_project
from projects import list_tracks, add_track

LO, HI = 36, 96                    # C2 .. C7
KEY_H = 16
KEYS_W = 84
RULER_H = 26
BLACK = (1, 3, 6, 8, 10)
QWERTY = {"a": 0, "w": 1, "s": 2, "e": 3, "d": 4, "f": 5, "t": 6, "g": 7, "y": 8,
          "h": 9, "u": 10, "j": 11, "k": 12, "o": 13, "l": 14, "p": 15, ";": 16}
LENGTHS = {"1/4": 0.25, "1/2": 0.5, "1": 1.0, "2": 2.0, "4": 4.0}
SNAPS = {"1/4": 0.25, "1/2": 0.5, "1": 1.0, "Off": 0.0}

P = {"track_id": None, "instr_id": None, "instr": None, "instruments": [], "tracks": [],
     "notes": [], "sel": None, "drag": None, "beat_w": 46.0, "nbeats": 64, "oct": 4,
     "down": set(), "play_beat": None, "bpm": 120}


# ======================================================================
#  BUILD
# ======================================================================
def build(parent):
    f = tk.Frame(parent, bg=T.BG)
    P["frame"] = f

    top = tk.Frame(f, bg=T.PANEL)
    top.pack(fill="x")
    r1 = tk.Frame(top, bg=T.PANEL)
    r1.pack(fill="x", padx=14, pady=(10, 4))
    T.label(r1, "Track", T.DIM, T.FONT, bg=T.PANEL).pack(side="left")
    P["track_var"] = tk.StringVar()
    T.combo(r1, [], P["track_var"], width=18, command=on_track_selected).pack(side="left", padx=6)
    P["track_combo"] = r1.winfo_children()[-1]
    T.button(r1, "+ Synth track", new_track, "normal").pack(side="left", padx=2)
    T.label(r1, "   Instrument", T.DIM, T.FONT, bg=T.PANEL).pack(side="left")
    P["instr_var"] = tk.StringVar()
    P["instr_combo"] = T.combo(r1, [], P["instr_var"], width=14, command=on_instrument_selected)
    P["instr_combo"].pack(side="left", padx=6)
    T.button(r1, "Design...", design_instrument, "normal").pack(side="left", padx=2)
    T.label(r1, "   Note length", T.DIM, T.FONT, bg=T.PANEL).pack(side="left")
    P["len_var"] = tk.StringVar(value="1")
    T.combo(r1, list(LENGTHS), P["len_var"], width=4).pack(side="left", padx=6)
    T.label(r1, "Snap", T.DIM, T.FONT, bg=T.PANEL).pack(side="left", padx=(6, 0))
    P["snap_var"] = tk.StringVar(value="1/2")
    T.combo(r1, list(SNAPS), P["snap_var"], width=4).pack(side="left", padx=6)
    T.label(r1, "Velocity", T.DIM, T.FONT, bg=T.PANEL).pack(side="left", padx=(6, 0))
    P["vel"] = T.slider(r1, 1, 127, 1, 100, None, "horizontal", 90, release=velocity_released, bg=T.PANEL)
    P["vel"].pack(side="left", padx=6)
    T.button(r1, "\u25b6  Play track", play_track, "accent").pack(side="right")

    r2 = tk.Frame(top, bg=T.PANEL)
    r2.pack(fill="x", padx=14, pady=(2, 10))
    T.label(r2, "Scale", T.DIM, T.FONT, bg=T.PANEL).pack(side="left")
    P["root_var"] = tk.StringVar(value="C")
    T.combo(r2, synth.NOTE_NAMES, P["root_var"], width=4, command=redraw_bg).pack(side="left", padx=6)
    P["scale_var"] = tk.StringVar(value="major")
    T.combo(r2, list(synth.SCALES), P["scale_var"], width=16, command=redraw_bg).pack(side="left", padx=2)
    P["lock_var"] = tk.BooleanVar(value=False)
    T.check(r2, "Lock to scale", P["lock_var"], bg=T.PANEL).pack(side="left", padx=10)
    T.divider(r2, True).pack(side="left", fill="y", padx=8, pady=2)
    for text, cmd in (("Chords...", chords_dialog), ("Bass...", bass_dialog),
                      ("Arpeggio...", arp_dialog), ("Melody...", melody_dialog)):
        T.button(r2, text, cmd, "normal").pack(side="left", padx=2)
    T.divider(r2, True).pack(side="left", fill="y", padx=8, pady=2)
    for text, semis in (("\u221212", -12), ("\u22121", -1), ("+1", 1), ("+12", 12)):
        T.button(r2, text, lambda s=semis: transpose(s), "normal", padx=8).pack(side="left", padx=1)
    T.button(r2, "Clear all", clear_all, "danger").pack(side="right")
    T.label(r2, "keys: A W S E D F T G Y H U J K ...   Z/X = octave", T.DIM, T.FONT_S, bg=T.PANEL).pack(
        side="right", padx=14)

    # ---- canvases
    area = tk.Frame(f, bg=T.BG)
    area.pack(fill="both", expand=True)
    area.grid_rowconfigure(1, weight=1)
    area.grid_columnconfigure(1, weight=1)
    tk.Frame(area, bg=T.PANEL, width=KEYS_W, height=RULER_H).grid(row=0, column=0, sticky="nsew")
    ruler = tk.Canvas(area, bg=T.PANEL, height=RULER_H, highlightthickness=0)
    ruler.grid(row=0, column=1, sticky="ew")
    keys = tk.Canvas(area, bg=T.PANEL, width=KEYS_W, highlightthickness=0)
    keys.grid(row=1, column=0, sticky="ns")
    grid = tk.Canvas(area, bg=T.BG, highlightthickness=0)
    grid.grid(row=1, column=1, sticky="nsew")
    vbar = ttk.Scrollbar(area, orient="vertical", command=lambda *a: grid.yview(*a))
    vbar.grid(row=1, column=2, sticky="ns")
    hbar = ttk.Scrollbar(area, orient="horizontal", command=lambda *a: grid.xview(*a))
    hbar.grid(row=2, column=1, sticky="ew")

    def xs(lo, hi):
        hbar.set(lo, hi)
        ruler.xview_moveto(lo)

    def ys(lo, hi):
        vbar.set(lo, hi)
        keys.yview_moveto(lo)
    grid.configure(xscrollcommand=xs, yscrollcommand=ys)
    P.update(ruler=ruler, keys=keys, grid=grid)
    grid.bind("<Button-1>", on_press)
    grid.bind("<B1-Motion>", on_motion)
    grid.bind("<ButtonRelease-1>", on_release)
    grid.bind("<Button-3>", on_right)
    keys.bind("<Button-1>", on_key_click)
    for w in (grid, keys, ruler):
        T.on_wheel(w, on_wheel)
    S["root"].bind("<KeyPress>", on_key_down, add="+")
    S["root"].bind("<KeyRelease>", on_key_up, add="+")
    S["root"].bind("<Delete>", lambda e: delete_selected(), add="+")
    P["empty"] = T.label(area, "Open a project and add a Synth track\nto start composing.",
                         T.DIM, T.FONT_H, bg=T.BG, justify="center")
    return f


def show():
    S["play_fn"] = play_track
    S["on_playhead"] = None
    S["on_stop"] = _on_stop
    refresh()
    # start scrolled around middle C
    P["grid"].yview_moveto(max(0.0, (HI - 76) * KEY_H / max(1, (HI - LO + 1) * KEY_H)))


# ======================================================================
#  DATA
# ======================================================================
def refresh():
    P["empty"].place_forget()
    proj = current_project() if S["project_id"] is not None else None
    P["instruments"] = synth.list_instruments()
    labels = ["%s (#%d)" % (i["name"], i["instrument_id"]) for i in P["instruments"]]
    P["instr_combo"].configure(values=labels)
    if proj is None:
        P["tracks"], P["notes"], P["track_id"] = [], [], None
        P["track_combo"].configure(values=[])
        P["track_var"].set("")
        P["empty"].place(relx=0.5, rely=0.5, anchor="center")
        P["empty"].lift()
        redraw()
        return
    P["bpm"] = proj["bpm"]
    P["tracks"] = [t for t in list_tracks(S["project_id"]) if t["track_type"] == "instrument"]
    t_labels = ["%s  (#%d)" % (t["track_name"], t["track_id"]) for t in P["tracks"]]
    P["track_combo"].configure(values=t_labels)
    ids = [t["track_id"] for t in P["tracks"]]
    want = S["piano_track"] if S["piano_track"] in ids else (P["track_id"] if P["track_id"] in ids else None)
    if want is None and ids:
        want = ids[0]
    P["track_id"] = want
    P["track_var"].set(t_labels[ids.index(want)] if want is not None else "")
    if P["instr"] is None and P["instruments"]:
        select_instrument(P["instruments"][0]["instrument_id"])
    elif P["instr"] is not None:
        select_instrument(P["instr"]["instrument_id"])
    if want is None:
        P["empty"].place(relx=0.5, rely=0.5, anchor="center")
        P["empty"].lift()
    load_notes()


def select_instrument(iid):
    for i in P["instruments"]:
        if i["instrument_id"] == iid:
            P["instr"] = i
            P["instr_id"] = iid
            P["instr_var"].set("%s (#%d)" % (i["name"], iid))


def on_instrument_selected():
    label = P["instr_var"].get()
    for i in P["instruments"]:
        if label.endswith("(#%d)" % i["instrument_id"]):
            select_instrument(i["instrument_id"])
            preview(synth.note_to_midi("C4"))


def on_track_selected():
    label = P["track_var"].get()
    for t in P["tracks"]:
        if label.endswith("(#%d)" % t["track_id"]):
            P["track_id"] = t["track_id"]
            S["piano_track"] = t["track_id"]
    P["sel"] = None
    load_notes()


def load_notes():
    P["notes"] = []
    if P["track_id"] is not None:
        for n in synth.list_notes(P["track_id"]):
            P["notes"].append({"id": n["note_id"], "midi": n["midi_number"],
                               "start": float(n["start_beat"]), "len": float(n["length_beats"]),
                               "vel": n["velocity"], "instr": n["instrument_name"]})
    end = max([n["start"] + n["len"] for n in P["notes"]] + [0.0])
    P["nbeats"] = max(32, int(math.ceil((end + 16) / 4.0) * 4))
    redraw()


def _note(nid):
    for n in P["notes"]:
        if n["id"] == nid:
            return n
    return None


# ======================================================================
#  DRAWING
# ======================================================================
def _scale_set():
    root = synth.NOTE_NAMES.index(P["root_var"].get())
    return root, {(root + iv) % 12 for iv in synth.SCALES[P["scale_var"].get()]}


def redraw():
    redraw_bg()


def redraw_bg(*_args):
    g, k, r = P["grid"], P["keys"], P["ruler"]
    for c in (g, k, r):
        c.delete("all")
    bw = P["beat_w"]
    W = int(P["nbeats"] * bw)
    H = (HI - LO + 1) * KEY_H
    g.configure(scrollregion=(0, 0, W, H))
    r.configure(scrollregion=(0, 0, W, RULER_H))
    k.configure(scrollregion=(0, 0, KEYS_W, H))
    root, scale = _scale_set()
    chromatic = P["scale_var"].get() == "chromatic"
    for m in range(LO, HI + 1):
        y = (HI - m) * KEY_H
        pc = m % 12
        base = "#0c0f15" if pc in BLACK else "#121722"
        if not chromatic and pc in scale:
            base = T.blend(base, T.CYAN, 0.22 if pc == root else 0.09)
        g.create_rectangle(0, y, W, y + KEY_H, fill=base, outline="")
        g.create_line(0, y + KEY_H, W, y + KEY_H, fill="#2a3144" if pc == 0 else "#171c28")
        if pc in BLACK:
            k.create_rectangle(0, y, KEYS_W - 24, y + KEY_H, fill="#1b2030", outline=T.EDGE)
            k.create_rectangle(KEYS_W - 24, y, KEYS_W, y + KEY_H, fill="#e8ebf3", outline="#9aa2b5")
        else:
            k.create_rectangle(0, y, KEYS_W, y + KEY_H, fill="#e8ebf3", outline="#9aa2b5")
        if pc == 0:
            k.create_text(KEYS_W - 6, y + KEY_H / 2, text=synth.midi_to_name(m), fill="#1b2030",
                          font=T.FONT_S, anchor="e")
        elif not chromatic and pc == root:
            k.create_oval(6, y + 4, 12, y + 10, fill=T.CYAN, outline="")
    for b in range(P["nbeats"] + 1):
        x = b * bw
        g.create_line(x, 0, x, H, fill="#232a3b" if b % 4 == 0 else "#161b26")
        if b % 4 == 0:
            r.create_line(x, 4, x, RULER_H, fill=T.DIM)
            r.create_text(x + 4, 12, text=str(b // 4 + 1), fill=T.TEXT, font=T.FONT_S, anchor="w")
        else:
            r.create_line(x, RULER_H - 7, x, RULER_H, fill=T.EDGE)
    draw_notes()


def draw_notes():
    g = P["grid"]
    g.delete("note")
    g.delete("ph")
    bw = P["beat_w"]
    for n in P["notes"]:
        if not (LO <= n["midi"] <= HI):
            continue
        x0 = n["start"] * bw
        x1 = max(x0 + 6, (n["start"] + n["len"]) * bw)
        y = (HI - n["midi"]) * KEY_H
        sel = P["sel"] == n["id"]
        fill = T.blend(T.PANEL3, T.CYAN, 0.30 + 0.70 * n["vel"] / 127.0)
        tag = ("note", "note_%d" % n["id"])
        g.create_rectangle(x0 + 1, y + 2, x1 - 1, y + KEY_H - 2, fill=fill,
                           outline="#ffffff" if sel else T.CYAN, width=2 if sel else 1, tags=tag)
        g.create_rectangle(x1 - 6, y + 2, x1 - 1, y + KEY_H - 2, fill=T.blend(fill, "#ffffff", 0.35),
                           outline="", tags=tag)
    draw_playhead()


def draw_playhead():
    g, r = P["grid"], P["ruler"]
    g.delete("ph")
    r.delete("ph")
    if P["play_beat"] is None:
        return
    x = P["play_beat"] * P["beat_w"]
    H = (HI - LO + 1) * KEY_H
    g.create_line(x, 0, x, H, fill=T.LIME, width=2, tags="ph")
    r.create_polygon(x - 5, 0, x + 5, 0, x, 9, fill=T.LIME, outline="", tags="ph")


# ======================================================================
#  MOUSE
# ======================================================================
def _snap(beats_value):
    step = SNAPS[P["snap_var"].get()]
    return round(beats_value / step) * step if step else beats_value


def _note_at(cx, cy):
    bw = P["beat_w"]
    for n in reversed(P["notes"]):
        x0 = n["start"] * bw
        x1 = max(x0 + 6, (n["start"] + n["len"]) * bw)
        y = (HI - n["midi"]) * KEY_H
        if x0 <= cx <= x1 and y <= cy <= y + KEY_H:
            return n, cx >= x1 - 7
    return None, False


def on_press(e):
    if P["track_id"] is None or P["instr_id"] is None:
        return
    g = P["grid"]
    cx, cy = g.canvasx(e.x), g.canvasy(e.y)
    note, edge = _note_at(cx, cy)
    if note:
        P["sel"] = note["id"]
        P["drag"] = {"id": note["id"], "mode": "resize" if edge else "move", "x0": cx, "y0": cy,
                     "start": note["start"], "len": note["len"], "midi": note["midi"], "moved": False}
        draw_notes()
        return
    midi = HI - int(cy // KEY_H)
    if not (LO <= midi <= HI):
        return
    if P["lock_var"].get():
        _root, scale = _scale_set()
        if midi % 12 not in scale:
            set_status("Off-scale note blocked (Lock to scale is on)")
            return
    start = max(0.0, _snap(cx / P["beat_w"]))
    length = LENGTHS[P["len_var"].get()]
    nid, msg = synth.add_note(P["track_id"], P["instr_id"], midi, start, length, int(P["vel"].get()))
    if nid is None:
        T.show_message("Cannot add note", msg, "warn")
        return
    P["sel"] = nid
    load_notes()
    preview(midi)


def on_motion(e):
    d = P["drag"]
    if not d:
        return
    g = P["grid"]
    cx, cy = g.canvasx(e.x), g.canvasy(e.y)
    n = _note(d["id"])
    if n is None:
        return
    if abs(cx - d["x0"]) > 3 or abs(cy - d["y0"]) > 3:
        d["moved"] = True
    if not d["moved"]:
        return
    bw = P["beat_w"]
    if d["mode"] == "move":
        n["start"] = max(0.0, _snap(d["start"] + (cx - d["x0"]) / bw))
        row_shift = int(cy // KEY_H) - int(d["y0"] // KEY_H)
        n["midi"] = max(LO, min(HI, d["midi"] - row_shift))
    else:
        step = SNAPS[P["snap_var"].get()] or 0.125
        n["len"] = max(step, _snap(d["len"] + (cx - d["x0"]) / bw))
    draw_notes()


def on_release(e):
    d, P["drag"] = P["drag"], None
    if not d or not d["moved"]:
        return
    n = _note(d["id"])
    if n:
        gui_data.update_note(n["id"], n["midi"], n["start"], n["len"])
        if n["midi"] != d["midi"]:
            preview(n["midi"])
        load_notes()


def on_right(e):
    g = P["grid"]
    note, _edge = _note_at(g.canvasx(e.x), g.canvasy(e.y))
    if note:
        synth.delete_note(note["id"])
        if P["sel"] == note["id"]:
            P["sel"] = None
        load_notes()


def delete_selected():
    if S["view"] == "piano" and P["sel"] is not None:
        synth.delete_note(P["sel"])
        P["sel"] = None
        load_notes()


def velocity_released():
    n = _note(P["sel"]) if P["sel"] is not None else None
    if n:
        gui_data.update_note(n["id"], n["midi"], n["start"], n["len"], int(P["vel"].get()))
        load_notes()


def on_key_click(e):
    cy = P["keys"].canvasy(e.y)
    midi = HI - int(cy // KEY_H)
    if LO <= midi <= HI:
        preview(midi)


def on_wheel(e):
    if e.state & 0x4:
        P["beat_w"] = max(14.0, min(160.0, P["beat_w"] * (1.12 if e.delta > 0 else 1 / 1.12)))
        redraw_bg()
    elif e.state & 0x1:
        P["grid"].xview_scroll((-1 if e.delta > 0 else 1) * 3, "units")
    else:
        P["grid"].yview_scroll((-1 if e.delta > 0 else 1) * 2, "units")


# ======================================================================
#  QWERTY KEYBOARD
# ======================================================================
def _typing_in_field():
    w = S["root"].focus_get()
    return w is not None and w.winfo_class() in ("Entry", "TEntry", "Spinbox", "TCombobox", "Text", "Listbox")


def on_key_down(e):
    if S["view"] != "piano" or _typing_in_field():
        return
    ch = (e.char or "").lower()
    if ch == "z":
        P["oct"] = max(1, P["oct"] - 1)
        set_status("Keyboard octave: C%d" % P["oct"])
    elif ch == "x":
        P["oct"] = min(7, P["oct"] + 1)
        set_status("Keyboard octave: C%d" % P["oct"])
    elif ch in QWERTY and ch not in P["down"]:
        P["down"].add(ch)
        preview((P["oct"] + 1) * 12 + QWERTY[ch])


def on_key_up(e):
    P["down"].discard((e.char or "").lower())


# ======================================================================
#  SOUND
# ======================================================================
def preview(midi):
    if P["instr"] is None or not (0 <= midi <= 127):
        return
    samples = synth.render_note(P["instr"], midi, 0.55, 100, 44100)
    gui_play.play_audio({"rate": 44100, "channels": [samples, list(samples)]})


def play_track():
    if P["track_id"] is None:
        T.show_message("Play", "Add a Synth track and some notes first.", "info")
        return
    tid, bpm = P["track_id"], P["bpm"]
    rate = (current_project() or {"sample_rate": 44100})["sample_rate"]

    def work():
        audio = synth.render_instrument_track(tid, bpm, rate)
        return None if audio is None else ed.limit(ed.normalize(audio, 0.9))

    def done(audio):
        if audio is None:
            T.show_message("Play", "This track has no notes yet.", "info")
            return
        dur = gui_play.play_audio(audio)
        if dur is None:
            return
        beat_sec = 60.0 / bpm

        def tick(t):
            P["play_beat"] = t / beat_sec
            draw_playhead()
            gui_play.set_time(t)

        def ended():
            P["play_beat"] = None
            draw_playhead()
        gui_play.start_playhead(dur, tick, ended)
    gui_play.run_task("Rendering notes...", work, done)


def _on_stop():
    P["play_beat"] = None
    if P.get("grid") is not None:
        draw_playhead()


# ======================================================================
#  COMPOSING TOOLS
# ======================================================================
def _need_track():
    if P["track_id"] is None or P["instr_id"] is None:
        T.show_message("Piano roll", "Create a Synth track first (button at the top).", "info")
        return False
    return True


def new_track():
    if S["project_id"] is None:
        T.show_message("No project", "Open or create a project first.", "info")
        return
    n = len(P["tracks"]) + 1
    res = T.form("New synth track", [{"key": "name", "label": "Track name", "default": "Synth %d" % n}], ok="Add track")
    if res:
        tid, msg = add_track(S["project_id"], uid(), res["name"], "instrument")
        S["piano_track"] = tid
        set_status(msg)
        refresh()


def _run_tool(func):
    try:
        count = func()
    except (ValueError, KeyError) as err:
        T.show_message("Could not do that", str(err), "warn")
        return
    set_status("%d notes added" % count)
    load_notes()


def chords_dialog():
    if not _need_track():
        return
    res = T.form("Chord progression", [
        {"key": "prog", "label": "Progression", "kind": "choice", "choices": list(synth.PROGRESSIONS)},
        {"key": "root", "label": "Key / root note", "default": "C3"},
        {"key": "start", "label": "Start beat", "kind": "float", "default": 0, "min": 0},
        {"key": "bpc", "label": "Beats per chord", "kind": "float", "default": 4, "min": 0.5, "max": 16},
        {"key": "reps", "label": "Repeats", "kind": "int", "default": 2, "min": 1, "max": 16}],
        ok="Add chords", intro="pop = I-V-vi-IV, 50s = I-vi-IV-V, jazz = ii-V-I, sad/epic = minor keys.")
    if res:
        _run_tool(lambda: synth.add_progression(P["track_id"], P["instr_id"], synth.note_to_midi(res["root"], 3),
                                                res["prog"], res["start"], res["bpc"], res["reps"]))


def bass_dialog():
    if not _need_track():
        return
    res = T.form("Bass line", [
        {"key": "prog", "label": "Follow progression", "kind": "choice", "choices": list(synth.PROGRESSIONS)},
        {"key": "root", "label": "Key / root note", "default": "C3"},
        {"key": "start", "label": "Start beat", "kind": "float", "default": 0, "min": 0},
        {"key": "reps", "label": "Repeats", "kind": "int", "default": 2, "min": 1, "max": 16}],
        ok="Add bass", intro="Tip: pick a bass instrument (e.g. Sub Bass) first.")
    if res:
        _run_tool(lambda: synth.add_bass_line(P["track_id"], P["instr_id"], synth.note_to_midi(res["root"], 3),
                                              res["prog"], res["start"], 4.0, res["reps"]))


def arp_dialog():
    if not _need_track():
        return
    res = T.form("Arpeggio", [
        {"key": "root", "label": "Root note", "default": "C3"},
        {"key": "type", "label": "Chord", "kind": "choice", "choices": list(synth.CHORDS)},
        {"key": "start", "label": "Start beat", "kind": "float", "default": 0, "min": 0},
        {"key": "total", "label": "Total beats", "kind": "float", "default": 8, "min": 1, "max": 128},
        {"key": "step", "label": "Step (beats)", "kind": "float", "default": 0.5, "min": 0.125, "max": 4},
        {"key": "pat", "label": "Pattern", "kind": "choice", "choices": ["up", "down", "updown"]}], ok="Add")
    if res:
        _run_tool(lambda: synth.add_arpeggio(P["track_id"], P["instr_id"], synth.note_to_midi(res["root"], 3),
                                             res["type"], res["start"], res["total"], res["step"], res["pat"]))


def melody_dialog():
    if not _need_track():
        return
    res = T.form("Random melody", [
        {"key": "root", "label": "Root note", "default": "C4"},
        {"key": "scale", "label": "Scale", "kind": "choice", "choices": list(synth.SCALES), "default": "major_pentatonic"},
        {"key": "start", "label": "Start beat", "kind": "float", "default": 0, "min": 0},
        {"key": "bars", "label": "Bars", "kind": "int", "default": 4, "min": 1, "max": 32},
        {"key": "seed", "label": "Seed (blank = random)", "kind": "int", "optional": True}], ok="Generate",
        intro="A random walk along the scale that always ends on the root. Use the same seed to get the same tune.")
    if res:
        _run_tool(lambda: synth.random_melody(P["track_id"], P["instr_id"], synth.note_to_midi(res["root"], 4),
                                              res["scale"], res["start"], res["bars"], 4, res["seed"]))


def design_instrument():
    res = T.form("Instrument designer", [
        {"key": "name", "label": "Name", "default": "My Synth"},
        {"key": "wave", "label": "Waveform", "kind": "choice", "choices": list(synth.WAVE_FUNCS)},
        {"key": "a", "label": "Attack (s)", "kind": "float", "default": 0.01, "min": 0, "max": 9},
        {"key": "d", "label": "Decay (s)", "kind": "float", "default": 0.15, "min": 0, "max": 9},
        {"key": "s", "label": "Sustain (0-1)", "kind": "float", "default": 0.7, "min": 0, "max": 1},
        {"key": "r", "label": "Release (s)", "kind": "float", "default": 0.25, "min": 0, "max": 9}], ok="Create",
        intro="ADSR = how loud the note is over time: Attack up, Decay down, Sustain hold, Release fade.")
    if res is None:
        return
    iid, msg = synth.add_instrument(res["name"], res["wave"], res["a"], res["d"], res["s"], res["r"])
    if iid is None:
        T.show_message("Could not create instrument", msg, "warn")
        return
    refresh()
    select_instrument(iid)
    preview(synth.note_to_midi("C4"))


def transpose(semitones):
    if P["track_id"] is None:
        return
    ok, msg = synth.transpose_track(P["track_id"], semitones)
    set_status(msg)
    if ok:
        load_notes()


def clear_all():
    if P["track_id"] is not None and P["notes"] and T.confirm(
            "Clear track", "Delete all %d notes on this track?" % len(P["notes"]), yes="Clear", danger=True):
        synth.clear_notes(P["track_id"])
        P["sel"] = None
        load_notes()
