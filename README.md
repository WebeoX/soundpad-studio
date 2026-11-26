[README.md](https://github.com/user-attachments/files/35446244/README.md)
# Soundpad Studio

A Python + MySQL application for **audio mixing, beat making and music composition**, with a dark-mode
graphical interface. Written in the procedural style: **no classes**, only functions.

Made by Johaan Jomon as a Computer Science project.

## Features

- **Arrange** - multi-track timeline with audio clips, waveforms, snapping, split / duplicate, per-clip effect chain
- **Mixer** - fader, pan, mute and solo per track, real peak / RMS metering of the final mix
- **Beat Maker** - step sequencer with 8 synthesized drum sounds, swing, presets and live loop audition
- **Piano Roll** - synthesizer with ADSR instruments, scales, chord progressions, arpeggios, random melodies
- **Audio Lab** - waveform editor with region effects, undo / redo, merge / mix and an FFT spectrum analyser
- **Insights** - dashboard drawn from SQL queries (JOIN, GROUP BY, HAVING)
- Accounts with salted PBKDF2 password hashing; everything is stored in MySQL; export to WAV

## Requirements

- Windows (live playback uses `winsound`; exporting WAV files works anywhere)
- Python 3 (Tkinter is included with Python)
- MySQL Server

## Setup

1. Install the one extra Python package:

   ```
   pip install -r requirements.txt
   ```

2. Tell the program how to reach your MySQL server. Copy `db_config.example.json` to
   `db_config.json` and put your own MySQL password in it. This file is ignored by Git, so your
   password is never uploaded.

3. Create the database and tables (run once):

   ```
   python setup_db.py
   ```

4. Start the program:

   ```
   python gui.py
   ```

   (`python main.py` starts the older text-menu version.)

## Project files

| File | Purpose |
| --- | --- |
| `setup_db.py` | Creates the database, 13 tables and starter data |
| `db.py` | MySQL helper functions and connection settings |
| `auth.py` | Registration, login, password hashing |
| `audio_io.py` | WAV reading / writing, audio library, playback |
| `editing.py` | Audio editing and effects |
| `projects.py` | Projects, tracks, clips, effect chains |
| `render.py` | Mixes a project into one WAV file |
| `beats.py` | Drum synthesis and step sequencer |
| `synth.py` | Synthesizer, scales, chords, melody generator |
| `visualizer.py` | Waveform and FFT spectrum |
| `gui*.py` | The graphical interface, one module per screen (`gui.py` is the entry point) |
| `main.py` | Console (text-menu) version |

## Notes

- Your database and audio files stay on your own computer; the repository holds only the code.
  On a new computer, repeat the setup above and import your WAV files again.
