"""
vocalis/config.py — Configuration loader & startup validator.

Loads from environment variables or ~/.gemini/credentials/vocalis-nexus/config.env
Falls back to .env in the plugin directory.
Validates required keys at startup so failures are loud and early.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*args, **kwargs):
        pass

try:
    from rich.console import Console
    console = Console()
except ImportError:
    import re
    class DummyConsole:
        def print(self, *args, **kwargs):
            cleaned = [re.sub(r'\[/?[^\]]+\]', '', str(a)) for a in args]
            print(*cleaned, **kwargs)
    console = DummyConsole()

# Canonical credential vault path (per sovereign security convention)
_VAULT_ENV = Path.home() / ".gemini" / "credentials" / "vocalis-nexus" / "config.env"
_LOCAL_ENV = Path(__file__).resolve().parent.parent / ".env"

# Load vault first, then local fallback
if _VAULT_ENV.exists():
    load_dotenv(_VAULT_ENV, override=False)
elif _LOCAL_ENV.exists():
    load_dotenv(_LOCAL_ENV, override=False)


def _require(key: str) -> str:
    """Get an env var or abort loudly."""
    val = os.environ.get(key, "").strip()
    if not val:
        console.print(
            f"[bold red]❌ MISSING CONFIG: {key} is not set.[/bold red]\n"
            f"   Set it in: {_VAULT_ENV}\n"
            f"   Or copy .env.example → .env and fill in values."
        )
        sys.exit(1)
    return val


class Config:
    """Single source of truth for all runtime settings."""

    GEMINI_API_KEY: str = _require("GEMINI_API_KEY")
    WAKE_WORD: str = os.environ.get("VOCALIS_WAKE_WORD", "hey_jarvis")
    VOICE: str = os.environ.get("VOCALIS_VOICE", "Puck")
    DEFAULT_MODE: str = os.environ.get("VOCALIS_MODE", "loop")
    LOG_DIR: Path = Path(
        os.path.expanduser(os.environ.get("VOCALIS_LOG_DIR", "~/.gemini/logs"))
    )
    JOBS_FILE: Path = LOG_DIR / "vocalis_jobs.json"

    # Audio constants
    SAMPLE_RATE: int = 16_000          # Mic input (Gemini Live API requirement)
    OUTPUT_SAMPLE_RATE: int = 24_000   # Speaker output (Gemini Live API output)
    CHUNK_FRAMES: int = 512            # ~32ms per chunk at 16kHz
    VAD_THRESHOLD: float = 0.65        # Silero VAD speech probability gate
    WAKE_SCORE_THRESHOLD: float = 0.50 # openWakeWord confidence gate

    # Session lifecycle
    SILENCE_TIMEOUT_S: float = 15.0    # Auto-close Loop session on N seconds silence
    MODEL: str = "gemini-3.1-flash-live-preview"


# Singleton — import Config directly, never re-instantiate
cfg = Config()
