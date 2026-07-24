"""CI deploy gate: block deploys when the error budget is spent.

The pattern: run ``slo-kit gate`` in a deploy pipeline. If the SLO's error
budget is exhausted (or has fallen below a configured floor, or an alert is
already firing), the gate exits non-zero and the deploy is blocked — you don't
ship risky changes while you're already burning reliability you don't have.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import SLO
from .report.status import SLOStatus, evaluate_status
from .sources.base import MetricSource

__all__ = ["GateDecision", "evaluate_gate"]


@dataclass(frozen=True)
class GateDecision:
    """The outcome of a deploy-gate evaluation."""

    passed: bool
    reason: str
    status: SLOStatus

    @property
    def exit_code(self) -> int:
        """Process exit code: 0 = allow deploy, 1 = block."""
        return 0 if self.passed else 1


def evaluate_gate(
    slo: SLO,
    source: MetricSource,
    *,
    min_budget_pct: float = 0.0,
    block_on_firing: bool = False,
) -> GateDecision:
    """Decide whether a deploy should proceed for ``slo``.

    Args:
        slo: The SLO to gate on.
        source: Metric source to sample.
        min_budget_pct: Minimum remaining budget fraction (``0..1``) required
            to pass. ``0.0`` blocks only on full exhaustion; ``0.2`` requires
            at least 20% of the budget remaining.
        block_on_firing: When true, also block if the multi-window alert
            policy is currently firing, even if budget remains.
    """
    status = evaluate_status(slo, source)
    remaining = status.budget_remaining_pct

    if remaining <= min_budget_pct:
        return GateDecision(
            passed=False,
            reason=(
                f"error budget too low: {remaining:.1%} remaining (minimum {min_budget_pct:.1%})"
            ),
            status=status,
        )

    if block_on_firing and status.is_firing:
        return GateDecision(
            passed=False,
            reason=f"burn-rate alert firing (severity: {status.severity})",
            status=status,
        )

    return GateDecision(
        passed=True,
        reason=f"error budget healthy: {remaining:.1%} remaining",
        status=status,
    )
