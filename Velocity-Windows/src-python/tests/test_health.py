"""Test health check and stats endpoints."""


def test_root_endpoint_returns_ok(client):
    """GET / should return status ok."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "Velocity Bridge"


def test_stats_endpoint_returns_counts(client):
    """GET /stats should return session statistics."""
    response = client.get("/stats")
    assert response.status_code == 200
    data = response.json()
    assert "request_count" in data
    assert "unique_ips" in data
