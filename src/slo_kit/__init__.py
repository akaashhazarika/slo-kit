"""slo-kit: define SLOs as code and get correct multi-window burn-rate alerts.

Public API::

    from slo_kit import load_spec, evaluate_status, generate_rules_yaml

    slo = load_spec("checkout_slo.yaml")
    status = evaluate_status(slo, PrometheusSource("http://localhost:9090"))
    print(status.budget_remaining_pct)
    print(generate_rules_yaml(slo))
"""

from __future__ import annotations

from .alerts.multiwindow import MultiWindowPolicy, default_conditions
from .alerts.prometheus_rules import generate_rules, generate_rules_yaml
from .budget.burn_rate import burn_rate, burn_rate_from_counts
from .budget.error_budget import ErrorBudget, compute_error_budget
from .gate import GateDecision, evaluate_gate
from .models import SLI, SLO, AlertingConfig, BurnCondition, Target, Window
from .report.status import SLOStatus, evaluate_status
from .sources.base import MetricSource, SLISample
from .sources.otel import OTelSource
from .sources.prometheus import PrometheusSource
from .spec import SpecError, dump_spec, load_spec, load_specs

__version__ = "1.0.0"

__all__ = [
    "SLI",
    "SLO",
    "AlertingConfig",
    "BurnCondition",
    "ErrorBudget",
    "GateDecision",
    "MetricSource",
    "MultiWindowPolicy",
    "OTelSource",
    "PrometheusSource",
    "SLISample",
    "SLOStatus",
    "SpecError",
    "Target",
    "Window",
    "__version__",
    "burn_rate",
    "burn_rate_from_counts",
    "compute_error_budget",
    "default_conditions",
    "dump_spec",
    "evaluate_gate",
    "evaluate_status",
    "generate_rules",
    "generate_rules_yaml",
    "load_spec",
    "load_specs",
]
