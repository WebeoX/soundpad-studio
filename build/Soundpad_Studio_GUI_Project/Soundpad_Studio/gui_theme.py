"""
gui_theme.py - Dark neon theme, small widget "factory" functions and dialogs.
Procedural: every widget is made by a plain function, no classes anywhere.
"""
import math
import tkinter as tk
from tkinter import ttk

# ----------------------------------------------------------------- palette
BG = "#080a0f"
PANEL = "#0f1218"
PANEL2 = "#161a23"
PANEL3 = "#1d2230"
EDGE = "#272d3d"
TEXT = "#dfe3ee"
DIM = "#6d768c"
CYAN = "#00e5ff"
MAGENTA = "#ff2e97"
LIME = "#b6ff3b"
AMBER = "#ffb020"
RED = "#ff4560"
VIOLET = "#9b6bff"
DARK_TEXT = "#001419"
TRACK_COLORS = [CYAN, MAGENTA, LIME, AMBER, VIOLET, "#2ee6a6", "#ff7a45", "#4d9bff"]

FONT = ("Segoe UI", 10)
FONT_B = ("Segoe UI Semibold", 10)
FONT_H = ("Segoe UI Semibold", 13)
FONT_BIG = ("Segoe UI Semibold", 24)
FONT_S = ("Segoe UI", 8)
FONT_MONO = ("Consolas", 10)
FONT_MONO_L = ("Consolas", 17)

_root = [None]
_wheel = {}


def _rgb(color):
    return int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)


def blend(c1, c2, t):
    """Mix two #rrggbb colours: t=0 gives c1, t=1 gives c2."""
    t = max(0.0, min(1.0, t))
    a, b = _rgb(c1), _rgb(c2)
    return "#%02x%02x%02x" % tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def track_color(index):
    return TRACK_COLORS[index % len(TRACK_COLORS)]


def to_db(value):
    return 20 * math.log10(value) if value > 0 else -120.0


