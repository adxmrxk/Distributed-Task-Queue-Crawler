package main

import (
	"crypto/tls"
	"fmt"
	"net"
	"net/http"
	"strings"
	"sync"
	"time"
)

// CheckResult holds the outcome of checking a single URL.
type CheckResult struct {
	URL         string
	IsValid     bool
	StatusCode  int
	ErrorType   string
	ErrorMessage string
}

// Checker makes HTTP HEAD requests to validate URLs.
type Checker struct {
	client *http.Client
}

func NewChecker() *Checker {
	return &Checker{
		client: &http.Client{
			Timeout: 10 * time.Second,
			Transport: &http.Transport{
				TLSClientConfig: &tls.Config{InsecureSkipVerify: false},
				DialContext: (&net.Dialer{
					Timeout: 5 * time.Second,
				}).DialContext,
				MaxIdleConnsPerHost: 50,
			},
			CheckRedirect: func(req *http.Request, via []*http.Request) error {
				if len(via) >= 10 {
					return fmt.Errorf("too many redirects")
				}
				return nil
			},
		},
	}
}

// Check validates a single URL. Uses HEAD; falls back to GET on 405.
func (c *Checker) Check(url string) CheckResult {
	result := c.doRequest("HEAD", url)

	// Some servers don't support HEAD — retry with GET.
	if result.StatusCode == http.StatusMethodNotAllowed {
		result = c.doRequest("GET", url)
	}

	return result
}

func (c *Checker) doRequest(method, url string) CheckResult {
	req, err := http.NewRequest(method, url, nil)
	if err != nil {
		return CheckResult{URL: url, IsValid: false, ErrorType: "INVALID_URL", ErrorMessage: err.Error()}
	}
	req.Header.Set("User-Agent", "Mozilla/5.0 (compatible; WebCrawler/1.0)")

	resp, err := c.client.Do(req)
	if err != nil {
		return classifyNetError(url, err)
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 400 {
		// 403/429 means the server is blocking the bot, not that the link is broken
		if resp.StatusCode == http.StatusForbidden || resp.StatusCode == http.StatusTooManyRequests {
			return CheckResult{URL: url, IsValid: true, StatusCode: resp.StatusCode}
		}
		return CheckResult{
			URL:          url,
			IsValid:      false,
			StatusCode:   resp.StatusCode,
			ErrorType:    "HTTP_ERROR",
			ErrorMessage: fmt.Sprintf("HTTP %d", resp.StatusCode),
		}
	}

	return CheckResult{URL: url, IsValid: true, StatusCode: resp.StatusCode}
}

// CheckBatch checks up to maxConcurrent URLs simultaneously using goroutines.
func (c *Checker) CheckBatch(urls []string, maxConcurrent int) []CheckResult {
	sem := make(chan struct{}, maxConcurrent)
	results := make([]CheckResult, len(urls))
	var wg sync.WaitGroup

	for i, url := range urls {
		wg.Add(1)
		go func(idx int, u string) {
			defer wg.Done()
			sem <- struct{}{}
			defer func() { <-sem }()
			results[idx] = c.CheckWithRetry(u, 2)
		}(i, url)
	}

	wg.Wait()
	return results
}

// CheckWithRetry retries transient failures (TIMEOUT, CONNECTION_ERROR) with
// exponential backoff. Permanent failures (DNS errors, HTTP 4xx/5xx) are not retried.
func (c *Checker) CheckWithRetry(url string, maxRetries int) CheckResult {
	result := c.Check(url)
	if result.IsValid {
		return result
	}
	// Only retry transient network errors, not permanent failures
	if result.ErrorType != "TIMEOUT" && result.ErrorType != "CONNECTION_ERROR" {
		return result
	}
	for attempt := 1; attempt <= maxRetries; attempt++ {
		backoff := time.Duration(attempt*attempt) * 500 * time.Millisecond
		time.Sleep(backoff)
		result = c.Check(url)
		if result.IsValid || (result.ErrorType != "TIMEOUT" && result.ErrorType != "CONNECTION_ERROR") {
			return result
		}
	}
	return result
}

func classifyNetError(url string, err error) CheckResult {
	msg := err.Error()
	errType := "CONNECTION_ERROR"

	switch {
	case strings.Contains(msg, "timeout") || strings.Contains(msg, "deadline exceeded"):
		errType = "TIMEOUT"
	case strings.Contains(msg, "no such host") || strings.Contains(msg, "DNS") || strings.Contains(msg, "lookup"):
		errType = "DNS_ERROR"
	case strings.Contains(msg, "certificate") || strings.Contains(msg, "tls") || strings.Contains(msg, "x509"):
		errType = "SSL_ERROR"
	}

	return CheckResult{URL: url, IsValid: false, ErrorType: errType, ErrorMessage: msg}
}
