"""
gui.py - SOUNDPAD STUDIO (graphical version). Run this file:   python gui.py

Procedural, no classes. Layout: top bar with transport, a sidebar to switch
screens, the screen itself, and a status bar. Shared state lives in the
dictionary S (gui_state.py); every screen is a module with build() and show().
"""
import tkinter as tk
import traceback

import gui_theme as T
import gui_play
from gui_state import S, current_project
import gui_login
import gui_home
import gui_library
import gui_arrange
import gui_mixer
import gui_beats
import gui_piano
import gui_lab
import gui_stats
from db import close_connection
from synth import ensure_extra_instruments

VIEWS = [
    ("home", "\u2302   Projects", gui_home),
    ("library", "\u266b   Library", gui_library),
    ("arrange", "\u25a4   Arrange", gui_arrange),
    ("mixer", "\u2261   Mixer", gui_mixer),
    ("beats", "\u25a6   Beat Maker", gui_beats),
    ("piano", "\u266a   Piano Roll", gui_piano),
    ("lab", "\u223f   Audio Lab", gui_lab),
    ("stats", "\u25a5   Insights", gui_stats),
]
G = {"shell": None, "frames": {}, "mods": {}, "navs": {}, "lbl_project": None}


# ======================================================================
#  NAVIGATION AND TRANSPORT
# ======================================================================
def do_stop():
    gui_play.stop()
    hook = S.get("on_stop")
    if hook:
        hook()


def go(name):
    do_stop()
    for frame in G["frames"].values():
        frame.pack_forget()
    S["view"], S["play_fn"], S["on_playhead"], S["on_stop"] = name, None, None, None
    G["frames"][name].pack(fill="both", expand=True)
    for key, btn in G["navs"].items():
        active = key == name
        btn.configure(bg=T.PANEL3 if active else T.PANEL, fg=T.CYAN if active else T.TEXT)
    G["mods"][name].show()
    update_topbar()


def update_topbar():
    proj = current_project()
    if proj is None:
        G["lbl_project"].configure(text="no project open", fg=T.DIM)
    else:
        G["lbl_project"].configure(text="%s   \u00b7   %d BPM" % (proj["name"], proj["bpm"]), fg=T.TEXT)


def on_play():
    fn = S.get("play_fn")
    if fn:
        fn()
    elif S["project_id"] is None:
        T.show_message("Play", "Open or create a project first.", "info")
    else:
        gui_play.play_project(0.0)


def on_rewind():
    S["playhead"] = 0.0
    gui_play.set_time(0.0)
    hook = S.get("on_playhead")
    if hook:
        hook()


def _typing_in_field():
    w = S["root"].focus_get()
    return w is not None and w.winfo_class() in ("Entry", "TEntry", "Spinbox", "TCombobox", "Text")


def on_space(event):
    if _typing_in_field():
        return None
    if gui_play.is_playing():
        do_stop()
    else:
        on_play()
    return "break"


# ======================================================================
#  WINDOW PARTS
# ======================================================================
def _nav_button(parent, key, text):
    btn = tk.Button(parent, text=text, anchor="w", relief="flat", bd=0, highlightthickness=0,
                    bg=T.PANEL, fg=T.TEXT, activebackground=T.PANEL3, activeforeground=T.CYAN,
                    font=("Segoe UI Semibold", 11), padx=20, pady=11, cursor="hand2",
                    command=lambda: go(key))
    btn.pack(fill="x")
    G["navs"][key] = btn


