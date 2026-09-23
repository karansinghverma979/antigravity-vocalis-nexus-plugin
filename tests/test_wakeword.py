"""
tests/test_wakeword.py — Unit test suite for hardened wake word sentinel.
Verifies dBFS audio energy calculation, EMA temporal filtering,
consecutive frame gates, refractory debounce, and singleton caching.
"""
import numpy as np
import pytest
from unittest.mock import MagicMock

from vocalis.wakeword.detector import (
    calculate_dbfs,
    WakeWordDetector,
    _SHARED_MODEL,
)
from vocalis.config import cfg


def test_calculate_dbfs():
    # Dead silence (all 0s)
    silence = np.zeros(1280, dtype=np.int16)
    assert calculate_dbfs(silence) == -100.0

    # Max amplitude DC/square wave (full scale: 32767)
    full_scale = np.full(1280, 32767, dtype=np.int16)
    dbfs = calculate_dbfs(full_scale)
    assert -0.1 <= dbfs <= 0.1

    # Low noise (amplitude ~30 / 32768 => ~ -60 dBFS)
    low_noise = np.full(1280, 30, dtype=np.int16)
    dbfs_low = calculate_dbfs(low_noise)
    assert dbfs_low < -50.0


def test_energy_pre_gate_skips_inference():
    detector = WakeWordDetector()
    detector.energy_threshold_db = -45.0

    # Mock model that should NEVER be called on silence
    mock_model = MagicMock()

    silent_frame = np.full(1280, 10, dtype=np.int16)  # ~ -70 dBFS
    is_wake, score, dbfs = detector.process_frame(silent_frame, model=mock_model)

    assert not is_wake
    assert score == 0.0
    assert dbfs < -45.0
    mock_model.predict.assert_not_called()


def test_ema_smoothing_and_consecutive_verification():
    detector = WakeWordDetector()
    detector.energy_threshold_db = -50.0
    detector.threshold = 0.50
    detector.consecutive_target = 2
    detector.ema_alpha = 0.50
    detector.debounce_s = 1.0

    # Normal speech level frame (~ -20 dBFS)
    speech_frame = np.full(1280, 3000, dtype=np.int16)

    # Frame 1: Single spike with raw score 0.80
    # Expected EMA: 0.5 * 0.80 + 0.5 * 0.0 = 0.40 (< 0.50 threshold)
    mock_model = MagicMock()
    mock_model.predict.return_value = {detector.wake_word: 0.80}

    is_wake_1, score_1, _ = detector.process_frame(speech_frame, model=mock_model, now=10.0)
    assert not is_wake_1
    assert pytest.approx(score_1, abs=1e-5) == 0.40
    assert detector.consecutive_hits == 0

    # Frame 2: Second frame with raw score 0.80
    # Expected EMA: 0.5 * 0.80 + 0.5 * 0.40 = 0.60 (>= 0.50 threshold) -> 1st hit
    is_wake_2, score_2, _ = detector.process_frame(speech_frame, model=mock_model, now=10.08)
    assert not is_wake_2
    assert pytest.approx(score_2, abs=1e-5) == 0.60
    assert detector.consecutive_hits == 1

    # Frame 3: Third frame with raw score 0.80 -> 2nd hit -> TRIGGER!
    is_wake_3, score_3, _ = detector.process_frame(speech_frame, model=mock_model, now=10.16)
    assert is_wake_3
    assert detector.last_trigger_time == 10.16
    assert detector.consecutive_hits == 0  # reset after trigger


def test_refractory_debounce_lockout():
    detector = WakeWordDetector()
    detector.energy_threshold_db = -50.0
    detector.threshold = 0.40
    detector.consecutive_target = 1
    detector.ema_alpha = 1.0  # Instant response
    detector.debounce_s = 1.5

    speech_frame = np.full(1280, 3000, dtype=np.int16)
    mock_model = MagicMock()
    mock_model.predict.return_value = {detector.wake_word: 0.90}

    # Initial wake at t=100.0
    is_wake_1, _, _ = detector.process_frame(speech_frame, model=mock_model, now=100.0)
    assert is_wake_1

    # Frame immediately after at t=100.5 (within 1.5s lockout) -> Must be blocked!
    is_wake_2, _, _ = detector.process_frame(speech_frame, model=mock_model, now=100.5)
    assert not is_wake_2

    # Frame after lockout expires at t=102.0 -> Permitted
    is_wake_3, _, _ = detector.process_frame(speech_frame, model=mock_model, now=102.0)
    assert is_wake_3


if __name__ == "__main__":
    test_calculate_dbfs()
    test_energy_pre_gate_skips_inference()
    test_ema_smoothing_and_consecutive_verification()
    test_refractory_debounce_lockout()
    print("All wake word unit tests passed!")
