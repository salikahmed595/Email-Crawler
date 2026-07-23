# Lead Intelligence & Email Discovery Engine

> Enterprise-grade, deterministic email discovery and business data enrichment platform.  
> Zero AI dependency. Zero external API costs. Pure engineering.

---

## Architecture

```
CSV Input → Import Queue → Crawler (HTTP → Playwright → PDF → OCR)
         → Parser → Email Extractor (11 strategies)
         → Email Validator (10 stages) → Confidence Engine
         → Deduplication → PostgreSQL → JSON Export
```

## Quick Start (No Docker — Direct Mode)

```bash
# 1. Install dependencies
pip install uv
uv pip install -e .

# 2. Install Playwright browsers
playwright install chromium

# 3. Copy env
cp .env.example .env

# 4. Start PostgreSQL + Redis (or use Docker)
docker-compose up -d postgres redis

# 5. Run migrations
alembic upgrade head

# 6. Crawl a CSV directly (no queue needed)
python scripts/run_crawler.py --input sample_data/small.csv --no-queue

# 7. Export results
python scripts/run_export.py --output output/results.json
```

## Queue Mode (Scalable)

```bash
# Terminal 1: Start API
python scripts/run_api.py

# Terminal 2: Import CSV
curl -X POST http://localhost:8000/jobs/import \
  -F "file=@sample_data/small.csv"

# Terminal 3: Start workers
python scripts/run_worker.py --workers 4

# Terminal 4: Export when done
python scripts/run_export.py
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/jobs/import` | Upload CSV, queue crawl jobs |
| `GET` | `/jobs/queue-status` | Redis queue depths |
| `GET` | `/results/companies` | List all companies |
| `GET` | `/results/companies/{id}` | Single company + emails |
| `POST` | `/results/export` | Trigger JSON export |
| `GET` | `/results/stats` | Crawl statistics |
| `GET` | `/health` | Liveness |
| `GET` | `/health/ready` | DB + Redis readiness |

## Email Discovery Strategies

1. `mailto:` links (confidence ~90)
2. Visible HTML regex (confidence ~70)
3. Footer text (confidence ~75)
4. Header text (confidence ~65)
5. Schema.org / JSON-LD (confidence ~85)
6. JavaScript source (confidence ~60)
7. HTML comments (confidence ~55)
8. Base64 decoded strings (confidence ~65)
9. Unicode obfuscated emails (confidence ~60)
10. Cloudflare email protection decode (confidence ~80)
11. PDF text / OCR output (confidence ~50)

## Email Validation Stages

1. Normalization
2. Syntax (RFC 5322)
3. Domain format
4. DNS resolution
5. MX record check
6. SMTP handshake (opt-in: `SMTP_VALIDATION_ENABLED=true`)
7. Disposable domain detection
8. Role-based prefix detection
9. Deduplication (SHA-256)
10. Confidence scoring (0-100, deterministic)

## Configuration

All settings via `.env`. See `.env.example` for all options.

Key settings:
```env
MAX_WORKERS=4               # Concurrent crawl workers
PLAYWRIGHT_ENABLED=true     # JS rendering fallback
PDF_ENABLED=false           # PDF extraction (off by default)
OCR_ENABLED=false           # OCR (off by default)
SMTP_VALIDATION_ENABLED=false  # SMTP check (opt-in)
MIN_EMAIL_CONFIDENCE=30     # Drop emails below this threshold
```

## Running Tests

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

## Docker

```bash
# Full stack
docker-compose up

# With object storage
docker-compose --profile storage up
```

## Output Format (JSON)

```json
[
  {
    "id": "uuid",
    "name": "Company Name",
    "domain": "example.com",
    "emails": [
      {
        "address": "contact@example.com",
        "confidence": 85,
        "source": "https://example.com/contact",
        "method": "mailto",
        "page": "https://example.com/contact",
        "validation_status": "valid",
        "mx_valid": true,
        "is_disposable": false,
        "is_role_based": true,
        "discovered_at": "2024-01-01T12:00:00Z"
      }
    ]
  }
]
```
