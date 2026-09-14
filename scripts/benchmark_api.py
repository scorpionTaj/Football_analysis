#!/usr/bin/env python3
"""Benchmark the read-only FastAPI service against the real database.

Exit gate (Phase 2): p95 local response time stays below 300 ms
for filtered analytical reads.
"""

from __future__ import annotations

import statistics
import time

from fastapi.testclient import TestClient

from football_analysis.api.app import create_app
from football_analysis.config import DB


def timed(fn):
    """Return (result, elapsed_ms)."""
    start = time.perf_counter()
    result = fn()
    elapsed = (time.perf_counter() - start) * 1000
    return result, elapsed


def run_benchmark():
    if not DB.exists():
        print(f"Database not found at {DB} — skipping benchmark.")
        return

    app = create_app(DB)
    client = TestClient(app, raise_server_exceptions=False)
    iterations = 5

    endpoints = [
        ("GET", "/api/v1/health", {}),
        ("GET", "/api/v1/catalog", {}),
        ("GET", "/api/v1/teams", {"competition": "E0", "season": 2026}),
        ("GET", "/api/v1/teams", {}),
        ("GET", "/api/v1/matches", {"competition": "E0", "season": 2026, "limit": 50}),
        ("GET", "/api/v1/matches", {"limit": 20}),
        ("POST", "/api/v1/analysis", None),
        ("GET", "/api/v1/tournaments/UCL/2024", {}),
        ("GET", "/api/v1/predictions", {}),
        ("GET", "/api/v1/players", {"limit": 50}),
        ("GET", "/api/v1/players", {"q": "Saka", "limit": 10}),
        ("GET", "/api/v1/quality", {}),
    ]

    analysis_body = {
        "competitions": ["E0"],
        "seasons": [2026],
        "teams": [],
        "form_window": 5,
    }

    print(f"Benchmarking {len(endpoints)} endpoints × {iterations} iterations against {DB}\n")
    print(f"{'Endpoint':<55} {'p50':>7} {'p95':>7} {'p99':>7} {'max':>7}")
    print("-" * 90)

    all_times: list[float] = []
    analytical_times: list[float] = []
    analytical_routes = {"/api/v1/analysis", "/api/v1/catalog", "/api/v1/quality", "/api/v1/predictions"}

    for method, path, params in endpoints:
        times: list[float] = []
        for _ in range(iterations):
            if method == "POST":
                _, ms = timed(lambda: client.post(path, json=analysis_body))
            else:
                _, ms = timed(lambda p=params: client.get(path, params=p))
            times.append(ms)

        times.sort()
        p50 = statistics.median(times)
        p95 = times[int(len(times) * 0.95)] if len(times) >= 20 else max(times)
        p99 = times[int(len(times) * 0.99)] if len(times) >= 100 else max(times)
        mx = max(times)

        label = f"{method} {path}"
        if params:
            label += f"?{'&'.join(f'{k}={v}' for k, v in (params if isinstance(params, dict) else {}).items())}"
        label = label[:54]
        print(f"{label:<55} {p50:6.1f}ms {p95:6.1f}ms {p99:6.1f}ms {mx:6.1f}ms")

        all_times.extend(times)
        if any(r in path for r in analytical_routes):
            analytical_times.extend(times)

    print("-" * 90)
    all_times.sort()
    analytical_times.sort()

    overall_p95 = all_times[int(len(all_times) * 0.95)] if len(all_times) >= 20 else max(all_times)
    analytical_p95 = analytical_times[int(len(analytical_times) * 0.95)] if len(analytical_times) >= 20 else max(analytical_times)

    print(f"\nOverall      p95: {overall_p95:.1f}ms  (n={len(all_times)})")
    print(f"Analytical   p95: {analytical_p95:.1f}ms  (n={len(analytical_times)})")

    gate = 300.0
    if analytical_p95 < gate:
        print(f"\n✅ EXIT GATE PASSED: analytical p95 ({analytical_p95:.1f}ms) < {gate:.0f}ms")
    else:
        print(f"\n❌ EXIT GATE FAILED: analytical p95 ({analytical_p95:.1f}ms) >= {gate:.0f}ms")


if __name__ == "__main__":
    run_benchmark()
