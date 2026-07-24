"""The ``MetricSource`` protocol shared by all backends.

A metric source knows one thing: given a backend-native query, return a single
scalar value. Everything else — SLI evaluation, budgets, burn rates — is built
on top of that primitive, so adding a backend (Prometheus, OTel, a fake for
tests) means implementing a single method.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

__all__ = ["MetricSource", "SLISample"]


@dataclass(frozen=True)
class SLISample:
    """Good/total counts for an SLI over some window."""

    good: float
    total: float
    window: str

    @property
    def ratio(self) -> float:
        """The good ratio (SLI value); 1.0 when there is no traffic."""
        if self.total <= 0:
            return 1.0
        return min(max(self.good, 0.0), self.total) / self.total

    @property
    def error_ratio(self) -> float:
        return 1.0 - self.ratio


@runtime_checkable
class MetricSource(Protocol):
    """A backend capable of resolving a query to a single float.

    The query may contain a ``{window}`` placeholder; the caller substitutes a
    concrete duration before calling :meth:`scalar`.
    """

    def scalar(self, query: str) -> float:
        """Evaluate ``query`` and return its scalar result."""
        ...
