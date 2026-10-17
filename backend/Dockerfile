# syntax=docker/dockerfile:1
# Production-oriented Dockerfile for REBOOTX Backend Services
# Targets: api (default), worker, dispatcher

FROM python:3.12-slim AS base

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

# Install security updates and curl for health check probes
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Create dedicated non-root application user and group
RUN groupadd -g 1001 rebootx && \
    useradd -u 1001 -g rebootx -s /bin/bash -m rebootx

# Install Python dependencies first for caching
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source code, Alembic migrations, and configuration
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini .
COPY scripts/ ./scripts/

# Ensure non-root ownership
RUN chown -R rebootx:rebootx /app

# Switch to non-root user
USER rebootx

# ==========================================
# Target: API (FastAPI Backend)
# ==========================================
FROM base AS api

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ==========================================
# Target: Worker (Temporal Activity Worker)
# ==========================================
FROM base AS worker

CMD ["python", "-m", "app.temporal.worker"]

# ==========================================
# Target: Dispatcher (Outbox Dispatcher)
# ==========================================
FROM base AS dispatcher

CMD ["python", "-m", "app.temporal.dispatcher"]

