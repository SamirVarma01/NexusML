# Docker Setup for ModelVault

This guide explains how to use ModelVault with Docker for consistent, portable deployment.

## Quick Start

### 1. Build the Docker Image

```bash
docker build -t modelvault:latest .
```

Or using docker-compose:

```bash
docker-compose build
```

### 2. Run ModelVault Commands

**Using docker-compose (recommended):**

```bash
# Store a model
docker-compose run --rm modelvault store ./models/my_model.pkl my_model

# List models
docker-compose run --rm modelvault list

# Load a model
docker-compose run --rm modelvault load abc123def ./models/restored.pkl

# Load latest
docker-compose run --rm modelvault load latest ./models/latest.pkl --model-name my_model

# Rollback
docker-compose run --rm modelvault rollback abc123def my_model
```

**Using docker directly:**

```bash
docker run --rm \
  -v $(pwd):/workspace \
  -v ~/.aws:/root/.aws:ro \
  modelvault:latest store ./models/my_model.pkl my_model
```

## Configuration

### AWS Credentials

**Option 1: Mount AWS credentials directory (recommended)**
```bash
# Already configured in docker-compose.yml
docker-compose run --rm modelvault list
```

**Option 2: Environment variables**
```bash
docker run --rm \
  -v $(pwd):/workspace \
  -e AWS_ACCESS_KEY_ID=your_key \
  -e AWS_SECRET_ACCESS_KEY=your_secret \
  -e AWS_DEFAULT_REGION=us-east-1 \
  modelvault:latest list
```

**Option 3: Create .env file**
```bash
# Create .env file in project root
cat > .env << EOF
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_DEFAULT_REGION=us-east-1
EOF

# docker-compose will automatically load it
docker-compose run --rm modelvault list
```

### Google Cloud Credentials

**Option 1: Mount gcloud config directory**
```bash
# Already configured in docker-compose.yml
docker-compose run --rm modelvault list
```

**Option 2: Mount service account key**
```bash
docker run --rm \
  -v $(pwd):/workspace \
  -v /path/to/service-account.json:/creds/key.json:ro \
  -e GOOGLE_APPLICATION_CREDENTIALS=/creds/key.json \
  modelvault:latest list
```

## Interactive Shell Access

Sometimes you need to debug or run multiple commands:

```bash
# Access bash shell inside container
docker-compose run --rm modelvault-shell

# Inside the container, you can run:
root@container:/workspace# modelvault list
root@container:/workspace# git status
root@container:/workspace# ls -la
root@container:/workspace# exit
```

## Complete Workflow Example

```bash
# 1. Ensure you're in a git repo with .modelvaultrc configured
cd /path/to/your/ml/project

# 2. Create .modelvaultrc
cat > .modelvaultrc << EOF
provider: s3
bucket: my-ml-models-bucket
EOF

# 3. Build the image (one time)
docker-compose build

# 4. Create a test model
mkdir -p models
python -c "import pickle; pickle.dump({'weights': [1,2,3]}, open('models/test.pkl', 'wb'))"

# 5. Ensure git is clean
git add .modelvaultrc
git commit -m "Add ModelVault config"

# 6. Store the model
docker-compose run --rm modelvault store ./models/test.pkl test_model

# 7. Commit the metadata
git add .model_meta.json
git commit -m "Add model metadata"

# 8. List models
docker-compose run --rm modelvault list

# 9. Load the model
docker-compose run --rm modelvault load latest ./models/loaded.pkl --model-name test_model
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Store Model Artifact

on:
  push:
    branches: [main]

jobs:
  store-model:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Build ModelVault image
        run: docker build -t modelvault:latest .

      - name: Store model
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
        run: |
          docker run --rm \
            -v $(pwd):/workspace \
            -e AWS_ACCESS_KEY_ID \
            -e AWS_SECRET_ACCESS_KEY \
            -e AWS_DEFAULT_REGION=us-east-1 \
            modelvault:latest store ./models/trained_model.pkl production_model

      - name: Commit metadata
        run: |
          git config user.name "GitHub Actions"
          git config user.email "actions@github.com"
          git add .model_meta.json
          git commit -m "Update model metadata [skip ci]"
          git push
```

### GitLab CI Example

```yaml
store-model:
  image: docker:latest
  services:
    - docker:dind
  script:
    - docker build -t modelvault:latest .
    - |
      docker run --rm \
        -v $(pwd):/workspace \
        -e AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID \
        -e AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY \
        -e AWS_DEFAULT_REGION=us-east-1 \
        modelvault:latest store ./models/model.pkl my_model
    - git add .model_meta.json
    - git commit -m "Update model metadata"
    - git push
  only:
    - main
```

## Troubleshooting

### Permission Issues

If you encounter permission errors with mounted volumes:

```bash
# Option 1: Run with your user ID
docker run --rm \
  --user $(id -u):$(id -g) \
  -v $(pwd):/workspace \
  -v ~/.aws:/root/.aws:ro \
  modelvault:latest list

# Option 2: Fix ownership after running
sudo chown -R $USER:$USER .
```

### Git Config Warnings

If you see git configuration warnings:

```bash
# Set git config in the container
docker-compose run --rm modelvault-shell
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"
exit
```

### AWS/GCP Credentials Not Found

```bash
# Verify credentials are mounted
docker-compose run --rm modelvault-shell
ls -la /root/.aws/
cat /root/.aws/credentials
exit

# If missing, ensure ~/.aws exists locally
ls -la ~/.aws/
```

### Model Files Not Found

```bash
# Ensure you're running from the correct directory
pwd  # Should be your project root

# Check if files are visible in container
docker-compose run --rm modelvault-shell
ls -la /workspace/models/
exit
```

## Advanced Usage

### Custom Dockerfile for Production

For production, you might want to create a custom Dockerfile:

```dockerfile
FROM modelvault:latest

# Install additional dependencies
RUN pip install mlflow wandb

# Set custom git config
RUN git config --global user.name "Production CI" && \
    git config --global user.email "ci@company.com"

# Add custom scripts
COPY scripts/ /scripts/
```

### Multi-Stage Build for Smaller Images

```dockerfile
# Builder stage
FROM python:3.11-slim as builder
WORKDIR /app
COPY pyproject.toml README.md ./
COPY modelvault/ ./modelvault/
RUN pip install --user -e .

# Runtime stage
FROM python:3.11-slim
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH
WORKDIR /workspace
ENTRYPOINT ["modelvault"]
```

## Best Practices

1. **Always use docker-compose** for local development - it's simpler
2. **Mount credentials as read-only** (`:ro`) for security
3. **Use `.env` file** for sensitive environment variables (add to `.gitignore`)
4. **Run with `--rm` flag** to automatically clean up containers
5. **Use specific image tags** in production instead of `latest`
6. **Keep the image updated** by rebuilding when dependencies change

## Security Notes

- Never commit AWS/GCP credentials to Docker images
- Always mount credential files as read-only volumes
- Use Docker secrets or environment variables for credentials
- Consider using IAM roles when running in AWS (EC2, ECS)
- Use Workload Identity when running in GCP (GKE)
