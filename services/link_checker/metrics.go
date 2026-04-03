package main

import (
	"net/http"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

var (
	urlsCheckedTotal = promauto.NewCounter(prometheus.CounterOpts{
		Name: "link_checker_urls_checked_total",
		Help: "Total number of URLs checked",
	})

	urlsBrokenTotal = promauto.NewCounterVec(prometheus.CounterOpts{
		Name: "link_checker_urls_broken_total",
		Help: "Total broken URLs discovered, partitioned by error type",
	}, []string{"error_type"})

	checkDurationSeconds = promauto.NewHistogram(prometheus.HistogramOpts{
		Name:    "link_checker_check_duration_seconds",
		Help:    "Time spent checking a single URL (seconds)",
		Buckets: prometheus.DefBuckets,
	})

	kafkaMessagesTotal = promauto.NewCounter(prometheus.CounterOpts{
		Name: "link_checker_kafka_messages_total",
		Help: "Total Kafka messages consumed and processed",
	})

	goroutinesActive = promauto.NewGauge(prometheus.GaugeOpts{
		Name: "link_checker_goroutines_active",
		Help: "Number of currently active link-check goroutines",
	})
)

// startMetricsServer exposes Prometheus metrics on addr (e.g. ":9091").
func startMetricsServer(addr string) {
	mux := http.NewServeMux()
	mux.Handle("/metrics", promhttp.Handler())
	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	})
	go func() {
		if err := http.ListenAndServe(addr, mux); err != nil {
			// Non-fatal: metrics unavailability should not crash the service
		}
	}()
}
