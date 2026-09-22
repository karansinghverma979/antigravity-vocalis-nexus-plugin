import json
import pytest
from vocalis.core.dispatcher import handle_tool_call


def test_dispatcher_dispatch_job(tmp_path, monkeypatch):
    test_file = tmp_path / "test_jobs.json"
    monkeypatch.setattr("vocalis.config.cfg.JOBS_FILE", test_file)
    # Mock spawn_worker so it doesn't try to invoke external agy CLI during tests
    monkeypatch.setattr("vocalis.jobs.worker.spawn_worker", lambda job: None)

    args = {
        "target_agent": "repo_architect",
        "title": "Audit repository",
        "prompt": "Run full repository architecture check",
        "priority": "normal",
    }

    res_str = handle_tool_call("dispatch_job", args)
    res = json.loads(res_str)

    assert "job_id" in res
    assert res["job_id"].startswith("JOB-")
    assert res["agent"] == "repo_architect"
    assert res["status"] == "queued"


def test_dispatcher_telemetry(monkeypatch):
    args = {"metric": "ram"}
    res_str = handle_tool_call("get_system_telemetry", args)
    res = json.loads(res_str)
    assert "ram_percent" in res or "ram_total_gb" in res


def test_dispatcher_unknown():
    res_str = handle_tool_call("nonexistent_tool", {})
    res = json.loads(res_str)
    assert "error" in res
