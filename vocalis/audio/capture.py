"""
vocalis/audio/capture.py — Microphone capture via sounddevice.

Provides a non-blocking async generator that yields raw PCM chunks
(16kHz, 16-bit mono, numpy int16) from the system microphone.

Design:
  - Uses a thread-safe asyncio.Queue as a ring buffer between
    the sounddevice callback thread and the async send loop.
  - Queue size is bounded to prevent memory runaway if the consumer
    (Gemini WebSocket) falls behind.
"""
from __future__ import annotations

import asyncio
import numpy as np
import sounddevice as sd
from typing import AsyncGenerator

from vocalis.config import cfg


class MicCapture:
    """
    Async microphone stream.

    Usage:
        async with MicCapture() as mic:
            async for chunk in mic.stream():
                # chunk: bytes — raw PCM 16kHz 16-bit mono
                await session.send_realtime_input(audio=chunk)
    """

    def __init__(self) -> None:
        self._queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=100)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stream: sd.InputStream | None = None

    def _callback(
        self,
        indata: np.ndarray,
        frames: int,
        time_info: object,
        status: sd.CallbackFlags,
    ) -> None:
        """Called by sounddevice on the audio thread — must be thread-safe."""
        if status:
            pass  # log but never crash
        # Convert float32 → int16 PCM, then to raw bytes
        pcm = (indata[:, 0] * 32767).astype(np.int16).tobytes()
        # Thread-safe put — drop if queue full (prevents memory buildup)
        if self._loop and not self._queue.full():
            self._loop.call_soon_threadsafe(self._queue.put_nowait, pcm)

    async def __aenter__(self) -> "MicCapture":
        self._loop = asyncio.get_running_loop()
        self._stream = sd.InputStream(
            samplerate=cfg.SAMPLE_RATE,
            blocksize=cfg.CHUNK_FRAMES,
            dtype="float32",
            channels=1,
            callback=self._callback,
        )
        self._stream.start()
        return self

    async def __aexit__(self, *args: object) -> None:
        if self._stream:
            self._stream.stop()
            self._stream.close()

    async def stream(self) -> AsyncGenerator[bytes, None]:
        """Yield raw PCM bytes chunks indefinitely."""
        while True:
            chunk = await self._queue.get()
            yield chunk
