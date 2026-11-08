# Optional IR head tracking — Windows G14

Built against the uploaded main snapshot 639cf8c43d4b1fa823b5fd88497cd89ff6de7a70.
This adds selectable colour/IR capture, not simultaneous camera fusion.

## Install and run

Use Python 3.11 for this project: it pins MediaPipe 0.10.21 and NumPy <2.
Your separate Python 3.14 ir-test environment demonstrated camera access, but
should not replace the application's environment.

From the GitHappens repository root on Windows:

```powershell
py -3.11 -m venv .venv-ir
.\.venv-ir\Scripts\python.exe -m pip install -r requirements.txt -r requirements-ir.txt
.\.venv-ir\Scripts\python.exe -m accessshift
```

If Python 3.11 is missing, install it first and reopen PowerShell:

```powershell
winget install -e --id Python.Python.3.11
```

Do not install `whircam[full]` here: the app already supplies compatible NumPy
and OpenCV versions through requirements.txt. WHIRCAM itself is pinned to 0.1.0.
Close the separate WHIRCAM preview before starting AccessShift.

## User flow

1. Enable Eye & blink control / GazeControl.
2. On Windows with WHIRCAM installed, the app discovers IR groups in a separate
   process. Discovery has a 20-second timeout and a Keep regular webcam button.
   It does not start IR capture.
3. If an IR source is found, explicitly choose Use infrared or Keep regular webcam.
4. For the tested G14, choose Rts-DMFT-Group. The choice is stored in local QSettings.
5. The camera worker opens IR, supplies BGR-formatted grayscale data to the existing
   MediaPipe FaceMesh tracker, and discards frames flagged as ambient.
6. Complete the existing head calibration. Inspect the preview while turning/tilting
   the head. A visible IR face is not evidence that MediaPipe landmarks are reliable.
7. Camera… in the gaze toolbar lets you choose the webcam again or rediscover IR.
   It stops capture before switching and invalidates the previous calibration.

Mac/Linux retain the regular webcam path and do not import WHIRCAM.
The app does not silently switch camera geometry during an active calibration.
If IR opening fails, no usable illuminated frames arrive for 10 seconds, or no
face is detected for 15 seconds, a tracking error is shown. Use Camera… → Regular
webcam, then recalibrate. No camera data is recorded by these changes.

The illuminated flag is WHIRCAM's latest-frame metadata, so treat its frame
filter as best effort. Missing illumination metadata is accepted. Both of the
G14 groups tested by the user advertised 640x360 at 15 FPS; this code does not
increase camera FPS, adjust emitter power, modify drivers, or alter Windows Hello.

## Files changed

- gaze/ir_camera.py: lazy optional Windows capture adapter.
- gaze/tracker.py: selectable IR capture feeding the original landmark processing.
- gaze/controller.py: camera calibration reset and longer bounded stop wait.
- ui/ir_camera_choice.py: discovery, consent, remembered selection.
- ui/gaze_mode.py: selection and switching lifecycle.
- ui/main_window.py: Camera… toolbar button.
- requirements-ir.txt and tests/gaze/test_ir_camera.py.

No SteadyHand filters, portal logic, or speech implementation is replaced.

## Verification

Hardware-independent tests cover IR frame filtering, release, timeout, platform
fallback, remembered choice and calibration reset. Existing gaze tests are also
run. Real Windows capture, driver sharing, and MediaPipe accuracy on this G14
must still be tested on the laptop. The build environment has no Windows IR camera.
