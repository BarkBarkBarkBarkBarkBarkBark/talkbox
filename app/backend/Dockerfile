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

COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project


# ─── whisper.cpp ─────────────────────────────────────────────────────────────
# Build once for the image architecture (arm64 on Pi, amd64 elsewhere). The
# model remains outside the image so normal application rebuilds stay small.
FROM alpine:3.22 AS whisper-builder

ARG WHISPER_CPP_VERSION=v1.7.6

RUN apk add --no-cache build-base cmake git
RUN git clone --branch "${WHISPER_CPP_VERSION}" --depth 1 \
            https://github.com/ggerganov/whisper.cpp.git /src \
        && cmake -S /src -B /src/build \
            -DCMAKE_BUILD_TYPE=Release \
            -DBUILD_SHARED_LIBS=OFF \
            -DGGML_NATIVE=OFF \
            -DWHISPER_BUILD_TESTS=OFF \
            -DWHISPER_BUILD_SERVER=OFF \
        && cmake --build /src/build --config Release --target whisper-cli --parallel


# ─── Runtime ─────────────────────────────────────────────────────────────────
# Only Python, libpq (psycopg2 runtime), and curl (healthcheck). No toolchain,
# no uv, no rust — the venv baked by the builder is self-contained.
FROM python:3.13-alpine AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

RUN apk add --no-cache curl ffmpeg libgomp libpq libstdc++ iptables

# ─── Tailscale (userspace) ───────────────────────────────────────────────────
# Static binaries copied from the official image so the Fly machine can join the
# tailnet and (optionally) expose the API over Tailscale Funnel — giving Twilio
# a stable https://<hostname>.<tailnet>.ts.net webhook. Bring-up is handled by
# docker-entrypoint.sh and is a no-op unless TS_AUTHKEY is set.
COPY --from=tailscale/tailscale:stable /usr/local/bin/tailscaled /usr/local/bin/tailscaled
COPY --from=tailscale/tailscale:stable /usr/local/bin/tailscale  /usr/local/bin/tailscale
RUN mkdir -p /var/run/tailscale /var/lib/tailscale

COPY --from=builder /app/.venv /app/.venv
COPY --from=whisper-builder /src/build/bin/whisper-cli /usr/local/bin/whisper-cli

COPY backend/src/ ./src/
COPY backend/alembic/ ./alembic/
COPY backend/alembic.ini backend/main.py ./
COPY backend/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
COPY database/sacramento.db /app/database/sacramento.db
RUN chmod +x /usr/local/bin/docker-entrypoint.sh


FROM base AS api
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --retries=3 --start-period=20s \
    CMD curl -fsS http://localhost:8000/healthz || exit 1
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["python", "main.py", "api"]
