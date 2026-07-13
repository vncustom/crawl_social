from datetime import UTC, datetime

import httpx
import pytest

from app.graph.client import GraphAPIError, GraphClient
from app.graph.metrics import METRICS


START = datetime(2026, 7, 1, tzinfo=UTC)
END = datetime(2026, 7, 2, tzinfo=UTC)


def test_iter_posts_follows_next_page():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(
                200,
                json={
                    "data": [{"id": "1"}],
                    "paging": {"next": "https://graph.facebook.com/next?cursor=x"},
                },
            )
        return httpx.Response(200, json={"data": [{"id": "2"}]})

    client = GraphClient("SECRET", "v25.0", transport=httpx.MockTransport(handler))

    assert [item["id"] for item in client.iter_posts("PAGE", START, END)] == ["1", "2"]
    assert "access_token=SECRET" in str(requests[0].url)
    assert str(requests[1].url) == "https://graph.facebook.com/next?cursor=x"


def test_graph_error_classifies_and_redacts_token():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={"error": {"code": 190, "message": "Token SECRET has expired"}},
        )

    client = GraphClient("SECRET", "v25.0", transport=httpx.MockTransport(handler))

    with pytest.raises(GraphAPIError) as caught:
        client.get_page_identity("PAGE")

    assert caught.value.kind == "authentication"
    assert "SECRET" not in str(caught.value)


def test_metric_registry_preserves_semantics():
    assert METRICS["daily_new_followers"].candidates[0] == "page_daily_follows_unique"
    assert METRICS["followers_total"].additive is False
    assert METRICS["post_engagements"].unit == "interactions"
