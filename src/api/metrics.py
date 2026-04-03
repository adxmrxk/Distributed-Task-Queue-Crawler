from prometheus_client import Counter, Gauge, Histogram

pages_crawled_total = Counter(
    "crawler_pages_crawled_total",
    "Total pages successfully crawled",
    ["job_id"],
)

broken_links_total = Counter(
    "crawler_broken_links_total",
    "Total broken links discovered",
    ["error_type"],
)

crawl_duration_seconds = Histogram(
    "crawler_page_crawl_duration_seconds",
    "Time to crawl a single page (seconds)",
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
)

active_jobs = Gauge(
    "crawler_active_jobs",
    "Number of currently IN_PROGRESS jobs",
)
