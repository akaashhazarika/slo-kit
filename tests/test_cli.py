"""CLI smoke tests via typer's CliRunner."""

from __future__ import annotations

from pathlib import Path

import yaml
from tests.conftest import FakeSource
from typer.testing import CliRunner

import slo_kit.cli as cli_module
from slo_kit.cli import app

runner = CliRunner()
EXAMPLE = str(Path(__file__).parents[1] / "examples" / "checkout_slo.yaml")
# FakeSource distinguishes good/total by query prefix, so status/gate tests use
# a spec whose queries start with "good"/"total".
FAKE_SPEC = str(Path(__file__).parent / "data" / "fake_slo.yaml")

HEALTHY = {
    "30d": (1_000_000, 1_000_000),
    "1h": (1_000, 1_000),
    "5m": (1_000, 1_000),
    "6h": (1_000, 1_000),
    "30m": (1_000, 1_000),
    "24h": (1_000, 1_000),
    "2h": (1_000, 1_000),
}
BURNING = {
    "30d": (985_000, 1_000_000),
    "1h": (985, 1_000),
    "5m": (985, 1_000),
    "6h": (985, 1_000),
    "30m": (985, 1_000),
    "24h": (985, 1_000),
    "2h": (985, 1_000),
}


def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "slo-kit" in result.output


def test_validate_ok():
    result = runner.invoke(app, ["validate", EXAMPLE])
    assert result.exit_code == 0
    assert "checkout-availability" in result.output
    assert "valid" in result.output


def test_validate_bad_file():
    result = runner.invoke(app, ["validate", "/nope.yaml"])
    assert result.exit_code == 2


def test_gen_alerts_stdout():
    result = runner.invoke(app, ["gen-alerts", EXAMPLE])
    assert result.exit_code == 0
    parsed = yaml.safe_load(result.output)
    assert parsed["groups"][0]["name"] == "slo:checkout-availability"


def test_gen_alerts_to_file(tmp_path):
    out = tmp_path / "rules.yaml"
    result = runner.invoke(app, ["gen-alerts", EXAMPLE, "--out", str(out)])
    assert result.exit_code == 0
    assert out.exists()
    assert yaml.safe_load(out.read_text())["groups"]


def test_status_json(monkeypatch):
    monkeypatch.setattr(cli_module, "_make_source", lambda url, kind: FakeSource(HEALTHY))
    result = runner.invoke(app, ["status", FAKE_SPEC, "--source", "x", "--output", "json"])
    assert result.exit_code == 0
    import json

    data = json.loads(result.output)
    assert data["slo"] == "checkout-availability"
    assert data["error_budget"]["remaining_pct"] == 1.0


def test_status_text(monkeypatch):
    monkeypatch.setattr(cli_module, "_make_source", lambda url, kind: FakeSource(HEALTHY))
    result = runner.invoke(app, ["status", FAKE_SPEC, "--source", "x"])
    assert result.exit_code == 0
    assert "budget remaining" in result.output


def test_gate_pass(monkeypatch):
    monkeypatch.setattr(cli_module, "_make_source", lambda url, kind: FakeSource(HEALTHY))
    result = runner.invoke(app, ["gate", FAKE_SPEC, "--source", "x"])
    assert result.exit_code == 0


def test_gate_block_on_firing(monkeypatch):
    monkeypatch.setattr(cli_module, "_make_source", lambda url, kind: FakeSource(BURNING))
    result = runner.invoke(app, ["gate", FAKE_SPEC, "--source", "x", "--block-on-firing"])
    assert result.exit_code == 1
