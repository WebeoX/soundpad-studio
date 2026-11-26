"""
gui_arrange.py - The timeline: track lanes, audio clips with waveforms,
beat and synth blocks, ruler, playhead, snapping, split/duplicate and an
inspector for the selected clip (properties + effect chain).
"""
import math
import tkinter as tk
from tkinter import ttk

import gui_theme as T
import gui_play
import gui_data
from gui_state import S, uid, set_status, current_project
from projects import (list_tracks, add_track, delete_track, rename_track,
                      toggle_mute, toggle_solo, add_clip, update_clip,
                      delete_clip, list_effects, add_clip_effect,
                      remove_clip_effect)
from synth import list_notes
from audio_io import list_user_files
from beats import list_drum_samples

HEAD_W = 214
RULER_H = 32
LANE_H = 84

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
TYPE_NAMES = {"audio": "AUDIO", "beat": "BEAT", "instrument": "SYNTH"}

A = {"pps": 60.0, "tracks": [], "clips": [], "fx": {}, "blocks": {}, "notes": {},
     "drum_ids": [], "bpm": 120, "sel_clip": None, "drag": None, "height": 100,
     "playing_t": None, "fx_ids": [], "width": 100}


# ======================================================================
#  BUILD
# ======================================================================
def build(parent):
    f = tk.Frame(parent, bg=T.BG)
    A["frame"] = f

    # ---- toolbar
    bar = tk.Frame(f, bg=T.PANEL)
    bar.pack(fill="x")
    pad = {"side": "left", "padx": 4, "pady": 8}
    tk.Frame(bar, width=10, bg=T.PANEL).pack(side="left")
    T.button(bar, "+ Audio track", lambda: add_track_dialog("audio"), "normal").pack(**pad)
    T.button(bar, "+ Beat track", lambda: add_track_dialog("beat"), "normal").pack(**pad)
    T.button(bar, "+ Synth track", lambda: add_track_dialog("instrument"), "normal").pack(**pad)
    T.divider(bar, True).pack(side="left", fill="y", padx=8, pady=8)
    T.button(bar, "Add clip", add_clip_dialog, "accent").pack(**pad)
    T.button(bar, "Split @ playhead", split_clip, "normal").pack(**pad)
    T.button(bar, "Duplicate", duplicate_clip, "normal").pack(**pad)
    T.divider(bar, True).pack(side="left", fill="y", padx=8, pady=8)
    T.label(bar, "Snap", T.DIM, T.FONT, bg=T.PANEL).pack(side="left", padx=(4, 4))
    A["snap_var"] = tk.StringVar(value="Beat")
    T.combo(bar, ["Beat", "Bar", "1/2 beat", "Off"], A["snap_var"], width=8).pack(side="left")
    T.divider(bar, True).pack(side="left", fill="y", padx=8, pady=8)
    T.button(bar, "\u2212", lambda: zoom(1 / 1.3), "normal", padx=10).pack(**pad)
    T.label(bar, "Zoom", T.DIM, T.FONT, bg=T.PANEL).pack(side="left")
    T.button(bar, "+", lambda: zoom(1.3), "normal", padx=10).pack(**pad)
    T.button(bar, "Export WAV", gui_play.export_project_wav, "magenta").pack(side="right", padx=14, pady=8)

    # ---- timeline area: header column | ruler + body
    area = tk.Frame(f, bg=T.BG)
    area.pack(fill="both", expand=True)
    area.grid_rowconfigure(1, weight=1)
    area.grid_columnconfigure(1, weight=1)
    corner = tk.Frame(area, bg=T.PANEL, width=HEAD_W, height=RULER_H)
    corner.grid(row=0, column=0, sticky="nsew")
    T.label(corner, "TRACKS", T.DIM, ("Segoe UI Semibold", 8), bg=T.PANEL).place(x=14, y=9)
    ruler = tk.Canvas(area, bg=T.PANEL, height=RULER_H, highlightthickness=0)
    ruler.grid(row=0, column=1, sticky="ew")
    head = tk.Canvas(area, bg=T.PANEL, width=HEAD_W, highlightthickness=0)
    head.grid(row=1, column=0, sticky="ns")
    body = tk.Canvas(area, bg=T.BG, highlightthickness=0)
    body.grid(row=1, column=1, sticky="nsew")
    vbar = ttk.Scrollbar(area, orient="vertical", command=_yview)
    vbar.grid(row=1, column=2, sticky="ns")
    hbar = ttk.Scrollbar(area, orient="horizontal", command=_xview)
    hbar.grid(row=2, column=1, sticky="ew")
    body.configure(xscrollcommand=_xscroll, yscrollcommand=_yscroll)
    A.update(ruler=ruler, head=head, body=body, vbar=vbar, hbar=hbar)

    body.bind("<Button-1>", on_press)
    body.bind("<B1-Motion>", on_motion)
    body.bind("<ButtonRelease-1>", on_release)
    body.bind("<Double-Button-1>", on_double)
    body.bind("<Button-3>", on_context)
    head.bind("<Button-1>", on_head_press)
    head.bind("<Double-Button-1>", on_head_double)
    head.bind("<Button-3>", on_head_context)
    ruler.bind("<Button-1>", on_ruler)
    ruler.bind("<B1-Motion>", on_ruler)
    for w in (body, head, ruler):
        T.on_wheel(w, on_wheel)

    A["empty"] = T.label(area, "Open a project from the Projects screen\nto start arranging.",
                         T.DIM, T.FONT_H, bg=T.BG, justify="center")

    # ---- inspector
    insp = tk.Frame(f, bg=T.PANEL, height=176)
    insp.pack(fill="x")
    insp.pack_propagate(False)
    tk.Frame(insp, bg=T.EDGE, height=1).pack(fill="x")
    inner = tk.Frame(insp, bg=T.PANEL, padx=18, pady=8)
    inner.pack(fill="both", expand=True)
    A["insp_title"] = T.label(inner, "", T.CYAN, T.FONT_B, bg=T.PANEL)
    A["insp_title"].grid(row=0, column=0, columnspan=8, sticky="w", pady=(0, 6))
    A["v"] = {}
    fields = [("start", "Start (s)"), ("tstart", "Trim start"), ("tend", "Trim end"),
              ("vol", "Volume"), ("fin", "Fade in"), ("fout", "Fade out")]
    for i, (key, text) in enumerate(fields):
        r, c = divmod(i, 3)
        T.label(inner, text, T.DIM, T.FONT, bg=T.PANEL).grid(row=r + 1, column=c * 2, sticky="w",
                                                              padx=(0, 6), pady=3)
        var = tk.StringVar()
        A["v"][key] = var
        T.entry(inner, var, width=9).grid(row=r + 1, column=c * 2 + 1, padx=(0, 18), pady=3)
    btns = tk.Frame(inner, bg=T.PANEL)
    btns.grid(row=3, column=0, columnspan=6, sticky="w", pady=(8, 0))
    T.button(btns, "Apply", apply_inspector, "accent").pack(side="left", padx=(0, 6))
    T.button(btns, "Delete clip", delete_selected_clip, "danger").pack(side="left", padx=6)
    fxbox = tk.Frame(inner, bg=T.PANEL)
    fxbox.grid(row=0, column=7, rowspan=4, sticky="nsew", padx=(20, 0))
    inner.grid_columnconfigure(6, weight=1)
    T.title(fxbox, "Effect chain (runs top to bottom)").pack(anchor="w")
    A["fxlist"] = T.listbox(fxbox, height=5, width=34)
    A["fxlist"].pack(side="left", pady=4)
    fxb = tk.Frame(fxbox, bg=T.PANEL)
    fxb.pack(side="left", padx=8, anchor="n", pady=4)
    T.button(fxb, "+ Effect", add_effect_dialog, "normal").pack(fill="x", pady=2)
    T.button(fxb, "Remove", remove_effect, "normal").pack(fill="x", pady=2)
    return f


