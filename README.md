# Music HandControl

Music HandControl is a polished desktop MP3 player controlled by hand gestures, mouse, or keyboard. It combines a responsive PySide6 interface, MediaPipe hand tracking, pygame-ce playback, embedded metadata/artwork, and three playback-synchronized visualizer modes.

> The app is local-first: it does not upload camera frames, music, metadata, or settings.

## Highlights

- Open-palm hold for play/pause with state locking so a raised hand does not trigger accidentally
- Right thumb–index pinch for next and left thumb–index pinch for previous
- Easy volume mode: hold a peace sign, move your hand vertically, then hold a fist to save
- Add local MP3 files or download and convert one YouTube video with an optional filename
- Threaded webcam capture and hand analysis, keeping the interface responsive
- Spectrum, wave, and circular visualizers with rise/fall interpolation
- MP3 metadata, duration, and embedded cover artwork via Mutagen
- Clickable playlist, seeking, mute, shuffle, repeat playlist, and repeat track
- Webcam-free operation with complete mouse and keyboard controls
- Camera, hand, sensitivity, cooldown, landmarks, and visualizer settings
- Persistent local settings and rotating diagnostic logs
- Safe handling of empty folders, missing cameras, invalid MP3s, and audio errors

## Screenshot

<!-- Replace this placeholder after capturing the app on your system. -->

![Music HandControl interface placeholder](docs/screenshot-placeholder.svg)

## Requirements

- Windows, macOS, or Linux desktop
- Python 3.10–3.14 (64-bit recommended)
- A working audio output device
- Optional webcam for gesture control

## Install and run

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

On macOS/Linux, activate the environment with `source .venv/bin/activate`.

## Add music

Click **＋ Add** above the playlist and choose either:

- **From Files** — select one or more `.mp3` files. Music HandControl copies them into `music/` without overwriting an existing track.
- **From YouTube** — paste a `youtube.com` or `youtu.be` video link, optionally enter the desired MP3 filename, then select **Download and Convert to MP3**. Leave the filename blank to use the video title.

The download and FFmpeg conversion run in the background. The playlist refreshes as soon as the operation completes. Download only content you own or have permission to use; availability and permitted use vary by video and region.

You can also copy `.mp3` files directly into:

```text
music/
```

The folder is created automatically and rescanned at startup. Files are sorted by filename. MP3 files are intentionally excluded from Git; `music/.gitkeep` preserves the folder.

If the folder is empty, the app stays fully usable and displays:

```text
No music found.

Add MP3 files inside the /music folder.
```

## Gestures

Keep one primary hand clearly visible and roughly face the palm toward the camera.

| Gesture | Action | Recognition behavior |
|---|---|---|
| Open palm held for 0.85 seconds | Play / pause | Fires once; reset by changing the gesture |
| Right thumb + index pinch | Next song | Fires once per pinch |
| Left thumb + index pinch | Previous song | Fires once per pinch |
| Peace sign held for 0.55 seconds | Enter volume mode | Works with either hand |
| Move the active hand up or down | Raise or lower volume | Continuous, smoothed 0–100% mapping |
| Closed fist held for 0.65 seconds | Save volume and exit | The current volume freezes as soon as the fist is seen |

For Next or Previous, raise the intended hand and make one clear thumb–index pinch. Volume mode deliberately separates adjustment from track changes: hold a peace sign to enter, move the tracked hand vertically to adjust, then hold a closed fist to save and return to normal controls.

With multiple hands, Music HandControl selects the hand matching **Control Hand** when configured; in Auto mode it uses the best-confidence hand, with palm size as the tie breaker. Tune sensitivity and cooldown in Settings if lighting or camera placement causes unreliable detection.

## Gesture tutorial

Keep your full hand inside the camera view, face your palm roughly toward the camera, and wait for the gesture label before changing poses.

### Play or pause

1. Raise either hand with all fingers open.
2. Hold the open palm steady for about one second.
3. Lower or change your hand before using the gesture again.

### Next song

1. Raise your **right hand**.
2. Touch your right index fingertip and thumb together once.
3. Separate them before making another Next gesture.

### Previous song

1. Raise your **left hand**.
2. Touch your left index fingertip and thumb together once.
3. Separate them before making another Previous gesture.

### Change and save the volume

