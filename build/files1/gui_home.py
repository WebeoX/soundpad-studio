"""
gui_home.py - Projects screen: a grid of project cards.
"""
import tkinter as tk

import gui_theme as T
from gui_state import S, uid, set_status
from gui_data import project_counts
from projects import (list_projects, create_project, rename_project,
                      delete_project)

_H = {"frame": None, "inner": None, "sel": None, "cards": {}}


def build(parent):
    f = tk.Frame(parent, bg=T.BG)
    _H["frame"] = f
    head = tk.Frame(f, bg=T.BG)
    head.pack(fill="x", padx=28, pady=(24, 4))
    T.label(head, "Projects", T.TEXT, T.FONT_BIG, bg=T.BG).pack(side="left")
    T.button(head, "Delete", delete_selected, "normal").pack(side="right", padx=(6, 0))
    T.button(head, "Rename", rename_selected, "normal").pack(side="right", padx=6)
    T.button(head, "Open", open_selected, "normal").pack(side="right", padx=6)
    T.button(head, "+  New project", new_project, "accent").pack(side="right", padx=6)
    T.label(f, "Double-click a card to open it. Everything you make lives in MySQL.",
            T.DIM, T.FONT, bg=T.BG).pack(anchor="w", padx=30)
    outer, inner = T.scrollable(f, bg=T.BG)
    outer.pack(fill="both", expand=True, padx=20, pady=12)
    _H["inner"] = inner
    return f


def show():
    S["play_fn"] = None
    S["on_playhead"] = None
    refresh()


def _style_cards():
    for pid, card in _H["cards"].items():
        card.configure(highlightbackground=T.CYAN if pid == _H["sel"] else T.EDGE)


def _select(pid):
    _H["sel"] = pid
    _style_cards()


def _bind_all(widget, pid):
    widget.bind("<Button-1>", lambda e: _select(pid))
    widget.bind("<Double-Button-1>", lambda e: open_project(pid))
    for child in widget.winfo_children():
        _bind_all(child, pid)


def _card(i, p):
    color = T.track_color(i)
    tracks, clips = project_counts(p["project_id"])
    c = tk.Frame(_H["inner"], bg=T.PANEL, width=310, height=132,
                 highlightthickness=2, highlightbackground=T.EDGE)
    c.pack_propagate(False)
    c.grid(row=i // 3, column=i % 3, padx=10, pady=10)
    tk.Frame(c, bg=color, width=6).pack(side="left", fill="y")
    body = tk.Frame(c, bg=T.PANEL, padx=14, pady=10)
    body.pack(side="left", fill="both", expand=True)
    T.label(body, p["name"][:26], T.TEXT, T.FONT_H, bg=T.PANEL).pack(anchor="w")
    T.label(body, "%d BPM  \u00b7  %.1f kHz" % (p["bpm"], p["sample_rate"] / 1000.0),
            color, T.FONT_B, bg=T.PANEL).pack(anchor="w", pady=(2, 0))
    T.label(body, "%d tracks  \u00b7  %d audio clips" % (tracks, clips), T.DIM, T.FONT,
            bg=T.PANEL).pack(anchor="w", pady=(6, 0))
    mod = p["modified_at"]
    stamp = mod.strftime("%d %b %Y  %H:%M") if hasattr(mod, "strftime") else str(mod)
    T.label(body, "edited " + stamp, T.DIM, T.FONT_S, bg=T.PANEL).pack(anchor="w", pady=(2, 0))
    _H["cards"][p["project_id"]] = c
    _bind_all(c, p["project_id"])


def refresh():
    inner = _H["inner"]
    for w in inner.winfo_children():
        w.destroy()
    _H["cards"] = {}
    projects = list_projects(uid())
    if not projects:
        T.label(inner, "No projects yet.\nClick  + New project  to start your first track.",
                T.DIM, T.FONT_H, bg=T.BG, justify="left").grid(row=0, column=0, padx=20, pady=40)
        return
    for i, p in enumerate(projects):
        _card(i, p)
    if _H["sel"] not in _H["cards"]:
        _H["sel"] = None
    _style_cards()


# ----------------------------------------------------------------- actions
def open_project(pid):
    S["project_id"] = pid
    S["playhead"] = 0.0
    S["mix_cache"] = None
    S["sel_track"] = None
    S["update_topbar"]()
    S["go"]("arrange")


def open_selected():
    if _H["sel"] is None:
        T.show_message("Open project", "Click a project card first.", "info")
    else:
        open_project(_H["sel"])


def new_project():
    res = T.form("New project", [
        {"key": "name", "label": "Project name", "default": "Untitled"},
        {"key": "bpm", "label": "Tempo (BPM)", "kind": "int", "default": 120, "min": 20, "max": 300},
        {"key": "rate", "label": "Sample rate (Hz)", "kind": "choice",
         "choices": ["44100", "48000", "22050"], "default": "44100"}], ok="Create")
    if res is None:
        return
    pid, msg = create_project(uid(), res["name"], res["bpm"], int(res["rate"]))
    if pid is None:
        T.show_message("Could not create project", msg, "error")
        return
    set_status(msg)
    open_project(pid)


def rename_selected():
    if _H["sel"] is None:
        T.show_message("Rename", "Click a project card first.", "info")
        return
    res = T.form("Rename project", [{"key": "name", "label": "New name"}], ok="Rename")
    if res:
        rename_project(_H["sel"], uid(), res["name"])
        S["update_topbar"]()
        refresh()


def delete_selected():
    if _H["sel"] is None:
        T.show_message("Delete", "Click a project card first.", "info")
        return
    if T.confirm("Delete project", "Delete this project and all its tracks, clips, "
                 "patterns and notes?\nYour audio library files are not affected.",
                 yes="Delete", danger=True):
        if S["project_id"] == _H["sel"]:
            S["project_id"] = None
            S["update_topbar"]()
        delete_project(_H["sel"], uid())
        _H["sel"] = None
        refresh()
