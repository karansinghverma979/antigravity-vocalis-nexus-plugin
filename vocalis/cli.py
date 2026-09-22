"""
vocalis/cli.py — Command-line interface.

Usage:
    python -m vocalis                      # default mode from .env
    python -m vocalis --mode direct        # single-shot
    python -m vocalis --mode loop          # continuous session
    python -m vocalis --mode daemon        # background wake-word watchdog
"""
from __future__ import annotations

import argparse
import asyncio
import sys

try:
    from rich.console import Console
    from rich import print as rprint
    console = Console()
except ImportError:
    import re
    class DummyConsole:
        def print(self, *args, **kwargs):
            cleaned = [re.sub(r'\[/?[^\]]+\]', '', str(a)) for a in args]
            print(*cleaned, **kwargs)
    console = DummyConsole()
    def rprint(*args, **kwargs):
        console.print(*args, **kwargs)


def _banner() -> None:
    console.print(
        "\n[bold cyan]🎙️  Vocalis-Nexus[/bold cyan] [dim]v0.1.0[/dim]\n"
        "[dim]Sovereign ambient voice-to-voice AI assistant[/dim]\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="vocalis",
        description="Vocalis-Nexus: Ambient voice-to-voice AI assistant",
    )
    parser.add_argument(
        "--mode",
        choices=["direct", "loop", "daemon"],
        default=None,
        help="Operating mode: direct (single-shot), loop (continuous), daemon (background)",
    )
    parser.add_argument(
        "--no-wakeword",
        action="store_true",
        help="Skip wake word detection — open mic immediately (dev/test mode)",
    )
    args = parser.parse_args()

    _banner()

    # Import here to avoid loading heavy deps before arg parse
    from vocalis.config import cfg
    from vocalis.core.session import run_session
    from vocalis.wakeword.detector import WakeWordDetector

    mode = args.mode or cfg.DEFAULT_MODE

    if mode == "direct":
        rprint("[bold]Mode:[/bold] [yellow]DIRECT[/yellow] — single wake → answer → exit")
        asyncio.run(_run_direct(args.no_wakeword))

    elif mode == "loop":
        rprint("[bold]Mode:[/bold] [green]LOOP[/green] — continuous ambient session")
        asyncio.run(_run_loop(args.no_wakeword))

    elif mode == "daemon":
        rprint("[bold]Mode:[/bold] [blue]DAEMON[/blue] — background watchdog")
        asyncio.run(_run_daemon())


async def _run_direct(skip_wake: bool) -> None:
    """Single-shot: wake → session → answer → done."""
    from vocalis.config import cfg
    from vocalis.core.session import run_session
    from vocalis.wakeword.detector import WakeWordDetector

    if not skip_wake:
        console.print(f"[dim]Listening for wake word: '{cfg.WAKE_WORD}'...[/dim]")
        detector = WakeWordDetector()
        await detector.wait_for_wake()
        console.print("[bold green]⚡ Wake word detected![/bold green]")

    await run_session(mode="direct")


async def _run_loop(skip_wake: bool) -> None:
    """Continuous: wake → persistent session → auto-close on silence/dismiss."""
    from vocalis.config import cfg
    from vocalis.core.session import run_session
    from vocalis.wakeword.detector import WakeWordDetector

    while True:
        if not skip_wake:
            console.print(f"\n[dim]👂 Listening for: '{cfg.WAKE_WORD}'...[/dim]")
            detector = WakeWordDetector()
            await detector.wait_for_wake()
            console.print("[bold green]⚡ Wake detected — opening session[/bold green]")

        try:
            await run_session(mode="loop")
        except KeyboardInterrupt:
            console.print("\n[yellow]Session interrupted. Returning to standby.[/yellow]")
            if skip_wake:
                break

        if skip_wake:
            break  # no loop in skip mode


async def _run_daemon() -> None:
    """Daemon: run loop silently in background, no rich output."""
    from vocalis.core.session import run_session
    from vocalis.wakeword.detector import WakeWordDetector
    from vocalis.config import cfg

    while True:
        detector = WakeWordDetector()
        await detector.wait_for_wake()
        await run_session(mode="loop")
