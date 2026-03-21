package main

import (
	"context"
	"encoding/json"
	"log"
	"os"
	"time"

	"github.com/segmentio/kafka-go"
)

// LinkCheckJob is the message Python publishes to the Kafka topic.
type LinkCheckJob struct {
	JobID      string   `json:"job_id"`
	SourceURL  string   `json:"source_url"`
	TargetURLs []string `json:"target_urls"`
	Depth      int      `json:"depth"`
}

func main() {
	brokers := getEnv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
	topic := getEnv("KAFKA_TOPIC", "link_check_jobs")
	groupID := getEnv("KAFKA_GROUP_ID", "link-checker-group")
	esURL := getEnv("ELASTICSEARCH_URL", "http://localhost:9200")

	reader := kafka.NewReader(kafka.ReaderConfig{
		Brokers:        []string{brokers},
		Topic:          topic,
		GroupID:        groupID,
		MinBytes:       1,
		MaxBytes:       10e6, // 10 MB
		MaxWait:        500 * time.Millisecond,
		CommitInterval: time.Second,
	})
	defer reader.Close()

	esClient := NewESClient(esURL)
	checker := NewChecker()

	log.Printf("Go link checker started — broker: %s, topic: %s, group: %s", brokers, topic, groupID)

	ctx := context.Background()
	for {
		msg, err := reader.ReadMessage(ctx)
		if err != nil {
			log.Printf("Kafka read error: %v — retrying in 1s", err)
			time.Sleep(time.Second)
			continue
		}

		var job LinkCheckJob
		if err := json.Unmarshal(msg.Value, &job); err != nil {
			log.Printf("Failed to parse message at offset %d: %v", msg.Offset, err)
			continue
		}

		// Each job processed in its own goroutine — consumer loop never blocks.
		go processJob(ctx, job, checker, esClient)
	}
}

func processJob(ctx context.Context, job LinkCheckJob, checker *Checker, es *ESClient) {
	log.Printf("Checking %d links for job %s (source: %s)", len(job.TargetURLs), job.JobID, job.SourceURL)

	results := checker.CheckBatch(job.TargetURLs, 50)

	broken := 0
	for _, r := range results {
		if r.IsValid {
			continue
		}

		doc := BrokenLinkDoc{
			JobID:        job.JobID,
			SourceURL:    job.SourceURL,
			BrokenURL:    r.URL,
			ErrorType:    r.ErrorType,
			ErrorMessage: r.ErrorMessage,
			Depth:        job.Depth,
			DiscoveredAt: time.Now().UTC().Format(time.RFC3339),
		}
		if r.StatusCode != 0 {
			doc.StatusCode = &r.StatusCode
		}

		if err := es.IndexBrokenLink(ctx, doc); err != nil {
			log.Printf("Failed to index broken link %s: %v", r.URL, err)
			continue
		}
		if err := es.IncrementBrokenLinks(ctx, job.JobID); err != nil {
			log.Printf("Failed to increment broken links count for job %s: %v", job.JobID, err)
		}
		broken++
	}

	log.Printf("Job %s done: %d/%d links broken", job.JobID, broken, len(job.TargetURLs))
}

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
