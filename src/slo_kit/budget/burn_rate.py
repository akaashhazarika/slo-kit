"""Burn-rate math — the beating heart of SLO alerting.

**Definition.** The *burn rate* is how fast we are consuming the error budget
relative to the pace that would exactly exhaust it over the SLO window:

    burn_rate = observed_error_rate / error_budget
              = observed_error_rate / (1 - objective)

where ``observed_error_rate`` is the fraction of *bad* events measured over
some (usually short) window.

**Why divide by the error budget?** The error budget is the maximum error rate
you can sustain for the *entire* SLO window and still exactly meet the
objective. So:

    * burn_rate == 1  -> you are on track to spend 100% of the budget over the
                         whole window (right at the objective).
    * burn_rate == 2  -> you would exhaust the whole budget in half the window.
    * burn_rate == 14.4 over 30 days -> the whole budget gone in ~50 hours,
                         which is why 14.4 is the classic fast-page threshold.

The general identity: at a constant burn rate ``B``, the full budget is
consumed in ``window / B``. Every threshold in the multi-window tables is just
a choice of "how much of the budget are we willing to let a single incident
burn before we page?" — see :mod:`slo_kit.alerts.multiwindow`.

This module is pure arithmetic on counts/ratios: no I/O, fully deterministic,
and exhaustively unit-tested against hand-computed values.
"""

from __future__ import annotations

__all__ = [
    "budget_consumed_fraction",
    "burn_rate",
    "burn_rate_from_counts",
    "error_rate_from_counts",
    "threshold_for_budget_fraction",
    "time_to_full_burn_seconds",
]


def error_rate_from_counts(good: float, total: float) -> float:
    """Fraction of bad events: ``(total - good) / total``.

    A total of zero means "no traffic", which we treat as a 0.0 error rate
    (you cannot fail requests you never received). ``good`` is clamped to
    ``[0, total]`` so noisy inputs cannot produce a negative or >1 error rate.
    """
    if total <= 0:
        return 0.0
    good = min(max(good, 0.0), total)
    return (total - good) / total


def burn_rate(error_rate: float, objective: float) -> float:
    """Burn rate from an already-computed error rate and the objective.

    ``burn_rate = error_rate / (1 - objective)``.
    """
    if not 0.0 < objective < 1.0:
        raise ValueError(f"objective must be in (0, 1), got {objective}")
    budget = 1.0 - objective
    return error_rate / budget


def burn_rate_from_counts(good: float, total: float, objective: float) -> float:
    """Burn rate computed directly from good/total event counts."""
    return burn_rate(error_rate_from_counts(good, total), objective)


def time_to_full_burn_seconds(current_burn_rate: float, window_seconds: float) -> float | None:
    """Seconds to exhaust a *full, fresh* budget at ``current_burn_rate``.

    Returns ``None`` when the burn rate is non-positive (budget never
    exhausts). Note this is time to burn the *entire* budget; to account for a
    budget that is already partly consumed, use
    :meth:`slo_kit.budget.error_budget.ErrorBudget.time_to_exhaustion`.
    """
    if current_burn_rate <= 0:
        return None
    return window_seconds / current_burn_rate


def budget_consumed_fraction(
    threshold: float, alert_window_seconds: float, slo_window_seconds: float
) -> float:
    """Fraction of the total budget consumed if a burn of ``threshold`` runs
    for exactly ``alert_window_seconds``.

    This is the "budget consumed before alert" column in the SRE workbook
    tables: ``threshold * alert_window / slo_window``.
    """
    if slo_window_seconds <= 0:
        raise ValueError("slo_window_seconds must be positive")
    return threshold * alert_window_seconds / slo_window_seconds


def threshold_for_budget_fraction(
    budget_fraction: float, alert_window_seconds: float, slo_window_seconds: float
) -> float:
    """Inverse of :func:`budget_consumed_fraction`.

    Given the fraction of budget you're willing to burn within an alert window,
    return the burn-rate threshold that corresponds to it. Handy for deriving
    custom multi-window tables for non-standard SLO windows.
    """
    if alert_window_seconds <= 0:
        raise ValueError("alert_window_seconds must be positive")
    return budget_fraction * slo_window_seconds / alert_window_seconds
