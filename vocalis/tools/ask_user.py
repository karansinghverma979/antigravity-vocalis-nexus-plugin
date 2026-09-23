"""
vocalis/tools/ask_user.py — Agent-Initiated Two-Way Voice Conversation Engine.

Allows the Antigravity agent to:
  1. Speak a clarifying question or request aloud via TTS.
  2. Immediately trigger the Vocalis Pet mic (no wake word needed).
  3. Wait for Karan's voice response (up to timeout_s seconds).
  4. Return the transcribed reply as a plain string.

Usage (from agent / dispatcher):
    from vocalis.tools.ask_user import ask_user
    answer = ask_user("Which folder should I save it to?", timeout_s=30)
    print(answer)  # → "save it in downloads"

Architecture:
  - Writes EVOKE_FILE to signal the daemon's audio_listener_worker to start
    listening immediately (same path as desktop-pet click-to-evoke).
  - Polls vocalis_inbox.json for a NEW pending message (created after the
    evoke timestamp) with a configurable timeout.
  - Cleans up: marks the reply message as "processed" so the dispatcher
    does not re-process it as a normal voice command.
"""
from __future__ import annotations

import time
import threading
from pathlib import Path

LOG_DIR = Path.home() / ".gemini" / "logs"
EVOKE_FILE = LOG_DIR / "vocalis_evoke.flag"


def ask_user(
    question: str,
    timeout_s: float = 30.0,
    agent_label: str = "AI",
) -> str:
    """
    Speak a question and capture the user's voice reply.

    Args:
        question:    Text the agent speaks aloud before opening mic.
        timeout_s:   Max seconds to wait for a reply (default 30s).
        agent_label: Short label shown on pet HUD, e.g. "AI asking...".

    Returns:
        Transcribed reply text, or "" if no response before timeout.
    """
    from vocalis.tools.speak import speak_text
    from vocalis.tools.notifications import play_wake_chime
    from vocalis.inbox import _load_inbox, _save_inbox, _lock

    # ── 1. Speak the question aloud ──────────────────────────────────────────
    play_wake_chime()
    speak_text(question)

    # ── 2. Record the timestamp so we can detect the NEW reply message ────────
    evoke_ts = time.time()

    # ── 3. Touch the EVOKE_FILE → daemon opens mic in ≤40ms ─────────────────
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    EVOKE_FILE.touch()

    # ── 4. Poll inbox for a new pending message created AFTER evoke_ts ───────
    deadline = evoke_ts + timeout_s
    while time.time() < deadline:
        time.sleep(0.4)  # check 2.5x per second — low CPU, fast enough
        with _lock:
            data = _load_inbox()
            messages = data.get("messages", [])

        for msg in reversed(messages):  # newest first
            # Only pick up messages created after we opened the mic
            if (
                msg.get("status") == "pending"
                and float(msg.get("timestamp_epoch", 0)) > evoke_ts
            ):
                # Mark as processed so dispatcher ignores it
                with _lock:
                    data2 = _load_inbox()
                    for m in data2.get("messages", []):
                        if m.get("id") == msg["id"]:
                            m["status"] = "processed"
                            m["processed_by"] = "ask_user"
                            break
                    _save_inbox(data2)

                return msg.get("text", "").strip()

    # ── 5. Timeout — clean up evoke file if still present ────────────────────
    EVOKE_FILE.unlink(missing_ok=True)
    return ""


def ask_user_async(
    question: str,
    callback,
    timeout_s: float = 30.0,
) -> threading.Thread:
    """
    Non-blocking version. Calls callback(answer: str) when response arrives.
    Returns the background thread in case caller wants to join().

    Example:
        def on_answer(text):
            print(f"User said: {text}")
        ask_user_async("Which file?", callback=on_answer)
    """
    def _run():
        answer = ask_user(question, timeout_s=timeout_s)
        try:
            callback(answer)
        except Exception:
            pass

    t = threading.Thread(target=_run, daemon=True, name="ask_user_async")
    t.start()
    return t
