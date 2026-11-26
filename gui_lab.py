"""
gui_lab.py - Audio Lab: a waveform editor. Drag on the waveform to select a
region; effects apply to the selection (or the whole file if nothing is
selected). Undo/redo, zoom, spectrum analyser, merge / mix, save to library.
"""
import math
import os
import tkinter as tk
from tkinter import filedialog

import gui_theme as T
import gui_play
import editing as ed
from audio_io import load_wav, save_wav, import_audio_file, list_user_files, get_audio_file
from render import EXPORT_DIR
from visualizer import spectrum_bands
from gui_state import S, uid, set_status

L = {"audio": None, "name": "", "undo": [], "redo": [], "sel": None, "anchor": None,
     "v0": 0.0, "v1": 1.0, "ph": 0.0, "play_t": None, "saved": True, "base": "audio"}


# ======================================================================
#  BUILD
# ======================================================================
def build(parent):
    f = tk.Frame(parent, bg=T.BG)
    top = tk.Frame(f, bg=T.PANEL)
    top.pack(fill="x")
    row = tk.Frame(top, bg=T.PANEL)
    row.pack(fill="x", padx=14, pady=10)
    L["title"] = T.label(row, "No file open", T.CYAN, T.FONT_H, bg=T.PANEL)
    L["title"].pack(side="left")
    T.button(row, "Save to library", save_file, "lime").pack(side="right", padx=(6, 0))
    T.button(row, "Open from library", open_dialog, "normal").pack(side="right", padx=6)
    T.button(row, "Redo", redo, "normal").pack(side="right", padx=2)
    T.button(row, "Undo", undo, "normal").pack(side="right", padx=2)
    T.divider(row, True).pack(side="right", fill="y", padx=8)
    for text, cmd in (("Fit", zoom_fit), ("Zoom sel", zoom_selection), ("\u2212", lambda: zoom(1.4)),
                      ("+", lambda: zoom(1 / 1.4)), ("\u25b6", lambda: scroll(0.3)), ("\u25c0", lambda: scroll(-0.3))):
        T.button(row, text, cmd, "normal", padx=9).pack(side="right", padx=1)

    body = tk.Frame(f, bg=T.BG)
    body.pack(fill="both", expand=True)

    # ---- right tool panel
    tools_outer, tools = T.scrollable(body, bg=T.PANEL)
    tools_outer.pack(side="right", fill="y")
    tools_outer.configure(width=232)
    tools_outer.pack_propagate(False)
    _build_tools(tools)

    # ---- waveform + spectrum
    main = tk.Frame(body, bg=T.BG)
    main.pack(side="left", fill="both", expand=True)
    wave = tk.Canvas(main, bg=T.PANEL, highlightthickness=0)
    wave.pack(fill="both", expand=True, padx=(14, 8), pady=(12, 4))
    wave.bind("<Configure>", lambda e: draw_wave())
    wave.bind("<Button-1>", on_press)
    wave.bind("<B1-Motion>", on_drag)
    wave.bind("<ButtonRelease-1>", on_release)
    wave.bind("<Double-Button-1>", lambda e: select_all())
    T.on_wheel(wave, on_wheel)
    L["wave"] = wave
    L["info"] = T.label(main, "", T.DIM, T.FONT_MONO, bg=T.BG, anchor="w")
    L["info"].pack(fill="x", padx=16)
    spec_head = tk.Frame(main, bg=T.BG)
    spec_head.pack(fill="x", padx=16, pady=(6, 0))
    T.title(spec_head, "Spectrum analyser").pack(side="left")
    T.button(spec_head, "Analyse selection / playhead", draw_spectrum, "ghost", font=T.FONT).pack(side="right")
    spec = tk.Canvas(main, bg=T.PANEL, height=150, highlightthickness=0)
    spec.pack(fill="x", padx=(14, 8), pady=(4, 12))
    L["spec"] = spec

    S["root"].bind("<Control-z>", lambda e: undo() if S["view"] == "lab" else None, add="+")
    S["root"].bind("<Control-y>", lambda e: redo() if S["view"] == "lab" else None, add="+")
    return f


