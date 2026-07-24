"""OpenTelemetry metric source.

Most OTel metrics pipelines land in a backend that speaks PromQL (the OTLP
metrics data model maps cleanly onto Prometheus, and the Collector's
``prometheus`` / ``prometheusremotewrite`` exporters are the common path). So
the OTel source is a thin specialization of the Prometheus source that applies
OTLP naming conventions to the query, keeping the same ``MetricSource``
protocol and identical evaluation behaviour.

If your OTel metrics are queried through a backend with a different API, this
class is the seam to override :meth:`scalar` for that API.
"""

from __future__ import annotations

import httpx

from .prometheus import PrometheusSource

__all__ = ["OTelSource"]


class OTelSource(PrometheusSource):
    """OTLP-metrics source backed by a PromQL-compatible query endpoint.

    Args:
        base_url: PromQL-compatible query endpoint (e.g. a Prometheus, Mimir,
            or Thanos frontend that ingests OTLP metrics).
        normalize_names: When true, apply the OTLP -> Prometheus name
            translation (``.`` -> ``_``) to metric-name-like tokens in the
            query, matching the Collector's default normalization.
    """

    def __init__(
        self,
        base_url: str,
        *,
        normalize_names: bool = True,
        timeout: float = 30.0,
        client: httpx.Client | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(base_url, timeout=timeout, client=client, headers=headers)
        self._normalize_names = normalize_names

    def scalar(self, query: str) -> float:
        return super().scalar(self._normalize(query))

    def _normalize(self, query: str) -> str:
        """Apply OTLP -> Prometheus metric-name normalization.

        OTLP metric names use dotted namespaces (``http.server.duration``)
        which the Prometheus exporter rewrites to underscores. We only rewrite
        dotted identifiers, leaving float literals (``0.999``) and label
        matchers untouched.
        """
        if not self._normalize_names:
            return query
        import re

        # Dotted identifier: a letter/underscore start, then name.parts, with
        # at least one dot between identifier chars. Avoids matching numbers.
        pattern = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+)\b")
        return pattern.sub(lambda m: m.group(1).replace(".", "_"), query)
