"""In-process request metrics.

This is a deliberately small, dependency-free implementation. The numbers are
suitable for:

* A developer hitting ``GET /metrics`` while debugging locally.
* A single-replica instance feeding a Prometheus scraper via the JSON output.
* Spotting a sudden flood of 5xx in the logs.

It is **not** designed to be aggregated across replicas. For a production
multi-replica setup, swap the dict-backed counters for a real TSDB client
(``prometheus_client``, ``statsd``, OpenTelemetry exporter). The shape of
:func:`snapshot` is the contract — keep it stable.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field

MAX_LATENCY_SAMPLES = 1000


@dataclass
class _RouteStats:
    count: int = 0
    errors: int = 0
    latency_ms_total: float = 0.0
    latency_samples: deque[float] = field(default_factory=lambda: deque(maxlen=MAX_LATENCY_SAMPLES))


class MetricsRegistry:
    """Thread-safe registry of request counters and latency histograms."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._started_at = time.time()
        self._routes: dict[str, _RouteStats] = defaultdict(_RouteStats)
        self._errors_total: dict[str, int] = defaultdict(int)
        self._active_matters: int | None = None
        self._active_documents: int | None = None
        self._counts_loaded_at: float | None = None
        self._counts_organization_id: int | None = None

    def record_request(self, method: str, path: str, status_code: int, duration_ms: float) -> None:
        key = f"{method} {path}"
        with self._lock:
            stats = self._routes[key]
            stats.count += 1
            stats.latency_ms_total += duration_ms
            stats.latency_samples.append(duration_ms)
            if status_code >= 500:
                stats.errors += 1
                self._errors_total["5xx"] += 1
            elif status_code >= 400:
                self._errors_total["4xx"] += 1

    def record_error(self, kind: str) -> None:
        with self._lock:
            self._errors_total[kind] += 1

    def set_business_counts(self, *, active_matters: int, active_documents: int) -> None:
        with self._lock:
            self._active_matters = active_matters
            self._active_documents = active_documents
            self._counts_loaded_at = time.time()
            self._counts_organization_id = getattr(
                self, "_pending_counts_org", None
            )
            self._pending_counts_org = None

    def reset_for_test(self) -> None:
        """Clear all cached state. Test-only helper.

        Production code never calls this; it exists so test_s2_isolation_full
        can verify per-request scoping without depending on the order in
        which the test suite hits `/metrics`. The 60-second cache TTL on
        ``set_business_counts`` would otherwise let a previous test's
        snapshot leak into the next one.
        """
        with self._lock:
            self._routes.clear()
            self._errors_total.clear()
            self._active_matters = None
            self._active_documents = None
            self._counts_loaded_at = None
            self._counts_organization_id = None

    def snapshot(self) -> dict:
        with self._lock:
            routes_out: list[dict] = []
            for key, stats in sorted(self._routes.items()):
                avg = stats.latency_ms_total / stats.count if stats.count else 0.0
                p50, p95, p99 = _percentiles(stats.latency_samples)
                routes_out.append({
                    "route": key,
                    "request_count": stats.count,
                    "error_count": stats.errors,
                    "latency_ms_avg": round(avg, 2),
                    "latency_ms_p50": round(p50, 2),
                    "latency_ms_p95": round(p95, 2),
                    "latency_ms_p99": round(p99, 2),
                })

            return {
                "uptime_seconds": round(time.time() - self._started_at, 2),
                "request_count": sum(s.count for s in self._routes.values()),
                "error_count": sum(self._errors_total.values()),
                "errors_by_class": dict(self._errors_total),
                "active_matters": self._active_matters,
                "active_documents": self._active_documents,
                "business_counts_loaded_at": self._counts_loaded_at,
                "_organization_id": self._counts_organization_id,
                "routes": routes_out,
            }


def _percentiles(samples: deque[float]) -> tuple[float, float, float]:
    if not samples:
        return 0.0, 0.0, 0.0
    ordered = sorted(samples)
    n = len(ordered)

    def at(p: float) -> float:
        idx = max(0, min(n - 1, int(round(p * (n - 1)))))
        return ordered[idx]

    return at(0.50), at(0.95), at(0.99)


registry = MetricsRegistry()