def fmt_time(seconds):
    seconds = max(0.0, seconds)
    return "%02d:%05.2f" % (int(seconds // 60), seconds % 60)


# ------------------------------------------------------------------- setup
def setup_style(root):
    """Apply the dark theme to ttk widgets and remember the root window."""
    _root[0] = root
    root.configure(bg=BG)
    st = ttk.Style(root)
    st.theme_use("clam")
    st.configure("TCombobox", fieldbackground=PANEL2, background=PANEL3,
                 foreground=TEXT, arrowcolor=CYAN, bordercolor=EDGE,
                 lightcolor=PANEL2, darkcolor=PANEL2, selectbackground=PANEL2,
                 selectforeground=TEXT, padding=4)
    st.map("TCombobox", fieldbackground=[("readonly", PANEL2)],
           foreground=[("readonly", TEXT)], background=[("active", EDGE)],
           bordercolor=[("focus", CYAN)])
    root.option_add("*TCombobox*Listbox.background", PANEL2)
    root.option_add("*TCombobox*Listbox.foreground", TEXT)
    root.option_add("*TCombobox*Listbox.selectBackground", CYAN)
    root.option_add("*TCombobox*Listbox.selectForeground", DARK_TEXT)
    root.option_add("*TCombobox*Listbox.font", FONT)
    for orient in ("Vertical", "Horizontal"):
        st.configure(orient + ".TScrollbar", background=PANEL3, troughcolor=BG,
                     bordercolor=BG, arrowcolor=DIM, lightcolor=PANEL3,
                     darkcolor=PANEL3, relief="flat")
        st.map(orient + ".TScrollbar", background=[("active", EDGE)])
    st.configure("Dark.Treeview", background=PANEL, fieldbackground=PANEL,
                 foreground=TEXT, rowheight=28, borderwidth=0, font=FONT)
    st.map("Dark.Treeview", background=[("selected", "#12323a")],
           foreground=[("selected", CYAN)])
    st.configure("Dark.Treeview.Heading", background=PANEL2, foreground=DIM,
                 relief="flat", font=FONT_B, borderwidth=0)
    st.map("Dark.Treeview.Heading", background=[("active", PANEL3)])


def install_wheel(root):
    """One global mouse-wheel handler. Widgets register a function with
    on_wheel(); the handler finds the widget under the pointer and calls it."""
    def handler(event):
        try:
            w = root.winfo_containing(event.x_root, event.y_root)
        except (tk.TclError, KeyError):
            return None
        while w is not None:
            fn = _wheel.get(str(w))
            if fn:
                fn(event)
                return "break"
            w = w.master
        return None
    root.bind_all("<MouseWheel>", handler)


def on_wheel(widget, fn):
    _wheel[str(widget)] = fn


# ------------------------------------------------------- widget factories
def panel(parent, bg=PANEL, **kw):
    return tk.Frame(parent, bg=bg, **kw)


def label(parent, text="", fg=TEXT, font=FONT, bg=None, **kw):
    return tk.Label(parent, text=text, fg=fg, bg=bg or parent["bg"], font=font, **kw)


def title(parent, text, bg=None):
    """Small spaced-out section heading."""
    return tk.Label(parent, text=text.upper(), fg=DIM, bg=bg or parent["bg"],
                    font=("Segoe UI Semibold", 8), anchor="w")


def divider(parent, vertical=False):
    if vertical:
        return tk.Frame(parent, bg=EDGE, width=1)
    return tk.Frame(parent, bg=EDGE, height=1)


_BUTTONS = {
    "normal": (PANEL2, TEXT, PANEL3),
    "accent": (CYAN, DARK_TEXT, "#6df1ff"),
    "magenta": (MAGENTA, "#1a0010", "#ff7ab9"),
    "lime": (LIME, "#0d1400", "#d3ff7a"),
    "danger": (RED, "#1a0006", "#ff8a9b"),
    "ghost": (None, DIM, PANEL2),
}


def button(parent, text, command, kind="normal", width=None, font=FONT_B,
           padx=12, pady=5):
    bg, fg, hover = _BUTTONS[kind]
    bg = bg or parent["bg"]
    b = tk.Button(parent, text=text, command=command, bg=bg, fg=fg,
                  activebackground=hover, activeforeground=fg, relief="flat",
                  bd=0, highlightthickness=0, font=font, padx=padx, pady=pady,
                  cursor="hand2", width=width)
    b.bind("<Enter>", lambda e: b.configure(bg=hover))
    b.bind("<Leave>", lambda e: b.configure(bg=bg))
    return b


def toggle(parent, text, command, color=CYAN, initial=False, width=3):
    """Latching button (used for Mute / Solo / Loop). Returns (button, setter)."""
    state = {"on": initial}
    b = tk.Button(parent, text=text, relief="flat", bd=0, highlightthickness=0,
                  font=FONT_B, width=width, cursor="hand2", pady=3)

    def paint():
        if state["on"]:
            b.configure(bg=color, fg=DARK_TEXT, activebackground=color)
        else:
            b.configure(bg=PANEL3, fg=DIM, activebackground=EDGE)

    def clicked():
        state["on"] = not state["on"]
        paint()
        if command:
            command(state["on"])

    def setter(value):
        state["on"] = bool(value)
        paint()

    b.configure(command=clicked)
    paint()
    return b, setter


def entry(parent, var=None, width=12, show=None):
    return tk.Entry(parent, textvariable=var, width=width, show=show,
                    bg=PANEL2, fg=TEXT, insertbackground=CYAN, relief="flat",
                    bd=6, highlightthickness=1, highlightbackground=EDGE,
                    highlightcolor=CYAN, font=FONT)


def combo(parent, values, var=None, width=12, command=None):
    cb = ttk.Combobox(parent, values=list(values), textvariable=var,
                      state="readonly", width=width, font=FONT)
    if command:
        cb.bind("<<ComboboxSelected>>", lambda e: command())
    return cb


def spin(parent, from_, to, var, width=4, command=None):
    return tk.Spinbox(parent, from_=from_, to=to, textvariable=var, width=width,
                      command=command, bg=PANEL2, fg=TEXT, insertbackground=CYAN,
                      buttonbackground=PANEL3, relief="flat", bd=0,
                      highlightthickness=1, highlightbackground=EDGE,
                      highlightcolor=CYAN, font=FONT)


def check(parent, text, var, command=None, bg=None):
    bg = bg or parent["bg"]
    return tk.Checkbutton(parent, text=text, variable=var, command=command,
                          bg=bg, fg=TEXT, activebackground=bg,
                          activeforeground=CYAN, selectcolor=PANEL2,
                          highlightthickness=0, bd=0, font=FONT, cursor="hand2")


def slider(parent, from_, to, resolution=0.01, value=None, command=None,
           orient="horizontal", length=140, release=None, bg=None):
    s = tk.Scale(parent, from_=from_, to=to, resolution=resolution, orient=orient,
                 length=length, showvalue=0, bg=bg or PANEL, fg=TEXT,
                 troughcolor=PANEL3, activebackground=CYAN, highlightthickness=0,
                 bd=0, sliderrelief="flat", sliderlength=16,
                 width=12 if orient == "horizontal" else 14, font=FONT_S)
    if value is not None:
        s.set(value)
    if command:
        s.configure(command=command)
    if release:
        s.bind("<ButtonRelease-1>", lambda e: release())
    return s


def listbox(parent, height=8, width=24):
    return tk.Listbox(parent, height=height, width=width, bg=PANEL2, fg=TEXT,
                      selectbackground=CYAN, selectforeground=DARK_TEXT,
                      highlightthickness=0, bd=0, activestyle="none",
                      font=FONT, exportselection=False)


def dark_menu():
    return tk.Menu(_root[0], tearoff=0, bg=PANEL2, fg=TEXT, activebackground=CYAN,
                   activeforeground=DARK_TEXT, bd=0, relief="flat", font=FONT)


def popup(menu, event):
    try:
        menu.tk_popup(event.x_root, event.y_root)
    finally:
        menu.grab_release()


def scrollable(parent, bg=BG):
    """A vertically scrollable area. Returns (outer_frame, inner_frame)."""
    outer = tk.Frame(parent, bg=bg)
    canvas = tk.Canvas(outer, bg=bg, highlightthickness=0, bd=0)
    sb = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=sb.set)
    sb.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)
    inner = tk.Frame(canvas, bg=bg)
    win = canvas.create_window((0, 0), window=inner, anchor="nw")
    inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win, width=e.width))
    on_wheel(outer, lambda e: canvas.yview_scroll(int(-e.delta / 120) or (-1 if e.delta > 0 else 1), "units"))
    return outer, inner


