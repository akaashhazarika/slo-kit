# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-07-23

First stable release. Full SLO-as-code toolkit: typed models, YAML/Python spec
loader, Prometheus + OpenTelemetry sources, error-budget engine, burn-rate math,
multi-window multi-burn-rate alerting, Prometheus rule generation, CLI, CI
deploy gate, Docker image, and docs.

### Added
- `models` — typed `SLO`, `SLI`, `Window`, `Target`, `BurnCondition` (pydantic v2).
- `spec` — load/validate SLO specs from YAML (single- and multi-doc) or dicts.
- `sources` — `MetricSource` protocol, `PrometheusSource`, `OTelSource`.
- `budget/burn_rate` — burn-rate math and budget-fraction/threshold conversions.
- `budget/error_budget` — consumed / remaining / remaining % / time-to-exhaustion.
- `alerts/multiwindow` — multi-window multi-burn-rate policy with SRE-workbook defaults.
- `alerts/prometheus_rules` — recording + alerting rule generation.
- `report/status` — programmatic status with JSON output.
- `gate` — CI deploy gate (`slo-kit gate`).
- `cli` — `validate`, `status`, `gen-alerts`, `gate`.
- Grafana dashboard, multi-stage Dockerfile, mkdocs-material docs, GitHub Actions CI.

[1.0.0]: https://github.com/slo-kit/slo-kit/releases/tag/v1.0.0
