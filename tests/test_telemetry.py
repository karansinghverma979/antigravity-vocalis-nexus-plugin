import pytest
from vocalis.tools.telemetry import get_telemetry


def test_telemetry_metrics():
    for metric in ["ram", "cpu", "strikes", "all"]:
        res = get_telemetry(metric)
        assert isinstance(res, dict)
        assert len(res) > 0

    err_res = get_telemetry("invalid_metric_xyz")
    assert "error" in err_res
