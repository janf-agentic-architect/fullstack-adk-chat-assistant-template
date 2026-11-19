# Multi-stage build for WhatsApp Channel Webhook
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# Install dependencies
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# Copy source and sync project
COPY . /app
RUN uv sync --frozen --no-dev

# Production runtime stage
FROM python:3.12-slim-bookworm

WORKDIR /app

# Copy virtualenv and application from builder
COPY --from=builder /app /app
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

EXPOSE 8080

# Run uvicorn respecting Cloud Run $PORT
CMD ["sh", "-c", "exec uvicorn whatsapp.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
