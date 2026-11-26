"""
gui_state.py - The one shared dictionary every screen reads and writes.
(Procedural alternative to passing an "app object" around.)
"""
from projects import get_project

S = {
    "root": None,          # the Tk window
    "user": None,          # {'user_id', 'username'} after login
    "project_id": None,    # currently open project
    "view": None,          # name of the visible screen
    "playhead": 0.0,       # timeline position in seconds
    "mix_cache": None,     # (fingerprint, audio) of the last rendered mix
    "status": None,        # StringVar shown in the status bar
    "time_var": None,      # StringVar shown in the transport clock
    "play_fn": None,       # what the Play button does on this screen
    "on_playhead": None,   # redraw hook for the current screen's playhead
    "go": None,            # go(view_name) - set by gui.py
    "update_topbar": None,
    "auto_norm": True,
    "sel_track": None,
    "beat_track": None,
    "piano_track": None,
    "lab_open_file": None,
}


def uid():
    return S["user"]["user_id"]


def set_status(text):
    if S["status"] is not None:
        S["status"].set(text)


def current_project():
    """The open project's row, or None."""
    if S["project_id"] is None or S["user"] is None:
        return None
    return get_project(S["project_id"], uid())
