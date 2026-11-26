# ClearCursor Privacy Policy

ClearCursor processes pointer movement, accessibility element coordinates, webcam frames, and motor telemetry locally on your computer.

## What Data ClearCursor Processes

1. **Pointer Coordinates & Click Timing**
   When system-wide stabilization is enabled, ClearCursor reads pointer movements, button presses, and scroll events in memory to smooth tremor oscillations, block accidental double-clicks, and pull slowed pointers toward nearby interface controls. Raw coordinate streams are kept in a rolling 4-second memory buffer for spectral calculation and are discarded immediately afterward.

2. **Summarized Motor Telemetry**
   Every 0.5 seconds during active cursor movement, ClearCursor can store a numerical summary row in your local SQLite database: timestamp, 4-12 Hz tremor power percentages, estimated RMS displacement in pixels and millimeters, dominant frequency, stability score, active preset name, and counts of rescued clicks or blocked drags.

3. **Medication & Symptom Diary Entries**
   Any medication doses, dosages, symptom severity ratings, or notes you enter on the Clinician Report tab are saved locally in the same SQLite database.

4. **Webcam Video (Gaze Mode Only)**
   The webcam is only opened when you explicitly turn on GazeControl Tracking or run Guided Calibration. Frames are processed in memory with OpenCV and MediaPipe to estimate head pose, iris position, and blink state. ClearCursor never writes webcam video or still images to disk and never transmits frames off your device.

## No Cloud Servers or Analytics

ClearCursor makes zero outbound network requests during normal operation. There is no telemetry upload, no third-party crash tracker, and no cloud account.

## Where Your Data Is Stored

Packaged desktop builds store the SQLite database in your per-user application data directory:

- **macOS:** `~/Library/Application Support/ClearCursor/clearcursor.db`
- **Windows:** `%APPDATA%\ClearCursor\clearcursor.db`
- **Linux:** `~/.local/share/ClearCursor/clearcursor.db`

You can override this location by setting the `CLEARCURSOR_DB_PATH` environment variable.

## Exporting and Deleting Data

- **Export:** Open the **Clinician Report** tab to export your longitudinal summaries and medication diary as a PDF report or CSV spreadsheet.
- **Delete:** Quit ClearCursor from the menu bar or system tray, then delete `clearcursor.db` (and any accompanying `-wal` or `-shm` files) from the folder listed above.
