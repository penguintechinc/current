FROM python:3.12-slim

# Metadata labels
LABEL org.opencontainers.image.title="ShortURL"
LABEL org.opencontainers.image.description="Enterprise URL shortener with analytics and multi-arch support"
LABEL org.opencontainers.image.version="1.0.0"
LABEL org.opencontainers.image.authors="ShortURL Team"
LABEL org.opencontainers.image.source="https://github.com/your-org/shorturl"
LABEL org.opencontainers.image.licenses="MIT"

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libssl-dev \
    libffi-dev \
    cron \
    certbot \
    openssl \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories and set permissions
RUN mkdir -p /var/data/current /var/log/shorturl /etc/letsencrypt \
    && chmod +x /app/entrypoint.sh

# Environment variables
ENV DB_TYPE=sqlite
ENV DB_CONNECTION=/var/data/current/db.sqlite
ENV DOMAIN=localhost
ENV ADMIN_EMAIL=admin@localhost
ENV SECRET_KEY=change-me-in-production
ENV REDIS_URL=redis://redis:6379/0
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Expose ports
EXPOSE 80 443 9443

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:9443/healthz || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]