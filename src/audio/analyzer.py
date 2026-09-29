from __future__ import annotations

import logging
import math
import threading
from pathlib import Path

import numpy as np

LOGGER = logging.getLogger(__name__)


class AudioAnalyzer:
    """Builds a bounded, playback-synced spectral map on a worker thread."""

    def __init__(self, bars: int = 48) -> None:
        self.bars = bars
        self.frames = np.zeros((1, bars), dtype=np.float32)
        self.duration = 0.0
        self._generation = 0
        self._lock = threading.Lock()

    def analyze_async(self, path: Path, duration: float) -> None:
        self._generation += 1
        generation = self._generation
        with self._lock:
            self.frames = np.zeros((1, self.bars), dtype=np.float32)
            self.duration = duration
        threading.Thread(
            target=self._analyze, args=(path, duration, generation), daemon=True, name="audio-analysis"
        ).start()

    def _analyze(self, path: Path, duration: float, generation: int) -> None:
        try:
            import pygame

            # Playback can stream large files, but decoding a very large file into
            # RAM for visualization would be an avoidable resource-exhaustion risk.
            if path.stat().st_size > 64 * 1024 * 1024:
                LOGGER.info("Skipping in-memory spectrum analysis for large file %s", path.name)
                return
            sound = pygame.mixer.Sound(str(path))
            samples = pygame.sndarray.array(sound)
            if samples.ndim == 2:
                samples = samples.astype(np.float32).mean(axis=1)
            else:
                samples = samples.astype(np.float32)
            if not len(samples):
                return
            sample_rate = int(len(samples) / max(duration, 0.1))
            window = max(512, min(4096, 2 ** int(math.log2(max(512, sample_rate // 20)))))
            frame_count = min(3600, max(1, int(max(duration, 0.1) * 20)))
            starts = np.linspace(0, max(0, len(samples) - window), frame_count).astype(np.int64)
            edges = np.geomspace(2, window // 2, self.bars + 1).astype(int)
            result = np.zeros((len(starts), self.bars), dtype=np.float32)
            taper = np.hanning(window).astype(np.float32)
            peak = float(np.max(np.abs(samples))) or 1.0
            samples /= peak
            for row, start in enumerate(starts):
                spectrum = np.abs(np.fft.rfft(samples[start : start + window] * taper))
                for bar in range(self.bars):
                    lo, hi = edges[bar], max(edges[bar] + 1, edges[bar + 1])
                    result[row, bar] = float(np.sqrt(np.mean(np.square(spectrum[lo:hi]))))
            result = np.log1p(result * 10.0)
            result /= max(float(np.percentile(result, 98)), 1e-6)
            np.clip(result, 0.0, 1.0, out=result)
            if generation == self._generation:
                with self._lock:
                    self.frames = result
                    self.duration = duration
        except Exception as exc:
            LOGGER.info("Spectrum analysis unavailable for %s: %s", path.name, exc)

    def levels_at(self, position: float) -> np.ndarray:
        with self._lock:
            frames = self.frames
            duration = self.duration
            if duration <= 0 or len(frames) <= 1:
                phase = position * 2.2
                indices = np.arange(self.bars, dtype=np.float32)
                return (0.12 + 0.08 * np.sin(indices * 0.7 + phase)).astype(np.float32)
            index = min(len(frames) - 1, max(0, int(position / duration * (len(frames) - 1))))
            return frames[index].copy()
