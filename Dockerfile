ARG APP_VERSION=0.0.0

# ─── Stage 1: builder ────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app

RUN pip install uv

COPY pyproject.toml uv.lock ./
COPY src/ ./src/
COPY README.md ./

RUN uv venv /app/.venv \
    && uv pip install --python /app/.venv/bin/python --no-cache .

# ─── Stage 2: runtime ─────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

ARG APP_VERSION
ENV APP_VERSION=${APP_VERSION}

WORKDIR /app

RUN addgroup --system app && adduser --system --group app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src ./src

ENV PATH="/app/.venv/bin:$PATH"

USER app

EXPOSE 8000

CMD ["uvicorn", "caramello.main:app", "--host", "0.0.0.0", "--port", "8000"]
