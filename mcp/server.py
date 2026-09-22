#!/usr/bin/env python3
"""
Vocalis-Nexus MCP Server
Sovereign Ambient Voice-to-Voice AI Gateway & Multi-Agent Dispatcher for Google Antigravity.
Zero-dependency, pure Python standard library stdio JSON-RPC implementation.
"""
from __future__ import annotations

import sys
import json
import os
from pathlib import Path

# Force UTF-8 on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Ensure plugin root is in python path
PLUGIN_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PLUGIN_ROOT))

from vocalis.jobs.registry import JobRegistry
from vocalis.tools.notifications import play_wake_chime, play_completion_chime, play_error_chime

SERVER_NAME = "vocalis-nexus"
SERVER_VERSION = "0.1.0"

TOOLS = [
    {
        "name": "vocalis_get_status",
        "description": "Inspect the operational status of Vocalis-Nexus, active wake word, model, and queued jobs.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "vocalis_list_jobs",
        "description": "List all background jobs dispatched by voice or other agents.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["all", "queued", "running", "completed", "failed"],
                    "description": "Filter by job status (default: all)",
                }
            },
        },
    },
    {
        "name": "vocalis_get_job",
        "description": "Retrieve full details for a specific Vocalis job ticket.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "job_id": {
                    "type": "string",
                    "description": "The job ID (e.g. JOB-1)",
                }
            },
            "required": ["job_id"],
        },
    },
    {
        "name": "vocalis_create_job",
        "description": "Programmatically inject a job ticket into the Vocalis dispatcher queue.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "target_agent": {
                    "type": "string",
                    "enum": ["win_janitor", "campaigns", "repo_architect", "research", "general_worker"],
                    "description": "Target agent swarm specialist",
                },
                "title": {"type": "string", "description": "Short title of the task"},
                "prompt": {"type": "string", "description": "Instructions for the worker agent"},
                "priority": {
                    "type": "string",
                    "enum": ["normal", "high", "critical"],
                    "description": "Priority level",
                },
            },
            "required": ["target_agent", "title", "prompt"],
        },
    },
    {
        "name": "vocalis_cancel_job",
        "description": "Cancel a queued or running job ticket.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "job_id": {"type": "string", "description": "The job ID to cancel"}
            },
            "required": ["job_id"],
        },
    },
    {
        "name": "vocalis_speak",
        "description": "Speak a message aloud through the workstation speakers using native speech synthesis (0 tokens).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "The text message to vocalize aloud",
                }
            },
            "required": ["text"],
        },
    },
    {
        "name": "vocalis_play_chime",
        "description": "Play an acoustic notification tone on the host workstation speakers.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "chime_type": {
                    "type": "string",
                    "enum": ["wake", "completion", "error"],
                    "description": "Type of chime to play",
                }
            },
            "required": ["chime_type"],
        },
    },
]


def handle_call_tool(name: str, arguments: dict) -> list[dict]:
    registry = JobRegistry()

    if name == "vocalis_get_status":
        from vocalis.config import cfg
        jobs = registry.list_all()
        running = sum(1 for j in jobs if j.get("status") in ("QUEUED", "RUNNING"))
        return [{
            "type": "text",
            "text": json.dumps({
                "status": "online",
                "model": cfg.MODEL,
                "wake_word": cfg.WAKE_WORD,
                "voice": cfg.VOICE,
                "sample_rate": cfg.SAMPLE_RATE,
                "total_jobs": len(jobs),
                "active_jobs": running,
            }, indent=2)
        }]

    elif name == "vocalis_list_jobs":
        status_filter = arguments.get("status", "all").upper()
        jobs = registry.list_all()
        if status_filter != "ALL":
            jobs = [j for j in jobs if j.get("status") == status_filter]
        return [{
            "type": "text",
            "text": json.dumps({"count": len(jobs), "jobs": jobs}, indent=2)
        }]

    elif name == "vocalis_get_job":
        job_id = arguments.get("job_id", "")
        job = registry.get(job_id)
        if not job:
            return [{"type": "text", "text": json.dumps({"error": f"Job not found: {job_id}"})}]
        return [{"type": "text", "text": json.dumps(job, indent=2)}]

    elif name == "vocalis_create_job":
        target_agent = arguments["target_agent"]
        title = arguments["title"]
        prompt = arguments["prompt"]
        priority = arguments.get("priority", "normal")

        job = registry.create(
            agent=target_agent,
            title=title,
            prompt=prompt,
            priority=priority,
        )
        from vocalis.jobs.worker import spawn_worker
        spawn_worker(job)

        return [{
            "type": "text",
            "text": json.dumps({
                "status": "created",
                "job_id": job["id"],
                "agent": job["agent"],
            }, indent=2)
        }]

    elif name == "vocalis_cancel_job":
        job_id = arguments.get("job_id", "")
        ok = registry.update(job_id, status="CANCELLED")
        return [{
            "type": "text",
            "text": json.dumps({"success": ok, "job_id": job_id})
        }]

    elif name == "vocalis_speak":
        from vocalis.tools.speak import speak_text
        text = arguments.get("text", "")
        ok = speak_text(text)
        return [{
            "type": "text",
            "text": json.dumps({"status": "spoken" if ok else "failed", "text": text}, indent=2)
        }]

    elif name == "vocalis_play_chime":
        chime_type = arguments.get("chime_type", "completion")
        if chime_type == "wake":
            play_wake_chime()
        elif chime_type == "error":
            play_error_chime()
        else:
            play_completion_chime()
        return [{
            "type": "text",
            "text": json.dumps({"played": chime_type})
        }]

    else:
        return [{"type": "text", "text": json.dumps({"error": f"Unknown tool: {name}"})}]


def main():
    while True:
        line = sys.stdin.readline()
        if not line:
            break
        try:
            req = json.loads(line)
        except Exception:
            continue

        method = req.get("method")
        msg_id = req.get("id")

        if method == "initialize":
            res = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {
                        "name": SERVER_NAME,
                        "version": SERVER_VERSION,
                    },
                },
            }
        elif method == "notifications/initialized":
            continue
        elif method == "tools/list":
            res = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {"tools": TOOLS},
            }
        elif method == "tools/call":
            params = req.get("params", {})
            name = params.get("name")
            arguments = params.get("arguments", {})
            try:
                content = handle_call_tool(name, arguments)
                res = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {"content": content},
                }
            except Exception as e:
                res = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {"code": -32000, "message": str(e)},
                }
        else:
            res = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            }

        sys.stdout.write(json.dumps(res) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
