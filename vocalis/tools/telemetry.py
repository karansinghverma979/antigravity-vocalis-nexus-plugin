"""
vocalis/tools/telemetry.py — Real-time system metrics (fast-path tool).

Called synchronously from dispatcher.py — must return in < 50ms.
Uses psutil for RAM/CPU, campaigns.sqlite for strikes/treasury.
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any


def _ram() -> dict:
    try:
        import psutil
        vm = psutil.virtual_memory()
        return {
            "ram_total_gb": round(vm.total / 1e9, 1),
            "ram_used_gb": round(vm.used / 1e9, 1),
            "ram_percent": vm.percent,
        }
    except ImportError:
        return {"ram_percent": "psutil not installed"}


def _cpu() -> dict:
    try:
        import psutil
        return {"cpu_percent": psutil.cpu_percent(interval=0.1)}
    except ImportError:
        return {"cpu_percent": "psutil not installed"}


def _campaigns() -> dict:
    """Quick query against campaigns.sqlite for today's strikes."""
    db_path = Path(os.environ.get(
        "CAMPAIGNS_DB",
        Path.home() / "AppData" / "Roaming" / "Campaigns" / "Database" / "campaigns.sqlite"
    ))
    if not db_path.exists():
        return {"strikes_today": "campaigns.sqlite not found"}
    try:
        from datetime import date
        today = date.today().isoformat()
        with sqlite3.connect(str(db_path)) as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM strikes WHERE date=? AND status='pending'",
                (today,),
            ).fetchone()
            pending = row[0] if row else 0
        return {"strikes_pending_today": pending}
    except Exception as e:
        return {"strikes_error": str(e)}


def get_telemetry(metric: str) -> dict[str, Any]:
    """
    Return live system metrics as a dict.
    metric: "ram" | "cpu" | "strikes" | "treasury" | "all"
    """
    if metric == "ram":
        return _ram()
    elif metric == "cpu":
        return _cpu()
    elif metric == "strikes":
        return _campaigns()
    elif metric == "treasury":
        return {"note": "Treasury query coming in v0.2 — use campaigns skill directly"}
    elif metric == "all":
        data = {}
        data.update(_ram())
        data.update(_cpu())
        data.update(_campaigns())
        return data
    else:
        return {"error": f"Unknown metric: {metric}"}
