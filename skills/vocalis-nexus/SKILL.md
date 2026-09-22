---
name: vocalis-nexus
description: Sovereign ambient voice-to-voice AI assistant, local wake-word sentinel, and multi-agent dispatcher for Google Antigravity.
---

# 🎙️ Vocalis-Nexus Skill

The `/vocalis-nexus` skill provides complete control over Karan's ambient voice assistant, background task delegation, and acoustic notifications on Motobook.

---

## ⚡ Quick Invocations

| Command | Action |
| :--- | :--- |
| **`/vocalis-nexus status`** | Check daemon health, model, active wake word, and job counts. |
| **`/vocalis-nexus direct`** | Single-shot push-to-talk: wake $\rightarrow$ query $\rightarrow$ voice answer $\rightarrow$ disarm. |
| **`/vocalis-nexus loop`** | Full-duplex ambient listening loop with automatic silence timeout. |
| **`/vocalis-nexus jobs`** | Display active and completed background worker tickets. |
| **`/vocalis-nexus chime [wake|completion|error]`** | Test audio speaker output and notification chords. |

---

## 🏛️ Architecture Overview

```text
┌──────────────────────────────────────────────────────────────┐
│  LAYER 0: LOCAL EAR (Offline, 0 Tokens, <1.5% CPU)          │
│  Mic ──► Silero VAD ──► openWakeWord ONNX ("Hey Jarvis")     │
└──────────────────────────┬───────────────────────────────────┘
                           │ Wake Detected
                           ▼
┌──────────────────────────────────────────────────────────────┐
│  LAYER 1: REAL-TIME VOCAL BRAIN (Gemini Live API WebSocket)  │
│  Model: gemini-3.1-flash-live-preview (PCM In / Out)         │
│  Latency: <700ms | Native Barge-In | Synchronous Tools       │
└─────────────┬────────────────────────────────┬───────────────┘
              │                                │
     [Fast-Path Query]                 [Heavy-Path Work]
              │                                │
              ▼                                ▼
     Instant Spoken Answer            ┌────────────────────────┐
     ("RAM is at 41%, sir.")          │ LAYER 2: WORKER SWARM  │
                                      │ • Spoken ACK (<1s)     │
                                      │ • JOB-XXX in ledger    │
                                      │ • Async AGY Subagent   │
                                      │ • Completion Chime     │
                                      └────────────────────────┘
```

---

## 🛠️ CLI Direct Usage

From any PowerShell or terminal prompt:

```powershell
# 1. Continuous ambient mode (default)
python -m vocalis --mode loop

# 2. Single-shot direct mode
python -m vocalis --mode direct

# 3. Skip wake-word for immediate interactive dev testing
python -m vocalis --mode direct --no-wakeword
```

---

## 🔑 Configuration & Credential Quarantine

Credentials reside strictly in the sovereign external vault:
* Path: `%USERPROFILE%\.gemini\credentials\vocalis-nexus\config.env`
* Key: `GEMINI_API_KEY=AIzaSy...`

Runtime variables:
* `VOCALIS_WAKE_WORD`: Default `hey_jarvis` (pre-trained ONNX)
* `VOCALIS_VOICE`: `Puck`, `Charon`, `Aoede`, `Fenrir`, or `Kore`
* `VOCALIS_MODE`: `loop` or `direct`