# ----------------------------------------------------------------- dialogs
def _make_dialog(title_text):
    top = tk.Toplevel(_root[0])
    top.title(title_text)
    top.configure(bg=PANEL)
    top.transient(_root[0])
    top.resizable(False, False)
    return top


def _show_dialog(top):
    root = _root[0]
    top.update_idletasks()
    x = root.winfo_rootx() + (root.winfo_width() - top.winfo_reqwidth()) // 2
    y = root.winfo_rooty() + (root.winfo_height() - top.winfo_reqheight()) // 3
    top.geometry("+%d+%d" % (max(0, x), max(0, y)))
    try:
        top.wait_visibility()
        top.grab_set()
    except tk.TclError:
        pass
    top.focus_force()


def show_message(title_text, text, kind="info"):
    color = {"info": CYAN, "warn": AMBER, "error": RED}.get(kind, CYAN)
    top = _make_dialog(title_text)
    body = tk.Frame(top, bg=PANEL, padx=24, pady=20)
    body.pack()
    tk.Frame(body, bg=color, height=3).pack(fill="x", pady=(0, 12))
    label(body, title_text, color, FONT_H, bg=PANEL).pack(anchor="w")
    label(body, text, TEXT, FONT, bg=PANEL, wraplength=460, justify="left").pack(
        anchor="w", pady=(8, 16))
    button(body, "OK", top.destroy, "accent", padx=26).pack(anchor="e")
    top.bind("<Return>", lambda e: top.destroy())
    top.bind("<Escape>", lambda e: top.destroy())
    _show_dialog(top)
    top.wait_window()


def confirm(title_text, text, yes="Yes", danger=False):
    result = {"v": False}
    top = _make_dialog(title_text)
    body = tk.Frame(top, bg=PANEL, padx=24, pady=20)
    body.pack()
    color = RED if danger else CYAN
    tk.Frame(body, bg=color, height=3).pack(fill="x", pady=(0, 12))
    label(body, title_text, color, FONT_H, bg=PANEL).pack(anchor="w")
    label(body, text, TEXT, FONT, bg=PANEL, wraplength=440, justify="left").pack(
        anchor="w", pady=(8, 16))
    row = tk.Frame(body, bg=PANEL)
    row.pack(anchor="e")

    def yes_():
        result["v"] = True
        top.destroy()
    button(row, "Cancel", top.destroy, "normal").pack(side="left", padx=6)
    button(row, yes, yes_, "danger" if danger else "accent").pack(side="left")
    top.bind("<Escape>", lambda e: top.destroy())
    _show_dialog(top)
    top.wait_window()
    return result["v"]


