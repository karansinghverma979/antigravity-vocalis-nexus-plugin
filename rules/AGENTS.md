# 🎙️ Vocalis-Nexus: Agent Rules & Operational Invariants

Whenever interacting with Vocalis-Nexus, dispatching voice tasks, or authoring code for this plugin, all Antigravity agents must strictly obey these directives:

---

### 1. 🔑 Sovereign External Credential Quarantine (Rule Zero)
* **MANDATORY**: Gemini API keys and sensitive tokens must **NEVER** be hardcoded, committed, or staged inside the git repository tree.
* Credentials reside strictly in the sovereign external quarantine vault:
  - `%USERPROFILE%\.gemini\credentials\vocalis-nexus\config.env` (Windows)
  - `~/.gemini/credentials/vocalis-nexus/config.env` (Linux / macOS)
  - Or specified via `GEMINI_API_KEY` environment variable.
* Never print or log API keys or raw bearer tokens into logs, transcript files, or public audit registers.

---

### 2. 🗣️ The Voice Output Mandate (Speak Aloud First)
* **MANDATORY**: In every turn where an inbound voice message or query is handled, the agent **MUST speak the synthesized answer aloud through Motobook speakers** using:
  ```pwsh
  python -m vocalis.tools.speak --text "<spoken_sentence>"
  ```
  or calling the `vocalis_speak` tool.
* **Dual Delivery**:
  - **For Ears**: 1 to 2 conversational, concise sentences (under 30 words) with pure phonetics (zero markdown, zero URLs, symbols expanded into plain words like "percent" and "gigabytes").
  - **For Eyes**: Full technical details, data cards, and diffs rendered in the terminal chat.
* Never leave Karan in silence after processing a voice command!

---

### 3. ⚡ Master Dispatcher & Swarm Team Delegation (Zero Heavy Self-Work)
* **Priority #1: Instant Acoustic ACK**: The moment voice input is pulled, **IMMEDIATELY speak aloud** through Motobook speakers:
  - Fast-Path (direct questions/status): Speak answer directly (<1s).
  - Heavy Tasks (coding, OS sweeps, research, git tasks): Speak verbal ACK immediately: *"Understood Karan, starting [Task Title] with the specialist team now."*
* **Master Agent Doctrine (Zero Heavy Self-Work)**: You are the Commander, NOT the foot soldier. **NEVER execute multi-step coding, large refactoring, long research, or OS maintenance yourself in the dispatcher turn!**
  - Create ticket via `vocalis_create_job` (e.g. `JOB-XX`).
  - Immediately delegate work to specialist subagents using `invoke_subagent`:
    - `win_janitor`: OS cleanup, memory trimming, background process diagnostics.
    - `repo_architect`: GitHub repos, OpenSSF CI/CD, README maintenance.
    - `campaigns`: SQLite strike updates, daily task queries, treasury operations.
    - `google_workspace`: Drive, Docs, Gmail, Calendar, Sheets, Tasks.
    - `play_console`: Android App Bundles, Play Console release tracks.
    - `research`: Deep web/code exploration and documentation lookups.
    - `self`: Code writing, implementation, test running, bug fixing.
    - Custom agents via `define_subagent` if required.
* **CRITICAL - Re-Arm in Same Turn**: Launch `voice_wait.py` via `run_command(WaitMsBeforeAsync=500)` in the **exact same turn** before ending execution! Never wait for subagents to finish before re-arming!
* **On Subagent Completion**: Speak a 1-2 sentence spoken summary aloud confirming task completion, output the card, and ensure `voice_wait.py` is re-armed.

---

### 4. 🔒 The Sacred Re-Arming Invariant (MANDATORY IN THE SAME TURN)
* At the end of every active turn in Gear 1 (Ambient Sentinel mode):
  ```pwsh
  python "$HOME/.gemini/config/plugins/vocalis-nexus-plugin/scripts/voice_wait.py"
  ```
  Must be executed via `run_command(WaitMsBeforeAsync=500)` before sleeping!
* The agent must never terminate or go dead after 1 or 2 voice messages.

---

### 5. ⚡ The Instant Pull / Direct Mode (100% Nexus Parity, Zero Loop)
* When invoked via `/vocalis-nexus pull` or `/vocalis-nexus direct`:
  - Fetch pending voice messages from Voice Inbox via `vocalis_poll_inbox` or `listener.py --pull`.
  - Process messages, speak the answer aloud, and display the card.
  - **NEVER launch or re-arm `voice_wait.py`**.
  - Turn ends cleanly with **zero background processes**.

---

### 6. ⏱️ The 4-Minute Watchdog & Progress Sentinel
* If any background job (`JOB-XX`) takes **more than 4 minutes (240s)**:
  - `voice_wait.py` detects elapsed time and automatically wakes up the agent.
  - The agent announces verbal progress update: *"Job [JOB-XX] is still crunching on Motobook workstation. Will notify you immediately upon completion."*
  - Re-arm `voice_wait.py` immediately.

---

### 7. 🛡️ The Zero Absolute Local User Path Invariant
* Never allow machine-specific local paths like `C:\Users\<username>\...` to leak into git-tracked source code, JSON configs, or markdown documentation.
* Always enforce portable dynamic expansion via `$HOME`, `Path.home()`, or dynamic home resolution.
