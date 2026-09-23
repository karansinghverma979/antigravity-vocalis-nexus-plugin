"""
vocalis/wakeword/detector.py — Hardened local offline wake word sentinel.

Key Architectural Invariants:
1. Persistent Singleton Model: Caches openWakeWord ONNX sessions in-memory.
   Eliminates the 1.5–2.0 second model reload freeze between conversational turns.
2. Tier 0 RMS Energy Pre-Gate: Drops silent frames (< -45 dBFS) before neural inference,
   dropping idle CPU usage to near 0%.
3. 80ms Frame Alignment: Ingests 1,280 samples at 16kHz to match openWakeWord's
   optimal temporal receptive field.
4. EMA Temporal Smoothing & Debounce: Filters confidence scores with Exponential Moving
   Average (alpha=0.55), 2-frame consecutive verification, and a 1.5s refractory lockout.
5. Instant Acoustic Earcon: Fires play_wake_chime() (<10ms) upon positive verification.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any

import numpy as np
import sounddevice as sd

from vocalis.config import cfg

try:
    from rich.console import Console
    console = Console()
except ImportError:
    import re
    class DummyConsole:
        def print(self, *args, **kwargs):
            cleaned = [re.sub(r'\[/?[^\]]+\]', '', str(a)) for a in args]
            print(*cleaned, **kwargs)
    console = DummyConsole()

# Class-level shared model cache (zero disk reload across sessions)
_SHARED_MODEL: Any = None
_SHARED_WAKE_WORD: str | None = None


def calculate_dbfs(samples: np.ndarray) -> float:
    """
    Calculate Root-Mean-Square (RMS) audio energy in decibels relative to full scale (dBFS).
    Full scale for 16-bit signed PCM is 32768.
    """
    if len(samples) == 0:
        return -100.0
    float_samples = samples.astype(np.float32)
    rms = float(np.sqrt(np.mean(float_samples ** 2)))
    if rms <= 1e-9:
        return -100.0
    return float(20.0 * np.log10(rms / 32768.0))


def get_shared_model(wake_word: str | None = None) -> Any:
    """
    Retrieve or lazy-load the openWakeWord ONNX singleton model.
    Throws a helpful RuntimeError if openwakeword is not installed.
    """
    global _SHARED_MODEL, _SHARED_WAKE_WORD
    target_word = wake_word or cfg.WAKE_WORD

    if _SHARED_MODEL is not None and _SHARED_WAKE_WORD == target_word:
        return _SHARED_MODEL

    try:
        from openwakeword.model import Model
    except ImportError as e:
        raise RuntimeError(
            "openWakeWord is not installed in the active environment.\n"
            "Install it via: pip install openwakeword onnxruntime\n"
            "Or run vocalis with '--no-wakeword' to open the microphone directly."
        ) from e

    console.print(f"[dim]⚡ Loading openWakeWord ONNX model for '{target_word}'...[/dim]")
    _SHARED_MODEL = Model(
        wakeword_models=[target_word],
        inference_framework="onnx",
    )
    _SHARED_WAKE_WORD = target_word
    return _SHARED_MODEL


class WakeWordDetector:
    """
    High-precision wake word sentinel with energy pre-gating,
    temporal EMA smoothing, and refractory debounce.
    """

    def __init__(self, wake_word: str | None = None) -> None:
        self.wake_word = wake_word or cfg.WAKE_WORD
        self.threshold = cfg.WAKE_SCORE_THRESHOLD
        self.consecutive_target = cfg.WAKE_CONSECUTIVE_FRAMES
        self.ema_alpha = cfg.WAKE_EMA_ALPHA
        self.energy_threshold_db = cfg.WAKE_ENERGY_THRESHOLD_DB
        self.debounce_s = cfg.WAKE_DEBOUNCE_S

        self.ema_score: float = 0.0
        self.consecutive_hits: int = 0
        self.last_trigger_time: float = 0.0

    def reset_state(self) -> None:
        """Reset temporal smoothing filters."""
        self.ema_score = 0.0
        self.consecutive_hits = 0

    def process_frame(
        self,
        samples: np.ndarray,
        model: Any = None,
        now: float | None = None,
    ) -> tuple[bool, float, float]:
        """
        Process a single 80ms PCM audio frame (1,280 samples at 16kHz).

        Returns:
            tuple of (is_wake_triggered, smoothed_ema_score, energy_dbfs)
        """
        if now is None:
            now = time.monotonic()

        # Step 1: Tier 0 RMS Energy Pre-Gate
        dbfs = calculate_dbfs(samples)
        if dbfs < self.energy_threshold_db:
            # Silence/background noise — decay score and skip ONNX computation
            self.ema_score = (1.0 - self.ema_alpha) * self.ema_score
            self.consecutive_hits = 0
            return (False, self.ema_score, dbfs)

        # Step 2: Acquire model & predict
        if model is None:
            model = get_shared_model(self.wake_word)

        prediction = model.predict(samples)
        raw_score = float(prediction.get(self.wake_word, 0.0))

        # Step 3: EMA Temporal Smoothing
        self.ema_score = self.ema_alpha * raw_score + (1.0 - self.ema_alpha) * self.ema_score

        # Step 4: Multi-Frame Consecutive Verification
        if self.ema_score >= self.threshold:
            self.consecutive_hits += 1
        else:
            self.consecutive_hits = 0

        # Step 5: Refractory Lockout / Debounce Check
        time_since_last = now - self.last_trigger_time
        if self.consecutive_hits >= self.consecutive_target and time_since_last >= self.debounce_s:
            self.last_trigger_time = now
            self.reset_state()
            return (True, self.ema_score, dbfs)

        return (False, self.ema_score, dbfs)

    async def wait_for_wake(self) -> None:
        """
        Asynchronously block until the wake word is detected.
        Runs listening loop in thread executor without stalling the event loop.
        """
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._blocking_listen)

    def _blocking_listen(self) -> None:
        """Blocking microphone read loop with 80ms frame ingestion."""
        model = get_shared_model(self.wake_word)
        chunk_size = cfg.WAKE_CHUNK_FRAMES

        self.reset_state()

        with sd.InputStream(
            samplerate=cfg.SAMPLE_RATE,
            channels=1,
            dtype="int16",
            blocksize=chunk_size,
        ) as stream:
            while True:
                audio, _ = stream.read(chunk_size)
                samples = audio[:, 0]

                is_wake, score, dbfs = self.process_frame(samples, model=model)

                if is_wake:
                    console.print(
                        f"[bold green]🎤 '{self.wake_word}' detected "
                        f"(score={score:.2f}, energy={dbfs:.1f} dBFS)[/bold green]"
                    )
                    # Instant acoustic earcon feedback (<10ms)
                    self._play_chime_safely()
                    return

    def _play_chime_safely(self) -> None:
        """Play ascending wake chime without throwing if audio is busy."""
        try:
            from vocalis.tools.notifications import play_wake_chime
            play_wake_chime()
        except Exception:
            pass
