# NexusML Data Plane - Go Inference Proxy
# High-performance request batching and routing

FROM golang:1.21-alpine AS builder

WORKDIR /app

# Install dependencies
COPY go.mod go.sum ./
RUN go mod download

# Copy source code
COPY . .

# Build the binary
RUN CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo -o proxy ./cmd/server

# Runtime image
FROM alpine:latest

RUN apk --no-cache add ca-certificates curl

WORKDIR /root/

# Copy binary from builder
COPY --from=builder /app/proxy .

# Expose port
EXPOSE 8080

# Health check endpoint
HEALTHCHECK --interval=10s --timeout=5s --retries=3 \
  CMD curl -f http://localhost:8080/health || exit 1

# Run the proxy
CMD ["./proxy"]
