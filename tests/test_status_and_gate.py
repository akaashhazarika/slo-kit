"""End-to-end status + deploy-gate tests using the FakeSource fixture."""

from __future__ import annotations

import pytest
from tests.conftest import FakeSource, make_slo

from slo_kit.gate import evaluate_gate
from slo_kit.report.status import evaluate_status

# Window good/total counts. The 30d window drives the budget; the alert
# windows (1h,5m,6h,30m,24h,2h) drive burn rates.
HEALTHY = {
    "30d": (1_000_000, 1_000_000),  # perfect over the SLO window
    "1h": (1_000, 1_000),
    "5m": (1_000, 1_000),
    "6h": (1_000, 1_000),
    "30m": (1_000, 1_000),
    "24h": (1_000, 1_000),
    "2h": (1_000, 1_000),
}

# 1.5% errors everywhere -> burn rate 15x (> 14.4 fast threshold).
BURNING = {
    "30d": (985_000, 1_000_000),
    "1h": (985, 1_000),
    "5m": (985, 1_000),
    "6h": (985, 1_000),
    "30m": (985, 1_000),
    "24h": (985, 1_000),
    "2h": (985, 1_000),
}

# Budget fully spent over the window but currently no burn.
EXHAUSTED = {
    "30d": (997_000, 1_000_000),  # 3000 errors, budget 1000 -> exhausted
    "1h": (1_000, 1_000),
    "5m": (1_000, 1_000),
    "6h": (1_000, 1_000),
    "30m": (1_000, 1_000),
    "24h": (1_000, 1_000),
    "2h": (1_000, 1_000),
}


def test_status_healthy():
    slo = make_slo()
    status = evaluate_status(slo, FakeSource(HEALTHY))
    assert status.sli == pytest.approx(1.0)
    assert status.budget_remaining_pct == pytest.approx(1.0)
    assert not status.is_firing
    assert status.severity is None


def test_status_burning_fires_page():
    slo = make_slo()
    status = evaluate_status(slo, FakeSource(BURNING))
    assert status.burn_rate("1h") == pytest.approx(15.0)
    assert status.is_firing
    assert status.severity == "page"


def test_status_to_dict_shape():
    slo = make_slo()
    d = evaluate_status(slo, FakeSource(HEALTHY)).to_dict()
    assert d["slo"] == "test-slo"
    assert set(d["error_budget"]) >= {"consumed", "remaining", "remaining_pct", "is_exhausted"}
    assert d["alerts"]["firing"] is False
    assert len(d["alerts"]["conditions"]) == 3


def test_status_burn_rate_unknown_window_raises():
    slo = make_slo()
    status = evaluate_status(slo, FakeSource(HEALTHY))
    with pytest.raises(KeyError):
        status.burn_rate("99h")


def test_gate_passes_when_healthy():
    slo = make_slo()
    decision = evaluate_gate(slo, FakeSource(HEALTHY))
    assert decision.passed
    assert decision.exit_code == 0


def test_gate_blocks_when_exhausted():
    slo = make_slo()
    decision = evaluate_gate(slo, FakeSource(EXHAUSTED))
    assert not decision.passed
    assert decision.exit_code == 1
    assert "budget" in decision.reason


def test_gate_min_budget_floor():
    slo = make_slo()
    # Healthy has 100% remaining, so a 50% floor still passes.
    assert evaluate_gate(slo, FakeSource(HEALTHY), min_budget_pct=0.5).passed
    # 60% remaining scenario:
    partial = dict(HEALTHY)
    partial["30d"] = (999_400, 1_000_000)  # 600 errors, budget 1000 -> 40% remaining
    decision = evaluate_gate(slo, FakeSource(partial), min_budget_pct=0.5)
    assert not decision.passed


def test_gate_block_on_firing():
    slo = make_slo()
    # Budget over 30d is fine but short windows are burning hot.
    firing_only = dict(BURNING)
    firing_only["30d"] = (1_000_000, 1_000_000)  # full budget remaining
    passed_default = evaluate_gate(slo, FakeSource(firing_only))
    assert passed_default.passed  # budget healthy -> passes by default
    blocked = evaluate_gate(slo, FakeSource(firing_only), block_on_firing=True)
    assert not blocked.passed
    assert "firing" in blocked.reason
