import pytest

from app import create_app


@pytest.fixture
def client():
    app = create_app("development")
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_index(client):
    response = client.get("/")
    assert response.status_code == 200


def test_intelligence_route_reads_json_store(client):
    response = client.get("/intelligence?severity=Critical")

    assert response.status_code == 200
    assert b"Credential stuffing campaign" in response.data
    assert b"Unusual PowerShell execution" not in response.data


def test_intelligence_route_supports_text_filter(client):
    response = client.get("/intelligence?q=cloud")

    assert response.status_code == 200
    assert b"Exposed S3 bucket detected" in response.data
    assert b"Credential stuffing campaign" not in response.data
