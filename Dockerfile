# ──────────────────────────
# Build stage
# ──────────────────────────
FROM python:3.13-alpine AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    VIRTUAL_ENV=/opt/venv

RUN apk add --no-cache gcc musl-dev libpq-dev zlib-dev jpeg-dev && \
    uv venv /opt/venv

# Install dependencies first — separate layer so code changes don't bust this cache
COPY pyproject.toml README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip compile pyproject.toml -o /tmp/requirements.txt && \
    uv pip install -r /tmp/requirements.txt

# Install the project itself (non-editable so bot/ lands in site-packages)
COPY bot/ bot/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --no-deps "mtg-proxy-bot @ ."

# ──────────────────────────
# Runtime stage
# ──────────────────────────
FROM python:3.13-alpine

RUN addgroup -g 1001 app && \
    adduser -u 1001 -G app -H -s /sbin/nologin -D app

WORKDIR /app

ENV PATH="/opt/venv/bin:$PATH" \
    VIRTUAL_ENV=/opt/venv \
    PYTHONUNBUFFERED=1

COPY --from=builder --chown=app:app /opt/venv /opt/venv
COPY --chown=app:app alembic/ alembic/
COPY --chown=app:app alembic.ini ./
COPY --chown=app:app entrypoint.sh ./

RUN chmod +x entrypoint.sh

EXPOSE 8080

USER app

ENTRYPOINT ["./entrypoint.sh"]
