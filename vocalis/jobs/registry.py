"""
vocalis/jobs/registry.py — Job ticket ledger (vocalis_jobs.json).

Lightweight JSON-backed job store. No database needed.
Operations are atomic (read-modify-write with lock) for thread safety.

Schema:
{
  "next_id": 43,
  "jobs": [
    {
      "id": "JOB-42",
      "agent": "win_janitor",
      "title": "Full memory audit",
      "prompt": "...",
      "priority": "normal",
      "status": "QUEUED",        # QUEUED | RUNNING | COMPLETED | FAILED
      "created_at": "2026-09-22T21:00:00",
      "completed_at": null,
      "result_summary": null
    }
  ]
}
"""
from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from vocalis.config import cfg


class JobRegistry:
    """Thread-safe JSON job ticket manager."""

    _lock = threading.Lock()

    def __init__(self) -> None:
        self._path = cfg.JOBS_FILE
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> dict:
        if self._path.exists():
            try:
                return json.loads(self._path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
        return {"next_id": 1, "jobs": []}

    def _save(self, data: dict) -> None:
        self._path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def create(
        self,
        agent: str,
        title: str,
        prompt: str,
        priority: str = "normal",
    ) -> dict[str, Any]:
        """Create a new job ticket. Returns the job dict."""
        with self._lock:
            data = self._load()
            job_id = f"JOB-{data['next_id']}"
            job = {
                "id": job_id,
                "agent": agent,
                "title": title,
                "prompt": prompt,
                "priority": priority,
                "status": "QUEUED",
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "completed_at": None,
                "result_summary": None,
            }
            data["jobs"].append(job)
            data["next_id"] += 1
            self._save(data)
        return job

    def update(self, job_id: str, **kwargs: Any) -> bool:
        """Update fields on an existing job. Returns True if found."""
        with self._lock:
            data = self._load()
            for job in data["jobs"]:
                if job["id"] == job_id:
                    job.update(kwargs)
                    self._save(data)
                    return True
        return False

    def get(self, job_id: str) -> dict | None:
        data = self._load()
        for job in data["jobs"]:
            if job["id"] == job_id:
                return job
        return None

    def list_all(self) -> list[dict]:
        return self._load().get("jobs", [])

    def list_running(self) -> list[dict]:
        return [j for j in self.list_all() if j["status"] in ("QUEUED", "RUNNING")]
