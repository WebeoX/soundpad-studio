"""
projects.py - Projects, tracks, clips and clip effects stored in MySQL.
Procedural, no classes. Every function returns plain values, dicts or
(success, message) tuples so the menu / GUI can show the result.
"""
from db import execute, fetch_one, fetch_all


# ------------------------------------------------------------ small helpers
def _touch(project_id):
    """Update the project's modified_at time."""
    execute("UPDATE projects SET modified_at = NOW() WHERE project_id = %s",
            (project_id,))


def _project_of_track(track_id):
    row = fetch_one("SELECT project_id FROM tracks WHERE track_id = %s", (track_id,))
    return row["project_id"] if row else None


def _project_of_clip(clip_id):
    row = fetch_one(
        """SELECT t.project_id FROM clips c
           JOIN tracks t ON c.track_id = t.track_id WHERE c.clip_id = %s""",
        (clip_id,))
    return row["project_id"] if row else None


def owns_project(project_id, user_id):
    return fetch_one(
        "SELECT 1 AS ok FROM projects WHERE project_id = %s AND user_id = %s",
        (project_id, user_id)) is not None


# ----------------------------------------------------------------- projects
def create_project(user_id, name, bpm=120, sample_rate=44100):
    """Returns (project_id, message)."""
    name = name.strip()
    if not name:
        return None, "Project name cannot be empty."
    if not 20 <= bpm <= 300:
        return None, "BPM must be between 20 and 300."
    if sample_rate not in (8000, 11025, 22050, 44100, 48000):
        return None, "Sample rate must be 8000, 11025, 22050, 44100 or 48000."
    pid = execute(
        "INSERT INTO projects (user_id, name, bpm, sample_rate) VALUES (%s,%s,%s,%s)",
        (user_id, name, bpm, sample_rate))
    return pid, "Project '%s' created." % name


def list_projects(user_id):
    return fetch_all(
        """SELECT project_id, name, bpm, sample_rate, created_at, modified_at
           FROM projects WHERE user_id = %s ORDER BY modified_at DESC""",
        (user_id,))


def get_project(project_id, user_id):
    return fetch_one(
        "SELECT * FROM projects WHERE project_id = %s AND user_id = %s",
        (project_id, user_id))


def rename_project(project_id, user_id, new_name):
    if not owns_project(project_id, user_id) or not new_name.strip():
        return False, "Cannot rename project."
    execute("UPDATE projects SET name = %s WHERE project_id = %s",
            (new_name.strip(), project_id))
    return True, "Renamed."


def set_bpm(project_id, user_id, bpm):
    if not owns_project(project_id, user_id):
        return False, "Project not found."
    if not 20 <= bpm <= 300:
        return False, "BPM must be between 20 and 300."
    execute("UPDATE projects SET bpm = %s WHERE project_id = %s", (bpm, project_id))
    return True, "BPM set to %d." % bpm


def delete_project(project_id, user_id):
    """Deletes the project and (via cascade) its tracks, clips, notes, patterns."""
    if not owns_project(project_id, user_id):
        return False, "Project not found."
    execute("DELETE FROM projects WHERE project_id = %s", (project_id,))
    return True, "Project deleted."


# ------------------------------------------------------------------- tracks
def add_track(project_id, user_id, name, track_type="audio"):
    """track_type: 'audio', 'beat' or 'instrument'. Returns (track_id, message)."""
    if not owns_project(project_id, user_id):
        return None, "Project not found."
    if track_type not in ("audio", "beat", "instrument"):
        return None, "Track type must be audio, beat or instrument."
    row = fetch_one(
        "SELECT COALESCE(MAX(track_order), 0) + 1 AS nxt FROM tracks WHERE project_id = %s",
        (project_id,))
    tid = execute(
        "INSERT INTO tracks (project_id, track_name, track_type, track_order) VALUES (%s,%s,%s,%s)",
        (project_id, name.strip() or "Track", track_type, row["nxt"]))
    _touch(project_id)
    return tid, "Track added."


def list_tracks(project_id):
    return fetch_all(
        "SELECT * FROM tracks WHERE project_id = %s ORDER BY track_order, track_id",
        (project_id,))


def set_track_volume(track_id, volume):
    if not 0 <= volume <= 4:
        return False, "Volume must be between 0 and 4 (1 = normal)."
    execute("UPDATE tracks SET volume = %s WHERE track_id = %s", (volume, track_id))
    _touch(_project_of_track(track_id))
    return True, "Volume set."


def set_track_pan(track_id, pan):
    if not -1 <= pan <= 1:
        return False, "Pan must be between -1 (left) and 1 (right)."
    execute("UPDATE tracks SET pan = %s WHERE track_id = %s", (pan, track_id))
    _touch(_project_of_track(track_id))
    return True, "Pan set."


def toggle_mute(track_id):
    execute("UPDATE tracks SET is_muted = NOT is_muted WHERE track_id = %s", (track_id,))
    _touch(_project_of_track(track_id))


def toggle_solo(track_id):
    execute("UPDATE tracks SET is_solo = NOT is_solo WHERE track_id = %s", (track_id,))
    _touch(_project_of_track(track_id))


def rename_track(track_id, new_name):
    execute("UPDATE tracks SET track_name = %s WHERE track_id = %s",
            (new_name.strip(), track_id))
    _touch(_project_of_track(track_id))


