"""Spec loading and validation tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from slo_kit.models import SLO
from slo_kit.spec import SpecError, dump_spec, load_spec, load_spec_dict, load_specs

EXAMPLE = Path(__file__).parents[1] / "examples" / "checkout_slo.yaml"


def test_load_example_spec():
    slo = load_spec(EXAMPLE)
    assert isinstance(slo, SLO)
    assert slo.name == "checkout-availability"
    assert slo.objective == 0.999
    assert slo.window.duration == "30d"
    assert slo.window.seconds == 30 * 86400
    assert slo.error_budget == pytest.approx(0.001)
    assert slo.alerting is not None
    assert len(slo.alerting.conditions) == 3


def test_load_spec_dict_minimal():
    slo = load_spec_dict(
        {
            "name": "svc",
            "objective": 0.99,
            "window": "7d",
            "sli": {"good_query": "g[{window}]", "total_query": "t[{window}]"},
        }
    )
    assert slo.objective == 0.99
    assert slo.alerting is None


def test_window_as_mapping():
    slo = load_spec_dict(
        {
            "name": "svc",
            "objective": 0.99,
            "window": {"duration": "7d"},
            "sli": {"good_query": "g", "total_query": "t"},
        }
    )
    assert slo.window.duration == "7d"


@pytest.mark.parametrize(
    "mutation,message",
    [
        ({"apiVersion": "slo-kit/v2"}, "unsupported apiVersion"),
        ({"sli": None}, "missing an 'sli'"),
        ({"objective": None, "_drop": "objective"}, "missing 'objective'"),
        ({"window": None, "_drop": "window"}, "missing 'window'"),
    ],
)
def test_invalid_specs_raise(mutation, message):
    base = {
        "name": "svc",
        "objective": 0.99,
        "window": "7d",
        "sli": {"good_query": "g", "total_query": "t"},
    }
    base.update({k: v for k, v in mutation.items() if not k.startswith("_")})
    if "_drop" in mutation:
        base.pop(mutation["_drop"])
    with pytest.raises(SpecError) as exc:
        load_spec_dict(base)
    assert message in str(exc.value)


def test_invalid_objective_range():
    with pytest.raises(SpecError):
        load_spec_dict(
            {
                "name": "svc",
                "objective": 1.5,
                "window": "7d",
                "sli": {"good_query": "g", "total_query": "t"},
            }
        )


def test_bad_duration_rejected():
    with pytest.raises(SpecError):
        load_spec_dict(
            {
                "name": "svc",
                "objective": 0.99,
                "window": "banana",
                "sli": {"good_query": "g", "total_query": "t"},
            }
        )


def test_missing_file():
    with pytest.raises(SpecError):
        load_spec("/nonexistent/spec.yaml")


def test_empty_file(tmp_path):
    p = tmp_path / "empty.yaml"
    p.write_text("")
    with pytest.raises(SpecError):
        load_spec(p)


def test_multi_doc(tmp_path):
    doc = tmp_path / "multi.yaml"
    doc.write_text(
        "name: a\nobjective: 0.99\nwindow: 7d\n"
        "sli: {good_query: g, total_query: t}\n"
        "---\n"
        "name: b\nobjective: 0.999\nwindow: 30d\n"
        "sli: {good_query: g, total_query: t}\n"
    )
    specs = load_specs(doc)
    assert [s.name for s in specs] == ["a", "b"]


def test_round_trip_dump_and_load():
    slo = load_spec(EXAMPLE)
    dumped = dump_spec(slo)
    reloaded = load_spec_dict(__import__("yaml").safe_load(dumped))
    assert reloaded.name == slo.name
    assert reloaded.objective == slo.objective
    assert len(reloaded.alerting.conditions) == len(slo.alerting.conditions)
