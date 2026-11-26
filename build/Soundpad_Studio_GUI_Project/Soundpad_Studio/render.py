"""
render.py - Turns a project stored in MySQL into one mixed WAV file.

Flow:  project -> tracks -> clips -> (trim, volume, fades, effects)
       -> track bus -> (track volume, pan) -> master mix -> normalize -> WAV
"""
import os
import re

from db import execute, fetch_one, fetch_all
from audio_io import load_wav, save_wav, play_audio
from projects import get_project, list_tracks, list_clips, list_clip_effects
import editing as ed

EXPORT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "exports")


# ------------------------------------------------------------------ effects
def apply_effect(audio, name, p1, p2):
    """Apply one named effect. p1/p2 are floats or None."""
    if name == "gain":
        return ed.change_volume(audio, p1 if p1 is not None else 1.0)
    if name == "fade_in":
        return ed.fade_in(audio, p1 if p1 is not None else 1.0)
    if name == "fade_out":
        return ed.fade_out(audio, p1 if p1 is not None else 1.0)
    if name == "reverse":
        return ed.reverse(audio)
    if name == "speed":
        return ed.change_speed(audio, p1 if p1 else 1.0)
    if name == "normalize":
        return ed.normalize(audio, p1 if p1 else 0.95)
    if name == "echo":
        return ed.add_echo(audio, p1 if p1 else 0.3, p2 if p2 is not None else 0.5, 3)
    if name == "lowpass":
        return ed.lowpass(audio, p1 if p1 else 5000)
    if name == "highpass":
        return ed.highpass(audio, p1 if p1 else 200)
    if name == "distortion":
        return ed.distortion(audio, p1 if p1 else 5.0)
    return audio     # unknown effect: leave audio unchanged


def _num(value):
    """MySQL DECIMAL -> float (None stays None)."""
    return None if value is None else float(value)


# -------------------------------------------------------------------- clips
def render_clip(clip, cache):
    """Load a clip's source file and apply trim, volume, fades and effects.
    `cache` is a dict path -> audio so each file is read from disk only once."""
    path = clip["file_path"]
    if path not in cache:
        cache[path] = load_wav(path)
    audio = cache[path]                      # never modified: all edits copy

    t_start = _num(clip["trim_start"]) or 0.0
    t_end = _num(clip["trim_end"])
    if t_start > 0 or t_end is not None:
        audio = ed.trim(audio, t_start, t_end)

    vol = _num(clip["volume"])
    if vol is not None and vol != 1.0:
        audio = ed.change_volume(audio, vol)
    if _num(clip["fade_in"]):
        audio = ed.fade_in(audio, _num(clip["fade_in"]))
    if _num(clip["fade_out"]):
        audio = ed.fade_out(audio, _num(clip["fade_out"]))

    for fx in list_clip_effects(clip["clip_id"]):
        audio = apply_effect(audio, fx["effect_name"], _num(fx["param1"]), _num(fx["param2"]))
    return audio


# ------------------------------------------------------------------- tracks
def render_track(track, project, cache):
    """Return the track's audio (before track volume/pan), or None if empty."""
    rate = project["sample_rate"]
    ttype = track["track_type"]

    if ttype == "audio":
        bus = ed.make_audio(rate, 2, 0)
        clips = list_clips(track["track_id"])
        if not clips:
            return None
        for clip in clips:
            if not os.path.isfile(clip["file_path"]):
                print("    ! missing file, skipped: %s" % clip["file_path"])
                continue
            audio = render_clip(clip, cache)
            ed.mix_into(bus, audio, float(clip["start_time"]))
        return bus

    # Beat and instrument tracks are rendered by modules we add later.
    if ttype == "beat":
        try:
            import beats
            return beats.render_beat_track(track["track_id"], project["bpm"], rate)
        except ImportError:
            print("    (beats.py not added yet - beat track skipped)")
            return None
    if ttype == "instrument":
        try:
            import synth
            return synth.render_instrument_track(track["track_id"], project["bpm"], rate)
        except ImportError:
            print("    (synth.py not added yet - instrument track skipped)")
            return None
    return None


# ------------------------------------------------------------------ project
def render_project(project_id, user_id, auto_normalize=True, verbose=True):
    """Mix the whole project. Returns the master audio dict, or None."""
    project = get_project(project_id, user_id)
    if project is None:
        print("Project not found.")
        return None

    tracks = list_tracks(project_id)
    any_solo = any(t["is_solo"] for t in tracks)
    master = ed.make_audio(project["sample_rate"], 2, 0)
    cache = {}

    for t in tracks:
        if t["is_muted"] or (any_solo and not t["is_solo"]):
            if verbose:
                print("  skipping track '%s' (muted/not solo)" % t["track_name"])
            continue
        if verbose:
            print("  rendering track '%s' ..." % t["track_name"])
        bus = render_track(t, project, cache)
        if bus is None:
            continue
        ed.mix_into(master, bus, 0.0, float(t["volume"]), float(t["pan"]))

    if ed.length(master) == 0:
        print("Nothing to render (no audible clips).")
        return None

    peak = ed.get_peak(master)
    if auto_normalize and peak > 0.98:
        master = ed.normalize(master, 0.95)
        if verbose:
            print("  mix peaked at %.2f dB, normalized to avoid clipping" % ed.to_db(peak))
    return ed.limit(master)


def export_project(project_id, user_id, filename=None):
    """Render and save to exports/<name>.wav and log it. Returns (path, message)."""
    project = get_project(project_id, user_id)
    if project is None:
        return None, "Project not found."
    master = render_project(project_id, user_id)
    if master is None:
        return None, "Nothing to export."

    os.makedirs(EXPORT_DIR, exist_ok=True)
    if not filename:
        safe = re.sub(r"[^A-Za-z0-9_-]+", "_", project["name"]).strip("_") or "project"
        filename = safe + ".wav"
    path = os.path.join(EXPORT_DIR, filename)
    save_wav(path, master)
    execute("INSERT INTO exports (project_id, output_path) VALUES (%s, %s)",
            (project_id, path))
    return path, "Exported %.1f seconds to %s" % (ed.duration(master), path)


def preview_project(project_id, user_id):
    """Render and play the project (Windows)."""
    master = render_project(project_id, user_id)
    if master is not None:
        play_audio(master)


def list_exports(project_id):
    return fetch_all(
        "SELECT export_id, output_path, exported_on FROM exports "
        "WHERE project_id = %s ORDER BY exported_on DESC", (project_id,))