def delete_track(track_id):
    pid = _project_of_track(track_id)
    execute("DELETE FROM tracks WHERE track_id = %s", (track_id,))
    if pid:
        _touch(pid)


# -------------------------------------------------------------------- clips
def add_clip(track_id, user_id, file_id, start_time=0.0, trim_start=0.0,
             trim_end=None, volume=1.0, fade_in=0.0, fade_out=0.0):
    """Place an audio file on a track. Returns (clip_id, message)."""
    pid = _project_of_track(track_id)
    if pid is None or not owns_project(pid, user_id):
        return None, "Track not found."
    if fetch_one("SELECT 1 AS ok FROM audio_files WHERE file_id=%s AND user_id=%s",
                 (file_id, user_id)) is None:
        return None, "Audio file not found in your library."
    if start_time < 0 or trim_start < 0:
        return None, "Times cannot be negative."
    if trim_end is not None and trim_end <= trim_start:
        return None, "trim_end must be greater than trim_start."
    cid = execute(
        """INSERT INTO clips (track_id, file_id, start_time, trim_start, trim_end,
                              volume, fade_in, fade_out)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
        (track_id, file_id, start_time, trim_start, trim_end, volume, fade_in, fade_out))
    _touch(pid)
    return cid, "Clip added."


def list_clips(track_id):
    """Clips on a track, with the source file's name and path."""
    return fetch_all(
        """SELECT c.*, f.file_name, f.file_path
           FROM clips c JOIN audio_files f ON c.file_id = f.file_id
           WHERE c.track_id = %s ORDER BY c.start_time""",
        (track_id,))


def update_clip(clip_id, **fields):
    """Change any of: start_time, trim_start, trim_end, volume, fade_in, fade_out."""
    allowed = ("start_time", "trim_start", "trim_end", "volume", "fade_in", "fade_out")
    items = [(k, v) for k, v in fields.items() if k in allowed]
    if not items:
        return False, "Nothing to update."
    sets = ", ".join("%s = %%s" % k for k, _ in items)     # column names are whitelisted
    execute("UPDATE clips SET %s WHERE clip_id = %%s" % sets,
            tuple(v for _, v in items) + (clip_id,))
    _touch(_project_of_clip(clip_id))
    return True, "Clip updated."


def delete_clip(clip_id):
    pid = _project_of_clip(clip_id)
    execute("DELETE FROM clips WHERE clip_id = %s", (clip_id,))
    if pid:
        _touch(pid)


# ------------------------------------------------------------- clip effects
def list_effects():
    return fetch_all("SELECT effect_name, description FROM effects ORDER BY effect_id")


def add_clip_effect(clip_id, effect_name, param1=None, param2=None):
    """Attach an effect to a clip. Effects run in the order they were added.
    Params:  gain(factor) fade_in(sec) fade_out(sec) speed(factor)
             normalize(peak) echo(delay_sec, decay) lowpass(hz) highpass(hz)
             distortion(amount) reverse()"""
    eff = fetch_one("SELECT effect_id FROM effects WHERE effect_name = %s", (effect_name,))
    if eff is None:
        return False, "Unknown effect '%s'." % effect_name
    row = fetch_one(
        "SELECT COALESCE(MAX(apply_order), 0) + 1 AS nxt FROM clip_effects WHERE clip_id = %s",
        (clip_id,))
    execute(
        """INSERT INTO clip_effects (clip_id, effect_id, param1, param2, apply_order)
           VALUES (%s,%s,%s,%s,%s)""",
        (clip_id, eff["effect_id"], param1, param2, row["nxt"]))
    _touch(_project_of_clip(clip_id))
    return True, "Effect '%s' added." % effect_name


def list_clip_effects(clip_id):
    return fetch_all(
        """SELECT ce.ce_id, e.effect_name, ce.param1, ce.param2, ce.apply_order
           FROM clip_effects ce JOIN effects e ON ce.effect_id = e.effect_id
           WHERE ce.clip_id = %s ORDER BY ce.apply_order, ce.ce_id""",
        (clip_id,))


def remove_clip_effect(ce_id):
    execute("DELETE FROM clip_effects WHERE ce_id = %s", (ce_id,))


# ------------------------------------------------------------------ display
def print_project(project_id, user_id):
    """Print a text view of a project's tracks and clips."""
    p = get_project(project_id, user_id)
    if p is None:
        print("Project not found.")
        return
    print("\nProject: %s   BPM: %s   Rate: %s Hz" % (p["name"], p["bpm"], p["sample_rate"]))
    for t in list_tracks(project_id):
        flags = ("M" if t["is_muted"] else "-") + ("S" if t["is_solo"] else "-")
        print("  [%s] #%d %-18s %-10s vol %.2f pan %+.2f" % (
            flags, t["track_id"], t["track_name"], t["track_type"],
            float(t["volume"]), float(t["pan"])))
        for c in list_clips(t["track_id"]):
            fx = ", ".join(e["effect_name"] for e in list_clip_effects(c["clip_id"]))
            print("        clip #%d %-22s at %.2fs%s" % (
                c["clip_id"], c["file_name"][:22], float(c["start_time"]),
                ("  fx: " + fx) if fx else ""))