# NexusML Control Plane

The control plane handles **model versioning and storage** - linking model artifacts to Git commits and managing cloud storage.

## Quick Start

### Installation

```bash
cd control-plane
pip install -e .
```

### Configuration

Create a `.nexusrc` file in your project root:

```yaml
provider: s3
bucket: your-bucket-name
```

### Basic Usage

```bash
# Store a model (links to current Git commit)
nexus store ./models/my_model.pt my_model

# List all stored models
nexus list

# Load a specific version
nexus load abc123def ./models/restored.pt

# Load the latest version
nexus load latest ./models/latest.pt --model-name my_model

# Rollback to a previous version
nexus rollback abc123def my_model
```

## How It Works

1. **Store**: Gets current Git commit hash, uploads model to S3/GCS, creates metadata entry
2. **Load**: Looks up model by commit hash or "latest", downloads from cloud storage
3. **List**: Shows all stored models with metadata
4. **Rollback**: Sets a previous version as the "latest"

## Docker Usage

```bash
# Build the image
docker build -t nexusml-control:latest .

# Use with docker-compose (from project root)
docker-compose run --rm nexus store ./models/model.pt my_model
```

## Configuration File

The `.nexusrc` file supports:

```yaml
# Required
provider: s3  # or 'gcs'
bucket: my-models-bucket

# Optional (uses environment variables by default)
# AWS credentials - set via AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY
# GCP credentials - set via GOOGLE_APPLICATION_CREDENTIALS
```

## Metadata File

Models are tracked in `.nexus_meta.json`:

```json
{
  "models": [
    {
      "commit_hash": "abc123def",
      "model_name": "my_model",
      "storage_uri": "my_model/abc123def.pt",
      "file_size": 524288000,
      "timestamp": "2024-01-15T10:30:00",
      "is_latest": true
    }
  ]
}
```

**Important**: Commit this file to Git after storing models!

## See Also

- [Docker Documentation](../docs/DOCKER.md)
- [Full Documentation](../README.md)
