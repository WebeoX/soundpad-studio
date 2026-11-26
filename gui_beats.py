"""
gui_beats.py - Step sequencer. Click or drag across pads to paint a drum
pattern; right-click a pad to cycle soft / normal / accent. Patterns, presets,
swing, repeats and a live loop audition (re-renders when you edit).
"""
import tkinter as tk

import gui_theme as T
import gui_play
import editing as ed
import beats
from gui_state import S, uid, set_status, current_project
from projects import list_tracks, add_track

B = {"track_id": None, "pattern_id": None, "pat": None, "steps": {}, "drums": [],
     "tracks": [], "patterns": [], "paint": None, "last": None, "cache": {},
     "job": None, "left": 150, "top": 38, "pad_w": 40, "pad_h": 44, "lock": False}
VEL_CYCLE = {55: 100, 100: 127, 127: 55}


# ======================================================================
#  BUILD
# ======================================================================
def build(parent):
    f = tk.Frame(parent, bg=T.BG)
    B["frame"] = f

    # ---- left column: track + pattern list
    left = tk.Frame(f, bg=T.PANEL, width=250)
    left.pack(side="left", fill="y")
    left.pack_propagate(False)
    inner = tk.Frame(left, bg=T.PANEL, padx=16, pady=18)
    inner.pack(fill="both", expand=True)
    T.title(inner, "Beat track").pack(anchor="w")
    B["track_var"] = tk.StringVar()
    B["track_combo"] = T.combo(inner, [], B["track_var"], width=24, command=on_track_selected)
    B["track_combo"].pack(fill="x", pady=(4, 6))
    T.button(inner, "+ New beat track", new_track, "normal").pack(fill="x")
    T.divider(inner).pack(fill="x", pady=14)
    T.title(inner, "Patterns (play in order)").pack(anchor="w")
    B["plist"] = T.listbox(inner, height=9, width=26)
    B["plist"].pack(fill="x", pady=(4, 8))
    B["plist"].bind("<<ListboxSelect>>", lambda e: on_pattern_selected())
    T.button(inner, "+ New pattern", new_pattern, "accent").pack(fill="x", pady=2)
    T.button(inner, "Delete pattern", delete_pattern, "normal").pack(fill="x", pady=2)

    # ---- right: controls + grid
    right = tk.Frame(f, bg=T.BG)
    right.pack(side="left", fill="both", expand=True)
    ctl = tk.Frame(right, bg=T.BG)
    ctl.pack(fill="x", padx=22, pady=(20, 6))
    B["title"] = T.label(ctl, "Beat Maker", T.TEXT, T.FONT_H, bg=T.BG)
    B["title"].pack(side="left")
    T.button(ctl, "\u25b6  Play loop", play_pattern, "accent").pack(side="right")
    B["loop_var"] = tk.BooleanVar(value=False)
    T.check(ctl, "Loop (live)", B["loop_var"], on_loop_toggled, bg=T.BG).pack(side="right", padx=14)

    row2 = tk.Frame(right, bg=T.BG)
    row2.pack(fill="x", padx=22, pady=(0, 8))
    T.label(row2, "Preset", T.DIM, T.FONT, bg=T.BG).pack(side="left")
    B["preset_var"] = tk.StringVar(value=beats.list_presets()[0])
    T.combo(row2, beats.list_presets(), B["preset_var"], width=9).pack(side="left", padx=6)
    T.button(row2, "Apply", apply_preset, "normal").pack(side="left", padx=2)
    T.button(row2, "Randomize", randomize, "normal").pack(side="left", padx=2)
    T.button(row2, "Clear", clear, "normal").pack(side="left", padx=2)
    T.label(row2, "   Swing", T.DIM, T.FONT, bg=T.BG).pack(side="left")
    B["swing"] = T.slider(row2, 0.0, 1.0, 0.05, 0.0, None, "horizontal", 120, release=swing_released, bg=T.BG)
    B["swing"].pack(side="left", padx=6)
    T.label(row2, "Repeats", T.DIM, T.FONT, bg=T.BG).pack(side="left", padx=(10, 4))
    B["rep_var"] = tk.StringVar(value="4")
    T.spin(row2, 1, 64, B["rep_var"], 4, repeats_changed).pack(side="left")
    B["rep_var"].trace_add("write", lambda *a: repeats_changed())

    canvas = tk.Canvas(right, bg=T.BG, highlightthickness=0)
    canvas.pack(fill="both", expand=True, padx=18, pady=6)
    canvas.bind("<Configure>", lambda e: draw_grid())
    canvas.bind("<Button-1>", on_press)
    canvas.bind("<B1-Motion>", on_drag)
    canvas.bind("<ButtonRelease-1>", on_release)
    canvas.bind("<Button-3>", on_right)
    B["canvas"] = canvas
    T.label(right, "Click or drag to paint hits  \u00b7  right-click a pad: soft / normal / accent  \u00b7  "
            "click a drum name to hear it", T.DIM, T.FONT_S, bg=T.BG).pack(anchor="w", padx=24, pady=(0, 10))
    return f


