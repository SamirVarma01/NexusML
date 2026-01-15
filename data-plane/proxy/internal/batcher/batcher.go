package batcher

import (
	"context"
	"sync"
	"time"

	"github.com/rs/zerolog/log"
)

// Request represents a single inference request waiting to be batched
type Request struct {
	ID       string
	Payload  []byte
	Response chan Response
}

// Response represents the result of an inference request
type Response struct {
	ID    string
	Data  []byte
	Error error
}

// Batch represents a collection of requests to be processed together
type Batch struct {
	Requests []*Request
}

// ProcessFunc is the function signature for processing a batch of requests
type ProcessFunc func(ctx context.Context, batch *Batch) []Response

// Batcher collects incoming requests and processes them in batches
type Batcher struct {
	maxBatchSize int
	timeout      time.Duration
	processFunc  ProcessFunc

	requestChan chan *Request
	stopChan    chan struct{}
	wg          sync.WaitGroup

	// Metrics
	mu              sync.RWMutex
	totalRequests   int64
	totalBatches    int64
	avgBatchSize    float64
}

// New creates a new Batcher with the given configuration
func New(maxBatchSize int, timeout time.Duration, processFunc ProcessFunc) *Batcher {
	return &Batcher{
		maxBatchSize: maxBatchSize,
		timeout:      timeout,
		processFunc:  processFunc,
		requestChan:  make(chan *Request, maxBatchSize*10), // Buffer for incoming requests
		stopChan:     make(chan struct{}),
	}
}

// Start begins the batching goroutine
func (b *Batcher) Start() {
	b.wg.Add(1)
	go b.batchLoop()
	log.Info().
		Int("max_batch_size", b.maxBatchSize).
		Dur("timeout", b.timeout).
		Msg("Batcher started")
}

// Stop gracefully shuts down the batcher
func (b *Batcher) Stop() {
	close(b.stopChan)
	b.wg.Wait()
	log.Info().Msg("Batcher stopped")
}

// Submit adds a request to the batch queue and waits for the response
func (b *Batcher) Submit(ctx context.Context, id string, payload []byte) ([]byte, error) {
	req := &Request{
		ID:       id,
		Payload:  payload,
		Response: make(chan Response, 1),
	}

	select {
	case b.requestChan <- req:
		// Request submitted
	case <-ctx.Done():
		return nil, ctx.Err()
	}

	select {
	case resp := <-req.Response:
		return resp.Data, resp.Error
	case <-ctx.Done():
		return nil, ctx.Err()
	}
}

// batchLoop is the main goroutine that collects and processes batches
func (b *Batcher) batchLoop() {
	defer b.wg.Done()

	for {
		batch := b.collectBatch()
		if batch == nil {
			return // Stop signal received
		}

		if len(batch.Requests) > 0 {
			b.processBatch(batch)
		}
	}
}

// collectBatch collects requests until batch is full or timeout expires
func (b *Batcher) collectBatch() *Batch {
	batch := &Batch{
		Requests: make([]*Request, 0, b.maxBatchSize),
	}

	// Wait for first request or stop signal
	select {
	case req := <-b.requestChan:
		batch.Requests = append(batch.Requests, req)
	case <-b.stopChan:
		return nil
	}

	// Set timeout for collecting more requests
	timer := time.NewTimer(b.timeout)
	defer timer.Stop()

	// Collect more requests until batch is full or timeout
	for len(batch.Requests) < b.maxBatchSize {
		select {
		case req := <-b.requestChan:
			batch.Requests = append(batch.Requests, req)
		case <-timer.C:
			// Timeout reached, process what we have
			return batch
		case <-b.stopChan:
			// Process remaining requests before stopping
			return batch
		}
	}

	return batch
}

// processBatch sends the batch to the process function and routes responses
func (b *Batcher) processBatch(batch *Batch) {
	ctx := context.Background()

	log.Debug().
		Int("batch_size", len(batch.Requests)).
		Msg("Processing batch")

	// Call the process function
	responses := b.processFunc(ctx, batch)

	// Route responses back to waiting requests
	responseMap := make(map[string]Response)
	for _, resp := range responses {
		responseMap[resp.ID] = resp
	}

	for _, req := range batch.Requests {
		if resp, ok := responseMap[req.ID]; ok {
			req.Response <- resp
		} else {
			req.Response <- Response{
				ID:    req.ID,
				Error: ErrResponseNotFound,
			}
		}
		close(req.Response)
	}

	// Update metrics
	b.updateMetrics(len(batch.Requests))
}

func (b *Batcher) updateMetrics(batchSize int) {
	b.mu.Lock()
	defer b.mu.Unlock()

	b.totalRequests += int64(batchSize)
	b.totalBatches++
	b.avgBatchSize = float64(b.totalRequests) / float64(b.totalBatches)
}

// Metrics returns current batcher statistics
func (b *Batcher) Metrics() (totalRequests, totalBatches int64, avgBatchSize float64) {
	b.mu.RLock()
	defer b.mu.RUnlock()
	return b.totalRequests, b.totalBatches, b.avgBatchSize
}

// Custom errors
type BatcherError string

func (e BatcherError) Error() string { return string(e) }

const ErrResponseNotFound = BatcherError("response not found for request")
