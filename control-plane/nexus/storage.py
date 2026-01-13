"""Cloud storage abstraction layer for S3 and GCS."""

import os
from pathlib import Path
from typing import BinaryIO, Optional
from abc import ABC, abstractmethod

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from google.cloud import storage as gcs_storage
from google.cloud.exceptions import GoogleCloudError

from .config import CloudProvider, Config


class StorageBackend(ABC):
    """Abstract base class for storage backends."""
    
    @abstractmethod
    def upload(self, local_path: Path, storage_uri: str) -> None:
        """Upload a file to cloud storage."""
        pass
    
    @abstractmethod
    def download(self, storage_uri: str, local_path: Path) -> None:
        """Download a file from cloud storage."""
        pass
    
    @abstractmethod
    def exists(self, storage_uri: str) -> bool:
        """Check if a file exists in cloud storage."""
        pass


class S3StorageBackend(StorageBackend):
    """S3 storage backend implementation."""
    
    def __init__(self, bucket_name: str):
        """
        Initialize S3 storage backend.
        
        Args:
            bucket_name: Name of the S3 bucket.
        """
        self.bucket_name = bucket_name
        try:
            self.s3_client = boto3.client('s3')
        except NoCredentialsError:
            raise RuntimeError(
                "Failed to connect to S3 bucket: Authentication Failure.\n"
                "Action: Please ensure your AWS credentials (AWS Access Key / AWS Secret Key) "
                "are configured correctly and have read/write access to the bucket."
            )
    
    def upload(self, local_path: Path, storage_uri: str) -> None:
        """Upload a file to S3."""
        try:
            self.s3_client.upload_file(
                str(local_path),
                self.bucket_name,
                storage_uri
            )
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            if error_code == 'NoCredentialsError':
                raise RuntimeError(
                    f"Failed to connect to S3 bucket: {self.bucket_name}.\n"
                    f"Reason: Authentication Failure.\n"
                    f"Action: Please ensure your cloud credentials (AWS Access Key / AWS Secret Key) "
                    f"are configured correctly and have read/write access to the bucket."
                )
            elif error_code == 'NoSuchBucket':
                raise RuntimeError(
                    f"Failed to connect to S3 bucket: {self.bucket_name}.\n"
                    f"Reason: Bucket not found.\n"
                    f"Action: Please ensure the bucket exists and you have access to it."
                )
            else:
                raise RuntimeError(
                    f"Failed to upload to S3 bucket: {self.bucket_name}.\n"
                    f"Reason: {error_code}.\n"
                    f"Error: {str(e)}"
                )
    
    def download(self, storage_uri: str, local_path: Path) -> None:
        """Download a file from S3."""
        try:
            # Ensure parent directory exists
            local_path.parent.mkdir(parents=True, exist_ok=True)
            self.s3_client.download_file(
                self.bucket_name,
                storage_uri,
                str(local_path)
            )
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            if error_code == 'NoSuchKey':
                raise RuntimeError(
                    f"Model artifact not found in S3 bucket: {self.bucket_name}.\n"
                    f"Storage URI: {storage_uri}\n"
                    f"Action: Please verify the commit hash and model name."
                )
            elif error_code == 'NoCredentialsError':
                raise RuntimeError(
                    f"Failed to connect to S3 bucket: {self.bucket_name}.\n"
                    f"Reason: Authentication Failure.\n"
                    f"Action: Please ensure your cloud credentials (AWS Access Key / AWS Secret Key) "
                    f"are configured correctly and have read/write access to the bucket."
                )
            else:
                raise RuntimeError(
                    f"Failed to download from S3 bucket: {self.bucket_name}.\n"
                    f"Reason: {error_code}.\n"
                    f"Error: {str(e)}"
                )
    
    def exists(self, storage_uri: str) -> bool:
        """Check if a file exists in S3."""
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=storage_uri)
            return True
        except ClientError as e:
            if e.response.get('Error', {}).get('Code') == '404':
                return False
            raise


class GCSStorageBackend(StorageBackend):
    """Google Cloud Storage backend implementation."""
    
    def __init__(self, bucket_name: str):
        """
        Initialize GCS storage backend.
        
        Args:
            bucket_name: Name of the GCS bucket.
        """
        self.bucket_name = bucket_name
        try:
            self.gcs_client = gcs_storage.Client()
            self.bucket = self.gcs_client.bucket(bucket_name)
        except Exception as e:
            if "credentials" in str(e).lower() or "authentication" in str(e).lower():
                raise RuntimeError(
                    "Failed to connect to GCS bucket: Authentication Failure.\n"
                    "Action: Please ensure your GCP credentials (Service Account Key) "
                    "are configured correctly and have read/write access to the bucket."
                )
            raise RuntimeError(
                f"Failed to connect to GCS bucket: {self.bucket_name}.\n"
                f"Reason: {str(e)}\n"
                f"Action: Please ensure your cloud credentials (GCP Service Account) "
                f"are configured correctly and have read/write access to the bucket."
            )
    
    def upload(self, local_path: Path, storage_uri: str) -> None:
        """Upload a file to GCS."""
        try:
            blob = self.bucket.blob(storage_uri)
            blob.upload_from_filename(str(local_path))
        except GoogleCloudError as e:
            raise RuntimeError(
                f"Failed to upload to GCS bucket: {self.bucket_name}.\n"
                f"Reason: {str(e)}\n"
                f"Action: Please ensure your cloud credentials (GCP Service Account) "
                f"are configured correctly and have read/write access to the bucket."
            )
    
    def download(self, storage_uri: str, local_path: Path) -> None:
        """Download a file from GCS."""
        try:
            # Ensure parent directory exists
            local_path.parent.mkdir(parents=True, exist_ok=True)
            blob = self.bucket.blob(storage_uri)
            if not blob.exists():
                raise RuntimeError(
                    f"Model artifact not found in GCS bucket: {self.bucket_name}.\n"
                    f"Storage URI: {storage_uri}\n"
                    f"Action: Please verify the commit hash and model name."
                )
            blob.download_to_filename(str(local_path))
        except GoogleCloudError as e:
            raise RuntimeError(
                f"Failed to download from GCS bucket: {self.bucket_name}.\n"
                f"Reason: {str(e)}\n"
                f"Action: Please ensure your cloud credentials (GCP Service Account) "
                f"are configured correctly and have read/write access to the bucket."
            )
    
    def exists(self, storage_uri: str) -> bool:
        """Check if a file exists in GCS."""
        try:
            blob = self.bucket.blob(storage_uri)
            return blob.exists()
        except GoogleCloudError:
            return False


def get_storage_backend(config: Config) -> StorageBackend:
    """
    Factory function to get the appropriate storage backend.
    
    Args:
        config: Configuration object.
        
    Returns:
        Storage backend instance.
    """
    provider = config.provider
    bucket_name = config.bucket_name
    
    if provider == CloudProvider.S3:
        return S3StorageBackend(bucket_name)
    elif provider == CloudProvider.GCS:
        return GCSStorageBackend(bucket_name)
    else:
        raise ValueError(f"Unsupported provider: {provider}")
