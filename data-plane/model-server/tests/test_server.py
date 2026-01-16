"""
Tests for NexusML Model Server
"""

import pickle
import tempfile
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


class MockModel:
    """Mock sklearn-style model for testing"""

    def predict(self, inputs):
        # Simple mock: return sum of each input
        return [sum(x) if hasattr(x, "__iter__") else x for x in inputs]


@pytest.fixture
def mock_model_file():
    """Create a temporary pickle file with a mock model"""
    with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
        pickle.dump(MockModel(), f)
        return f.name


@pytest.fixture
def client(mock_model_file):
    """Create test client with mock model loaded"""
    # Set environment to use local model
    with patch.dict(
        "os.environ",
        {
            "MODEL_PATH": mock_model_file,
            "PROVIDER": "local",
        },
    ):
        # Import here to pick up patched env
        from server import app

        with TestClient(app) as client:
            yield client


class TestHealthEndpoint:
    """Tests for /health endpoint"""

    def test_health_with_model(self, client):
        """Health check should return healthy when model is loaded"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["model_loaded"] is True

    def test_health_response_format(self, client):
        """Health response should have expected fields"""
        response = client.get("/health")
        data = response.json()
        assert "status" in data
        assert "model_loaded" in data


class TestReadyEndpoint:
    """Tests for /ready endpoint"""

    def test_ready_with_model(self, client):
        """Ready check should succeed when model is loaded"""
        response = client.get("/ready")
        assert response.status_code == 200
        assert response.json()["status"] == "ready"


class TestPredictEndpoint:
    """Tests for /predict endpoint"""

    def test_single_prediction(self, client):
        """Single prediction should work"""
        response = client.post("/predict", json={"data": [1.0, 2.0, 3.0]})
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert data["result"] == 6.0  # sum of [1, 2, 3]

    def test_prediction_missing_data(self, client):
        """Should return error when data field is missing"""
        response = client.post("/predict", json={})
        assert response.status_code == 400


class TestBatchPredictEndpoint:
    """Tests for /predict/batch endpoint"""

    def test_batch_prediction(self, client):
        """Batch prediction should process multiple requests"""
        response = client.post(
            "/predict/batch",
            json={
                "requests": [
                    {"id": "req-1", "data": [1.0, 2.0, 3.0]},
                    {"id": "req-2", "data": [4.0, 5.0, 6.0]},
                ]
            },
        )
        assert response.status_code == 200
        data = response.json()

        assert "responses" in data
        assert len(data["responses"]) == 2

        # Check responses are properly mapped by ID
        responses = {r["id"]: r for r in data["responses"]}
        assert responses["req-1"]["result"] == 6.0
        assert responses["req-2"]["result"] == 15.0

    def test_batch_preserves_ids(self, client):
        """Batch responses should preserve request IDs"""
        response = client.post(
            "/predict/batch",
            json={
                "requests": [
                    {"id": "uuid-abc-123", "data": [1.0]},
                    {"id": "uuid-def-456", "data": [2.0]},
                ]
            },
        )
        data = response.json()
        ids = [r["id"] for r in data["responses"]]
        assert "uuid-abc-123" in ids
        assert "uuid-def-456" in ids

    def test_empty_batch(self, client):
        """Empty batch should return empty responses"""
        response = client.post("/predict/batch", json={"requests": []})
        assert response.status_code == 200
        data = response.json()
        assert data["responses"] == []


class TestInfoEndpoint:
    """Tests for /info endpoint"""

    def test_info_response(self, client):
        """Info endpoint should return server information"""
        response = client.get("/info")
        assert response.status_code == 200
        data = response.json()
        assert data["server"] == "NexusML Model Server"
        assert "version" in data
        assert data["model_loaded"] is True
