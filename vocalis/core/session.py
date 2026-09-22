"""
vocalis/core/session.py — Gemini Live API session lifecycle manager.

This is the heart of Vocalis-Nexus. Manages the full WebSocket session:
  - Connects to gemini-3.1-flash-live-preview
  - Runs two concurrent async loops: send_loop + receive_loop
  - Handles barge-in (interrupted signal)
  - Handles function calls via dispatcher
  - Implements session resumption (survives 10-min WebSocket resets)
  - Auto-closes on silence timeout (Loop mode) or explicit dismiss
"""
from __future__ import annotations

import asyncio
import base64
import json
import time
from typing import Literal

from google import genai
from google.genai import types

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

from vocalis.audio.capture import MicCapture
from vocalis.audio.playback import AudioPlayer
from vocalis.audio.vad import is_speech
from vocalis.config import cfg
from vocalis.core.dispatcher import TOOL_DECLARATIONS, handle_tool_call
from vocalis.core.system_prompt import SYSTEM_PROMPT

console = Console()

# Session resumption handle — persists across reconnects
_last_session_handle: str | None = None


async def run_session(mode: Literal["direct", "loop"] = "loop") -> None:
    """
    Open a Gemini Live API session and run until completion.

    Args:
        mode: "direct" — closes after first response
              "loop"   — stays open until silence timeout or "dismiss"
    """
    global _last_session_handle

    client = genai.Client(api_key=cfg.GEMINI_API_KEY)
    player = AudioPlayer()
    player.start()

    # Build session resumption config if we have a previous handle
    resumption_cfg = None
    if _last_session_handle:
        resumption_cfg = types.SessionResumptionConfig(
            handle=_last_session_handle
        )

    live_config = types.LiveConnectConfig(
        response_modalities=[types.Modality.AUDIO],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                    voice_name=cfg.VOICE
                )
            )
        ),
        thinking_config=types.ThinkingConfig(thinking_level="minimal"),
        tools=[TOOL_DECLARATIONS],
        system_instruction=types.Content(
            parts=[types.Part(text=SYSTEM_PROMPT)]
        ),
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
        session_resumption_config=resumption_cfg,
    )

    console.print("[dim cyan]🌐 Opening Gemini Live session...[/dim cyan]")

    try:
        async with client.aio.live.connect(
            model=cfg.MODEL,
            config=live_config,
        ) as session:
            console.print("[bold green]✅ Session open — listening[/bold green]")

            # Run send and receive loops concurrently
            done, pending = await asyncio.wait(
                [
                    asyncio.create_task(_send_loop(session, mode, player)),
                    asyncio.create_task(_receive_loop(session, player)),
                ],
                return_when=asyncio.FIRST_COMPLETED,
            )

            # Cancel the other loop when one finishes
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    except Exception as e:
        console.print(f"[red]Session error: {e}[/red]")
    finally:
        player.stop()
        console.print("[dim]Session closed.[/dim]")


async def _send_loop(
    session: object,
    mode: str,
    player: AudioPlayer,
) -> None:
    """
    Continuously capture mic audio, apply VAD gate, stream to Gemini.
    Also monitors silence timeout for auto-close in loop mode.
    """
    last_speech_time = time.monotonic()
    dismissed = False

    async with MicCapture() as mic:
        async for chunk in mic.stream():
            # VAD gate — only send speech frames
            if not is_speech(chunk):
                # Check silence timeout in loop mode
                if mode == "loop":
                    silence_s = time.monotonic() - last_speech_time
                    if silence_s >= cfg.SILENCE_TIMEOUT_S:
                        console.print(
                            f"[dim]⏱️ {cfg.SILENCE_TIMEOUT_S}s silence — session closing[/dim]"
                        )
                        return
                continue  # Drop silence chunk — never sends to WebSocket

            last_speech_time = time.monotonic()

            # Stream validated speech chunk to Gemini Live API
            await session.send_realtime_input(
                audio=types.Blob(
                    data=chunk,
                    mime_type=f"audio/pcm;rate={cfg.SAMPLE_RATE}",
                )
            )

            # Direct mode: single-shot — return after sending first speech burst
            if mode == "direct":
                # Send stream-end marker to flush the model's audio buffer
                await session.send_realtime_input(audio_stream_end=True)
                return


async def _receive_loop(session: object, player: AudioPlayer) -> None:
    """
    Receive events from Gemini Live API:
    - Audio chunks → play on speaker
    - Transcriptions → log to console
    - Interruptions → flush player queue
    - Function calls → dispatch and return result synchronously
    - Session handles → save for resumption
    """
    global _last_session_handle

    async for response in session.receive():
        # ── Session resumption handle ──
        if hasattr(response, "session_resumption_update"):
            upd = response.session_resumption_update
            if upd and upd.resumable and upd.new_handle:
                _last_session_handle = upd.new_handle

        content = response.server_content
        if not content:
            continue

        # ── Barge-in: user interrupted Nexus speaking ──
        if content.interrupted:
            player.interrupt()
            console.print("[yellow]⚡ Interrupted[/yellow]")
            continue

        # ── Audio output: Gemini speaking ──
        if content.model_turn:
            for part in content.model_turn.parts:
                if part.inline_data and part.inline_data.data:
                    player.enqueue(part.inline_data.data)

        # ── Transcription logging ──
        if content.input_transcription and content.input_transcription.text:
            console.print(
                f"[dim white]You:[/dim white] {content.input_transcription.text}"
            )
        if content.output_transcription and content.output_transcription.text:
            console.print(
                f"[dim cyan]Nexus:[/dim cyan] {content.output_transcription.text}"
            )

        # ── Function calls (tool use) ──
        tool_call = getattr(response, "tool_call", None)
        if tool_call and tool_call.function_calls:
            for fc in tool_call.function_calls:
                console.print(
                    f"[bold magenta]🔧 Tool:[/bold magenta] {fc.name}({fc.args})"
                )
                # Handle synchronously — must return before Gemini speaks
                result_str = handle_tool_call(fc.name, dict(fc.args))

                # Return tool result to Gemini
                await session.send_realtime_input(
                    tool_response=types.LiveClientToolResponse(
                        function_responses=[
                            types.FunctionResponse(
                                id=fc.id,
                                name=fc.name,
                                response={"result": result_str},
                            )
                        ]
                    )
                )
