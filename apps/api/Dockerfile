# syntax=docker/dockerfile:1

FROM python:3.12-slim-bookworm AS builder
# uv binary copied from the official distroless image, per Astral's own
# Docker integration guide (docs.astral.sh/uv/guides/integration/docker/).
COPY --from=ghcr.io/astral-sh/uv:0.9.11 /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
WORKDIR /app

# Layer 1: dependencies only — cacheable, does not invalidate on source changes.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# Layer 2: installs the project itself (editable, pointing at /app/src).
COPY README.md ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

FROM python:3.12-slim-bookworm AS runner
ENV PATH="/app/.venv/bin:$PATH"

# gosu drops privilege in entrypoint.sh (see the root docs/architecture.md).
# Version pinned to bookworm's current candidate for build reproducibility;
# bump after checking `apt-cache policy gosu` if it updates.
RUN apt-get update \
    && apt-get install -y --no-install-recommends gosu=1.14-1+b10 \
    && rm -rf /var/lib/apt/lists/*

# Placeholder "app" user (UID/GID 1000 baked at build time only as the
# default — entrypoint.sh adjusts it at runtime; see the root
# docs/architecture.md).
RUN groupadd --gid 1000 app \
    && useradd --uid 1000 --gid app --no-create-home --shell /usr/sbin/nologin app

WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src ./src
# alembic.ini + the migrations (which live inside src/caramello_api/migrations)
# let the entrypoint apply the schema automatically on every boot. Both are
# required in the image: without them `alembic upgrade head` cannot run at all.
COPY alembic.ini ./
# Operator tooling that has no HTTP equivalent by design: allowlist
# administration (`scripts/seed_allowed_email.py`,
# `scripts/remove_allowed_email.py`) is run with `docker exec` against the
# running container — see the "User authorization" section of docs/release.md.
COPY scripts ./scripts
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Documentation only — it publishes nothing by itself. The real mapping lives
# in the `ports:` block of the compose file.
EXPOSE 8000

# No fixed USER on purpose — the process starts as root inside ENTRYPOINT and
# only drops privilege inside entrypoint.sh, right before running the
# migrations and exec'ing the real application process.
ENTRYPOINT ["/entrypoint.sh"]
# `python -m caramello_api` reads host/port/log level from Settings
# (CARAMELLO_API_HOST/CARAMELLO_API_PORT/CARAMELLO_API_LOG_LEVEL) instead of
# hardcoded CLI flags — if you change the bind port via env var, also update
# the `ports:` mapping in your compose file, since EXPOSE 8000 above is
# documentation only.
CMD ["python", "-m", "caramello_api"]
