# slo-kit

> **Stop hand-rolling SLO alerts.** Define SLOs as code and get correct
> multi-window burn-rate Prometheus alerts for free.

`slo-kit` turns raw Prometheus / OpenTelemetry metrics into:

- **SLO definitions as code** — SLI query + target + rolling window.
- **Live error-budget & burn-rate tracking** — consumed, remaining, time-to-exhaustion.
- **Correct multi-window / multi-burn-rate Prometheus alert rules** — per the
  Google SRE workbook.

SLO math is subtle and commonly implemented incorrectly. slo-kit packages it
correctly and reusably.

## Install

```bash
pip install slo-kit
# or
docker run --rm ghcr.io/slo-kit/slo-kit --help
```

## Where to next

- [Quickstart](quickstart.md) — define, validate, and alert in under 5 minutes.
- [Concepts](concepts.md) — SLI, error budget, burn rate, multi-window alerting.
- [CLI](cli.md) — `validate`, `status`, `gen-alerts`, `gate`.
- [API reference](api.md) — the Python API.
