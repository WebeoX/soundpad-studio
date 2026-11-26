"""
studio_theme.py - Dark "studio" look, widget helpers, dialogs, background tasks.
Procedural: every widget is built by a plain function, no classes.
"""
import threading
import tkinter as tk
from tkinter import ttk

# ------------------------------------------------------------------ palette
C = {
    "bg": "#0a0b10", "panel": "#11131a", "panel2": "#171a23", "panel3": "#1e2230",
    "line": "#2a2f3f", "text": "#dde1ec", "muted": "#7b8296", "dim": "#4b5165",
    "cyan": "#22e6ff", "magenta": "#ff3d9a", "lime": "#b4ff39", "amber": "#ffb020",
    "violet": "#9b6bff", "red": "#ff4d5e", "green": "#3dff9a",
}
TRACK_COLORS = ["#22e6ff", "#ff3d9a", "#b4ff39", "#ffb020",
                "#9b6bff", "#ff6b3d", "#3dff9a", "#4d8dff"]

FONT_UI = ("Segoe UI", 10)
FONT_BOLD = ("Segoe UI", 10, "bold")
FONT_SMALL = ("Segoe UI", 8)
FONT_MONO = ("Consolas", 10)
FONT_MONO_BIG = ("Consolas", 20, "bold")
FONT_TITLE = ("Consolas", 15, "bold")
FONT_HEAD = ("Consolas", 9, "bold")


# ---------------------------------------------------------- colour utilities
def _rgb(h):
    return int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)


def _hex(r, g, b):
    return "#%02x%02x%02x" % (max(0, min(255, int(r))), max(0, min(255, int(g))),
                              max(0, min(255, int(b))))


def blend(c1, c2, t):
    """Mix two #rrggbb colours: t=0 -> c1, t=1 -> c2."""
    a, b = _rgb(c1), _rgb(c2)
    return _hex(*(a[i] + (b[i] - a[i]) * t for i in range(3)))


def shade(color, factor):
    r, g, b = _rgb(color)
    return _hex(r * factor, g * factor, b * factor)


def track_color(index):
    return TRACK_COLORS[index % len(TRACK_COLORS)]


