#!/usr/bin/env python
"""Fail CI if coverage on the core budget/alert modules drops below 90%.

The core math is the product, so we hold it to a higher bar than the rest of
the tree. Reads ``coverage.xml`` produced by ``pytest --cov-report=xml``.
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET

CORE_MODULES = (
    "slo_kit/budget/burn_rate.py",
    "slo_kit/budget/error_budget.py",
    "slo_kit/alerts/multiwindow.py",
    "slo_kit/alerts/prometheus_rules.py",
)
THRESHOLD = 0.90


def main() -> int:
    tree = ET.parse("coverage.xml")
    worst = 1.0
    for cls in tree.iter("class"):
        filename = cls.get("filename", "")
        if filename.endswith(CORE_MODULES):
            rate = float(cls.get("line-rate", "0"))
            print(f"{filename}: {rate:.1%}")
            worst = min(worst, rate)
    if worst < THRESHOLD:
        print(f"FAIL: core coverage {worst:.1%} < {THRESHOLD:.0%}")
        return 1
    print(f"OK: core coverage >= {THRESHOLD:.0%}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
