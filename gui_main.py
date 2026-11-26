"""
gui_main.py - Procedural Desktop GUI for Soundpad Studio.
Features:
- Live 12-Pad Trigger Board
- FL Studio 16-Step Drum Sequencer (BPM + Swing)
- Complete Audio Editor / Lab: Cut, Trim, Merge, Mix, Fade, Echo, Filters
- Audio Library Manager (Import WAV, Delete, Play)
- Project Mixer (Tracks, Mute/Solo, Vol)
- Threaded non-blocking playback with emergency global stop
- Strictly procedural (no classes/OOP).
"""

import os
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

# Backend modules
import auth
import audio_io
import projects
import render
import beats
import editing as ed
from db import close_connection

# -----------------------------------------------------------------------------
# GLOBAL STATE
# -----------------------------------------------------------------------------
current_user = None
root = None
content_frame = None

# Audio Lab / Editor State
lab_state = {
    "file_id": None,
    "file_name": "",
    "audio": None,      # {"rate": int, "channels": [[...]]}
    "undo": [],
    "redo": [],
    "saved": True
}

# Step Sequencer State
SEQUENCER_DRUMS = ["Kick", "Snare", "Closed Hi-Hat", "Open Hi-Hat", "Clap", "Rimshot", "Low Tom", "High Tom"]
sequencer_grid = {}       # {drum_name: [0] * 16}
sequencer_bpm = 120
sequencer_swing = 0.0
is_sequencer_playing = False

# Dark Studio Theme Palette
COLOR_BG = "#121214"
COLOR_SIDEBAR = "#18181b"
COLOR_PANEL = "#222227"
COLOR_BORDER = "#2f2f38"
COLOR_ACCENT = "#6366f1"
COLOR_ACCENT_HOVER = "#4f46e5"
COLOR_SUCCESS = "#10b981"
COLOR_DANGER = "#ef4444"
COLOR_TEXT = "#f4f4f5"
COLOR_MUTED = "#a1a1aa"

STEP_ON_COLOR = "#f97316"
STEP_OFF_BEAT = "#2c2d35"
STEP_OFF_OFFBEAT = "#1e1e24"

PAD_COLORS = [
    "#f43f5e", "#ec4899", "#8b5cf6", "#6366f1",
    "#0ea5e9", "#14b8a6", "#10b981", "#eab308",
    "#f97316", "#06b6d4", "#a855f7", "#3b82f6"
]

def init_sequencer_data():
    global sequencer_grid
    sequencer_grid = {drum: [0] * 16 for drum in SEQUENCER_DRUMS}
    sequencer_grid["Kick"][0] = 1
    sequencer_grid["Kick"][4] = 1
    sequencer_grid["Kick"][8] = 1
    sequencer_grid["Kick"][12] = 1
    sequencer_grid["Snare"][4] = 1
    sequencer_grid["Snare"][12] = 1
    for s in range(0, 16, 2):
        sequencer_grid["Closed Hi-Hat"][s] = 1

init_sequencer_data()

# -----------------------------------------------------------------------------
# THREADING & PLAYBACK CONTROLS
# -----------------------------------------------------------------------------
def stop_all_audio():
    """Instantly kills all active audio playback."""
    global is_sequencer_playing
    is_sequencer_playing = False
    audio_io.stop_playback()

def run_in_background(task_func, *args):
    """Executes long-running audio playback or mixing in a background daemon thread."""
    t = threading.Thread(target=task_func, args=args, daemon=True)
    t.start()

def thread_safe_play_wav(path):
    run_in_background(audio_io.play_file, path, False)

def thread_safe_play_audio_dict(audio_dict):
    run_in_background(audio_io.play_audio, audio_dict, False)

# -----------------------------------------------------------------------------
# UI STYLING ROUTINES
# -----------------------------------------------------------------------------
def clear_container(container):
    for widget in container.winfo_children():
        widget.destroy()

def style_button(btn, bg=COLOR_PANEL, fg=COLOR_TEXT, hover=COLOR_BORDER):
    btn.config(
        bg=bg, fg=fg, activebackground=hover, activeforeground=fg,
        relief="flat", bd=0, padx=12, pady=6, cursor="hand2", font=("Segoe UI", 9, "bold")
    )
    btn.bind("<Enter>", lambda e: btn.config(bg=hover))
    btn.bind("<Leave>", lambda e: btn.config(bg=bg))

def setup_modern_theme():
    style = ttk.Style()
    style.theme_use("clam")
    style.configure(".", background=COLOR_BG, foreground=COLOR_TEXT, font=("Segoe UI", 9))
    style.configure("TFrame", background=COLOR_BG)
    style.configure("Treeview", background=COLOR_PANEL, foreground=COLOR_TEXT,
                    fieldbackground=COLOR_PANEL, borderwidth=0, rowheight=28)
    style.map("Treeview", background=[("selected", COLOR_ACCENT)], foreground=[("selected", "#ffffff")])
    style.configure("Treeview.Heading", background=COLOR_SIDEBAR, foreground=COLOR_MUTED, relief="flat", font=("Segoe UI", 9, "bold"))