def fmt_time(seconds):
    """Seconds -> 'm:ss.cc'."""
    seconds = max(0.0, seconds)
    m = int(seconds // 60)
    return "%d:%05.2f" % (m, seconds - 60 * m)


# ---------------------------------------------------------------- ttk style
def setup_style(root):
    root.configure(bg=C["bg"])
    st = ttk.Style(root)
    try:
        st.theme_use("clam")
    except tk.TclError:
        pass
    st.configure(".", background=C["panel"], foreground=C["text"],
                 fieldbackground=C["panel3"], bordercolor=C["line"],
                 lightcolor=C["line"], darkcolor=C["line"],
                 troughcolor=C["panel2"], font=FONT_UI)
    st.configure("TFrame", background=C["panel"])
    st.configure("TLabel", background=C["panel"], foreground=C["text"])
    st.configure("TCombobox", fieldbackground=C["panel3"], background=C["panel3"],
                 foreground=C["text"], arrowcolor=C["cyan"], bordercolor=C["line"],
                 selectbackground=C["panel3"], selectforeground=C["text"],
                 padding=3)
    st.map("TCombobox", fieldbackground=[("readonly", C["panel3"])],
           foreground=[("readonly", C["text"])],
           background=[("active", C["line"])])
    st.configure("TSpinbox", fieldbackground=C["panel3"], foreground=C["text"],
                 arrowcolor=C["cyan"], background=C["panel3"])
    st.configure("Treeview", background=C["panel2"], fieldbackground=C["panel2"],
                 foreground=C["text"], rowheight=28, borderwidth=0,
                 font=FONT_UI)
    st.map("Treeview", background=[("selected", "#0e4654")],
           foreground=[("selected", "#ffffff")])
    st.configure("Treeview.Heading", background=C["panel3"], foreground=C["muted"],
                 relief="flat", font=FONT_HEAD)
    st.map("Treeview.Heading", background=[("active", C["line"])])
    for orient in ("Vertical", "Horizontal"):
        st.configure(orient + ".TScrollbar", background=C["panel3"],
                     troughcolor=C["panel2"], bordercolor=C["panel2"],
                     arrowcolor=C["muted"], gripcount=0)
    st.configure("Horizontal.TScale", background=C["panel"], troughcolor=C["panel3"])
    for opt, val in (("background", C["panel3"]), ("foreground", C["text"]),
                     ("selectBackground", C["cyan"]), ("selectForeground", "#04141a")):
        root.option_add("*TCombobox*Listbox." + opt, val)


# ----------------------------------------------------------- widget helpers
_BUTTONS = {
    "normal":  (C["panel3"], C["text"], C["line"]),
    "accent":  (C["cyan"], "#04141a", "#7df1ff"),
    "magenta": (C["magenta"], "#1a0410", "#ff7dbd"),
    "lime":    (C["lime"], "#0c1400", "#d6ff85"),
    "amber":   (C["amber"], "#1a1000", "#ffd070"),
    "danger":  ("#5a1823", "#ffd9de", C["red"]),
    "ghost":   (C["panel"], C["muted"], C["panel3"]),
    "off":     (C["panel3"], C["muted"], C["line"]),
}


def style_button(b, kind):
    bg, fg, hover = _BUTTONS[kind]
    b._colors = (bg, fg, hover)
    b.configure(bg=bg, fg=fg, activebackground=hover, activeforeground=fg)


def button(parent, text, command=None, kind="normal", width=None, font=None,
           padx=10, pady=4):
    b = tk.Button(parent, text=text, command=command, relief="flat", bd=0,
                  highlightthickness=0, cursor="hand2", font=font or FONT_UI,
                  padx=padx, pady=pady)
    if width:
        b.configure(width=width)
    style_button(b, kind)
    b.bind("<Enter>", lambda e: b.configure(bg=b._colors[2]))
    b.bind("<Leave>", lambda e: b.configure(bg=b._colors[0]))
    return b


def frame(parent, bg=None, **kw):
    return tk.Frame(parent, bg=bg or C["panel"], **kw)


def label(parent, text="", kind="normal", bg=None, **kw):
    styles = {
        "normal": (C["text"], FONT_UI), "muted": (C["muted"], FONT_SMALL),
        "title": (C["cyan"], FONT_TITLE), "mono": (C["text"], FONT_MONO),
        "head": (C["muted"], FONT_HEAD), "accent": (C["cyan"], FONT_BOLD),
        "big": (C["cyan"], FONT_MONO_BIG), "error": (C["red"], FONT_SMALL),
    }
    fg, font = styles[kind]
    return tk.Label(parent, text=text, bg=bg or C["panel"], fg=fg, font=font, **kw)


def entry(parent, textvariable=None, width=14, show=None):
    return tk.Entry(parent, textvariable=textvariable, width=width, show=show,
                    bg=C["panel3"], fg=C["text"], insertbackground=C["cyan"],
                    relief="flat", highlightthickness=1,
                    highlightbackground=C["line"], highlightcolor=C["cyan"],
                    font=FONT_MONO)


def combo(parent, values, textvariable=None, width=14, readonly=True):
    return ttk.Combobox(parent, values=values, textvariable=textvariable,
                        width=width, state="readonly" if readonly else "normal")


def separator(parent, vertical=False, bg=None):
    if vertical:
        return tk.Frame(parent, bg=C["line"], width=1)
    return tk.Frame(parent, bg=C["line"], height=1)


def context_menu(root, items, event):
    """items: list of (label, command) or None for a separator."""
    m = tk.Menu(root, tearoff=0, bg=C["panel3"], fg=C["text"], bd=0,
                activebackground=C["cyan"], activeforeground="#04141a",
                font=FONT_UI)
    for it in items:
        if it is None:
            m.add_separator()
        else:
            m.add_command(label=it[0], command=it[1])
    try:
        m.tk_popup(event.x_root, event.y_root)
    finally:
        m.grab_release()


# ------------------------------------------------------------------ dialogs
def _center(win, parent):
    win.update_idletasks()
    w, h = win.winfo_width(), win.winfo_height()
    x = parent.winfo_rootx() + (parent.winfo_width() - w) // 2
    y = parent.winfo_rooty() + (parent.winfo_height() - h) // 3
    win.geometry("+%d+%d" % (max(0, x), max(0, y)))


def _new_dialog(parent, title):
    win = tk.Toplevel(parent)
    win.title(title)
    win.configure(bg=C["panel"], padx=18, pady=16)
    win.transient(parent)
    win.resizable(False, False)
    return win


def dialog_form(parent, title, fields, ok_text="OK", message=None):
    """Modal form. fields = list of dicts with keys:
         key, label, kind ('text'|'password'|'int'|'float'|'choice'|'check'),
         default, choices, lo, hi, optional, editable
       Returns a dict {key: value} or None if cancelled."""
    win = _new_dialog(parent, title)
    result = {"value": None}
    variables = {}
    row = 0
    if message:
        label(win, message, "muted", wraplength=340, justify="left").grid(
            row=row, column=0, columnspan=2, sticky="w", pady=(0, 10))
        row += 1
    first = None
    for f in fields:
        label(win, f["label"], "normal").grid(row=row, column=0, sticky="w",
                                              padx=(0, 14), pady=4)
        kind = f.get("kind", "text")
        if kind == "check":
            var = tk.BooleanVar(value=bool(f.get("default", False)))
            w = tk.Checkbutton(win, variable=var, bg=C["panel"], activebackground=C["panel"],
                               selectcolor=C["panel3"], fg=C["text"])
        elif kind == "choice":
            var = tk.StringVar(value=str(f.get("default", f["choices"][0])))
            w = combo(win, f["choices"], var, 18, not f.get("editable", False))
        else:
            var = tk.StringVar(value="" if f.get("default") is None else str(f["default"]))
            w = entry(win, var, 20, "•" if kind == "password" else None)
        w.grid(row=row, column=1, sticky="ew", pady=4)
        variables[f["key"]] = var
        if first is None:
            first = w
        row += 1

    err = label(win, "", "error")
    err.grid(row=row, column=0, columnspan=2, sticky="w", pady=(6, 0))
    row += 1

    def submit(event=None):
        out = {}
        for f in fields:
            kind, key = f.get("kind", "text"), f["key"]
            raw = variables[key].get()
            if kind == "check":
                out[key] = bool(raw)
                continue
            raw = str(raw).strip()
            if raw == "":
                if f.get("optional"):
                    out[key] = None
                    continue
                err.configure(text="'%s' is required." % f["label"])
                return
            if kind in ("int", "float"):
                try:
                    num = float(raw)
                except ValueError:
                    err.configure(text="'%s' must be a number." % f["label"])
                    return
                lo, hi = f.get("lo"), f.get("hi")
                if (lo is not None and num < lo) or (hi is not None and num > hi):
                    err.configure(text="'%s' must be between %s and %s." % (
                        f["label"], lo, hi))
                    return
                out[key] = int(num) if kind == "int" else num
            else:
                out[key] = raw
        result["value"] = out
        win.destroy()

    bar = frame(win)
    bar.grid(row=row, column=0, columnspan=2, sticky="e", pady=(12, 0))
    button(bar, "Cancel", win.destroy, "ghost").pack(side="left", padx=6)
    button(bar, ok_text, submit, "accent").pack(side="left")
    win.bind("<Return>", submit)
    win.bind("<Escape>", lambda e: win.destroy())
    _center(win, parent)
    win.grab_set()
    if first is not None:
        first.focus_set()
    win.wait_window()
    return result["value"]


def dialog_info(parent, title, message):
    win = _new_dialog(parent, title)
    label(win, message, "normal", wraplength=380, justify="left").pack(pady=(0, 14))
    button(win, "OK", win.destroy, "accent").pack(anchor="e")
    win.bind("<Return>", lambda e: win.destroy())
    _center(win, parent)
    win.grab_set()
    win.wait_window()


def dialog_confirm(parent, title, message, ok_text="Yes", danger=False):
    win = _new_dialog(parent, title)
    result = {"ok": False}

    def yes(event=None):
        result["ok"] = True
        win.destroy()
    label(win, message, "normal", wraplength=380, justify="left").pack(pady=(0, 14))
    bar = frame(win)
    bar.pack(anchor="e")
    button(bar, "Cancel", win.destroy, "ghost").pack(side="left", padx=6)
    button(bar, ok_text, yes, "danger" if danger else "accent").pack(side="left")
    win.bind("<Return>", yes)
    win.bind("<Escape>", lambda e: win.destroy())
    _center(win, parent)
    win.grab_set()
    win.wait_window()
    return result["ok"]


def dialog_choice(parent, title, message, options):
    """Pick one item from a list. Returns the chosen index or None."""
    if not options:
        return None
    res = dialog_form(parent, title, [
        {"key": "pick", "label": "Choose", "kind": "choice",
         "choices": options, "default": options[0]}], message=message)
    if res is None:
        return None
    return options.index(res["pick"])


# --------------------------------------------------------- background tasks
def run_task(root, message, work, done):
    """Run work() in a thread behind a modal 'busy' box so the window never
    freezes. done(result, error) is called on the main thread afterwards."""
    box = {"result": None, "error": None, "finished": False}

    def runner():
        try:
            box["result"] = work()
        except Exception as e:             # report any failure to the caller
            box["error"] = e
        box["finished"] = True

    win = tk.Toplevel(root)
    win.title("Working")
    win.configure(bg=C["panel"], padx=26, pady=20)
    win.transient(root)
    win.resizable(False, False)
    win.protocol("WM_DELETE_WINDOW", lambda: None)
    spin = label(win, "◐  " + message + " ...", "accent")
    spin.pack()
    label(win, "Pure-Python audio processing - long files take a moment.",
          "muted").pack(pady=(6, 0))
    _center(win, root)
    win.grab_set()

    frames = ["◐", "◓", "◑", "◒"]
    tick = {"n": 0}
    threading.Thread(target=runner, daemon=True).start()

    def poll():
        if box["finished"]:
            win.destroy()
            done(box["result"], box["error"])
            return
        tick["n"] += 1
        spin.configure(text="%s  %s ..." % (frames[tick["n"] % 4], message))
        root.after(120, poll)
    poll()
