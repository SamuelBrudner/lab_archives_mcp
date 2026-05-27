"""Internal-path microbenchmark for the lab_archives_mcp tool surface.

Times in-process operations that do not depend on LabArchives, OpenAI, or
Pinecone. Reports median wall-clock latency over N iterations to give a
reproducible measurement of the tool dispatch and state-management cost that
the package itself contributes. End-to-end search and write times are
dominated by external services and are not measured here.

Run with:
    ./conda_envs/test-env/bin/python scripts/benchmark_internal.py
"""

from __future__ import annotations

import gc
import statistics
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from labarchives_mcp.linked_data.provo_export import export_project_context
from labarchives_mcp.state.manager import StateManager
from vector_backend.labarchives_indexer import clean_html


SAMPLE_HTML = (
    "<div><h2>Protocol</h2>"
    "<p>This <b>protocol</b> describes the <i>preparation</i> of buffer "
    "solutions for <a href='https://example.org'>routine</a> use. "
    "Step 1: Combine reagents.</p>"
    "<ul><li>Tris-HCl, 50 mM</li><li>NaCl, 150 mM</li><li>EDTA, 1 mM</li></ul>"
    "<p>Mix gently. Store at 4&deg;C for up to <b>two weeks</b>.</p></div>"
)


def _median_ms(samples: list[float]) -> float:
    return statistics.median(samples) * 1000.0


def _p95_ms(samples: list[float]) -> float:
    if not samples:
        return 0.0
    ordered = sorted(samples)
    index = max(0, int(round(0.95 * (len(ordered) - 1))))
    return ordered[index] * 1000.0


def bench_clean_html(iterations: int) -> tuple[float, float]:
    samples: list[float] = []
    for _ in range(iterations):
        gc.collect()
        start = time.perf_counter()
        clean_html(SAMPLE_HTML)
        samples.append(time.perf_counter() - start)
    return _median_ms(samples), _p95_ms(samples)


def bench_state_ops(iterations: int) -> dict[str, tuple[float, float]]:
    with tempfile.TemporaryDirectory() as tmp:
        manager = StateManager(storage_dir=tmp)
        ctx = manager.create_project(
            name="benchmark", description="microbench", linked_notebook_ids=["NB1"]
        )
        manager.switch_project(ctx.id)

        visit_samples: list[float] = []
        for i in range(iterations):
            gc.collect()
            start = time.perf_counter()
            manager.log_visit("NB1", f"page-{i}", f"Page {i}")
            visit_samples.append(time.perf_counter() - start)

        finding_samples: list[float] = []
        for i in range(iterations):
            gc.collect()
            start = time.perf_counter()
            manager.log_finding(
                f"Observation {i}: signal increased.",
                source_url=f"https://mynotebook.labarchives.com/share/NB1/page-{i}",
                page_id=f"page-{i}",
            )
            finding_samples.append(time.perf_counter() - start)

        jsonld_samples: list[float] = []
        active = manager.get_active_context()
        assert active is not None
        for _ in range(max(5, iterations // 5)):
            gc.collect()
            start = time.perf_counter()
            export_project_context(active)
            jsonld_samples.append(time.perf_counter() - start)

    return {
        "log_visit": (_median_ms(visit_samples), _p95_ms(visit_samples)),
        "log_finding": (_median_ms(finding_samples), _p95_ms(finding_samples)),
        "export_project_context": (_median_ms(jsonld_samples), _p95_ms(jsonld_samples)),
    }


def main() -> int:
    iterations = 200
    html_med, html_p95 = bench_clean_html(iterations)
    state = bench_state_ops(iterations)

    rows = [
        ("clean_html (one HTML chunk)", html_med, html_p95, iterations),
        ("log_visit (StateManager)", *state["log_visit"], iterations),
        ("log_finding (StateManager)", *state["log_finding"], iterations),
        ("export_project_context (JSON-LD, 200-page graph)",
         *state["export_project_context"], max(5, iterations // 5)),
    ]

    print(f"{'Operation':<42} {'median (ms)':>12} {'p95 (ms)':>10} {'N':>6}")
    print("-" * 72)
    for name, med, p95, n in rows:
        print(f"{name:<42} {med:>12.3f} {p95:>10.3f} {n:>6}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
