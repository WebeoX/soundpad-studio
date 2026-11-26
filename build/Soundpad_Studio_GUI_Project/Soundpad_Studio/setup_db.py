"""
setup_db.py - Run ONCE to create the audio_studio database, all tables,
and starter data (effects, drum sounds, instruments).
Safe to re-run: uses IF NOT EXISTS and skips existing seed rows.
"""
import mysql.connector
from db import DB_CONFIG

TABLES = [
    """CREATE TABLE IF NOT EXISTS users (
        user_id       INT AUTO_INCREMENT PRIMARY KEY,
        username      VARCHAR(50) UNIQUE NOT NULL,
        password_hash VARCHAR(255) NOT NULL,
        created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS projects (
        project_id   INT AUTO_INCREMENT PRIMARY KEY,
        user_id      INT NOT NULL,
        name         VARCHAR(100) NOT NULL,
        bpm          INT DEFAULT 120,
        sample_rate  INT DEFAULT 44100,
        created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
        modified_at  DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
    )""",
    """CREATE TABLE IF NOT EXISTS audio_files (
        file_id      INT AUTO_INCREMENT PRIMARY KEY,
        user_id      INT NOT NULL,
        file_name    VARCHAR(150) NOT NULL,
        file_path    VARCHAR(255) NOT NULL,
        duration_sec DECIMAL(8,3),
        sample_rate  INT,
        channels     TINYINT,
        bit_depth    TINYINT,
        added_on     DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
    )""",
    """CREATE TABLE IF NOT EXISTS tracks (
        track_id    INT AUTO_INCREMENT PRIMARY KEY,
        project_id  INT NOT NULL,
        track_name  VARCHAR(60) NOT NULL,
        track_type  ENUM('audio','beat','instrument') NOT NULL,
        volume      DECIMAL(4,2) DEFAULT 1.00,
        pan         DECIMAL(3,2) DEFAULT 0.00,
        is_muted    BOOLEAN DEFAULT FALSE,
        is_solo     BOOLEAN DEFAULT FALSE,
        track_order INT DEFAULT 0,
        FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE CASCADE
    )""",
    """CREATE TABLE IF NOT EXISTS clips (
        clip_id      INT AUTO_INCREMENT PRIMARY KEY,
        track_id     INT NOT NULL,
        file_id      INT NOT NULL,
        start_time   DECIMAL(8,3) NOT NULL,
        trim_start   DECIMAL(8,3) DEFAULT 0,
        trim_end     DECIMAL(8,3) DEFAULT NULL,
        volume       DECIMAL(4,2) DEFAULT 1.00,
        fade_in      DECIMAL(5,2) DEFAULT 0,
        fade_out     DECIMAL(5,2) DEFAULT 0,
        FOREIGN KEY (track_id) REFERENCES tracks(track_id) ON DELETE CASCADE,
        FOREIGN KEY (file_id)  REFERENCES audio_files(file_id)
    )""",
    """CREATE TABLE IF NOT EXISTS effects (
        effect_id   INT AUTO_INCREMENT PRIMARY KEY,
        effect_name VARCHAR(40) UNIQUE NOT NULL,
        description VARCHAR(200)
    )""",
    """CREATE TABLE IF NOT EXISTS clip_effects (
        ce_id        INT AUTO_INCREMENT PRIMARY KEY,
        clip_id      INT NOT NULL,
        effect_id    INT NOT NULL,
        param1       DECIMAL(8,3),
        param2       DECIMAL(8,3),
        apply_order  INT DEFAULT 1,
        FOREIGN KEY (clip_id)   REFERENCES clips(clip_id) ON DELETE CASCADE,
        FOREIGN KEY (effect_id) REFERENCES effects(effect_id)
    )""",
    """CREATE TABLE IF NOT EXISTS drum_samples (
        sample_id  INT AUTO_INCREMENT PRIMARY KEY,
        name       VARCHAR(50) UNIQUE NOT NULL,
        category   ENUM('kick','snare','hihat','clap','tom','perc','other') NOT NULL,
        file_id    INT NULL,
        FOREIGN KEY (file_id) REFERENCES audio_files(file_id)
    )""",
    """CREATE TABLE IF NOT EXISTS beat_patterns (
        pattern_id   INT AUTO_INCREMENT PRIMARY KEY,
        track_id     INT NOT NULL,
        pattern_name VARCHAR(60),
        total_steps  INT DEFAULT 16,
        swing        DECIMAL(3,2) DEFAULT 0,
        repeats      INT DEFAULT 4,
        FOREIGN KEY (track_id) REFERENCES tracks(track_id) ON DELETE CASCADE
    )""",
    """CREATE TABLE IF NOT EXISTS pattern_steps (
        step_id    INT AUTO_INCREMENT PRIMARY KEY,
        pattern_id INT NOT NULL,
        sample_id  INT NOT NULL,
        step_no    INT NOT NULL,
        velocity   INT DEFAULT 100,
        FOREIGN KEY (pattern_id) REFERENCES beat_patterns(pattern_id) ON DELETE CASCADE,
        FOREIGN KEY (sample_id)  REFERENCES drum_samples(sample_id)
    )""",
    """CREATE TABLE IF NOT EXISTS instruments (
        instrument_id INT AUTO_INCREMENT PRIMARY KEY,
        name      VARCHAR(50) UNIQUE NOT NULL,
        waveform  ENUM('sine','square','sawtooth','triangle') NOT NULL,
        attack    DECIMAL(4,3) DEFAULT 0.010,
        decay     DECIMAL(4,3) DEFAULT 0.100,
        sustain   DECIMAL(3,2) DEFAULT 0.70,
        release_t DECIMAL(4,3) DEFAULT 0.200
    )""",
    """CREATE TABLE IF NOT EXISTS notes (
        note_id       INT AUTO_INCREMENT PRIMARY KEY,
        track_id      INT NOT NULL,
        instrument_id INT NOT NULL,
        midi_number   INT NOT NULL,
        start_beat    DECIMAL(7,3) NOT NULL,
        length_beats  DECIMAL(5,3) NOT NULL,
        velocity      INT DEFAULT 100,
        FOREIGN KEY (track_id)      REFERENCES tracks(track_id) ON DELETE CASCADE,
        FOREIGN KEY (instrument_id) REFERENCES instruments(instrument_id)
    )""",
    """CREATE TABLE IF NOT EXISTS exports (
        export_id   INT AUTO_INCREMENT PRIMARY KEY,
        project_id  INT NOT NULL,
        output_path VARCHAR(255) NOT NULL,
        exported_on DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE CASCADE
    )""",
]

