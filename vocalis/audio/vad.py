"""
vocalis/audio/vad.py — Silero VAD (Voice Activity Detection).

Uses the Silero VAD ONNX model to classify each 32ms audio frame
as speech or silence. Only speech frames are forwarded to the
Gemini Live API WebSocket — silence is dropped locally.

This is the primary token-cost reduction mechanism.
~85% of idle/ambient audio is suppressed before hitting the network.

Model auto-downloaded from torch.hub on first use, then cached.
"""
from __future__ import annotations

import numpy as np

from vocalis.config import cfg

# Silero VAD uses torch.hub — lazy import to avoid startup cost
_model = None
_utils = None


def _load_model() -> None:
    global _model, _utils
    if _model is not None:
        return
    import torch
    _model, _utils = torch.hub.load(
        repo_or_dir="snakers4/silero-vad",
        model="silero_vad",
        force_reload=False,
        trust_repo=True,
    )


def is_speech(pcm_bytes: bytes) -> bool:
    """
    Return True if this 32ms PCM chunk contains human speech.

    Args:
        pcm_bytes: Raw PCM bytes, 16kHz 16-bit mono (512 samples = ~32ms)

    Returns:
        bool: True if speech probability >= VAD_THRESHOLD (default 0.65)
    """
    import torch
    _load_model()

    audio = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    tensor = torch.from_numpy(audio).unsqueeze(0)  # shape: (1, samples)

    with torch.no_grad():
        prob = _model(tensor, cfg.SAMPLE_RATE).item()

    return prob >= cfg.VAD_THRESHOLD
