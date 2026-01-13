"""Metadata management for model artifacts."""

import json
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime


METADATA_FILE = ".nexus_meta.json"


class MetadataManager:
    """Manages model metadata stored in .model_meta.json file."""
    
    def __init__(self, project_root: Optional[Path] = None):
        """
        Initialize metadata manager.
        
        Args:
            project_root: Root directory of the project. If None, uses current directory.
        """
        if project_root is None:
            project_root = Path.cwd()
        self.project_root = Path(project_root).resolve()
        self.metadata_file = self.project_root / METADATA_FILE
        self._metadata: Dict[str, Any] = {}
        self._load_metadata()
    
    def _load_metadata(self) -> None:
        """Load metadata from .model_meta.json file."""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'r') as f:
                    self._metadata = json.load(f)
            except json.JSONDecodeError as e:
                raise ValueError(f"Failed to parse metadata file: {e}")
        else:
            # Initialize empty metadata structure
            self._metadata = {
                "models": {},
                "latest": {}
            }
    
    def ensure_exists(self) -> None:
        """Ensure metadata file exists, raising error if not."""
        if not self.metadata_file.exists():
            raise RuntimeError(
                f"Model metadata file ({METADATA_FILE}) not found in the current directory.\n"
                f"Action: Please ensure you are running ModelVault from the project root directory."
            )
    
    def add_model(
        self,
        commit_hash: str,
        model_name: str,
        storage_uri: str,
        file_size: int,
        file_extension: str
    ) -> None:
        """
        Add a model entry to metadata.
        
        Args:
            commit_hash: Git commit hash.
            model_name: Name of the model.
            storage_uri: Cloud storage URI.
            file_size: Size of the file in bytes.
            file_extension: File extension.
        """
        if "models" not in self._metadata:
            self._metadata["models"] = {}
        
        if model_name not in self._metadata["models"]:
            self._metadata["models"][model_name] = {}
        
        self._metadata["models"][model_name][commit_hash] = {
            "storage_uri": storage_uri,
            "commit_hash": commit_hash,
            "file_size": file_size,
            "file_extension": file_extension,
            "timestamp": datetime.now().isoformat()
        }
        
        # Update latest pointer
        if "latest" not in self._metadata:
            self._metadata["latest"] = {}
        self._metadata["latest"][model_name] = commit_hash
    
    def get_storage_uri(
        self,
        commit_hash: str,
        model_name: Optional[str] = None
    ) -> Optional[str]:
        """
        Get storage URI for a given commit hash.
        
        Args:
            commit_hash: Git commit hash or 'latest'.
            model_name: Name of the model. Required if commit_hash is 'latest'.
            
        Returns:
            Storage URI if found, None otherwise.
        """
        self.ensure_exists()
        
        # Handle 'latest' keyword
        if commit_hash == "latest":
            if model_name is None:
                raise ValueError(
                    "Model name is required when using 'latest' commit hash."
                )
            if "latest" not in self._metadata or model_name not in self._metadata["latest"]:
                return None
            commit_hash = self._metadata["latest"][model_name]
        
        # If model_name is provided, search in that model's entries
        if model_name:
            if (
                model_name in self._metadata.get("models", {}) and
                commit_hash in self._metadata["models"][model_name]
            ):
                return self._metadata["models"][model_name][commit_hash]["storage_uri"]
        else:
            # Search across all models
            for model_entries in self._metadata.get("models", {}).values():
                if commit_hash in model_entries:
                    return model_entries[commit_hash]["storage_uri"]
        
        return None
    
    def get_all_models(self) -> Dict[str, Any]:
        """
        Get all model entries.
        
        Returns:
            Dictionary of all model metadata.
        """
        self.ensure_exists()
        return self._metadata.get("models", {})
    
    def list_models(self) -> list:
        """
        Get a list of all stored models with their metadata.
        
        Returns:
            List of dictionaries containing model information.
        """
        self.ensure_exists()
        models_list = []
        
        for model_name, commits in self._metadata.get("models", {}).items():
            latest_hash = self._metadata.get("latest", {}).get(model_name)
            for commit_hash, metadata in commits.items():
                models_list.append({
                    "model_name": model_name,
                    "commit_hash": commit_hash,
                    "storage_uri": metadata["storage_uri"],
                    "file_size": metadata["file_size"],
                    "timestamp": metadata["timestamp"],
                    "is_latest": commit_hash == latest_hash
                })
        
        return models_list
    
    def save(self) -> None:
        """Save metadata to .model_meta.json file."""
        # Ensure parent directory exists
        self.metadata_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.metadata_file, 'w') as f:
            json.dump(self._metadata, f, indent=2)
    
    def set_latest(self, commit_hash: str, model_name: str) -> None:
        """
        Set a specific commit as the latest for a model.
        
        Args:
            commit_hash: Git commit hash.
            model_name: Name of the model.
        """
        self.ensure_exists()
        
        if model_name not in self._metadata.get("models", {}):
            raise ValueError(f"Model '{model_name}' not found in metadata.")
        
        if commit_hash not in self._metadata["models"][model_name]:
            raise ValueError(
                f"Commit hash '{commit_hash}' not found for model '{model_name}'."
            )
        
        if "latest" not in self._metadata:
            self._metadata["latest"] = {}
        self._metadata["latest"][model_name] = commit_hash
