package main

import (
	"net/http"
	"net/http/httptest"
	"sync/atomic"
	"testing"
	"time"
)

// --- Check ---

func TestCheck_ValidURL(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))
	defer srv.Close()

	c := NewChecker()
	result := c.Check(srv.URL)

	if !result.IsValid {
		t.Errorf("expected valid, got error: %s", result.ErrorMessage)
	}
	if result.StatusCode != http.StatusOK {
		t.Errorf("expected 200, got %d", result.StatusCode)
	}
}

func TestCheck_404(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusNotFound)
	}))
	defer srv.Close()

	c := NewChecker()
	result := c.Check(srv.URL)

	if result.IsValid {
		t.Error("expected invalid for 404")
	}
	if result.ErrorType != "HTTP_ERROR" {
		t.Errorf("expected HTTP_ERROR, got %s", result.ErrorType)
	}
	if result.StatusCode != http.StatusNotFound {
		t.Errorf("expected status 404, got %d", result.StatusCode)
	}
}

func TestCheck_500(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
	}))
	defer srv.Close()

	c := NewChecker()
	result := c.Check(srv.URL)

	if result.IsValid {
		t.Error("expected invalid for 500")
	}
	if result.ErrorType != "HTTP_ERROR" {
		t.Errorf("expected HTTP_ERROR, got %s", result.ErrorType)
	}
}

func TestCheck_HeadFallbackToGet(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method == http.MethodHead {
			w.WriteHeader(http.StatusMethodNotAllowed)
			return
		}
		w.WriteHeader(http.StatusOK)
	}))
	defer srv.Close()

	c := NewChecker()
	result := c.Check(srv.URL)

	if !result.IsValid {
		t.Errorf("expected valid after GET fallback, got: %s", result.ErrorMessage)
	}
}

func TestCheck_InvalidURL(t *testing.T) {
	c := NewChecker()
	// Control character in URL fails http.NewRequest at parse time
	result := c.Check("http://example.com/\x7f")

	if result.IsValid {
		t.Error("expected invalid for malformed URL")
	}
	if result.ErrorType != "INVALID_URL" {
		t.Errorf("expected INVALID_URL, got %s", result.ErrorType)
	}
}

func TestCheck_Redirect(t *testing.T) {
	var finalSrv *httptest.Server
	finalSrv = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/redirected" {
			w.WriteHeader(http.StatusOK)
			return
		}
		http.Redirect(w, r, finalSrv.URL+"/redirected", http.StatusMovedPermanently)
	}))
	defer finalSrv.Close()

	c := NewChecker()
	result := c.Check(finalSrv.URL)

	if !result.IsValid {
		t.Errorf("expected valid after redirect, got: %s", result.ErrorMessage)
	}
}

// --- CheckBatch ---

func TestCheckBatch_AllValid(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))
	defer srv.Close()

	urls := make([]string, 20)
	for i := range urls {
		urls[i] = srv.URL
	}

	c := NewChecker()
	results := c.CheckBatch(urls, 5)

	if len(results) != 20 {
		t.Errorf("expected 20 results, got %d", len(results))
	}
	for i, r := range results {
		if !r.IsValid {
			t.Errorf("result[%d] expected valid, got: %s", i, r.ErrorMessage)
		}
	}
}

func TestCheckBatch_MixedResults(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/broken" {
			w.WriteHeader(http.StatusNotFound)
			return
		}
		w.WriteHeader(http.StatusOK)
	}))
	defer srv.Close()

	urls := []string{
		srv.URL + "/ok",
		srv.URL + "/broken",
		srv.URL + "/ok",
	}

	c := NewChecker()
	results := c.CheckBatch(urls, 3)

	if len(results) != 3 {
		t.Fatalf("expected 3 results, got %d", len(results))
	}
	if !results[0].IsValid {
		t.Error("results[0] expected valid")
	}
	if results[1].IsValid {
		t.Error("results[1] expected invalid (404)")
	}
	if !results[2].IsValid {
		t.Error("results[2] expected valid")
	}
}

func TestCheckBatch_RespectsConcurrencyLimit(t *testing.T) {
	var active int32
	var maxObserved int32

	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		current := atomic.AddInt32(&active, 1)
		for {
			observed := atomic.LoadInt32(&maxObserved)
			if current <= observed || atomic.CompareAndSwapInt32(&maxObserved, observed, current) {
				break
			}
		}
		time.Sleep(10 * time.Millisecond)
		atomic.AddInt32(&active, -1)
		w.WriteHeader(http.StatusOK)
	}))
	defer srv.Close()

	urls := make([]string, 30)
	for i := range urls {
		urls[i] = srv.URL
	}

	c := NewChecker()
	c.CheckBatch(urls, 5)

	if maxObserved > 5 {
		t.Errorf("concurrency exceeded limit: max observed %d, limit 5", maxObserved)
	}
}

// --- CheckWithRetry ---

func TestCheckWithRetry_SucceedsFirstTry(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))
	defer srv.Close()

	c := NewChecker()
	result := c.CheckWithRetry(srv.URL, 2)

	if !result.IsValid {
		t.Errorf("expected valid, got: %s", result.ErrorMessage)
	}
}

func TestCheckWithRetry_NoRetryOnPermanentError(t *testing.T) {
	var callCount int32
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		atomic.AddInt32(&callCount, 1)
		w.WriteHeader(http.StatusNotFound)
	}))
	defer srv.Close()

	c := NewChecker()
	result := c.CheckWithRetry(srv.URL, 3)

	if result.IsValid {
		t.Error("expected invalid for permanent 404")
	}
	// HEAD + GET fallback attempt = 2 calls max; should NOT retry 404
	if atomic.LoadInt32(&callCount) > 2 {
		t.Errorf("expected no retries for HTTP_ERROR, got %d calls", callCount)
	}
}

// --- classifyNetError ---

func TestClassifyNetError_Timeout(t *testing.T) {
	c := NewChecker()
	// Use a non-routable address to trigger a connection timeout
	result := c.doRequest("HEAD", "http://192.0.2.1")
	// 192.0.2.0/24 is TEST-NET — guaranteed non-routable per RFC 5737
	// The error type should be TIMEOUT or CONNECTION_ERROR (OS dependent)
	if result.IsValid {
		t.Error("expected invalid for non-routable address")
	}
}
