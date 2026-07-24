"""Metric-source tests with mocked HTTP (no real Prometheus)."""

from __future__ import annotations

import httpx
import pytest

from slo_kit.sources.base import MetricSource, SLISample
from slo_kit.sources.otel import OTelSource
from slo_kit.sources.prometheus import PrometheusError, PrometheusSource


def _mock_client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_sli_sample_ratio():
    s = SLISample(good=990, total=1000, window="5m")
    assert s.ratio == pytest.approx(0.99)
    assert s.error_ratio == pytest.approx(0.01)


def test_sli_sample_no_traffic():
    assert SLISample(good=0, total=0, window="5m").ratio == 1.0


def test_prometheus_scalar_vector():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/query"
        return httpx.Response(
            200,
            json={
                "status": "success",
                "data": {"resultType": "vector", "result": [{"value": [0, "42.5"]}]},
            },
        )

    src = PrometheusSource("http://prom:9090", client=_mock_client(handler))
    assert src.scalar("up") == pytest.approx(42.5)


def test_prometheus_scalar_type():
    def handler(request):
        return httpx.Response(
            200,
            json={"status": "success", "data": {"resultType": "scalar", "result": [0, "7"]}},
        )

    src = PrometheusSource("http://prom:9090", client=_mock_client(handler))
    assert src.scalar("scalar(2+5)") == 7.0


def test_prometheus_empty_vector_is_zero():
    def handler(request):
        return httpx.Response(
            200, json={"status": "success", "data": {"resultType": "vector", "result": []}}
        )

    src = PrometheusSource("http://prom:9090", client=_mock_client(handler))
    assert src.scalar("missing_metric") == 0.0


def test_prometheus_sums_multiple_samples():
    def handler(request):
        return httpx.Response(
            200,
            json={
                "status": "success",
                "data": {
                    "resultType": "vector",
                    "result": [{"value": [0, "1"]}, {"value": [0, "2"]}, {"value": [0, "3"]}],
                },
            },
        )

    src = PrometheusSource("http://prom:9090", client=_mock_client(handler))
    assert src.scalar("x") == pytest.approx(6.0)


def test_prometheus_error_status():
    def handler(request):
        return httpx.Response(200, json={"status": "error", "error": "bad query"})

    src = PrometheusSource("http://prom:9090", client=_mock_client(handler))
    with pytest.raises(PrometheusError, match="bad query"):
        src.scalar("garbage{")


def test_prometheus_http_error():
    def handler(request):
        return httpx.Response(500, text="boom")

    src = PrometheusSource("http://prom:9090", client=_mock_client(handler))
    with pytest.raises(PrometheusError):
        src.scalar("up")


def test_prometheus_is_metric_source():
    src = PrometheusSource("http://prom:9090")
    assert isinstance(src, MetricSource)


def test_otel_normalizes_dotted_names():
    seen = {}

    def handler(request):
        seen["query"] = dict(request.url.params)["query"]
        return httpx.Response(
            200,
            json={
                "status": "success",
                "data": {"resultType": "vector", "result": [{"value": [0, "1"]}]},
            },
        )

    src = OTelSource("http://otel:9090", client=_mock_client(handler))
    src.scalar("sum(rate(http.server.request.count[5m]))")
    assert "http_server_request_count" in seen["query"]
    # A float literal like 0.999 must NOT be rewritten.
    src.scalar("http.errors > 0.999")
    assert "0.999" in seen["query"]
    assert "http_errors" in seen["query"]


def test_otel_normalization_can_be_disabled():
    seen = {}

    def handler(request):
        seen["query"] = dict(request.url.params)["query"]
        return httpx.Response(
            200,
            json={
                "status": "success",
                "data": {"resultType": "vector", "result": [{"value": [0, "1"]}]},
            },
        )

    src = OTelSource("http://otel:9090", normalize_names=False, client=_mock_client(handler))
    src.scalar("http.server.count")
    assert seen["query"] == "http.server.count"
