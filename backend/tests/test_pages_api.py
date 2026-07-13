from datetime import date, timedelta
from contextlib import contextmanager

from app.dependencies import get_graph_client
from test_auth import build_client


class FakeGraphClient:
    def get_page_identity(self, page_id: str):
        return {
            "id": page_id,
            "name": "HTV Test",
            "category": "TV Channel",
            "link": f"https://facebook.com/{page_id}",
        }


@contextmanager
def authenticated_client():
    with build_client() as client:
        client.app.dependency_overrides[get_graph_client] = lambda: FakeGraphClient()
        login = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "correct horse battery staple"},
        )
        yield client, login.json()["csrf_token"]


def test_create_page_validates_and_enqueues_90_day_backfill():
    with authenticated_client() as (client, csrf):
        response = client.post(
            "/api/pages",
            headers={"X-CSRF-Token": csrf},
            json={"page_id": "1125132200689307"},
        )

        assert response.status_code == 201
        body = response.json()
        assert body["display_name"] == "HTV Test"
        assert date.fromisoformat(body["initial_job"]["end_date"]) == date.today()
        assert date.fromisoformat(body["initial_job"]["start_date"]) == date.today() - timedelta(days=89)


def test_disable_page_is_soft_delete():
    with authenticated_client() as (client, csrf):
        created = client.post(
            "/api/pages",
            headers={"X-CSRF-Token": csrf},
            json={
                "page_id": "1125132200689307",
                "backfill_start": "2026-07-01",
                "backfill_end": "2026-07-02",
            },
        ).json()
        response = client.patch(
            f"/api/pages/{created['id']}",
            headers={"X-CSRF-Token": csrf},
            json={"enabled": False},
        )

        assert response.status_code == 200
        assert response.json()["enabled"] is False
        assert len(client.get("/api/pages").json()) == 1
