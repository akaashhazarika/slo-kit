# slo-kit

> **Stop hand-rolling SLO alerts.** Define SLOs as code and get correct
> multi-window burn-rate Prometheus alerts for free.

[![CI](https://github.com/slo-kit/slo-kit/actions/workflows/ci.yml/badge.svg)](https://github.com/slo-kit/slo-kit/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/slo-kit.svg)](https://pypi.org/project/slo-kit/)
[![Python](https://img.shields.io/pypi/pyversions/slo-kit.svg)](https://pypi.org/project/slo-kit/)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

`slo-kit` turns raw Prometheus / OpenTelemetry metrics into:

- **SLO definitions as code** — SLI query + target + rolling window, in YAML or Python.
- **Live error-budget & burn-rate tracking** — consumed, remaining, and time-to-exhaustion.
- **Correct multi-window / multi-burn-rate Prometheus alert rules** — per the Google SRE workbook.

SLO math (error budgets, multi-window multi-burn-rate alerting) is subtle and
commonly implemented incorrectly. `slo-kit` packages it correctly and reusably,
so you define reliability targets and get paged on budget burn **without
hand-rolling brittle PromQL**.

## Install

```bash
pip install slo-kit
# or
docker run --rm ghcr.io/slo-kit/slo-kit --help
```

## Quickstart (< 5 minutes)

**1. Define an SLO** (`checkout_slo.yaml`):

```yaml
apiVersion: slo-kit/v1
name: checkout-availability
service: checkout
description: Checkout API availability
objective: 0.999          # three nines
window: 30d               # rolling 30-day window
sli:
  # {window} is substituted per alert/budget window
  good_query: 'sum(rate(http_requests_total{job="checkout",code!~"5.."}[{window}]))'
  total_query: 'sum(rate(http_requests_total{job="checkout"}[{window}]))'
labels:
  team: payments
```

**2. Validate it:**

```bash
slo-kit validate checkout_slo.yaml
```

**3. Check live budget & burn rate:**

```bash
slo-kit status checkout_slo.yaml --source http://localhost:9090
```

**4. Generate correct multi-window burn-rate alerts:**

```bash
slo-kit gen-alerts checkout_slo.yaml > checkout_rules.yaml
```

**5. Gate deploys on remaining budget (CI):**

```bash
slo-kit gate checkout_slo.yaml --source http://localhost:9090 --min-budget 0.1
# exits non-zero when < 10% budget remains
```

### From Python

```python
from slo_kit import load_spec, evaluate_status, generate_rules_yaml
from slo_kit import PrometheusSource

slo = load_spec("checkout_slo.yaml")
source = PrometheusSource("http://localhost:9090")

status = evaluate_status(slo, source)
print(f"budget remaining: {status.budget_remaining_pct:.1%}")
print(f"1h burn rate:     {status.burn_rate('1h'):.2f}x")

print(generate_rules_yaml(slo))   # Prometheus alerting rules
```

## Why multi-window multi-burn-rate?

Alerting on a single window forces a bad trade-off: short windows page fast but
cry wolf; long windows are stable but slow to fire and slow to reset. The SRE
workbook fix is to require **two windows at once** — a long window that
measures how much budget is burning, and a short window (≈1/12 of it) that
confirms the burn is *still happening right now*:

| severity | long | short | burn rate | budget burned before firing (30d) |
|----------|------|-------|-----------|-----------------------------------|
| page     | 1h   | 5m    | 14.4×     | 2%   |
| page     | 6h   | 30m   | 6×        | 5%   |
| ticket   | 24h  | 2h    | 3×        | 10%  |

`slo-kit` implements this in [`alerts/multiwindow.py`](src/slo_kit/alerts/multiwindow.py)
and emits the equivalent Prometheus rules from
[`alerts/prometheus_rules.py`](src/slo_kit/alerts/prometheus_rules.py) — validated
against an explicit truth table and golden files.

## Core concepts

- **SLI** — `good_events / total_events` from a metric query.
- **SLO target** — e.g. `0.999` over a rolling window (e.g. `30d`).
- **Error budget** — allowed failures `= (1 - target) × total`; track consumed,
  remaining, remaining %, and time-to-exhaustion.
- **Burn rate** — `observed_error_rate / (1 - target)`; a burn rate of `1`
  exactly exhausts the budget over the window, `>1` is too fast.
- **Multi-window multi-burn-rate alerts** — fast + slow burn condition sets to
  balance fast detection against low false positives.

See the [documentation](https://slo-kit.github.io/slo-kit/) for concepts, the
full API, and examples.

## Development

```bash
pip install -e ".[dev]"
ruff check . && ruff format --check .
mypy src/slo_kit
pytest --cov=slo_kit --cov-report=term-missing
```

## License

[Apache-2.0](LICENSE).
