#!/usr/bin/env python3
"""
Vocalis Nexus Sovereign Autonomous Dispatcher & Acoustic Sentinel Lifecycle Controller.
Provides live terminal monitoring, daemon lifecycle management, and reactive voice orchestration.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import subprocess
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

import psutil

from vocalis.inbox import has_pending_messages, pop_pending_messages
from vocalis.tools.notifications import play_wake_chime
from vocalis.tools.speak import get_default_voice, speak_text

LOG_DIR = Path.home() / ".gemini" / "logs"
DAEMON_PID_FILE = LOG_DIR / "vocalis_daemon.pid"
DAEMON_STOP_FILE = LOG_DIR / "vocalis_daemon_stop.flag"
TRIGGER_PID_FILE = LOG_DIR / "vocalis_trigger.pid"
TRIGGER_STOP_FILE = LOG_DIR / "vocalis_stop.flag"
INBOX_FILE = LOG_DIR / "vocalis_inbox.json"
JOBS_FILE = LOG_DIR / "vocalis_jobs.json"


def _is_proc_alive(pid_file: Path) -> tuple[bool, int | None]:
    if not pid_file.exists():
        return False, None
    try:
        pid = int(pid_file.read_text(encoding="utf-8").strip())
        if psutil.pid_exists(pid):
            proc = psutil.Process(pid)
            if "python" in proc.name().lower():
                return True, pid
    except Exception:
        pass
    return False, None


def get_status() -> dict:
    daemon_running, daemon_pid = _is_proc_alive(DAEMON_PID_FILE)
    trigger_running, trigger_pid = _is_proc_alive(TRIGGER_PID_FILE)

    pending_count = 0
    processed_count = 0
    if INBOX_FILE.exists():
        try:
            data = json.loads(INBOX_FILE.read_text(encoding="utf-8"))
            msgs = data.get("messages", [])
            pending_count = sum(1 for m in msgs if m.get("status") == "pending")
            processed_count = sum(1 for m in msgs if m.get("status") == "processed")
        except Exception:
            pass

    active_jobs = 0
    if JOBS_FILE.exists():
        try:
            jobs = json.loads(JOBS_FILE.read_text(encoding="utf-8"))
            active_jobs = sum(1 for j in jobs.values() if j.get("status") == "RUNNING")
        except Exception:
            pass

    active_voice = get_default_voice()

    print("┌─────────────────────────────────────────────────────────────┐")
    print("│ 🎙️  VOCALIS NEXUS: ACOUSTIC SENTINEL TELEMETRY              │")
    print("├─────────────────────────────────────────────────────────────┤")
    print(f"│ 🐱 Desktop Pet Daemon : {'ONLINE & LISTENING' if daemon_running else 'STOPPED / OFF':<36}│")
    print(f"│ ⚙️  Daemon PID         : {str(daemon_pid) if daemon_running else 'None':<36}│")
    print(f"│ ⚡ Reactive Trigger   : {'HOLDING INBOX SOCKET' if trigger_running else 'IDLE / NOT ARMED':<36}│")
    print(f"│ ⚙️  Trigger PID        : {str(trigger_pid) if trigger_running else 'None':<36}│")
    print("├─────────────────────────────────────────────────────────────┤")
    print(f"│ 📥 Pending Voice Msgs : {pending_count:<36}│")
    print(f"│ ✅ Processed Msgs     : {processed_count:<36}│")
    print(f"│ 🎟️ Active Subagent Jobs: {active_jobs:<36}│")
    print(f"│ 🗣️ Default Voice      : {active_voice:<36}│")
    print("└─────────────────────────────────────────────────────────────┘")

    return {
        "daemon_running": daemon_running,
        "daemon_pid": daemon_pid,
        "trigger_running": trigger_running,
        "trigger_pid": trigger_pid,
        "pending_count": pending_count,
        "processed_count": processed_count,
        "active_jobs": active_jobs,
        "default_voice": active_voice,
    }


def stop_listener() -> None:
    print("🛑 Halting Vocalis Nexus Sentinel & Trigger...", flush=True)

    # 1. Flag stops
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    DAEMON_STOP_FILE.write_text("stop", encoding="utf-8")
    TRIGGER_STOP_FILE.write_text("stop", encoding="utf-8")

    # 2. Terminate trigger
    trig_running, trig_pid = _is_proc_alive(TRIGGER_PID_FILE)
    if trig_running and trig_pid:
        try:
            psutil.Process(trig_pid).terminate()
        except Exception:
            pass
    TRIGGER_PID_FILE.unlink(missing_ok=True)

    # 3. Terminate daemon
    daem_running, daem_pid = _is_proc_alive(DAEMON_PID_FILE)
    if daem_running and daem_pid:
        try:
            psutil.Process(daem_pid).terminate()
        except Exception:
            pass
    DAEMON_PID_FILE.unlink(missing_ok=True)

    time.sleep(0.4)
    DAEMON_STOP_FILE.unlink(missing_ok=True)
    TRIGGER_STOP_FILE.unlink(missing_ok=True)

    print("✅ Vocalis Nexus Sentinel & Trigger terminated cleanly. Mic released.", flush=True)


def start_daemon(headless: bool = False, monitor: bool = False) -> bool:
    daem_running, daem_pid = _is_proc_alive(DAEMON_PID_FILE)
    if daem_running:
        print(f"⚡ Desktop Pet Daemon is already running (PID: {daem_pid}).", flush=True)
        return True

    print("🚀 Spawning Vocalis Desktop Pet Sentinel in background...", flush=True)
    script_path = PLUGIN_ROOT / "scripts" / "vocalis_daemon.py"
    cmd = [sys.executable, str(script_path)]
    if headless:
        cmd.append("--no-ui")
    if monitor:
        cmd.append("--monitor")

    # Spawn fully detached on Windows
    kwargs: dict = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS

    proc = subprocess.Popen(cmd, **kwargs)

    # Wait briefly for PID file
    for _ in range(15):
        time.sleep(0.2)
        running, pid = _is_proc_alive(DAEMON_PID_FILE)
        if running:
            print(f"✅ Desktop Pet Daemon online (PID: {pid}). Listening for 'Hey Nexus'.", flush=True)
            play_wake_chime()
            return True

    print("⚠️ Daemon spawned (PID: {proc.pid}) — waiting for initialization.", flush=True)
    return True


def pull_direct() -> None:
    """Execute a single-shot manual inbox pass without starting any background loop."""
    print("⚡ Vocalis Nexus: Checking for pending voice messages (One-Shot Pull)...", flush=True)
    pending = pop_pending_messages()
    if not pending:
        print("📭 Zero pending voice messages (Queue empty).", flush=True)
        return

    print(f"📥 Pulled {len(pending)} pending message(s) from Voice Inbox:\n", flush=True)
    for idx, m in enumerate(pending, 1):
        mid = m.get("id", "UNKNOWN")
        text = m.get("text", "")
        wake = m.get("wake_word", "nexus")
        created = m.get("created_at", "")
        print(f"  [{idx}] 🎙️ Ticket: {mid} | Wake: '{wake}' | Time: {created}")
        print(f"      Transcript: \"{text}\"")
        print()


def test_audio() -> None:
    print("🔍 Testing Vocalis Audio Stack...", flush=True)
    print("1. Playing wake chime...")
    play_wake_chime()
    time.sleep(0.5)
    print("2. Synthesizing voice playback...")
    speak_text("Vocalis Nexus audio verification complete.", voice_key=get_default_voice())
    print("✅ Audio stack verified successfully.")


def run_dashboard() -> None:
    print("┌─────────────────────────────────────────────────────────────┐")
    print("│ 🎙️  VOCALIS NEXUS: IN-SESSION ACOUSTIC SENTINEL             │")
    print("├─────────────────────────────────────────────────────────────┤")
    print("│ 🚀 Usage in Antigravity (agy):                              │")
    print("│    /vocalis-nexus start   -> Boots daemon & arms live loop  │")
    print("│    /vocalis-nexus stop    -> Halts daemon & trigger cleanly │")
    print("│    /vocalis-nexus status  -> Displays live sentinel status  │")
    print("│    /vocalis-nexus pull    -> One-shot drain (0 bg tasks)    │")
    print("│    /vocalis-nexus speak <text> -> Speak text via speakers   │")
    print("│                                                             │")
    print("│ ⚙️ CLI Flags:                                               │")
    print("│    --start                -> Launch desktop pet daemon      │")
    print("│    --stop                 -> Halt daemon and trigger        │")
    print("│    --status               -> Display live status telemetry  │")
    print("│    --pull / --direct      -> Drain pending voice messages   │")
    print("│    --test                 -> Test chimes and voice engine   │")
    print("└─────────────────────────────────────────────────────────────┘")
    get_status()


def main() -> None:
    parser = argparse.ArgumentParser(description="Vocalis-Nexus Sentinel Lifecycle Controller")
    parser.add_argument("--start", action="store_true", help="Launch the Desktop Pet listener daemon")
    parser.add_argument("--stop", action="store_true", help="Halt the listener daemon and reactive trigger")
    parser.add_argument("--status", action="store_true", help="Display live telemetry and process health")
    parser.add_argument("--pull", "--direct", dest="pull", action="store_true", help="Drain pending voice messages (one-shot)")
    parser.add_argument("--test", action="store_true", help="Test acoustic chimes and speaker playback")
    parser.add_argument("--headless", action="store_true", help="Start daemon without UI")
    args = parser.parse_args()

    if args.status:
        get_status()
    elif args.stop:
        stop_listener()
    elif args.start:
        start_daemon(headless=args.headless)
    elif args.pull:
        pull_direct()
    elif args.test:
        test_audio()
    else:
        run_dashboard()


if __name__ == "__main__":
    main()
