"""Prometheus rule-generation tests, including a golden-file comparison."""

from __future__ import annotations

from pathlib import Path

import yaml

from slo_kit.alerts.prometheus_rules import (
    build_rule_group,
    generate_rules,
    generate_rules_yaml,
    recording_rule_name,
)
from slo_kit.spec import load_spec

GOLDEN = Path(__file__).parent / "golden" / "checkout_rules.yaml"
EXAMPLE = Path(__file__).parents[1] / "examples" / "checkout_slo.yaml"


def test_recording_rule_name():
    assert recording_rule_name("5m") == "slo:sli_error:ratio_rate5m"


def test_generate_rules_is_valid_yaml():
    slo = load_spec(EXAMPLE)
    rendered = generate_rules_yaml(slo)
    parsed = yaml.safe_load(rendered)
    assert "groups" in parsed
    assert parsed["groups"][0]["name"] == "slo:checkout-availability"


def test_recording_rule_per_window():
    slo = load_spec(EXAMPLE)
    group = build_rule_group(slo)
    records = [r["record"] for r in group["rules"] if "record" in r]
    # 3 conditions -> 6 windows: 1h,5m,6h,30m,24h,2h (all distinct here).
    assert set(records) == {
        "slo:sli_error:ratio_rate1h",
        "slo:sli_error:ratio_rate5m",
        "slo:sli_error:ratio_rate6h",
        "slo:sli_error:ratio_rate30m",
        "slo:sli_error:ratio_rate24h",
        "slo:sli_error:ratio_rate2h",
    }


def test_window_substituted_into_recording_expr():
    slo = load_spec(EXAMPLE)
    group = build_rule_group(slo)
    rule_5m = next(r for r in group["rules"] if r.get("record", "").endswith("rate5m"))
    assert "[5m]" in rule_5m["expr"]
    assert "{window}" not in rule_5m["expr"]


def test_alert_threshold_is_burn_rate_times_budget():
    slo = load_spec(EXAMPLE)  # objective 0.999 -> budget 0.001
    group = build_rule_group(slo)
    fast = next(r for r in group["rules"] if r.get("alert", "").endswith("FastBurn"))
    # 14.4 * 0.001 = 0.0144
    assert "0.0144" in fast["expr"]
    assert fast["labels"]["severity"] == "page"
    # Both windows must appear, joined by 'and'.
    assert "ratio_rate1h" in fast["expr"]
    assert "ratio_rate5m" in fast["expr"]
    assert "\n  and\n" in fast["expr"]


def test_alert_names_and_severities():
    slo = load_spec(EXAMPLE)
    group = build_rule_group(slo)
    alerts = {r["alert"]: r["labels"]["severity"] for r in group["rules"] if "alert" in r}
    assert alerts == {
        "CheckoutAvailabilityFastBurn": "page",
        "CheckoutAvailabilitySlowBurn": "page",
        "CheckoutAvailabilitySlowerBurn": "ticket",
    }


def test_default_policy_used_when_no_alerting_config(make_slo_fixture):
    slo = make_slo_fixture()  # no alerting block
    rules = generate_rules(slo)
    alerts = [r["alert"] for r in rules["groups"][0]["rules"] if "alert" in r]
    assert len(alerts) == 3  # default fast/slow/slower


def test_labels_propagated():
    slo = load_spec(EXAMPLE)
    group = build_rule_group(slo)
    rec = next(r for r in group["rules"] if "record" in r)
    assert rec["labels"]["slo"] == "checkout-availability"
    assert rec["labels"]["service"] == "checkout"
    assert rec["labels"]["team"] == "payments"


def test_golden_file_matches():
    slo = load_spec(EXAMPLE)
    rendered = generate_rules_yaml(slo)
    if not GOLDEN.exists():  # pragma: no cover - first-run bootstrap
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(rendered)
    assert rendered == GOLDEN.read_text(), (
        "generated rules drifted from golden file; if intentional, delete "
        f"{GOLDEN} and re-run to regenerate."
    )
