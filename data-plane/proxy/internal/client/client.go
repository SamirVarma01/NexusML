package client

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"

	"github.com/nexusml/proxy/internal/batcher"
	"github.com/rs/zerolog/log"
)

// ModelClient handles communication with the backend Python model server
type ModelClient struct {
	baseURL    string
	httpClient *http.Client
}

// BatchRequest is the payload sent to the model server
type BatchRequest struct {
	Requests []SingleRequest `json:"requests"`
}

// SingleRequest represents one inference request in a batch
type SingleRequest struct {
	ID   string          `json:"id"`
	Data json.RawMessage `json:"data"`
}

// BatchResponse is the response from the model server
type BatchResponse struct {
	Responses []SingleResponse `json:"responses"`
}

// SingleResponse represents one inference result
type SingleResponse struct {
	ID     string          `json:"id"`
	Result json.RawMessage `json:"result,omitempty"`
	Error  string          `json:"error,omitempty"`
}

// New creates a new ModelClient
func New(baseURL string) *ModelClient {
	return &ModelClient{
		baseURL: baseURL,
		httpClient: &http.Client{
			Timeout: 30 * time.Second,
			Transport: &http.Transport{
				MaxIdleConns:        100,
				MaxIdleConnsPerHost: 100,
				IdleConnTimeout:     90 * time.Second,
			},
		},
	}
}

// ProcessBatch sends a batch of requests to the model server
// This function is designed to be used as the batcher.ProcessFunc
func (c *ModelClient) ProcessBatch(ctx context.Context, batch *batcher.Batch) []batcher.Response {
	responses := make([]batcher.Response, 0, len(batch.Requests))

	// Build batch request
	batchReq := BatchRequest{
		Requests: make([]SingleRequest, len(batch.Requests)),
	}

	for i, req := range batch.Requests {
		batchReq.Requests[i] = SingleRequest{
			ID:   req.ID,
			Data: req.Payload,
		}
	}

	// Serialize request
	reqBody, err := json.Marshal(batchReq)
	if err != nil {
		log.Error().Err(err).Msg("Failed to marshal batch request")
		return c.errorResponses(batch, err)
	}

	// Send to model server
	url := fmt.Sprintf("%s/predict/batch", c.baseURL)
	httpReq, err := http.NewRequestWithContext(ctx, "POST", url, bytes.NewReader(reqBody))
	if err != nil {
		log.Error().Err(err).Msg("Failed to create HTTP request")
		return c.errorResponses(batch, err)
	}

	httpReq.Header.Set("Content-Type", "application/json")

	startTime := time.Now()
	resp, err := c.httpClient.Do(httpReq)
	if err != nil {
		log.Error().Err(err).Msg("Failed to send request to model server")
		return c.errorResponses(batch, err)
	}
	defer resp.Body.Close()

	duration := time.Since(startTime)
	log.Debug().
		Int("batch_size", len(batch.Requests)).
		Dur("duration", duration).
		Int("status_code", resp.StatusCode).
		Msg("Model server response")

	// Read response body
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		log.Error().Err(err).Msg("Failed to read response body")
		return c.errorResponses(batch, err)
	}

	// Check HTTP status
	if resp.StatusCode != http.StatusOK {
		err := fmt.Errorf("model server returned status %d: %s", resp.StatusCode, string(body))
		log.Error().Err(err).Msg("Model server error")
		return c.errorResponses(batch, err)
	}

	// Parse response
	var batchResp BatchResponse
	if err := json.Unmarshal(body, &batchResp); err != nil {
		log.Error().Err(err).Msg("Failed to unmarshal response")
		return c.errorResponses(batch, err)
	}

	// Convert to batcher responses
	for _, singleResp := range batchResp.Responses {
		resp := batcher.Response{
			ID:   singleResp.ID,
			Data: singleResp.Result,
		}
		if singleResp.Error != "" {
			resp.Error = fmt.Errorf("%s", singleResp.Error)
		}
		responses = append(responses, resp)
	}

	return responses
}

// errorResponses creates error responses for all requests in a batch
func (c *ModelClient) errorResponses(batch *batcher.Batch, err error) []batcher.Response {
	responses := make([]batcher.Response, len(batch.Requests))
	for i, req := range batch.Requests {
		responses[i] = batcher.Response{
			ID:    req.ID,
			Error: err,
		}
	}
	return responses
}

// HealthCheck verifies the model server is reachable
func (c *ModelClient) HealthCheck(ctx context.Context) error {
	url := fmt.Sprintf("%s/health", c.baseURL)
	req, err := http.NewRequestWithContext(ctx, "GET", url, nil)
	if err != nil {
		return err
	}

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("model server health check failed with status %d", resp.StatusCode)
	}

	return nil
}
