"""Prometheus metric source.

Talks to the Prometheus HTTP API (``/api/v1/query``) and reduces the result to
a single scalar. Instant vectors with a single sample and scalar results are
both supported; multi-sample vectors are summed so that a bare selector like
``sum(rate(...))`` and an un-aggregated one behave sensibly.
"""

from __future__ import annotations

from typing import Any

import httpx

__all__ = ["PrometheusError", "PrometheusSource"]


class PrometheusError(RuntimeError):
    """Raised when Prometheus returns an error or an unusable response."""


class PrometheusSource:
    """A :class:`~slo_kit.sources.base.MetricSource` backed by Prometheus."""

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 30.0,
        client: httpx.Client | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=timeout, headers=headers or {})

    def scalar(self, query: str) -> float:
        """Run an instant query and collapse the result to a single float."""
        url = f"{self.base_url}/api/v1/query"
        try:
            resp = self._client.get(url, params={"query": query})
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise PrometheusError(f"Prometheus request failed: {exc}") from exc

        payload: dict[str, Any] = resp.json()
        if payload.get("status") != "success":
            raise PrometheusError(
                f"Prometheus query failed: {payload.get('error', 'unknown error')}"
            )
        return _reduce_result(payload.get("data", {}))

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> PrometheusSource:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def _reduce_result(data: dict[str, Any]) -> float:
    """Reduce a Prometheus query ``data`` object to a scalar.

    * ``scalar`` -> the value.
    * ``vector`` -> the single sample's value, or the sum if multiple samples.
    * empty vector -> 0.0 (no matching series == no events).
    """
    result_type = data.get("resultType")
    result = data.get("result")

    if result_type == "scalar":
        # result is [timestamp, "value"]
        if not result:
            raise PrometheusError("scalar result was empty")
        return float(result[1])

    if result_type == "vector":
        if not result:
            return 0.0
        values = [float(sample["value"][1]) for sample in result]
        return values[0] if len(values) == 1 else float(sum(values))

    raise PrometheusError(f"unsupported Prometheus resultType: {result_type!r}")