def show():
    S["play_fn"] = play_from_playhead
    S["on_playhead"] = draw_playhead
    S["on_stop"] = _on_stop
    refresh()


# ======================================================================
#  SCROLLING / ZOOM / SNAP
# ======================================================================
def _xview(*args):
    A["body"].xview(*args)


def _yview(*args):
    A["body"].yview(*args)


def _xscroll(lo, hi):
    A["hbar"].set(lo, hi)
    A["ruler"].xview_moveto(lo)


def _yscroll(lo, hi):
    A["vbar"].set(lo, hi)
    A["head"].yview_moveto(lo)


def on_wheel(e):
    step = -1 if e.delta > 0 else 1
    if e.state & 0x4:                       # Ctrl + wheel = zoom
        zoom(1.15 if e.delta > 0 else 1 / 1.15)
    elif e.state & 0x1:                     # Shift + wheel = sideways
        A["body"].xview_scroll(step * 3, "units")
    else:
        A["body"].yview_scroll(step * 2, "units")


def zoom(factor):
    A["pps"] = max(12.0, min(400.0, A["pps"] * factor))
    redraw()


def _snap(seconds):
    beat = 60.0 / A["bpm"]
    grid = {"Beat": beat, "Bar": beat * 4, "1/2 beat": beat / 2}.get(A["snap_var"].get())
    if not grid:
        return seconds
    return round(seconds / grid) * grid


