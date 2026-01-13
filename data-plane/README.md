# NexusML Data Plane

The data plane handles **high-performance model serving** through dynamic batching and GPU optimization.

## Architecture

```
Users → Go Proxy (batching) → Python Server (inference) → GPU
```

## Components

### 1. Go Inference Proxy (`proxy/`)
- Accepts HTTP requests from users
- Queues and batches requests
- Forwards batches to Python server
- Routes responses back to users

### 2. Python Model Server (`model-server/`)
- Loads models from S3 using control-plane metadata
- Runs batch inference on GPU/CPU
- Exposes FastAPI endpoint for batched predictions

## Performance

**Goal**: 10x throughput improvement through batching

- **Without batching**: ~50 requests/second, 15-25% GPU utilization
- **With batching**: ~500 requests/second, 80-90% GPU utilization

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Trained model stored via control-plane
- `.nexus_meta.json` file in project root

### Run Locally

```bash
# From project root
docker-compose up

# The system will:
# 1. Start Python model server (downloads model from S3)
# 2. Start Go inference proxy
# 3. Ready to accept requests on port 8080
```

### Make Predictions

```bash
curl -X POST http://localhost:8080/predict \
  -H "Content-Type: application/json" \
  -d '{"input": [1, 2, 3, 4, 5]}'
```

## Development Status

🚧 **In Development**

- [ ] Go proxy implementation
- [ ] Python FastAPI server
- [ ] S3 model loader
- [ ] Batch inference logic
- [ ] Performance benchmarking
- [ ] Kubernetes deployment

## Configuration

### Go Proxy

Environment variables:
- `MODEL_SERVER_URL`: Python server address (default: `http://model-server:8000`)
- `BATCH_SIZE`: Maximum batch size (default: `32`)
- `BATCH_TIMEOUT_MS`: Maximum wait time (default: `50`)
- `PORT`: Proxy listen port (default: `8080`)

### Python Server

Environment variables:
- `AWS_ACCESS_KEY_ID`: AWS credentials
- `AWS_SECRET_ACCESS_KEY`: AWS credentials
- `MODEL_BUCKET`: S3 bucket name
- `PORT`: Server listen port (default: `8000`)
- `DEVICE`: Inference device (`cuda` or `cpu`, default: auto-detect)

## See Also

- [Architecture Documentation](../docs/ARCHITECTURE.md)
- [Control Plane](../control-plane/README.md)
- [Main README](../README.md)
