# Soundpad Studio — Complete GUI

A procedural Tkinter interface for the complete Class XII Computer Science project. The GUI uses functions and dictionaries; it defines no custom classes.

## Included modules and features
- Authentication: register, sign in, change password, delete account.
- Audio library: import WAV files, list metadata, remove library records.
- Audio Lab: playback, waveform/spectrum, analysis, trim, cut, volume, fades, reverse, speed, normalize, echo, filters, distortion, loop, silence, merge, mono/stereo, undo/redo and save edited WAV.
- Projects: create, rename, delete, open, BPM controls.
- Tracks: audio, beat and instrument tracks; volume, pan, mute, solo, rename and delete.
- Audio clips: add, reposition, trim, volume, fades, delete and ordered clip effects.
- Beat maker: create/edit/delete patterns, step sequencer, swing/repeats, presets and custom WAV drum samples.
- Music composer: individual notes, chords, progressions, bass lines, arpeggios, generated melodies, transpose, note deletion/clear and note preview.
- Mix engine: preview, WAV export and export history.

## Setup
1. Install Python 3.10+ and MySQL Server.
2. Install dependencies: `pip install -r requirements.txt`
3. Edit `DB_CONFIG` in `db.py` with your local MySQL username/password.
4. Run `python setup_db.py` once to create the database and seed effects, drum samples and instruments.
5. Run `python main.py`.

The project stores account/project/library data in MySQL. WAV files are imported by registering their existing file paths; keep those files available on disk. Audio preview playback uses the Windows `winsound` module where available. Exported WAV files are written to the `exports` folder.

## Notes
- All project source modules from the supplied archive are retained.
- GUI and application logic are procedural; no custom `class` definitions are used.
- The app needs a working MySQL server. A Python syntax check alone cannot verify database credentials, schema state, or the local audio device.