def form(title_text, fields, ok="OK", intro=None):
    """Modal form. fields = list of dicts:
         key, label, default, kind = text|int|float|password|choice|check,
         choices (for choice), min, max, optional.
    Returns a dict of values, or None if cancelled."""
    top = _make_dialog(title_text)
    body = tk.Frame(top, bg=PANEL, padx=24, pady=20)
    body.pack()
    label(body, title_text, CYAN, FONT_H, bg=PANEL).grid(row=0, column=0, columnspan=2, sticky="w")
    row = 1
    if intro:
        label(body, intro, DIM, FONT, bg=PANEL, wraplength=380, justify="left").grid(
            row=row, column=0, columnspan=2, sticky="w", pady=(4, 8))
        row += 1
    vars_ = {}
    first = None
    for f in fields:
        label(body, f["label"], DIM, FONT, bg=PANEL).grid(row=row, column=0, sticky="w",
                                                            pady=5, padx=(0, 16))
        kind = f.get("kind", "text")
        if kind == "choice":
            default = f.get("default")
            if default not in f["choices"]:
                default = f["choices"][0]
            var = tk.StringVar(value=str(default))
            widget = combo(body, f["choices"], var, width=f.get("width", 24))
        elif kind == "check":
            var = tk.BooleanVar(value=bool(f.get("default", False)))
            widget = check(body, "", var, bg=PANEL)
        else:
            default = f.get("default")
            var = tk.StringVar(value="" if default is None else str(default))
            widget = entry(body, var, width=f.get("width", 26),
                           show="\u2022" if kind == "password" else None)
        widget.grid(row=row, column=1, sticky="we", pady=5)
        vars_[f["key"]] = (var, f)
        if first is None:
            first = widget
        row += 1
    msg = label(body, "", RED, FONT, bg=PANEL, wraplength=380, justify="left")
    msg.grid(row=row, column=0, columnspan=2, sticky="w", pady=(4, 0))
    row += 1
    result = {"v": None}

    def parse():
        out = {}
        for key, (var, f) in vars_.items():
            kind = f.get("kind", "text")
            raw = var.get()
            if kind in ("int", "float"):
                if str(raw).strip() == "":
                    if f.get("optional"):
                        out[key] = None
                        continue
                    msg.configure(text="'%s' is required." % f["label"])
                    return None
                try:
                    val = float(raw)
                except ValueError:
                    msg.configure(text="'%s' must be a number." % f["label"])
                    return None
                lo, hi = f.get("min"), f.get("max")
                if (lo is not None and val < lo) or (hi is not None and val > hi):
                    msg.configure(text="'%s' must be between %s and %s." % (f["label"], lo, hi))
                    return None
                out[key] = int(val) if kind == "int" else val
            elif kind == "check":
                out[key] = bool(raw)
            else:
                text = str(raw).strip()
                if not text and not f.get("optional"):
                    msg.configure(text="'%s' is required." % f["label"])
                    return None
                out[key] = text
        return out

    def on_ok(event=None):
        values = parse()
        if values is not None:
            result["v"] = values
            top.destroy()

    row_btn = tk.Frame(body, bg=PANEL)
    row_btn.grid(row=row, column=0, columnspan=2, sticky="e", pady=(14, 0))
    button(row_btn, "Cancel", top.destroy, "normal").pack(side="left", padx=6)
    button(row_btn, ok, on_ok, "accent", padx=20).pack(side="left")
    top.bind("<Return>", on_ok)
    top.bind("<Escape>", lambda e: top.destroy())
    _show_dialog(top)
    if first is not None:
        first.focus_set()
    top.wait_window()
    return result["v"]


def choose(title_text, prompt, labels, default=0):
    """Pick one item from a list. Returns its index, or None."""
    if not labels:
        return None
    res = form(title_text, [{"key": "pick", "label": prompt, "kind": "choice",
                             "choices": list(labels), "default": labels[default]}])
    if res is None:
        return None
    return list(labels).index(res["pick"])


# ------------------------------------------------------------ busy overlay
def busy_start(text="Working..."):
    root = _root[0]
    top = tk.Toplevel(root)
    top.overrideredirect(True)
    top.configure(bg=CYAN)
    inner = tk.Frame(top, bg=PANEL, padx=30, pady=20)
    inner.pack(padx=1, pady=1)
    label(inner, text, TEXT, FONT_B, bg=PANEL).pack()
    bar = tk.Canvas(inner, width=300, height=6, bg=PANEL3, highlightthickness=0)
    bar.pack(pady=(14, 0))
    box = {"top": top, "bar": bar, "x": 0, "job": None, "alive": True}
    top.update_idletasks()
    x = root.winfo_rootx() + (root.winfo_width() - top.winfo_reqwidth()) // 2
    y = root.winfo_rooty() + (root.winfo_height() - top.winfo_reqheight()) // 2
    top.geometry("+%d+%d" % (max(0, x), max(0, y)))

    def tick():
        if not box["alive"]:
            return
        bar.delete("all")
        x0 = box["x"]
        bar.create_rectangle(x0 - 80, 0, x0, 6, fill=CYAN, outline="")
        box["x"] = (x0 + 10) % 380
        box["job"] = root.after(28, tick)

    try:
        top.wait_visibility()
        top.grab_set()
    except tk.TclError:
        pass
    tick()
    top.update()
    return box


def busy_stop(box):
    box["alive"] = False
    if box["job"] is not None:
        try:
            _root[0].after_cancel(box["job"])
        except tk.TclError:
            pass
    try:
        box["top"].grab_release()
    except tk.TclError:
        pass
    box["top"].destroy()
