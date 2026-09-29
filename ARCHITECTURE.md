# Architecture

## Design goals

Music HandControl separates hardware access, interpretation, application rules, playback, and presentation. Camera frames never directly call the audio backend, and the Qt UI thread never runs continuous computer-vision work.

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
- `importer.py` copies local MP3 files or retrieves one allowlisted YouTube video through yt-dlp. It sanitizes destinations, avoids overwrites, enforces a 512 MiB limit, disables third-party yt-dlp plugins, and delegates MP3 conversion to the bundled FFmpeg binary on a worker thread.

### Vision

- `hand_tracker.py` owns the camera on a dedicated thread, supports MediaPipe's legacy and Tasks interfaces, passes up to two detected hands to the gesture layer, draws subtle landmarks for each, and emits copied `QImage` frames.
- `gesture_detector.py` depends only on normalized hand points, handedness, and confidence. It recognizes posture, pinch distance, and timed holds, making the recognition logic independently testable.
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
- `music-import` handles local copies, network retrieval, and FFmpeg conversion without UI access.
- Qt signals cross the camera thread boundary safely.
- Closing the window stops and joins the camera worker, closes the mixer, saves settings, and accepts the close event.

Worker threads are daemonized as a final safety net, but explicit shutdown is the primary lifecycle mechanism.

## Gesture details

- Finger extension compares tip, PIP, and MCP landmark Y positions.
- Open palm requires all four fingers, a separated thumb, and a 0.85-second hold before play/pause.
- A right thumb–index pinch held for two seconds emits Next; the same held pinch on the left hand emits Previous. The event carries continuous progress for the UI loading bar, and release cancels or rearms it.
- A peace sign on either hand enables two-hand volume mode while a second hand is visible.
- The second hand's normalized thumb–index distance maps continuously and smoothly to 0–100% volume.
- Releasing the peace sign keeps the current level and exits volume mode.
- Sensitivity adjusts pinch thresholds while action cooldown remains a separate setting.
- Two-hand volume has priority over single-hand track gestures; the configured Control Hand still filters ordinary single-hand actions.

## Visual analysis

The analyzer uses sample windows distributed across the song at up to 20 frames per second (capped at 3,600), a Hann taper, real FFT, logarithmically spaced bins, RMS energy, logarithmic compression, and 98th-percentile normalization. The rendering layer applies fast attack and slow release interpolation. This gives stable bass/mid/treble response without decoding on every paint.
