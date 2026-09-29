# Architecture

## Design goals

HandWave separates hardware access, interpretation, application rules, playback, and presentation. Camera frames never directly call the audio backend, and the Qt UI thread never runs continuous computer-vision work.

```text
CameraWorker thread
  → MediaPipe adapter
  → normalized landmarks
  → GestureDetector
  → GestureEvent signal
  → GestureController (locks, cooldown, smoothing)
  → MainWindow action
  → AudioPlayer

MP3 folder
  → safe scanner / Mutagen
  → immutable Track records
  → playlist + AudioPlayer
  → background FFT analyzer
  → playback-position lookup
  → Visualizer painter
```

## Components

### Audio

- `metadata.py` constrains discovery to direct `.mp3` children, caps accepted file and artwork size, sanitizes display strings, and turns parsed files into immutable `Track` values.
- `audio_player.py` owns pygame mixer state, timing, seeking, completion behavior, shuffle, and repeat rules.
- `analyzer.py` computes a bounded 48-band spectral map on a daemon worker. Analysis is skipped for files over 64 MiB to avoid a large in-memory decode; playback continues with the elegant fallback animation. The UI retrieves one frame by current playback position and never blocks on decoding.

### Vision

- `hand_tracker.py` owns the camera on a dedicated thread, supports MediaPipe's legacy and Tasks interfaces, selects exactly one primary hand, draws subtle landmarks, and emits copied `QImage` frames.
- `gesture_detector.py` depends only on 21 normalized points. It recognizes posture, pinch distance, and time-window wrist motion, making the recognition logic independently testable.
- `gesture_controller.py` makes commands safe: a held discrete pose is locked, cooldowns survive a brief pose change, and volume uses exponential smoothing plus an emission-rate limit.

### UI

`MainWindow` coordinates components through small public methods and Qt signals. Custom-painted artwork and visualizer widgets avoid asset/theme inconsistencies. Timers update animation at about 30 fps and player state at 5 fps.

### Configuration and diagnostics

`SettingsStore` allows only known dataclass fields and normalizes every range or enum. Diagnostic details go to bounded rotating files under `logs/`; user-facing failures use short messages.

## Threading and lifecycle

- The Qt main thread handles widgets, callbacks, and lightweight timers.
- `camera-discovery` performs bounded device probing without blocking Qt.
- `camera-worker` owns OpenCV and MediaPipe resources until disabled or the window closes.
- `audio-analysis` handles decode and FFT without UI access.
- Qt signals cross the camera thread boundary safely.
- Closing the window stops and joins the camera worker, closes the mixer, saves settings, and accepts the close event.

Worker threads are daemonized as a final safety net, but explicit shutdown is the primary lifecycle mechanism.

## Gesture details

- Finger extension compares tip, PIP, and MCP landmark Y positions.
- Open palm requires all four fingers and a separated thumb.
- Volume requires most non-index fingers folded, preventing conflict with open palm.
- Swipes require displacement and velocity inside a 550 ms history.
- Sensitivity changes displacement threshold, not the gesture action layer.
- MediaPipe is configured for two-hand detection, but only one selected hand feeds the detector.

## Visual analysis

The analyzer uses sample windows distributed across the song at up to 20 frames per second (capped at 3,600), a Hann taper, real FFT, logarithmically spaced bins, RMS energy, logarithmic compression, and 98th-percentile normalization. The rendering layer applies fast attack and slow release interpolation. This gives stable bass/mid/treble response without decoding on every paint.
