"""
gui_data.py - Extra SQL used only by the GUI: bulk loaders for the timeline,
note updates, a change-detector for the render cache, and the statistics
dashboard queries (JOIN / GROUP BY / HAVING).
"""
import hashlib

from db import execute, fetch_one, fetch_all


# --------------------------------------------------------------- loaders
def project_clips(project_id):
    """Every audio clip in a project with its file name, path and duration."""
    return fetch_all(
        """SELECT c.*, f.file_name, f.file_path, f.duration_sec
           FROM clips c
           JOIN audio_files f ON c.file_id = f.file_id
           JOIN tracks t ON c.track_id = t.track_id
           WHERE t.project_id = %s
           ORDER BY c.start_time""", (project_id,))


def project_clip_effects(project_id):
    """Dict clip_id -> list of effect rows, in the order they are applied."""
    rows = fetch_all(
        """SELECT ce.ce_id, ce.clip_id, e.effect_name, ce.param1, ce.param2, ce.apply_order
           FROM clip_effects ce
           JOIN effects e ON ce.effect_id = e.effect_id
           JOIN clips c ON ce.clip_id = c.clip_id
           JOIN tracks t ON c.track_id = t.track_id
           WHERE t.project_id = %s
           ORDER BY ce.apply_order, ce.ce_id""", (project_id,))
    out = {}
    for r in rows:
        out.setdefault(r["clip_id"], []).append(r)
    return out


def project_counts(project_id):
    """(number of tracks, number of audio clips) for a project card."""
    t = fetch_one("SELECT COUNT(*) AS n FROM tracks WHERE project_id = %s", (project_id,))
    c = fetch_one(
        """SELECT COUNT(*) AS n FROM clips c JOIN tracks t ON c.track_id = t.track_id
           WHERE t.project_id = %s""", (project_id,))
    return int(t["n"]), int(c["n"])


def clip_length(clip, fx_list, file_duration):
    """Length in seconds of a clip on the timeline (trim, speed and echo tail)."""
    start = float(clip["trim_start"] or 0)
    end = float(clip["trim_end"]) if clip["trim_end"] is not None else file_duration
    if file_duration:
        end = min(end, file_duration)
    length = max(0.05, end - start)
    for fx in fx_list:
        p1 = float(fx["param1"]) if fx["param1"] is not None else None
        if fx["effect_name"] == "speed" and p1:
            length /= p1
        elif fx["effect_name"] == "echo":
            length += (p1 or 0.3) * 3
    return length


def speed_factor(fx_list):
    """Total playback-speed factor of a clip's effects (1.0 if none)."""
    factor = 1.0
    for fx in fx_list:
        if fx["effect_name"] == "speed" and fx["param1"]:
            factor *= float(fx["param1"])
    return factor


def beat_blocks(track_id, bpm):
    """Patterns of a beat track laid end to end: list of dicts with start,
    loop length, repeats and the hits (sample_id, step) for drawing."""
    blocks, t = [], 0.0
    patterns = fetch_all("SELECT * FROM beat_patterns WHERE track_id = %s ORDER BY pattern_id",
                         (track_id,))
    for p in patterns:
        loop = p["total_steps"] * 60.0 / bpm / 4
        repeats = int(p.get("repeats") or 4)
        hits = fetch_all("SELECT sample_id, step_no FROM pattern_steps WHERE pattern_id = %s",
                         (p["pattern_id"],))
        blocks.append({"pattern_id": p["pattern_id"], "name": p["pattern_name"],
                       "start": t, "loop": loop, "repeats": repeats,
                       "length": loop * repeats, "steps": p["total_steps"],
                       "hits": [(h["sample_id"], h["step_no"]) for h in hits]})
        t += loop * repeats
    return blocks


def update_note(note_id, midi, start_beat, length_beats, velocity=None):
    if velocity is None:
        execute("UPDATE notes SET midi_number=%s, start_beat=%s, length_beats=%s WHERE note_id=%s",
                (int(midi), round(start_beat, 3), round(length_beats, 3), note_id))
    else:
        execute("UPDATE notes SET midi_number=%s, start_beat=%s, length_beats=%s, velocity=%s "
                "WHERE note_id=%s",
                (int(midi), round(start_beat, 3), round(length_beats, 3), int(velocity), note_id))


# ------------------------------------------------- change detection (cache)
def project_fingerprint(project_id):
    """A hash of everything that affects the rendered sound. If it is unchanged,
    the previously rendered mix can be reused instead of rendering again."""
    j_tracks = "JOIN tracks t ON %s.track_id = t.track_id WHERE t.project_id = %%s ORDER BY 1"
    parts = [
        repr(fetch_one("SELECT bpm, sample_rate FROM projects WHERE project_id = %s", (project_id,))),
        repr(fetch_all("SELECT track_id, track_type, volume, pan, is_muted, is_solo "
                       "FROM tracks WHERE project_id = %s ORDER BY track_id", (project_id,))),
        repr(fetch_all("SELECT c.* FROM clips c " + j_tracks % "c", (project_id,))),
        repr(fetch_all("""SELECT ce.* FROM clip_effects ce
                          JOIN clips c ON ce.clip_id = c.clip_id
                          JOIN tracks t ON c.track_id = t.track_id
                          WHERE t.project_id = %s ORDER BY ce.ce_id""", (project_id,))),
        repr(fetch_all("SELECT bp.* FROM beat_patterns bp " + j_tracks % "bp", (project_id,))),
        repr(fetch_all("""SELECT ps.* FROM pattern_steps ps
                          JOIN beat_patterns bp ON ps.pattern_id = bp.pattern_id
                          JOIN tracks t ON bp.track_id = t.track_id
                          WHERE t.project_id = %s ORDER BY ps.step_id""", (project_id,))),
        repr(fetch_all("SELECT n.* FROM notes n " + j_tracks % "n", (project_id,))),
    ]
    return hashlib.md5("|".join(parts).encode("utf-8")).hexdigest()


