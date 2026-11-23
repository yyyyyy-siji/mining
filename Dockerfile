# ---- Build Stage ----
FROM python:3.12-slim AS builder

WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir ".[postgres]"

# ---- Runtime Stage ----
FROM python:3.12-slim AS runtime

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application source
COPY signal_miner/ signal_miner/
COPY frontend/ frontend/
COPY alembic/ alembic/
COPY alembic.ini .

# Environment defaults
ENV ENVIRONMENT=production
ENV DEBUG=false
ENV API_HOST=0.0.0.0
ENV API_PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import httpx; httpx.get('http://localhost:8000/health').raise_for_status()"

CMD ["python", "-m", "signal_miner.main", "--no-reload"]
