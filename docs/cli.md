# CLI

```text
slo-kit [OPTIONS] COMMAND [ARGS]...
```

Global options:

- `--version` — print the version and exit.

## `validate`

Load and validate one or more SLO specs (supports multi-document YAML).

```bash
slo-kit validate checkout_slo.yaml
```

Exit code `2` on an invalid spec.

## `status`

Sample an SLO against a metric source and report budget + burn-rate status.

```bash
slo-kit status checkout_slo.yaml --source http://localhost:9090
slo-kit status checkout_slo.yaml -s http://localhost:9090 --output json
```

Options:

- `--source, -s` — metric source URL (required).
- `--kind, -k` — `prometheus` (default) or `otel`.
- `--output, -o` — `text` (default) or `json`.

## `gen-alerts`

Generate Prometheus multi-window burn-rate alert rules from a spec.

```bash
slo-kit gen-alerts checkout_slo.yaml            # to stdout
slo-kit gen-alerts checkout_slo.yaml --out rules.yaml
```

## `gate`

CI deploy gate. Exits non-zero when the error budget is spent.

```bash
slo-kit gate checkout_slo.yaml --source http://localhost:9090 --min-budget 0.1
```

Options:

- `--source, -s` — metric source URL (required).
- `--kind, -k` — `prometheus` (default) or `otel`.
- `--min-budget` — minimum remaining budget fraction (`0..1`) required to pass.
- `--block-on-firing` — also block when a burn-rate alert is currently firing.

Exit code `0` allows the deploy; `1` blocks it.
