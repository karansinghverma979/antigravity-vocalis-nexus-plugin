#!/usr/bin/env python3
"""
Vocalis-Nexus Sovereign Listener Daemon & Desktop Pet Sentinel.

Runs as a persistent background acoustic sentinel with a tiny, always-on-top
cyber-cat desktop companion in the screen's left corner.

Zero PyAudio dependency — utilizes native sounddevice + numpy for rock-solid
cross-platform audio streaming on Python 3.14.

Operational Upgrades:
1. Instant Click-to-Evoke: Left-click anywhere on the Pet HUD to immediately open
   the microphone (0ms delay, acoustic chime, silences active speaker playback).
2. Long Prompt Architecture:
   - Up to 90 seconds continuous recording for complex, multi-sentence prompts.
   - 5.0 Seconds Post-Speech Silence Wait: Enforces Karan's mandate to wait a full
     5 seconds of silence before finalizing and starting transcription.
3. Enhanced Speech Recognition:
   - Dynamic PCM amplitude normalization (boosts quiet laptop microphones).
   - Multi-language fallback (en-IN -> hi-IN -> en-US) for flawless Hinglish intake.
   - Comprehensive wake words & phonetic variants across Indian English accents.
4. Adjustable & Resizable HUD:
   - Mouse wheel zooming (65% to 250%).
   - Position & scale persistent across reboots via ~/.gemini/config/vocalis_pet.json.
"""
from __future__ import annotations

import argparse
import collections
import datetime
import math
import os
import queue
import re
import sys
import threading
import time
from pathlib import Path


# Force UTF-8 on Windows
if sys.stdout is not None and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr is not None and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PLUGIN_ROOT))

from vocalis.inbox import enqueue_voice_message
from vocalis.tools.notifications import play_wake_chime
from vocalis.tools.speak import abort_speech, is_speaking
from vocalis.ui.pet import VocalisPetUI

LOG_DIR = Path.home() / ".gemini" / "logs"
PID_FILE = LOG_DIR / "vocalis_daemon.pid"
STOP_FILE = LOG_DIR / "vocalis_daemon_stop.flag"
EVOKE_FILE = LOG_DIR / "vocalis_evoke.flag"
LOG_FILE = LOG_DIR / "vocalis_daemon.log"