# ======================================================================
#  DATA
# ======================================================================
def _clear():
    for key in ("body", "head", "ruler"):
        A[key].delete("all")


def refresh():
    A["empty"].place_forget()
    pid = S["project_id"]
    proj = current_project() if pid is not None else None
    if proj is None:
        _clear()
        A["tracks"], A["clips"] = [], []
        A["empty"].place(relx=0.5, rely=0.5, anchor="center")
        A["empty"].lift()
        fill_inspector()
        return
    A["bpm"] = proj["bpm"]
    A["tracks"] = list_tracks(pid)
    A["clips"] = gui_data.project_clips(pid)
    A["fx"] = gui_data.project_clip_effects(pid)
    A["blocks"], A["notes"] = {}, {}
    for t in A["tracks"]:
        tid = t["track_id"]
        if t["track_type"] == "beat":
            A["blocks"][tid] = gui_data.beat_blocks(tid, A["bpm"])
        elif t["track_type"] == "instrument":
            A["notes"][tid] = [(float(n["midi_number"]), float(n["start_beat"]),
                                float(n["length_beats"])) for n in list_notes(tid)]
    A["drum_ids"] = [d["sample_id"] for d in list_drum_samples()]
    if A["sel_clip"] not in {c["clip_id"] for c in A["clips"]}:
        A["sel_clip"] = None
    gui_play.ensure_peaks([c["file_path"] for c in A["clips"]], _after_peaks)


def _after_peaks():
    redraw()
    fill_inspector()


def _clip(cid):
    for c in A["clips"]:
        if c["clip_id"] == cid:
            return c
    return None


def _f(value):
    return None if value is None else float(value)


def _extent():
    beat = 60.0 / A["bpm"]
    end = 0.0
    for c in A["clips"]:
        length = gui_data.clip_length(c, A["fx"].get(c["clip_id"], []), float(c["duration_sec"] or 0))
        end = max(end, float(c["start_time"]) + length)
    for blocks in A["blocks"].values():
        for b in blocks:
            end = max(end, b["start"] + b["length"])
    for notes in A["notes"].values():
        for _m, s, ln in notes:
            end = max(end, (s + ln) * beat)
    return end


# ======================================================================
#  DRAWING
# ======================================================================
def redraw():
    _clear()
    pps, bpm = A["pps"], A["bpm"]
    beat = 60.0 / bpm
    tracks = A["tracks"]
    total = max(30.0, _extent() + 10.0)
    width = int(total * pps)
    height = max(len(tracks) * LANE_H + 20, 120)
    A["width"], A["height"] = width, height
    A["body"].configure(scrollregion=(0, 0, width, height))
    A["ruler"].configure(scrollregion=(0, 0, width, RULER_H))
    A["head"].configure(scrollregion=(0, 0, HEAD_W, height))

    _draw_ruler(total, pps, beat)
    _draw_grid(total, pps, beat, height, len(tracks))
    for i, t in enumerate(tracks):
        _draw_header(i, t)
        color = T.track_color(i)
        y0 = i * LANE_H
        if t["track_type"] == "audio":
            for c in A["clips"]:
                if c["track_id"] == t["track_id"]:
                    _draw_audio_clip(c, y0, color)
        elif t["track_type"] == "beat":
            _draw_beat_blocks(t, y0, color)
        else:
            _draw_notes(t, y0, color)
    draw_playhead()


