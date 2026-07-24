"""Programmatic SLO status: budget + burn rates + alert policy, one call.

:func:`evaluate_status` samples an SLO against a metric source and returns a
:class:`SLOStatus` bundling everything a human or dashboard needs: the current
SLI, the error-budget breakdown, per-window burn rates, projected time to
exhaustion, and whether the multi-window alert policy is firing. It also
serializes to JSON for the CLI and Grafana.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..alerts.multiwindow import MultiWindowPolicy, PolicyResult, default_conditions
from ..budget.burn_rate import burn_rate_from_counts
from ..budget.error_budget import ErrorBudget, compute_error_budget
from ..models import SLO, Window
from ..sources.base import MetricSource

__all__ = ["SLOStatus", "evaluate_status"]


@dataclass(frozen=True)
class SLOStatus:
    """A complete point-in-time status report for one SLO."""

    slo: SLO
    budget: ErrorBudget
    burn_rates: dict[str, float] = field(default_factory=dict)
    policy_result: PolicyResult | None = None

    @property
    def sli(self) -> float:
        return self.budget.sli

    @property
    def objective(self) -> float:
        return self.slo.objective

    @property
    def budget_remaining_pct(self) -> float:
        return self.budget.remaining_pct

    @property
    def budget_consumed_pct(self) -> float:
        return self.budget.consumed_pct

    @property
    def is_exhausted(self) -> bool:
        return self.budget.is_exhausted

    @property
    def is_firing(self) -> bool:
        return bool(self.policy_result and self.policy_result.firing)

    @property
    def severity(self) -> str | None:
        return self.policy_result.severity if self.policy_result else None

    def burn_rate(self, window: str) -> float:
        """Burn rate over a given window duration (must have been sampled)."""
        if window not in self.burn_rates:
            raise KeyError(
                f"no burn rate sampled for window {window!r}; available: {sorted(self.burn_rates)}"
            )
        return self.burn_rates[window]

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable status structure."""
        ttl = self.budget.time_to_exhaustion()
        return {
            "slo": self.slo.name,
            "service": self.slo.service,
            "objective": self.objective,
            "window": self.slo.window.duration,
            "sli": self.sli,
            "error_budget": {
                "allowed_bad_events": self.budget.allowed_bad_events,
                "consumed": self.budget.consumed,
                "remaining": self.budget.remaining,
                "consumed_pct": self.budget.consumed_pct,
                "remaining_pct": self.budget.remaining_pct,
                "is_exhausted": self.budget.is_exhausted,
                "time_to_exhaustion_seconds": ttl.total_seconds() if ttl else None,
            },
            "burn_rates": dict(self.burn_rates),
            "alerts": {
                "firing": self.is_firing,
                "severity": self.severity,
                "conditions": [
                    {
                        "name": r.name,
                        "severity": r.severity,
                        "firing": r.firing,
                        "long_window": r.condition.long_window.duration,
                        "short_window": r.condition.short_window.duration,
                        "threshold": r.condition.threshold,
                        "long_burn_rate": r.long_burn_rate,
                        "short_burn_rate": r.short_burn_rate,
                    }
                    for r in (self.policy_result.results if self.policy_result else ())
                ],
            },
        }


def _resolve_policy(slo: SLO) -> MultiWindowPolicy:
    if slo.alerting and slo.alerting.conditions:
        return MultiWindowPolicy(slo.alerting.conditions)
    return MultiWindowPolicy(default_conditions())


def evaluate_status(slo: SLO, source: MetricSource) -> SLOStatus:
    """Sample ``slo`` against ``source`` and build a full :class:`SLOStatus`."""
    # 1. Error budget over the full SLO window.
    window_sample = slo.sample(source)
    budget = compute_error_budget(
        objective=slo.objective,
        window_seconds=slo.window.seconds,
        good=window_sample.good,
        total=window_sample.total,
    )

    # 2. Burn rates over each window the alert policy needs.
    policy = _resolve_policy(slo)
    burn_rates: dict[str, float] = {}
    for duration in policy.required_windows:
        sample = slo.sample(source, Window(duration=duration))
        burn_rates[duration] = burn_rate_from_counts(sample.good, sample.total, slo.objective)

    policy_result = policy.evaluate(burn_rates)
    return SLOStatus(slo=slo, budget=budget, burn_rates=burn_rates, policy_result=policy_result)
