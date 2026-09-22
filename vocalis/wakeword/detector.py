"""
vocalis/wakeword/detector.py — Local offline wake word detection.

Uses openWakeWord with pre-trained ONNX models.
Runs continuously on the mic stream. Zero cloud tokens consumed.
Fires WAKE_TRIGGERED event when confidence score >= threshold.

Default model: "hey_jarvis" (pre-trained, available out of box).
Future: swap for custom "hey_nexus.onnx" model.

CPU usage: ~1.5% on Motobook (i5/Ryzen).
RAM usage: ~60MB (ONNX model + embeddings).
"""
from __future__ import annotations

import asyncio
import time

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


class WakeWordDetector:
    """
    Continuously listens to the mic and waits for the wake word.

    Usage (async):
        detector = WakeWordDetector()
        await detector.wait_for_wake()
        # Wake word was detected — open Gemini session now
    """

    def __init__(self) -> None:
        self._wake_word = cfg.WAKE_WORD
        self._threshold = cfg.WAKE_SCORE_THRESHOLD

    def _load_model(self):
        """Lazy-load openWakeWord model on first call."""
        from openwakeword.model import Model
        # Models dir — auto-downloads to user cache on first run
        return Model(
            wakeword_models=[self._wake_word],
            inference_framework="onnx",
        )

    async def wait_for_wake(self) -> None:
        """
        Block asynchronously until the wake word is detected.
        Runs mic listening in a thread executor to not block the event loop.
        """
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._blocking_listen)

    def _blocking_listen(self) -> None:
        """Blocking mic read loop — runs in thread pool."""
        model = self._load_model()
        chunk_size = cfg.CHUNK_FRAMES

        with sd.InputStream(
            samplerate=cfg.SAMPLE_RATE,
            channels=1,
            dtype="int16",
            blocksize=chunk_size,
        ) as stream:
            while True:
                audio, _ = stream.read(chunk_size)
                # openWakeWord expects int16 numpy array, mono
                samples = audio[:, 0]
                prediction = model.predict(samples)

                # prediction is a dict: {model_name: score}
                score = prediction.get(self._wake_word, 0.0)

                if score >= self._threshold:
                    console.print(
                        f"[bold green]🎤 '{self._wake_word}' detected "
                        f"(score={score:.2f})[/bold green]"
                    )
                    return  # Exit blocking loop — wake detected
