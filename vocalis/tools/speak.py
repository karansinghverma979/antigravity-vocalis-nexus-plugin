"""
vocalis/tools/speak.py — Native Windows Speech Synthesis (TTS).

Uses Windows built-in SpeechSynthesizer (System.Speech.Synthesis).
100% offline, zero API keys, zero token consumption, instant playback.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def speak_text(text: str, voice_gender: str = "Neutral") -> bool:
    """
    Speak text out loud through workstation speakers using Windows native TTS.
    Runs non-blocking or synchronously.
    """
    if not text or not text.strip():
        return False

    clean_text = text.replace('"', '""').replace("'", "''").strip()

    if sys.platform == "win32":
        # PowerShell command calling .NET SpeechSynthesizer
        ps_cmd = (
            "Add-Type -AssemblyName System.Speech; "
            "$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            "$synth.Rate = 1; "
            "$synth.Volume = 100; "
            f"$synth.Speak('{clean_text}');"
        )
        try:
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                timeout=30,
            )
            return res.returncode == 0
        except Exception:
            return False
    else:
        # Linux fallback via espeak or speech-dispatcher
        try:
            subprocess.run(["espeak", clean_text], capture_output=True, timeout=15)
            return True
        except Exception:
            return False


if __name__ == "__main__":
    if len(sys.argv) > 1:
        msg = " ".join(sys.argv[1:])
        speak_text(msg)
    else:
        speak_text("Vocalis Nexus online and listening.")
