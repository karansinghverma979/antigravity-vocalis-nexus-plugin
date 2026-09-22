import json
from pathlib import Path
import pytest
from vocalis.jobs.registry import JobRegistry


def test_job_registry_crud(tmp_path, monkeypatch):
    test_file = tmp_path / "test_jobs.json"
    monkeypatch.setattr("vocalis.config.cfg.JOBS_FILE", test_file)

    registry = JobRegistry()
    registry._path = test_file

    # 1. Create Job
    job = registry.create(
        agent="win_janitor",
        title="Trim RAM Working Set",
        prompt="Perform system RAM working set trim",
        priority="high",
    )
    assert job["id"] == "JOB-1"
    assert job["agent"] == "win_janitor"
    assert job["status"] == "QUEUED"

    # 2. Verify file content
    assert test_file.exists()
    data = json.loads(test_file.read_text(encoding="utf-8"))
    assert data["next_id"] == 2
    assert len(data["jobs"]) == 1

    # 3. Create Second Job
    job2 = registry.create(
        agent="campaigns",
        title="Check strikes",
        prompt="Check today's active strikes",
    )
    assert job2["id"] == "JOB-2"

    # 4. Update Job Status
    updated = registry.update("JOB-1", status="COMPLETED", result_summary="Reclaimed 850MB RAM")
    assert updated is True

    fetched = registry.get("JOB-1")
    assert fetched is not None
    assert fetched["status"] == "COMPLETED"
    assert fetched["result_summary"] == "Reclaimed 850MB RAM"

    # 5. List Running vs All
    all_jobs = registry.list_all()
    assert len(all_jobs) == 2

    running_jobs = registry.list_running()
    assert len(running_jobs) == 1
    assert running_jobs[0]["id"] == "JOB-2"
