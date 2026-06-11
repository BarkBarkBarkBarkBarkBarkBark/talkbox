# ─── Builder ─────────────────────────────────────────────────────────────────
# Carries the full toolchain (build-base, cargo+rust, postgresql-dev, …) so
# native extensions without musl wheels can compile. Nothing from this stage
# reaches the final image except the resolved virtualenv.
FROM python:3.13-alpine AS builder

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

RUN apk add --no-cache \
      build-base \
      cargo \
      curl \
      libffi-dev \
      openssl-dev \
      postgresql-dev \
      python3-dev \
      rust

RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
    && mv /root/.local/bin/uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project


# ─── Runtime ─────────────────────────────────────────────────────────────────
# Only Python, libpq (psycopg2 runtime), and curl (healthcheck). No toolchain,
# no uv, no rust — the venv baked by the builder is self-contained.
FROM python:3.13-alpine AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

RUN apk add --no-cache curl libpq

COPY --from=builder /app/.venv /app/.venv

COPY src/ ./src/
COPY alembic/ ./alembic/
COPY alembic.ini main.py ./
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh


FROM base AS api
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --retries=3 --start-period=20s \
    CMD curl -fsS http://localhost:8000/api/health || exit 1
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["python", "main.py", "api"]
