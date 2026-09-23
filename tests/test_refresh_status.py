import time

from football_analysis.api.contracts import RefreshRequest
from football_analysis.api.refresh import RefreshCoordinator


def test_refresh_status_survives_restart_and_reports_partial_failure(tmp_path):
    path = tmp_path / "refresh.json"
    coordinator = RefreshCoordinator(path)

    def fails_after_first_stage(_request, progress):
        progress(1, "Results", "Started")
        progress(2, "Tables", "Started")
        raise RuntimeError("source unavailable")

    coordinator.start(RefreshRequest(target_step=3), fails_after_first_stage)
    for _ in range(100):
        if coordinator.status().status == "failed":
            break
        time.sleep(0.01)
    status = RefreshCoordinator(path).status()
    assert status.status == "failed"
    assert status.completed_steps == [1]
    assert "partial" in status.message
    assert status.error == "source unavailable"


def test_interrupted_refresh_is_not_reported_as_running(tmp_path):
    path = tmp_path / "refresh.json"
    path.write_text(RefreshCoordinator().status().model_copy(update={"status": "running"}).model_dump_json())
    status = RefreshCoordinator(path).status()
    assert status.status == "failed"
    assert "stopped" in status.error
