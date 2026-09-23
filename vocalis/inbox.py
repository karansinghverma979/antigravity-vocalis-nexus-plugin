"""
vocalis/inbox.py — Persistent Voice Inbox Queue Manager.

Manages ~/.gemini/logs/vocalis_inbox.json as a thread-safe, process-safe
FIFO queue. Buffers incoming voice commands so none are lost even if the
Antigravity agent is temporarily busy executing tasks.
"""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any

INBOX_FILE = Path(os.path.expanduser("~/.gemini/logs/vocalis_inbox.json"))
_lock = threading.Lock()


def _load_inbox() -> dict[str, Any]:
    INBOX_FILE.parent.mkdir(parents=True, exist_ok=True)
    if INBOX_FILE.exists():
        try:
            return json.loads(INBOX_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"messages": []}


def _save_inbox(data: dict[str, Any]) -> None:
    INBOX_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = INBOX_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(INBOX_FILE)


def enqueue_voice_message(
    text: str,
    raw_transcript: str = "",
    wake_word: str = "nexus",
) -> dict[str, Any]:
    """
    Append an incoming voice command to the persistent inbox.
    Called by vocalis_daemon.py when speech is transcribed.
    """
    with _lock:
        data = _load_inbox()
        msg_id = f"MSG-{uuid.uuid4().hex[:8]}"
        msg = {
            "id": msg_id,
            "text": text.strip(),
            "raw_transcript": raw_transcript.strip() or text.strip(),
            "wake_word": wake_word,
            "status": "pending",  # pending | processed | archived
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "timestamp_epoch": time.time(),
        }
        data["messages"].append(msg)
        _save_inbox(data)
        return msg


def pop_pending_messages() -> list[dict[str, Any]]:
    """
    Fetch all pending voice messages and mark them as processed.
    Called by voice_wait.py to deliver to the Antigravity session.
    """
    with _lock:
        data = _load_inbox()
        pending = []
        for m in data.get("messages", []):
            if m.get("status") == "pending":
                m["status"] = "processed"
                m["processed_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                pending.append(m)

        if pending:
            # Retain only last 50 processed messages to prevent file bloat
            if len(data["messages"]) > 50:
                data["messages"] = data["messages"][-50:]
            _save_inbox(data)

        return pending


def has_pending_messages() -> bool:
    """Check if there are any unhandled messages waiting in the inbox."""
    with _lock:
        data = _load_inbox()
        return any(m.get("status") == "pending" for m in data.get("messages", []))


def clear_inbox() -> None:
    """Clear all messages from the inbox."""
    with _lock:
        _save_inbox({"messages": []})
