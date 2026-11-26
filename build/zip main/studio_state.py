"""
studio_state.py - The one shared dictionary every GUI module reads and writes.
(Procedural design: a plain dict + small helper functions, no classes.)
"""
from projects import get_project

APP = {
    "root": None,          # the tk root window
    "user": None,          # {'user_id':..., 'username':...} after login
    "project_id": None,    # currently open project (or None)
    "dirty": True,         # True = project changed since the last render
    "master": None,        # cached render: {'audio','path','levels','duration'}
    "navigate": None,      # function(view_name, payload=None) set by studio.py
    "refresh_all": None,   # function() that refreshes every project view
    "status_var": None,    # tk.StringVar shown in the status bar
}


def uid():
    return APP["user"]["user_id"]


def set_status(text):
    if APP["status_var"] is not None:
        APP["status_var"].set(text)


def mark_dirty():
    """Call after ANY change to the project so the next play re-renders it."""
    APP["dirty"] = True


def current_project():
    """The open project's database row, or None."""
    if APP["project_id"] is None or APP["user"] is None:
        return None
    return get_project(APP["project_id"], uid())


def navigate(view, payload=None):
    if APP["navigate"] is not None:
        APP["navigate"](view, payload)


def refresh_all():
    if APP["refresh_all"] is not None:
        APP["refresh_all"]()
