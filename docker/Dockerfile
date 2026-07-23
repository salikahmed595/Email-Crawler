FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml ./
RUN pip install --no-cache-dir uv && \
    uv pip install --system --no-cache -e .

# Install Playwright browsers
RUN playwright install chromium && playwright install-deps chromium

# Copy application
COPY app/ ./app/
COPY scripts/ ./scripts/
COPY migrations/ ./migrations/
COPY alembic.ini ./

# Create output directories
RUN mkdir -p output logs temp

EXPOSE 8000

CMD ["python", "scripts/run_api.py"]