EFFECTS = [
    ("gain", "Change volume"),
    ("fade_in", "Gradually raise volume at the start"),
    ("fade_out", "Gradually lower volume at the end"),
    ("reverse", "Play the audio backwards"),
    ("speed", "Change playback speed (and pitch)"),
    ("normalize", "Scale audio to a target peak level"),
    ("echo", "Repeating delayed copies"),
    ("lowpass", "Remove high frequencies"),
    ("highpass", "Remove low frequencies"),
    ("distortion", "Clip the signal for a gritty sound"),
]

DRUMS = [
    ("Kick", "kick"), ("Snare", "snare"), ("Closed Hi-Hat", "hihat"),
    ("Open Hi-Hat", "hihat"), ("Clap", "clap"), ("Low Tom", "tom"),
    ("High Tom", "tom"), ("Rimshot", "perc"),
]

# name, waveform, attack, decay, sustain, release
INSTRUMENTS = [
    ("Sine Pad", "sine", 0.100, 0.200, 0.80, 0.500),
    ("Square Lead", "square", 0.010, 0.100, 0.60, 0.150),
    ("Saw Bass", "sawtooth", 0.005, 0.150, 0.70, 0.100),
    ("Soft Triangle", "triangle", 0.020, 0.100, 0.75, 0.250),
]


def create_database():
    cfg = dict(DB_CONFIG)
    db_name = cfg.pop("database")
    conn = mysql.connector.connect(**cfg)
    cur = conn.cursor()
    cur.execute(f"CREATE DATABASE IF NOT EXISTS {db_name}")
    conn.commit()
    cur.close()
    conn.close()
    print(f"Database '{db_name}' ready.")


def create_tables_and_seed():
    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor()

    for ddl in TABLES:
        cur.execute(ddl)
    print(f"{len(TABLES)} tables ready.")

    cur.executemany(
        "INSERT IGNORE INTO effects (effect_name, description) VALUES (%s, %s)", EFFECTS)
    cur.executemany(
        "INSERT IGNORE INTO drum_samples (name, category) VALUES (%s, %s)", DRUMS)
    cur.executemany(
        """INSERT IGNORE INTO instruments
           (name, waveform, attack, decay, sustain, release_t)
           VALUES (%s, %s, %s, %s, %s, %s)""", INSTRUMENTS)

    conn.commit()
    cur.close()
    conn.close()
    print("Starter effects, drum sounds and instruments added.")


if __name__ == "__main__":
    create_database()
    create_tables_and_seed()
    print("Setup complete.")