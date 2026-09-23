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
import json
import os
import sys
import tempfile
import threading
import time
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
STATE_FILE = Path.home() / ".gemini" / "logs" / "vocalis_state.json"
_speech_lock = threading.Lock()


def _set_speaking_state(is_speaking: bool, alias: str = "") -> None:
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "is_speaking": is_speaking,
            "pid": os.getpid() if is_speaking else None,
            "alias": alias if is_speaking else "",
            "updated_at": time.time(),
        }
        STATE_FILE.write_text(json.dumps(data), encoding="utf-8")
    except Exception:
        pass


def is_speaking() -> bool:
    """Return True if the assistant is currently speaking audio through the speakers."""
    if STATE_FILE.exists():
        try:
            data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            if data.get("is_speaking") and (time.time() - data.get("updated_at", 0)) < 45:
                return True
        except Exception:
            pass
    return False


def abort_speech() -> bool:
    """
    Acoustic Barge-In: Instantly silence and abort current speaker playback.
    Called by vocalis_daemon.py when the user speaks 'Hey Nexus'.
    """
    try:
        if STATE_FILE.exists():
            try:
                data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
                pid = data.get("pid")
                if pid and pid != os.getpid():
                    import psutil
                    if psutil.pid_exists(pid):
                        psutil.Process(pid).terminate()
            except Exception:
                pass

        if sys.platform == "win32":
            import subprocess
            subprocess.run(["taskkill", "/F", "/IM", "ffplay.exe"], capture_output=True, timeout=2)
            winmm = ctypes.windll.winmm
            # Close all open MCI audio devices instantly
            winmm.mciSendStringW("stop all", None, 0, 0)
            winmm.mciSendStringW("close all", None, 0, 0)
        _set_speaking_state(False)
        return True
    except Exception:
        return False


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


def _amplify_audio(mp3_path: str, gain: float = 4.0) -> str:
    """
    Boost audio volume pre-amplification via ffmpeg if available.
    Uses dynamic audio normalization and peak limiting for maximum acoustic projection.
    Returns path to amplified audio, or original if ffmpeg is unavailable.
    """
    import subprocess
    try:
        boosted = mp3_path.replace(".mp3", "_boosted.mp3")
        res = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                mp3_path,
                "-filter:a",
                f"volume={gain},dynaudnorm=f=75:g=21,alimiter=limit=0.98",
                boosted,
            ],
            capture_output=True,
            timeout=5,
        )
        if res.returncode == 0 and os.path.exists(boosted) and os.path.getsize(boosted) > 0:
            return boosted
    except Exception:
        pass
    return mp3_path


def _play_mp3_native(mp3_path: str) -> bool:
    """
    Play an MP3 file directly through Motobook speakers.
    Primary: ffplay (Rock-solid SDL2/WASAPI pipeline directly to Senary Audio speakers).
    Fallback: winmm.dll legacy MCI.
    """
    final_path = _amplify_audio(mp3_path, gain=4.0)

    # 1. Primary: ffplay (WASAPI direct)
    import subprocess
    try:
        alias = f"voc_ffplay_{os.getpid()}"
        cmd = ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", final_path]
        proc = subprocess.Popen(cmd)
        try:
            STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "is_speaking": True,
                "pid": proc.pid,
                "alias": alias,
                "updated_at": time.time(),
            }
            STATE_FILE.write_text(json.dumps(data), encoding="utf-8")
        except Exception:
            pass
        ret = proc.wait(timeout=30)
        _set_speaking_state(False)
        if ret == 0:
            return True
    except Exception:
        pass
    finally:
        _set_speaking_state(False)
        if final_path != mp3_path and os.path.exists(final_path):
            try:
                os.remove(final_path)
            except Exception:
                pass

    # 2. Secondary Fallback: winmm.dll
    if sys.platform == "win32":
        alias = f"voc_{os.getpid()}_{int(time.time() * 1000) % 100000}"
        try:
            _set_speaking_state(True, alias)
            winmm = ctypes.windll.winmm
            winmm.mciSendStringW(f'open "{mp3_path}" type mpegvideo alias {alias}', None, 0, 0)
            winmm.mciSendStringW(f"setaudio {alias} volume to 1000", None, 0, 0)
            winmm.mciSendStringW(f"play {alias} wait", None, 0, 0)
            winmm.mciSendStringW(f"close {alias}", None, 0, 0)
            return True
        except Exception:
            pass
        finally:
            _set_speaking_state(False)

    return False


