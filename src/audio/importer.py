from __future__ import annotations

import logging
import os
import re
import shutil
import threading
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlparse

from PySide6.QtCore import QObject, Signal

LOGGER = logging.getLogger(__name__)
MAX_IMPORT_BYTES = 512 * 1024 * 1024
INVALID_FILENAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
}
YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
}


def is_youtube_url(value: str) -> bool:
    try:
        parsed = urlparse(value.strip())
        return parsed.scheme in {"http", "https"} and (parsed.hostname or "").lower() in YOUTUBE_HOSTS
    except ValueError:
        return False


def safe_mp3_name(value: str, fallback: str = "track") -> str:
    name = Path(value.strip()).stem if value.strip().lower().endswith(".mp3") else value.strip()
    name = INVALID_FILENAME.sub("_", name)
    name = re.sub(r"\s+", " ", name).strip(" ._")[:120]
    if not name:
        name = fallback
    if name.upper() in RESERVED_NAMES:
        name = f"_{name}"
    return f"{name}.mp3"


def unique_destination(music_dir: Path, filename: str) -> Path:
    root = music_dir.resolve()
    candidate = root / safe_mp3_name(filename)
    counter = 2
    while candidate.exists():
        candidate = root / f"{Path(safe_mp3_name(filename)).stem} ({counter}).mp3"
        counter += 1
    return candidate


class _DownloadLogger:
    def __init__(self, report: Callable[[str], None]) -> None:
        self.report = report

    def debug(self, message: str) -> None:
        if message.startswith("[download]"):
            self.report(message.removeprefix("[download]").strip())

    def info(self, message: str) -> None:
        LOGGER.info("yt-dlp: %s", message)

    def warning(self, message: str) -> None:
        LOGGER.warning("yt-dlp: %s", message)

    def error(self, message: str) -> None:
        LOGGER.error("yt-dlp: %s", message)


class MusicImporter(QObject):
    progress = Signal(int, str)
    completed = Signal(str)
    failed = Signal(str)

    def __init__(self, music_dir: Path) -> None:
        super().__init__()
        self.music_dir = music_dir
        self.music_dir.mkdir(parents=True, exist_ok=True)
        self._busy = False
        self._lock = threading.Lock()

    @property
    def busy(self) -> bool:
        with self._lock:
            return self._busy

    def _start(self, target: Callable[[], str]) -> bool:
        with self._lock:
            if self._busy:
                return False
            self._busy = True

        def run() -> None:
            try:
                message = target()
                self.progress.emit(100, "Complete")
                self.completed.emit(message)
            except Exception as exc:
                LOGGER.exception("Music import failed")
                message = re.sub(r"\s+", " ", str(exc)).strip()[:300]
                self.failed.emit(message or "The music could not be added.")
            finally:
                with self._lock:
                    self._busy = False

        threading.Thread(target=run, daemon=True, name="music-import").start()
        return True

    def import_local(self, paths: list[str]) -> bool:
        return self._start(lambda: self._copy_local(paths))

    def _copy_local(self, paths: list[str]) -> str:
        if not paths:
            raise ValueError("Choose at least one MP3 file.")
        added = 0
        root = self.music_dir.resolve()
        for index, raw_path in enumerate(paths, 1):
            source = Path(raw_path).resolve(strict=True)
            if not source.is_file() or source.suffix.lower() != ".mp3":
                raise ValueError(f"{source.name} is not an MP3 file.")
            if source.stat().st_size > MAX_IMPORT_BYTES:
                raise ValueError(f"{source.name} is larger than the 512 MB limit.")
            self.progress.emit(round((index - 1) / len(paths) * 90), f"Importing {source.name}")
            if source.parent == root:
                added += 1
                continue
            destination = unique_destination(root, source.name)
            shutil.copy2(source, destination)
            added += 1
        return f"Added {added} track{'s' if added != 1 else ''} to your library."

    def download_youtube(self, url: str, optional_name: str = "") -> bool:
        if not is_youtube_url(url):
            self.failed.emit("Enter a valid youtube.com or youtu.be video URL.")
            return False
        return self._start(lambda: self._download_youtube(url.strip(), optional_name))

    def _download_youtube(self, url: str, optional_name: str) -> str:
        # Third-party yt-dlp plugins execute Python code; disable discovery for this local app.
        os.environ["YTDLP_NO_PLUGINS"] = "1"
        import imageio_ffmpeg
        import yt_dlp

        root = self.music_dir.resolve()
        runtime = next(
            (
                (name, executable)
                for name in ("deno", "node", "bun", "quickjs")
                if (executable := shutil.which(name))
            ),
            None,
        )
        if runtime is None:
            raise RuntimeError(
                "YouTube import requires Node.js, Deno, Bun, or QuickJS. Install Node.js and restart HandWave."
            )
        runtime_name, runtime_path = runtime
        before = {path.resolve() for path in root.glob("*.mp3")}
        if optional_name.strip():
            destination = unique_destination(root, optional_name)
            output_template = str(destination.with_suffix(".%(ext)s"))
        else:
            output_template = str(root / "%(title).120B [%(id)s].%(ext)s")

        def download_progress(data: dict) -> None:
            status = data.get("status")
            if status == "downloading":
                total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
                downloaded = data.get("downloaded_bytes") or 0
                percent = round(downloaded / total * 90) if total else 0
                self.progress.emit(max(0, min(percent, 90)), "Downloading audio…")
            elif status == "finished":
                self.progress.emit(92, "Converting to MP3…")

        def postprocessor_progress(data: dict) -> None:
            if data.get("status") == "started":
                self.progress.emit(94, "Converting to MP3…")
            elif data.get("status") == "finished":
                self.progress.emit(98, "Finalizing metadata…")

        options = {
            "format": "bestaudio/best",
            "outtmpl": output_template,
            "noplaylist": True,
            "playlistend": 1,
            "max_filesize": MAX_IMPORT_BYTES,
            "overwrites": False,
            "continuedl": False,
            "windowsfilenames": True,
            "socket_timeout": 30,
            "retries": 3,
            "fragment_retries": 3,
            "concurrent_fragment_downloads": 1,
            "js_runtimes": {runtime_name: {"path": runtime_path}},
            "ffmpeg_location": imageio_ffmpeg.get_ffmpeg_exe(),
            "postprocessors": [
                {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"},
                {"key": "FFmpegMetadata", "add_metadata": True},
            ],
            "progress_hooks": [download_progress],
            "postprocessor_hooks": [postprocessor_progress],
            "logger": _DownloadLogger(lambda text: self.progress.emit(0, text[:120])),
            "quiet": True,
            "no_warnings": True,
        }
        self.progress.emit(0, "Reading YouTube video information…")
        with yt_dlp.YoutubeDL(options) as downloader:
            downloader.download([url])
        new_files = [path for path in root.glob("*.mp3") if path.resolve() not in before]
        if not new_files:
            raise RuntimeError("Download finished, but no new MP3 file was created.")
        newest = max(new_files, key=lambda path: path.stat().st_mtime)
        return f"Added {newest.name} to your library."
