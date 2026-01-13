# NexusML Data Plane - Python Model Server
# FastAPI-based batch inference server

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY *.py ./

# Create models directory
RUN mkdir -p /app/models

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=10s --timeout=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Run the server
CMD ["python", "server.py"]
