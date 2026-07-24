"""``slo-kit`` command-line interface.

Commands:
    validate     Load and validate a spec file.
    status       Sample an SLO and print budget + burn-rate status.
    gen-alerts   Emit Prometheus multi-window burn-rate alert rules.
    gate         CI deploy gate; exits non-zero when the budget is spent.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated

import typer

from . import __version__
from .alerts.prometheus_rules import generate_rules_yaml
from .gate import evaluate_gate
from .models import SLO
from .report.status import evaluate_status
from .sources.base import MetricSource
from .sources.otel import OTelSource
from .sources.prometheus import PrometheusSource
from .spec import SpecError, load_specs

app = typer.Typer(
    name="slo-kit",
    help="Define SLOs as code and get correct multi-window burn-rate alerts.",
    no_args_is_help=True,
    add_completion=False,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"slo-kit {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option(
            "--version", callback=_version_callback, is_eager=True, help="Show version and exit."
        ),
    ] = False,
) -> None:
    """slo-kit: SLOs as code with correct burn-rate alerting."""


def _load(spec: Path) -> list[SLO]:
    try:
        return load_specs(spec)
    except SpecError as exc:
        typer.secho(f"error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2) from exc


def _make_source(url: str, kind: str) -> MetricSource:
    if kind == "otel":
        return OTelSource(url)
    return PrometheusSource(url)


@app.command()
def validate(
    spec: Annotated[Path, typer.Argument(help="Path to an SLO spec YAML file.")],
) -> None:
    """Load and validate one or more SLO specs."""
    specs = _load(spec)
    for slo in specs:
        typer.secho(f"✓ {slo.name}", fg=typer.colors.GREEN)
        typer.echo(f"    objective: {slo.objective:g}   window: {slo.window.duration}")
    typer.secho(f"{len(specs)} SLO(s) valid.", fg=typer.colors.GREEN, bold=True)


@app.command()
def status(
    spec: Annotated[Path, typer.Argument(help="Path to an SLO spec YAML file.")],
    source: Annotated[str, typer.Option("--source", "-s", help="Metric source URL.")],
    kind: Annotated[
        str, typer.Option("--kind", "-k", help="Source kind: prometheus|otel.")
    ] = "prometheus",
    output: Annotated[
        str, typer.Option("--output", "-o", help="Output format: text|json.")
    ] = "text",
) -> None:
    """Sample an SLO and report budget + burn-rate status."""
    specs = _load(spec)
    metric_source = _make_source(source, kind)
    reports = [evaluate_status(slo, metric_source).to_dict() for slo in specs]

    if output == "json":
        typer.echo(json.dumps(reports if len(reports) > 1 else reports[0], indent=2))
        return

    for report in reports:
        eb = report["error_budget"]
        color = typer.colors.RED if eb["is_exhausted"] else typer.colors.GREEN
        typer.secho(
            f"\n{report['slo']}  (objective {report['objective']:g}, {report['window']})", bold=True
        )
        typer.echo(f"  SLI:              {report['sli']:.5f}")
        typer.secho(f"  budget remaining: {eb['remaining_pct']:.1%}", fg=color)
        typer.echo(f"  budget consumed:  {eb['consumed_pct']:.1%}")
        ttl = eb["time_to_exhaustion_seconds"]
        if ttl is not None:
            typer.echo(f"  time to exhaust:  {ttl / 3600:.1f}h")
        typer.echo(
            "  burn rates:       "
            + ", ".join(f"{w}={r:.2f}x" for w, r in report["burn_rates"].items())
        )
        alerts = report["alerts"]
        if alerts["firing"]:
            typer.secho(
                f"  ALERT FIRING:     severity={alerts['severity']}", fg=typer.colors.RED, bold=True
            )
        else:
            typer.secho("  no alerts firing", fg=typer.colors.GREEN)


@app.command(name="gen-alerts")
def gen_alerts(
    spec: Annotated[Path, typer.Argument(help="Path to an SLO spec YAML file.")],
    out: Annotated[
        Path | None, typer.Option("--out", help="Write rules to this file instead of stdout.")
    ] = None,
) -> None:
    """Generate Prometheus multi-window burn-rate alert rules from a spec."""
    specs = _load(spec)
    rendered = "\n".join(generate_rules_yaml(slo) for slo in specs)
    if out:
        out.write_text(rendered)
        typer.secho(f"wrote rules to {out}", fg=typer.colors.GREEN, err=True)
    else:
        typer.echo(rendered)


@app.command()
def gate(
    spec: Annotated[Path, typer.Argument(help="Path to an SLO spec YAML file.")],
    source: Annotated[str, typer.Option("--source", "-s", help="Metric source URL.")],
    kind: Annotated[
        str, typer.Option("--kind", "-k", help="Source kind: prometheus|otel.")
    ] = "prometheus",
    min_budget: Annotated[
        float,
        typer.Option("--min-budget", help="Minimum remaining budget fraction (0..1) to pass."),
    ] = 0.0,
    block_on_firing: Annotated[
        bool, typer.Option("--block-on-firing", help="Also block when a burn-rate alert is firing.")
    ] = False,
) -> None:
    """CI deploy gate: exits non-zero when the error budget is spent."""
    specs = _load(spec)
    metric_source = _make_source(source, kind)
    worst_exit = 0
    for slo in specs:
        decision = evaluate_gate(
            slo, metric_source, min_budget_pct=min_budget, block_on_firing=block_on_firing
        )
        icon = "✓" if decision.passed else "✗"
        color = typer.colors.GREEN if decision.passed else typer.colors.RED
        typer.secho(f"{icon} {slo.name}: {decision.reason}", fg=color)
        worst_exit = max(worst_exit, decision.exit_code)
    raise typer.Exit(code=worst_exit)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(app())
