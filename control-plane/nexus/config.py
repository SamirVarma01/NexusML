"""Configuration management for NexusML."""

import os
import yaml
from pathlib import Path
from typing import Optional, Dict, Any
from enum import Enum


class CloudProvider(str, Enum):
    """Supported cloud storage providers."""
    S3 = "s3"
    GCS = "gcs"


class Config:
    """Configuration manager for NexusML."""
    
    CONFIG_FILE = ".nexusrc"
    
    def __init__(self, project_root: Optional[Path] = None):
        """
        Initialize configuration.
        
        Args:
            project_root: Root directory of the project. If None, uses current directory.
        """
        if project_root is None:
            project_root = Path.cwd()
        self.project_root = Path(project_root).resolve()
        self.config_file = self.project_root / self.CONFIG_FILE
        self._config: Dict[str, Any] = {}
        self._load_config()
    
    def _load_config(self) -> None:
        """Load configuration from .modelvaultrc file."""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    self._config = yaml.safe_load(f) or {}
            except Exception as e:
                raise ValueError(f"Failed to parse configuration file: {e}")
    
    @property
    def provider(self) -> CloudProvider:
        """Get the cloud provider."""
        provider_str = self._config.get("provider", "s3").lower()
        try:
            return CloudProvider(provider_str)
        except ValueError:
            raise ValueError(
                f"Invalid provider '{provider_str}'. "
                f"Supported providers: {', '.join([p.value for p in CloudProvider])}"
            )
    
    @property
    def bucket_name(self) -> str:
        """Get the bucket name."""
        bucket = self._config.get("bucket")
        if not bucket:
            raise ValueError(
                "Bucket name not configured. "
                "Please set 'bucket' in .modelvaultrc file."
            )
        return bucket
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        return self._config.get(key, default)
