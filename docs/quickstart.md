# Quickstart

Define an SLO, check its budget, and generate correct burn-rate alerts in under
five minutes.

## 1. Install

```bash
pip install slo-kit
```

## 2. Write a spec

Save as `checkout_slo.yaml`:

```yaml
apiVersion: slo-kit/v1
name: checkout-availability
service: checkout
description: Checkout API availability
objective: 0.999          # three nines
window: 30d               # rolling 30-day window
sli:
  good_query: 'sum(rate(http_requests_total{job="checkout",code!~"5.."}[{window}]))'
  total_query: 'sum(rate(http_requests_total{job="checkout"}[{window}]))'
labels:
  team: payments
```

The `{window}` placeholder is substituted with each budget/alert window when
slo-kit evaluates the SLI.

## 3. Validate

```bash
slo-kit validate checkout_slo.yaml
```

## 4. Check live budget & burn rate

```bash
slo-kit status checkout_slo.yaml --source http://localhost:9090
```

```text
checkout-availability  (objective 0.999, 30d)
  SLI:              0.99981
  budget remaining: 81.0%
  budget consumed:  19.0%
  burn rates:       1h=0.30x, 5m=0.00x, 6h=0.50x, 30m=0.10x, 24h=0.80x, 2h=0.40x
  no alerts firing
```

## 5. Generate alert rules

```bash
slo-kit gen-alerts checkout_slo.yaml > checkout_rules.yaml
```

Load `checkout_rules.yaml` into Prometheus (`rule_files:`) — you now have
multi-window multi-burn-rate alerts.

## 6. Gate deploys (CI)

```bash
slo-kit gate checkout_slo.yaml --source http://localhost:9090 --min-budget 0.1
```

Exits non-zero when less than 10% of the budget remains, blocking risky
deploys. See [`examples/github-action-gate.yml`](https://github.com/slo-kit/slo-kit/blob/main/examples/github-action-gate.yml)
for a ready-made CI recipe.

## From Python

```python
from slo_kit import load_spec, evaluate_status, generate_rules_yaml, PrometheusSource

slo = load_spec("checkout_slo.yaml")
source = PrometheusSource("http://localhost:9090")

status = evaluate_status(slo, source)
print(f"budget remaining: {status.budget_remaining_pct:.1%}")
print(f"1h burn rate:     {status.burn_rate('1h'):.2f}x")

print(generate_rules_yaml(slo))
```