def show():
    S["play_fn"] = play_pattern
    S["on_playhead"] = None
    S["on_stop"] = lambda: draw_grid()
    refresh()


# ======================================================================
#  DATA
# ======================================================================
def refresh():
    B["drums"] = beats.list_drum_samples()
    if S["project_id"] is None or current_project() is None:
        B["tracks"], B["patterns"], B["pat"], B["track_id"] = [], [], None, None
        B["track_combo"].configure(values=[])
        B["track_var"].set("")
        B["plist"].delete(0, "end")
        B["title"].configure(text="Beat Maker \u2014 open a project first")
        draw_grid()
        return
    B["tracks"] = [t for t in list_tracks(S["project_id"]) if t["track_type"] == "beat"]
    labels = ["%s  (#%d)" % (t["track_name"], t["track_id"]) for t in B["tracks"]]
    B["track_combo"].configure(values=labels)
    ids = [t["track_id"] for t in B["tracks"]]
    want = S["beat_track"] if S["beat_track"] in ids else (B["track_id"] if B["track_id"] in ids else None)
    if want is None and ids:
        want = ids[0]
    B["track_id"] = want
    if want is not None:
        B["track_var"].set(labels[ids.index(want)])
    else:
        B["track_var"].set("")
    load_patterns()


def load_patterns(select=None):
    pl = B["plist"]
    pl.delete(0, "end")
    B["patterns"] = beats.list_patterns(B["track_id"]) if B["track_id"] is not None else []
    for p in B["patterns"]:
        pl.insert("end", "%s  \u00b7  %d steps  \u00d7%d" % (p["pattern_name"], p["total_steps"], p["repeats"]))
    ids = [p["pattern_id"] for p in B["patterns"]]
    pid = select if select in ids else (B["pattern_id"] if B["pattern_id"] in ids else (ids[0] if ids else None))
    B["pattern_id"] = pid
    if pid is not None:
        pl.selection_set(ids.index(pid))
    load_pattern()


def load_pattern():
    pid = B["pattern_id"]
    B["pat"] = beats.get_pattern(pid) if pid is not None else None
    B["steps"] = {}
    if B["pat"]:
        for s in beats.get_steps(pid):
            B["steps"][(s["sample_id"], s["step_no"])] = s["velocity"]
        B["swing"].set(float(B["pat"]["swing"]))
        B["rep_var"].set(str(B["pat"]["repeats"]))
        B["title"].configure(text="%s  \u2014  %d steps" % (B["pat"]["pattern_name"], B["pat"]["total_steps"]))
    else:
        B["title"].configure(text="Beat Maker" + ("" if B["track_id"] else "  \u2014  create a beat track to begin"))
    draw_grid()


def on_track_selected():
    label = B["track_var"].get()
    for t in B["tracks"]:
        if label.endswith("(#%d)" % t["track_id"]):
            B["track_id"] = t["track_id"]
            S["beat_track"] = t["track_id"]
    B["pattern_id"] = None
    load_patterns()


def on_pattern_selected():
    sel = B["plist"].curselection()
    if sel:
        B["pattern_id"] = B["patterns"][sel[0]]["pattern_id"]
        load_pattern()


