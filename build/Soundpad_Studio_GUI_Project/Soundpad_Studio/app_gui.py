"""
app_gui.py — Soundpad Studio desktop interface.
Built with Tkinter using procedural functions only (no custom classes).
Run: python main.py
"""
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

import mysql.connector
import db
from auth import login_user, register_user
from projects import (list_projects, create_project, get_project, delete_project,
                      rename_project, add_track, list_tracks, delete_track,
                      set_bpm, add_clip)
from audio_io import import_audio_file, list_user_files, remove_audio_file
from render import render_project, EXPORT_DIR
from audio_io import save_wav

# ── visual system ─────────────────────────────────────────────────────────
COL = {
    "bg": "#090b12", "panel": "#111522", "panel2": "#171d2c",
    "line": "#273149", "text": "#edf2ff", "muted": "#8994ad",
    "cyan": "#62e6df", "purple": "#a78bfa", "orange": "#ffb86b",
    "red": "#ff7185", "green": "#91e6ad"
}
FONT = ("Segoe UI", 10)
FONT_B = ("Segoe UI Semibold", 10)
FONT_H = ("Segoe UI Semibold", 23)
FONT_MONO = ("Consolas", 10)

STATE = {"root": None, "user": None, "project": None, "content": None,
         "status": None, "page": "login"}

def safe_call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except mysql.connector.Error as exc:
        messagebox.showerror("Database connection", 
            "Could not complete this action.\n\n"
            "Check that MySQL is running, the database is set up, and db.py "
            "contains the correct connection details.\n\n" + str(exc))
    except (ValueError, OSError) as exc:
        messagebox.showerror("Unable to complete", str(exc))
    except Exception as exc:
        messagebox.showerror("Something went wrong", str(exc))
    return None

def set_status(text):
    if STATE["status"] is not None:
        STATE["status"].set(text)

def clear_content():
    if STATE["content"] is not None:
        STATE["content"].destroy()
    STATE["content"] = tk.Frame(STATE["root"], bg=COL["bg"])
    STATE["content"].pack(fill="both", expand=True)

def label(parent, text, size=10, color=None, bold=False, **kw):
    return tk.Label(parent, text=text, bg=kw.pop("bg", COL["bg"]),
                    fg=color or COL["text"],
                    font=("Segoe UI Semibold" if bold else "Segoe UI", size),
                    **kw)

def button(parent, text, command, accent=False, **kw):
    bg = COL["cyan"] if accent else COL["panel2"]
    fg = "#071316" if accent else COL["text"]
    b = tk.Button(parent, text=text, command=command, bg=bg, fg=fg,
                  activebackground=COL["purple"], activeforeground="#ffffff",
                  relief="flat", bd=0, padx=15, pady=9, cursor="hand2",
                  font=FONT_B, **kw)
    b.bind("<Enter>", lambda e: b.configure(bg=COL["purple"] if not accent else "#8af0e9"))
    b.bind("<Leave>", lambda e: b.configure(bg=bg))
    return b

def panel(parent, **kw):
    return tk.Frame(parent, bg=COL["panel"], highlightthickness=1,
                    highlightbackground=COL["line"], **kw)

def heading(parent, eyebrow, title, subtitle=""):
    label(parent, eyebrow.upper(), 9, COL["cyan"], True).pack(anchor="w", pady=(0, 5))
    label(parent, title, 24, COL["text"], True).pack(anchor="w")
    if subtitle:
        label(parent, subtitle, 10, COL["muted"]).pack(anchor="w", pady=(4, 0))

def entry(parent, variable=None, show=None, width=30):
    e = tk.Entry(parent, textvariable=variable, show=show, width=width,
                 bg=COL["panel2"], fg=COL["text"], insertbackground=COL["cyan"],
                 relief="flat", highlightthickness=1, highlightbackground=COL["line"],
                 highlightcolor=COL["cyan"], font=FONT)
    e.pack(fill="x", ipady=9, pady=(5, 13))
    return e