1. With either hand, raise only your index and middle fingers to make a peace sign.
2. Hold the peace sign until **Volume Mode On** appears.
3. Move the tracked hand upward for louder audio or downward for quieter audio. You may relax and open your hand while moving it.
4. When the displayed percentage is right, close the same hand into a fist. The volume freezes immediately, so closing the fist will not decrease it.
5. Hold the fist briefly until **Volume Saved** appears, then reopen or lower your hand.

For the most reliable control, use even front lighting, keep one hand closer to the camera than the other, and avoid letting fingertips leave the frame.

## Keyboard controls

| Key | Action |
|---|---|
| Space | Play / pause |
| Right Arrow | Next track |
| Left Arrow | Previous track or restart after four seconds |
| Up Arrow | Volume +5% |
| Down Arrow | Volume −5% |

## Mouse controls

- Click any playlist item to play it.
- Drag the progress bar to seek.
- Use the player buttons for previous, play/pause, next, shuffle, repeat, and mute.
- Select Spectrum, Wave, or Circular above the visualizer.
- Turn **Hand Control** off to release the camera while music keeps playing.

## Settings

- Hand tracking: On / Off
- Camera index
- Gesture sensitivity: Low / Medium / High
- Gesture cooldown: 0.4–2.5 seconds
- Control hand: Auto / Left / Right
- Visualizer mode and sensitivity
- Hand landmark visibility

Settings are saved to the ignored `settings.json` file when the app closes.

## Technology

- **PySide6 / Qt 6** — desktop UI and painting
- **MediaPipe** — hand landmark tracking
- **OpenCV** — camera capture and frame conversion
- **pygame-ce** — streamed MP3 playback and seeking
- **NumPy** — bounded FFT spectrum analysis and animation data
- **Mutagen** — MP3 metadata and embedded artwork
- **yt-dlp** — single-video YouTube audio retrieval
- **imageio-ffmpeg** — bundled FFmpeg binary for MP3 conversion

## Project structure

```text
handwave-music/
├── main.py
├── music/                 # add MP3 files here (not committed)
├── assets/                # MediaPipe task model when required
├── src/
│   ├── audio/             # playback, metadata, import/download, FFT analysis
│   ├── config/            # JSON settings
│   ├── ui/                # window, camera, artwork, visualizer
│   ├── vision/            # tracking, gestures, debounce controller
│   └── utils/             # rotating logs
├── tests/
├── requirements.txt
├── ARCHITECTURE.md
├── DEPLOYMENT.md
└── SECURITY.md
```

## Troubleshooting

### Camera unavailable

Close other apps using the webcam, confirm camera permission for desktop apps, choose another camera in Settings, then toggle Hand Control off and on. The player remains functional without a camera.

### Audio device unavailable

Connect or enable an output device before launch. Check `logs/music-handcontrol.log` for backend details. Corrupt tracks are skipped or reported without terminating the app.

### Gestures fire too easily or not at all

Use even front lighting, keep the entire hand in frame, select the intended control hand, and adjust Gesture Sensitivity. Increase cooldown if discrete actions repeat too quickly.

### Visualizer is idle

The accurate spectrum is computed asynchronously after a track begins. A subtle fallback animation is displayed while analysis loads or when the decoder cannot analyze a file.

### YouTube download fails

Confirm the link points to one public YouTube video rather than a playlist, private video, live stream, or age/region-restricted video. YouTube import requires Node.js, Deno, Bun, or QuickJS; Node.js is the recommended choice. YouTube changes frequently, so update the pinned yt-dlp version after reviewing and testing upstream releases when extraction stops working. The application log contains the technical failure reason.

### MediaPipe model missing

The pinned release includes the classic Hands model. The code also supports newer Tasks-only builds; if using one and the application reports `assets/hand_landmarker.task is missing`, follow [DEPLOYMENT.md](DEPLOYMENT.md) to retrieve the official model asset.

## Development and tests

```powershell
pip install -r requirements-dev.txt
pytest
ruff check .
```

Hardware integration checks (camera, actual MP3 playback, gestures in varied lighting) must be performed on the target machine. Pure gesture interpretation, cooldowns, settings, and safe playlist discovery are covered by automated tests.

## Documentation

- [Architecture](ARCHITECTURE.md)
- [Deployment](DEPLOYMENT.md)
- [Security](SECURITY.md)

## Credits

Music HandControl was created for and is credited to **Arjunrenvon**.

## License

MIT © 2026 Arjunrenvon
