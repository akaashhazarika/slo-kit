# Contributing to slo-kit

Thanks for your interest in improving slo-kit! Correctness of the SLO math is
the whole point of this project, so contributions to the core modules
(`budget/burn_rate.py`, `budget/error_budget.py`, `alerts/multiwindow.py`,
`alerts/prometheus_rules.py`) must come with tests that pin behaviour against
hand-computed expected values.

## Development setup

```bash
git clone https://github.com/slo-kit/slo-kit
cd slo-kit
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install
```

## Quality gates (run before pushing)

```bash
ruff check .            # lint
ruff format .           # format
mypy src/slo_kit        # strict types
pytest --cov=slo_kit --cov-report=term-missing
```

CI runs these on Python 3.11 and 3.12, and enforces **≥ 90% coverage on the
core budget/alert modules**.

## Conventions

- **Conventional Commits** for messages (`feat:`, `fix:`, `docs:`, `test:`,
  `refactor:`, `chore:`). This drives the CHANGELOG.
- **SemVer** for releases.
- New behaviour needs tests; core-math changes need tests against synthetic
  series with known-correct outputs.
- Public API changes must update `docs/` and `CHANGELOG.md`.

## Releasing

1. Update `CHANGELOG.md` and bump `version` in `pyproject.toml` and
   `src/slo_kit/__init__.py`.
2. Tag `vX.Y.Z` and push the tag — the release workflow publishes to PyPI
   (trusted publishing) and pushes the Docker image.

## Code of Conduct

Be kind and constructive. We follow the
[Contributor Covenant](https://www.contributor-covenant.org/).
