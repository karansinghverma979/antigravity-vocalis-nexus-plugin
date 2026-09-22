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

### 2. ⚡ The Non-Blocking Acoustic Stream Invariant
* **MANDATORY**: The real-time vocal loop must **NEVER** block on code execution, git commits, network downloads, or long-running computations.
* **Fast-Path**: Conversational answers and quick telemetry queries (`get_system_telemetry`) must return within **50 milliseconds**.
* **Heavy-Path**: Any work taking >1 second must immediately issue a `dispatch_job` tool call, provide an instant verbal receipt (`JOB-XXX`), and release the vocal brain to continue listening while background subagents execute asynchronously.

---

### 3. 🛡️ The Zero Absolute Local User Path Invariant
* Never allow machine-specific local paths like `C:\Users\<username>\...` to leak into git-tracked source code, JSON configs, or markdown documentation.
* Always enforce portable dynamic expansion:
  - Python: `Path.home()` or `os.path.expanduser('~')`
  - PowerShell: `$HOME` or `[Environment]::GetFolderPath('UserProfile')`
* In documentation, always wrap placeholder paths with angle brackets (e.g., `<USERPROFILE>`).

---

### 4. 🧱 Token Economy & Silence Suppression
* Raw audio must never be sent to cloud WebSockets 24/7.
* Layer 0 must always gate mic input through local VAD (`Silero VAD`). Audio chunks with `speech_prob < 0.65` must be dropped locally to suppress token consumption during silence.
* In Loop Mode, auto-close sessions after 15 seconds of sustained silence.

---

### 5. 🎧 Acoustic Feedback Loop Prevention
* Full-duplex audio models listen while speaking (barge-in capability).
* When testing locally without headphones, speaker audio can loop back into the microphone. Always recommend headphones/earbuds for development to prevent self-interruption feedback loops.