def _group(parent, text):
    T.title(parent, text, bg=T.PANEL).pack(anchor="w", padx=14, pady=(14, 4))


def _tool(parent, text, command):
    T.button(parent, text, command, "normal", font=T.FONT, pady=4).pack(fill="x", padx=14, pady=2)


def _build_tools(p):
    _group(p, "Selection")
    _tool(p, "Trim to selection", lambda: whole(trim_sel))
    _tool(p, "Cut out selection", lambda: whole(cut_sel))
    _tool(p, "Silence selection", lambda: region(silence_fn))
    _group(p, "Level")
    _tool(p, "Gain...", gain_dialog)
    _tool(p, "Normalize", lambda: region(lambda a: ed.normalize(a, 0.95)))
    _tool(p, "Fade in...", lambda: fade_dialog(True))
    _tool(p, "Fade out...", lambda: fade_dialog(False))
    _group(p, "Time & pitch")
    _tool(p, "Reverse", lambda: region(ed.reverse))
    _tool(p, "Speed...", speed_dialog)
    _tool(p, "Loop...", loop_dialog)
    _tool(p, "Insert silence at cursor...", insert_silence_dialog)
    _group(p, "Effects")
    _tool(p, "Echo...", echo_dialog)
    _tool(p, "Low-pass...", lambda: filter_dialog("Low-pass", ed.lowpass, 3000))
    _tool(p, "High-pass...", lambda: filter_dialog("High-pass", ed.highpass, 300))
    _tool(p, "Distortion...", distortion_dialog)
    _group(p, "Combine")
    _tool(p, "Merge file after...", merge_dialog)
    _tool(p, "Mix file over at cursor...", mix_dialog)
    _tool(p, "Convert to mono", lambda: whole(ed.to_mono))
    _tool(p, "Convert to stereo", lambda: whole(ed.to_stereo))
    tk.Frame(p, bg=T.PANEL, height=20).pack()


def show():
    S["play_fn"] = play_lab
    S["on_playhead"] = None
    S["on_stop"] = _on_stop
    fid = S["lab_open_file"]
    S["lab_open_file"] = None
    if fid is not None:
        load_from_library(fid)
    else:
        draw_wave()


# ======================================================================
#  LOADING / SAVING
# ======================================================================
def open_dialog():
    files = list_user_files(uid())
    if not files:
        T.show_message("Library is empty", "Import a WAV file in the Library screen first.", "info")
        return
    labels = ["%s  (%.1fs)" % (f["file_name"], float(f["duration_sec"] or 0)) for f in files]
    idx = T.choose("Open in Audio Lab", "Audio file", labels)
    if idx is not None:
        load_from_library(files[idx]["file_id"])


def load_from_library(file_id):
    row = get_audio_file(file_id, uid())
    if row is None or not os.path.isfile(row["file_path"]):
        T.show_message("Cannot open", "That file is missing from disk.", "warn")
        return

    def done(audio):
        L.update(audio=audio, name=row["file_name"], undo=[], redo=[], sel=None, ph=0.0,
                 v0=0.0, v1=max(0.01, ed.duration(audio)), saved=True,
                 base=os.path.splitext(row["file_name"])[0])
        refresh_all()
    gui_play.run_task("Loading audio...", lambda: load_wav(row["file_path"]), done)


