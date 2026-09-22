import pytest
from vocalis.tools.notifications import _generate_tone


def test_generate_tone():
    tone = _generate_tone(440.0, 0.1, sample_rate=24000)
    assert isinstance(tone, bytes)
    # 24,000 samples/sec * 0.1 sec * 2 bytes/sample (16-bit) = 4,800 bytes
    assert len(tone) == int(24000 * 0.1 * 2)
