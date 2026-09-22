#!/usr/bin/env python3
"""
Vocalis-Nexus Reactive Voice Trigger for Google Antigravity.

Holds the microphone listener silently in the background.
Exits IMMEDIATELY with code 0 when:
1. Speech is detected and transcribed via the zero-token Chromium STT endpoint.
2. An explicit stop signal (vocalis_stop.flag) is detected.

When this script exits with code 0, Antigravity CLI's reactive engine automatically
wakes up the live vocalis_nexus agent in the terminal window with full context intact!
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
import time
from pathlib import Path

# Force UTF-8 on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PLUGIN_ROOT))

from vocalis.tools.notifications import play_wake_chime, play_error_chime

LOG_DIR = Path(os.path.expanduser("~/.gemini/logs"))
PID_FILE = LOG_DIR / "vocalis_trigger.pid"
STOP_FILE = LOG_DIR / "vocalis_stop.flag"


def listen_for_speech(require_wake_word: bool = True, timeout_s: float = 30.0) -> dict | None:
    """
    Listen to the microphone and transcribe speech using the zero-token browser endpoint.
    """
    import speech_recognition as sr

    r = sr.Recognizer()
    r.dynamic_energy_threshold = True
    r.pause_threshold = 0.8  # Stop recording after 0.8s of silence

    try:
        with sr.Microphone(sample_rate=16000) as source:
            # Quick 0.3s ambient noise calibration
            r.adjust_for_ambient_noise(source, duration=0.3)

            # Listen for speech phrase
            audio = r.listen(source, timeout=timeout_s, phrase_time_limit=15.0)

            # Transcribe via Chromium speech endpoint (0 tokens, 0 API keys)
            raw_text = r.recognize_google(audio, language="en-IN")
            if not raw_text or not raw_text.strip():
                return None

            clean = raw_text.strip()
            lower = clean.lower()

            # Wake word filtering if required
            wake_words = ["nexus", "jarvis", "hey nexus", "hey jarvis", "ok nexus", "alexa"]
            matched_wake = None

            if require_wake_word:
                for w in wake_words:
                    if w in lower:
                        matched_wake = w
                        break
                if not matched_wake:
                    # Speech was spoken, but wake word was not present; ignore
                    return None

                # Extract command after wake word
                idx = lower.find(matched_wake) + len(matched_wake)
                command = clean[idx:].strip(" ,.?!")
                if not command:
                    command = "status"  # default if user just said "Hey Nexus"
            else:
                command = clean

            # Play wake chime confirmation
            play_wake_chime()

            return {
                "event": "VOICE_INPUT",
                "text": command,
                "raw_transcript": clean,
                "wake_word_detected": matched_wake or "direct",
                "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
            }

    except sr.WaitTimeoutError:
        return None
    except sr.UnknownValueError:
        return None
    except Exception as e:
        return None


def run_trigger(direct_mode: bool = False):
    # Clear any stale stop flag
    if STOP_FILE.exists():
        STOP_FILE.unlink(missing_ok=True)

    # Acquire PID lock to avoid duplicate mic listeners
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    if PID_FILE.exists():
        try:
            with open(PID_FILE, "r", encoding="utf-8") as f:
                existing_pid = int(f.read().strip())
            import psutil
            if existing_pid != os.getpid() and psutil.pid_exists(existing_pid):
                proc = psutil.Process(existing_pid)
                if "python" in proc.name().lower():
                    # Another instance is already actively holding the mic
                    print(json.dumps({"event": "ALREADY_LISTENING", "pid": existing_pid}, ensure_ascii=False), flush=True)
                    sys.exit(0)
        except Exception:
            pass

    with open(PID_FILE, "w", encoding="utf-8") as f:
        f.write(str(os.getpid()))

    try:
        while True:
            # 1. Check for explicit stop request
            if STOP_FILE.exists():
                STOP_FILE.unlink(missing_ok=True)
                print(json.dumps({"event": "STOP_REQUESTED"}, ensure_ascii=False), flush=True)
                sys.exit(0)

            # 2. Listen for speech
            # In direct mode: do not require wake word (listen immediately)
            # In loop mode: require "nexus" or "jarvis"
            require_wake = not direct_mode
            result = listen_for_speech(require_wake_word=require_wake, timeout_s=5.0)

            if result:
                # Speech captured and transcribed!
                # Output JSON payload and exit Code 0 -> wakes up Antigravity agent!
                print(json.dumps(result, ensure_ascii=False), flush=True)
                sys.exit(0)

            if direct_mode:
                # In direct mode, exit if no speech within timeout
                print(json.dumps({"event": "DIRECT_TIMEOUT", "message": "No speech detected."}, ensure_ascii=False), flush=True)
                sys.exit(0)

            # Tiny sleep to avoid spinning CPU
            time.sleep(0.1)

    finally:
        # Release PID lock on exit
        if PID_FILE.exists():
            try:
                with open(PID_FILE, "r", encoding="utf-8") as f:
                    if int(f.read().strip()) == os.getpid():
                        PID_FILE.unlink(missing_ok=True)
            except Exception:
                pass


def main():
    parser = argparse.ArgumentParser(description="Vocalis-Nexus Reactive Voice Trigger")
    parser.add_argument("--direct", action="store_true", help="Single-shot direct mode: listen immediately without wake word")
    args = parser.parse_args()

    run_trigger(direct_mode=args.direct)


if __name__ == "__main__":
    main()
