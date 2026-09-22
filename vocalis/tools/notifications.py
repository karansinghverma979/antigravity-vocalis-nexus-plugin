"""
vocalis/tools/notifications.py — Native acoustic feedback & chimes.

Generates smooth sine-wave tones using pure standard library (math + struct)
with optional sounddevice / numpy / winsound acceleration.
No external MP3/WAV assets required — works completely offline and standalone.
Gracefully handles headless environments (CI) or missing audio output.
"""
from __future__ import annotations

import math
import struct
import sys
from typing import Any

from vocalis.config import cfg


def _generate_tone(
    freq: float,
    duration_s: float,
    sample_rate: int = 24_000,
    fade_ms: float = 15.0,
) -> bytes:
    """Generate a clean 16-bit mono PCM sine wave with gentle fade-in and fade-out."""
    total_samples = int(sample_rate * duration_s)
    fade_samples = int(sample_rate * (fade_ms / 1000.0))
    raw = bytearray()

    for i in range(total_samples):
        mult = 1.0
        if fade_samples > 0:
            if i < fade_samples:
                mult = i / fade_samples
            elif i > total_samples - fade_samples:
                mult = max(0.0, (total_samples - i) / fade_samples)

        val = int(0.3 * mult * math.sin(2.0 * math.pi * freq * (i / sample_rate)) * 32767)
        clamped = max(-32768, min(32767, val))
        raw.extend(struct.pack("<h", clamped))

    return bytes(raw)


def _play_pcm(pcm_data: bytes, sample_rate: int = 24_000) -> None:
    """Attempt playback through sounddevice; falls back gracefully to winsound or no-op."""
    try:
        import sounddevice as sd
        import numpy as np
        arr = np.frombuffer(pcm_data, dtype=np.int16)
        sd.play(arr, samplerate=sample_rate, blocking=False)
        return
    except Exception:
        pass

    # Windows fallback: winsound beep
    if sys.platform == "win32":
        try:
            import winsound
            winsound.Beep(750, 100)
        except Exception:
            pass


def play_wake_chime() -> None:
    """Ascending two-tone chime (440Hz -> 880Hz) to signal wake word detected."""
    t1 = _generate_tone(440.0, 0.09)
    gap = b"\x00\x00" * int(24_000 * 0.02)
    t2 = _generate_tone(880.0, 0.12)
    _play_pcm(t1 + gap + t2)


def play_completion_chime() -> None:
    """Soft three-tone chord (C5 -> E5 -> G5) to signal background job completed."""
    t1 = _generate_tone(523.25, 0.08)
    gap = b"\x00\x00" * int(24_000 * 0.015)
    t2 = _generate_tone(659.25, 0.08)
    t3 = _generate_tone(783.99, 0.15)
    _play_pcm(t1 + gap + t2 + gap + t3)


def play_error_chime() -> None:
    """Descending tone (550Hz -> 330Hz) to signal error or disconnection."""
    t1 = _generate_tone(550.0, 0.12)
    gap = b"\x00\x00" * int(24_000 * 0.02)
    t2 = _generate_tone(330.0, 0.16)
    _play_pcm(t1 + gap + t2)
