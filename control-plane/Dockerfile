# NexusML Control Plane - Model Versioning CLI
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
# - git: Required for GitPython
# - ca-certificates: For SSL/TLS connections to cloud providers
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    git \
    ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml ./
COPY README.md ./
COPY nexus/ ./nexus/

# Install NexusML and dependencies
RUN pip install --no-cache-dir -e .

# Set the working directory to /workspace
# This is where user projects will be mounted
WORKDIR /workspace

# Set git config to avoid warnings (can be overridden by user)
RUN git config --global user.name "NexusML User" && \
    git config --global user.email "user@nexusml.local"

# Entrypoint is the nexus CLI
ENTRYPOINT ["nexus"]

# Default command shows help
CMD ["--help"]
