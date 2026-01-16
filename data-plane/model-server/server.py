"""
NexusML Model Server - FastAPI batch inference server
Loads models from S3 and runs batch predictions
"""

import json
import os
import traceback
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from config import Config
from model_loader import BaseModel as MLModel, ModelLoader


# Global state
model: Optional[MLModel] = None
config: Optional[Config] = None


class SingleRequest(BaseModel):
    id: str
    data: Any  # Flexible input format


class BatchRequest(BaseModel):
    requests: List[SingleRequest]


class SingleResponse(BaseModel):
    id: str
    result: Optional[Any] = None
    error: Optional[str] = None


class BatchResponse(BaseModel):
    responses: List[SingleResponse]


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    model_name: Optional[str] = None
    model_version: Optional[str] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic"""
    global model, config

    print("Starting NexusML Model Server...")
    config = Config.from_env()

    try:
        loader = ModelLoader(
            provider=config.provider,
            s3_bucket=config.s3_bucket,
            gcs_bucket=config.gcs_bucket,
            aws_region=config.aws_region,
        )

        if config.model_path:
            print(f"Loading model from local path: {config.model_path}")
            model = loader.load_from_path(config.model_path)
        elif config.get_bucket() and config.model_name:
            storage_key = f"{config.model_name}/{config.model_version}.pkl"
            bucket = config.get_bucket()
            prefix = "s3" if config.provider == "s3" else "gs"
            print(f"Loading model from {prefix}://{bucket}/{storage_key}")
            model = loader.load(storage_key)
        else:
            print("WARNING: No model configured. Server will start without model.")
            print("Set MODEL_PATH or (S3_BUCKET/GCS_BUCKET + MODEL_NAME + PROVIDER) to load a model.")

        if model:
            print("Model loaded successfully!")

    except Exception as e:
        print(f"ERROR loading model: {e}")
        traceback.print_exc()

    yield

    # Shutdown
    print("Shutting down NexusML Model Server...")


app = FastAPI(
    title="NexusML Model Server",
    description="High-performance batch inference server",
    version="0.2.0",
    lifespan=lifespan
)


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy" if model else "degraded",
        model_loaded=model is not None,
        model_name=config.model_name if config else None,
        model_version=config.model_version if config else None,
    )


@app.get("/ready")
async def ready():
    """K8s readiness probe"""
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    return {"status": "ready"}


@app.post("/predict/batch", response_model=BatchResponse)
async def predict_batch(batch: BatchRequest):
    """
    Batch inference endpoint - matches Go proxy format

    Request format:
    {
        "requests": [
            {"id": "uuid-1", "data": [1.0, 2.0, 3.0]},
            {"id": "uuid-2", "data": [4.0, 5.0, 6.0]}
        ]
    }

    Response format:
    {
        "responses": [
            {"id": "uuid-1", "result": 0.95},
            {"id": "uuid-2", "result": 0.87}
        ]
    }
    """
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    responses = []
    ids = [req.id for req in batch.requests]
    inputs = [req.data for req in batch.requests]

    try:
        results = model.predict(inputs)
        for req_id, result in zip(ids, results):
            responses.append(SingleResponse(id=req_id, result=result))

    except Exception as e:
        error_msg = str(e)
        for req_id in ids:
            responses.append(SingleResponse(id=req_id, error=error_msg))

    return BatchResponse(responses=responses)


@app.post("/predict")
async def predict_single(request: Dict[str, Any]):
    """
    Single prediction endpoint (for testing/debugging)

    Request: {"data": [1.0, 2.0, 3.0]}
    Response: {"result": 0.95}
    """
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    try:
        data = request.get("data")
        if data is None:
            raise HTTPException(status_code=400, detail="Missing 'data' field")

        result = model.predict_single(data)
        return {"result": result}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/info")
async def info():
    return {
        "server": "NexusML Model Server",
        "version": "0.2.0",
        "model_loaded": model is not None,
        "config": {
            "model_name": config.model_name if config else None,
            "model_version": config.model_version if config else None,
            "max_batch_size": config.max_batch_size if config else None,
        }
    }


if __name__ == "__main__":
    cfg = Config.from_env()
    uvicorn.run(
        "server:app",
        host=cfg.host,
        port=cfg.port,
        log_level=cfg.log_level.lower(),
    )
