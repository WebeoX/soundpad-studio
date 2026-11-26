# Soundpad Studio — Tkinter GUI

## Run it

1. Install Python 3.10 or newer.
2. Install the dependency:
   ```bash
   python -m pip install -r requirements.txt
   ```
3. Install and start MySQL Server.
4. Open `db.py` and set `DB_CONFIG` to your local MySQL username, password and database name.
5. Create the database tables and starter records:
   ```bash
   python setup_db.py
   ```
6. Launch the graphical app:
   ```bash
   python main.py
   ```

The GUI is written with Tkinter and uses **procedural functions and dictionaries**.
It does not define custom classes. The existing audio engine, project logic,
authentication, beat maker and synthesizer modules are retained.

## Notes

- Use WAV files in the Audio Library.
- Export creates a WAV mix. Rendering can take a little while for longer sessions.
- The project uses MySQL; it is not a standalone/offline database application.
- Live playback support in the original audio helpers is platform-dependent.
