"""
Tests for model loading utilities
"""

import pickle
import tempfile

import numpy as np
import pytest

from model_loader import ModelLoader, PickleModel


class SimpleModel:
    """Simple model for testing"""

    def predict(self, inputs):
        return np.array(inputs) * 2


class CallableModel:
    """Callable model for testing"""

    def __call__(self, x):
        return sum(x) if hasattr(x, "__iter__") else x * 2


@pytest.fixture
def pickle_model_file():
    """Create temporary pickle file with simple model"""
    with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
        pickle.dump(SimpleModel(), f)
        return f.name


@pytest.fixture
def callable_model_file():
    """Create temporary pickle file with callable model"""
    with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
        pickle.dump(CallableModel(), f)
        return f.name


class TestPickleModel:
    """Tests for PickleModel wrapper"""

    def test_predict_with_sklearn_style_model(self, pickle_model_file):
        """Should work with sklearn-style models"""
        loader = ModelLoader()
        model = loader.load_from_path(pickle_model_file)

        assert isinstance(model, PickleModel)
        results = model.predict([[1, 2, 3], [4, 5, 6]])
        assert results == [[2, 4, 6], [8, 10, 12]]

    def test_predict_single(self, pickle_model_file):
        """Single prediction should work"""
        loader = ModelLoader()
        model = loader.load_from_path(pickle_model_file)

        result = model.predict_single([1, 2, 3])
        assert result == [2, 4, 6]

    def test_callable_model(self, callable_model_file):
        """Should work with callable models"""
        loader = ModelLoader()
        model = loader.load_from_path(callable_model_file)

        results = model.predict([[1, 2], [3, 4]])
        assert results == [3, 7]  # sum of each input


class TestModelLoader:
    """Tests for ModelLoader"""

    def test_load_from_path(self, pickle_model_file):
        """Should load model from local path"""
        loader = ModelLoader()
        model = loader.load_from_path(pickle_model_file)
        assert model is not None

    def test_load_nonexistent_file(self):
        """Should raise error for missing file"""
        loader = ModelLoader()
        with pytest.raises(FileNotFoundError):
            loader.load_from_path("/nonexistent/path/model.pkl")

    def test_load_with_provider(self, pickle_model_file):
        """Should load using provider-based method"""
        loader = ModelLoader(provider="local")
        model = loader.load(pickle_model_file)
        assert model is not None

    def test_invalid_provider(self):
        """Should raise error for unknown provider"""
        loader = ModelLoader(provider="invalid")
        with pytest.raises(ValueError, match="Unknown provider"):
            loader.load("some/path")


class TestS3Loading:
    """Tests for S3 model loading (requires credentials)"""

    @pytest.fixture
    def s3_loader(self):
        """Create loader with S3 config"""
        import os

        bucket = os.environ.get("TEST_BUCKET")
        if not bucket:
            pytest.skip("TEST_BUCKET not set")

        return ModelLoader(provider="s3", s3_bucket=bucket)

    def test_s3_bucket_not_configured(self):
        """Should raise error when S3 bucket not set"""
        loader = ModelLoader(provider="s3", s3_bucket=None)
        with pytest.raises(ValueError, match="S3 bucket not configured"):
            loader.load_from_s3("some/key")


class TestGCSLoading:
    """Tests for GCS model loading (requires credentials)"""

    def test_gcs_bucket_not_configured(self):
        """Should raise error when GCS bucket not set"""
        loader = ModelLoader(provider="gcs", gcs_bucket=None)
        with pytest.raises(ValueError, match="GCS bucket not configured"):
            loader.load_from_gcs("some/key")