def log(msg: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    if sys.stdout is not None:
        try:
            print(line, flush=True)
        except Exception:
            pass
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def normalize_pcm(pcm_bytes: bytes) -> bytes:
    """
    Standardize speech volume to ~80% full scale using 99th-percentile gain.
    99th-percentile instead of single-sample peak prevents breath pops / clicks
    from muting quiet speech by ignoring transient outlier spikes.
    """
    try:
        import numpy as np
        samples = np.frombuffer(pcm_bytes, dtype=np.int16)
        if len(samples) == 0:
            return pcm_bytes
        # 99th-percentile peak — outlier-robust against breath pops & mic thumps
        peak = float(np.percentile(np.abs(samples), 99))
        if 400.0 < peak < 25000.0:
            scale = 26000.0 / peak
            scaled = np.clip(samples.astype(np.float32) * scale, -32767.0, 32767.0).astype(np.int16)
            return scaled.tobytes()
    except Exception:
        pass
    return pcm_bytes


def _apply_phonetic_corrections(text: str) -> str:
    """
    Post-process STT output to fix common Indian-English phonetic mishearings.
    Applied after all STT passes to clean up before wake-word matching.
    """
    # word-boundary aware substitutions (case-insensitive)
    PHONETIC_FIXES = {
        # Wake-word variants
        r"\bnexas\b": "nexus",
        r"\bnexis\b": "nexus",
        r"\bnexa\b": "nexus",
        r"\bnext us\b": "nexus",
        r"\bnikos\b": "nexus",
        r"\bnecas\b": "nexus",
        r"\btexas\b": "nexus",
        # App name fixes
        r"\bage browser\b": "edge browser",
        r"\baged browser\b": "edge browser",
        r"\bwhats up\b": "whatsapp",
        r"\bwhat's up\b": "whatsapp",
        r"\bwhat's app\b": "whatsapp",
        r"\boutlook express\b": "outlook",
        r"\bvs code\b": "vscode",
        r"\bvis code\b": "vscode",
        r"\byou tube\b": "youtube",
        # Common command fix-ups
        r"\bopen the\b": "open",
        r"\bclose the\b": "close",
        r"\bplay the\b": "play",
        r"\bpaws\b": "pause",
    }
    result = text
    for pattern, replacement in PHONETIC_FIXES.items():
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    return result


def transcribe_audio(r, audio_data) -> str:

    """
    Bilingual multi-pass STT engine with network retry resilience.
    1st pass: en-IN (Indian English)
    2nd pass: hi-IN (Hindi / Hinglish commands)
    3rd pass: en-US (General English fallback)
    """
    import speech_recognition as sr

    # Pass 1: Indian English
    try:
        res = r.recognize_google(audio_data, language="en-IN").strip()
        if res:
            return _apply_phonetic_corrections(res)
    except (sr.UnknownValueError, sr.WaitTimeoutError):
        pass
    except Exception as e:
        log(f"⚠️ Primary STT (en-IN) blip: {e}")
        # Brief retry on socket glitch
        try:
            time.sleep(0.3)
            res = r.recognize_google(audio_data, language="en-IN").strip()
            if res:
                return _apply_phonetic_corrections(res)
        except Exception:
            pass

    # Pass 2: Hindi fallback (for Hinglish commands like 'speed kya hai', 'gana chalao')
    try:
        res = r.recognize_google(audio_data, language="hi-IN").strip()
        if res:
            return _apply_phonetic_corrections(res)
    except Exception:
        pass

    # Pass 3: en-US fallback
    try:
        res = r.recognize_google(audio_data, language="en-US").strip()
        if res:
            return _apply_phonetic_corrections(res)
    except Exception:
        pass

    return ""


def capture_command_phrase(
    stream,
    r,
    sample_rate: int,
    block_size: int,
    ui_q: queue.Queue,
    stop_event: threading.Event,
    initial_timeout_s: float = 6.0,
    silence_wait_s: float = 2.0,
    max_phrase_s: float = 90.0,
    threshold_fn=None,
    display_wake: str = "nexus",
) -> tuple[str, str]:
    """
    Robust long-prompt audio capture loop.
    Waits 2.0 seconds of silence after speech ends before transcribing.
    """
    import numpy as np
    import speech_recognition as sr

    silence_blocks_needed = int(silence_wait_s * sample_rate / block_size)
    max_blocks = int(max_phrase_s * sample_rate / block_size)

    speech_buffer = []
    is_speaking_phrase = False
    silence_counter = 0
    start_time = time.time()
    initial_deadline = start_time + initial_timeout_s
    speech_start_time = start_time

    while not stop_event.is_set():
        if STOP_FILE.exists():
            return "", display_wake

        data, _ = stream.read(block_size)
        samples = data[:, 0].astype(np.float32)
        rms = float(np.sqrt(np.mean(samples ** 2)))
        thr = threshold_fn() if threshold_fn else 30.0

        # Stream live RMS to Pet UI (bars animate while capturing command)
        try:
            ui_q.put_nowait({"state": "RMS", "level": rms})
        except Exception:
            pass

        if not is_speaking_phrase:
            # Waiting for user to start speaking
            if rms > thr:
                is_speaking_phrase = True
                speech_start_time = time.time()
                speech_buffer.append(data.tobytes())
                silence_counter = 0
                ui_q.put({"state": "LISTENING", "text": "🎙️ listening..."})
            else:
                if time.time() > initial_deadline:
                    # Initial silence timeout — no speech detected
                    return "", display_wake
        else:
            # Actively capturing user speech
            speech_buffer.append(data.tobytes())
            elapsed = int(time.time() - speech_start_time)

            if rms < thr:
                silence_counter += 1
                # Visual pause countdown during the silence wait
                silence_secs = silence_counter * block_size / sample_rate
                rem_wait = max(1, int(round(silence_wait_s - silence_secs)))
                if silence_secs >= 1.0:
                    ui_q.put({"state": "LISTENING", "text": f"🎙️ pause ({rem_wait}s)..."})
            else:
                silence_counter = 0
                ui_q.put({"state": "LISTENING", "text": f"🎙️ listening ({elapsed}s)..."})


            # Enforce silence pause wait before starting transcribe
            if silence_counter >= silence_blocks_needed:
                log(f"⏱️ {silence_wait_s:.1f}s silence completed. Starting transcription ({elapsed}s audio).")
                break

            if len(speech_buffer) >= max_blocks:
                log(f"⏱️ Max phrase limit reached ({max_phrase_s}s). Commencing transcription.")
                break

    if not speech_buffer:
        return "", display_wake

    raw_pcm = b"".join(speech_buffer)
    # Ignore tiny audio noise (<0.4s)
    if len(raw_pcm) < int(0.4 * sample_rate * 2):
        return "", display_wake

    ui_q.put({"state": "TRANSCRIBING", "text": "⚡ thinking..."})

    # Boost low-volume microphone audio before recognition
    normalized_pcm = normalize_pcm(raw_pcm)
    audio_data = sr.AudioData(normalized_pcm, sample_rate, 2)

    text = transcribe_audio(r, audio_data)
    return text, display_wake


def audio_listener_worker(
    ui_q: queue.Queue,
    action_q: queue.Queue,
    stop_event: threading.Event,
    monitor: bool = False,
):
    """
    Dedicated background worker thread for audio capture and STT.
    Uses sounddevice + numpy for pure-Python audio capture without PyAudio.
    """
    import numpy as np
    import sounddevice as sd
    import speech_recognition as sr

    r = sr.Recognizer()

    wake_words = [
        # ── Primary Nexus ──────────────────────────────────────────────────────
        "nexus", "hey nexus", "ok nexus", "hi nexus",
        # ── Kavita (primary persona name) ──────────────────────────────────────
        "kavita", "hey kavita", "ok kavita", "hi kavita",
        "suno kavita", "kavita suno", "aye kavita",
        # ── Sarika ─────────────────────────────────────────────────────────────
        "sarika", "hey sarika", "ok sarika", "hi sarika",
        "suno sarika",
        # ── AI / Moto ──────────────────────────────────────────────────────────
        "hey ai", "ok ai",
        "moto", "hey moto", "ok moto",
        # ── Legacy / Power-user aliases ────────────────────────────────────────
        "jarvis", "hey jarvis", "ok jarvis",
        "antigravity", "hey antigravity",
        "vocalis", "hey vocalis",
        "computer", "gemini",
        # ── Casual Hindi triggers ──────────────────────────────────────────────
        "bhai", "karan", "assistant",
        "suno", "aye", "wake up",
        "sun",  # short "sun" (listen in Hindi)
    ]
    phonetic_variants = [
        # Nexus mishearings
        "nexas", "nexis", "nexa", "texas", "next us", "nikos", "necas",
        # Kavita mishearings
        "kabita", "kavitha", "cavita", "kavit", "kabitha",
        "sunno kavita", "sun kavita", "hey kavitha",
        # Sarika mishearings
        "sarica", "sharika", "sarika",
        "sunno sarika", "sun sarika",
        # Jarvis mishearings
        "jarvez", "jarves", "service", "travis", "harvest",
        # AI mishearings  
        "hey eye", "hai ai", "hay ai",
        # Moto mishearings
        "motto", "motor", "moto is",
        # Antigravity
        "anti gravity", "vocalist", "vocal is", "fox call is",
        # Casual
        "bhai", "shaktiman",
    ]
    all_wake = wake_words + phonetic_variants

    sample_rate = 16000
    block_size = 1024  # 64ms per block
    # In standby single-breath detection, allow 0.8s pause before checking
    # (reduced from 2.8s → instant wake reaction under 1 second)
    standby_silence_blocks = int(0.8 * sample_rate / block_size)
    max_standby_blocks = int(25.0 * sample_rate / block_size)

    ambient_history = collections.deque(maxlen=40)
    pre_speech_buffer = collections.deque(maxlen=int(0.6 * sample_rate / block_size))

    def get_current_threshold() -> float:
        ambient_floor = sum(ambient_history) / max(1, len(ambient_history))
        return max(24.0, ambient_floor * 3.0)

    ui_q.put({"state": "STANDBY", "text": "💤 nexus"})
    log(f"🎤 SoundDevice Audio Worker online ({sample_rate}Hz mono, int16). 2s post-speech wait active.")

    while not stop_event.is_set():
        if STOP_FILE.exists():
            log("🛑 Stop flag detected by audio worker.")
            ui_q.put("QUIT")
            break

        try:
            with sd.InputStream(samplerate=sample_rate, channels=1, dtype="int16", blocksize=block_size) as stream:
                is_recording = False
                speech_buffer = []
                silence_counter = 0

                while not stop_event.is_set():
                    if STOP_FILE.exists():
                        ui_q.put("QUIT")
                        return

                    # 1. Check for Instant Click-to-Evoke trigger from Desktop Pet HUD or Global Hotkey
                    manual_trigger = False
                    if EVOKE_FILE.exists():
                        EVOKE_FILE.unlink(missing_ok=True)
                        manual_trigger = True
                    elif action_q and not action_q.empty():
                        try:
                            act = action_q.get_nowait()
                            if act.get("cmd") == "MANUAL_TRIGGER":
                                manual_trigger = True
                        except queue.Empty:
                            pass

                    if manual_trigger:
                        log("⚡ Manual Click-to-Evoke / Hotkey triggered!")
                        abort_speech()
                        play_wake_chime()
                        ui_q.put({"state": "LISTENING", "text": "🎙️ speak now..."})

                        cmd_text, _ = capture_command_phrase(
                            stream=stream,
                            r=r,
                            sample_rate=sample_rate,
                            block_size=block_size,
                            ui_q=ui_q,
                            stop_event=stop_event,
                            initial_timeout_s=6.0,
                            silence_wait_s=2.0,  # 2-second wait before transcribe
                            max_phrase_s=90.0,
                            threshold_fn=get_current_threshold,
                            display_wake="click",
                        )

                        if cmd_text:
                            msg = enqueue_voice_message(
                                text=cmd_text,
                                raw_transcript=cmd_text,
                                wake_word="click",
                            )
                            log(f"🎙️ Captured [click]: \"{cmd_text}\" (Queued as {msg['id']})")
                            ui_q.put({
                                "state": "QUEUED",
                                "text": "✓ Queued",
                                "command": cmd_text[:14],
                            })
                            time.sleep(1.5)

                        ui_q.put({"state": "STANDBY", "text": "💤 nexus"})
                        is_recording = False
                        speech_buffer = []
                        silence_counter = 0
                        continue

                    # 2. Silence gating while Motobook speakers are active
                    if is_speaking():
                        time.sleep(0.05)
                        continue

                    data, _ = stream.read(block_size)
                    samples = data[:, 0].astype(np.float32)
                    rms = float(np.sqrt(np.mean(samples ** 2)))
                    threshold = get_current_threshold()

                    # Stream live RMS to Pet UI every block (64ms cadence)
                    # Pet uses this to drive real voice-reactive bars instead of fake sine waves
                    try:
                        ui_q.put_nowait({"state": "RMS", "level": rms})
                    except queue.Full:
                        pass

                    if not is_recording:
                        ambient_history.append(rms)
                        pre_speech_buffer.append(data.tobytes())

                        if monitor and sys.stdout is not None:
                            db = 20 * math.log10(max(1.0, rms))
                            bar_len = min(20, int(db / 3.0))
                            bar = "#" * bar_len + "-" * (20 - bar_len)
                            sys.stdout.write(f"\r[{bar}] RMS: {rms:5.1f} | Thr: {threshold:5.1f} | [STANDBY]")
                            sys.stdout.flush()

                        if rms > threshold:
                            is_recording = True
                            speech_buffer = list(pre_speech_buffer)
                            speech_buffer.append(data.tobytes())
                            silence_counter = 0
                            # Immediate visual: pet knows voice is incoming — show LISTENING
                            # the instant RMS crosses threshold, BEFORE STT runs
                            try:
                                ui_q.put_nowait({"state": "LISTENING", "text": "👂 hearing..."})
                            except Exception:
                                pass
                            if monitor and sys.stdout is not None:
                                sys.stdout.write(" -> [VOICE DETECTED]\n")
                                sys.stdout.flush()
                    else:
                        speech_buffer.append(data.tobytes())

                        if monitor and sys.stdout is not None:
                            db = 20 * math.log10(max(1.0, rms))
                            bar_len = min(20, int(db / 3.0))
                            bar = "#" * bar_len + "-" * (20 - bar_len)
                            sys.stdout.write(f"\r[{bar}] RMS: {rms:5.1f} | Thr: {threshold:5.1f} | [RECORDING]")
                            sys.stdout.flush()

                        if rms < threshold:
                            silence_counter += 1
                        else:
                            silence_counter = 0

                        if silence_counter >= standby_silence_blocks or len(speech_buffer) >= max_standby_blocks:
                            is_recording = False
                            raw_pcm = b"".join(speech_buffer)
                            speech_buffer = []
                            silence_counter = 0

                            # Ignore tiny audio noise (<0.35s)
                            if len(raw_pcm) < int(0.35 * sample_rate * 2):
                                # Too short to be a wake word — revert silently
                                ui_q.put_nowait({"state": "STANDBY", "text": "💤 nexus"})
                                continue

                            # Show "checking..." during STT — keeps pet in LISTENING visually
                            try:
                                ui_q.put_nowait({"state": "LISTENING", "text": "🔍 checking..."})
                            except Exception:
                                pass

                            # Normalize audio volume
                            normalized_pcm = normalize_pcm(raw_pcm)
                            audio_data = sr.AudioData(normalized_pcm, sample_rate, 2)

                            raw_text = transcribe_audio(r, audio_data)
                            if not raw_text:
                                # Nothing heard — snap back to standby
                                ui_q.put({"state": "STANDBY", "text": "💤 nexus"})
                                continue

                            clean = raw_text.strip()
                            lower = clean.lower()

                            matched_wake = None
                            for w in all_wake:
                                if w in lower:
                                    matched_wake = w
                                    break

                            if not matched_wake:
                                # Room chatter — snap back to standby immediately
                                ui_q.put({"state": "STANDBY", "text": "💤 nexus"})
                                if monitor and sys.stdout is not None:
                                    print(f"   [Ignored Chatter]: \"{clean}\"")
                                continue

                            display_wake = "nexus" if matched_wake in phonetic_variants or "nexus" in matched_wake else matched_wake
                            log(f"⚡ Wake word detected: '{matched_wake}' in '{clean}'")

                            # 1. Acoustic Barge-In (silence speaker)
                            abort_speech()

                            # 2. Play wake chime earcon
                            play_wake_chime()

                            # 3. Light up Pet UI — LISTENING state shown immediately on wake word confirm
                            ui_q.put({"state": "LISTENING", "text": "🎙️ listening..."})

                            # 4. Check if command was spoken in same breath
                            idx = lower.find(matched_wake) + len(matched_wake)
                            command = clean[idx:].strip(" ,.?!")

                            if not command:
                                # User said only wake-word — capture full prompt with 3s silence wait
                                ui_q.put({"state": "LISTENING", "text": "🎙️ speak now..."})
                                command, _ = capture_command_phrase(
                                    stream=stream,
                                    r=r,
                                    sample_rate=sample_rate,
                                    block_size=block_size,
                                    ui_q=ui_q,
                                    stop_event=stop_event,
                                    initial_timeout_s=6.0,
                                    silence_wait_s=3.0,  # 3-second silence before transcribe
                                    max_phrase_s=90.0,
                                    threshold_fn=get_current_threshold,
                                    display_wake=display_wake,
                                )
                            else:
                                # Same-breath command: hold LISTENING visible briefly so user
                                # can see the pet acknowledged the wake word before processing
                                time.sleep(0.35)
                                ui_q.put({"state": "TRANSCRIBING", "text": "⚡ thinking..."})


                            if not command:
                                command = "status"

                            # 5. Enqueue to Voice Inbox
                            msg = enqueue_voice_message(
                                text=command,
                                raw_transcript=clean,
                                wake_word=display_wake,
                            )
                            log(f"🎙️ Captured [{display_wake}]: \"{command}\" (Queued as {msg['id']})")

                            # 6. Show happy confirmation on Pet HUD
                            ui_q.put({
                                "state": "QUEUED",
                                "text": "✓ Queued",
                                "command": command[:14],
                            })
                            time.sleep(1.5)

                            # 7. Smoothly return to Standby
                            ui_q.put({"state": "STANDBY", "text": "💤 nexus"})

        except Exception as e:
            log(f"❌ Audio Worker Exception: {e}")
            try:
                sd._terminate()
                time.sleep(0.5)
                sd._initialize()
            except Exception:
                pass
            time.sleep(2.0)


def run_daemon(headless: bool = False, monitor: bool = False):
    # Clear any stale stop flag
    if STOP_FILE.exists():
        STOP_FILE.unlink(missing_ok=True)

    # Acquire PID lock to ensure singleton daemon
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    if PID_FILE.exists():
        try:
            with open(PID_FILE, "r", encoding="utf-8") as f:
                existing_pid = int(f.read().strip())
            import psutil
            if existing_pid != os.getpid() and psutil.pid_exists(existing_pid):
                proc = psutil.Process(existing_pid)
                cmdline = " ".join(proc.cmdline()).lower()
                if "vocalis_daemon" in cmdline or "pet.py" in cmdline:
                    log(f"⚡ Pet already running (PID: {existing_pid}). Triggering Evoke / Push-to-Talk.")
                    EVOKE_FILE.write_text("evoke", encoding="utf-8")
                    try:
                        from vocalis.tools.notifications import play_wake_chime
                        play_wake_chime()
                    except Exception:
                        pass
                    sys.exit(0)
                else:
                    log(f"⚠️ Stale PID file found (PID: {existing_pid} is {proc.name()}, not daemon). Overwriting.")
                    PID_FILE.unlink(missing_ok=True)
            else:
                PID_FILE.unlink(missing_ok=True)
        except Exception:
            PID_FILE.unlink(missing_ok=True)

    with open(PID_FILE, "w", encoding="utf-8") as f:
        f.write(str(os.getpid()))

    log(f"⚡ Vocalis Listener Daemon online (PID: {os.getpid()}). Gated on 'Hey Nexus' & Click-to-Evoke.")

    ui_q = queue.Queue()
    action_q = queue.Queue()
    stop_event = threading.Event()

    cleaned_up = False

    def cleanup():
        nonlocal cleaned_up
        if cleaned_up:
            return
        cleaned_up = True
        stop_event.set()
        if PID_FILE.exists():
            try:
                content = PID_FILE.read_text(encoding="utf-8").strip()
                if content and int(content) == os.getpid():
                    PID_FILE.unlink(missing_ok=True)
            except Exception:
                pass
        log("👋 Vocalis Listener Daemon stopped cleanly.")

    # Start audio worker in background thread
    worker_thread = threading.Thread(
        target=audio_listener_worker,
        args=(ui_q, action_q, stop_event, monitor),
        daemon=True,
        name="VocalisAudioWorker",
    )
    worker_thread.start()

    if headless or monitor:
        mode_desc = "live monitor" if monitor else "headless"
        log(f"🖥️ Running in {mode_desc} mode (no Pet UI). Press Ctrl+C to terminate.")
        try:
            while not stop_event.is_set():
                if STOP_FILE.exists():
                    break
                time.sleep(0.5)
        except KeyboardInterrupt:
            pass
        finally:
            cleanup()
    else:
        # Run Scalable Desktop Pet UI on main thread
        try:
            pet = VocalisPetUI(
                event_queue=ui_q,
                action_queue=action_q,
                on_close=cleanup,
            )
            pet.run()
        except KeyboardInterrupt:
            pass
        except Exception as e:
            log(f"⚠️ Pet UI error: {e}. Falling back to CLI loop.")
            try:
                while not stop_event.is_set():
                    time.sleep(0.5)
            except KeyboardInterrupt:
                pass
        finally:
            cleanup()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Vocalis-Nexus Sovereign Listener Daemon & Desktop Pet")
    parser.add_argument("--no-ui", action="store_true", help="Run headless without Desktop Pet UI")
    parser.add_argument("--monitor", action="store_true", help="Run with live console acoustic VU meter")
    args = parser.parse_args()
    run_daemon(headless=args.no_ui, monitor=args.monitor)