# -----------------------------------------------------------------------------
# AUTHENTICATION
# -----------------------------------------------------------------------------
def show_login_screen():
    stop_all_audio()
    clear_container(root)

    center = tk.Frame(root, bg=COLOR_PANEL, padx=40, pady=35, highlightbackground=COLOR_BORDER, highlightthickness=1)
    center.place(relx=0.5, rely=0.5, anchor="center")

    tk.Label(center, text="SOUNDPAD STUDIO", font=("Segoe UI", 18, "bold"), bg=COLOR_PANEL, fg=COLOR_ACCENT).pack(pady=(0, 4))
    tk.Label(center, text="Class 12 CS Studio Project", font=("Segoe UI", 9), bg=COLOR_PANEL, fg=COLOR_MUTED).pack(pady=(0, 20))

    tk.Label(center, text="Username", font=("Segoe UI", 9, "bold"), bg=COLOR_PANEL, fg=COLOR_TEXT).pack(anchor="w")
    u_entry = tk.Entry(center, font=("Segoe UI", 10), bg=COLOR_SIDEBAR, fg=COLOR_TEXT, insertbackground=COLOR_TEXT, relief="flat", bd=6)
    u_entry.pack(fill="x", pady=(4, 12))

    tk.Label(center, text="Password", font=("Segoe UI", 9, "bold"), bg=COLOR_PANEL, fg=COLOR_TEXT).pack(anchor="w")
    p_entry = tk.Entry(center, font=("Segoe UI", 10), show="•", bg=COLOR_SIDEBAR, fg=COLOR_TEXT, insertbackground=COLOR_TEXT, relief="flat", bd=6)
    p_entry.pack(fill="x", pady=(4, 20))

    def on_login():
        global current_user
        user = auth.login_user(u_entry.get().strip(), p_entry.get().strip())
        if user:
            current_user = user
            show_main_layout()
        else:
            messagebox.showerror("Error", "Invalid username or password.")

    btn_login = tk.Button(center, text="Sign In", command=on_login)
    style_button(btn_login, bg=COLOR_ACCENT, hover=COLOR_ACCENT_HOVER)
    btn_login.pack(fill="x", pady=(0, 8))

    btn_reg = tk.Button(center, text="Create Account", command=show_register_screen)
    style_button(btn_reg, bg=COLOR_SIDEBAR, hover=COLOR_BORDER)
    btn_reg.pack(fill="x")

def show_register_screen():
    clear_container(root)
    center = tk.Frame(root, bg=COLOR_PANEL, padx=40, pady=35, highlightbackground=COLOR_BORDER, highlightthickness=1)
    center.place(relx=0.5, rely=0.5, anchor="center")

    tk.Label(center, text="Register", font=("Segoe UI", 16, "bold"), bg=COLOR_PANEL, fg=COLOR_TEXT).pack(pady=(0, 15))

    tk.Label(center, text="Username", bg=COLOR_PANEL, fg=COLOR_TEXT).pack(anchor="w")
    u_entry = tk.Entry(center, bg=COLOR_SIDEBAR, fg=COLOR_TEXT, insertbackground=COLOR_TEXT, relief="flat", bd=6)
    u_entry.pack(fill="x", pady=(4, 10))

    tk.Label(center, text="Password", bg=COLOR_PANEL, fg=COLOR_TEXT).pack(anchor="w")
    p1_entry = tk.Entry(center, show="•", bg=COLOR_SIDEBAR, fg=COLOR_TEXT, insertbackground=COLOR_TEXT, relief="flat", bd=6)
    p1_entry.pack(fill="x", pady=(4, 10))

    tk.Label(center, text="Confirm Password", bg=COLOR_PANEL, fg=COLOR_TEXT).pack(anchor="w")
    p2_entry = tk.Entry(center, show="•", bg=COLOR_SIDEBAR, fg=COLOR_TEXT, insertbackground=COLOR_TEXT, relief="flat", bd=6)
    p2_entry.pack(fill="x", pady=(4, 20))

    def on_register():
        if p1_entry.get() != p2_entry.get():
            messagebox.showerror("Error", "Passwords do not match.")
            return
        ok, msg = auth.register_user(u_entry.get().strip(), p1_entry.get())
        if ok:
            messagebox.showinfo("Success", msg)
            show_login_screen()
        else:
            messagebox.showerror("Error", msg)

    btn_done = tk.Button(center, text="Register", command=on_register)
    style_button(btn_done, bg=COLOR_SUCCESS, hover="#059669")
    btn_done.pack(fill="x", pady=(0, 8))

    btn_back = tk.Button(center, text="Back", command=show_login_screen)
    style_button(btn_back, bg=COLOR_SIDEBAR, hover=COLOR_BORDER)
    btn_back.pack(fill="x")

# -----------------------------------------------------------------------------
# MAIN APP SHELL
# -----------------------------------------------------------------------------
def show_main_layout():
    clear_container(root)
    global content_frame

    # Header Bar
    topbar = tk.Frame(root, bg=COLOR_SIDEBAR, height=52, padx=20)
    topbar.pack(side="top", fill="x")

    tk.Label(topbar, text="SOUNDPAD STUDIO", font=("Segoe UI", 12, "bold"), bg=COLOR_SIDEBAR, fg=COLOR_ACCENT).pack(side="left")
    tk.Label(topbar, text=f"•  User: {current_user['username']}", font=("Segoe UI", 10), bg=COLOR_SIDEBAR, fg=COLOR_MUTED).pack(side="left", padx=10)

    btn_logout = tk.Button(topbar, text="Log Out", command=show_login_screen)
    style_button(btn_logout, bg=COLOR_SIDEBAR, hover=COLOR_BORDER)
    btn_logout.pack(side="right", padx=(8, 0))

    btn_global_stop = tk.Button(topbar, text="⏹ STOP ALL AUDIO", command=stop_all_audio)
    style_button(btn_global_stop, bg=COLOR_DANGER, hover="#dc2626")
    btn_global_stop.pack(side="right", padx=10)

    # Main Area
    body = tk.Frame(root, bg=COLOR_BG)
    body.pack(side="bottom", fill="both", expand=True)

    nav = tk.Frame(body, bg=COLOR_SIDEBAR, width=200, padx=12, pady=16)
    nav.pack(side="left", fill="y")
    nav.pack_propagate(False)

    nav_btns = [
        ("🎛️ Soundpad", view_soundpad),
        ("🎹 FL Step Sequencer", view_sequencer),
        ("✂️ Audio Editor & Lab", view_audio_lab),
        ("📁 Audio Library", view_library),
        ("🎚️ Projects & Mixer", view_projects),
    ]

    for label, target in nav_btns:
        b = tk.Button(nav, text=label, anchor="w", command=target)
        style_button(b, bg=COLOR_SIDEBAR, hover=COLOR_PANEL)
        b.pack(fill="x", pady=3)

    content_frame = tk.Frame(body, bg=COLOR_BG, padx=20, pady=20)
    content_frame.pack(side="right", fill="both", expand=True)

    view_soundpad()

