"""slo-kit quickstart — load a spec, check budget, generate alerts.

Run with a live Prometheus:

    python examples/quickstart.py http://localhost:9090

Or with no argument to just print the generated alert rules (no metrics needed).
"""

from __future__ import annotations

import sys

from slo_kit import (
    PrometheusSource,
    evaluate_status,
    generate_rules_yaml,
    load_spec,
)

SPEC = "examples/checkout_slo.yaml"


def main() -> None:
    slo = load_spec(SPEC)
    print(f"Loaded SLO: {slo.name}  (objective {slo.objective:g} over {slo.window})\n")

    # Always available: generate correct multi-window burn-rate alert rules.
    print("=== Prometheus alert rules ===")
    print(generate_rules_yaml(slo))

    # If a Prometheus URL was given, sample live budget + burn rate.
    if len(sys.argv) > 1:
        source = PrometheusSource(sys.argv[1])
        status = evaluate_status(slo, source)
        print("=== Live status ===")
        print(f"SLI:              {status.sli:.5f}")
        print(f"budget remaining: {status.budget_remaining_pct:.1%}")
        print(f"1h burn rate:     {status.burn_rate('1h'):.2f}x")
        print(f"alert firing:     {status.is_firing} ({status.severity})")


if __name__ == "__main__":
    main()
