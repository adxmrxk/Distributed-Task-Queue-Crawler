# Distributed Task Queue Web Crawler

A production-grade distributed web crawler built with Python, Celery, Playwright, PostgreSQL, and Redis. Features broken link detection, full browser automation with JavaScript rendering, dead letter queue for failed tasks, and exponential backoff retry logic.

## Features

- **Full Browser Automation**: Uses Playwright to handle JavaScript-heavy sites and SPAs
- **Distributed Architecture**: Celery workers with Redis broker for horizontal scalability
- **Broken Link Detection**: Efficiently finds and reports broken links across websites
- **Production-Ready Error Handling**:
  - Exponential backoff with jitter
  - Dead Letter Queue (DLQ) for permanently failed tasks
  - Comprehensive retry logic
- **Rate Limiting**: Per-domain token bucket algorithm to respect target sites
- **Politeness**: Respects robots.txt and crawl-delay directives
- **RESTful API**: FastAPI endpoints for job submission and status tracking
- **Monitoring**: Flower dashboard for real-time Celery task monitoring
- **Docker Deployment**: Complete containerized setup with docker-compose

## Architecture

**Components:**
- **API Layer** (FastAPI): Job submission, status queries, result retrieval
- **Task Queue** (Celery + Redis): Distributed task processing with reliability guarantees
- **Crawler Engine** (Playwright): Browser automation for JavaScript rendering
- **Database** (PostgreSQL): Persistent storage for jobs, results, and task metadata
- **Cache/Broker** (Redis): Message queue and distributed rate limiting

**Crawling Strategy:**
- Breadth-First Search (BFS) for efficient parallel processing
- Configurable depth and page limits
- URL deduplication with SHA256 hashing
- Per-domain rate limiting with token bucket algorithm

## Quick Start

### Prerequisites

- Python 3.11+
- Docker and Docker Compose
- Poetry (Python dependency management)

### Local Development

1. Clone the repository:
```bash
git clone <repository-url>
cd distributed-crawler
```

2. Copy environment variables:
```bash
cp .env.example .env
```

3. Install dependencies:
```bash
poetry install
```

4. Start infrastructure (PostgreSQL, Redis):
```bash
docker-compose up -d postgres redis
```

5. Run database migrations:
```bash
poetry run alembic upgrade head
```

6. Start the API:
```bash
poetry run uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

7. Start Celery workers:
```bash
poetry run celery -A src.worker.celery_app worker --loglevel=info --concurrency=4
```

8. (Optional) Start Flower for monitoring:
```bash
poetry run celery -A src.worker.celery_app flower --port=5555
```

### Docker Deployment

1. Build and start all services:
```bash
docker-compose up --build
```

2. Access the services:
   - API: http://localhost:8000
   - API Docs: http://localhost:8000/docs
   - Flower Dashboard: http://localhost:5555

## API Usage

### Submit a Crawl Job

```bash
curl -X POST http://localhost:8000/api/v1/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com",
    "max_depth": 3,
    "max_pages": 100,
    "respect_robots_txt": true
  }'
```

Response:
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "url": "https://example.com",
  "status": "IN_PROGRESS",
  "celery_task_id": "abc123...",
  "created_at": "2026-03-14T10:30:00Z"
}
```

### Check Job Status

```bash
curl http://localhost:8000/api/v1/jobs/{job_id}
```

