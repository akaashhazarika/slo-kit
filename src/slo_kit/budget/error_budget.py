"""Error-budget engine.

Given the good/total event counts observed over the SLO window and the
objective, this computes how much of the error budget has been *consumed*,
how much *remains*, and — combined with a current burn rate — an estimated
*time to exhaustion*.

All quantities are derived from three numbers (``good``, ``total``,
``objective``) so the results are trivially checkable by hand, which is
exactly how the tests validate them.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from .burn_rate import burn_rate_from_counts, error_rate_from_counts

__all__ = ["ErrorBudget", "compute_error_budget"]


@dataclass(frozen=True)
class ErrorBudget:
    """A point-in-time view of an SLO's error budget over its window.

    Attributes:
        objective: The SLO objective, e.g. ``0.999``.
        window_seconds: Length of the SLO window in seconds.
        good: Observed good events over the window.
        total: Observed total (valid) events over the window.
    """

    objective: float
    window_seconds: float
    good: float
    total: float

    @property
    def error_budget_fraction(self) -> float:
        """The allowed error fraction: ``1 - objective``."""
        return 1.0 - self.objective

    @property
    def allowed_bad_events(self) -> float:
        """Absolute budget: how many events are allowed to fail over the window."""
        return self.error_budget_fraction * self.total

    @property
    def bad_events(self) -> float:
        """Observed bad events (clamped to ``[0, total]``)."""
        good = min(max(self.good, 0.0), self.total)
        return self.total - good

    @property
    def consumed(self) -> float:
        """Absolute number of budgeted failures already spent."""
        return self.bad_events

    @property
    def remaining(self) -> float:
        """Absolute budget remaining (never negative)."""
        return max(0.0, self.allowed_bad_events - self.consumed)

    @property
    def consumed_pct(self) -> float:
        """Fraction of the budget consumed in ``[0, 1+]``.

        Values above 1.0 mean the budget is overspent (SLO violated). If the
        budget is zero (objective of 1.0 is disallowed, but total==0 yields a
        zero budget), any failure counts as fully consumed.
        """
        allowed = self.allowed_bad_events
        if allowed <= 0:
            return 0.0 if self.bad_events == 0 else float("inf")
        return self.consumed / allowed

    @property
    def remaining_pct(self) -> float:
        """Fraction of budget remaining in ``[0, 1]`` (clamped)."""
        consumed = self.consumed_pct
        if consumed == float("inf"):
            return 0.0
        return max(0.0, 1.0 - consumed)

    @property
    def is_exhausted(self) -> bool:
        """True once consumed failures meet or exceed the allowed budget."""
        return self.consumed >= self.allowed_bad_events and self.bad_events > 0

    @property
    def sli(self) -> float:
        """The observed SLI (good ratio) over the window."""
        if self.total <= 0:
            return 1.0
        return 1.0 - error_rate_from_counts(self.good, self.total)

    @property
    def current_burn_rate(self) -> float:
        """Burn rate implied by the full-window error rate."""
        return burn_rate_from_counts(self.good, self.total, self.objective)

    def time_to_exhaustion(self, burn_rate: float | None = None) -> timedelta | None:
        """Estimate time until the *remaining* budget is exhausted.

        At a constant burn rate ``B`` the entire budget empties in
        ``window / B``; the remaining fraction therefore empties in
        ``remaining_pct * window / B``.

        Args:
            burn_rate: Burn rate to project forward. Defaults to the
                full-window :attr:`current_burn_rate`.

        Returns:
            A ``timedelta``, or ``None`` if the budget is already exhausted or
            the burn rate is non-positive (never exhausts).
        """
        rate = self.current_burn_rate if burn_rate is None else burn_rate
        if rate <= 0:
            return None
        if self.remaining <= 0:
            return timedelta(0)
        seconds = self.remaining_pct * self.window_seconds / rate
        return timedelta(seconds=seconds)


def compute_error_budget(
    *, objective: float, window_seconds: float, good: float, total: float
) -> ErrorBudget:
    """Construct an :class:`ErrorBudget` (keyword-only for call-site clarity)."""
    if not 0.0 < objective < 1.0:
        raise ValueError(f"objective must be in (0, 1), got {objective}")
    if window_seconds <= 0:
        raise ValueError("window_seconds must be positive")
    if total < 0 or good < 0:
        raise ValueError("good and total counts must be non-negative")
    return ErrorBudget(objective=objective, window_seconds=window_seconds, good=good, total=total)
