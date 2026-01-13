# NexusML Architecture

This document describes the system design and data flow of NexusML.

## System Overview

NexusML is a two-plane architecture:
- **Control Plane**: Model versioning and storage management
- **Data Plane**: High-performance inference serving

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                           NexusML System                             │
└─────────────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────────┐
│                        CONTROL PLANE                               │
│                   (Model Versioning & Storage)                     │
└───────────────────────────────────────────────────────────────────┘

    Developer Laptop
    ┌──────────────────┐
    │  nexus CLI       │
    │  - store         │
    │  - load          │
    │  - list          │
    │  - rollback      │
    └────────┬─────────┘
             │
             ├─────────────┐
             │             │
             ▼             ▼
    ┌──────────────┐  ┌──────────────┐
    │  Git Repo    │  │  AWS S3 /    │
    │  .nexus_meta │  │  Google GCS  │
    │  .json       │  │              │
    └──────────────┘  └──────────────┘
         Metadata         Model Binaries
         (KB)             (GB)


┌───────────────────────────────────────────────────────────────────┐
│                         DATA PLANE                                 │
│                  (High-Performance Inference)                      │
└───────────────────────────────────────────────────────────────────┘

    Users (100s of requests/second)
            │
            │ HTTP POST /predict
            ▼
    ┌────────────────────────────────┐
    │   Go Inference Proxy           │
    │   (Port 8080)                  │
    │                                │
    │  ┌──────────────────────────┐  │
    │  │  Request Queue           │  │
    │  │  [req1, req2, ... req32] │  │
    │  └──────────────────────────┘  │
    │                                │
    │  Batching Logic:               │
    │  - Max 32 requests             │
    │  - Max 50ms wait               │
    │  - Whichever comes first       │
    └───────────┬────────────────────┘
                │
                │ HTTP POST /predict/batch
                │ [batch of 32 requests]
                ▼
    ┌────────────────────────────────┐
    │  Python Model Server           │
    │  (FastAPI on Port 8000)        │
    │                                │
    │  On Startup:                   │
    │  1. Read .nexus_meta.json      │
    │  2. Download model from S3     │
    │  3. Load into GPU memory       │
    │                                │
    │  On Request:                   │
    │  1. Receive batch              │
    │  2. Convert to tensors         │
    │  3. Run inference              │
    │  4. Return predictions         │
    └───────────┬────────────────────┘
                │
                ▼
    ┌────────────────────────────────┐
    │  GPU / CPU                     │
    │  PyTorch / TensorFlow Model    │
    │  Processes 32 items at once    │
    └────────────────────────────────┘
```

## Component Details

### Control Plane Components

#### 1. Nexus CLI (`nexus`)
- **Language**: Python
- **Framework**: Typer + Rich
- **Purpose**: User-facing command-line interface
- **Key Modules**:
  - `cli.py`: Command definitions (store, load, list, rollback)
  - `git_utils.py`: Git operations (get commit hash, check repo status)
  - `storage.py`: Cloud storage abstraction (S3, GCS)
  - `metadata.py`: Metadata file management
  - `config.py`: Configuration loading (.nexusrc)

#### 2. Git Repository
- **Purpose**: Version control for code and metadata
- **Tracked Files**:
  - `.nexus_meta.json`: Model metadata (commit hashes, storage URIs)
  - `.nexusrc`: Configuration (bucket name, provider)
  - Source code and training scripts
- **Not Tracked**: Model binaries (too large)

#### 3. Cloud Storage (S3 / GCS)
- **Purpose**: Off-site storage for large model binaries
- **Storage Structure**:
  ```
  my-models-bucket/
  ├── model_a/
  │   ├── abc123.pt
  │   ├── def456.pt
  │   └── ghi789.pt
  └── model_b/
      └── xyz999.pt
  ```

### Data Plane Components

#### 1. Go Inference Proxy
- **Language**: Go (Golang)
- **Port**: 8080 (public-facing)
- **Purpose**: Request batching and load balancing
- **Key Features**:
  - Concurrent request handling via goroutines
  - Adaptive batching (time-based or size-based)
  - Request/response routing
  - Health checks

**Key Modules** (to be implemented):
```
proxy/
├── cmd/server/main.go           # Entry point
├── internal/
│   ├── batcher/
│   │   └── batcher.go          # Batching logic
│   ├── router/
│   │   └── router.go           # HTTP routing
│   └── client/
│       └── model_client.go     # Python server client
└── config/
    └── config.go               # Configuration
```

#### 2. Python Model Server
- **Language**: Python
- **Framework**: FastAPI
- **Port**: 8000 (internal only)
- **Purpose**: Model loading and batch inference
- **Key Features**:
  - Loads latest model from S3 on startup
  - Accepts batched requests
  - Vectorized inference
  - GPU optimization

**Key Modules** (to be implemented):
```
model-server/
├── server.py        # FastAPI app
├── loader.py        # Model loading from S3
├── inference.py     # Batch inference logic
└── config.py        # Server configuration
```

## Data Flow

### Workflow 1: Store a Model (Control Plane)

```
1. Developer trains model → creates my_model.pt (500MB)

2. Developer runs: nexus store my_model.pt prod_model

