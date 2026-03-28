FROM python:3.13-slim

WORKDIR /app

# Install uv
RUN pip install --no-cache-dir uv

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock ./

# Install production deps only (no dev group)
RUN uv sync --frozen --no-dev

# Copy source
COPY src/ ./src/

# Vendor ID is set per-service in docker-compose.yml
ENV VENDOR_ID=helsinki-maker-store

EXPOSE 8000

CMD ["uv", "run", "ashre-vendor"]