# -----------------------------------------------------------------------------
# VIEW 1: LIVE SOUNDPAD
# -----------------------------------------------------------------------------
def view_soundpad():
    clear_container(content_frame)

    header = tk.Frame(content_frame, bg=COLOR_BG)
    header.pack(fill="x", pady=(0, 15))
    tk.Label(header, text="Trigger Soundpad", font=("Segoe UI", 16, "bold"), bg=COLOR_BG, fg=COLOR_TEXT).pack(side="left")

    files = audio_io.list_user_files(current_user["user_id"])
    if not files:
        tk.Label(content_frame, text="No audio files available.\nImport WAV files in the Library tab to trigger them here.",
                 font=("Segoe UI", 11), bg=COLOR_BG, fg=COLOR_MUTED, justify="center").pack(expand=True)
        return

    grid = tk.Frame(content_frame, bg=COLOR_BG)
    grid.pack(fill="both", expand=True)

    for i in range(12):
        row, col = divmod(i, 4)
        grid.grid_columnconfigure(col, weight=1, uniform="pad")
        grid.grid_rowconfigure(row, weight=1, uniform="pad")

        if i < len(files):
            file_meta = files[i]
            btn_color = PAD_COLORS[i % len(PAD_COLORS)]
            title = file_meta["file_name"]
            dur = f"{file_meta['duration_sec']}s"

            def trigger_pad(fid=file_meta["file_id"]):
                row_data = audio_io.get_audio_file(fid, current_user["user_id"])
                if row_data and os.path.isfile(row_data["file_path"]):
                    thread_safe_play_wav(row_data["file_path"])

            pad = tk.Button(
                grid, text=f"{title}\n[{dur}]", font=("Segoe UI", 10, "bold"),
                bg=COLOR_PANEL, fg=btn_color, activebackground=btn_color, activeforeground="#ffffff",
                relief="flat", highlightbackground=COLOR_BORDER, highlightthickness=1, cursor="hand2",
                command=trigger_pad
            )
        else:
            pad = tk.Button(grid, text="Empty", font=("Segoe UI", 9), bg=COLOR_SIDEBAR, fg=COLOR_MUTED, relief="flat", state="disabled")

        pad.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")

# -----------------------------------------------------------------------------
# VIEW 2: FL STUDIO STEP SEQUENCER
# -----------------------------------------------------------------------------
def render_current_grid_loop(bpm, swing, rate=44100):
    step_sec = 60.0 / bpm / 4
    total_len = int(round(16 * step_sec * rate))
    loop = ed.make_audio(rate, 2, 0)
    cache = {}

    for drum_name, steps in sequencer_grid.items():
        if drum_name not in beats.DRUM_SYNTHS:
            continue
        drum_audio = {"rate": rate, "channels": [beats.DRUM_SYNTHS[drum_name](rate)]}
        drum_stereo = ed.to_stereo(drum_audio)

        for s_idx, active in enumerate(steps):
            if active:
                t = s_idx * step_sec
                if s_idx % 2 == 1:
                    t += float(swing) * step_sec * 0.5
                ed.mix_into(loop, drum_stereo, t, 1.0)

    for ch in loop["channels"]:
        if len(ch) < total_len:
            ch.extend([0.0] * (total_len - len(ch)))
        else:
            for i, v in enumerate(ch[total_len:]):
                ch[i % total_len] += v
            del ch[total_len:]
    return loop

def sequencer_playback_loop():
    global is_sequencer_playing
    while is_sequencer_playing:
        loop = render_current_grid_loop(sequencer_bpm, sequencer_swing)
        audio_io.play_audio(ed.limit(loop), wait=True)

