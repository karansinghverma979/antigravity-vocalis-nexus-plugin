---
name: vocalis-nexus
description: Sovereign ambient voice-to-voice AI assistant, local wake-word sentinel, and multi-agent dispatcher for Google Antigravity.
---

# 🎙️ Vocalis-Nexus Skill

The `/vocalis-nexus` skill provides complete control over Karan's ambient voice assistant, background task delegation, and acoustic notifications on Motobook workstation.

---

## ⚡ Quick Invocations

| Command | Action |
| :--- | :--- |
| **`/vocalis-nexus start`** | Launch the continuous ambient sentinel loop (`voice_wait.py` in background). |
| **`/vocalis-nexus pull`** *(or `direct`)* | Single-shot push-to-talk: listen immediately $\rightarrow$ voice answer $\rightarrow$ disarm (0 bg processes). |
| **`/vocalis-nexus speak <text>`** | Speak a message aloud through laptop speakers using native Windows TTS (0 tokens). |
| **`/vocalis-nexus stop`** | Cleanly terminate the background voice listener trigger. |
| **`/vocalis-nexus status`** | Check daemon health, microphone state, and recent voice jobs. |
| **`/vocalis-nexus chime [wake|completion|error]`** | Test audio speaker output and notification chords. |

---

## 🏛️ System Architecture: 100% Telegram-Nexus Parity

```text
               ┌────────────────────────────────────────────────────────┐
               │              Incoming Room Voice Audio                 │
               └──────────────────────────┬─────────────────────────────┘
                                          │
                                          ▼
               ┌────────────────────────────────────────────────────────┐
               │         voice_wait.py exits with Code 0                │
               │         Antigravity Wakes Live Agent In-Session        │
               └──────────────────────────┬─────────────────────────────┘
                                          │
                   ┌──────────────────────┴──────────────────────┐
                   ▼                                             ▼
        [Fast-Path Query / Status]                      [Slow-Path Heavy Task]
                   │                                             │
                   ▼                                             ▼
        Formulate spoken answer                         1. Call vocalis_speak:
                   │                                       "On it Karan, running
                   ▼                                        Win Janitor now."
        Call vocalis_speak(text)                                 │
        & display terminal card                                  ▼
                   │                                    2. Delegate to specialist:
                   │                                       invoke_subagent(
                   │                                         TypeName="win_janitor"
                   │                                       )
                   │                                             │
                   └──────────────────────┬──────────────────────┘
                                          │
                                          ▼
                      ══════════════════════════════════════
                      🔒 SACRED RE-ARMING IN THE SAME TURN
                      Launch voice_wait.py immediately!
                      (WaitMsBeforeAsync=500)
                      ══════════════════════════════════════
                                          │
                                          ▼
                      Agent stops calling tools to SLEEP
                      (Mic is listening; Subagents are working)
```

---

## 🛠️ CLI Direct Usage

From any PowerShell or terminal prompt:

```powershell
# 1. Test native speech playback (0 tokens)
python -m vocalis.tools.speak "Hello Karan, Vocalis Nexus is online."

# 2. Test single-shot voice listening (0 tokens STT)
python "$HOME/.gemini/config/plugins/vocalis-nexus-plugin/scripts/voice_wait.py" --direct

# 3. Ambient wake-word background mode
python "$HOME/.gemini/config/plugins/vocalis-nexus-plugin/scripts/voice_wait.py"
```

---

## 🔒 Configuration & Directives
* **Rule Zero**: `GEMINI.md` is never touched or diluted.
* **Agent Switching**: Use `/agents` $\rightarrow$ `vocalis_nexus` to enter the master vocal session.
* **Zero Token Waste**: STT uses the free Chromium speech gateway, TTS uses native Windows SpeechSynthesizer.
