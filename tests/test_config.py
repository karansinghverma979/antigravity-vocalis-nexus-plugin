import os
import pytest


def test_config_defaults(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test_key_dummy_123")
    monkeypatch.setenv("VOCALIS_WAKE_WORD", "hey_jarvis")
    monkeypatch.setenv("VOCALIS_VOICE", "Puck")

    from vocalis.config import Config

    cfg = Config()
    assert cfg.GEMINI_API_KEY == "test_key_dummy_123"
    assert cfg.WAKE_WORD == "hey_jarvis"
    assert cfg.VOICE == "Puck"
    assert cfg.SAMPLE_RATE == 16000
    assert cfg.OUTPUT_SAMPLE_RATE == 24000
    assert cfg.CHUNK_FRAMES == 512
    assert cfg.MODEL == "gemini-3.1-flash-live-preview"
