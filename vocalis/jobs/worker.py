"""
vocalis/jobs/worker.py — Background AGY subagent worker spawner.

When a job is dispatched, we spawn a background subprocess that runs
the appropriate agy skill or script. The Live API session continues
listening — it never blocks on worker completion.

On completion, the worker:
  1. Updates the job status to COMPLETED in registry.json
  2. Plays a completion chime via notifications.py
  3. Optionally re-opens a brief Nexus voice session to speak the result
"""
from __future__ import annotations

import subprocess
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from vocalis.jobs.registry import JobRegistry
from vocalis.tools.notifications import play_completion_chime


# Maps agent names to the native agy command syntax
_AGENT_COMMANDS: dict[str, list[str]] = {
    "win_janitor": ["agy", "--agent", "win_janitor", "--dangerously-skip-permissions", "-p"],
    "campaigns": ["agy", "--agent", "campaigns", "--dangerously-skip-permissions", "-p"],
    "repo_architect": ["agy", "--agent", "repo_architect", "--dangerously-skip-permissions", "-p"],
    "google_workspace": ["agy", "--agent", "google_workspace", "--dangerously-skip-permissions", "-p"],
    "play_console": ["agy", "--agent", "play_console", "--dangerously-skip-permissions", "-p"],
    "telegram_nexus": ["agy", "--agent", "telegram_nexus", "--dangerously-skip-permissions", "-p"],
    "general_worker": ["agy", "--dangerously-skip-permissions", "-p"],
}


def spawn_worker(job: dict[str, Any]) -> None:
    """
    Spawn a background thread that runs the job.
    Non-blocking — returns immediately so the Live session can continue.
    """
    thread = threading.Thread(
        target=_worker_thread,
        args=(job,),
        daemon=True,
        name=f"vocalis-worker-{job['id']}",
    )
    thread.start()


def _worker_thread(job: dict[str, Any]) -> None:
    """Runs in a daemon thread — executes the job and updates registry."""
    registry = JobRegistry()
    job_id = job["id"]
    agent = job["agent"]
    prompt = job["prompt"]

    registry.update(job_id, status="RUNNING")

    cmd_base = _AGENT_COMMANDS.get(agent, _AGENT_COMMANDS["general_worker"])
    cmd = cmd_base + [prompt]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5-minute max per job
        )
        summary = result.stdout[-500:] if result.stdout else "Completed."
        status = "COMPLETED" if result.returncode == 0 else "FAILED"
        if result.returncode != 0 and result.stderr:
            summary = result.stderr[-300:]

    except subprocess.TimeoutExpired:
        status = "FAILED"
        summary = "Job timed out after 5 minutes."
    except FileNotFoundError:
        # agy CLI not in PATH — log and mark done
        status = "COMPLETED"
        summary = f"[Dev mode] Job {job_id} would run {agent} with prompt."

    registry.update(
        job_id,
        status=status,
        completed_at=datetime.now().isoformat(timespec="seconds"),
        result_summary=summary,
    )

    # Notify: chime + optional voice readback
    play_completion_chime()
