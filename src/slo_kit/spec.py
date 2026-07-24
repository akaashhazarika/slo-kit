"""Load and validate SLO specs from YAML (or plain Python dicts).

The YAML schema mirrors the models but uses friendly scalar fields so specs
read naturally::

    apiVersion: slo-kit/v1
    name: checkout-availability
    service: checkout
    description: Checkout API availability
    objective: 0.999
    window: 30d
    sli:
      good_query: 'sum(rate(http_requests_total{job="checkout",code!~"5.."}[{window}]))'
      total_query: 'sum(rate(http_requests_total{job="checkout"}[{window}]))'
    labels:
      team: payments
    alerting:
      conditions:
        - name: fast_burn
          long_window: 1h
          short_window: 5m
          threshold: 14.4
          severity: page
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from .models import SLI, SLO, AlertingConfig, BurnCondition, Target, Window

__all__ = ["SpecError", "dump_spec", "load_spec", "load_spec_dict", "load_specs"]

SUPPORTED_API_VERSIONS = {"slo-kit/v1"}


class SpecError(ValueError):
    """Raised when a spec is structurally invalid."""


def _coerce_window(value: Any) -> dict[str, str]:
    if isinstance(value, str):
        return {"duration": value}
    if isinstance(value, dict):
        return value
    raise SpecError(f"window must be a duration string or mapping, got {value!r}")


def _build_condition(raw: dict[str, Any]) -> BurnCondition:
    data = dict(raw)
    if "long_window" in data:
        data["long_window"] = _coerce_window(data["long_window"])
    if "short_window" in data:
        data["short_window"] = _coerce_window(data["short_window"])
    return BurnCondition(**data)


def load_spec_dict(data: dict[str, Any]) -> SLO:
    """Build a validated :class:`SLO` from an already-parsed mapping."""
    if not isinstance(data, dict):
        raise SpecError(f"spec must be a mapping, got {type(data).__name__}")

    api_version = data.get("apiVersion", "slo-kit/v1")
    if api_version not in SUPPORTED_API_VERSIONS:
        raise SpecError(
            f"unsupported apiVersion {api_version!r}; supported: {sorted(SUPPORTED_API_VERSIONS)}"
        )

    sli_raw = data.get("sli")
    if not isinstance(sli_raw, dict):
        raise SpecError("spec is missing an 'sli' mapping")

    if "objective" not in data:
        raise SpecError("spec is missing 'objective'")
    if "window" not in data:
        raise SpecError("spec is missing 'window'")

    alerting = None
    alerting_raw = data.get("alerting")
    if alerting_raw is not None:
        if not isinstance(alerting_raw, dict):
            raise SpecError("'alerting' must be a mapping")
        conditions = tuple(_build_condition(c) for c in alerting_raw.get("conditions", []))
        alerting = AlertingConfig(conditions=conditions)

    try:
        return SLO(
            name=data["name"],
            description=data.get("description", ""),
            service=data.get("service", ""),
            sli=SLI(**sli_raw),
            target=Target(objective=float(data["objective"])),
            window=Window(**_coerce_window(data["window"])),
            labels=data.get("labels", {}) or {},
            alerting=alerting,
        )
    except KeyError as exc:
        raise SpecError(f"spec is missing required field: {exc}") from exc
    except ValidationError as exc:
        raise SpecError(f"invalid spec:\n{exc}") from exc


def load_spec(path: str | Path) -> SLO:
    """Load a single SLO spec from a YAML file."""
    path = Path(path)
    try:
        raw = yaml.safe_load(path.read_text())
    except FileNotFoundError as exc:
        raise SpecError(f"spec file not found: {path}") from exc
    except yaml.YAMLError as exc:
        raise SpecError(f"could not parse YAML in {path}: {exc}") from exc
    if raw is None:
        raise SpecError(f"spec file is empty: {path}")
    return load_spec_dict(raw)


def load_specs(path: str | Path) -> list[SLO]:
    """Load one or more SLO specs from a YAML file (supports multi-doc YAML)."""
    path = Path(path)
    try:
        docs = list(yaml.safe_load_all(path.read_text()))
    except FileNotFoundError as exc:
        raise SpecError(f"spec file not found: {path}") from exc
    except yaml.YAMLError as exc:
        raise SpecError(f"could not parse YAML in {path}: {exc}") from exc
    specs = [load_spec_dict(doc) for doc in docs if doc is not None]
    if not specs:
        raise SpecError(f"no SLO specs found in {path}")
    return specs


def dump_spec(slo: SLO) -> str:
    """Serialize an :class:`SLO` back to canonical YAML."""
    doc: dict[str, Any] = {
        "apiVersion": "slo-kit/v1",
        "name": slo.name,
        "service": slo.service,
        "description": slo.description,
        "objective": slo.objective,
        "window": slo.window.duration,
        "sli": {
            "good_query": slo.sli.good_query,
            "total_query": slo.sli.total_query,
        },
    }
    if slo.labels:
        doc["labels"] = dict(slo.labels)
    if slo.alerting and slo.alerting.conditions:
        doc["alerting"] = {
            "conditions": [
                {
                    "name": c.name,
                    "long_window": c.long_window.duration,
                    "short_window": c.short_window.duration,
                    "threshold": c.threshold,
                    "severity": c.severity,
                }
                for c in slo.alerting.conditions
            ]
        }
    return yaml.safe_dump(doc, sort_keys=False)
