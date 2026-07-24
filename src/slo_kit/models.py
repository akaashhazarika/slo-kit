"""Typed domain models for SLOs.

These models are the vocabulary of the whole library: an :class:`SLO` bundles
an :class:`SLI` (how we measure success), a :class:`Target` (how reliable we
promise to be), and a :class:`Window` (over what rolling period).

Everything downstream — the budget engine, burn-rate math, and alert-rule
generation — consumes these models, so they are intentionally small and
strict.
"""

from __future__ import annotations

import re
from datetime import timedelta
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, model_validator

if TYPE_CHECKING:
    from .sources.base import MetricSource, SLISample

__all__ = ["SLI", "SLO", "AlertingConfig", "BurnCondition", "Target", "Window"]

# Accepts durations like "5m", "1h", "30d", "2w". Units follow Prometheus.
_DURATION_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*(ms|s|m|h|d|w)\s*$")
_UNIT_SECONDS: dict[str, float] = {
    "ms": 0.001,
    "s": 1.0,
    "m": 60.0,
    "h": 3600.0,
    "d": 86400.0,
    "w": 604800.0,
}


def parse_duration(value: str) -> float:
    """Parse a Prometheus-style duration string into seconds.

    >>> parse_duration("5m")
    300.0
    >>> parse_duration("30d")
    2592000.0
    """
    match = _DURATION_RE.match(value)
    if not match:
        raise ValueError(f"invalid duration {value!r}; expected e.g. '5m', '1h', '30d', '2w'")
    magnitude, unit = match.groups()
    return float(magnitude) * _UNIT_SECONDS[unit]


class Window(BaseModel):
    """A rolling time window, e.g. the 30-day SLO window or a 5m alert window."""

    model_config = ConfigDict(frozen=True)

    duration: str = Field(description="Prometheus-style duration, e.g. '30d'.")

    @model_validator(mode="after")
    def _validate_duration(self) -> Window:
        parse_duration(self.duration)  # raises on invalid input
        return self

    @property
    def seconds(self) -> float:
        return parse_duration(self.duration)

    @property
    def timedelta(self) -> timedelta:
        return timedelta(seconds=self.seconds)

    def __str__(self) -> str:
        return self.duration


class Target(BaseModel):
    """The reliability objective, e.g. ``0.999`` (three nines)."""

    model_config = ConfigDict(frozen=True)

    objective: float = Field(
        gt=0.0,
        lt=1.0,
        description="Fraction of good events required, strictly between 0 and 1.",
    )

    @property
    def error_budget(self) -> float:
        """The fraction of events allowed to fail: ``1 - objective``."""
        return 1.0 - self.objective

    def __str__(self) -> str:
        return f"{self.objective:.5g}"


class SLI(BaseModel):
    """A Service-Level Indicator expressed as a ``good / total`` event ratio.

    Both queries are source-native expressions (PromQL for the Prometheus
    source). They may contain a ``{window}`` placeholder which the source
    substitutes when it evaluates the SLI over a specific window::

        good_query: 'sum(rate(http_requests_total{code!~"5.."}[{window}]))'
        total_query: 'sum(rate(http_requests_total[{window}]))'
    """

    model_config = ConfigDict(frozen=True)

    good_query: str = Field(
        description="Query returning the count/rate of good (successful) events."
    )
    total_query: str = Field(description="Query returning the count/rate of total (valid) events.")
    description: str = ""

    @model_validator(mode="after")
    def _validate_queries(self) -> SLI:
        if not self.good_query.strip():
            raise ValueError("good_query must not be empty")
        if not self.total_query.strip():
            raise ValueError("total_query must not be empty")
        return self


class BurnCondition(BaseModel):
    """One row of a multi-window multi-burn-rate alert policy.

    A condition fires only when the burn rate over *both* the long and short
    windows exceeds ``threshold``. The long window gives sensitivity to the
    right amount of budget burn; the short "for real / still ongoing" window
    makes the alert resolve quickly once the incident ends.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    long_window: Window
    short_window: Window
    threshold: float = Field(gt=0.0, description="Burn-rate multiplier, e.g. 14.4.")
    severity: str = Field(default="page")

    @model_validator(mode="after")
    def _validate_windows(self) -> BurnCondition:
        if self.short_window.seconds >= self.long_window.seconds:
            raise ValueError(
                f"{self.name}: short_window ({self.short_window}) must be shorter "
                f"than long_window ({self.long_window})"
            )
        return self


class AlertingConfig(BaseModel):
    """Optional per-SLO alerting policy overriding the built-in defaults."""

    model_config = ConfigDict(frozen=True)

    conditions: tuple[BurnCondition, ...] = ()


class SLO(BaseModel):
    """A Service-Level Objective: an SLI held to a Target over a Window."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(pattern=r"^[a-zA-Z_][a-zA-Z0-9_.-]*$")
    description: str = ""
    service: str = ""
    sli: SLI
    target: Target
    window: Window
    labels: dict[str, str] = Field(default_factory=dict)
    alerting: AlertingConfig | None = None

    @property
    def objective(self) -> float:
        return self.target.objective

    @property
    def error_budget(self) -> float:
        return self.target.error_budget

    def sample(self, source: MetricSource, window: Window | None = None) -> SLISample:
        """Sample good/total event counts for this SLI over ``window``.

        The ``{window}`` placeholder in the SLI queries is substituted with the
        given window (defaulting to the SLO's own window) before querying.
        """
        from .sources.base import SLISample

        win = window or self.window
        good = source.scalar(self.sli.good_query.replace("{window}", win.duration))
        total = source.scalar(self.sli.total_query.replace("{window}", win.duration))
        return SLISample(good=good, total=total, window=win.duration)

    def evaluate(self, source: MetricSource, window: Window | None = None) -> float:
        """Evaluate the SLI over ``window`` and return the compliance ratio."""
        return self.sample(source, window).ratio
