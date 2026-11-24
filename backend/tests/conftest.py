import os
import tempfile
from pathlib import Path

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient

from alembic import command

# Configure before importing the app. Tests never open the developer database.
area = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
os.environ.update(
    V2_DATABASE_PATH=str(Path(area.name) / "tests.db"),
    APP_ENV="test",
    FRONTEND_URL="http://localhost:5173",
    ALLOW_SIGNUP="true",
    COOKIE_SECURE="false",
    PUBLIC_BASE_URL="https://tracking.example.org",
)
from app.db import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def clean_database():
    command.upgrade(
        Config(str(Path(__file__).resolve().parents[1] / "alembic.ini")), "head"
    )
    yield
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())


@pytest.fixture
def clients():
    def create(name):
        client = TestClient(app)
        r = client.post(
            "/api/signup",
            json={
                "email": name + "@example.org",
                "name": name,
                "password": "a long test password",
            },
        )
        assert r.status_code == 201, r.text
        client.headers["X-CSRF-Token"] = r.json()["csrf"]
        return client

    return create("alice"), create("bob")
