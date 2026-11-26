"""
gui_stats.py - Insights dashboard. Every number and bar on this screen comes
from a live SQL query (JOIN, GROUP BY, HAVING, aggregates). Tick "Show SQL"
to see the query behind each chart.
"""
import tkinter as tk

import gui_theme as T
from gui_state import S, uid
import gui_data

_X = {"inner": None, "sql_var": None}


def build(parent):
    f = tk.Frame(parent, bg=T.BG)
    head = tk.Frame(f, bg=T.BG)
    head.pack(fill="x", padx=28, pady=(24, 4))
    T.label(head, "Insights", T.TEXT, T.FONT_BIG, bg=T.BG).pack(side="left")
    T.button(head, "Refresh", refresh, "normal").pack(side="right")
    _X["sql_var"] = tk.BooleanVar(value=False)
    T.check(head, "Show SQL", _X["sql_var"], refresh, bg=T.BG).pack(side="right", padx=16)
    T.label(f, "Live statistics about your studio, computed by MySQL queries.", T.DIM, T.FONT,
            bg=T.BG).pack(anchor="w", padx=30)
    outer, inner = T.scrollable(f, bg=T.BG)
    outer.pack(fill="both", expand=True, padx=20, pady=10)
    _X["inner"] = inner
    return f


def show():
    S["play_fn"] = None
    S["on_playhead"] = None
    refresh()


def _tile(parent, col, name, value, unit, color):
    t = tk.Frame(parent, bg=T.PANEL, padx=16, pady=12, highlightthickness=1, highlightbackground=T.EDGE)
    t.grid(row=0, column=col, padx=6, pady=6, sticky="nsew")
    text = ("%.1f" % value) if unit == "min" else "%d" % value
    T.label(t, text, color, ("Segoe UI Semibold", 22), bg=T.PANEL).pack(anchor="w")
    T.label(t, name + ((" (%s)" % unit) if unit else ""), T.DIM, T.FONT_S, bg=T.PANEL).pack(anchor="w")


def _bars(canvas, rows, color):
    canvas.delete("all")
    w = max(canvas.winfo_width(), 420)
    if not rows:
        canvas.create_text(12, 20, text="No data yet", fill=T.DIM, font=T.FONT, anchor="w")
        return
    top = max(v for _l, v in rows) or 1.0
    for i, (label, value) in enumerate(rows):
        y = 8 + i * 28
        canvas.create_text(8, y + 10, text=label[:22], fill=T.TEXT, font=T.FONT, anchor="w")
        x0, x1 = 170, w - 70
        canvas.create_rectangle(x0, y + 3, x1, y + 17, fill=T.PANEL3, outline="")
        canvas.create_rectangle(x0, y + 3, x0 + max(3, (x1 - x0) * value / top), y + 17, fill=color, outline="")
        canvas.create_text(w - 10, y + 10, text=("%d" % value if value == int(value) else "%.1f" % value),
                           fill=color, font=T.FONT_B, anchor="e")


def refresh():
    inner = _X["inner"]
    for w in inner.winfo_children():
        w.destroy()
    user = uid()
    tiles = tk.Frame(inner, bg=T.BG)
    tiles.pack(fill="x")
    for i, (name, sql, unit) in enumerate(gui_data.TILES):
        _tile(tiles, i, name, gui_data.tile_value(sql, user), unit, T.track_color(i))
        tiles.grid_columnconfigure(i, weight=1)
    grid = tk.Frame(inner, bg=T.BG)
    grid.pack(fill="x", pady=6)
    for i, (title, sql, color) in enumerate(gui_data.PANELS):
        card = tk.Frame(grid, bg=T.PANEL, padx=16, pady=12, highlightthickness=1, highlightbackground=T.EDGE)
        card.grid(row=i // 2, column=i % 2, padx=6, pady=6, sticky="nsew")
        grid.grid_columnconfigure(i % 2, weight=1, uniform="cols")
        T.label(card, title, color, T.FONT_B, bg=T.PANEL).pack(anchor="w", pady=(0, 6))
        rows = gui_data.panel_rows(sql, user)
        canvas = tk.Canvas(card, bg=T.PANEL, height=max(36, 8 + 28 * max(1, len(rows))), highlightthickness=0)
        canvas.pack(fill="x")
        canvas.bind("<Configure>", lambda e, c=canvas, r=rows, col=color: _bars(c, r, col))
        if _X["sql_var"].get():
            T.label(card, sql, T.DIM, ("Consolas", 8), bg=T.PANEL, justify="left").pack(anchor="w", pady=(8, 0))