def show_login():
    STATE["page"] = "login"
    STATE["user"] = None
    STATE["project"] = None
    clear_content()
    root, f = STATE["root"], STATE["content"]
    f.configure(padx=30, pady=30)
    center = tk.Frame(f, bg=COL["bg"])
    center.place(relx=.5, rely=.5, anchor="center", width=440)
    label(center, "S / S", 13, COL["cyan"], True).pack(anchor="center", pady=(0, 12))
    label(center, "SOUNDPAD", 30, COL["text"], True).pack()
    label(center, "STUDIO  /  AUDIO WORKSPACE", 9, COL["muted"], True).pack(pady=(2, 26))
    card = panel(center, padx=30, pady=28)
    card.pack(fill="x")
    heading(card, "Welcome back", "Sign in", "Your ideas, arranged into sound.")
    u, p = tk.StringVar(), tk.StringVar()
    label(card, "USERNAME", 9, COL["muted"], True).pack(anchor="w", pady=(22, 0))
    ue = entry(card, u)
    label(card, "PASSWORD", 9, COL["muted"], True).pack(anchor="w")
    pe = entry(card, p, show="•")
    msg = label(card, "", 9, COL["red"], wraplength=330, justify="left")
    msg.pack(anchor="w", pady=(0, 8))

    def do_login(event=None):
        if not u.get().strip() or not p.get():
            msg.configure(text="Enter both your username and password.")
            return
        user = safe_call(login_user, u.get(), p.get())
        if user:
            STATE["user"] = user
            set_status("Signed in as " + user["username"])
            show_dashboard()
        elif user is None:
            msg.configure(text="Login failed. Check your details or database connection.")
    def do_register():
        username, password = u.get().strip(), p.get()
        if not username or not password:
            msg.configure(text="Enter a username and password to create an account.")
            return
        result = safe_call(register_user, username, password)
        if result:
            ok, text = result
            msg.configure(text=text, fg=COL["green"] if ok else COL["red"])
            if ok:
                msg.configure(text="Account created. You can sign in now.", fg=COL["green"])
                p.set("")
    button(card, "SIGN IN  →", do_login, True).pack(fill="x", pady=(4, 10))
    button(card, "CREATE AN ACCOUNT", do_register).pack(fill="x")
    pe.bind("<Return>", do_login)
    ue.bind("<Return>", lambda e: pe.focus_set())
    label(center, "A procedural Python audio workstation", 9, COL["muted"]).pack(pady=18)
    ue.focus_set()

def app_shell(active="projects"):
    clear_content()
    f = STATE["content"]
    top = tk.Frame(f, bg=COL["bg"])
    top.pack(fill="x", padx=30, pady=(22, 18))
    brand = tk.Frame(top, bg=COL["bg"])
    brand.pack(side="left")
    label(brand, "S / S", 14, COL["cyan"], True).pack(side="left")
    label(brand, "  SOUNDPAD STUDIO", 12, COL["text"], True).pack(side="left")
    nav = tk.Frame(top, bg=COL["bg"])
    nav.pack(side="right")
    for name, title, fn in [("projects", "PROJECTS", show_dashboard),
                            ("library", "LIBRARY", show_library)]:
        button(nav, title, fn, active == name).pack(side="left", padx=4)
    button(nav, "LOG OUT", show_login).pack(side="left", padx=(12, 0))
    tk.Frame(f, bg=COL["line"], height=1).pack(fill="x", padx=30)
    body = tk.Frame(f, bg=COL["bg"])
    body.pack(fill="both", expand=True, padx=30, pady=24)
    STATE["body"] = body
    return body

