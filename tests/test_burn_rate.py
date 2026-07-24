"""Burn-rate math tests with hand-computed multipliers."""

from __future__ import annotations

import pytest

from slo_kit.budget.burn_rate import (
    budget_consumed_fraction,
    burn_rate,
    burn_rate_from_counts,
    error_rate_from_counts,
    threshold_for_budget_fraction,
    time_to_full_burn_seconds,
)

WINDOW_30D = 30 * 86400.0
HOUR = 3600.0


@pytest.mark.parametrize(
    "good,total,expected_error_rate",
    [
        (1_000_000, 1_000_000, 0.0),
        (999_000, 1_000_000, 0.001),
        (990_000, 1_000_000, 0.01),
        (0, 1_000, 1.0),
        (500, 1_000, 0.5),
    ],
)
def test_error_rate_from_counts(good, total, expected_error_rate):
    assert error_rate_from_counts(good, total) == pytest.approx(expected_error_rate)


def test_error_rate_no_traffic():
    assert error_rate_from_counts(0, 0) == 0.0


def test_error_rate_clamps_bad_input():
    # good > total should not produce a negative error rate.
    assert error_rate_from_counts(1_500, 1_000) == 0.0


@pytest.mark.parametrize(
    "error_rate,objective,expected_burn",
    [
        (0.001, 0.999, 1.0),  # exactly at budget pace
        (0.002, 0.999, 2.0),  # 2x
        (0.0144, 0.999, 14.4),  # the classic fast-page threshold
        (0.0, 0.999, 0.0),  # no errors
        (0.01, 0.99, 1.0),  # objective 0.99 -> budget 0.01
        (0.02, 0.99, 2.0),
    ],
)
def test_burn_rate(error_rate, objective, expected_burn):
    assert burn_rate(error_rate, objective) == pytest.approx(expected_burn)


def test_burn_rate_from_counts():
    # 2000 errors in 1M, objective 0.999 (budget 0.001) -> 0.002/0.001 = 2.0
    assert burn_rate_from_counts(998_000, 1_000_000, 0.999) == pytest.approx(2.0)


def test_burn_rate_rejects_bad_objective():
    with pytest.raises(ValueError):
        burn_rate(0.01, 1.0)
    with pytest.raises(ValueError):
        burn_rate(0.01, 0.0)


def test_time_to_full_burn():
    # burn rate 1 -> whole window; burn rate 2 -> half the window.
    assert time_to_full_burn_seconds(1.0, WINDOW_30D) == pytest.approx(WINDOW_30D)
    assert time_to_full_burn_seconds(2.0, WINDOW_30D) == pytest.approx(WINDOW_30D / 2)


def test_time_to_full_burn_none_when_no_burn():
    assert time_to_full_burn_seconds(0.0, WINDOW_30D) is None
    assert time_to_full_burn_seconds(-1.0, WINDOW_30D) is None


def test_budget_consumed_fraction_matches_workbook():
    # The SRE-workbook 30d table: 14.4x over 1h burns ~2% of budget.
    frac = budget_consumed_fraction(14.4, HOUR, WINDOW_30D)
    assert frac == pytest.approx(0.02, rel=1e-3)
    # 6x over 6h burns ~5%.
    assert budget_consumed_fraction(6.0, 6 * HOUR, WINDOW_30D) == pytest.approx(0.05, rel=1e-3)


def test_threshold_is_inverse_of_consumed_fraction():
    frac = budget_consumed_fraction(14.4, HOUR, WINDOW_30D)
    threshold = threshold_for_budget_fraction(frac, HOUR, WINDOW_30D)
    assert threshold == pytest.approx(14.4)


def test_budget_consumed_fraction_rejects_bad_window():
    with pytest.raises(ValueError):
        budget_consumed_fraction(14.4, HOUR, 0)
    with pytest.raises(ValueError):
        threshold_for_budget_fraction(0.02, 0, WINDOW_30D)