def _speak_gtts(text: str, lang: str, tld: str) -> bool:
    """Synthesize voice using Google Assistant TTS."""
    from gtts import gTTS

    tmp = os.path.join(tempfile.gettempdir(), f"voc_gtts_{os.getpid()}_{int(time.time() * 1000) % 10000}.mp3")
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
    """Synthesize voice using Microsoft Edge Neural TTS with high volume gain."""
    import edge_tts

    tmp = os.path.join(tempfile.gettempdir(), f"voc_edge_{os.getpid()}_{int(time.time() * 1000) % 10000}.mp3")
    try:
        comm = edge_tts.Communicate(text, voice_name, volume="+200%")
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


def clean_phonetics(text: str) -> str:
    """
    Sanitize text for clean spoken pronunciation.
    Strips markdown formatting, code ticks, headers, bullet characters, and emojis
    so Text-to-Speech engines do not read out punctuation symbols.
    """
    import re
    if not text:
        return ""
    s = str(text)
    # Remove code blocks and inline code ticks
    s = re.sub(r"```[\s\S]*?```", "", s)
    s = re.sub(r"`([^`]+)`", r"\1", s)
    # Remove markdown links: [label](url) -> label
    s = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", s)
    # Remove markdown headers, bold, italics, strikethrough
    s = re.sub(r"^[#\s]+", "", s, flags=re.MULTILINE)
    s = re.sub(r"[\*_~]", "", s)
    # Remove bullet symbols at line start
    s = re.sub(r"^[\s•\-\*]+\s*", "", s, flags=re.MULTILINE)
    # Strip emojis and common symbol glyphs
    s = re.sub(r"[^\w\s\.,\?!'\":;\-/%$₹]", " ", s)
    # Normalize whitespace
    s = re.sub(r"\s+", " ", s).strip()
    return s


def speak_text(text: str, voice_key: str | None = None, silent: bool = False) -> bool:
    """
    Main speech entrypoint. Synthesizes and plays audio through Motobook speakers.
    """
    if not text or not str(text).strip():
        return False

    raw_text = str(text).strip()
    clean_text = clean_phonetics(raw_text)
    if not clean_text:
        return False

    v_name = (voice_key or get_default_voice()).lower()
    spec = VOICE_MAP.get(v_name, VOICE_MAP["google-in"])

    if not silent:
        print(f"🎙️ Speaking [{v_name}]: \"{clean_text}\"")

    try:
        if spec["type"] == "gtts":
            ok = _speak_gtts(clean_text, spec["lang"], spec["tld"])
        elif spec["type"] == "edge_tts":
            ok = asyncio.run(_speak_edge(clean_text, spec["voice"]))
        else:
            ok = _speak_native_sapi(clean_text)

        if not ok and spec["type"] != "native":
            if not silent:
                print("⚠️ Falling back to native Windows voice...")
            return _speak_native_sapi(clean_text)
        return ok
    except Exception as e:
        if not silent:
            print(f"⚠️ Voice error: {e}. Falling back to native voice...")
        return _speak_native_sapi(clean_text)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Vocalis-Nexus Multi-Voice Synthesizer")
    parser.add_argument("-v", "--voice", choices=list(VOICE_MAP.keys()), help="Choose voice persona")
    parser.add_argument("--set-default", choices=list(VOICE_MAP.keys()), help="Set permanent default voice")
    parser.add_argument("--list", action="store_true", help="List available voice personas")
    parser.add_argument("-t", "--text", dest="text_flag", help="Text message to synthesize (alternative to positional)")
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
    else:
        # Resolve text from either --text flag or positional text arguments
        target_text = args.text_flag or (" ".join(args.text) if args.text else None)
        if target_text:
            speak_text(target_text, voice_key=args.voice)
        else:
            speak_text("Vocalis Nexus online and listening.", voice_key=args.voice)