def show_dashboard():
    STATE["page"] = "projects"
    body = app_shell("projects")
    header = tk.Frame(body, bg=COL["bg"])
    header.pack(fill="x", pady=(0, 20))
    left = tk.Frame(header, bg=COL["bg"])
    left.pack(side="left")
    heading(left, "Your workspace", "Projects", "Create a session, build tracks and export your mix.")
    button(header, "+  NEW PROJECT", new_project, True).pack(side="right", pady=14)
    rows = safe_call(list_projects, STATE["user"]["user_id"])
    if rows is None: rows = []
    if not rows:
        box = panel(body, padx=25, pady=30)
        box.pack(fill="x", pady=10)
        label(box, "✳", 25, COL["cyan"], True).pack(anchor="w")
        label(box, "Nothing in the timeline yet.", 16, COL["text"], True).pack(anchor="w", pady=(8, 4))
        label(box, "Start with a new project. Your sessions will appear here.", 10, COL["muted"]).pack(anchor="w")
        return
    grid = tk.Frame(body, bg=COL["bg"])
    grid.pack(fill="both", expand=True)
    for i, proj in enumerate(rows):
        card = panel(grid, padx=20, pady=18)
        card.grid(row=i//2, column=i%2, sticky="nsew", padx=(0, 12), pady=(0, 12))
        grid.grid_columnconfigure(i%2, weight=1)
        label(card, "SESSION  /  %04d" % proj["project_id"], 9, COL["cyan"], True).pack(anchor="w")
        label(card, proj["name"], 17, COL["text"], True).pack(anchor="w", pady=(10, 3))
        label(card, "%s BPM     ·     %s Hz" % (proj["bpm"], proj["sample_rate"]), 10, COL["muted"]).pack(anchor="w")
        row = tk.Frame(card, bg=COL["panel"])
        row.pack(fill="x", pady=(17, 0))
        button(row, "OPEN SESSION  →", lambda p=proj: open_project(p), True).pack(side="left")
        button(row, "RENAME", lambda p=proj: rename_one(p)).pack(side="left", padx=6)
        button(row, "DELETE", lambda p=proj: delete_one(p)).pack(side="right")
    for i in range((len(rows)+1)//2):
        grid.grid_rowconfigure(i, weight=1)

def new_project():
    name = simpledialog.askstring("New project", "Project name:", parent=STATE["root"])
    if not name: return
    bpm = simpledialog.askinteger("Tempo", "Tempo (20–300 BPM):", initialvalue=120,
                                  minvalue=20, maxvalue=300, parent=STATE["root"])
    if bpm is None: return
    result = safe_call(create_project, STATE["user"]["user_id"], name, bpm)
    if result:
        pid, msg = result
        set_status(msg)
        show_dashboard()

def rename_one(proj):
    name = simpledialog.askstring("Rename project", "New project name:",
                                  initialvalue=proj["name"], parent=STATE["root"])
    if name:
        result = safe_call(rename_project, proj["project_id"], STATE["user"]["user_id"], name)
        if result: set_status(result[1]); show_dashboard()

def delete_one(proj):
    if messagebox.askyesno("Delete project", "Delete '%s' and all its tracks?" % proj["name"]):
        result = safe_call(delete_project, proj["project_id"], STATE["user"]["user_id"])
        if result: set_status(result[1]); show_dashboard()

def open_project(proj):
    STATE["project"] = proj["project_id"]
    show_project()

def show_project():
    STATE["page"] = "project"
    body = app_shell("projects")
    proj = safe_call(get_project, STATE["project"], STATE["user"]["user_id"])
    if not proj:
        show_dashboard()
        return
    head = tk.Frame(body, bg=COL["bg"])
    head.pack(fill="x", pady=(0, 18))
    heading(head, "SESSION  /  %04d" % proj["project_id"], proj["name"],
            "Arrange tracks and audio clips in one place.")
    controls = tk.Frame(body, bg=COL["bg"])
    controls.pack(fill="x", pady=(0, 18))
    label(controls, "TEMPO", 9, COL["muted"], True).pack(side="left")
    bpm_var = tk.StringVar(value=str(proj["bpm"]))
    bpm_box = tk.Spinbox(controls, from_=20, to=300, width=6, textvariable=bpm_var,
                         bg=COL["panel2"], fg=COL["text"], buttonbackground=COL["panel2"],
                         relief="flat", font=FONT)
    bpm_box.pack(side="left", padx=8, ipady=5)
    def save_bpm():
        try: val = int(bpm_var.get())
        except ValueError:
            messagebox.showwarning("Tempo", "Enter a whole number from 20 to 300."); return
        result = safe_call(set_bpm, proj["project_id"], STATE["user"]["user_id"], val)
        if result: set_status(result[1]); show_project()
    button(controls, "SAVE TEMPO", save_bpm).pack(side="left")
    button(controls, "+ ADD TRACK", add_track_dialog, True).pack(side="right")
    tracks = safe_call(list_tracks, proj["project_id"]) or []
    if not tracks:
        empty = panel(body, padx=24, pady=28); empty.pack(fill="x")
        label(empty, "No tracks yet", 16, COL["text"], True).pack(anchor="w")
        label(empty, "Add an audio, beat or instrument track to begin.", 10, COL["muted"]).pack(anchor="w", pady=(5, 0))
    for index, track in enumerate(tracks):
        card = panel(body, padx=18, pady=15)
        card.pack(fill="x", pady=6)
        stripe = tk.Frame(card, bg=[COL["cyan"], COL["purple"], COL["orange"]][index%3], width=3)
        stripe.pack(side="left", fill="y", padx=(0, 14))
        main = tk.Frame(card, bg=COL["panel"])
        main.pack(side="left", fill="x", expand=True)
        label(main, track["track_name"], 13, COL["text"], True).pack(anchor="w")
        label(main, "%s TRACK   ·   VOL %.2f   ·   PAN %+.2f" %
              (track["track_type"].upper(), float(track["volume"]), float(track["pan"])),
              9, COL["muted"], True).pack(anchor="w", pady=(4, 0))
        if track["track_type"] == "audio":
            clips = safe_call(__import__("projects").list_clips, track["track_id"]) or []
            for clip in clips:
                label(main, "  ◦  %s  ·  starts at %.2fs" %
                      (clip["file_name"], float(clip["start_time"])), 9, COL["cyan"]).pack(anchor="w", pady=(4, 0))
            button(card, "ADD CLIP", lambda t=track: add_clip_dialog(t)).pack(side="right", padx=5)
        button(card, "REMOVE", lambda t=track: remove_track(t)).pack(side="right", padx=5)
    foot = tk.Frame(body, bg=COL["bg"])
    foot.pack(fill="x", pady=(18, 0))
    button(foot, "← BACK TO PROJECTS", show_dashboard).pack(side="left")
    button(foot, "EXPORT WAV  ↓", export_current, True).pack(side="right")

def add_track_dialog():
    name = simpledialog.askstring("Add track", "Track name:", initialvalue="New track", parent=STATE["root"])
    if name is None: return
    kind = simpledialog.askstring("Track type", "Type: audio, beat, or instrument",
                                  initialvalue="audio", parent=STATE["root"])
    if not kind: return
    kind = kind.strip().lower()
    if kind not in ("audio", "beat", "instrument"):
        messagebox.showwarning("Track type", "Choose audio, beat, or instrument."); return
    result = safe_call(add_track, STATE["project"], STATE["user"]["user_id"], name, kind)
    if result: set_status(result[1]); show_project()

def remove_track(track):
    if messagebox.askyesno("Remove track", "Remove '%s' and its contents?" % track["track_name"]):
        result = safe_call(delete_track, track["track_id"])
        if result is not None: set_status("Track removed."); show_project()

def add_clip_dialog(track):
    files = safe_call(list_user_files, STATE["user"]["user_id"]) or []
    if not files:
        messagebox.showinfo("Audio library", "Import a WAV file in the Library first."); return
    options = ["%s  (#%s)" % (r["file_name"], r["file_id"]) for r in files]
    chosen = simpledialog.askstring("Add audio clip", "Available files:\n" + "\n".join(options) +
                                    "\n\nEnter the file ID:", parent=STATE["root"])
    if not chosen: return
    try: file_id = int(chosen)
    except ValueError:
        messagebox.showwarning("File ID", "Enter a numeric file ID."); return
    start = simpledialog.askfloat("Clip position", "Start time in seconds:", initialvalue=0,
                                  minvalue=0, parent=STATE["root"])
    if start is None: return
    result = safe_call(add_clip, track["track_id"], STATE["user"]["user_id"], file_id, start)
    if result: set_status(result[1]); show_project()

def show_library():
    STATE["page"] = "library"
    body = app_shell("library")
    heading(body, "Your sounds", "Audio library", "Import WAV files to use them in your sessions.")
    row = tk.Frame(body, bg=COL["bg"])
    row.pack(fill="x", pady=18)
    button(row, "+ IMPORT WAV", import_wavs, True).pack(side="left")
    files = safe_call(list_user_files, STATE["user"]["user_id"]) or []
    if not files:
        card = panel(body, padx=24, pady=25); card.pack(fill="x")
        label(card, "Your library is quiet.", 15, COL["text"], True).pack(anchor="w")
        label(card, "Import a WAV file to get started.", 10, COL["muted"]).pack(anchor="w", pady=(5, 0))
        return
    tree_frame = panel(body, padx=12, pady=12)
    tree_frame.pack(fill="both", expand=True)
    style = ttk.Style()
    style.configure("Sound.Treeview", background=COL["panel"], foreground=COL["text"],
                    fieldbackground=COL["panel"], rowheight=34, font=FONT)
    style.configure("Sound.Treeview.Heading", background=COL["panel2"],
                    foreground=COL["muted"], font=FONT_B, relief="flat")
    tree = ttk.Treeview(tree_frame, columns=("file", "duration", "rate", "channels"),
                        show="headings", style="Sound.Treeview", height=10)
    for col, title, width in [("file","FILE",330),("duration","DURATION",110),
                              ("rate","SAMPLE RATE",130),("channels","CHANNELS",100)]:
        tree.heading(col, text=title); tree.column(col, width=width, anchor="w" if col=="file" else "center")
    tree.pack(fill="both", expand=True)
    for r in files:
        tree.insert("", "end", iid=str(r["file_id"]), values=(
            r["file_name"], "%.2f sec" % float(r["duration_sec"] or 0),
            "%s Hz" % r["sample_rate"], "Stereo" if r["channels"] == 2 else "Mono"))
    def remove_selected():
        sel = tree.selection()
        if not sel: messagebox.showinfo("Select a file", "Choose a file first."); return
        row = next((r for r in files if r["file_id"] == int(sel[0])), None)
        if row and messagebox.askyesno("Remove file", "Remove '%s' from your library? The WAV stays on disk." % row["file_name"]):
            result = safe_call(remove_audio_file, row["file_id"], STATE["user"]["user_id"])
            if result: set_status(result[1]); show_library()
    button(row, "REMOVE SELECTED", remove_selected).pack(side="right")

def import_wavs():
    paths = filedialog.askopenfilenames(parent=STATE["root"], title="Import WAV audio",
                                        filetypes=[("WAV audio", "*.wav")])
    added, errors = 0, []
    for path in paths:
        result = safe_call(import_audio_file, STATE["user"]["user_id"], path)
        if result:
            fid, msg = result
            if fid: added += 1
            else: errors.append(os.path.basename(path) + ": " + msg)
    if added: set_status("Imported %d WAV file(s)." % added)
    if errors: messagebox.showwarning("Some files were skipped", "\n".join(errors))
    show_library()

def export_current():
    proj = safe_call(get_project, STATE["project"], STATE["user"]["user_id"])
    if not proj: return
    os.makedirs(EXPORT_DIR, exist_ok=True)
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in proj["name"]) or "mix"
    path = filedialog.asksaveasfilename(parent=STATE["root"], title="Export mix",
        initialdir=EXPORT_DIR, initialfile=safe + ".wav",
        defaultextension=".wav", filetypes=[("WAV audio", "*.wav")])
    if not path: return
    set_status("Rendering project…")
    STATE["root"].configure(cursor="watch")
    STATE["root"].update_idletasks()
    try:
        audio = render_project(STATE["project"], STATE["user"]["user_id"], True, False)
        if audio is None:
            messagebox.showinfo("Nothing to export", "Add clips, beats or notes before exporting.")
            return
        save_wav(path, audio)
        set_status("Exported " + os.path.basename(path))
        messagebox.showinfo("Export complete", "Your WAV mix was saved to:\n" + path)
    except Exception as exc:
        messagebox.showerror("Export failed", str(exc))
    finally:
        STATE["root"].configure(cursor="")

def main():
    root = tk.Tk()
    STATE["root"] = root
    root.title("Soundpad Studio")
    root.geometry("1120x760")
    root.minsize(860, 620)
    root.configure(bg=COL["bg"])
    root.option_add("*Font", FONT)
    STATE["status"] = tk.StringVar(value="Ready")
    show_login()
    statusbar = tk.Frame(root, bg=COL["panel"], height=30)
    statusbar.pack(side="bottom", fill="x")
    label(statusbar, "●", 8, COL["cyan"]).pack(side="left", padx=(14, 6), pady=7)
    tk.Label(statusbar, textvariable=STATE["status"], bg=COL["panel"],
             fg=COL["muted"], font=("Segoe UI", 9)).pack(side="left", pady=6)
    label(statusbar, "SOUNDPAD  /  BUILD 01", 8, COL["muted"], True,
          bg=COL["panel"]).pack(side="right", padx=14)
    root.protocol("WM_DELETE_WINDOW", lambda: (db.close_connection(), root.destroy()))
    root.mainloop()

if __name__ == "__main__":
    main()
