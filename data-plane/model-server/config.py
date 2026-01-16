"""
Configuration management for NexusML Model Server
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class Config:
    """Server configuration loaded from environment variables"""

    # Server settings
    port: int = 8000
    host: str = "0.0.0.0"
    log_level: str = "info"

    # Model settings
    model_path: Optional[str] = None  # Local path to model file
    model_name: Optional[str] = None  # Model name in NexusML
    model_version: str = "latest"     # Version to load (commit hash or "latest")
    provider: str = "local"

    # S3 settings
    s3_bucket: Optional[str] = None
    aws_region: str = "us-east-1"

    # GCS settings
    gcs_bucket: Optional[str] = None

    max_batch_size: int = 32

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            port=int(os.getenv("PORT", "8000")),
            host=os.getenv("HOST", "0.0.0.0"),
            log_level=os.getenv("LOG_LEVEL", "info"),
            model_path=os.getenv("MODEL_PATH"),
            model_name=os.getenv("MODEL_NAME"),
            model_version=os.getenv("MODEL_VERSION", "latest"),
            provider=os.getenv("PROVIDER", "local"),
            s3_bucket=os.getenv("S3_BUCKET"),
            aws_region=os.getenv("AWS_REGION", "us-east-1"),
            gcs_bucket=os.getenv("GCS_BUCKET"),
            max_batch_size=int(os.getenv("MAX_BATCH_SIZE", "32")),
        )

    def get_bucket(self) -> Optional[str]:
        if self.provider == "s3":
            return self.s3_bucket
        elif self.provider == "gcs":
            return self.gcs_bucket
        return None

    def validate(self) -> None:
        if not self.model_path:
            bucket = self.get_bucket()
            if not bucket or not self.model_name:
                raise ValueError(
                    "Must set either MODEL_PATH for local model, "
                    "or (S3_BUCKET/GCS_BUCKET + MODEL_NAME + PROVIDER) to load from cloud"
                )