def _draw_ruler(total, pps, beat):
    r = A["ruler"]
    bar_px = beat * 4 * pps
    label_every = max(1, int(math.ceil(34.0 / bar_px)))
    step = 1 if beat * pps >= 14 else 4
    b = 0
    while b * beat <= total:
        x = b * beat * pps
        if b % 4 == 0:
            r.create_line(x, 4, x, RULER_H, fill=T.DIM)
            if (b // 4) % label_every == 0:
                r.create_text(x + 4, 9, text=str(b // 4 + 1), fill=T.TEXT,
                              font=T.FONT_S, anchor="w")
        else:
            r.create_line(x, RULER_H - 8, x, RULER_H, fill=T.EDGE)
        b += step
    sec_step = next((s for s in (1, 2, 5, 10, 15, 30, 60, 120, 300) if s * pps >= 84), 600)
    s = 0
    while s <= total:
        r.create_text(s * pps + 4, 22, text="%d:%02d" % (s // 60, s % 60),
                      fill=T.DIM, font=T.FONT_S, anchor="w")
        s += sec_step


def _draw_grid(total, pps, beat, height, n_lanes):
    c = A["body"]
    for i in range(max(n_lanes, 1) + 1):
        y0 = i * LANE_H
        if i < n_lanes:
            c.create_rectangle(0, y0, A["width"], y0 + LANE_H,
                               fill=T.PANEL if i % 2 == 0 else "#0b0e14", outline="")
        c.create_line(0, y0, A["width"], y0, fill=T.EDGE)
    show_minor = beat * pps >= 8
    b = 0
    while b * beat <= total:
        x = b * beat * pps
        if b % 4 == 0:
            c.create_line(x, 0, x, height, fill="#1d2332")
        elif show_minor:
            c.create_line(x, 0, x, height, fill="#12161f")
        b += 1


def _draw_header(i, t):
    h = A["head"]
    y0 = i * LANE_H
    color = T.track_color(i)
    selected = S["sel_track"] == t["track_id"]
    h.create_rectangle(0, y0, HEAD_W, y0 + LANE_H, fill=T.PANEL3 if selected else T.PANEL2,
                       outline=T.EDGE)
    h.create_rectangle(0, y0, 6, y0 + LANE_H, fill=color, outline="")
    h.create_text(18, y0 + 19, text=t["track_name"][:15], fill=T.TEXT, font=T.FONT_B, anchor="w")
    h.create_text(18, y0 + 40, text="%s  \u00b7  vol %.2f" % (TYPE_NAMES[t["track_type"]], float(t["volume"])),
                  fill=T.DIM, font=T.FONT_S, anchor="w")
    for x0, text, on, col in ((HEAD_W - 66, "M", t["is_muted"], T.AMBER),
                              (HEAD_W - 36, "S", t["is_solo"], T.LIME)):
        h.create_rectangle(x0, y0 + 10, x0 + 24, y0 + 28, fill=col if on else T.PANEL3, outline="")
        h.create_text(x0 + 12, y0 + 19, text=text, fill=T.DARK_TEXT if on else T.DIM, font=T.FONT_B)
    pan = float(t["pan"])
    h.create_text(18, y0 + 62, text="pan " + ("C" if abs(pan) < 0.05 else
                                              ("L%d" % round(-pan * 100) if pan < 0 else "R%d" % round(pan * 100))),
                  fill=T.DIM, font=T.FONT_S, anchor="w")


def _draw_audio_clip(c, y0, color):
    cv = A["body"]
    pps = A["pps"]
    fx = A["fx"].get(c["clip_id"], [])
    dur = float(c["duration_sec"] or 0)
    length = gui_data.clip_length(c, fx, dur)
    x0 = float(c["start_time"]) * pps
    x1 = x0 + max(4.0, length * pps)
    top, bot = y0 + 6, y0 + LANE_H - 6
    tag = "clip_%d" % c["clip_id"]
    selected = A["sel_clip"] == c["clip_id"]
    cv.create_rectangle(x0, top, x1, bot, fill=T.blend(color, T.BG, 0.80),
                        outline="#ffffff" if selected else color, width=2 if selected else 1, tags=(tag,))
    cached = gui_play.cached_peaks(c["file_path"])
    if cached and dur > 0:
        _d, peaks = cached
        n = len(peaks)
        ts = float(c["trim_start"] or 0)
        te = float(c["trim_end"]) if c["trim_end"] is not None else dur
        te = min(te, dur)
        span = max(1e-6, te - ts)
        mid, amp = (top + bot) / 2 + 6, (bot - top) / 2 - 12
        up, down = [], []
        w = x1 - x0
        for px in range(0, int(w) + 1, 2):
            pos = ts + (px / max(w, 1)) * span
            lo, hi = peaks[max(0, min(n - 1, int(pos / dur * n)))]
            up += [x0 + px, mid - hi * amp]
            down = [x0 + px, mid - lo * amp] + down
        if len(up) >= 4:
            cv.create_polygon(up + down, fill=color, outline="", tags=(tag,))
    fin, fout = float(c["fade_in"] or 0) * pps, float(c["fade_out"] or 0) * pps
    if fin > 1:
        cv.create_line(x0, bot, x0 + fin, top, fill="#ffffff", tags=(tag,))
    if fout > 1:
        cv.create_line(x1 - fout, top, x1, bot, fill="#ffffff", tags=(tag,))
    names = ",".join(f["effect_name"] for f in fx)
    cv.create_text(x0 + 6, top + 9, text=c["file_name"][:28] + (("  \u00b7 fx: " + names) if names else ""),
                   fill="#ffffff", font=T.FONT_S, anchor="w", tags=(tag,))


def _draw_beat_blocks(t, y0, color):
    cv = A["body"]
    pps = A["pps"]
    tag = "blk_%d" % t["track_id"]
    ids = A["drum_ids"]
    rows = max(1, len(ids))
    top, bot = y0 + 6, y0 + LANE_H - 6
    row_h = (bot - top - 16) / rows
    for blk in A["blocks"].get(t["track_id"], []):
        x0 = blk["start"] * pps
        x1 = x0 + blk["length"] * pps
        cv.create_rectangle(x0, top, x1, bot, fill=T.blend(color, T.BG, 0.82), outline=color,
                            tags=(tag,))
        step_px = blk["loop"] / blk["steps"] * pps
        for rep in range(min(blk["repeats"], 24)):
            lx = x0 + rep * blk["loop"] * pps
            if rep:
                cv.create_line(lx, top, lx, bot, fill=T.blend(color, T.BG, 0.55), tags=(tag,))
            for sid, step in blk["hits"]:
                if sid in ids:
                    row = ids.index(sid)
                    hx = lx + step * step_px
                    hy = top + 16 + row * row_h
                    cv.create_rectangle(hx, hy, hx + max(2, step_px * 0.7), hy + max(2, row_h - 1),
                                        fill=color, outline="", tags=(tag,))
        cv.create_text(x0 + 6, top + 8, text="%s  \u00d7%d" % (blk["name"], blk["repeats"]),
                       fill="#ffffff", font=T.FONT_S, anchor="w", tags=(tag,))
    if not A["blocks"].get(t["track_id"]):
        cv.create_text(14, y0 + LANE_H / 2, text="empty beat track \u2014 double-click the track name to open the Beat Maker",
                       fill=T.DIM, font=T.FONT_S, anchor="w")


def _draw_notes(t, y0, color):
    cv = A["body"]
    pps = A["pps"]
    beat = 60.0 / A["bpm"]
    tag = "blk_%d" % t["track_id"]
    notes = A["notes"].get(t["track_id"], [])
    if not notes:
        cv.create_text(14, y0 + LANE_H / 2, text="empty synth track \u2014 double-click the track name to open the Piano Roll",
                       fill=T.DIM, font=T.FONT_S, anchor="w")
        return
    lo = min(n[0] for n in notes)
    hi = max(n[0] for n in notes)
    top, bot = y0 + 6, y0 + LANE_H - 6
    x_end = max((s + ln) * beat for _m, s, ln in notes) * pps
    cv.create_rectangle(0, top, x_end, bot, fill=T.blend(color, T.BG, 0.85), outline=color, tags=(tag,))
    span = max(1.0, hi - lo)
    for m, s, ln in notes:
        y = top + 8 + (hi - m) / span * (bot - top - 22)
        cv.create_rectangle(s * beat * pps, y, max(s * beat * pps + 2, (s + ln) * beat * pps - 1),
                            y + 4, fill=color, outline="", tags=(tag,))


def draw_playhead():
    body, ruler = A["body"], A["ruler"]
    body.delete("ph")
    ruler.delete("ph")
    pps = A["pps"]
    x = S["playhead"] * pps
    body.create_line(x, 0, x, A["height"], fill=T.MAGENTA, width=2, tags="ph")
    ruler.create_polygon(x - 6, 0, x + 6, 0, x, 10, fill=T.MAGENTA, outline="", tags="ph")
    if A["playing_t"] is not None:
        px = A["playing_t"] * pps
        body.create_line(px, 0, px, A["height"], fill=T.LIME, width=2, tags="ph")
        view_lo = body.canvasx(0)
        if px < view_lo or px > view_lo + body.winfo_width() - 60:
            body.xview_moveto(max(0.0, (px - 80) / max(1, A["width"])))


# ======================================================================
#  MOUSE
# ======================================================================
def _hit(cx, cy):
    body = A["body"]
    for item in reversed(body.find_overlapping(cx, cy, cx, cy)):
        for tg in body.gettags(item):
            if tg.startswith("clip_"):
                return "clip", int(tg[5:])
            if tg.startswith("blk_"):
                return "block", int(tg[4:])
    return None


def on_press(e):
    body = A["body"]
    cx, cy = body.canvasx(e.x), body.canvasy(e.y)
    lane = int(cy // LANE_H)
    if 0 <= lane < len(A["tracks"]):
        S["sel_track"] = A["tracks"][lane]["track_id"]
    hit = _hit(cx, cy)
    if hit and hit[0] == "clip":
        A["sel_clip"] = hit[1]
        clip = _clip(hit[1])
        A["drag"] = {"id": hit[1], "x0": cx, "orig": float(clip["start_time"]),
                     "dx": 0.0, "moved": False}
    else:
        A["sel_clip"] = None
        A["drag"] = None
    redraw()
    fill_inspector()


def on_motion(e):
    d = A["drag"]
    if not d:
        return
    cx = A["body"].canvasx(e.x)
    dx = cx - d["x0"]
    if abs(dx) > 3:
        d["moved"] = True
    if d["moved"]:
        A["body"].move("clip_%d" % d["id"], dx - d["dx"], 0)
        d["dx"] = dx


def on_release(e):
    d, A["drag"] = A["drag"], None
    if d and d["moved"]:
        new = max(0.0, _snap(d["orig"] + d["dx"] / A["pps"]))
        update_clip(d["id"], start_time=round(new, 3))
        refresh()


def on_double(e):
    body = A["body"]
    hit = _hit(body.canvasx(e.x), body.canvasy(e.y))
    if hit and hit[0] == "block":
        _open_editor(hit[1])


def _open_editor(track_id):
    for t in A["tracks"]:
        if t["track_id"] == track_id:
            if t["track_type"] == "beat":
                S["beat_track"] = track_id
                S["go"]("beats")
            elif t["track_type"] == "instrument":
                S["piano_track"] = track_id
                S["go"]("piano")


def on_context(e):
    body = A["body"]
    cx, cy = body.canvasx(e.x), body.canvasy(e.y)
    hit = _hit(cx, cy)
    menu = T.dark_menu()
    if hit and hit[0] == "clip":
        A["sel_clip"] = hit[1]
        redraw()
        fill_inspector()
        menu.add_command(label="Split at playhead", command=split_clip)
        menu.add_command(label="Duplicate", command=duplicate_clip)
        menu.add_command(label="Add effect...", command=add_effect_dialog)
        menu.add_separator()
        menu.add_command(label="Delete clip", command=delete_selected_clip)
    elif hit and hit[0] == "block":
        menu.add_command(label="Open editor", command=lambda: _open_editor(hit[1]))
    else:
        def put():
            S["playhead"] = max(0.0, _snap(cx / A["pps"]))
            draw_playhead()
            gui_play.set_time(S["playhead"])
        menu.add_command(label="Move playhead here", command=put)
    T.popup(menu, e)


def _track_at(e):
    cy = A["head"].canvasy(e.y)
    lane = int(cy // LANE_H)
    if 0 <= lane < len(A["tracks"]):
        return A["tracks"][lane], cy - lane * LANE_H
    return None, 0


def on_head_press(e):
    t, y_in = _track_at(e)
    if t is None:
        return
    S["sel_track"] = t["track_id"]
    if y_in < 34 and HEAD_W - 66 <= e.x <= HEAD_W - 42:
        toggle_mute(t["track_id"])
        refresh()
    elif y_in < 34 and HEAD_W - 36 <= e.x <= HEAD_W - 12:
        toggle_solo(t["track_id"])
        refresh()
    else:
        redraw()


def on_head_double(e):
    t, _y = _track_at(e)
    if t is None:
        return
    if t["track_type"] == "audio":
        rename_dialog(t)
    else:
        _open_editor(t["track_id"])


def on_head_context(e):
    t, _y = _track_at(e)
    if t is None:
        return
    menu = T.dark_menu()
    menu.add_command(label="Rename...", command=lambda: rename_dialog(t))
    if t["track_type"] != "audio":
        menu.add_command(label="Open editor", command=lambda: _open_editor(t["track_id"]))
    menu.add_separator()
    menu.add_command(label="Delete track", command=lambda: delete_track_dialog(t))
    T.popup(menu, e)


def on_ruler(e):
    x = A["ruler"].canvasx(e.x)
    S["playhead"] = max(0.0, _snap(x / A["pps"]))
    draw_playhead()
    gui_play.set_time(S["playhead"])


# ======================================================================
#  TRACKS
# ======================================================================
def add_track_dialog(kind):
    if S["project_id"] is None:
        T.show_message("No project", "Open or create a project first.", "info")
        return
    n = sum(1 for t in A["tracks"] if t["track_type"] == kind) + 1
    default = {"audio": "Audio", "beat": "Drums", "instrument": "Synth"}[kind] + " %d" % n
    res = T.form("New %s track" % TYPE_NAMES[kind].lower(), [{"key": "name", "label": "Track name", "default": default}],
                 ok="Add track")
    if res:
        tid, msg = add_track(S["project_id"], uid(), res["name"], kind)
        set_status(msg)
        refresh()


def rename_dialog(t):
    res = T.form("Rename track", [{"key": "name", "label": "New name", "default": t["track_name"]}], ok="Rename")
    if res:
        rename_track(t["track_id"], res["name"])
        refresh()


def delete_track_dialog(t):
    if T.confirm("Delete track", "Delete '%s' and everything on it?" % t["track_name"],
                 yes="Delete", danger=True):
        delete_track(t["track_id"])
        refresh()


# ======================================================================
#  CLIPS
# ======================================================================
def add_clip_dialog():
    pid = S["project_id"]
    if pid is None:
        T.show_message("No project", "Open or create a project first.", "info")
        return
    files = list_user_files(uid())
    if not files:
        T.show_message("Library is empty", "Import a WAV file in the Library screen first.", "info")
        return
    audio_tracks = [t for t in A["tracks"] if t["track_type"] == "audio"]
    if not audio_tracks:
        add_track(pid, uid(), "Audio 1", "audio")
        refresh()
        audio_tracks = [t for t in A["tracks"] if t["track_type"] == "audio"]
    t_labels = ["%s  (#%d)" % (t["track_name"], t["track_id"]) for t in audio_tracks]
    f_labels = ["%s  (#%d)" % (f["file_name"], f["file_id"]) for f in files]
    default_track = t_labels[0]
    for t, lab in zip(audio_tracks, t_labels):
        if t["track_id"] == S["sel_track"]:
            default_track = lab
    res = T.form("Add audio clip", [
        {"key": "track", "label": "Track", "kind": "choice", "choices": t_labels, "default": default_track},
        {"key": "file", "label": "Audio file", "kind": "choice", "choices": f_labels},
        {"key": "start", "label": "Start (seconds)", "kind": "float", "default": round(S["playhead"], 2), "min": 0}],
        ok="Add clip")
    if res is None:
        return
    track = audio_tracks[t_labels.index(res["track"])]
    fid = files[f_labels.index(res["file"])]["file_id"]
    cid, msg = add_clip(track["track_id"], uid(), fid, res["start"])
    set_status(msg)
    if cid:
        A["sel_clip"] = cid
    refresh()


def fill_inspector():
    lb = A["fxlist"]
    lb.delete(0, "end")
    A["fx_ids"] = []
    c = _clip(A["sel_clip"]) if A["sel_clip"] is not None else None
    v = A["v"]
    if c is None:
        A["insp_title"].configure(text="No clip selected \u2014 click a clip on the timeline")
        for var in v.values():
            var.set("")
        return
    A["insp_title"].configure(text="%s    (clip #%d)" % (c["file_name"], c["clip_id"]))
    v["start"].set("%.3f" % float(c["start_time"]))
    v["tstart"].set("%.3f" % float(c["trim_start"] or 0))
    v["tend"].set("" if c["trim_end"] is None else "%.3f" % float(c["trim_end"]))
    v["vol"].set("%.2f" % float(c["volume"]))
    v["fin"].set("%.2f" % float(c["fade_in"] or 0))
    v["fout"].set("%.2f" % float(c["fade_out"] or 0))
    for fx in A["fx"].get(c["clip_id"], []):
        params = " ".join(str(float(p)) for p in (fx["param1"], fx["param2"]) if p is not None)
        lb.insert("end", "%s  %s" % (fx["effect_name"], params))
        A["fx_ids"].append(fx["ce_id"])


def apply_inspector():
    c = _clip(A["sel_clip"]) if A["sel_clip"] is not None else None
    if c is None:
        return
    v = A["v"]
    try:
        tend = v["tend"].get().strip()
        fields = {"start_time": float(v["start"].get()), "trim_start": float(v["tstart"].get()),
                  "trim_end": float(tend) if tend else None, "volume": float(v["vol"].get()),
                  "fade_in": float(v["fin"].get()), "fade_out": float(v["fout"].get())}
    except ValueError:
        T.show_message("Clip properties", "Please enter numbers only (leave 'Trim end' empty to play to the end).", "warn")
        return
    if fields["trim_end"] is not None and fields["trim_end"] <= fields["trim_start"]:
        T.show_message("Clip properties", "'Trim end' must be larger than 'Trim start'.", "warn")
        return
    update_clip(c["clip_id"], **fields)
    set_status("Clip updated")
    refresh()


def delete_selected_clip():
    c = _clip(A["sel_clip"]) if A["sel_clip"] is not None else None
    if c and T.confirm("Delete clip", "Delete this clip from the timeline?", yes="Delete", danger=True):
        delete_clip(c["clip_id"])
        A["sel_clip"] = None
        refresh()


def _copy_effects(src_clip_id, dst_clip_id):
    for fx in A["fx"].get(src_clip_id, []):
        add_clip_effect(dst_clip_id, fx["effect_name"], _f(fx["param1"]), _f(fx["param2"]))


def split_clip():
    c = _clip(A["sel_clip"]) if A["sel_clip"] is not None else None
    if c is None:
        T.show_message("Split clip", "Select a clip first, then click the ruler to place the playhead.", "info")
        return
    fx = A["fx"].get(c["clip_id"], [])
    dur = float(c["duration_sec"] or 0)
    length = gui_data.clip_length(c, fx, dur)
    start, ph = float(c["start_time"]), S["playhead"]
    if not (start + 0.05 < ph < start + length - 0.05):
        T.show_message("Split clip", "Click the ruler to put the playhead inside the selected clip first.", "info")
        return
    split_pt = float(c["trim_start"] or 0) + (ph - start) * gui_data.speed_factor(fx)
    old_end = _f(c["trim_end"])
    update_clip(c["clip_id"], trim_end=round(split_pt, 3), fade_out=0)
    new_id, msg = add_clip(c["track_id"], uid(), c["file_id"], round(ph, 3), round(split_pt, 3),
                           old_end, float(c["volume"]), 0, float(c["fade_out"] or 0))
    if new_id:
        _copy_effects(c["clip_id"], new_id)
        A["sel_clip"] = new_id
    set_status("Clip split" if new_id else msg)
    refresh()


def duplicate_clip():
    c = _clip(A["sel_clip"]) if A["sel_clip"] is not None else None
    if c is None:
        T.show_message("Duplicate", "Select a clip first.", "info")
        return
    fx = A["fx"].get(c["clip_id"], [])
    length = gui_data.clip_length(c, fx, float(c["duration_sec"] or 0))
    new_id, msg = add_clip(c["track_id"], uid(), c["file_id"], round(float(c["start_time"]) + length, 3),
                           float(c["trim_start"] or 0), _f(c["trim_end"]), float(c["volume"]),
                           float(c["fade_in"] or 0), float(c["fade_out"] or 0))
    if new_id:
        _copy_effects(c["clip_id"], new_id)
        A["sel_clip"] = new_id
    set_status("Clip duplicated" if new_id else msg)
    refresh()


def add_effect_dialog():
    c = _clip(A["sel_clip"]) if A["sel_clip"] is not None else None
    if c is None:
        T.show_message("Add effect", "Select a clip first.", "info")
        return
    effects = list_effects()
    labels = ["%s \u2014 %s" % (e["effect_name"], e["description"]) for e in effects]
    idx = T.choose("Add effect", "Effect", labels)
    if idx is None:
        return
    name = effects[idx]["effect_name"]
    params = EFFECT_PARAMS.get(name, [])
    values = [None, None]
    if params:
        fields = [{"key": "p%d" % i, "label": lab, "kind": "float", "default": d}
                  for i, (lab, d) in enumerate(params)]
        res = T.form("Effect: " + name, fields, ok="Add")
        if res is None:
            return
        for i in range(len(params)):
            values[i] = res["p%d" % i]
    ok, msg = add_clip_effect(c["clip_id"], name, values[0], values[1])
    set_status(msg)
    refresh()


def remove_effect():
    sel = A["fxlist"].curselection()
    if not sel:
        T.show_message("Remove effect", "Select an effect in the list first.", "info")
        return
    remove_clip_effect(A["fx_ids"][sel[0]])
    refresh()


# ======================================================================
#  PLAYBACK
# ======================================================================
def play_from_playhead():
    def tick(t):
        A["playing_t"] = t
        draw_playhead()

    def ended():
        A["playing_t"] = None
        draw_playhead()
    gui_play.play_project(S["playhead"], tick, ended)


def _on_stop():
    A["playing_t"] = None
    if A.get("body") is not None:
        draw_playhead()
