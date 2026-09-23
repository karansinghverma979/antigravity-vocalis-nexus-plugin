# 🎙️ Vocalis-Nexus: Core Invariants

1. **Credential Quarantine**: Gemini keys live strictly in `%USERPROFILE%\.gemini\credentials\vocalis-nexus\config.env`. Never log or commit raw keys.
2. **The Voice Output Mandate**:
   - Always speak synthesized answer aloud through Motobook speakers: `python -m vocalis.tools.speak --text "<spoken_sentence>"` or `vocalis_speak`.
   - Dual delivery: Concise phonetics for ears (<30 words, zero markdown/URLs), full technical cards for terminal display.
3. **Master Dispatcher & Reactive Loop**:
   - Fast-path queries: Speak answer directly (<1s).
   - Heavy tasks: Speak immediate acoustic ACK, create ticket, delegate to subagents via `invoke_subagent`.
   - Ambient Mode (Gear 1): Always launch `voice_wait.py` in the exact same turn before sleeping.
4. **Direct Pull Mode (`/vocalis-nexus pull`)**:
   - Process inbox, speak aloud, and exit with zero background processes.