def save_file():
    if L["audio"] is None:
        T.show_message("Save", "Open a file first.", "info")
        return
    os.makedirs(EXPORT_DIR, exist_ok=True)
    path = filedialog.asksaveasfilename(title="Save edited audio", defaultextension=".wav",
                                        initialdir=EXPORT_DIR, initialfile=L["base"] + "_edit.wav",
                                        filetypes=[("WAV audio", "*.wav")])
    if not path:
        return
    audio = L["audio"]

    def work():
        save_wav(path, ed.limit(audio))
        return import_audio_file(uid(), path)

    def done(res):
        L["saved"] = True
        set_status("Saved " + path)
        T.show_message("Saved", "Saved and added to your library:\n%s" % path, "info")
    gui_play.run_task("Saving...", work, done)


# ======================================================================
#  EDIT PLUMBING
# ======================================================================
def push(new_audio):
    L["undo"].append(L["audio"])
    L["redo"].clear()
    L["audio"] = new_audio
    L["saved"] = False
    L["v1"] = min(max(L["v1"], 0.01), max(0.01, ed.duration(new_audio)))
    if L["v1"] <= L["v0"]:
        L["v0"], L["v1"] = 0.0, max(0.01, ed.duration(new_audio))
    L["sel"] = None
    refresh_all()


def undo():
    if L["undo"]:
        L["redo"].append(L["audio"])
        L["audio"] = L["undo"].pop()
        L["sel"] = None
        refresh_all()


def redo():
    if L["redo"]:
        L["undo"].append(L["audio"])
        L["audio"] = L["redo"].pop()
        L["sel"] = None
        refresh_all()


def region(func, heavy=False, label="Applying..."):
    """Apply func to the selection (or the whole file) and push the result."""
    a = L["audio"]
    if a is None:
        T.show_message("Audio Lab", "Open a file first (Open from library).", "info")
        return
    sel = L["sel"]

    def work():
        if not sel:
            return func(a)
        s, e = sel
        pieces = [ed.trim(a, 0, s), func(ed.trim(a, s, e)), ed.trim(a, e, None)]
        pieces = [p for p in pieces if ed.length(p) > 0]
        return ed.merge_many(pieces)
    if heavy:
        gui_play.run_task(label, work, push)
    else:
        push(work())


def whole(func):
    a = L["audio"]
    if a is None:
        T.show_message("Audio Lab", "Open a file first (Open from library).", "info")
        return
    try:
        new = func(a)
    except ValueError as err:
        T.show_message("Audio Lab", str(err), "info")
        return
    if new is not None:
        push(new)


def trim_sel(a):
    if not L["sel"]:
        raise ValueError("Drag on the waveform to select the part you want to keep.")
    return ed.trim(a, L["sel"][0], L["sel"][1])


def cut_sel(a):
    if not L["sel"]:
        raise ValueError("Drag on the waveform to select the part to remove.")
    return ed.cut_out(a, L["sel"][0], L["sel"][1])


def silence_fn(r):
    return ed.make_audio(r["rate"], len(r["channels"]), ed.duration(r))


# ---- dialogs for parameterised tools
def gain_dialog():
    res = T.form("Gain", [{"key": "f", "label": "Volume factor (1 = same, 2 = double)", "kind": "float",
                           "default": 1.5, "min": 0, "max": 10}], ok="Apply")
    if res:
        region(lambda a: ed.change_volume(a, res["f"]))


def fade_dialog(fade_in):
    res = T.form("Fade " + ("in" if fade_in else "out"), [
        {"key": "s", "label": "Length (seconds)", "kind": "float", "default": 1.0, "min": 0.01, "max": 60}], ok="Apply")
    if res:
        region(lambda a: (ed.fade_in if fade_in else ed.fade_out)(a, res["s"]))


def speed_dialog():
    res = T.form("Speed", [{"key": "f", "label": "Speed factor (2 = double + higher pitch)", "kind": "float",
                            "default": 1.25, "min": 0.1, "max": 8}], ok="Apply")
    if res:
        region(lambda a: ed.change_speed(a, res["f"]), True, "Changing speed...")


def loop_dialog():
    res = T.form("Loop", [{"key": "n", "label": "Repeat how many times", "kind": "int", "default": 2,
                           "min": 1, "max": 50}], ok="Apply")
    if res:
        whole(lambda a: ed.loop_audio(a, res["n"]))


