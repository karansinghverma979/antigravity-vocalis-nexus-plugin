#!/usr/bin/env python3
"""
Vocalis-Nexus Standalone Test Runner.
Executes all unit tests with zero external test framework dependencies.
"""
import sys
import os
import json
import tempfile
from pathlib import Path

# Force UTF-8 on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PLUGIN_ROOT))

# Provide dummy test key for config loading
os.environ["GEMINI_API_KEY"] = "test_key_dummy_123"

passed = 0
failed = 0


def test(name):
    def decorator(fn):
        global passed, failed
        try:
            fn()
            print(f"  [PASS] {name}")
            passed += 1
        except Exception as e:
            print(f"  [FAIL] {name}: {e}")
            failed += 1
        return fn
    return decorator


print("\n=======================================================")
print("  🎙️ VOCALIS-NEXUS: STANDALONE TEST SUITE VERIFICATION")
print("=======================================================\n")


@test("Config: Default constants and environment loader")
def _():
    from vocalis.config import Config
    cfg = Config()
    assert cfg.GEMINI_API_KEY == "test_key_dummy_123"
    assert cfg.SAMPLE_RATE == 16000
    assert cfg.OUTPUT_SAMPLE_RATE == 24000
    assert cfg.MODEL == "gemini-3.1-flash-live-preview"


@test("Job Registry: Thread-safe ticket CRUD and lifecycle")
def _():
    from vocalis.jobs.registry import JobRegistry
    from vocalis.config import cfg
    with tempfile.TemporaryDirectory() as td:
        tf = Path(td) / "jobs.json"
        cfg.JOBS_FILE = tf
        reg = JobRegistry()
        reg._path = tf
        j1 = reg.create("win_janitor", "Clean RAM", "Trim memory", "high")
        assert j1["id"] == "JOB-1"
        assert j1["status"] == "QUEUED"
        j2 = reg.create("campaigns", "Check strikes", "List strikes")
        assert j2["id"] == "JOB-2"
        reg.update("JOB-1", status="COMPLETED", result_summary="Reclaimed 800MB")
        assert reg.get("JOB-1")["status"] == "COMPLETED"
        assert len(reg.list_running()) == 1


@test("Dispatcher: Split-brain tool router (dispatch_job & telemetry)")
def _():
    import vocalis.jobs.worker as worker_mod
    orig = worker_mod.spawn_worker
    worker_mod.spawn_worker = lambda job: None
    try:
        from vocalis.core.dispatcher import handle_tool_call
        from vocalis.config import cfg
        with tempfile.TemporaryDirectory() as td:
            cfg.JOBS_FILE = Path(td) / "jobs.json"
            res = json.loads(handle_tool_call("dispatch_job", {
                "target_agent": "repo_architect",
                "title": "Audit repo",
                "prompt": "Run full check",
            }))
            assert res["job_id"].startswith("JOB-")
            assert res["status"] == "queued"
            tel = json.loads(handle_tool_call("get_system_telemetry", {"metric": "ram"}))
            assert isinstance(tel, dict)
    finally:
        worker_mod.spawn_worker = orig


@test("Notifications: Pure Python PCM tone synthesis")
def _():
    from vocalis.tools.notifications import _generate_tone
    tone = _generate_tone(440.0, 0.05, sample_rate=24000)
    assert isinstance(tone, bytes)
    assert len(tone) == int(24000 * 0.05 * 2)


@test("Telemetry: Safe metric extraction without crashes")
def _():
    from vocalis.tools.telemetry import get_telemetry
    for m in ["ram", "cpu", "strikes", "all"]:
        res = get_telemetry(m)
        assert isinstance(res, dict)


@test("MCP Server: Stdio JSON-RPC protocol compliance")
def _():
    import subprocess
    server_py = str(PLUGIN_ROOT / "mcp" / "server.py")
    init_msg = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}) + "\n"
    list_msg = json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}) + "\n"

    proc = subprocess.Popen([sys.executable, server_py], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    stdout, _ = proc.communicate(init_msg + list_msg, timeout=5)
    lines = [json.loads(l) for l in stdout.strip().split("\n") if l.strip()]
    assert lines[0]["result"]["serverInfo"]["name"] == "vocalis-nexus"
    tools = [t["name"] for t in lines[1]["result"]["tools"]]
    assert "vocalis_get_status" in tools
    assert "vocalis_create_job" in tools
    assert "vocalis_play_chime" in tools


print(f"\nResults: {passed} passed, {failed} failed.")
if failed > 0:
    sys.exit(1)
print("All systems verified successfully!\n")
