"""Shared test fixtures: synthetic series and a fake metric source.

These fixtures let budget/burn-rate/alert tests run against fully deterministic
inputs with hand-computed expected outputs — no network, no Prometheus.
"""

from __future__ import annotations

import pytest

from slo_kit.models import SLI, SLO, Target, Window


class FakeSource:
    """A :class:`~slo_kit.sources.base.MetricSource` driven by a lookup table.

    Configure per-window good/total counts; the source resolves the SLI's
    rendered ``good_query`` / ``total_query`` back to those counts by matching
    the window duration embedded in the query.
    """

    def __init__(self, per_window: dict[str, tuple[float, float]]):
        # per_window maps a window duration -> (good, total)
        self._per_window = per_window

    def scalar(self, query: str) -> float:
        for window, (good, total) in self._per_window.items():
            if f"[{window}]" in query:
                return good if query.startswith("good") else total
        raise KeyError(f"FakeSource has no data for query: {query!r}")


def make_slo(
    *,
    name: str = "test-slo",
    objective: float = 0.999,
    window: str = "30d",
    alerting=None,
) -> SLO:
    """Build a simple SLO whose queries embed ``[{window}]`` for FakeSource."""
    return SLO(
        name=name,
        service="test",
        sli=SLI(good_query="good[{window}]", total_query="total[{window}]"),
        target=Target(objective=objective),
        window=Window(duration=window),
        alerting=alerting,
    )


@pytest.fixture
def make_slo_fixture():
    return make_slo


@pytest.fixture
def fake_source():
    return FakeSource
