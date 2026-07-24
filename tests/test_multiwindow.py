"""Multi-window multi-burn-rate policy tests — an explicit truth table.

Default conditions (SRE-workbook, 30d window):
    fast_burn   : 1h  AND 5m   > 14.4  -> page
    slow_burn   : 6h  AND 30m  > 6     -> page
    slower_burn : 24h AND 2h   > 3     -> ticket

A condition fires iff BOTH its windows exceed the threshold. The policy fires
if ANY condition fires.
"""

from __future__ import annotations

import pytest

from slo_kit.alerts.multiwindow import MultiWindowPolicy, default_conditions
from slo_kit.models import BurnCondition, Window

WINDOWS = ("1h", "5m", "6h", "30m", "24h", "2h")


def rates(**overrides: float) -> dict[str, float]:
    """All windows default to 0 burn rate; override the interesting ones."""
    base = dict.fromkeys(WINDOWS, 0.0)
    base.update(overrides)
    return base


# (label, burn_rates, expect_firing, expect_severity)
TRUTH_TABLE = [
    # 1. All quiet -> nothing fires.
    ("all_quiet", rates(), False, None),
    # 2. Fast burn: both 1h and 5m well over 14.4 -> page.
    ("fast_burn_both", rates(**{"1h": 20, "5m": 20}), True, "page"),
    # 3. Long window over but short window recovered -> no page (reset gate).
    ("fast_long_only", rates(**{"1h": 20, "5m": 1}), False, None),
    # 4. Short spike but long window not yet over -> no page (noise gate).
    ("fast_short_only", rates(**{"1h": 2, "5m": 50}), False, None),
    # 5. Exactly at threshold is NOT over (strict >) -> no fire.
    ("fast_exactly_at_threshold", rates(**{"1h": 14.4, "5m": 14.4}), False, None),
    # 6. Just over threshold on both -> page.
    ("fast_just_over", rates(**{"1h": 14.5, "5m": 14.5}), True, "page"),
    # 7. Slow burn (6h & 30m > 6) but below fast threshold -> page via slow_burn.
    ("slow_burn_both", rates(**{"6h": 8, "30m": 8}), True, "page"),
    # 8. Slow long window over, short recovered -> no fire.
    ("slow_long_only", rates(**{"6h": 8, "30m": 1}), False, None),
    # 9. Slower burn (24h & 2h > 3) only -> ticket, not page.
    ("slower_burn_both", rates(**{"24h": 4, "2h": 4}), True, "ticket"),
    # 10. Slower windows over 3 but under 6 -> ticket only.
    ("slower_between_3_and_6", rates(**{"24h": 5, "2h": 5}), True, "ticket"),
    # 11. Both fast and slower firing -> highest severity is page.
    ("fast_and_slower", rates(**{"1h": 20, "5m": 20, "24h": 4, "2h": 4}), True, "page"),
    # 12. Below all thresholds everywhere -> nothing.
    ("all_below", rates(**{"1h": 2, "5m": 2, "6h": 2, "30m": 2, "24h": 2, "2h": 2}), False, None),
]


@pytest.fixture
def policy() -> MultiWindowPolicy:
    return MultiWindowPolicy(default_conditions())


@pytest.mark.parametrize(
    "label,burn_rates,expect_firing,expect_severity",
    TRUTH_TABLE,
    ids=[c[0] for c in TRUTH_TABLE],
)
def test_truth_table(policy, label, burn_rates, expect_firing, expect_severity):
    result = policy.evaluate(burn_rates)
    assert result.firing is expect_firing, label
    assert result.severity == expect_severity, label


def test_is_firing_shortcut(policy):
    assert policy.is_firing(rates(**{"1h": 20, "5m": 20})) is True
    assert policy.is_firing(rates()) is False


def test_firing_conditions_named(policy):
    result = policy.evaluate(rates(**{"6h": 8, "30m": 8}))
    firing = [c.name for c in result.firing_conditions]
    assert firing == ["slow_burn"]


def test_required_windows(policy):
    assert set(policy.required_windows) == set(WINDOWS)


def test_missing_window_raises(policy):
    with pytest.raises(KeyError):
        policy.evaluate({"1h": 20})  # missing others


def test_default_conditions_shape():
    conds = default_conditions()
    assert [c.name for c in conds] == ["fast_burn", "slow_burn", "slower_burn"]
    assert conds[0].threshold == 14.4
    assert conds[0].severity == "page"
    assert conds[2].severity == "ticket"


def test_empty_policy_rejected():
    with pytest.raises(ValueError):
        MultiWindowPolicy([])


def test_short_window_must_be_shorter():
    with pytest.raises(ValueError):
        BurnCondition(
            name="bad",
            long_window=Window(duration="5m"),
            short_window=Window(duration="1h"),
            threshold=10,
        )


def test_custom_conditions():
    custom = [
        BurnCondition(
            name="only",
            long_window=Window(duration="2h"),
            short_window=Window(duration="10m"),
            threshold=10,
            severity="page",
        )
    ]
    policy = MultiWindowPolicy(custom)
    assert policy.is_firing({"2h": 11, "10m": 11})
    assert not policy.is_firing({"2h": 11, "10m": 9})
