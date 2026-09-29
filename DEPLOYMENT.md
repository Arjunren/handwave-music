# Deployment

HandWave is a source-run desktop app. It does not require a server, database, account, or network connection after installation.

## Supported environment

- 64-bit CPython 3.10–3.14
- Windows 10/11, modern macOS, or a desktop Linux distribution
- Audio output device; webcam optional

## Clean installation

```powershell
git clone https://github.com/Arjunren/handwave-music.git
cd handwave-music
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

Use `source .venv/bin/activate` on macOS or Linux.

## MediaPipe task model

MediaPipe distributions vary by Python/platform. The tracker first uses the classic bundled Hands solution when available. New Tasks-only builds require the official `hand_landmarker.task` asset at:

```text
assets/hand_landmarker.task
```

Only obtain this binary from Google's official MediaPipe model storage linked by the [Hand Landmarker documentation](https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker/python). Do not substitute an untrusted similarly named file.

## First run

The entry point creates `music/`, `assets/`, and `logs/`, loads or defaults `settings.json`, scans direct MP3 children, initializes audio, opens the window, and then enumerates a bounded set of camera indexes.

If camera or audio setup fails, the interface remains open and displays a user-facing error. Technical detail is retained in `logs/handwave.log`.

## Updating dependencies

Dependencies are pinned for reproducible installs. Before changing them:

1. Review upstream release and security notes.
2. Install into a fresh virtual environment.
3. Run `pytest` and `ruff check .`.
4. Exercise startup, playback/seek/completion, camera toggle, all gestures, all visualizer modes, and clean shutdown.
5. Update the compatibility notes in this document if supported Python versions change.

## Packaging

PyInstaller can be used for private distribution, but Qt, pygame codecs, OpenCV, MediaPipe native libraries, and the task model must all be collected. Build on each target operating system; cross-platform executable builds are not supported by PyInstaller. The source-run workflow is the verified distribution method for this release.
