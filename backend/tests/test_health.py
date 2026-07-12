def test_health(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_token_is_not_exposed(client):
    body = client.get("/openapi.json").text

    assert "test-page-token" not in body
