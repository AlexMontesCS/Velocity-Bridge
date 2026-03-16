"""Shared test fixtures for Velocity Bridge backend tests."""
import pytest
from fastapi.testclient import TestClient

# Import the FastAPI app
from server import app


@pytest.fixture
def client():
    """Provide a test client for the FastAPI app."""
    return TestClient(app)
