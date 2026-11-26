"""
gui_play.py - Playback, playhead animation, background tasks, waveform
peaks, the cached project mix and WAV export for the GUI.
"""
import os
import tempfile
import threading
import time
import traceback
from tkinter import filedialog

import editing as ed
import render
from audio_io import load_wav, save_wav
from db import execute
import gui_theme as T
from gui_data import project_fingerprint
from gui_state import S, uid, set_status, current_project

try:
    import winsound            # Windows only
except ImportError:
    winsound = None

_play = {"token": 0, "active": False, "slot": 0}
_peaks = {}


# ---------------------------------------------------------------- playback
def can_play():
    return winsound is not None


def is_playing():
    return _play["active"]


def stop():
    """Stop any sound and cancel the playhead animation."""
    _play["token"] += 1
    _play["active"] = False
    if winsound is not None:
        try:
            winsound.PlaySound(None, winsound.SND_PURGE)
        except RuntimeError:
            pass


def play_audio(audio, loop=False):
    """Play an audio dict in the background. Returns its length in seconds,
    or None if playback is not available."""
    if winsound is None:
        T.show_message("Playback unavailable",
                       "Live playback uses the Windows sound system.\n"
                       "You can still export WAV files and play them anywhere.", "warn")
        return None
    stop()
    _play["slot"] ^= 1
    path = os.path.join(tempfile.gettempdir(), "soundpad_gui_%d.wav" % _play["slot"])
    save_wav(path, ed.limit(audio))
    flags = winsound.SND_FILENAME | winsound.SND_ASYNC
    if loop:
        flags |= winsound.SND_LOOP
    winsound.PlaySound(path, flags)
    _play["active"] = True
    return ed.duration(audio)


def play_file(path):
    """Play a WAV file straight from disk. Returns True if it started."""
    if winsound is None:
        T.show_message("Playback unavailable",
                       "Live playback uses the Windows sound system.", "warn")
        return False
    stop()
    winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
    _play["active"] = True
    return True


def start_playhead(duration, on_tick, on_end=None, loop=False):
    """Call on_tick(seconds_since_start) about 30 times a second until the
    sound ends (or forever, wrapping round, if loop is True)."""
    token = _play["token"]
    t0 = time.perf_counter()
    root = S["root"]

    def tick():
        if _play["token"] != token:
            return
        el = time.perf_counter() - t0
        if not loop and el >= duration:
            _play["active"] = False
            on_tick(duration)
            if on_end:
                on_end()
            return
        on_tick(el % duration if (loop and duration > 0) else el)
        root.after(30, tick)
    tick()


def set_time(seconds):
    if S["time_var"] is not None:
        S["time_var"].set(T.fmt_time(seconds))


# -------------------------------------------------------- background tasks
def run_task(text, work, done):
    """Run work() in a thread behind a busy overlay, then call done(result)
    on the main thread. Only plain Python/MySQL work may run in the thread."""
    box = T.busy_start(text)
    result = {}

    def target():
        try:
            result["v"] = work()
        except Exception:                       # shown to the user below
            result["err"] = traceback.format_exc()

    th = threading.Thread(target=target, daemon=True)
    th.start()

    def poll():
        if th.is_alive():
            S["root"].after(50, poll)
            return
        T.busy_stop(box)
        if "err" in result:
            print(result["err"])
            T.show_message("Something went wrong", result["err"][-700:], "error")
            return
        done(result.get("v"))
    S["root"].after(50, poll)


# ---------------------------------------------------------- waveform peaks
def peaks_of(audio, n):
    """List of n (lowest, highest) sample pairs across the audio."""
    chans = audio["channels"]
    total = len(chans[0])
    if total == 0:
        return [(0.0, 0.0)] * n
    out = []
    for i in range(n):
        s = i * total // n
        e = max(s + 1, (i + 1) * total // n)
        lo = min(min(c[s:e]) for c in chans)
        hi = max(max(c[s:e]) for c in chans)
        out.append((lo, hi))
    return out


def file_peaks(path, n=900):
    """(duration_sec, peaks) for a WAV file, cached after the first read."""
    if path not in _peaks:
        audio = load_wav(path)
        _peaks[path] = (ed.duration(audio), peaks_of(audio, n))
    return _peaks[path]


def cached_peaks(path):
    return _peaks.get(path)


def ensure_peaks(paths, done):
    """Make sure the peaks of every file are cached, then call done()."""
    missing = [p for p in dict.fromkeys(paths) if p not in _peaks and os.path.isfile(p)]
    if not missing:
        done()
        return

    def work():
        for p in missing:
            try:
                file_peaks(p)
            except Exception:                   # unreadable file: draw it flat
                _peaks[p] = (0.0, [(0.0, 0.0)] * 900)
    run_task("Reading waveforms...", work, lambda _r: done())


# ------------------------------------------------------- project mix cache
def get_project_mix(done, force=False):
    """Render the open project (or reuse the cached render if nothing changed)
    and call done(audio)."""
    pid = S["project_id"]
    if pid is None:
        T.show_message("No project", "Open or create a project first.", "info")
        return
    user = uid()
    key = (project_fingerprint(pid), bool(S["auto_norm"]))
    cache = S.get("mix_cache")
    if cache and cache[0] == key and not force:
        done(cache[1])
        return

    def work():
        return render.render_project(pid, user, bool(S["auto_norm"]), False)

    def finished(audio):
        if audio is None:
            T.show_message("Nothing to play",
                           "This project has no audible content yet.\n"
                           "Add an audio clip, a beat pattern or some notes.", "info")
            return
        S["mix_cache"] = (key, audio)
        done(audio)
    run_task("Rendering mix...", work, finished)


def play_project(start_sec=0.0, on_tick=None, on_end=None):
    """Render (if needed) and play the project from start_sec."""
    def go(audio):
        seg = ed.trim(audio, start_sec, None) if start_sec > 0 else audio
        if ed.length(seg) == 0:
            return
        dur = play_audio(seg)
        if dur is None:
            return

        def tick(t):
            set_time(start_sec + t)
            if on_tick:
                on_tick(start_sec + t)
        start_playhead(dur, tick, on_end)
    get_project_mix(go)


def export_project_wav():
    """Ask where to save, render the mix and write a WAV file."""
    proj = current_project()
    if proj is None:
        T.show_message("No project", "Open or create a project first.", "info")
        return
    os.makedirs(render.EXPORT_DIR, exist_ok=True)
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in proj["name"]) or "mix"
    path = filedialog.asksaveasfilename(
        title="Export mix as WAV", defaultextension=".wav", initialdir=render.EXPORT_DIR,
        initialfile=safe + ".wav", filetypes=[("WAV audio", "*.wav")])
    if not path:
        return

    def go(audio):
        def write():
            save_wav(path, audio)
            execute("INSERT INTO exports (project_id, output_path) VALUES (%s, %s)",
                    (proj["project_id"], path))

        def finished(_r):
            set_status("Exported %.1f s to %s" % (ed.duration(audio), path))
            T.show_message("Export complete", "Saved %.1f seconds of audio to:\n%s"
                           % (ed.duration(audio), path), "info")
        run_task("Writing WAV file...", write, finished)
    get_project_mix(go)
