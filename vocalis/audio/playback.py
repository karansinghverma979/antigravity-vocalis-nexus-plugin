"""
vocalis/audio/playback.py — Speaker output with instant barge-in flushing.

Receives PCM chunks (24kHz, 16-bit mono bytes) from Gemini Live API
and plays them through the system speaker.

Critical design: on barge-in (user speaks while Nexus is talking),
the playback queue must be flushed instantly — zero lingering audio.
"""
from __future__ import annotations

import asyncio
import queue
import threading

import numpy as np
import sounddevice as sd

from vocalis.config import cfg


class AudioPlayer:
    """
    Thread-backed PCM speaker output.

    Usage:
        player = AudioPlayer()
        player.start()
        player.enqueue(pcm_bytes)   # from Gemini receive loop
        player.interrupt()           # on barge-in signal
        player.stop()
    """

    def __init__(self) -> None:
        self._queue: queue.Queue[bytes | None] = queue.Queue(maxsize=200)
        self._thread: threading.Thread | None = None
        self._running = False
        self._stream: sd.OutputStream | None = None

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._playback_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        self._queue.put(None)  # Sentinel to unblock thread
        if self._thread:
            self._thread.join(timeout=2.0)

    def enqueue(self, pcm_bytes: bytes) -> None:
        """Queue PCM audio for playback — drops silently if queue is full."""
        if self._running:
            try:
                self._queue.put_nowait(pcm_bytes)
            except queue.Full:
                pass

    def interrupt(self) -> None:
        """
        Barge-in: instantly flush the playback queue and stop current audio.
        Called when Gemini sends server_content.interrupted = True,
        or when the VAD detects user speech during playback.
        """
        # Drain all pending audio chunks
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

    def _playback_loop(self) -> None:
        """Runs on a dedicated thread — pulls chunks and plays them."""
        with sd.OutputStream(
            samplerate=cfg.OUTPUT_SAMPLE_RATE,
            channels=1,
            dtype="int16",
        ) as stream:
            while self._running:
                chunk = self._queue.get()
                if chunk is None:
                    break
                audio = np.frombuffer(chunk, dtype=np.int16)
                stream.write(audio)
