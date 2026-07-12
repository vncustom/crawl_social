import os
import sys
from pathlib import Path

import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ.update(
    {
        "DATABASE_URL": "sqlite+pysqlite:///:memory:",
        "FB_PAGE_ACCESS_TOKEN": "test-page-token",
        "APP_SECRET_KEY": "test-secret-at-least-32-characters",
    }
)


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import create_app

    with TestClient(create_app()) as value:
        yield value
