# Distributed Web Crawler

**Production-grade distributed web crawler that finds broken links across an entire site.**

Submit a URL, the system crawls the whole site with a real browser, validates every external link in parallel, and reports back which ones are dead. Built as a polyglot distributed system using Python for orchestration and Go for high-throughput URL validation, with Kafka and Redis as the connective tissue.

---

## Table of Contents

- [Project Overview](#project-overview)
- [How It Works](#how-it-works)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [API Reference](#api-reference)
- [Configuration](#configuration)

---

## Project Overview

### What It Is

A distributed web crawler designed as a horizontally scalable task pipeline. The Python side handles orchestration, JavaScript-aware page rendering, and result aggregation. The Go side does high-throughput external link validation. Kafka decouples the two so each can scale independently.

The system exposes a REST API for submitting crawl jobs and querying results, plus a Next.js dashboard for live progress tracking and full-text search across crawled pages.

### The Problem It Solves

Broken links degrade user experience, hurt SEO rankings, and undermine trust. Manually auditing a website with thousands of pages and tens of thousands of outbound links is infeasible. Commercial site-audit tools work but are expensive and opaque.

The technical challenges of doing this well are non-trivial:

- **Modern sites are JavaScript-heavy.** A naive HTTP crawler misses anything rendered client-side.
- **External link validation is the bottleneck.** A site with 10,000 outbound links to slow external hosts will take hours if validated sequentially.
- **Politeness matters.** Hammering a single domain gets you rate-limited, blocked, or sued. Robots.txt and per-domain rate limits are required, not optional.
- **Failure is the norm, not the exception.** Network timeouts, 5xx errors, JavaScript bombs, infinite redirect loops, and adversarial pages all need graceful handling.

This project solves each of these problems with the right tool for the job: Playwright for rendering, Go goroutines for parallel HTTP validation, Redis token buckets for rate limiting, exponential backoff with a dead letter queue for resilience.

### What It Does

- Crawls a website breadth-first with configurable depth and page limits
- Renders JavaScript using a headless browser so SPAs work correctly
- Validates every external link in parallel via a Go microservice
- Respects `robots.txt` and rate limits per domain
- Stores all page content and broken-link findings in Elasticsearch with full-text search
- Streams live progress to a Next.js dashboard
- Exposes Prometheus metrics and a pre-built Grafana dashboard
- Handles failures with exponential backoff retries and a dead letter queue

---

## How It Works

The system runs as a multi-stage pipeline. Each stage is independently scalable.

```
        ┌────────────────────────────┐
        │  Client (UI or API)        │
        │  POST /api/v1/jobs         │
        └──────────────┬─────────────┘
                       ▼
        ┌────────────────────────────┐
        │  FastAPI                   │   Job intake, validation,
        │  Creates job record        │   auth, REST endpoints
        └──────────────┬─────────────┘
                       ▼
        ┌────────────────────────────┐
        │  Celery (Redis broker)     │   Task queue with 3 workers
        └──────────────┬─────────────┘
                       ▼
   1.  Crawler Worker (Python + Playwright)
       • Fetches the page in a real browser
       • Extracts every <a href> link
       • Applies robots.txt and per-domain rate limits
       • Classifies links as internal vs external
                       │
            ┌──────────┴──────────┐
            ▼                     ▼
   2.  Internal Links        3.  External Links
       Re-queued in Celery       Pushed to Kafka topic
       for further crawling      `link_check_jobs`
       (BFS, depth-limited)
                                  │
                                  ▼
                       ┌────────────────────────────┐
                       │  Link Checker (Go)         │   2 replicas, 50
                       │  Kafka consumer            │   goroutines each
                       │  Parallel HTTP HEAD/GET    │
                       └──────────────┬─────────────┘
                                      ▼
        ┌──────────────────────────────────────────────┐
        │  Elasticsearch                                │
        │  Pages, broken links, crawl metadata          │
        └──────────────┬───────────────────────────────┘
                       ▼
        ┌──────────────────────────────────────────────┐
        │  Next.js Frontend                             │
        │  Polls /api/v1/jobs/{id} every 2s             │
        │  Live progress, results, full-text search     │
        └──────────────────────────────────────────────┘
```

---

## Architecture

```
                   ┌──────────────────────────────────────┐
                   │           CLIENT LAYER               │
                   │   Next.js UI  /  REST API consumers  │
                   └─────────────────┬────────────────────┘
                                     ▼
                   ┌──────────────────────────────────────┐
                   │           API LAYER                  │
                   │   FastAPI (Uvicorn)                  │
                   │   JWT auth, request validation       │
                   └─────────────────┬────────────────────┘
                                     ▼
                   ┌──────────────────────────────────────┐
                   │         TASK QUEUE LAYER             │
                   │   Celery (Redis broker + backend)    │
                   │   3 worker replicas, retry policy    │
                   └─────────────────┬────────────────────┘
                                     ▼
       ┌─────────────────────────────────────────────────────┐
       │                COMPUTE LAYER                         │
       │  ┌─────────────────────┐   ┌──────────────────────┐ │
       │  │  Crawler (Python)   │   │  Link Checker (Go)   │ │
       │  │  Playwright + BFS   │   │  50 goroutines per   │ │
       │  │  rate-limited fetch │   │  replica, Kafka cons │ │
       │  └──────────┬──────────┘   └──────────┬───────────┘ │
       └────────────┼─────────────────────────┼─────────────┘
                    │                          │
                    ▼                          ▼
       ┌─────────────────────────────────────────────────────┐
       │              MESSAGING LAYER                         │
       │   Kafka (link_check_jobs)  +  Redis (Celery broker) │
       └─────────────────────────────────────────────────────┘
                              ▼
       ┌─────────────────────────────────────────────────────┐
       │                 DATA LAYER                           │
       │   Elasticsearch (pages, broken links, metadata)      │
       │   Redis (rate limiter token buckets, cache)          │
       └─────────────────────────────────────────────────────┘

       ┌─────────────────────────────────────────────────────┐
       │             OBSERVABILITY LAYER                      │
       │   Prometheus  ──▶  Grafana                           │
       │   Flower (Celery)  /  celery-exporter                │
       └─────────────────────────────────────────────────────┘
```

---

## Tech Stack

### Application Runtime

| Component       | Technology               | Why It's Used |
|-----------------|--------------------------|---------------|
| API             | **FastAPI + Uvicorn**    | Async-first, automatic OpenAPI docs at `/docs`, Pydantic validation for free |
| Task queue      | **Celery 5 + Redis**     | Battle-tested Python task queue with retries, scheduling, and dead-letter handling |
| Crawler         | **Playwright**           | Real browser rendering so JavaScript-heavy sites work; HTTP-only crawlers miss SPA content |
| Link checker    | **Go 1.21**              | Goroutines make parallel HTTP validation trivial and fast; ~100 to 300 URLs/sec per replica |
| Frontend        | **Next.js 14 + TypeScript** | App Router with React Server Components, Tailwind for styling |

### Messaging and Queueing

| Component  | Purpose |
|------------|---------|
| **Kafka**  | Decouples the Python crawler from the Go link checker. Topic `link_check_jobs` carries external URLs awaiting validation. Each service scales independently. |
| **Redis**  | Celery broker and result backend for internal task distribution. Also stores rate limiter token buckets. |
| **Zookeeper** | Kafka coordination (Confluent platform). |

### Data and Storage

| Component       | Purpose |
|-----------------|---------|
| **Elasticsearch** | Stores crawled page content, broken link findings, and job metadata. Provides full-text search across all crawled content via `/api/v1/search`. |
| **Redis**         | Token bucket rate limiting per domain. Cache for parsed `robots.txt` to avoid re-fetching. |

### Crawling and Politeness

| Component                | Purpose |
|--------------------------|---------|
| **Playwright**           | Headless browser for JavaScript-aware page fetching |
| **Robots.txt parser**    | Respects site crawl rules; configurable per-deployment |
| **Redis token bucket**   | Per-domain rate limiting; default 1.0 req/sec/domain |
| **Exponential backoff**  | Retries on 5xx and network errors with capped delays |
| **Dead letter queue**    | Failed tasks after max retries are captured for inspection rather than lost |

### Frontend

| Component             | Purpose |
|-----------------------|---------|
| **Next.js 14**        | App Router, file-based routing, React Server Components |
| **TypeScript**        | Type-safe API client and component props |
| **Tailwind CSS**      | Utility-first styling, no design system overhead |
| **Polling (2s)**      | Live job progress without WebSocket complexity |
| **Toast notifications** | Job completion alerts |

### Containers and Orchestration

| Tool              | Purpose |
|-------------------|---------|
| **Docker**        | Multi-stage builds for API, worker, and link checker |
| **Docker Compose**| Full local stack in one command |
| **Kubernetes**    | Production manifests for each service with replicas |

### Observability

| Component             | Purpose |
|-----------------------|---------|
| **Prometheus**        | Scrapes metrics from the API, Celery, and the link checker |
| **Grafana**           | Pre-provisioned dashboard for crawl rate, queue depth, error rate |
| **Flower**            | Live Celery task inspection at port 5555 |
| **celery-exporter**   | Exposes Celery queue metrics in Prometheus format |
| **JSON logging**      | Structured logs via `python-json-logger` for ingestion into log pipelines |

### Security

| Component                       | Purpose |
|----------------------------------|---------|
| **JWT auth** (`python-jose`)    | Stateless authentication on protected endpoints |
| **bcrypt**                       | Password hashing |
| **Pydantic validation**         | Input validation on every API endpoint |

### Tooling and Quality

| Tool                | Purpose |
|---------------------|---------|
| **Poetry**          | Python dependency management with lockfile |
| **Black + Ruff**    | Formatting and linting (line length 100) |
| **pytest**          | Unit and integration test runner |
| **GitHub Actions**  | CI for both Python and Go on every push |

---

## Project Structure

```
distributed-crawler/
│
├── src/                              Python source
│   ├── api/                          FastAPI application
│   │   ├── main.py                   App entry point and middleware setup
│   │   ├── auth.py                   JWT token issuance and validation
│   │   ├── dependencies.py           Reusable FastAPI dependencies
│   │   ├── metrics.py                Prometheus metric definitions
│   │   ├── routes/
│   │   │   ├── jobs.py               Submit and retrieve crawl jobs
│   │   │   ├── results.py            Fetch broken links and crawl results
│   │   │   ├── search.py             Full-text search over crawled pages
│   │   │   ├── auth.py               Login and registration endpoints
│   │   │   └── health.py             Liveness and readiness probes
│   │   └── schemas/                  Pydantic request and response models
│   │
│   ├── worker/                       Celery worker code
│   │   ├── celery_app.py             Celery configuration and broker setup
│   │   ├── base_task.py              Base task class with retry logic
│   │   └── tasks/
│   │       └── crawler.py            The crawl task itself
│   │
│   ├── crawler/                      Crawling primitives
│   │   ├── playwright_crawler.py     Browser-based page fetcher
│   │   ├── link_extractor.py         Parses links from rendered HTML
│   │   ├── link_validator.py         Internal validation helpers
│   │   ├── politeness.py             Robots.txt parsing and enforcement
│   │   └── rate_limiter.py           Redis token bucket implementation
│   │
│   ├── db/                           Storage layer
│   │   ├── elasticsearch_client.py   ES connection wrapper
│   │   ├── indices.py                Index mappings and settings
│   │   ├── models/                   Document schemas for jobs, pages, broken links, DLQ
│   │   ├── repositories/             Data access methods per entity
│   │   └── migrations/               Alembic migrations
│   │
│   ├── core/                         Cross-cutting concerns
│   │   ├── config.py                 Pydantic Settings with env var loading
│   │   ├── constants.py              Shared constants
│   │   ├── exceptions.py             Domain exception types
│   │   └── logging.py                JSON logging setup
│   │
│   └── utils/
│       ├── url_utils.py              URL normalization, domain extraction
│       └── retry_utils.py            Exponential backoff helpers
│
├── services/link_checker/            Go microservice
│   ├── main.go                       Kafka consumer entrypoint
│   ├── checker.go                    Parallel URL validation logic
│   ├── es.go                         Elasticsearch writer
│   ├── metrics.go                    Prometheus metrics
│   ├── checker_test.go               Unit tests
│   └── go.mod / go.sum               Go module manifest
│
├── frontend/                         Next.js dashboard
│   ├── app/
│   │   ├── page.tsx                  Home (submit a crawl)
│   │   ├── jobs/page.tsx             Job list and live progress
│   │   ├── search/page.tsx           Full-text search UI
│   │   ├── layout.tsx                Root layout
│   │   └── globals.css               Tailwind imports
│   ├── components/toast.tsx          Toast notification component
│   ├── lib/api.ts                    Typed REST client
│   └── package.json
│
├── docker/                           Container build files
│   ├── Dockerfile.api                Multi-stage FastAPI image
│   ├── Dockerfile.worker             Multi-stage Celery worker image
│   └── Dockerfile.link_checker       Multi-stage Go image
│
├── k8s/                              Kubernetes manifests
│   ├── namespace.yaml
│   ├── api.yaml                      API Deployment and Service
│   ├── worker.yaml                   Worker Deployment with replicas
│   ├── link-checker.yaml             Go service Deployment
│   ├── redis.yaml                    Redis StatefulSet
│   ├── kafka.yaml                    Kafka and Zookeeper
│   └── elasticsearch.yaml            Elasticsearch StatefulSet
│
├── prometheus/
│   └── prometheus.yml                Scrape config for all services
│
├── grafana/
│   ├── dashboards/crawler.json       Pre-built crawler dashboard
│   └── provisioning/                 Auto-provisioned datasource and dashboards
│
├── tests/
│   ├── unit/                         Fast, isolated tests
│   │   ├── test_link_extractor.py
│   │   ├── test_url_utils.py
│   │   └── test_retry_utils.py
│   └── integration/                  Real Elasticsearch and Redis required
│       ├── test_api_jobs.py
│       ├── test_job_repository.py
│       └── test_link_repository.py
│
├── .github/workflows/
│   ├── test.yml                      Runs pytest and go test on every push
│   └── docker.yml                    Builds and publishes container images
│
├── scripts/                          Operational scripts
├── alembic.ini                       Database migration config
├── pyproject.toml                    Poetry config, Black, Ruff, pytest settings
├── docker-compose.yml                Local development stack
├── .env.example                      Environment variable template
└── README.md
```

---

## Getting Started

### Prerequisites

You only need Docker installed. Everything else runs in containers.

For local frontend development, you also need Node.js 18+.

### One-Command Backend Startup

```bash
docker-compose up -d
```

This brings up the full backend stack:

| Service        | URL                        | Purpose |
|----------------|----------------------------|---------|
| API + docs     | http://localhost:8000/docs | Interactive Swagger UI |
| Flower         | http://localhost:5555      | Celery task inspector |
| Prometheus     | http://localhost:9090      | Metrics queries |
| Grafana        | http://localhost:3001      | Crawler dashboards (admin / admin) |
| Elasticsearch  | http://localhost:9200      | Direct ES queries |

### Frontend

The Next.js dashboard runs separately for faster iteration:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000.

### Submit Your First Crawl

```bash
curl -X POST http://localhost:8000/api/v1/jobs \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com", "max_depth": 2, "max_pages": 50}'
```

The response includes a `job_id`. Use it to poll progress or open the dashboard at http://localhost:3000 to watch live.

### Tear Down

```bash
docker-compose down -v
```

The `-v` flag also removes persisted Elasticsearch, Redis, and Kafka data.

---

## API Reference

Full interactive docs at http://localhost:8000/docs (Swagger UI).

### Submit a Job

```http
POST /api/v1/jobs
Content-Type: application/json

{
  "url": "https://example.com",
  "max_depth": 3,
  "max_pages": 100
}
```

### Get Job Status

```http
GET /api/v1/jobs/{job_id}
```

Returns crawl progress: pages visited, links queued, broken links found so far, current status (PENDING, RUNNING, COMPLETED, FAILED).

### Get Broken Links

```http
GET /api/v1/results/{job_id}/broken-links
```

Returns the full list of broken links discovered, including the source page, the dead URL, and the HTTP status code that classified it as broken.

### Full-Text Search

```http
GET /api/v1/search?q=keyword
```

Searches across all crawled page content using Elasticsearch.

### Authentication

```http
POST /api/v1/auth/register
POST /api/v1/auth/login
```

Returns a JWT bearer token to include as `Authorization: Bearer <token>` on protected endpoints.

---

## Configuration

All configuration is via environment variables, defined in `.env`. Copy `.env.example` to `.env` and adjust.

### Application

| Variable          | Description                  | Default |
|-------------------|------------------------------|---------|
| `APP_NAME`        | Display name                 | `Distributed Web Crawler` |
| `DEBUG`           | Enable debug mode            | `False` |

### Elasticsearch

| Variable             | Description       | Default                  |
|----------------------|-------------------|--------------------------|
| `ELASTICSEARCH_URL`  | Cluster URL       | `http://localhost:9200`  |

### Redis and Celery

| Variable                       | Description                | Default                  |
|--------------------------------|----------------------------|--------------------------|
| `REDIS_URL`                    | Redis connection           | `redis://localhost:6379/0` |
| `REDIS_MAX_CONNECTIONS`        | Pool size                  | `50`                     |
| `CELERY_BROKER_URL`            | Celery broker              | `redis://localhost:6379/0` |
| `CELERY_RESULT_BACKEND`        | Celery results             | `redis://localhost:6379/1` |
| `CELERY_TASK_SOFT_TIME_LIMIT`  | Soft task timeout (seconds)| `300`                    |
| `CELERY_TASK_TIME_LIMIT`       | Hard task timeout (seconds)| `360`                    |

### Crawler

| Variable                          | Description                            | Default |
|-----------------------------------|----------------------------------------|---------|
| `CRAWLER_USER_AGENT`              | User-Agent string sent to target sites | `DistributedCrawler/1.0 (...)` |
| `CRAWLER_DEFAULT_TIMEOUT`         | Per-page fetch timeout (seconds)       | `30`    |
| `CRAWLER_MAX_DEPTH`               | BFS depth cap                          | `3`     |
| `CRAWLER_MAX_PAGES`               | Max pages crawled per job              | `100`   |
| `CRAWLER_RESPECT_ROBOTS`          | Honor robots.txt                       | `True`  |
| `CRAWLER_RATE_LIMIT_PER_DOMAIN`   | Requests per second per domain         | `1.0`   |

### Retry and Dead Letter

| Variable               | Description                              | Default |
|------------------------|------------------------------------------|---------|
| `RETRY_MAX_ATTEMPTS`   | Max retries before sending to DLQ        | `5`     |
| `RETRY_BACKOFF_BASE`   | Initial backoff (seconds)                | `60`    |
| `RETRY_BACKOFF_MAX`    | Backoff cap (seconds)                    | `600`   |
| `DLQ_ENABLED`          | Capture exhausted tasks                  | `True`  |
| `DLQ_ALERT_WEBHOOK`    | Optional webhook for DLQ events          | (none)  |