def insert_silence_dialog():
    if L["audio"] is None:
        T.show_message("Audio Lab", "Open a file first.", "info")
        return
    res = T.form("Insert silence", [{"key": "s", "label": "Length (seconds)", "kind": "float",
                                     "default": 1.0, "min": 0.01, "max": 60}], ok="Insert",
                 intro="Silence is inserted at the cursor (the last place you clicked).")
    if res:
        whole(lambda a: ed.insert_silence(a, L["ph"], res["s"]))


def echo_dialog():
    res = T.form("Echo", [
        {"key": "d", "label": "Delay (seconds)", "kind": "float", "default": 0.3, "min": 0.02, "max": 2},
        {"key": "k", "label": "Strength (0-0.95)", "kind": "float", "default": 0.5, "min": 0, "max": 0.95},
        {"key": "r", "label": "Repeats", "kind": "int", "default": 3, "min": 1, "max": 10}], ok="Apply")
    if res:
        region(lambda a: ed.add_echo(a, res["d"], res["k"], res["r"]), True, "Adding echo...")


def filter_dialog(name, func, default):
    res = T.form(name, [{"key": "hz", "label": "Cutoff (Hz)", "kind": "float", "default": default,
                         "min": 20, "max": 20000}], ok="Apply")
    if res:
        region(lambda a: func(a, min(res["hz"], a["rate"] / 2 - 1)), True, "Filtering...")


def distortion_dialog():
    res = T.form("Distortion", [{"key": "a", "label": "Amount (1-30)", "kind": "float", "default": 6,
                                 "min": 1, "max": 30}], ok="Apply")
    if res:
        region(lambda a: ed.distortion(a, res["a"]), True, "Distorting...")


def _pick_other():
    files = list_user_files(uid())
    if not files:
        T.show_message("Library is empty", "Import a WAV file first.", "info")
        return None
    labels = ["%s  (%.1fs)" % (f["file_name"], float(f["duration_sec"] or 0)) for f in files]
    idx = T.choose("Choose a file", "Audio file", labels)
    return None if idx is None else get_audio_file(files[idx]["file_id"], uid())


def merge_dialog():
    if L["audio"] is None:
        T.show_message("Audio Lab", "Open a file first.", "info")
        return
    row = _pick_other()
    if row:
        gui_play.run_task("Loading audio...", lambda: load_wav(row["file_path"]),
                          lambda other: push(ed.merge(L["audio"], other)))


def mix_dialog():
    if L["audio"] is None:
        T.show_message("Audio Lab", "Open a file first.", "info")
        return
    row = _pick_other()
    if not row:
        return
    res = T.form("Mix over", [{"key": "v", "label": "Volume of the other sound", "kind": "float",
                               "default": 1.0, "min": 0, "max": 5}], ok="Mix",
                 intro="It starts at the cursor (the last place you clicked).")
    if res is None:
        return

    def done(other):
        mixed = ed.copy_audio(L["audio"])
        ed.mix_into(mixed, other, L["ph"], res["v"])
        push(mixed)
    gui_play.run_task("Loading audio...", lambda: load_wav(row["file_path"]), done)


# ======================================================================
#  WAVEFORM DISPLAY
# ======================================================================
def refresh_all():
    a = L["audio"]
    if a is not None:
        L["title"].configure(text="%s%s" % (L["name"], "" if L["saved"] else "  \u25cf unsaved"))
        peak, rms = ed.get_peak(a), ed.get_rms(a)
        L["info"].configure(text="%.2f s  |  %d Hz  |  %s  |  peak %.1f dB  |  rms %.1f dB  |  %d edit(s)" % (
            ed.duration(a), a["rate"], "stereo" if len(a["channels"]) == 2 else "mono",
            T.to_db(peak), T.to_db(rms), len(L["undo"])))
    else:
        L["title"].configure(text="No file open")
        L["info"].configure(text="")
    draw_wave()