# --------------------------------------------------------------- statistics
TILES = [
    ("Projects", "SELECT COUNT(*) AS v FROM projects WHERE user_id = %s", ""),
    ("Tracks", """SELECT COUNT(*) AS v FROM tracks t
                  JOIN projects p ON t.project_id = p.project_id
                  WHERE p.user_id = %s""", ""),
    ("Audio clips", """SELECT COUNT(*) AS v FROM clips c
                       JOIN tracks t ON c.track_id = t.track_id
                       JOIN projects p ON t.project_id = p.project_id
                       WHERE p.user_id = %s""", ""),
    ("Notes", """SELECT COUNT(*) AS v FROM notes n
                 JOIN tracks t ON n.track_id = t.track_id
                 JOIN projects p ON t.project_id = p.project_id
                 WHERE p.user_id = %s""", ""),
    ("Drum hits", """SELECT COUNT(*) AS v FROM pattern_steps ps
                     JOIN beat_patterns bp ON ps.pattern_id = bp.pattern_id
                     JOIN tracks t ON bp.track_id = t.track_id
                     JOIN projects p ON t.project_id = p.project_id
                     WHERE p.user_id = %s""", ""),
    ("Library files", "SELECT COUNT(*) AS v FROM audio_files WHERE user_id = %s", ""),
    ("Library minutes", "SELECT COALESCE(SUM(duration_sec), 0) / 60 AS v FROM audio_files "
                        "WHERE user_id = %s", "min"),
    ("Exports", """SELECT COUNT(*) AS v FROM exports e
                   JOIN projects p ON e.project_id = p.project_id
                   WHERE p.user_id = %s""", ""),
]

PANELS = [
    ("Tracks by type",
     """SELECT t.track_type AS label, COUNT(*) AS total
FROM tracks t
JOIN projects p ON t.project_id = p.project_id
WHERE p.user_id = %s
GROUP BY t.track_type
ORDER BY total DESC""", "#00e5ff"),
    ("Most-used effects",
     """SELECT e.effect_name AS label, COUNT(*) AS total
FROM clip_effects ce
JOIN effects e ON ce.effect_id = e.effect_id
JOIN clips c ON ce.clip_id = c.clip_id
JOIN tracks t ON c.track_id = t.track_id
JOIN projects p ON t.project_id = p.project_id
WHERE p.user_id = %s
GROUP BY e.effect_name
ORDER BY total DESC
LIMIT 8""", "#ff2e97"),
    ("Drum hits by sound",
     """SELECT d.name AS label, COUNT(*) AS total
FROM pattern_steps ps
JOIN drum_samples d ON ps.sample_id = d.sample_id
JOIN beat_patterns bp ON ps.pattern_id = bp.pattern_id
JOIN tracks t ON bp.track_id = t.track_id
JOIN projects p ON t.project_id = p.project_id
WHERE p.user_id = %s
GROUP BY d.name
ORDER BY total DESC""", "#b6ff3b"),
    ("Notes per instrument",
     """SELECT i.name AS label, COUNT(*) AS total
FROM notes n
JOIN instruments i ON n.instrument_id = i.instrument_id
JOIN tracks t ON n.track_id = t.track_id
JOIN projects p ON t.project_id = p.project_id
WHERE p.user_id = %s
GROUP BY i.name
ORDER BY total DESC
LIMIT 8""", "#ffb020"),
    ("Busiest projects (HAVING 1+ track)",
     """SELECT p.name AS label, COUNT(t.track_id) AS total
FROM projects p
LEFT JOIN tracks t ON t.project_id = p.project_id
WHERE p.user_id = %s
GROUP BY p.project_id, p.name
HAVING COUNT(t.track_id) >= 1
ORDER BY total DESC
LIMIT 6""", "#9b6bff"),
    ("Longest library files (seconds)",
     """SELECT file_name AS label, duration_sec AS total
FROM audio_files
WHERE user_id = %s
ORDER BY duration_sec DESC
LIMIT 6""", "#2ee6a6"),
]


def tile_value(sql, user_id):
    row = fetch_one(sql, (user_id,))
    return float(row["v"] or 0) if row else 0.0


def panel_rows(sql, user_id):
    """Run a dashboard query; returns [(label, number), ...]."""
    return [(str(r["label"]), float(r["total"] or 0)) for r in fetch_all(sql, (user_id,))]