def view_sequencer():
    clear_container(content_frame)

    header = tk.Frame(content_frame, bg=COLOR_BG)
    header.pack(fill="x", pady=(0, 12))
    tk.Label(header, text="Step Sequencer (FL Studio Style Grid)", font=("Segoe UI", 16, "bold"), bg=COLOR_BG, fg=COLOR_TEXT).pack(side="left")

    controls = tk.Frame(content_frame, bg=COLOR_PANEL, padx=12, pady=10, highlightbackground=COLOR_BORDER, highlightthickness=1)
    controls.pack(fill="x", pady=(0, 15))

    tk.Label(controls, text="Tempo (BPM):", bg=COLOR_PANEL, fg=COLOR_TEXT, font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 5))
    bpm_spin = tk.Spinbox(controls, from_=40, to=240, width=5, bg=COLOR_SIDEBAR, fg=COLOR_TEXT, insertbackground=COLOR_TEXT, relief="flat", bd=4)
    bpm_spin.delete(0, "end")
    bpm_spin.insert(0, str(sequencer_bpm))
    bpm_spin.pack(side="left", padx=(0, 15))

    tk.Label(controls, text="Swing:", bg=COLOR_PANEL, fg=COLOR_TEXT, font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 5))
    swing_scale = tk.Scale(controls, from_=0.0, to=0.8, resolution=0.05, orient="horizontal",
                           bg=COLOR_PANEL, fg=COLOR_TEXT, highlightthickness=0, bd=0, length=90)
    swing_scale.set(sequencer_swing)
    swing_scale.pack(side="left", padx=(0, 15))

    def on_play_sequencer():
        global is_sequencer_playing, sequencer_bpm, sequencer_swing
        if is_sequencer_playing:
            return
        try:
            sequencer_bpm = int(bpm_spin.get())
        except ValueError:
            sequencer_bpm = 120
        sequencer_swing = swing_scale.get()
        is_sequencer_playing = True
        run_in_background(sequencer_playback_loop)

    btn_play = tk.Button(controls, text="▶ PLAY LOOP", command=on_play_sequencer)
    style_button(btn_play, bg=COLOR_SUCCESS, hover="#059669")
    btn_play.pack(side="left", padx=(0, 8))

    btn_stop = tk.Button(controls, text="⏹ STOP", command=stop_all_audio)
    style_button(btn_stop, bg=COLOR_DANGER, hover="#dc2626")
    btn_stop.pack(side="left", padx=(0, 15))

    preset_var = tk.StringVar(value="rock")
    preset_box = ttk.Combobox(controls, textvariable=preset_var, values=beats.list_presets(), state="readonly", width=10)
    preset_box.pack(side="left", padx=(0, 5))

    def load_preset_to_grid():
        name = preset_var.get()
        preset = beats.PRESETS.get(name, {})
        for d in SEQUENCER_DRUMS:
            sequencer_grid[d] = [0] * 16
        for drum_name, hit_str in preset.items():
            if drum_name in sequencer_grid:
                for idx, char in enumerate(hit_str[:16]):
                    if char in ("x", "o"):
                        sequencer_grid[drum_name][idx] = 1
        view_sequencer()

    btn_preset = tk.Button(controls, text="Load Preset", command=load_preset_to_grid)
    style_button(btn_preset, bg=COLOR_SIDEBAR, hover=COLOR_BORDER)
    btn_preset.pack(side="left", padx=(0, 8))

    def clear_grid():
        for d in SEQUENCER_DRUMS:
            sequencer_grid[d] = [0] * 16
        view_sequencer()

    btn_clear = tk.Button(controls, text="Clear All", command=clear_grid)
    style_button(btn_clear, bg=COLOR_SIDEBAR, hover=COLOR_BORDER)
    btn_clear.pack(side="left")

    grid_container = tk.Frame(content_frame, bg=COLOR_PANEL, padx=15, pady=15, highlightbackground=COLOR_BORDER, highlightthickness=1)
    grid_container.pack(fill="both", expand=True)

    header_row = tk.Frame(grid_container, bg=COLOR_PANEL)
    header_row.pack(fill="x", pady=(0, 6))
    tk.Label(header_row, text="", width=14, bg=COLOR_PANEL).pack(side="left")
    for s in range(16):
        bar_color = COLOR_ACCENT if s % 4 == 0 else COLOR_MUTED
        lbl = tk.Label(header_row, text=str(s + 1), font=("Segoe UI", 8, "bold"), fg=bar_color, bg=COLOR_PANEL, width=3)
        lbl.pack(side="left", padx=2)

    for drum_name in SEQUENCER_DRUMS:
        row = tk.Frame(grid_container, bg=COLOR_PANEL)
        row.pack(fill="x", pady=2)

        def audition_sound(d=drum_name):
            rate = 44100
            fn = beats.DRUM_SYNTHS[d]
            thread_safe_play_audio_dict(ed.to_stereo({"rate": rate, "channels": [fn(rate)]}))

        btn_inst = tk.Button(row, text=drum_name, anchor="w", font=("Segoe UI", 9, "bold"),
                             bg=COLOR_SIDEBAR, fg=COLOR_TEXT, relief="flat", bd=0, padx=8, pady=4, width=12,
                             cursor="hand2", command=audition_sound)
        btn_inst.pack(side="left", padx=(0, 6))

        for step in range(16):
            is_active = sequencer_grid[drum_name][step] == 1
            default_bg = STEP_OFF_BEAT if (step // 4) % 2 == 0 else STEP_OFF_OFFBEAT
            bg_color = STEP_ON_COLOR if is_active else default_bg

            def toggle_cell(d=drum_name, s=step):
                sequencer_grid[d][s] = 0 if sequencer_grid[d][s] == 1 else 1
                view_sequencer()

            cell = tk.Button(
                row, text="", width=3, height=1, relief="flat", bd=0,
                bg=bg_color, activebackground=COLOR_ACCENT, cursor="hand2",
                command=toggle_cell
            )
            cell.pack(side="left", padx=2)

# -----------------------------------------------------------------------------
# VIEW 3: AUDIO EDITOR & LAB (CUT, MERGE, MIX, EFFECTS)
# -----------------------------------------------------------------------------
def lab_apply_change(new_audio):
    """Pushes previous audio into undo stack, sets new audio, and clears redo."""
    lab_state["undo"].append(lab_state["audio"])
    lab_state["audio"] = new_audio
    lab_state["redo"].clear()
    lab_state["saved"] = False
    view_audio_lab()

def draw_canvas_waveform(canvas, audio_dict):
    """Draws a sleek audio waveform onto a Tkinter Canvas."""
    canvas.delete("all")
    if not audio_dict or not audio_dict["channels"]:
        return

    w = canvas.winfo_width()
    h = canvas.winfo_height()
    if w <= 1:
        w = 700
    if h <= 1:
        h = 100

    mid = h / 2.0
    channel = audio_dict["channels"][0]
    total_samples = len(channel)
    if total_samples == 0:
        return

    step = max(1, total_samples // w)
    canvas.create_line(0, mid, w, mid, fill=COLOR_BORDER, width=1)

    for x in range(min(w, total_samples // step)):
        chunk = channel[x * step:(x + 1) * step]
        if chunk:
            peak = max(abs(s) for s in chunk)
            bar_height = max(1.0, peak * (mid - 6))
            canvas.create_line(x, mid - bar_height, x, mid + bar_height, fill=COLOR_ACCENT, width=1)

def view_audio_lab():
    clear_container(content_frame)

    header = tk.Frame(content_frame, bg=COLOR_BG)
    header.pack(fill="x", pady=(0, 12))
    tk.Label(header, text="Audio Editor & Lab", font=("Segoe UI", 16, "bold"), bg=COLOR_BG, fg=COLOR_TEXT).pack(side="left")

    # If no file is loaded, show selector
    if lab_state["audio"] is None:
        empty_box = tk.Frame(content_frame, bg=COLOR_PANEL, padx=30, pady=40, highlightbackground=COLOR_BORDER, highlightthickness=1)
        empty_box.pack(fill="x", pady=20)
        tk.Label(empty_box, text="No Audio File Loaded in Editor", font=("Segoe UI", 13, "bold"), bg=COLOR_PANEL, fg=COLOR_TEXT).pack(pady=(0, 6))
        tk.Label(empty_box, text="Select an imported WAV from your audio library to begin cutting, merging, or editing.", font=("Segoe UI", 9), bg=COLOR_PANEL, fg=COLOR_MUTED).pack(pady=(0, 16))

        files = audio_io.list_user_files(current_user["user_id"])
        if files:
            pick_var = tk.StringVar(value=f"{files[0]['file_id']}: {files[0]['file_name']}")
            opts = [f"{f['file_id']}: {f['file_name']}" for f in files]
            combo = ttk.Combobox(empty_box, textvariable=pick_var, values=opts, state="readonly", width=40)
            combo.pack(pady=(0, 12))

            def on_load_selected():
                selected_str = pick_var.get()
                fid = int(selected_str.split(":")[0])
                audio = audio_io.load_audio_by_id(fid, current_user["user_id"])
                if audio:
                    lab_state["file_id"] = fid
                    lab_state["file_name"] = selected_str.split(":")[1].strip()
                    lab_state["audio"] = audio
                    lab_state["undo"].clear()
                    lab_state["redo"].clear()
                    lab_state["saved"] = True
                    view_audio_lab()
                else:
                    messagebox.showerror("Error", "Could not load file from disk.")

            btn_load = tk.Button(empty_box, text="Open in Editor", command=on_load_selected)
            style_button(btn_load, bg=COLOR_ACCENT, hover=COLOR_ACCENT_HOVER)
            btn_load.pack()
        else:
            tk.Label(empty_box, text="Library is empty. Import a .WAV file in the Audio Library tab first.", bg=COLOR_PANEL, fg=COLOR_DANGER).pack()
        return

    # File Info Bar & Save/Undo
    a = lab_state["audio"]
    dur = ed.duration(a)
    peak = ed.get_peak(a)
    channels_label = "Stereo" if len(a["channels"]) == 2 else "Mono"

    info_card = tk.Frame(content_frame, bg=COLOR_PANEL, padx=15, pady=10, highlightbackground=COLOR_BORDER, highlightthickness=1)
    info_card.pack(fill="x", pady=(0, 10))

    tk.Label(info_card, text=f"File: {lab_state['file_name']}", font=("Segoe UI", 11, "bold"), bg=COLOR_PANEL, fg=COLOR_TEXT).pack(side="left")
    meta_text = f"{dur:.2f}s  |  {a['rate']} Hz  |  {channels_label}  |  Peak: {ed.to_db(peak):.1f} dB"
    tk.Label(info_card, text=meta_text, font=("Segoe UI", 9), bg=COLOR_PANEL, fg=COLOR_MUTED).pack(side="left", padx=15)

    def on_undo():
        if lab_state["undo"]:
            lab_state["redo"].append(lab_state["audio"])
            lab_state["audio"] = lab_state["undo"].pop()
            lab_state["saved"] = False
            view_audio_lab()

    def on_redo():
        if lab_state["redo"]:
            lab_state["undo"].append(lab_state["audio"])
            lab_state["audio"] = lab_state["redo"].pop()
            lab_state["saved"] = False
            view_audio_lab()

    def on_save_as():
        dest = filedialog.asksaveasfilename(defaultextension=".wav", filetypes=[("WAV files", "*.wav")])
        if dest:
            audio_io.save_wav(dest, ed.limit(lab_state["audio"]))
            audio_io.import_audio_file(current_user["user_id"], dest)
            lab_state["saved"] = True
            messagebox.showinfo("Saved", f"Exported & imported to library:\n{os.path.basename(dest)}")

    def on_close_editor():
        if lab_state["saved"] or messagebox.askyesno("Confirm", "Discard unsaved changes?"):
            lab_state["audio"] = None
            view_audio_lab()

    btn_close = tk.Button(info_card, text="Close File", command=on_close_editor)
    style_button(btn_close, bg=COLOR_SIDEBAR, hover=COLOR_BORDER)
    btn_close.pack(side="right", padx=(5, 0))

    btn_save = tk.Button(info_card, text="💾 Save to Library", command=on_save_as)
    style_button(btn_save, bg=COLOR_SUCCESS, hover="#059669")
    btn_save.pack(side="right", padx=5)

    btn_redo = tk.Button(info_card, text="↷ Redo", state="normal" if lab_state["redo"] else "disabled", command=on_redo)
    style_button(btn_redo, bg=COLOR_SIDEBAR, hover=COLOR_BORDER)
    btn_redo.pack(side="right", padx=3)

    btn_undo = tk.Button(info_card, text="↶ Undo", state="normal" if lab_state["undo"] else "disabled", command=on_undo)
    style_button(btn_undo, bg=COLOR_SIDEBAR, hover=COLOR_BORDER)
    btn_undo.pack(side="right", padx=3)

    # Waveform Display
    wave_canvas = tk.Canvas(content_frame, height=90, bg=COLOR_SIDEBAR, highlightthickness=1, highlightbackground=COLOR_BORDER)
    wave_canvas.pack(fill="x", pady=(0, 12))
    wave_canvas.bind("<Configure>", lambda e: draw_canvas_waveform(wave_canvas, lab_state["audio"]))

    # Audition Bar
    audition_bar = tk.Frame(content_frame, bg=COLOR_BG)
    audition_bar.pack(fill="x", pady=(0, 12))

    btn_preview = tk.Button(audition_bar, text="▶ Play Edited Audio", command=lambda: thread_safe_play_audio_dict(ed.limit(lab_state["audio"])))
    style_button(btn_preview, bg=COLOR_ACCENT, hover=COLOR_ACCENT_HOVER)
    btn_preview.pack(side="left", padx=(0, 8))

    btn_stop_audition = tk.Button(audition_bar, text="⏹ Stop", command=stop_all_audio)
    style_button(btn_stop_audition, bg=COLOR_DANGER, hover="#dc2626")
    btn_stop_audition.pack(side="left")

    # Operations Panel (Tabs or categorized frame)
    toolbox = tk.Frame(content_frame, bg=COLOR_PANEL, padx=15, pady=12, highlightbackground=COLOR_BORDER, highlightthickness=1)
    toolbox.pack(fill="both", expand=True)

    # Cut & Trim Section
    tk.Label(toolbox, text="1. Cut & Trim (Time Controls)", font=("Segoe UI", 10, "bold"), bg=COLOR_PANEL, fg=COLOR_TEXT).pack(anchor="w", pady=(0, 4))
    cut_frame = tk.Frame(toolbox, bg=COLOR_PANEL)
    cut_frame.pack(fill="x", pady=(0, 12))

    tk.Label(cut_frame, text="Start (s):", bg=COLOR_PANEL, fg=COLOR_MUTED).pack(side="left")
    start_entry = tk.Entry(cut_frame, width=6, bg=COLOR_SIDEBAR, fg=COLOR_TEXT, relief="flat", bd=4)
    start_entry.insert(0, "0.0")
    start_entry.pack(side="left", padx=(4, 10))

    tk.Label(cut_frame, text="End (s):", bg=COLOR_PANEL, fg=COLOR_MUTED).pack(side="left")
    end_entry = tk.Entry(cut_frame, width=6, bg=COLOR_SIDEBAR, fg=COLOR_TEXT, relief="flat", bd=4)
    end_entry.insert(0, f"{dur:.2f}")
    end_entry.pack(side="left", padx=(4, 15))

    def on_trim():
        try:
            s = float(start_entry.get())
            e = float(end_entry.get())
            if e > s:
                lab_apply_change(ed.trim(lab_state["audio"], s, e))
        except ValueError:
            messagebox.showerror("Error", "Please enter valid numeric seconds.")

    def on_cut_out():
        try:
            s = float(start_entry.get())
            e = float(end_entry.get())
            if e > s:
                lab_apply_change(ed.cut_out(lab_state["audio"], s, e))
        except ValueError:
            messagebox.showerror("Error", "Please enter valid numeric seconds.")

    btn_trim = tk.Button(cut_frame, text="✂️ Trim (Keep Selection)", command=on_trim)
    style_button(btn_trim, bg=COLOR_SIDEBAR, hover=COLOR_BORDER)
    btn_trim.pack(side="left", padx=4)

    btn_cut = tk.Button(cut_frame, text="🗑 Cut Out (Delete Selection)", command=on_cut_out)
    style_button(btn_cut, bg=COLOR_SIDEBAR, hover=COLOR_BORDER)
    btn_cut.pack(side="left", padx=4)

    # Merge & Mix Section
    tk.Label(toolbox, text="2. Merge & Mix (Multi-file Combining)", font=("Segoe UI", 10, "bold"), bg=COLOR_PANEL, fg=COLOR_TEXT).pack(anchor="w", pady=(0, 4))
    merge_frame = tk.Frame(toolbox, bg=COLOR_PANEL)
    merge_frame.pack(fill="x", pady=(0, 12))

    other_files = [f for f in audio_io.list_user_files(current_user["user_id"]) if f["file_id"] != lab_state["file_id"]]
    if other_files:
        merge_var = tk.StringVar(value=f"{other_files[0]['file_id']}: {other_files[0]['file_name']}")
        combo_merge = ttk.Combobox(merge_frame, textvariable=merge_var, values=[f"{f['file_id']}: {f['file_name']}" for f in other_files], state="readonly", width=25)
        combo_merge.pack(side="left", padx=(0, 8))

        def on_merge():
            target_id = int(merge_var.get().split(":")[0])
            other_audio = audio_io.load_audio_by_id(target_id, current_user["user_id"])
            if other_audio:
                lab_apply_change(ed.merge(lab_state["audio"], other_audio))

        def on_mix():
            target_id = int(merge_var.get().split(":")[0])
            other_audio = audio_io.load_audio_by_id(target_id, current_user["user_id"])
            if other_audio:
                base_copy = ed.copy_audio(lab_state["audio"])
                ed.mix_into(base_copy, other_audio, start_sec=0.0, volume=1.0)
                lab_apply_change(base_copy)

        btn_merge = tk.Button(merge_frame, text="➕ Merge After (Append)", command=on_merge)
        style_button(btn_merge, bg=COLOR_SIDEBAR, hover=COLOR_BORDER)
        btn_merge.pack(side="left", padx=4)

        btn_mix = tk.Button(merge_frame, text="🎚 Mix Over Top", command=on_mix)
        style_button(btn_mix, bg=COLOR_SIDEBAR, hover=COLOR_BORDER)
        btn_mix.pack(side="left", padx=4)
    else:
        tk.Label(merge_frame, text="Import more files into your library to merge or mix them together.", bg=COLOR_PANEL, fg=COLOR_MUTED).pack(side="left")

    # Volume, Speed & Effects Toolbar
    tk.Label(toolbox, text="3. Effects & Dynamics", font=("Segoe UI", 10, "bold"), bg=COLOR_PANEL, fg=COLOR_TEXT).pack(anchor="w", pady=(0, 4))
    fx_frame = tk.Frame(toolbox, bg=COLOR_PANEL)
    fx_frame.pack(fill="x")

    def apply_vol(factor):
        lab_apply_change(ed.change_volume(lab_state["audio"], factor))

    btn_norm = tk.Button(fx_frame, text="Normalize Peak", command=lambda: lab_apply_change(ed.normalize(lab_state["audio"], 0.95)))
    style_button(btn_norm, bg=COLOR_SIDEBAR, hover=COLOR_BORDER)
    btn_norm.pack(side="left", padx=3)

    btn_vol_up = tk.Button(fx_frame, text="+3dB Gain", command=lambda: apply_vol(1.4))
    style_button(btn_vol_up, bg=COLOR_SIDEBAR, hover=COLOR_BORDER)
    btn_vol_up.pack(side="left", padx=3)

    btn_vol_dn = tk.Button(fx_frame, text="-3dB Gain", command=lambda: apply_vol(0.7))
    style_button(btn_vol_dn, bg=COLOR_SIDEBAR, hover=COLOR_BORDER)
    btn_vol_dn.pack(side="left", padx=3)

    btn_fade_in = tk.Button(fx_frame, text="Fade In (1s)", command=lambda: lab_apply_change(ed.fade_in(lab_state["audio"], 1.0)))
    style_button(btn_fade_in, bg=COLOR_SIDEBAR, hover=COLOR_BORDER)
    btn_fade_in.pack(side="left", padx=3)

    btn_fade_out = tk.Button(fx_frame, text="Fade Out (1s)", command=lambda: lab_apply_change(ed.fade_out(lab_state["audio"], 1.0)))
    style_button(btn_fade_out, bg=COLOR_SIDEBAR, hover=COLOR_BORDER)
    btn_fade_out.pack(side="left", padx=3)

    btn_rev = tk.Button(fx_frame, text="Reverse", command=lambda: lab_apply_change(ed.reverse(lab_state["audio"])))
    style_button(btn_rev, bg=COLOR_SIDEBAR, hover=COLOR_BORDER)
    btn_rev.pack(side="left", padx=3)

    btn_echo = tk.Button(fx_frame, text="Echo (0.3s)", command=lambda: lab_apply_change(ed.add_echo(lab_state["audio"], delay_sec=0.3, decay=0.5, repeats=3)))
    style_button(btn_echo, bg=COLOR_SIDEBAR, hover=COLOR_BORDER)
    btn_echo.pack(side="left", padx=3)

    btn_dist = tk.Button(fx_frame, text="Distort Crunch", command=lambda: lab_apply_change(ed.distortion(lab_state["audio"], amount=5.0)))
    style_button(btn_dist, bg=COLOR_SIDEBAR, hover=COLOR_BORDER)
    btn_dist.pack(side="left", padx=3)

# -----------------------------------------------------------------------------
# VIEW 4: AUDIO LIBRARY
# -----------------------------------------------------------------------------
def view_library():
    clear_container(content_frame)

    header = tk.Frame(content_frame, bg=COLOR_BG)
    header.pack(fill="x", pady=(0, 15))
    tk.Label(header, text="Audio File Library", font=("Segoe UI", 16, "bold"), bg=COLOR_BG, fg=COLOR_TEXT).pack(side="left")

    def on_import():
        file_path = filedialog.askopenfilename(filetypes=[("WAV files", "*.wav")])
        if file_path:
            _, msg = audio_io.import_audio_file(current_user["user_id"], file_path)
            messagebox.showinfo("Import", msg)
            view_library()

    btn_import = tk.Button(header, text="+ Import .WAV", command=on_import)
    style_button(btn_import, bg=COLOR_ACCENT, hover=COLOR_ACCENT_HOVER)
    btn_import.pack(side="right")

    cols = ("ID", "File Name", "Duration (s)", "Sample Rate", "Channels", "Bit Depth")
    tree = ttk.Treeview(content_frame, columns=cols, show="headings", selectmode="browse")
    for col in cols:
        tree.heading(col, text=col)
        tree.column(col, anchor="center" if col != "File Name" else "w", width=110)
    tree.column("File Name", width=240)
    tree.pack(fill="both", expand=True)

    files = audio_io.list_user_files(current_user["user_id"])
    for f in files:
        tree.insert("", "end", values=(
            f["file_id"], f["file_name"], f["duration_sec"],
            f["sample_rate"], f["channels"], f["bit_depth"]
        ))

    actions = tk.Frame(content_frame, bg=COLOR_BG)
    actions.pack(fill="x", pady=(15, 0))

    def on_play():
        selected = tree.selection()
        if not selected:
            return
        f_id = tree.item(selected[0])["values"][0]
        row = audio_io.get_audio_file(f_id, current_user["user_id"])
        if row and os.path.isfile(row["file_path"]):
            thread_safe_play_wav(row["file_path"])

    def on_open_in_lab():
        selected = tree.selection()
        if not selected:
            return
        f_id = tree.item(selected[0])["values"][0]
        f_name = tree.item(selected[0])["values"][1]
        audio = audio_io.load_audio_by_id(f_id, current_user["user_id"])
        if audio:
            lab_state["file_id"] = f_id
            lab_state["file_name"] = f_name
            lab_state["audio"] = audio
            lab_state["undo"].clear()
            lab_state["redo"].clear()
            lab_state["saved"] = True
            view_audio_lab()

    def on_delete():
        selected = tree.selection()
        if not selected:
            return
        f_id = tree.item(selected[0])["values"][0]
        if messagebox.askyesno("Confirm", "Remove this audio clip from library?"):
            ok, msg = audio_io.remove_audio_file(f_id, current_user["user_id"])
            messagebox.showinfo("Result", msg)
            view_library()

    btn_play = tk.Button(actions, text="▶ Play Selected", command=on_play)
    style_button(btn_play, bg=COLOR_SUCCESS, hover="#059669")
    btn_play.pack(side="left", padx=(0, 8))

    btn_edit = tk.Button(actions, text="✂️ Edit in Lab", command=on_open_in_lab)
    style_button(btn_edit, bg=COLOR_ACCENT, hover=COLOR_ACCENT_HOVER)
    btn_edit.pack(side="left", padx=(0, 8))

    btn_del = tk.Button(actions, text="🗑 Remove", command=on_delete)
    style_button(btn_del, bg=COLOR_PANEL, hover=COLOR_DANGER)
    btn_del.pack(side="left")

# -----------------------------------------------------------------------------
# VIEW 5: PROJECTS & MIXER
# -----------------------------------------------------------------------------
def view_projects():
    clear_container(content_frame)

    header = tk.Frame(content_frame, bg=COLOR_BG)
    header.pack(fill="x", pady=(0, 15))
    tk.Label(header, text="Studio Projects", font=("Segoe UI", 16, "bold"), bg=COLOR_BG, fg=COLOR_TEXT).pack(side="left")

    def create_project_popup():
        pop = tk.Toplevel(root)
        pop.title("New Project")
        pop.geometry("320x240")
        pop.config(bg=COLOR_PANEL)

        tk.Label(pop, text="Project Name", bg=COLOR_PANEL, fg=COLOR_TEXT).pack(anchor="w", padx=20, pady=(15, 4))
        name_entry = tk.Entry(pop, bg=COLOR_SIDEBAR, fg=COLOR_TEXT, relief="flat", bd=5)
        name_entry.pack(fill="x", padx=20)

        tk.Label(pop, text="Tempo (BPM)", bg=COLOR_PANEL, fg=COLOR_TEXT).pack(anchor="w", padx=20, pady=(10, 4))
        bpm_entry = tk.Entry(pop, bg=COLOR_SIDEBAR, fg=COLOR_TEXT, relief="flat", bd=5)
        bpm_entry.insert(0, "120")
        bpm_entry.pack(fill="x", padx=20)

        def save_proj():
            try:
                bpm = int(bpm_entry.get().strip())
                _, msg = projects.create_project(current_user["user_id"], name_entry.get().strip(), bpm)
                messagebox.showinfo("Project", msg)
                pop.destroy()
                view_projects()
            except ValueError:
                messagebox.showerror("Error", "BPM must be a number.")

        btn = tk.Button(pop, text="Create", command=save_proj)
        style_button(btn, bg=COLOR_ACCENT, hover=COLOR_ACCENT_HOVER)
        btn.pack(pady=20, fill="x", padx=20)

    btn_new = tk.Button(header, text="+ New Project", command=create_project_popup)
    style_button(btn_new, bg=COLOR_ACCENT, hover=COLOR_ACCENT_HOVER)
    btn_new.pack(side="right")

    projs = projects.list_projects(current_user["user_id"])
    if not projs:
        tk.Label(content_frame, text="No projects found. Create one to begin mixing.", bg=COLOR_BG, fg=COLOR_MUTED).pack(pady=40)
        return

    proj_list_frame = tk.Frame(content_frame, bg=COLOR_BG)
    proj_list_frame.pack(fill="both", expand=True)

    for p in projs:
        card = tk.Frame(proj_list_frame, bg=COLOR_PANEL, padx=15, pady=12, highlightbackground=COLOR_BORDER, highlightthickness=1)
        card.pack(fill="x", pady=5)
        tk.Label(card, text=p["name"], font=("Segoe UI", 11, "bold"), bg=COLOR_PANEL, fg=COLOR_TEXT).pack(side="left")
        tk.Label(card, text=f"{p['bpm']} BPM  |  Modified: {p['modified_at']}", font=("Segoe UI", 9), bg=COLOR_PANEL, fg=COLOR_MUTED).pack(side="left", padx=15)

        btn_open = tk.Button(card, text="Open Mixer", command=lambda p_dict=p: open_mixer_view(p_dict))
        style_button(btn_open, bg=COLOR_ACCENT, hover=COLOR_ACCENT_HOVER)
        btn_open.pack(side="right", padx=5)

def open_mixer_view(proj):
    clear_container(content_frame)

    header = tk.Frame(content_frame, bg=COLOR_BG)
    header.pack(fill="x", pady=(0, 15))
    tk.Label(header, text=f"Mixer: {proj['name']} ({proj['bpm']} BPM)", font=("Segoe UI", 16, "bold"), bg=COLOR_BG, fg=COLOR_TEXT).pack(side="left")

    def on_export():
        path, msg = render.export_project(proj["project_id"], current_user["user_id"])
        messagebox.showinfo("Export Result", msg)

    def on_preview():
        run_in_background(render.preview_project, proj["project_id"], current_user["user_id"])

    btn_back = tk.Button(header, text="← Back", command=view_projects)
    style_button(btn_back, bg=COLOR_SIDEBAR, hover=COLOR_BORDER)
    btn_back.pack(side="right", padx=5)

    btn_exp = tk.Button(header, text="Render WAV", command=on_export)
    style_button(btn_exp, bg=COLOR_SUCCESS, hover="#059669")
    btn_exp.pack(side="right", padx=5)

    btn_prev = tk.Button(header, text="▶ Play Mix", command=on_preview)
    style_button(btn_prev, bg=COLOR_ACCENT, hover=COLOR_ACCENT_HOVER)
    btn_prev.pack(side="right", padx=5)

    tracks = projects.list_tracks(proj["project_id"])
    tracks_container = tk.Frame(content_frame, bg=COLOR_BG)
    tracks_container.pack(fill="both", expand=True)

    if not tracks:
        tk.Label(tracks_container, text="No tracks added to this project yet.", bg=COLOR_BG, fg=COLOR_MUTED).pack(pady=20)
        return

    for t in tracks:
        t_id = t["track_id"]
        strip = tk.Frame(tracks_container, bg=COLOR_PANEL, padx=12, pady=10, highlightbackground=COLOR_BORDER, highlightthickness=1)
        strip.pack(fill="x", pady=4)

        tk.Label(strip, text=f"#{t_id} {t['track_name']}", font=("Segoe UI", 10, "bold"), bg=COLOR_PANEL, fg=COLOR_TEXT, width=16, anchor="w").pack(side="left")
        tk.Label(strip, text=f"[{t['track_type']}]", font=("Segoe UI", 8), bg=COLOR_PANEL, fg=COLOR_MUTED, width=10).pack(side="left")

        tk.Label(strip, text="Vol", font=("Segoe UI", 8), bg=COLOR_PANEL, fg=COLOR_MUTED).pack(side="left", padx=(10, 2))
        vol_scale = tk.Scale(strip, from_=0.0, to=2.0, resolution=0.05, orient="horizontal",
                             bg=COLOR_PANEL, fg=COLOR_TEXT, highlightthickness=0, bd=0, length=100)
        vol_scale.set(float(t["volume"]))
        vol_scale.pack(side="left")
        vol_scale.bind("<ButtonRelease-1>", lambda e, tid=t_id, sc=vol_scale: projects.set_track_volume(tid, sc.get()))

        mute_color = COLOR_DANGER if t["is_muted"] else COLOR_SIDEBAR
        btn_mute = tk.Button(strip, text="M", width=3, command=lambda tid=t_id: (projects.toggle_mute(tid), open_mixer_view(proj)))
        style_button(btn_mute, bg=mute_color, hover=COLOR_BORDER)
        btn_mute.pack(side="left", padx=5)

        solo_color = COLOR_SUCCESS if t["is_solo"] else COLOR_SIDEBAR
        btn_solo = tk.Button(strip, text="S", width=3, command=lambda tid=t_id: (projects.toggle_solo(tid), open_mixer_view(proj)))
        style_button(btn_solo, bg=solo_color, hover=COLOR_BORDER)
        btn_solo.pack(side="left", padx=2)

# -----------------------------------------------------------------------------
# APPLICATION ENTRY POINT
# -----------------------------------------------------------------------------
def start_app():
    global root
    root = tk.Tk()
    root.title("Soundpad Studio")
    root.geometry("1060x720")
    root.minsize(920, 600)
    root.config(bg=COLOR_BG)

    setup_modern_theme()
    show_login_screen()

    def on_close():
        stop_all_audio()
        close_connection()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()

if __name__ == "__main__":
    start_app()