def _nice_step(raw):
    for s in (0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 15, 30, 60, 120, 300):
        if s >= raw:
            return s
    return 600


def draw_wave():
    c = L["wave"]
    c.delete("all")
    w, h = c.winfo_width(), c.winfo_height()
    a = L["audio"]
    if a is None:
        c.create_text(w / 2, h / 2, text="Open a file from your library to start editing\n"
                      "(Open from library, or  Library \u2192 Edit in Audio Lab)",
                      fill=T.DIM, font=T.FONT_H, justify="center")
        return
    rate, chans = a["rate"], a["channels"]
    total = len(chans[0])
    v0, v1 = L["v0"], L["v1"]
    span = max(1e-4, v1 - v0)
    lane_h = (h - 26) / len(chans)
    step = _nice_step(span / max(1.0, w / 110.0))
    t = math.ceil(v0 / step) * step
    while t < v1:
        x = (t - v0) / span * w
        c.create_line(x, 24, x, h, fill="#1a2030")
        c.create_text(x + 3, 12, text=T.fmt_time(t)[:8], fill=T.DIM, font=T.FONT_S, anchor="w")
        t += step
    colors = (T.CYAN, T.MAGENTA)
    for ci, ch in enumerate(chans):
        mid = 26 + lane_h * (ci + 0.5)
        amp = lane_h / 2 - 6
        c.create_line(0, mid, w, mid, fill=T.EDGE)
        up, down = [], []
        for px in range(0, w, 2):
            s = max(0, min(total - 1, int((v0 + px / w * span) * rate)))
            e = max(s + 1, min(total, int((v0 + (px + 2) / w * span) * rate)))
            seg = ch[s:e]
            if not seg:
                continue
            up += [px, mid - max(seg) * amp]
            down = [px, mid - min(seg) * amp] + down
        if len(up) >= 4:
            c.create_polygon(up + down, fill=colors[ci % 2], outline="")
    draw_overlay()


def _x(sec):
    w = L["wave"].winfo_width()
    return (sec - L["v0"]) / max(1e-4, L["v1"] - L["v0"]) * w


def _t(x):
    w = max(1, L["wave"].winfo_width())
    return L["v0"] + x / w * (L["v1"] - L["v0"])


def draw_overlay():
    c = L["wave"]
    c.delete("ov")
    if L["audio"] is None:
        return
    h = c.winfo_height()
    if L["sel"]:
        x0, x1 = _x(L["sel"][0]), _x(L["sel"][1])
        c.create_rectangle(x0, 24, x1, h, fill=T.CYAN, stipple="gray25", outline=T.CYAN, tags="ov")
    x = _x(L["ph"])
    c.create_line(x, 24, x, h, fill=T.MAGENTA, width=2, tags="ov")
    if L["play_t"] is not None:
        px = _x(L["play_t"])
        c.create_line(px, 24, px, h, fill=T.LIME, width=2, tags="ov")


# ---- mouse
def on_press(e):
    if L["audio"] is None:
        return
    L["anchor"] = max(0.0, min(ed.duration(L["audio"]), _t(e.x)))
    L["sel"] = None
    L["ph"] = L["anchor"]
    draw_overlay()
    gui_play.set_time(L["ph"])


def on_drag(e):
    if L["audio"] is None or L["anchor"] is None:
        return
    t = max(0.0, min(ed.duration(L["audio"]), _t(e.x)))
    lo, hi = min(L["anchor"], t), max(L["anchor"], t)
    L["sel"] = (lo, hi) if hi - lo > 0.005 else None
    draw_overlay()


def on_release(e):
    L["anchor"] = None
    if L["sel"]:
        L["ph"] = L["sel"][0]
        set_status("Selection: %.3f s  (%s - %s)" % (L["sel"][1] - L["sel"][0],
                   T.fmt_time(L["sel"][0]), T.fmt_time(L["sel"][1])))
    draw_overlay()


