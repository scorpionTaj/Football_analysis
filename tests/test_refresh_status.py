import time
from types import SimpleNamespace

from football_analysis.api.contracts import RefreshRequest
from football_analysis.api.refresh import RefreshCoordinator, RefreshRunReport
from football_analysis.ingest import connect


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


def test_degraded_source_status_survives_restart(tmp_path):
    path = tmp_path / "refresh.json"
    report = RefreshRunReport()
    report.add(1, "Football-Data.co.uk", {"league": "E0", "status": "success"}, required=True)
    report.add(2, "Reference standings", {"league": "E0", "status": "failed", "detail": "provider offline"})
    coordinator = RefreshCoordinator(path)
    coordinator.start(RefreshRequest(target_step=2), lambda _request, progress: (
        progress(1, "Results", "Done"), progress(2, "Tables", "Done"), report,
    )[-1])
    for _ in range(100):
        if coordinator.status().status == "degraded":
            break
        time.sleep(0.01)
    status = RefreshCoordinator(path).status()
    assert status.status == "degraded"
    assert status.completed_steps == [1, 2]
    assert status.failed_count == 0
    assert status.degraded_count == 1
    assert "provider offline" in status.source_messages[0]
    assert status.source_outcomes[1].source == "Reference standings"


def test_required_source_failure_status_survives_restart(tmp_path):
    path = tmp_path / "refresh.json"
    report = RefreshRunReport()
    report.add(1, "Weekly fixtures", {"status": "unavailable", "detail": "provider offline"})
    report.add(1, "Football-Data.co.uk", {"league": "E0", "status": "failed", "detail": "invalid CSV"}, required=True)
    coordinator = RefreshCoordinator(path)
    coordinator.start(RefreshRequest(target_step=1), lambda _request, progress: report)
    for _ in range(100):
        if coordinator.status().status == "failed":
            break
        time.sleep(0.01)
    status = RefreshCoordinator(path).status()
    assert status.status == "failed"
    assert status.completed_steps == []
    assert status.step_name == "Needs retry"
    assert status.failed_count == 1
    assert status.degraded_count == 1
    assert len(status.source_messages) == 2
    assert "invalid CSV" in status.error


def test_api_refresh_handoff_persists_runner_outcomes(tmp_path):
    from football_analysis.api.app import create_app

    db = tmp_path / "api.duckdb"
    with connect(db):
        pass
    report = RefreshRunReport()
    report.add(1, "Football-Data.co.uk", {"league": "E0", "status": "cached"}, required=True)
    report.add(1, "Weekly fixtures", {"status": "unavailable", "detail": "provider offline"})
    app = create_app(db, refresh_runner=lambda _request, _progress: report, defer_database_open=True)
    endpoint = next(route.endpoint for route in app.routes if route.path == "/api/v1/refresh" and "POST" in route.methods)
    loopback = SimpleNamespace(headers={}, client=SimpleNamespace(host="127.0.0.1"))
    endpoint(RefreshRequest(target_step=1), loopback)
    for _ in range(100):
        if app.state.refresh.status().status == "degraded":
            break
        time.sleep(0.01)
    status = RefreshCoordinator(db.with_suffix(".refresh.json")).status()
    assert status.status == "degraded"
    assert status.degraded_count == 1
    assert "provider offline" in status.source_messages[0]
    app.state.store.close()
