#!/usr/bin/env python3
"""
Vocalis-Nexus Smart Desktop Launcher & Global Hotkey Summoner.

Behavior:
1. If Desktop Pet is CLOSED:
   - Launches Desktop Pet Sentinel silently (windowless via pythonw.exe, 0 console flicker).
   - Plays wake chime upon opening.
2. If Desktop Pet is ALREADY OPEN:
   - Functions as an instant Global Push-to-Talk / Evoke trigger!
   - Signals the pet to wake up cyan and open the microphone immediately.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PLUGIN_ROOT))

LOG_DIR = Path.home() / ".gemini" / "logs"
PID_FILE = LOG_DIR / "vocalis_daemon.pid"
EVOKE_FILE = LOG_DIR / "vocalis_evoke.flag"


def is_daemon_running() -> bool:
    if not PID_FILE.exists():
        return False
    try:
        import psutil
        pid = int(PID_FILE.read_text(encoding="utf-8").strip())
        if psutil.pid_exists(pid):
            proc = psutil.Process(pid)
            if "python" in proc.name().lower():
                return True
    except Exception:
        pass
    return False


def main():
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    if is_daemon_running():
        # Daemon is active -> Signal Instant Evoke / Push-to-Talk!
        EVOKE_FILE.write_text("evoke", encoding="utf-8")
        # Play immediate chime feedback
        try:
            from vocalis.tools.notifications import play_wake_chime
            play_wake_chime()
        except Exception:
            pass
    else:
        # Daemon is not active -> Launch silently in background
        daemon_script = PLUGIN_ROOT / "scripts" / "vocalis_daemon.py"

        # Locate pythonw.exe for zero-flicker windowless launch
        pythonw_candidate = Path(sys.executable).parent / "pythonw.exe"
        exe = str(pythonw_candidate) if pythonw_candidate.exists() else sys.executable

        kwargs = {}
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS

        subprocess.Popen([exe, str(daemon_script)], **kwargs)


if __name__ == "__main__":
    main()
