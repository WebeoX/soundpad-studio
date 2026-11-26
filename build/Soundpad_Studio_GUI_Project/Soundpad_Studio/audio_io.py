"""
audio_io.py - Reading/writing WAV files and registering them in MySQL.
Procedural, standard library only (plus db.py).

AUDIO FORMAT used everywhere in the project:
    audio = {"rate": 44100, "channels": [[float,...], [float,...]]}
    - one inner list per channel (1 = mono, 2 = stereo)
    - samples are floats between -1.0 and 1.0
"""
import os
import sys
import wave
import array
import tempfile

import mysql.connector
from db import execute, fetch_one, fetch_all

try:
    import winsound          # Windows only, built in
except ImportError:
    winsound = None


# ------------------------------------------------------------------ WAV I/O
def load_wav(path):
    """Read a PCM WAV file (8/16/24/32-bit) and return an audio dict."""
    with wave.open(path, "rb") as w:
        nch = w.getnchannels()
        width = w.getsampwidth()
        rate = w.getframerate()
        raw = w.readframes(w.getnframes())

    if width == 1:                                   # 8-bit is unsigned
        data = [(b - 128) / 128.0 for b in raw]
    elif width == 2:
        arr = array.array("h")
        arr.frombytes(raw)
        if sys.byteorder == "big":
            arr.byteswap()
        data = [s / 32768.0 for s in arr]
    elif width == 3:
        data = [int.from_bytes(raw[i:i + 3], "little", signed=True) / 8388608.0
                for i in range(0, len(raw), 3)]
    elif width == 4:
        arr = array.array("i")
        arr.frombytes(raw)
        if sys.byteorder == "big":
            arr.byteswap()
        data = [s / 2147483648.0 for s in arr]
    else:
        raise ValueError("Unsupported sample width: %d bytes" % width)

    channels = [data[c::nch] for c in range(nch)]
    return {"rate": rate, "channels": channels}


def save_wav(path, audio):
    """Write an audio dict to a 16-bit PCM WAV file (values are clipped)."""
    chans = audio["channels"]
    nch = len(chans)
    n = len(chans[0])

    inter = array.array("h", [0]) * (n * nch)
    for c, ch in enumerate(chans):
        inter[c::nch] = array.array(
            "h", [int(max(-1.0, min(1.0, s)) * 32767) for s in ch])
    if sys.byteorder == "big":
        inter.byteswap()

    with wave.open(path, "wb") as w:
        w.setnchannels(nch)
        w.setsampwidth(2)
        w.setframerate(audio["rate"])
        w.writeframes(inter.tobytes())


def get_wav_info(path):
    """Read only the header: returns rate, channels, bit_depth, duration."""
    with wave.open(path, "rb") as w:
        rate = w.getframerate()
        return {
            "sample_rate": rate,
            "channels": w.getnchannels(),
            "bit_depth": w.getsampwidth() * 8,
            "duration_sec": round(w.getnframes() / rate, 3),
        }


# ------------------------------------------------------- database functions
def import_audio_file(user_id, path):
    """Register a WAV file in the audio_files table.
    Returns (file_id, message). file_id is None on failure."""
    path = os.path.abspath(path.strip().strip('"'))
    if not os.path.isfile(path):
        return None, "File not found."
    if not path.lower().endswith(".wav"):
        return None, "Only .wav files are supported."
    try:
        info = get_wav_info(path)
    except (wave.Error, EOFError):
        return None, "Not a valid PCM WAV file."

    file_id = execute(
        """INSERT INTO audio_files
           (user_id, file_name, file_path, duration_sec, sample_rate, channels, bit_depth)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (user_id, os.path.basename(path), path, info["duration_sec"],
         info["sample_rate"], info["channels"], info["bit_depth"]),
    )
    return file_id, "Imported '%s'." % os.path.basename(path)


def list_user_files(user_id):
    return fetch_all(
        """SELECT file_id, file_name, duration_sec, sample_rate, channels, bit_depth
           FROM audio_files WHERE user_id = %s ORDER BY added_on DESC""",
        (user_id,),
    )


def get_audio_file(file_id, user_id):
    """Return the DB row for a file owned by this user (or None)."""
    return fetch_one(
        "SELECT * FROM audio_files WHERE file_id = %s AND user_id = %s",
        (file_id, user_id),
    )


def load_audio_by_id(file_id, user_id):
    """Look up a file in MySQL and load its samples. Returns audio dict or None."""
    row = get_audio_file(file_id, user_id)
    if row is None or not os.path.isfile(row["file_path"]):
        return None
    return load_wav(row["file_path"])


def remove_audio_file(file_id, user_id):
    """Remove a file's record (the file on disk is NOT deleted)."""
    try:
        execute("DELETE FROM audio_files WHERE file_id = %s AND user_id = %s",
                (file_id, user_id))
    except mysql.connector.IntegrityError:
        return False, "This file is used by a clip in one of your projects."
    return True, "Removed from library."


def print_library(user_id):
    files = list_user_files(user_id)
    if not files:
        print("Your library is empty.")
        return
    print("%-5s %-30s %8s %8s %4s %4s" %
          ("ID", "Name", "Seconds", "Rate", "Ch", "Bit"))
    for f in files:
        print("%-5s %-30s %8s %8s %4s %4s" % (
            f["file_id"], f["file_name"][:30], f["duration_sec"],
            f["sample_rate"], f["channels"], f["bit_depth"]))


# ----------------------------------------------------------------- playback
def play_file(path, wait=True):
    """Play a WAV file (Windows only)."""
    if winsound is None:
        print("Playback is only available on Windows.")
        return
    flags = winsound.SND_FILENAME | (0 if wait else winsound.SND_ASYNC)
    winsound.PlaySound(path, flags)


def play_audio(audio, wait=True):
    """Play an audio dict by writing it to a temporary WAV first."""
    tmp = os.path.join(tempfile.gettempdir(), "audio_studio_preview.wav")
    save_wav(tmp, audio)
    play_file(tmp, wait)


def stop_playback():
    if winsound is not None:
        winsound.PlaySound(None, winsound.SND_PURGE)