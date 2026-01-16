"""
Model loading utilities for NexusML Model Server
Supports loading models from local files, S3, or GCS
"""

import os
import pickle
import tempfile
from abc import ABC, abstractmethod
from typing import Any, List, Optional

import numpy as np


class BaseModel(ABC):
    """Abstract base class for model wrappers"""

    @abstractmethod
    def predict(self, inputs: List[Any]) -> List[Any]:
        pass

    @abstractmethod
    def predict_single(self, input_data: Any) -> Any:
        pass


class PickleModel(BaseModel):
    """Wrapper for pickle-serialized models (sklearn, custom, etc.)"""

    def __init__(self, model: Any):
        self.model = model

    def predict(self, inputs: List[Any]) -> List[Any]:
        # Convert inputs to numpy array if they're lists
        if inputs and isinstance(inputs[0], list):
            inputs = np.array(inputs)

        # Check if model has predict method
        if hasattr(self.model, "predict"):
            results = self.model.predict(inputs)
            return results.tolist() if hasattr(results, "tolist") else list(results)
        elif callable(self.model):
            # Model is a callable (function)
            return [self.model(x) for x in inputs]
        else:
            raise ValueError("Model does not have predict method and is not callable")

    def predict_single(self, input_data: Any) -> Any:
        results = self.predict([input_data])
        return results[0]


class TorchModel(BaseModel):
    """Wrapper for PyTorch models"""

    def __init__(self, model: Any):
        import torch
        self.model = model
        self.model.eval()  # Set to evaluation mode
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)

    def predict(self, inputs: List[Any]) -> List[Any]:
        import torch

        with torch.no_grad():
            # Convert to tensor
            if isinstance(inputs, list):
                tensor_input = torch.tensor(inputs, dtype=torch.float32)
            else:
                tensor_input = inputs

            tensor_input = tensor_input.to(self.device)

            # Run inference
            outputs = self.model(tensor_input)

            # Convert back to list
            return outputs.cpu().numpy().tolist()

    def predict_single(self, input_data: Any) -> Any:
        """Single prediction"""
        results = self.predict([input_data])
        return results[0]


class ModelLoader:
    """Loads models from local files, S3, or GCS"""

    def __init__(
        self,
        provider: str = "local",
        s3_bucket: Optional[str] = None,
        gcs_bucket: Optional[str] = None,
        aws_region: str = "us-east-1",
    ):
        self.provider = provider
        self.s3_bucket = s3_bucket
        self.gcs_bucket = gcs_bucket
        self.aws_region = aws_region
        self._s3_client = None
        self._gcs_client = None

    @property
    def s3_client(self):
        if self._s3_client is None:
            import boto3
            self._s3_client = boto3.client("s3", region_name=self.aws_region)
        return self._s3_client

    @property
    def gcs_client(self):
        if self._gcs_client is None:
            from google.cloud import storage
            self._gcs_client = storage.Client()
        return self._gcs_client

    def load_from_path(self, path: str) -> BaseModel:
        if not os.path.exists(path):
            raise FileNotFoundError(f"Model file not found: {path}")

        return self._load_file(path)

    def load_from_s3(self, s3_key: str) -> BaseModel:
        if not self.s3_bucket:
            raise ValueError("S3 bucket not configured")

        # Download to temp file
        suffix = self._get_suffix(s3_key)
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp_path = tmp.name

        try:
            print(f"Downloading model from s3://{self.s3_bucket}/{s3_key}")
            self.s3_client.download_file(self.s3_bucket, s3_key, tmp_path)
            return self._load_file(tmp_path)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def load_from_gcs(self, gcs_key: str) -> BaseModel:
        if not self.gcs_bucket:
            raise ValueError("GCS bucket not configured")

        # Download to temp file
        suffix = self._get_suffix(gcs_key)
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp_path = tmp.name

        try:
            print(f"Downloading model from gs://{self.gcs_bucket}/{gcs_key}")
            bucket = self.gcs_client.bucket(self.gcs_bucket)
            blob = bucket.blob(gcs_key)
            blob.download_to_filename(tmp_path)
            return self._load_file(tmp_path)
        finally:
            # Clean up temp file
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def load(self, key: str) -> BaseModel:
        """Load model based on configured provider"""
        if self.provider == "s3":
            return self.load_from_s3(key)
        elif self.provider == "gcs":
            return self.load_from_gcs(key)
        elif self.provider == "local":
            return self.load_from_path(key)
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    def _load_file(self, path: str) -> BaseModel:
        """Load model from file based on extension"""
        ext = os.path.splitext(path)[1].lower()

        if ext in (".pkl", ".pickle"):
            return self._load_pickle(path)
        elif ext in (".pt", ".pth"):
            return self._load_torch(path)
        else:
            # Try pickle as default
            return self._load_pickle(path)

    def _load_pickle(self, path: str) -> PickleModel:
        """Load pickle model"""
        with open(path, "rb") as f:
            model = pickle.load(f)
        return PickleModel(model)

    def _load_torch(self, path: str) -> TorchModel:
        """Load PyTorch model"""
        import torch
        model = torch.load(path, map_location="cpu")
        return TorchModel(model)

    def _get_suffix(self, key: str) -> str:
        """Get file suffix from key"""
        ext = os.path.splitext(key)[1]
        return ext if ext else ".pkl"
