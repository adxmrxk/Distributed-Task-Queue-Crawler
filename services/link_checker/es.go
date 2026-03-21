package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"time"

	"github.com/google/uuid"
)

// BrokenLinkDoc is the document written to the broken_links Elasticsearch index.
type BrokenLinkDoc struct {
	JobID        string  `json:"job_id"`
	SourceURL    string  `json:"source_url"`
	BrokenURL    string  `json:"broken_url"`
	StatusCode   *int    `json:"status_code,omitempty"`
	ErrorType    string  `json:"error_type"`
	ErrorMessage string  `json:"error_message"`
	Depth        int     `json:"depth"`
	DiscoveredAt string  `json:"discovered_at"`
}

// ESClient writes documents to Elasticsearch via its HTTP API.
// No SDK needed — ES speaks plain HTTP+JSON.
type ESClient struct {
	baseURL    string
	httpClient *http.Client
}

func NewESClient(baseURL string) *ESClient {
	return &ESClient{
		baseURL:    baseURL,
		httpClient: &http.Client{Timeout: 10 * time.Second},
	}
}

// IndexBrokenLink writes a broken link document to the broken_links index.
func (e *ESClient) IndexBrokenLink(ctx context.Context, doc BrokenLinkDoc) error {
	id := uuid.New().String()
	url := fmt.Sprintf("%s/broken_links/_doc/%s?refresh=true", e.baseURL, id)

	body, err := json.Marshal(doc)
	if err != nil {
		return err
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPut, url, bytes.NewReader(body))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := e.httpClient.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 400 {
		return fmt.Errorf("ES IndexBrokenLink returned %d", resp.StatusCode)
	}
	return nil
}

// IncrementBrokenLinks uses an ES painless script to atomically increment
// total_broken_links on the job document.
func (e *ESClient) IncrementBrokenLinks(ctx context.Context, jobID string) error {
	url := fmt.Sprintf("%s/crawl_jobs/_update/%s", e.baseURL, jobID)
	body := `{"script":{"source":"ctx._source.total_broken_links += 1","lang":"painless"}}`

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewBufferString(body))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := e.httpClient.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 400 {
		return fmt.Errorf("ES IncrementBrokenLinks returned %d", resp.StatusCode)
	}
	return nil
}
