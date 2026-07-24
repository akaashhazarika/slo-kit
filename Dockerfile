# syntax=docker/dockerfile:1

# ---- build stage ------------------------------------------------------------
FROM python:3.12-slim AS build

WORKDIR /app
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# Build a wheel so the runtime image carries only the installed package.
COPY pyproject.toml README.md CHANGELOG.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir build && python -m build --wheel --outdir /dist

# ---- runtime stage ----------------------------------------------------------
FROM python:3.12-slim AS runtime

LABEL org.opencontainers.image.title="slo-kit" \
      org.opencontainers.image.description="Define SLOs as code and get correct multi-window burn-rate alerts." \
      org.opencontainers.image.licenses="Apache-2.0" \
      org.opencontainers.image.source="https://github.com/slo-kit/slo-kit"

WORKDIR /work
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1

# Run as an unprivileged user.
RUN useradd --create-home --uid 10001 slokit

COPY --from=build /dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm -rf /tmp/*.whl

USER slokit

ENTRYPOINT ["slo-kit"]
CMD ["--help"]
