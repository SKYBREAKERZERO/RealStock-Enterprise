# syntax=docker/dockerfile:1

ARG PYTHON_IMAGE=python:3.12-slim-bookworm


# ============================================================
# Builder
# ============================================================
FROM ${PYTHON_IMAGE} AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

# Copy dependency metadata first so Docker can reuse this layer
# when application source changes.
COPY pyproject.toml ./

# RealStock Python packages.
COPY libs ./libs
COPY services ./services

# Build the application and runtime dependencies into wheels.
RUN python -m pip wheel \
    --wheel-dir=/wheels \
    .


# ============================================================
# Runtime
# ============================================================
FROM ${PYTHON_IMAGE} AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Fixed numeric UID/GID keeps the container non-root and
# predictable across Docker Compose and ECS.
RUN addgroup \
        --system \
        --gid 10001 \
        realstock \
    && adduser \
        --system \
        --uid 10001 \
        --ingroup realstock \
        --home /home/realstock \
        realstock

COPY --from=builder /wheels /wheels

# Runtime installation is network-independent.
RUN python -m pip install \
        --no-index \
        --find-links=/wheels \
        realstock-enterprise \
    && rm -rf /wheels

USER 10001:10001

# Docker Compose and ECS use SIGTERM for graceful shutdown.
STOPSIGNAL SIGTERM

CMD ["python", "-m", "services.outbox_dispatcher.main"]