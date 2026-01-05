# Quart Backend Dockerfile
# Multi-stage build for production with Hypercorn ASGI server

FROM python:3.13-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for layer caching
COPY services/flask-backend/requirements.txt .

# Copy shared libraries for editable install
COPY shared/py_libs /shared/py_libs

# Create virtual environment and install dependencies
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Production stage
FROM python:3.13-slim AS runtime

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash appuser

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy shared libraries (needed at runtime for editable install)
COPY --from=builder /shared/py_libs /shared/py_libs

# Copy application code
COPY --chown=appuser:appuser services/flask-backend/ .

# Switch to non-root user
USER appuser

# Environment variables
ENV ASGI_HOST=0.0.0.0
ENV ASGI_PORT=5000
ENV ASGI_WORKERS=4
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app:/shared/py_libs

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:5000/healthz || exit 1

# Run with Hypercorn ASGI server in production
CMD ["hypercorn", \
     "--bind", "0.0.0.0:5000", \
     "--workers", "4", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "--graceful-timeout", "10", \
     "app:create_app()"]
