"""Fixtures for API tests: the real app, a real database, and a helper that sets the test clock."""

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.builders import NOW

DAY = timedelta(days=1)
LOAN_PERIOD = timedelta(days=7)


class Api:
    """Thin wrapper over the test client. Every call runs at `at` (default NOW) via X-Test-Clock;
    pass `at=None` to send no header and use the real clock."""

    def __init__(self, client: TestClient):
        self.client = client

    def call(self, method: str, url: str, *, at: datetime | None = NOW, headers=None, **kwargs):
        headers = dict(headers or {})
        if at is not None:
            headers["X-Test-Clock"] = at.isoformat()
        return self.client.request(method, url, headers=headers, **kwargs)

    def get(self, url, **kwargs):
        return self.call("GET", url, **kwargs)

    def post(self, url, **kwargs):
        return self.call("POST", url, **kwargs)

    def patch(self, url, **kwargs):
        return self.call("PATCH", url, **kwargs)

    def delete(self, url, **kwargs):
        return self.call("DELETE", url, **kwargs)

    # --- shortcuts that insist on success, for arranging state ---------------------------

    def make_member(self, **overrides) -> dict:
        body = {"name": "Asha Rao", "phone": "+91 00000 20001"} | overrides
        response = self.post("/members", json=body)
        assert response.status_code == 201, response.text
        return response.json()

    def make_item(self, **overrides) -> dict:
        body = {
            "name": "Cordless Drill",
            "category": "Power Tools",
            "replacement_value_paise": 650_000,
        } | overrides
        response = self.post("/items", json=body)
        assert response.status_code == 201, response.text
        return response.json()

    def reserve(self, item_id: int, member_id: int, *, at: datetime = NOW):
        return self.post(f"/items/{item_id}/reservation", json={"member_id": member_id}, at=at)

    def rent(self, item_id: int, member_id: int, *, at: datetime = NOW) -> dict:
        """Reserve and check out at the same moment; returns the checked-out loan."""
        assert self.reserve(item_id, member_id, at=at).status_code == 201
        response = self.post(f"/items/{item_id}/check-out", at=at)
        assert response.status_code == 200, response.text
        return response.json()

    def return_late(self, item_id: int, due_at: datetime, late_by: timedelta) -> dict:
        response = self.post(f"/items/{item_id}/return", at=due_at + late_by)
        assert response.status_code == 200, response.text
        return response.json()


@pytest.fixture
def api(session_factory):
    with TestClient(create_app(session_factory)) as client:
        yield Api(client)


def error_code(response) -> str:
    return response.json()["error"]["code"]
