"""Multi-window, multi-burn-rate alerting — the differentiating core.

This implements the alerting strategy from the Google SRE Workbook
("Alerting on SLOs", multiwindow multi-burn-rate). The problem it solves:

  * Alert on a *single long window* (e.g. burn rate over 1h) and you detect
    slow burns but page slowly and keep paging long after an incident ends
    (poor reset time).
  * Alert on a *single short window* and you page fast but with lots of false
    positives from brief blips.

The fix is to require **two conditions simultaneously**: a *long* window (the
one that defines how much budget is being burned) **AND** a *short* window
(a fraction of the long one — typically 1/12) that must *also* be burning.
The short window is the "is this still happening right now?" gate: it makes
the alert fire quickly, and — crucially — *stop* firing quickly once errors
subside, because the short window recovers long before the long window does.

We then stack several such (long, short, threshold) conditions at different
severities so a catastrophic burn pages immediately while a slow leak opens a
ticket:

    | severity | long | short | burn rate | budget burned before firing |
    |----------|------|-------|-----------|-----------------------------|
    | page     | 1h   | 5m    | 14.4      | 2%   (over a 30d window)    |
    | page     | 6h   | 30m   | 6         | 5%                          |
    | ticket   | 24h  | 2h    | 3         | 10%                         |

A :class:`MultiWindowPolicy` fires when *any* of its conditions fire, and each
condition fires only when the burn rate over *both* its windows exceeds its
threshold.

The module is pure logic over a mapping of ``window -> burn_rate``; it does no
I/O and is validated against an explicit truth table in the tests.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from ..models import BurnCondition, Window

__all__ = [
    "ConditionResult",
    "MultiWindowPolicy",
    "PolicyResult",
    "default_conditions",
]


def default_conditions() -> tuple[BurnCondition, ...]:
    """The canonical SRE-workbook conditions for a 30-day SLO window.

    Two paging conditions (fast + medium burn) and one ticket condition
    (slow burn). Callers can override these per-SLO via ``AlertingConfig``.
    """
    return (
        BurnCondition(
            name="fast_burn",
            long_window=Window(duration="1h"),
            short_window=Window(duration="5m"),
            threshold=14.4,
            severity="page",
        ),
        BurnCondition(
            name="slow_burn",
            long_window=Window(duration="6h"),
            short_window=Window(duration="30m"),
            threshold=6.0,
            severity="page",
        ),
        BurnCondition(
            name="slower_burn",
            long_window=Window(duration="24h"),
            short_window=Window(duration="2h"),
            threshold=3.0,
            severity="ticket",
        ),
    )


@dataclass(frozen=True)
class ConditionResult:
    """Outcome of evaluating a single :class:`BurnCondition`."""

    condition: BurnCondition
    long_burn_rate: float
    short_burn_rate: float
    firing: bool

    @property
    def name(self) -> str:
        return self.condition.name

    @property
    def severity(self) -> str:
        return self.condition.severity


@dataclass(frozen=True)
class PolicyResult:
    """Outcome of evaluating a whole :class:`MultiWindowPolicy`."""

    results: tuple[ConditionResult, ...]

    @property
    def firing(self) -> bool:
        return any(r.firing for r in self.results)

    @property
    def firing_conditions(self) -> tuple[ConditionResult, ...]:
        return tuple(r for r in self.results if r.firing)

    @property
    def severity(self) -> str | None:
        """Highest-priority severity currently firing, or ``None``.

        ``page`` outranks ``ticket``; unknown severities sort last.
        """
        firing = self.firing_conditions
        if not firing:
            return None
        order = {"page": 0, "ticket": 1}
        return min((r.severity for r in firing), key=lambda s: order.get(s, 99))


class MultiWindowPolicy:
    """A set of multi-window burn-rate conditions evaluated together."""

    def __init__(self, conditions: Iterable[BurnCondition] | None = None) -> None:
        conds = tuple(conditions) if conditions is not None else default_conditions()
        if not conds:
            raise ValueError("a MultiWindowPolicy needs at least one condition")
        self.conditions: tuple[BurnCondition, ...] = conds

    @property
    def required_windows(self) -> tuple[str, ...]:
        """All distinct window durations this policy needs burn rates for."""
        seen: dict[str, None] = {}
        for c in self.conditions:
            seen.setdefault(c.long_window.duration, None)
            seen.setdefault(c.short_window.duration, None)
        return tuple(seen)

    def evaluate(self, burn_rates: Mapping[str, float]) -> PolicyResult:
        """Evaluate the policy against a mapping of ``window -> burn_rate``.

        Each condition fires iff the burn rate over *both* its long and short
        windows is strictly greater than the condition's threshold.
        """
        results = []
        for cond in self.conditions:
            long_key = cond.long_window.duration
            short_key = cond.short_window.duration
            if long_key not in burn_rates:
                raise KeyError(f"missing burn rate for window {long_key!r}")
            if short_key not in burn_rates:
                raise KeyError(f"missing burn rate for window {short_key!r}")
            long_br = burn_rates[long_key]
            short_br = burn_rates[short_key]
            firing = long_br > cond.threshold and short_br > cond.threshold
            results.append(
                ConditionResult(
                    condition=cond,
                    long_burn_rate=long_br,
                    short_burn_rate=short_br,
                    firing=firing,
                )
            )
        return PolicyResult(results=tuple(results))

    def is_firing(self, burn_rates: Mapping[str, float]) -> bool:
        return self.evaluate(burn_rates).firing
