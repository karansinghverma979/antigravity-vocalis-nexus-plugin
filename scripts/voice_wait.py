#!/usr/bin/env python3
"""
Vocalis-Nexus Reactive Event Trigger for Google Antigravity.
(100% Behavioral Parity with Telegram-Nexus poll_wait.py)

Holds silently in the background waiting on the persistent Voice Inbox (~/.gemini/logs/vocalis_inbox.json).
Exits IMMEDIATELY with code 0 when:
1. One or more voice commands are present in the Voice Inbox.
2. A direct single-shot voice prompt is recorded (--direct flag).
3. An explicit stop signal (vocalis_stop.flag) is detected.

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

from vocalis.inbox import pop_pending_messages, has_pending_messages, enqueue_voice_message
from vocalis.tools.notifications import play_wake_chime

LOG_DIR = Path(os.path.expanduser("~/.gemini/logs"))
PID_FILE = LOG_DIR / "vocalis_trigger.pid"
STOP_FILE = LOG_DIR / "vocalis_stop.flag"
JOB_REGISTRY_PATH = LOG_DIR / "vocalis_jobs.json"


def direct_capture_and_exit():
    """Single-shot direct mode: record 1 phrase immediately without wake word, then exit."""
    import collections
    import numpy as np
    import sounddevice as sd
    import speech_recognition as sr

    r = sr.Recognizer()
    sample_rate = 16000
    block_size = 1024
    silence_blocks_threshold = int(0.7 * sample_rate / block_size)
    max_phrase_blocks = int(12.0 * sample_rate / block_size)

    ambient_history = collections.deque(maxlen=40)
    pre_speech_buffer = collections.deque(maxlen=int(0.35 * sample_rate / block_size))

    try:
        play_wake_chime()
        with sd.InputStream(samplerate=sample_rate, channels=1, dtype="int16", blocksize=block_size) as stream:
            # Quick 0.3s noise calibration
            for _ in range(int(0.3 * sample_rate / block_size)):
                data, _ = stream.read(block_size)
                samples = data[:, 0].astype(np.float32)
                ambient_history.append(float(np.sqrt(np.mean(samples ** 2))))

            is_recording = False
            speech_buffer = []
            silence_counter = 0
            timeout_epoch = time.time() + 7.0

            while True:
                if not is_recording and time.time() > timeout_epoch:
                    raise TimeoutError("No speech detected within timeout.")

                data, _ = stream.read(block_size)
                samples = data[:, 0].astype(np.float32)
                rms = float(np.sqrt(np.mean(samples ** 2)))

                if not is_recording:
                    ambient_history.append(rms)
                    ambient_floor = sum(ambient_history) / max(1, len(ambient_history))
                    threshold = max(25.0, ambient_floor * 3.2)
                    pre_speech_buffer.append(data.tobytes())

                    if rms > threshold:
                        is_recording = True
                        speech_buffer = list(pre_speech_buffer)
                        speech_buffer.append(data.tobytes())
                        silence_counter = 0
                else:
                    speech_buffer.append(data.tobytes())
                    ambient_floor = sum(ambient_history) / max(1, len(ambient_history))
                    threshold = max(25.0, ambient_floor * 3.2)

                    if rms < threshold:
                        silence_counter += 1
                    else:
                        silence_counter = 0

                    if silence_counter >= silence_blocks_threshold or len(speech_buffer) >= max_phrase_blocks:
                        break

            raw_pcm = b"".join(speech_buffer)
            audio_data = sr.AudioData(raw_pcm, sample_rate, 2)
            text = r.recognize_google(audio_data, language="en-IN").strip()

            msg = {
                "id": "MSG-DIRECT",
                "text": text,
                "raw_transcript": text,
                "wake_word": "direct",
                "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
            }
            print(json.dumps({
                "event": "VOICE_INPUT",
                "messages": [msg],
                "count": 1,
            }, ensure_ascii=False), flush=True)
            sys.exit(0)
    except Exception as e:
        print(json.dumps({
            "event": "DIRECT_TIMEOUT",
            "message": str(e),
        }, ensure_ascii=False), flush=True)
        sys.exit(0)


def run_trigger():
    # Clear any stale stop flag
    if STOP_FILE.exists():
        STOP_FILE.unlink(missing_ok=True)

    # Acquire PID lock to avoid duplicate trigger scripts
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    if PID_FILE.exists():
        try:
            with open(PID_FILE, "r", encoding="utf-8") as f:
                existing_pid = int(f.read().strip())
            import psutil
            if existing_pid != os.getpid() and psutil.pid_exists(existing_pid):
                proc = psutil.Process(existing_pid)
                if "python" in proc.name().lower():
                    # Another trigger instance is already holding the inbox socket
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

            # 2. Check for active background jobs reaching the 4-minute threshold
            if JOB_REGISTRY_PATH.exists():
                try:
                    with open(JOB_REGISTRY_PATH, "r", encoding="utf-8") as f:
                        jobs = json.load(f)
                    now_epoch = time.time()
                    for j_id, j_data in jobs.items():
                        if j_data.get("status") in ("in_progress", "RUNNING") and not j_data.get("heartbeat_4m_sent"):
                            created_epoch = j_data.get("created_at_epoch")
                            if created_epoch and (now_epoch - created_epoch) >= 240:
                                j_data["heartbeat_4m_sent"] = True
                                with open(JOB_REGISTRY_PATH, "w", encoding="utf-8") as f_out:
                                    json.dump(jobs, f_out, indent=2, ensure_ascii=False)
                                payload = {
                                    "event": "JOB_HEARTBEAT_4M",
                                    "job_id": j_id,
                                    "task": j_data.get("task") or j_data.get("title", ""),
                                    "elapsed_seconds": int(now_epoch - created_epoch),
                                }
                                print(json.dumps(payload, ensure_ascii=False), flush=True)
                                sys.exit(0)
                except Exception:
                    pass

            # 3. Check the persistent voice inbox
            if has_pending_messages():
                pending = pop_pending_messages()
                if pending:
                    # Output structured payload and exit 0 -> wakes up Antigravity agent!
                    payload = {
                        "event": "VOICE_INPUT",
                        "messages": pending,
                        "count": len(pending),
                    }
                    print(json.dumps(payload, ensure_ascii=False), flush=True)
                    sys.exit(0)

            # Hold silently, poll every 100ms
            time.sleep(0.1)

    finally:
        if PID_FILE.exists():
            try:
                with open(PID_FILE, "r", encoding="utf-8") as f:
                    if int(f.read().strip()) == os.getpid():
                        PID_FILE.unlink(missing_ok=True)
            except Exception:
                pass


def main():
    parser = argparse.ArgumentParser(description="Vocalis-Nexus Reactive Event Trigger")
    parser.add_argument("--direct", action="store_true", help="Single-shot direct mode: listen immediately without waiting for daemon")
    args = parser.parse_args()

    if args.direct:
        direct_capture_and_exit()
    else:
        run_trigger()


if __name__ == "__main__":
    main()
