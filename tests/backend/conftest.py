import pytest
from fastapi.testclient import TestClient

from mv_hofki.api.app import app


@pytest.fixture
def client():
    return TestClient(app)
