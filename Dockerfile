FROM python:3.12-slim

WORKDIR /app

# System deps needed by Playwright's Chromium at runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY app/ ./app/

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e . && \
    playwright install --with-deps chromium

COPY dashboard.py ./
COPY .streamlit/ ./.streamlit/
COPY sample_data/ ./sample_data/

RUN mkdir -p data output logs

EXPOSE 8501

CMD ["sh", "-c", "streamlit run dashboard.py --server.port ${PORT:-8501} --server.address 0.0.0.0 --server.headless true"]