# ======================================================================
#  DRAWING
# ======================================================================
def draw_grid():
    c = B["canvas"]
    c.delete("all")
    pat = B["pat"]
    w = max(c.winfo_width(), 200)
    if pat is None:
        c.create_text(w / 2, 120, text="No pattern yet.\nCreate a beat track, then press  + New pattern.",
                      fill=T.DIM, font=T.FONT_H, justify="center")
        return
    n = pat["total_steps"]
    left, top = B["left"], B["top"]
    pad_w = max(16, min(54, (w - left - 20) // n))
    pad_h = B["pad_h"]
    B["pad_w"] = pad_w
    for s in range(n):
        x = left + s * pad_w
        if s % 4 == 0:
            c.create_text(x + 4, 16, text=str(s // 4 + 1), fill=T.TEXT, font=T.FONT_B, anchor="w")
        else:
            c.create_text(x + pad_w / 2, 16, text="\u00b7", fill=T.DIM, font=T.FONT_B)
    for r, d in enumerate(B["drums"]):
        y = top + r * pad_h
        color = T.track_color(r)
        c.create_oval(14, y + pad_h / 2 - 5, 24, y + pad_h / 2 + 5, fill=color, outline="")
        c.create_text(34, y + pad_h / 2, text=d["name"], fill=T.TEXT, font=T.FONT_B, anchor="w")
        for s in range(n):
            x = left + s * pad_w
            base = T.PANEL2 if (s // 4) % 2 == 0 else "#1b2030"
            vel = B["steps"].get((d["sample_id"], s))
            if vel:
                fill = T.blend(base, color, 0.30 + 0.70 * vel / 127.0)
                outline = color
            else:
                fill, outline = base, T.EDGE
            c.create_rectangle(x + 2, y + 3, x + pad_w - 2, y + pad_h - 3, fill=fill, outline=outline)
    draw_playhead(None)


def draw_playhead(step):
    c = B["canvas"]
    c.delete("ph")
    pat = B["pat"]
    if pat is None or step is None:
        return
    x = B["left"] + step * B["pad_w"]
    c.create_rectangle(x, B["top"] - 4, x + B["pad_w"], B["top"] + len(B["drums"]) * B["pad_h"] + 2,
                       outline=T.CYAN, width=2, tags="ph")


# ======================================================================
#  EDITING THE GRID
# ======================================================================
def _pad_at(e):
    pat = B["pat"]
    if pat is None:
        return None
    s = (e.x - B["left"]) // B["pad_w"]
    r = (e.y - B["top"]) // B["pad_h"]
    if e.x < B["left"] or e.y < B["top"] or not (0 <= s < pat["total_steps"]) or not (0 <= r < len(B["drums"])):
        return None
    return int(r), int(s)


def _set_hit(r, s, vel):
    sid = B["drums"][r]["sample_id"]
    if vel:
        beats.set_step(B["pattern_id"], sid, s, vel)
        B["steps"][(sid, s)] = vel
    else:
        beats.clear_step(B["pattern_id"], sid, s)
        B["steps"].pop((sid, s), None)


def on_press(e):
    if B["pat"] is None:
        return
    if e.x < B["left"] and e.y >= B["top"]:               # clicked a drum name
        r = int((e.y - B["top"]) // B["pad_h"])
        if 0 <= r < len(B["drums"]):
            preview_drum(r)
        return
    hit = _pad_at(e)
    if hit is None:
        return
    r, s = hit
    sid = B["drums"][r]["sample_id"]
    B["paint"] = "del" if (sid, s) in B["steps"] else "add"
    B["last"] = hit
    _set_hit(r, s, 0 if B["paint"] == "del" else 100)
    draw_grid()


def on_drag(e):
    if B["paint"] is None:
        return
    hit = _pad_at(e)
    if hit is None or hit == B["last"]:
        return
    B["last"] = hit
    r, s = hit
    sid = B["drums"][r]["sample_id"]
    if B["paint"] == "add" and (sid, s) not in B["steps"]:
        _set_hit(r, s, 100)
        draw_grid()
    elif B["paint"] == "del" and (sid, s) in B["steps"]:
        _set_hit(r, s, 0)
        draw_grid()


def on_release(e):
    if B["paint"] is not None:
        B["paint"] = None
        B["last"] = None
        schedule_restart()


def on_right(e):
    hit = _pad_at(e)
    if hit is None:
        return
    r, s = hit
    sid = B["drums"][r]["sample_id"]
    cur = B["steps"].get((sid, s))
    _set_hit(r, s, VEL_CYCLE.get(cur, 100) if cur else 55)
    draw_grid()
    schedule_restart()


# ======================================================================
#  PATTERN / TRACK ACTIONS
# ======================================================================
def new_track():
    if S["project_id"] is None:
        T.show_message("No project", "Open or create a project first.", "info")
        return
    res = T.form("New beat track", [{"key": "name", "label": "Track name", "default": "Drums"}], ok="Add track")
    if res:
        tid, msg = add_track(S["project_id"], uid(), res["name"], "beat")
        S["beat_track"] = tid
        set_status(msg)
        refresh()


def new_pattern():
    if B["track_id"] is None:
        T.show_message("No beat track", "Create a beat track first.", "info")
        return
    res = T.form("New pattern", [
        {"key": "name", "label": "Pattern name", "default": "Groove"},
        {"key": "steps", "label": "Steps", "kind": "choice", "choices": ["16", "8", "24", "32"], "default": "16"},
        {"key": "swing", "label": "Swing (0-1)", "kind": "float", "default": 0.0, "min": 0, "max": 1},
        {"key": "reps", "label": "Repeats", "kind": "int", "default": 4, "min": 1, "max": 64},
        {"key": "preset", "label": "Start from preset", "kind": "choice",
         "choices": ["(empty)"] + beats.list_presets(), "default": "(empty)"}], ok="Create")
    if res is None:
        return
    pid, msg = beats.create_pattern(B["track_id"], res["name"], int(res["steps"]), res["swing"], res["reps"])
    if pid is None:
        T.show_message("Could not create pattern", msg, "error")
        return
    if res["preset"] != "(empty)":
        beats.apply_preset(pid, res["preset"])
    B["pattern_id"] = pid
    load_patterns(select=pid)


def delete_pattern():
    if B["pat"] is None:
        return
    if T.confirm("Delete pattern", "Delete '%s'?" % B["pat"]["pattern_name"], yes="Delete", danger=True):
        beats.delete_pattern(B["pattern_id"])
        B["pattern_id"] = None
        load_patterns()


def apply_preset():
    if B["pat"] is None:
        return
    ok, msg = beats.apply_preset(B["pattern_id"], B["preset_var"].get())
    set_status(msg)
    load_pattern()
    schedule_restart()


def randomize():
    if B["pat"] is not None:
        beats.randomize_pattern(B["pattern_id"])
        load_pattern()
        schedule_restart()


def clear():
    if B["pat"] is not None:
        beats.clear_pattern(B["pattern_id"])
        load_pattern()
        schedule_restart()


def swing_released():
    if B["pat"] is not None:
        beats.set_swing(B["pattern_id"], float(B["swing"].get()))
        B["pat"] = beats.get_pattern(B["pattern_id"])
        schedule_restart()


def repeats_changed():
    if B["pat"] is None:
        return
    try:
        n = int(float(B["rep_var"].get()))
    except ValueError:
        return
    if 1 <= n <= 64 and n != B["pat"]["repeats"]:
        beats.set_repeats(B["pattern_id"], n)
        B["pat"] = beats.get_pattern(B["pattern_id"])
        i = B["patterns"].index(next(p for p in B["patterns"] if p["pattern_id"] == B["pattern_id"]))
        B["plist"].delete(i)
        B["plist"].insert(i, "%s  \u00b7  %d steps  \u00d7%d" % (B["pat"]["pattern_name"], B["pat"]["total_steps"], n))
        B["plist"].selection_set(i)


# ======================================================================
#  SOUND
# ======================================================================
def _rate_bpm():
    proj = current_project()
    return (proj["sample_rate"], proj["bpm"]) if proj else (44100, 120)


def preview_drum(r):
    rate, _bpm = _rate_bpm()
    audio = beats.sample_audio(B["drums"][r], rate, B["cache"])
    gui_play.play_audio(audio)


def play_pattern():
    if B["pat"] is None:
        T.show_message("Play", "Create or select a pattern first.", "info")
        return
    rate, bpm = _rate_bpm()
    loop = beats.render_pattern(B["pattern_id"], bpm, rate, B["cache"])
    looping = bool(B["loop_var"].get())
    audio = loop if looping else ed.loop_audio(loop, 2)
    dur = gui_play.play_audio(ed.limit(audio), loop=looping)
    if dur is None:
        return
    step_sec = 60.0 / bpm / 4
    n = B["pat"]["total_steps"]

    def tick(t):
        draw_playhead(int(t / step_sec) % n)
        gui_play.set_time(t)
    gui_play.start_playhead(dur, tick, lambda: draw_playhead(None), loop=looping)


def on_loop_toggled():
    if not B["loop_var"].get() and gui_play.is_playing():
        gui_play.stop()
        draw_playhead(None)


def schedule_restart():
    """While loop-audition is on, re-render and restart shortly after an edit."""
    if not B["loop_var"].get() or not gui_play.is_playing():
        return
    if B["job"] is not None:
        S["root"].after_cancel(B["job"])
    B["job"] = S["root"].after(350, play_pattern)
