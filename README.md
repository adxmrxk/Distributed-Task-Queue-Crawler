# Distributed Web Crawler

A web crawler that finds broken links on any site. Submit a URL, it crawls the whole site, validates every external link, and reports back which ones are dead.

Built it to learn distributed systems — Python handles the crawling, a separate Go service validates external links in parallel, and everything talks to each other through Kafka and Redis.

## What's in it

- **FastAPI** for the HTTP API
- **Celery + Redis** for the task queue
- **Playwright** to handle JavaScript-heavy sites
- **Kafka** to hand off external link validation to a Go microservice
- **Go service** with 50 goroutines validating URLs in parallel
- **Elasticsearch** for storage and full-text search across crawled pages
- **Next.js** frontend with live progress and a Grafana dashboard for metrics

## Run it

You need Docker. That's it.

```bash
docker-compose up -d
```

Then open the frontend (run separately):

```bash
cd frontend
npm install
npm run dev
```

Frontend is at `localhost:3000`, API at `localhost:8000/docs`, Grafana at `localhost:3001`.

## How it works

1. Submit a URL through the UI
2. A Celery worker crawls it with a real browser (Playwright), extracts every link
3. Internal links get queued for further crawling (BFS, configurable depth/page limits)
4. External links get pushed to Kafka, where the Go service picks them up and validates them
5. Broken links and full page content land in Elasticsearch
6. The frontend polls every 2s for live progress and fires a toast when the job finishes

Per-domain rate limiting (Redis token bucket), robots.txt support, exponential backoff retries, and a dead letter queue keep things polite and resilient.

## Hitting the API directly

```bash
# Submit a job
curl -X POST localhost:8000/api/v1/jobs \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com", "max_depth": 3, "max_pages": 100}'

# Check status
curl localhost:8000/api/v1/jobs/{job_id}

# Get broken links
curl localhost:8000/api/v1/results/{job_id}/broken-links

# Search across all crawled pages
curl "localhost:8000/api/v1/search?q=keyword"
```

Full docs at `localhost:8000/docs`.

## Tests

```bash
# Python
poetry run pytest

# Go
cd services/link_checker && go test ./...
```

CI runs both on every push.

## Layout

```
src/                # Python — FastAPI + Celery + crawler
services/link_checker/   # Go — Kafka consumer + URL validator
frontend/           # Next.js UI
k8s/                # Kubernetes manifests
prometheus/         # Scrape config
grafana/            # Dashboard JSON
.github/workflows/  # CI/CD
```

## Notes

- Tuned for ~2-6 pages/sec with default settings (Playwright is slow on purpose, it waits for the full page to render)
- The Go link checker handles 100-300 URLs/sec
- 403/429 responses don't count as broken links, those mean the site is blocking bots, not that the link is dead
- Set `CRAWLER_MAX_DEPTH` and `CRAWLER_MAX_PAGES` in `.env` to control crawl scope
