import json
import tempfile
from pathlib import Path
import pytest


def test_inbox_queue_lifecycle(tmp_path, monkeypatch):
    test_inbox_file = tmp_path / "vocalis_inbox.json"
    monkeypatch.setattr("vocalis.inbox.INBOX_FILE", test_inbox_file)

    from vocalis.inbox import (
        enqueue_voice_message,
        pop_pending_messages,
        has_pending_messages,
        clear_inbox,
    )

    # 1. Initially empty
    assert has_pending_messages() is False
    assert pop_pending_messages() == []

    # 2. Enqueue first message
    m1 = enqueue_voice_message("check RAM usage", "hey nexus check RAM usage", "nexus")
    assert m1["id"].startswith("MSG-")
    assert m1["text"] == "check RAM usage"
    assert has_pending_messages() is True

    # 3. Enqueue second message (multi-command buffering)
    m2 = enqueue_voice_message("run memory trim", "hey jarvis run memory trim", "jarvis")
    assert m2["id"].startswith("MSG-")

    # 4. Pop pending messages
    pending = pop_pending_messages()
    assert len(pending) == 2
    assert pending[0]["text"] == "check RAM usage"
    assert pending[1]["text"] == "run memory trim"

    # 5. Subsequent pop is empty
    assert has_pending_messages() is False
    assert pop_pending_messages() == []

    # 6. Verify file persistence
    data = json.loads(test_inbox_file.read_text(encoding="utf-8"))
    assert len(data["messages"]) == 2
    assert all(m["status"] == "processed" for m in data["messages"])


def test_acoustic_barge_in_state(tmp_path, monkeypatch):
    test_state_file = tmp_path / "vocalis_state.json"
    monkeypatch.setattr("vocalis.tools.speak.STATE_FILE", test_state_file)

    from vocalis.tools.speak import is_speaking, abort_speech, _set_speaking_state

    # Initially false
    assert is_speaking() is False

    # Simulate active speech playback
    _set_speaking_state(True, "test_alias_1")
    assert is_speaking() is True

    # Trigger Barge-In
    ok = abort_speech()
    assert ok is True
    assert is_speaking() is False
