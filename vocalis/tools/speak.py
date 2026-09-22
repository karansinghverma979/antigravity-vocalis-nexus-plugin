"""
vocalis/tools/speak.py — Multi-Persona Voice Synthesis & Speaker Output.

Supports:
1. Google Assistant (Indian English / Hindi via gTTS)
2. Microsoft Edge Neural Voices (Madhur, Jarvis/Prabhat, Neerja, Ava, Brian)
3. Windows Native SAPI (Offline fallback)

Playback directly through Motobook speakers using native Windows winmm.dll (0 tokens).
"""
from __future__ import annotations

import asyncio
import ctypes
import os
import sys
import tempfile
from pathlib import Path

# Force UTF-8 on Windows
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

VOICE_MAP = {
    "google-in": {
        "type": "gtts",
        "lang": "en",
        "tld": "co.in",
        "desc": "Google Assistant (Indian English) [Default ⭐]",
    },
    "google-hi": {
        "type": "gtts",
        "lang": "hi",
        "tld": "co.in",
        "desc": "Google Assistant (Hindi)",
    },
    "madhur": {
        "type": "edge_tts",
        "voice": "hi-IN-MadhurNeural",
        "desc": "Madhur (Hindi/English Neural Male - Warm & Expressive)",
    },
    "jarvis": {
        "type": "edge_tts",
        "voice": "en-IN-PrabhatNeural",
        "desc": "Jarvis / Prabhat (Indian English Male - Assistant)",
    },
    "neerja": {
        "type": "edge_tts",
        "voice": "en-IN-NeerjaExpressiveNeural",
        "desc": "Neerja (Indian English Female - Expressive)",
    },
    "ava": {
        "type": "edge_tts",
        "voice": "en-US-AvaMultilingualNeural",
        "desc": "Ava (US Female - Natural & Modern)",
    },
    "brian": {
        "type": "edge_tts",
        "voice": "en-US-BrianMultilingualNeural",
        "desc": "Brian (US Male - Clear & Authoritative)",
    },
    "native": {
        "type": "native",
        "desc": "Windows Native SpeechSynthesizer (100% Offline)",
    },
}

CONFIG_FILE = Path.home() / ".gemini" / "config" / "vocalis_voice.txt"


def get_default_voice() -> str:
    """Read saved default voice persona or fallback to google-in."""
    env_v = os.environ.get("VOCALIS_VOICE", "").strip().lower()
    if env_v in VOICE_MAP:
        return env_v

    if CONFIG_FILE.exists():
        try:
            val = CONFIG_FILE.read_text(encoding="utf-8").strip().lower()
            if val in VOICE_MAP:
                return val
        except Exception:
            pass

    return "google-in"


def set_default_voice(voice_name: str) -> bool:
    """Save the default voice persona permanently."""
    key = voice_name.strip().lower()
    if key not in VOICE_MAP:
        return False
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(key, encoding="utf-8")
    return True


def _play_mp3_native(mp3_path: str) -> bool:
    """Play an MP3 file directly through Motobook speakers using winmm.dll."""
    if sys.platform != "win32":
        return False

    try:
        winmm = ctypes.windll.winmm
        alias = f"voc_{os.getpid()}_{int(tempfile.time.time() * 1000) % 100000}"
        winmm.mciSendStringW(f'open "{mp3_path}" type mpegvideo alias {alias}', None, 0, 0)
        winmm.mciSendStringW(f"play {alias} wait", None, 0, 0)
        winmm.mciSendStringW(f"close {alias}", None, 0, 0)
        return True
    except Exception:
        return False


def _speak_gtts(text: str, lang: str, tld: str) -> bool:
    """Synthesize voice using Google Assistant TTS."""
    from gtts import gTTS

    tmp = os.path.join(tempfile.gettempdir(), f"voc_gtts_{os.getpid()}.mp3")
    try:
        tts = gTTS(text=text, lang=lang, tld=tld, slow=False)
        tts.save(tmp)
        return _play_mp3_native(tmp)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except Exception:
                pass


async def _speak_edge(text: str, voice_name: str) -> bool:
    """Synthesize voice using Microsoft Edge Neural TTS."""
    import edge_tts

    tmp = os.path.join(tempfile.gettempdir(), f"voc_edge_{os.getpid()}.mp3")
    try:
        comm = edge_tts.Communicate(text, voice_name, volume="+140%")
        await comm.save(tmp)
        return _play_mp3_native(tmp)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except Exception:
                pass


def _speak_native_sapi(text: str) -> bool:
    """Fallback: Windows SAPI SpeechSynthesizer."""
    import subprocess
    clean_text = text.replace('"', '""').replace("'", "''").strip()
    cmd = (
        "Add-Type -AssemblyName System.Speech; "
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        f"$s.Speak('{clean_text}');"
    )
    res = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True)
    return res.returncode == 0


def speak_text(text: str, voice_key: str | None = None) -> bool:
    """
    Main speech entrypoint. Synthesizes and plays audio through Motobook speakers.
    """
    if not text or not str(text).strip():
        return False

    clean_text = str(text).strip()
    v_name = (voice_key or get_default_voice()).lower()
    spec = VOICE_MAP.get(v_name, VOICE_MAP["google-in"])

    try:
        if spec["type"] == "gtts":
            return _speak_gtts(clean_text, spec["lang"], spec["tld"])
        elif spec["type"] == "edge_tts":
            return asyncio.run(_speak_edge(clean_text, spec["voice"]))
        else:
            return _speak_native_sapi(clean_text)
    except Exception:
        # Graceful fallback to native Windows voice
        return _speak_native_sapi(clean_text)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Vocalis-Nexus Multi-Voice Synthesizer")
    parser.add_argument("-v", "--voice", choices=list(VOICE_MAP.keys()), help="Choose voice persona")
    parser.add_argument("--set-default", choices=list(VOICE_MAP.keys()), help="Set permanent default voice")
    parser.add_argument("--list", action="store_true", help="List available voice personas")
    parser.add_argument("text", nargs="*", help="Text message to synthesize")
    args = parser.parse_args()

    if args.list:
        cur = get_default_voice()
        print("\nAvailable Vocalis Voice Personas:")
        print("──────────────────────────────────────────────────────────────────")
        for k, v in VOICE_MAP.items():
            mark = "⭐ (Default)" if k == cur else ""
            print(f"  • {k:<12} │ {v['desc']} {mark}")
        print("──────────────────────────────────────────────────────────────────\n")
    elif args.set_default:
        set_default_voice(args.set_default)
        print(f"Default voice set to: {args.set_default}")
        speak_text(f"Voice persona {args.set_default} set as default.", voice_key=args.set_default)
    elif args.text:
        msg = " ".join(args.text)
        speak_text(msg, voice_key=args.voice)
    else:
        speak_text("Vocalis Nexus online and listening.", voice_key=args.voice)