def build_shell(root):
    shell = tk.Frame(root, bg=T.BG)
    shell.pack(fill="both", expand=True)
    G["shell"] = shell

    # ---- top bar
    top = tk.Frame(shell, bg=T.PANEL, height=60)
    top.pack(fill="x")
    top.pack_propagate(False)
    T.label(top, "SOUNDPAD", T.CYAN, ("Segoe UI Semibold", 15), bg=T.PANEL).pack(side="left", padx=(22, 0))
    T.label(top, "STUDIO", T.MAGENTA, ("Segoe UI Semibold", 15), bg=T.PANEL).pack(side="left", padx=(6, 22))
    G["lbl_project"] = T.label(top, "", T.DIM, T.FONT_B, bg=T.PANEL)
    G["lbl_project"].pack(side="left", padx=8)

    right = tk.Frame(top, bg=T.PANEL)
    right.pack(side="right", padx=16)
    T.button(right, "Export WAV", gui_play.export_project_wav, "magenta").pack(side="left", padx=6)
    T.label(right, S["user"]["username"], T.DIM, T.FONT, bg=T.PANEL).pack(side="left", padx=(12, 6))
    T.button(right, "Log out", logout, "ghost").pack(side="left")

    transport = tk.Frame(top, bg=T.PANEL)
    transport.place(relx=0.5, rely=0.5, anchor="center")
    T.button(transport, "\u23ee", on_rewind, "normal", padx=12).pack(side="left", padx=3)
    T.button(transport, "\u25b6  Play", on_play, "accent", padx=18).pack(side="left", padx=3)
    T.button(transport, "\u25a0  Stop", do_stop, "normal", padx=14).pack(side="left", padx=3)
    clock = tk.Label(transport, textvariable=S["time_var"], bg=T.PANEL3, fg=T.CYAN,
                     font=T.FONT_MONO_L, padx=14, pady=2)
    clock.pack(side="left", padx=(14, 0))

    tk.Frame(shell, bg=T.EDGE, height=1).pack(fill="x")

    # ---- status bar (packed before the middle so it keeps its space)
    bar = tk.Frame(shell, bg=T.PANEL, height=26)
    bar.pack(side="bottom", fill="x")
    bar.pack_propagate(False)
    tk.Label(bar, textvariable=S["status"], bg=T.PANEL, fg=T.DIM, font=T.FONT_S, anchor="w",
             padx=14).pack(side="left", fill="x", expand=True)
    T.label(bar, "space = play/stop   \u00b7   esc = stop   \u00b7   ctrl+wheel = zoom", T.DIM, T.FONT_S,
            bg=T.PANEL).pack(side="right", padx=14)

    # ---- sidebar + content
    mid = tk.Frame(shell, bg=T.BG)
    mid.pack(fill="both", expand=True)
    side = tk.Frame(mid, bg=T.PANEL, width=180)
    side.pack(side="left", fill="y")
    side.pack_propagate(False)
    tk.Frame(side, bg=T.PANEL, height=14).pack()
    for key, text, _mod in VIEWS:
        _nav_button(side, key, text)
    tk.Frame(mid, bg=T.EDGE, width=1).pack(side="left", fill="y")
    content = tk.Frame(mid, bg=T.BG)
    content.pack(side="left", fill="both", expand=True)

    G["frames"], G["mods"] = {}, {}
    for key, _text, mod in VIEWS:
        G["frames"][key] = mod.build(content)
        G["mods"][key] = mod


def on_login(user):
    gui_login.destroy()
    S["user"] = user
    S["project_id"] = None
    S["playhead"] = 0.0
    S["mix_cache"] = None
    build_shell(S["root"])
    S["status"].set("Welcome, %s. Create or open a project to begin." % user["username"])
    go("home")


def logout():
    do_stop()
    if G["shell"] is not None:
        G["shell"].destroy()
        G["shell"] = None
    G["navs"] = {}
    S["user"], S["project_id"], S["view"] = None, None, None
    gui_login.build(S["root"], on_login)


def on_error(exc, value, tb):
    text = "".join(traceback.format_exception(exc, value, tb))
    print(text)
    T.show_message("Unexpected error", text[-600:], "error")


def on_close():
    gui_play.stop()
    close_connection()
    S["root"].destroy()


# ======================================================================
#  ENTRY POINT
# ======================================================================
def main():
    root = tk.Tk()
    S["root"] = root
    root.title("Soundpad Studio")
    root.geometry("1440x900")
    root.minsize(1180, 740)
    T.setup_style(root)
    T.install_wheel(root)
    try:
        root.state("zoomed")
    except tk.TclError:
        pass
    S["status"] = tk.StringVar(value="Ready")
    S["time_var"] = tk.StringVar(value="00:00.00")
    S["go"] = go
    S["update_topbar"] = update_topbar
    root.report_callback_exception = on_error
    root.protocol("WM_DELETE_WINDOW", on_close)
    root.bind("<space>", on_space)
    root.bind("<Escape>", lambda e: do_stop())
    try:
        ensure_extra_instruments()
    except Exception as err:                     # MySQL not running / wrong password
        T.show_message("Cannot reach MySQL",
                       "Check that MySQL is running and the settings in db.py are right.\n\n%s" % err, "error")
        root.destroy()
        return
    gui_login.build(root, on_login)
    root.mainloop()


if __name__ == "__main__":
    main()