Response:
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "url": "https://example.com",
  "status": "COMPLETED",
  "total_pages_crawled": 42,
  "total_links_found": 315,
  "total_broken_links": 5,
  "started_at": "2026-03-14T10:30:01Z",
  "completed_at": "2026-03-14T10:32:15Z"
}
```

### Get Broken Links

```bash
curl http://localhost:8000/api/v1/jobs/{job_id}/broken-links?skip=0&limit=100
```

Response:
```json
{
  "total": 5,
  "broken_links": [
    {
      "source_url": "https://example.com/page1",
      "broken_url": "https://example.com/404",
      "anchor_text": "Click here",
      "status_code": 404,
      "error_type": "HTTP_ERROR",
      "depth": 1
    }
  ]
}
```

### Cancel a Job

```bash
curl -X DELETE http://localhost:8000/api/v1/jobs/{job_id}
```

## Project Structure

```
distributed-crawler/
├── src/
│   ├── api/              # FastAPI application
│   ├── worker/           # Celery workers and tasks
│   ├── crawler/          # Playwright crawler and validators
│   ├── db/               # Database models and repositories
│   ├── core/             # Configuration, logging, exceptions
│   └── utils/            # Utility functions
├── docker/               # Dockerfiles
├── scripts/              # Utility scripts
├── tests/                # Test suite
├── docker-compose.yml    # Service orchestration
└── pyproject.toml        # Python dependencies
```

## Configuration

All configuration is managed through environment variables. See `.env.example` for available options.

Key configurations:
- `DATABASE_URL`: PostgreSQL connection string
- `CELERY_BROKER_URL`: Redis broker URL
- `CRAWLER_MAX_DEPTH`: Maximum crawl depth (default: 3)
- `CRAWLER_RATE_LIMIT_PER_DOMAIN`: Requests per second per domain (default: 1.0)
- `RETRY_MAX_ATTEMPTS`: Maximum retry attempts (default: 5)

## Monitoring

### Flower Dashboard

Access Flower at http://localhost:5555 to monitor:
- Active tasks and workers
- Task success/failure rates
- Worker status and health
- Task arguments and results
- Queue depth and throughput

### Health Checks

- `GET /health`: Basic liveness check
- `GET /ready`: Readiness check (database, redis, workers)

### Logging

Structured JSON logging with the following fields:
- `timestamp`: ISO 8601 timestamp
- `level`: Log level (INFO, WARNING, ERROR)
- `message`: Log message
- `job_id`, `task_id`, `url`, `depth`: Contextual metadata

## Testing

Run the full test suite:
```bash
poetry run pytest
```

Run with coverage:
```bash
poetry run pytest --cov=src --cov-report=html
```

Run specific test types:
```bash
poetry run pytest tests/unit/          # Unit tests
poetry run pytest tests/integration/   # Integration tests
poetry run pytest tests/e2e/           # End-to-end tests
```

## Production Deployment

### Scaling Workers

Adjust worker replicas in `docker-compose.yml`:
```yaml
worker:
  deploy:
    replicas: 10  # Scale to 10 workers
```

Or scale dynamically:
```bash
docker-compose up --scale worker=10
```

### Performance Tuning

- **Worker Concurrency**: Adjust `--concurrency` flag (default: 4)
- **Rate Limiting**: Tune `CRAWLER_RATE_LIMIT_PER_DOMAIN` per target site requirements
- **Database Connection Pool**: Adjust `DB_POOL_SIZE` and `DB_MAX_OVERFLOW`
- **Redis Max Connections**: Tune `REDIS_MAX_CONNECTIONS`

### Security Considerations

1. **Input Validation**: All URLs validated to prevent SSRF attacks
2. **Rate Limiting**: API rate limiting to prevent abuse
3. **Authentication**: Add API key authentication for production
4. **Network Isolation**: Workers in separate Docker network
5. **Secrets Management**: Use Docker secrets or environment injection
6. **Non-Root Containers**: All containers run as non-root users

## Troubleshooting

### Dead Letter Queue

Monitor failed tasks:
```bash
poetry run python scripts/monitor_dlq.py
```

### Database Migrations

Create a new migration:
```bash
poetry run alembic revision --autogenerate -m "Description"
```

Apply migrations:
```bash
poetry run alembic upgrade head
```

Rollback migration:
```bash
poetry run alembic downgrade -1
```

### Worker Debugging

Increase log level:
```bash
poetry run celery -A src.worker.celery_app worker --loglevel=debug
```

## License

MIT License

## Contributing

Contributions welcome! Please submit issues and pull requests.