def select_all():
    if L["audio"] is not None:
        L["sel"] = (0.0, ed.duration(L["audio"]))
        draw_overlay()


def on_wheel(e):
    if L["audio"] is None:
        return
    if e.state & 0x1:
        scroll(-0.2 if e.delta > 0 else 0.2)
    else:
        zoom(1 / 1.25 if e.delta > 0 else 1.25, around=_t(e.x))


def zoom(factor, around=None):
    a = L["audio"]
    if a is None:
        return
    dur = ed.duration(a)
    span = max(0.01, min(dur, (L["v1"] - L["v0"]) * factor))
    centre = around if around is not None else (L["v0"] + L["v1"]) / 2
    frac = (centre - L["v0"]) / max(1e-4, L["v1"] - L["v0"])
    v0 = max(0.0, min(dur - span, centre - frac * span))
    L["v0"], L["v1"] = v0, v0 + span
    draw_wave()


def zoom_fit():
    if L["audio"] is not None:
        L["v0"], L["v1"] = 0.0, max(0.01, ed.duration(L["audio"]))
        draw_wave()


def zoom_selection():
    if L["audio"] is not None and L["sel"]:
        L["v0"], L["v1"] = L["sel"][0], max(L["sel"][1], L["sel"][0] + 0.01)
        draw_wave()


def scroll(frac):
    a = L["audio"]
    if a is None:
        return
    span = L["v1"] - L["v0"]
    dur = ed.duration(a)
    v0 = max(0.0, min(dur - span, L["v0"] + span * frac))
    L["v0"], L["v1"] = v0, v0 + span
    draw_wave()


# ======================================================================
#  PLAYBACK + SPECTRUM
# ======================================================================
def play_lab():
    a = L["audio"]
    if a is None:
        T.show_message("Play", "Open a file first.", "info")
        return
    if L["sel"]:
        start, end = L["sel"]
    else:
        start, end = L["ph"], None
    seg = ed.trim(a, start, end)
    if ed.length(seg) == 0:
        return
    dur = gui_play.play_audio(seg)
    if dur is None:
        return

    def tick(t):
        L["play_t"] = start + t
        draw_overlay()
        gui_play.set_time(start + t)

    def ended():
        L["play_t"] = None
        draw_overlay()
    gui_play.start_playhead(dur, tick, ended)


def _on_stop():
    L["play_t"] = None
    if L.get("wave") is not None:
        draw_overlay()


def draw_spectrum():
    a = L["audio"]
    c = L["spec"]
    c.delete("all")
    if a is None:
        return
    start = L["sel"][0] if L["sel"] else L["ph"]
    bands = 56
    levels, edges = spectrum_bands(a, bands, 4096, start)
    w, h = max(c.winfo_width(), 300), c.winfo_height()
    if not any(levels):
        c.create_text(w / 2, h / 2, text="(silence here - nothing to analyse)", fill=T.DIM, font=T.FONT)
        return
    bw = (w - 20) / bands
    for i, lv in enumerate(levels):
        x = 10 + i * bw
        bh = lv * (h - 34)
        color = T.blend(T.CYAN, T.MAGENTA, i / bands)
        c.create_rectangle(x + 1, h - 20 - bh, x + bw - 1, h - 20, fill=color, outline="")
    for i in (0, bands // 4, bands // 2, 3 * bands // 4, bands):
        f = edges[min(i, bands)]
        c.create_text(10 + i * bw, h - 8, text="%.0f" % f if f < 1000 else "%.1fk" % (f / 1000),
                      fill=T.DIM, font=T.FONT_S)
    c.create_text(w - 8, 10, text="4096-sample FFT at %s" % T.fmt_time(start), fill=T.DIM,
                  font=T.FONT_S, anchor="e")
