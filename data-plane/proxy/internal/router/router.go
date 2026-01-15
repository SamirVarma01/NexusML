package router

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"time"

	"github.com/google/uuid"
	"github.com/gorilla/mux"
	"github.com/nexusml/proxy/internal/batcher"
	"github.com/rs/zerolog/log"
)

// Router handles HTTP routing for the inference proxy
type Router struct {
	router  *mux.Router
	batcher *batcher.Batcher
}

// PredictRequest is the incoming inference request format
type PredictRequest struct {
	Data json.RawMessage `json:"data"`
}

// PredictResponse is the inference response format
type PredictResponse struct {
	RequestID string          `json:"request_id"`
	Result    json.RawMessage `json:"result,omitempty"`
	Error     string          `json:"error,omitempty"`
}

// HealthResponse is the health check response format
type HealthResponse struct {
	Status        string  `json:"status"`
	Uptime        string  `json:"uptime"`
	TotalRequests int64   `json:"total_requests"`
	TotalBatches  int64   `json:"total_batches"`
	AvgBatchSize  float64 `json:"avg_batch_size"`
}

// New creates a new Router
func New(b *batcher.Batcher) *Router {
	r := &Router{
		router:  mux.NewRouter(),
		batcher: b,
	}
	r.setupRoutes()
	return r
}

var startTime = time.Now()

func (r *Router) setupRoutes() {
	// Health check endpoint
	r.router.HandleFunc("/health", r.healthHandler).Methods("GET")

	// Metrics endpoint
	r.router.HandleFunc("/metrics", r.metricsHandler).Methods("GET")

	// Prediction endpoint - single request (gets batched internally)
	r.router.HandleFunc("/predict", r.predictHandler).Methods("POST")

	// Ready check (for Kubernetes)
	r.router.HandleFunc("/ready", r.readyHandler).Methods("GET")

	// Add middleware
	r.router.Use(loggingMiddleware)
	r.router.Use(recoveryMiddleware)
}

// Handler returns the HTTP handler
func (r *Router) Handler() http.Handler {
	return r.router
}

func (r *Router) healthHandler(w http.ResponseWriter, req *http.Request) {
	totalReqs, totalBatches, avgBatchSize := r.batcher.Metrics()

	resp := HealthResponse{
		Status:        "healthy",
		Uptime:        time.Since(startTime).String(),
		TotalRequests: totalReqs,
		TotalBatches:  totalBatches,
		AvgBatchSize:  avgBatchSize,
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(resp)
}

func (r *Router) metricsHandler(w http.ResponseWriter, req *http.Request) {
	totalReqs, totalBatches, avgBatchSize := r.batcher.Metrics()

	// Prometheus-style metrics
	w.Header().Set("Content-Type", "text/plain")
	w.Write([]byte("# HELP nexus_proxy_requests_total Total number of inference requests\n"))
	w.Write([]byte("# TYPE nexus_proxy_requests_total counter\n"))
	w.Write([]byte("nexus_proxy_requests_total " + formatInt(totalReqs) + "\n"))

	w.Write([]byte("# HELP nexus_proxy_batches_total Total number of batches processed\n"))
	w.Write([]byte("# TYPE nexus_proxy_batches_total counter\n"))
	w.Write([]byte("nexus_proxy_batches_total " + formatInt(totalBatches) + "\n"))

	w.Write([]byte("# HELP nexus_proxy_batch_size_avg Average batch size\n"))
	w.Write([]byte("# TYPE nexus_proxy_batch_size_avg gauge\n"))
	w.Write([]byte("nexus_proxy_batch_size_avg " + formatFloat(avgBatchSize) + "\n"))
}

func (r *Router) readyHandler(w http.ResponseWriter, req *http.Request) {
	w.WriteHeader(http.StatusOK)
	w.Write([]byte(`{"status":"ready"}`))
}

func (r *Router) predictHandler(w http.ResponseWriter, req *http.Request) {
	// Read request body
	body, err := io.ReadAll(req.Body)
	if err != nil {
		sendError(w, "Failed to read request body", http.StatusBadRequest)
		return
	}
	defer req.Body.Close()

	// Generate request ID
	requestID := uuid.New().String()

	// Set timeout context
	ctx, cancel := context.WithTimeout(req.Context(), 30*time.Second)
	defer cancel()

	// Submit to batcher and wait for response
	result, err := r.batcher.Submit(ctx, requestID, body)

	// Build response
	resp := PredictResponse{
		RequestID: requestID,
	}

	if err != nil {
		resp.Error = err.Error()
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusInternalServerError)
		json.NewEncoder(w).Encode(resp)
		return
	}

	resp.Result = result

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(resp)
}

func sendError(w http.ResponseWriter, message string, status int) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(map[string]string{"error": message})
}

func formatInt(n int64) string {
	b, _ := json.Marshal(n)
	return string(b)
}

func formatFloat(f float64) string {
	b, _ := json.Marshal(f)
	return string(b)
}

// Middleware

func loggingMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()

		// Wrap response writer to capture status code
		wrapped := &responseWriter{ResponseWriter: w, statusCode: http.StatusOK}

		next.ServeHTTP(wrapped, r)

		log.Info().
			Str("method", r.Method).
			Str("path", r.URL.Path).
			Int("status", wrapped.statusCode).
			Dur("duration", time.Since(start)).
			Msg("Request completed")
	})
}

func recoveryMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		defer func() {
			if err := recover(); err != nil {
				log.Error().Interface("panic", err).Msg("Recovered from panic")
				sendError(w, "Internal server error", http.StatusInternalServerError)
			}
		}()
		next.ServeHTTP(w, r)
	})
}

type responseWriter struct {
	http.ResponseWriter
	statusCode int
}

func (rw *responseWriter) WriteHeader(code int) {
	rw.statusCode = code
	rw.ResponseWriter.WriteHeader(code)
}
