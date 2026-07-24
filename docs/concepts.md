# Concepts

## SLI — Service-Level Indicator

An SLI is a ratio of good to total events:

$$\text{SLI} = \frac{\text{good\_events}}{\text{total\_events}}$$

In slo-kit an SLI is two queries — `good_query` and `total_query` — each of
which may contain a `{window}` placeholder that is substituted per evaluation
window.

## SLO target

The objective is the fraction of good events you promise over a **rolling
window**, e.g. `0.999` ("three nines") over `30d`.

## Error budget

The error budget is what you're *allowed* to spend:

$$\text{allowed failures} = (1 - \text{target}) \times \text{total}$$

slo-kit tracks:

- **consumed** — bad events observed over the window,
- **remaining** — `allowed - consumed` (never negative),
- **remaining %** — fraction of budget left, and
- **time to exhaustion** — how long until the remaining budget is gone at the
  current (or a projected) burn rate.

## Burn rate

The burn rate is how fast you're spending budget relative to the pace that
would exactly exhaust it over the whole window:

$$\text{burn\_rate} = \frac{\text{observed\_error\_rate}}{1 - \text{target}}$$

- `burn_rate == 1` → on track to spend exactly 100% of the budget over the window.
- `burn_rate == 2` → the whole budget gone in half the window.
- `burn_rate == 14.4` over 30 days → the whole budget gone in ~50 hours.

At a constant burn rate `B`, the full budget empties in `window / B`.

## Multi-window multi-burn-rate alerting

Alerting on a single window forces a bad trade-off. A short window pages fast
but cries wolf; a long window is stable but slow to fire and slow to reset. The
SRE-workbook fix requires **two windows simultaneously**:

- a **long window** — how much budget is burning, and
- a **short window** (≈ 1/12 of the long one) — is the burn *still happening
  right now?*

The short window is the reset gate: it recovers quickly once errors stop, so
the alert clears promptly. slo-kit stacks several such conditions at different
severities:

| severity | long | short | burn rate | budget burned before firing (30d) |
|----------|------|-------|-----------|-----------------------------------|
| page     | 1h   | 5m    | 14.4×     | 2%   |
| page     | 6h   | 30m   | 6×        | 5%   |
| ticket   | 24h  | 2h    | 3×        | 10%  |

A condition fires iff the burn rate over **both** its windows exceeds the
threshold. The policy fires if **any** condition fires. The highest-priority
severity among firing conditions (`page` before `ticket`) is reported.

Because `burn_rate = error_ratio / (1 - target)`, the condition
`burn_rate > threshold` is equivalent to
`error_ratio > threshold × (1 - target)`. That identity is exactly what
[`generate_rules`](api.md) emits into Prometheus, so no division appears in the
alert expression.
