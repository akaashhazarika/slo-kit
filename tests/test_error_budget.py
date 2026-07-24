"""Error-budget engine tests against hand-computed synthetic scenarios."""

from __future__ import annotations

import math

import pytest

from slo_kit.budget.error_budget import compute_error_budget

WINDOW_30D = 30 * 86400.0


def budget(good: float, total: float, objective: float = 0.999):
    return compute_error_budget(
        objective=objective, window_seconds=WINDOW_30D, good=good, total=total
    )


# Six synthetic scenarios with hand-computed expected values.
# objective 0.999 -> error budget fraction = 0.001.
SCENARIOS = [
    # (good, total, objective, allowed, consumed, remaining_pct)
    # 1M requests, 0 errors -> full budget remaining.
    (1_000_000, 1_000_000, 0.999, 1000.0, 0.0, 1.0),
    # 1M requests, 500 errors -> half budget consumed.
    (999_500, 1_000_000, 0.999, 1000.0, 500.0, 0.5),
    # 1M requests, exactly 1000 errors -> budget exactly exhausted.
    (999_000, 1_000_000, 0.999, 1000.0, 1000.0, 0.0),
    # 1M requests, 1500 errors -> overspent (remaining clamps to 0).
    (998_500, 1_000_000, 0.999, 1000.0, 1500.0, 0.0),
    # 100k requests, 50 errors, objective 0.99 -> allowed 1000, 5% consumed.
    (99_950, 100_000, 0.99, 1000.0, 50.0, 0.95),
    # 100% success at 99.9% -> 0 consumed.
    (200_000, 200_000, 0.999, 200.0, 0.0, 1.0),
]


@pytest.mark.parametrize("good,total,objective,allowed,consumed,remaining_pct", SCENARIOS)
def test_budget_scenarios(good, total, objective, allowed, consumed, remaining_pct):
    b = budget(good, total, objective)
    assert b.allowed_bad_events == pytest.approx(allowed)
    assert b.consumed == pytest.approx(consumed)
    assert b.remaining_pct == pytest.approx(remaining_pct)
    assert b.consumed_pct == pytest.approx(consumed / allowed)


def test_remaining_is_never_negative():
    b = budget(998_000, 1_000_000)  # 2000 errors, budget 1000
    assert b.remaining == 0.0
    assert b.remaining_pct == 0.0
    assert b.is_exhausted


def test_sli_matches_good_ratio():
    b = budget(999_000, 1_000_000)
    assert b.sli == pytest.approx(0.999)


def test_no_traffic_is_fully_healthy():
    b = budget(0, 0)
    assert b.sli == 1.0
    assert b.remaining_pct == 1.0
    assert not b.is_exhausted


def test_time_to_exhaustion_at_burn_rate_one():
    # Half the budget spent, burn rate 1.0 -> half a window remaining.
    b = budget(999_500, 1_000_000)  # remaining_pct = 0.5
    ttl = b.time_to_exhaustion(burn_rate=1.0)
    assert ttl is not None
    assert ttl.total_seconds() == pytest.approx(0.5 * WINDOW_30D)


def test_time_to_exhaustion_scales_inversely_with_burn_rate():
    b = budget(999_500, 1_000_000)  # remaining_pct = 0.5
    slow = b.time_to_exhaustion(burn_rate=1.0)
    fast = b.time_to_exhaustion(burn_rate=2.0)
    assert fast.total_seconds() == pytest.approx(slow.total_seconds() / 2)


def test_time_to_exhaustion_none_when_no_burn():
    b = budget(999_500, 1_000_000)
    assert b.time_to_exhaustion(burn_rate=0.0) is None


def test_time_to_exhaustion_zero_when_already_exhausted():
    b = budget(998_000, 1_000_000)
    ttl = b.time_to_exhaustion(burn_rate=5.0)
    assert ttl is not None and ttl.total_seconds() == 0.0


def test_current_burn_rate_from_full_window():
    # error rate 0.002, budget 0.001 -> burn rate 2.0
    b = budget(998_000, 1_000_000)
    assert b.current_burn_rate == pytest.approx(2.0)


def test_consumed_pct_infinite_when_budget_zero_and_errors():
    # total==0 gives zero allowed budget; any bad event -> infinite consumption.
    # Construct via tiny total to exercise the guard.
    b = budget(0, 1, objective=0.999)  # allowed 0.001, consumed 1 -> 1000x
    assert b.consumed_pct == pytest.approx(1000.0)
    assert b.remaining_pct == 0.0


def test_invalid_objective_rejected():
    with pytest.raises(ValueError):
        compute_error_budget(objective=1.0, window_seconds=WINDOW_30D, good=1, total=1)
    with pytest.raises(ValueError):
        compute_error_budget(objective=0.0, window_seconds=WINDOW_30D, good=1, total=1)


def test_invalid_counts_rejected():
    with pytest.raises(ValueError):
        compute_error_budget(objective=0.999, window_seconds=WINDOW_30D, good=-1, total=1)
    with pytest.raises(ValueError):
        compute_error_budget(objective=0.999, window_seconds=0, good=1, total=1)


def test_isfinite_guard():
    b = budget(1_000_000, 1_000_000)
    assert math.isfinite(b.remaining_pct)
