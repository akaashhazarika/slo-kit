"""Generate Prometheus recording + alerting rules from an SLO.

Given an SLO and its multi-window policy we emit a Prometheus rule group with:

  * one **recording rule per distinct window**, recording the SLI *error
    ratio* over that window as ``slo:sli_error:ratio_rate<window>``. Recording
    rules keep the alert expressions cheap and readable.
  * one **alerting rule per burn condition**. Because
    ``burn_rate = error_ratio / (1 - objective)``, the condition
    ``burn_rate > threshold`` is equivalent to
    ``error_ratio > threshold * (1 - objective)`` — so the alert compares the
    recorded error ratios against ``threshold * error_budget`` directly, with
    no division in the alert expression.

The output is a plain dict that serializes to the exact YAML Prometheus
expects under ``groups:``. Golden-file tests pin the rendered output.
"""

from __future__ import annotations

from typing import Any

import yaml

from ..models import SLO, BurnCondition
from .multiwindow import MultiWindowPolicy, default_conditions

__all__ = [
    "build_rule_group",
    "generate_rules",
    "recording_rule_name",
]

_ERROR_RATIO_PREFIX = "slo:sli_error:ratio_rate"


def recording_rule_name(window_duration: str) -> str:
    """Metric name of the recorded error ratio for a window, e.g. ``...rate5m``."""
    return f"{_ERROR_RATIO_PREFIX}{window_duration}"


def _render_error_ratio_expr(slo: SLO, window_duration: str) -> str:
    """PromQL for the error ratio over a window: ``1 - good/total``.

    The ``{window}`` placeholder in the SLI queries is substituted with the
    concrete window duration.
    """
    good = slo.sli.good_query.replace("{window}", window_duration)
    total = slo.sli.total_query.replace("{window}", window_duration)
    return f"1 - (\n  {good}\n  /\n  {total}\n)"


def _base_labels(slo: SLO) -> dict[str, str]:
    labels = {"slo": slo.name}
    if slo.service:
        labels["service"] = slo.service
    labels.update(slo.labels)
    return labels


def _resolve_policy(slo: SLO) -> MultiWindowPolicy:
    if slo.alerting and slo.alerting.conditions:
        return MultiWindowPolicy(slo.alerting.conditions)
    return MultiWindowPolicy(default_conditions())


def _distinct_windows(policy: MultiWindowPolicy) -> list[str]:
    return list(policy.required_windows)


def _alert_name(slo: SLO, condition: BurnCondition) -> str:
    parts = [p.capitalize() for p in slo.name.replace("-", "_").split("_") if p]
    cond_parts = [p.capitalize() for p in condition.name.replace("-", "_").split("_") if p]
    return "".join(parts + cond_parts)


def build_rule_group(slo: SLO) -> dict[str, Any]:
    """Build the Prometheus rule group (as a dict) for a single SLO."""
    policy = _resolve_policy(slo)
    labels = _base_labels(slo)
    budget = slo.error_budget

    rules: list[dict[str, Any]] = []

    for window in _distinct_windows(policy):
        rules.append(
            {
                "record": recording_rule_name(window),
                "expr": _render_error_ratio_expr(slo, window),
                "labels": {**labels, "window": window},
            }
        )

    for cond in policy.conditions:
        long_metric = recording_rule_name(cond.long_window.duration)
        short_metric = recording_rule_name(cond.short_window.duration)
        # burn_rate > threshold  <=>  error_ratio > threshold * (1 - objective)
        limit = cond.threshold * budget
        label_selector = f'{{slo="{slo.name}"}}'
        expr = (
            f"(\n"
            f"  {long_metric}{label_selector} > {limit:g}\n"
            f"  and\n"
            f"  {short_metric}{label_selector} > {limit:g}\n"
            f")"
        )
        rules.append(
            {
                "alert": _alert_name(slo, cond),
                "expr": expr,
                "labels": {**labels, "severity": cond.severity, "condition": cond.name},
                "annotations": {
                    "summary": (
                        f"SLO {slo.name}: {cond.name} burn rate exceeded ({cond.threshold:g}x)"
                    ),
                    "description": (
                        f"Error budget for SLO '{slo.name}' is burning at more than "
                        f"{cond.threshold:g}x over {cond.long_window.duration} and "
                        f"{cond.short_window.duration}. Objective: {slo.objective:g}."
                    ),
                },
            }
        )

    return {"name": f"slo:{slo.name}", "rules": rules}


def generate_rules(slo: SLO) -> dict[str, Any]:
    """Return the full ``{'groups': [...]}`` structure for one SLO."""
    return {"groups": [build_rule_group(slo)]}


def generate_rules_yaml(slo: SLO) -> str:
    """Render the Prometheus rules for an SLO to a YAML string."""
    return yaml.safe_dump(generate_rules(slo), sort_keys=False, default_flow_style=False)
