"""
gui_mixer.py - Mixing desk: one channel strip per track (fader, pan, mute,
solo) plus a master section whose meters are measured from the real mix.
"""
import tkinter as tk

import gui_theme as T
import gui_play
import editing as ed
from gui_state import S, uid, set_status, current_project
from projects import (list_tracks, set_track_volume, set_track_pan,
                      toggle_mute, toggle_solo)

_M = {"strips": None, "meter": None, "readout": None, "norm_var": None}
SEGMENTS = 28


def build(parent):
    f = tk.Frame(parent, bg=T.BG)
    head = tk.Frame(f, bg=T.BG)
    head.pack(fill="x", padx=28, pady=(24, 4))
    T.label(head, "Mixer", T.TEXT, T.FONT_BIG, bg=T.BG).pack(side="left")
    T.label(f, "Drag a fader to set a track's level. Changes are saved to MySQL when you release the mouse.",
            T.DIM, T.FONT, bg=T.BG).pack(anchor="w", padx=30)

    desk = tk.Frame(f, bg=T.BG)
    desk.pack(fill="both", expand=True, padx=24, pady=14)
    strips = tk.Frame(desk, bg=T.BG)
    strips.pack(side="left", fill="both", expand=True)
    _M["strips"] = strips

    master = tk.Frame(desk, bg=T.PANEL, padx=18, pady=14, highlightthickness=1,
                      highlightbackground=T.MAGENTA)
    master.pack(side="right", fill="y", padx=(14, 0))
    T.label(master, "MASTER", T.MAGENTA, T.FONT_H, bg=T.PANEL).pack()
    _M["norm_var"] = tk.BooleanVar(value=True)
    T.check(master, "Auto-normalize", _M["norm_var"], _norm_changed, bg=T.PANEL).pack(pady=(8, 4))
    meter = tk.Canvas(master, width=120, height=SEGMENTS * 9 + 24, bg=T.PANEL, highlightthickness=0)
    meter.pack(pady=6)
    _M["meter"] = meter
    _M["readout"] = T.label(master, "Press Measure to meter\nthe full mix.", T.DIM, T.FONT_MONO,
                            bg=T.PANEL, justify="left")
    _M["readout"].pack(pady=6)
    T.button(master, "Measure mix", measure, "accent").pack(fill="x", pady=(4, 2))
    T.button(master, "Play mix", S_play, "normal").pack(fill="x", pady=2)
    _draw_meter(None)
    return f


def show():
    S["play_fn"] = None
    S["on_playhead"] = None
    refresh()


def S_play():
    gui_play.play_project(0.0)


def _norm_changed():
    S["auto_norm"] = bool(_M["norm_var"].get())


def refresh():
    for w in _M["strips"].winfo_children():
        w.destroy()
    if S["project_id"] is None or current_project() is None:
        T.label(_M["strips"], "Open a project to see its mixer.", T.DIM, T.FONT_H, bg=T.BG).pack(pady=60)
        return
    _M["norm_var"].set(bool(S["auto_norm"]))
    tracks = list_tracks(S["project_id"])
    if not tracks:
        T.label(_M["strips"], "This project has no tracks yet.\nAdd some in the Arrange screen.",
                T.DIM, T.FONT_H, bg=T.BG, justify="left").pack(pady=60, padx=20)
        return
    for i, t in enumerate(tracks):
        _strip(i, t)


def _pan_text(p):
    if abs(p) < 0.05:
        return "C"
    return "L%d" % round(-p * 100) if p < 0 else "R%d" % round(p * 100)


def _strip(i, t):
    color = T.track_color(i)
    tid = t["track_id"]
    s = tk.Frame(_M["strips"], bg=T.PANEL, padx=10, pady=10, highlightthickness=1,
                 highlightbackground=T.EDGE)
    s.pack(side="left", fill="y", padx=6)
    tk.Frame(s, bg=color, height=3, width=96).pack(fill="x")
    T.label(s, t["track_name"][:12], T.TEXT, T.FONT_B, bg=T.PANEL).pack(pady=(8, 0))
    T.label(s, {"audio": "AUDIO", "beat": "BEAT", "instrument": "SYNTH"}[t["track_type"]],
            T.DIM, T.FONT_S, bg=T.PANEL).pack()

    pan_label = T.label(s, _pan_text(float(t["pan"])), color, T.FONT_MONO, bg=T.PANEL)
    pan_label.pack(pady=(10, 0))

    def pan_moved(v):
        pan_label.configure(text=_pan_text(float(v)))
    pan = T.slider(s, -1.0, 1.0, 0.05, float(t["pan"]), pan_moved, "horizontal", 96,
                   release=lambda: set_track_pan(tid, float(pan.get())))
    pan.pack()
    T.label(s, "PAN", T.DIM, T.FONT_S, bg=T.PANEL).pack()

    db_label = T.label(s, "", T.TEXT, T.FONT_MONO, bg=T.PANEL)

    def vol_moved(v):
        v = float(v)
        db_label.configure(text="%.1f dB" % T.to_db(v) if v > 0 else "-inf dB")
    fader = T.slider(s, 2.0, 0.0, 0.01, None, vol_moved, "vertical", 230,
                     release=lambda: set_track_volume(tid, float(fader.get())))
    fader.set(float(t["volume"]))
    vol_moved(float(t["volume"]))
    fader.pack(pady=(12, 4))
    db_label.pack()

    row = tk.Frame(s, bg=T.PANEL)
    row.pack(pady=(10, 0))
    mute, _ = T.toggle(row, "M", lambda on: toggle_mute(tid), T.AMBER, bool(t["is_muted"]))
    solo, _ = T.toggle(row, "S", lambda on: toggle_solo(tid), T.LIME, bool(t["is_solo"]))
    mute.pack(side="left", padx=3)
    solo.pack(side="left", padx=3)


# --------------------------------------------------------------- metering
def _seg_color(i):
    frac = i / SEGMENTS
    if frac > 0.88:
        return T.RED
    if frac > 0.68:
        return T.AMBER
    return T.LIME


def _draw_meter(levels):
    """levels = (peak_l_db, peak_r_db) or None for an idle meter."""
    c = _M["meter"]
    c.delete("all")
    for ch in range(2):
        x0 = 14 + ch * 54
        lit = -1
        if levels is not None:
            db = max(-60.0, min(3.0, levels[ch]))
            lit = int((db + 60.0) / 63.0 * SEGMENTS)
        for i in range(SEGMENTS):
            y = (SEGMENTS - 1 - i) * 9 + 4
            on = i <= lit
            c.create_rectangle(x0, y, x0 + 36, y + 7,
                               fill=_seg_color(i) if on else T.PANEL3, outline="")
        c.create_text(x0 + 18, SEGMENTS * 9 + 14, text="LR"[ch], fill=T.DIM, font=T.FONT_B)


def measure():
    def done(audio):
        chans = audio["channels"]
        peaks = [max(map(abs, c)) if c else 0.0 for c in chans]
        if len(peaks) == 1:
            peaks = [peaks[0], peaks[0]]
        _draw_meter([T.to_db(p) for p in peaks])
        rms = ed.get_rms(audio)
        _M["readout"].configure(
            text="Peak  %.1f dB\nRMS   %.1f dB\nTime  %s\n%s" % (
                T.to_db(max(peaks)), T.to_db(rms), T.fmt_time(ed.duration(audio)),
                "CLIPPING!" if max(peaks) > 1.0 else "headroom OK"),
            fg=T.RED if max(peaks) > 1.0 else T.TEXT)
        set_status("Mix measured")
    gui_play.get_project_mix(done)
