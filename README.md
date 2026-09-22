# 🎙️ Vocalis-Nexus: Sovereign Real-Time Voice-to-Voice AI Assistant

[![Model: Gemini 3.1 Flash Live](https://img.shields.io/badge/Model-Gemini%203.1%20Flash%20Live-blue.svg)](#)
[![Acoustic: openWakeWord + Silero VAD](https://img.shields.io/badge/Acoustic-openWakeWord%20%2B%20Silero-green.svg)](#)
[![Latency: Sub--700ms](https://img.shields.io/badge/Latency-%3C700ms-orange.svg)](#)
[![License: MIT](https://img.shields.io/badge/License-MIT-purple.svg)](./LICENSE)
[![OpenSSF: Hardened](https://img.shields.io/badge/OpenSSF-Least--Privilege-brightgreen.svg)](#)

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        🎙️ VOCALIS-NEXUS ENGINE                         │
│         Sovereign Ambient Acoustic Assistant & Swarm Dispatcher         │
├────────────────────────────────────────────────────────────────────────┤
│  ⚡ Layer 0: Local Offline Ear (openWakeWord ONNX + Silero VAD) [0 TOKENS]│
│  ⚡ Layer 1: Bi-Directional Vocal Brain (Gemini Live WebSocket) [<700ms] │
│  ⚡ Layer 2: Split-Brain Router (Conversational vs Async Jobs)  [INSTANT]│
│  ⚡ Layer 3: Background Worker Swarm (Antigravity Subagents)    [ASYNC]  │
│  🔒 Sovereign Credential Vault (~/.gemini/credentials/vocalis) [SECURED]│
└────────────────────────────────────────────────────────────────────────┘
```

---

## ⚡ The 5-Second Hook

**Vocalis-Nexus** transforms your workstation into an ambient, voice-commanded cockpit. Speak naturally into the room with **"Hey Jarvis"** (or custom wake-words).

- **Zero Cold-Starts**: No clunky CLI spin-ups (`agy -p`). Audio streams directly over persistent WebSockets with native barge-in interruption.
- **Zero Cloud Snooping**: Room audio is never sent to the cloud 24/7. Layer 0 processes audio **100% locally** using ONNX runtime (~1.5% CPU, 0 tokens).
- **Split-Brain Dispatcher**:
  - *Fast-Path*: Instant spoken answers for conversational queries and system telemetry (<50ms tool response).
  - *Heavy-Path*: Immediate verbal acknowledgment (*"Queued JOB-42 on Repo Architect"*) followed by asynchronous background execution.

---

## 🚀 30-Second Quickstart

### 1. Installation
```powershell
# Clone or navigate to plugin directory
cd ~/.gemini/config/plugins/vocalis-nexus-plugin

# Install dependencies
python -m pip install -e .
```

### 2. Configure Credentials
Save your Gemini API key inside the sovereign credential vault:
```powershell
# Create external vault if not present
mkdir -p ~/.gemini/credentials/vocalis-nexus

# Set key inside config.env
Set-Content -Path "$HOME\.gemini\credentials\vocalis-nexus\config.env" -Value "GEMINI_API_KEY=AIzaSy..."
```

### 3. Launch
```powershell
# Continuous ambient loop (waits for "Hey Jarvis")
python -m vocalis --mode loop

# Single-shot query (push-to-talk / one answer)
python -m vocalis --mode direct

# Dev testing (skips wake-word, opens mic immediately)
python -m vocalis --mode direct --no-wakeword
```

---

## 🏛️ System Architecture

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        LAYER 0: THE LOCAL EAR                          │
│  [Microphone Stream] ──► [Silero VAD] ──► [openWakeWord ONNX]          │
│  (100% Offline, Zero Cloud Tokens, CPU < 1.5%, ~60MB RAM)              │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Wake Detected ("Hey Jarvis")
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   LAYER 1: REAL-TIME VOCAL BRAIN                       │
│             Gemini Live API (WebSocket: gemini-3.1-flash-live)         │
│                                                                        │
│  • Direct 16kHz PCM In ──► 24kHz PCM Out (Latency < 700ms)             │
│  • Native Barge-In (Interruption purges speaker queue instantly)       │
│  • Synchronous Function Calling (Live intent interception)             │
└───────────────────┬────────────────────────────────┬───────────────────┘
                    │                                │
     [Fast-Path: Instant Voice]            [Heavy-Path: Execution Work]
                    │                                │
                    ▼                                ▼
       Spoken Direct Response         ┌──────────────────────────────────┐
       ("RAM is at 41%, sir.")        │ LAYER 2: ASYNC SWARM DISPATCHER   │
                                      │ • Tool: dispatch_job(...)        │
                                      │ • Live Brain Vocally Speaks:     │
                                      │   "Queued JOB-42 on Win Janitor. │
                                      │    I'm continuing to listen."    │
                                      │ • Ledger: vocalis_jobs.json      │
                                      │ • Spawns AGY Subagent Worker     │
                                      │ • Acoustic Chime on Completion   │
                                      └──────────────────────────────────┘
```

👉 **Read full engineering specifications in [ARCHITECTURE.md](./ARCHITECTURE.md)**

---

## 🎮 Dual Operating Modes

| Mode | Trigger & Lifecycle | Best For |
| :--- | :--- | :--- |
| **Direct Mode** | Wake $\rightarrow$ 1 Query $\rightarrow$ 1 Spoken Response $\rightarrow$ Immediate Session Close | Quick telemetry checks, status queries, single commands. 0 idle tokens. |
| **Loop Mode** | Wake $\rightarrow$ Continuous full-duplex session $\rightarrow$ Auto-sleep after 15s silence or "Dismiss" | Interactive brainstorming, back-to-back questions, active pair programming. |

---

## 🧱 Token Economy & Suppression Engine

Naively streaming raw audio to a cloud WebSocket 24/7 costs millions of tokens per week. Vocalis-Nexus eliminates token burn through a 4-stage firewall:

1. **Layer 0 Silence Suppression**: Audio is filtered locally via `Silero VAD`. Audio frames with speech probability $< 0.65$ are dropped locally and never hit the network.
2. **Offline Wake Gating**: While in standby, the WebSocket is completely closed. 0 network calls, 0 tokens.
3. **Low-Token Thinking**: Configured with `thinking_level="minimal"` to optimize latency and eliminate token overhead.
4. **Auto-Hibernation**: Continuous sessions automatically close after 15 seconds of sustained silence.

---

## 🛠️ MCP Server Integration

Vocalis-Nexus exposes an Antigravity MCP Server (`mcp/server.py`) so other agents in Karan's ecosystem can interact with the voice layer:

* `vocalis_get_status` — Inspect daemon state and queued jobs.
* `vocalis_list_jobs` — Read background worker tickets.
* `vocalis_create_job` — Inject a job ticket into the dispatcher.
* `vocalis_play_chime` — Play acoustic notification tones on workstation speakers.

---

## 🛡️ Repository Invariants

1. **Zero Secret Leaks**: Credentials live strictly in `~/.gemini/credentials/vocalis-nexus/`. Never staged in git.
2. **Zero Machine Paths**: Dynamic path resolution (`Path.home()`) across all modules.
3. **Non-Blocking Vocal Stream**: Worker execution is strictly decoupled from the real-time audio loop.

---

*Authored by **Karan Singh Verma** & Antigravity Executive Assistant.*