3. Nexus CLI:
   a. Checks git status (must be clean)
   b. Gets current commit hash (e.g., "abc123")
   c. Uploads to S3: prod_model/abc123.pt
   d. Updates .nexus_meta.json:
      {
        "commit_hash": "abc123",
        "model_name": "prod_model",
        "storage_uri": "prod_model/abc123.pt",
        "is_latest": true
      }

4. Developer commits metadata:
   git add .nexus_meta.json
   git commit -m "Add prod_model v1"
   git push
```

### Workflow 2: Serve a Model (Data Plane)

```
1. Start services: docker-compose up

2. Python Model Server starts:
   a. Reads .nexus_meta.json
   b. Finds latest model: prod_model/abc123.pt
   c. Downloads from S3 (500MB)
   d. Loads into GPU memory
   e. Starts FastAPI server on port 8000

3. Go Proxy starts:
   a. Connects to Python server
   b. Starts HTTP server on port 8080
   c. Ready to accept requests

4. User makes prediction request:
   POST http://localhost:8080/predict
   {"image": "base64_data..."}

5. Go Proxy:
   a. Receives request at 10:00:00.000
   b. Adds to queue (queue size: 1)
   c. Waits for batch (max 32 requests or 50ms)

6. More requests arrive:
   - 10:00:00.010: Request 2 arrives
   - 10:00:00.020: Request 3 arrives
   - ...
   - 10:00:00.045: Request 30 arrives

7. At 10:00:00.050 (timeout reached):
   a. Go creates batch of 30 requests
   b. Sends to Python: POST /predict/batch

8. Python Model Server:
   a. Receives batch of 30 requests
   b. Converts to tensor (batch_size=30)
   c. Runs GPU inference (single forward pass)
   d. Returns 30 predictions

9. Go Proxy:
   a. Receives 30 predictions
   b. Routes each to original requester
   c. Returns responses to users
```

## Performance Analysis

### Without Batching (Standard API)

```
Timeline:
00ms: Request 1 arrives → Process → 20ms to complete
20ms: Request 2 arrives → Process → 40ms to complete
40ms: Request 3 arrives → Process → 60ms to complete
...

Throughput: 1000ms / 20ms = 50 requests/second
GPU Utilization: 15-25% (GPU idle between requests)
```

### With Batching (NexusML)

```
Timeline:
00ms: Request 1 arrives → Queue
10ms: Request 2 arrives → Queue
20ms: Request 3 arrives → Queue
...
45ms: Request 30 arrives → Queue
50ms: Batch timeout → Send all 30 to GPU
70ms: All 30 complete (single 20ms forward pass)

Throughput: 30 requests / 70ms = ~428 requests/second
GPU Utilization: 80-90% (GPU processes 30 items at once)

Individual Latency:
- Request 1: 70ms (50ms wait + 20ms inference)
- Request 30: 40ms (20ms wait + 20ms inference)
```

## Technology Choices

### Why Go for the Proxy?

1. **Concurrency**: Native goroutines handle 10,000+ concurrent connections
2. **Performance**: Low latency (1-5ms) vs Python (50-100ms)
3. **Single Binary**: Easy deployment, no dependencies
4. **Channel-based**: Perfect for queue management

### Why Python for Model Server?

1. **ML Ecosystem**: PyTorch, TensorFlow, scikit-learn
2. **Easy Integration**: Direct model loading
3. **FastAPI**: Modern, async, auto-docs
4. **Flexibility**: Easy to modify inference logic

### Why Docker Compose?

1. **Multi-service**: Orchestrates Go + Python + MinIO
2. **Networking**: Automatic service discovery
3. **Development**: Same setup for dev and prod
4. **Portability**: Works on any machine

## Scalability

### Horizontal Scaling

```
┌─────────────┐
│   Load      │
│  Balancer   │
└──────┬──────┘
       │
       ├──────────┬──────────┬──────────┐
       │          │          │          │
       ▼          ▼          ▼          ▼
   ┌─────┐    ┌─────┐    ┌─────┐    ┌─────┐
   │Go+Py│    │Go+Py│    │Go+Py│    │Go+Py│
   │Pod 1│    │Pod 2│    │Pod 3│    │Pod 4│
   └─────┘    └─────┘    └─────┘    └─────┘
```

Each pod runs both Go proxy and Python server, scaled via Kubernetes.

### Future Enhancements

- **Model hot-swapping**: Reload models without restart
- **Multi-model serving**: Route to different models
- **Request prioritization**: VIP requests bypass queue
- **Adaptive batch sizing**: Auto-tune based on load
- **Metrics**: Prometheus + Grafana monitoring

## Security Considerations

1. **Credentials**: Never commit to Git, use env vars
2. **S3 Access**: IAM roles with minimal permissions
3. **Internal Network**: Python server not exposed publicly
4. **HTTPS**: TLS termination at load balancer
5. **Rate Limiting**: Prevent abuse at proxy level

## Deployment Targets

- **Development**: Docker Compose (local machine)
- **Staging**: Kubernetes (single cluster)
- **Production**: Kubernetes (multi-region, auto-scaling)
- **Edge**: Single Docker container (embedded devices)
