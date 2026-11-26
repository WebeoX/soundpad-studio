"""
gui_login.py - Login / register screen with an animated neon waveform.
"""
import math
import tkinter as tk

import gui_theme as T
from gui_state import S
from auth import login_user, register_user

_L = {"frame": None, "job": None, "phase": 0.0, "on_login": None}

WAVES = [  # colour, amplitude (fraction of height), cycles, speed
    (T.CYAN, 0.30, 3.0, 1.4),
    (T.MAGENTA, 0.22, 4.5, -1.0),
    (T.LIME, 0.14, 7.0, 2.0),
]


def _draw_waves(canvas):
    w, h = canvas.winfo_width(), canvas.winfo_height()
    canvas.delete("all")
    if w < 20 or h < 20:
        return
    for i, (color, amp, cycles, speed) in enumerate(WAVES):
        pts = []
        for x in range(0, w + 1, 5):
            env = math.sin(math.pi * x / w)
            y = h / 2 + amp * h * env * math.sin(x / w * cycles * 2 * math.pi
                                                  + _L["phase"] * speed + i)
            pts += [x, y]
        canvas.create_line(*pts, fill=color, width=2, smooth=True)


def _animate(canvas):
    if not canvas.winfo_exists():
        return
    _L["phase"] += 0.06
    _draw_waves(canvas)
    _L["job"] = S["root"].after(40, lambda: _animate(canvas))


def stop_animation():
    if _L["job"] is not None:
        try:
            S["root"].after_cancel(_L["job"])
        except tk.TclError:
            pass
        _L["job"] = None


def build(parent, on_login):
    """Create the login screen inside parent. on_login(user_dict) is called
    after a successful login."""
    _L["on_login"] = on_login
    f = tk.Frame(parent, bg=T.BG)
    _L["frame"] = f

    wave = tk.Canvas(f, bg=T.BG, height=170, highlightthickness=0)
    wave.pack(fill="x", pady=(70, 0))
    T.label(f, "SOUNDPAD STUDIO", T.CYAN, T.FONT_BIG, bg=T.BG).pack(pady=(4, 0))
    T.label(f, "PRO AUDIO WORKSTATION  \u00b7  Python \u00d7 MySQL", T.DIM, T.FONT,
            bg=T.BG).pack(pady=(0, 24))

    card = tk.Frame(f, bg=T.PANEL, padx=34, pady=26, highlightthickness=1,
                    highlightbackground=T.EDGE)
    card.pack()
    user_var, pass_var = tk.StringVar(), tk.StringVar()
    T.title(card, "Username").pack(anchor="w")
    user_entry = T.entry(card, user_var, width=30)
    user_entry.pack(pady=(2, 12), fill="x")
    T.title(card, "Password").pack(anchor="w")
    pass_entry = T.entry(card, pass_var, width=30, show="\u2022")
    pass_entry.pack(pady=(2, 8), fill="x")
    msg = T.label(card, "", T.RED, T.FONT, bg=T.PANEL, wraplength=260, justify="left")
    msg.pack(anchor="w", pady=(0, 8))

    def do_login(event=None):
        user = login_user(user_var.get(), pass_var.get())
        if user is None:
            msg.configure(text="Invalid username or password.", fg=T.RED)
            return
        stop_animation()
        _L["on_login"](user)

    def do_register():
        res = T.form("Create account", [
            {"key": "u", "label": "Username", "default": user_var.get()},
            {"key": "p", "label": "Password", "kind": "password"},
            {"key": "c", "label": "Confirm password", "kind": "password"}],
            ok="Create account",
            intro="3-30 letters, digits or underscores. Password: 6+ characters mixing letters and digits.")
        if res is None:
            return
        if res["p"] != res["c"]:
            msg.configure(text="Passwords did not match.", fg=T.RED)
            return
        ok, text = register_user(res["u"], res["p"])
        msg.configure(text=text, fg=T.LIME if ok else T.RED)
        if ok:
            user_var.set(res["u"])
            pass_var.set("")

    row = tk.Frame(card, bg=T.PANEL)
    row.pack(fill="x")
    T.button(row, "Log in", do_login, "accent", padx=26).pack(side="left")
    T.button(row, "Create account", do_register, "ghost").pack(side="right")
    user_entry.bind("<Return>", do_login)
    pass_entry.bind("<Return>", do_login)

    f.pack(fill="both", expand=True)
    user_entry.focus_set()
    _animate(wave)
    return f


def destroy():
    stop_animation()
    if _L["frame"] is not None:
        _L["frame"].destroy()
        _L["frame"] = None
